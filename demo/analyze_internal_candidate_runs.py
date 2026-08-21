"""Analyse MI-00 passive screening and FI-09 steering interface injection."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np
from asammdf import MDF


TARGETS = {
    "SteeringWheelAngle_rad": "方向盘转角（Modelbase）",
    "FrontTrqCmd1": "前轴物理扭矩指令",
    "RearTrqCmd": "后轴物理扭矩指令",
    "EPB_Force_RL": "左后 EPB 力",
    "EPB_Force_RR": "右后 EPB 力",
    "Force_SusWext_1L": "左前悬架外力",
    "Force_SusWext_1R": "右前悬架外力",
    "Force_SusWext_2L": "左后悬架外力",
    "Force_SusWext_2R": "右后悬架外力",
    "EPSActuator_AN_IN_PowerSteeringTorque": "EPS 助力转向扭矩",
    "DecelZoneSet": "减速区状态",
}


def threshold(values: np.ndarray) -> float:
    finite = values[np.isfinite(values)]
    if not len(finite):
        return 1e-8
    return max(1e-8, max(1.0, float(np.max(np.abs(finite)))) * 1e-7)


def edges(values: np.ndarray) -> np.ndarray:
    return np.flatnonzero(np.abs(np.diff(values)) > threshold(values)) + 1 if len(values) > 1 else np.array([], dtype=int)


def values_text(values: np.ndarray) -> str:
    finite = values[np.isfinite(values)]
    unique = np.unique(finite)
    if len(unique) <= 8:
        return "{" + ", ".join(f"{value:g}" for value in unique) + "}"
    return f"min={np.min(finite):g}; max={np.max(finite):g}; span={np.max(finite)-np.min(finite):g}"


def load(path: Path) -> tuple[list[str], dict[str, tuple[np.ndarray, np.ndarray]]]:
    mdf = MDF(path)
    names = [channel.name for group in mdf.groups for index, channel in enumerate(group.channels) if index]
    data = {}
    for name in names:
        signal = mdf.get(name)
        data[name] = (np.asarray(signal.timestamps, dtype=float), np.asarray(signal.samples, dtype=float))
    return names, data


def find_suffix(names: list[str], suffix: str) -> str | None:
    matches = [name for name in names if name.endswith("." + suffix)]
    return matches[0] if len(matches) == 1 else None


def time_text(timestamps: np.ndarray, indices: np.ndarray, origin: float) -> str:
    return ", ".join(f"{timestamps[index] - origin:.3f}" for index in indices[:12]) + (" …" if len(indices) > 12 else "")


def analyse_mi(path: Path, out_dir: Path) -> None:
    names, data = load(path)
    origin = min(timestamps[0] for timestamps, _ in data.values())
    rows = []
    for suffix, meaning in TARGETS.items():
        name = find_suffix(names, suffix)
        if name is None:
            rows.append({"接口": suffix, "物理含义": meaning, "已记录": "否", "取值": "—", "变化次数": "—", "被动筛选分级": "未记录"})
            continue
        _, samples = data[name]
        count = len(edges(samples))
        span = float(np.nanmax(samples) - np.nanmin(samples))
        if count == 0 and np.nanmax(np.abs(samples)) <= threshold(samples):
            grade = "S3：当前工况恒零"
        elif count == 0:
            grade = "S2：恒定非零"
        else:
            grade = "S1：存在自然变化"
        rows.append({"接口": name, "物理含义": meaning, "已记录": "是", "取值": values_text(samples), "变化次数": count, "被动筛选分级": grade, "跨度": f"{span:g}"})

    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "MI-00_候选接口被动筛选统计.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=["接口", "物理含义", "已记录", "取值", "跨度", "变化次数", "被动筛选分级"])
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# MI-00 模型内部候选接口：正常运行被动筛选分析",
        "",
        "## 结论",
        "",
        "被动筛选只能用于确定下一步单通道注入优先级；接口自然变化不等于其下游已实现，接口恒零也不等于模型未连接。",
        "",
        "## 候选接口表现",
        "",
        "|候选接口|物理含义|实际取值|变化次数|筛选结论|",
        "|---|---|---|---:|---|",
    ]
    for row in rows:
        if row["已记录"] == "否":
            lines.append(f"|`{row['接口']}`|{row['物理含义']}|未记录|—|未能筛选|")
        else:
            lines.append(f"|`{row['接口']}`|{row['物理含义']}|{row['取值']}|{row['变化次数']}|{row['被动筛选分级']}|")
    s1 = [row for row in rows if str(row.get("被动筛选分级", "")).startswith("S1")]
    lines.extend(["", "## 下一步", ""])
    if s1:
        lines.append("优先对以下 S1 接口做单通道阶跃/冻结注入：" + "、".join(f"`{row['接口']}`" for row in s1) + "。")
    else:
        lines.append("本段录波中没有记录到可直接升级为 S1 的候选接口；需要按每个接口对应的激励工况重新录波，或先做小阶跃可达性验证。")
    lines.extend(["", "详细统计见：`MI-00_候选接口被动筛选统计.csv`。"])
    (out_dir / "MI-00_模型内部候选接口被动筛选分析.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def analyse_fi09(path: Path, out_dir: Path) -> None:
    names, data = load(path)
    steering = find_suffix(names, "SteeringWheelAngle_rad")
    if steering is None:
        raise RuntimeError("FI-09 MDF does not contain SteeringWheelAngle_rad")
    timestamps, steering_values = data[steering]
    origin = float(timestamps[0])
    steering_edges = edges(steering_values)
    dt = float(np.median(np.diff(timestamps))) if len(timestamps) > 1 else 0.02
    window = max(1.0, 2 * dt)

    candidates = []
    context = []
    for name, (ts, samples) in data.items():
        if name == steering:
            continue
        change = edges(samples)
        dynamic = len(change) > max(10, len(samples) * 0.05)
        near = []
        for event in timestamps[steering_edges]:
            near.extend(change[(ts[change] >= event) & (ts[change] <= event + window)].tolist())
        near = np.unique(near)
        summary = {"name": name, "values": values_text(samples), "edges": len(change), "near": len(near), "dynamic": dynamic, "near_times": time_text(ts, near, origin)}
        if len(near) and not dynamic:
            candidates.append(summary)
        if name.endswith((".Key", ".Driver.AccPedal_perc", ".Driver.BrakePedal_perc", ".Driver.Gear_Button", ".VCU_TqReqCmd")):
            context.append(summary)

    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "FI-09_转向角注入响应筛查.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=["候选输出接口", "取值摘要", "总变化次数", "注入后窗口内变化次数", "窗口内变化时刻_s", "判定"])
        writer.writeheader()
        for row in candidates:
            writer.writerow({"候选输出接口": row["name"], "取值摘要": row["values"], "总变化次数": row["edges"], "注入后窗口内变化次数": row["near"], "窗口内变化时刻_s": row["near_times"], "判定": "时间相邻，需复验"})

    lines = [
        "# FI-09 转向角内部接口：单通道可达性分析",
        "",
        "## 注入核验",
        "",
        f"- 注入接口：`{steering}`",
        f"- 实际取值：{values_text(steering_values)}",
        f"- 注入边沿数：{len(steering_edges)}；相对录波起点时刻：{time_text(timestamps, steering_edges, origin)} s",
        f"- 分析窗口：每个转向角边沿后的 {window:.3f} s。",
        "",
        "## 响应结论",
        "",
    ]
    if candidates:
        lines.append(f"发现 {len(candidates)} 个非连续信号在转向角边沿后发生变化；它们仅为时间相邻候选，尚不能证明转向角因果传播。")
        lines.extend(["", "|候选接口|取值摘要|窗口内变化时刻 (s)|", "|---|---|---|"])
        for row in candidates:
            lines.append(f"|`{row['name']}`|{row['values']}|{row['near_times']}|")
    else:
        lines.append("未发现非连续模型输出在转向角注入边沿后发生变化；现有录波未提供转向角到顶层可见输出的可达性证据。")
    lines.extend(["", "## 工况背景", "", "|接口|取值摘要|变化次数|", "|---|---|---:|"])
    for row in context:
        lines.append(f"|`{row['name']}`|{row['values']}|{row['edges']}|")
    lines.extend([
        "",
        "## 判定边界",
        "",
        "转向角的主要物理效应应优先体现为横摆角速度、侧向加速度、横向速度、轮胎侧向力或前轮转角。若本次未记录这些量，即使车速、前后电机转速不变，也不能判定转向支路未实现。",
        "详细筛查见：`FI-09_转向角注入响应筛查.csv`。",
    ])
    (out_dir / "FI-09_转向角内部接口单通道探测分析.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mi_mdf", type=Path)
    parser.add_argument("fi09_mdf", type=Path)
    parser.add_argument("out_root", type=Path)
    args = parser.parse_args()
    analyse_mi(args.mi_mdf, args.out_root / "MI_report" / "MI-00_模型内部候选接口_正常运行被动筛选")
    analyse_fi09(args.fi09_mdf, args.out_root / "FI_report" / "FI-09")


if __name__ == "__main__":
    main()
