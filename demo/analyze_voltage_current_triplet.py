"""Inventory voltage/current fault recordings across env, net and Veh models.

The recordings are separate experiments, so the program keeps every conclusion
within a single MDF file.  It reports observed input edges and only treats a
downstream edge shortly afterwards as a response *candidate*.
"""

from __future__ import annotations

import argparse
import csv
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from asammdf import MDF


ROOT = Path(__file__).resolve().parents[1]
RECORDINGS = (
    ("env", "others", ROOT / "EA_program/test01/.hlt/Caches/Recorder/环境通道_all/others_env_2.mdf"),
    ("env", "average", ROOT / "EA_program/test01/.hlt/Caches/Recorder/环境通道_all/average_Voltage_env_1.mdf"),
    ("env", "present", ROOT / "EA_program/test01/.hlt/Caches/Recorder/环境通道_all/present_Voltage_env_0.mdf"),
    ("net", "others", ROOT / "EA_program/test01/.hlt/Caches/Recorder/网络模型_all/others_net_2.mdf"),
    ("net", "average", ROOT / "EA_program/test01/.hlt/Caches/Recorder/网络模型_all/average_Voltage_net_1.mdf"),
    ("net", "present", ROOT / "EA_program/test01/.hlt/Caches/Recorder/网络模型_all/present_Voltage_net_0.mdf"),
    ("Veh", "others", Path(r"D:\TOOL\KunyiSoftwares\VcarEERecorder\recorder_root\Veh_1_all\others_Veh_3.mdf")),
    ("Veh", "average", Path(r"D:\TOOL\KunyiSoftwares\VcarEERecorder\recorder_root\Veh_1_all\average_Voltage_Veh_2.mdf")),
    ("Veh", "present", Path(r"D:\TOOL\KunyiSoftwares\VcarEERecorder\recorder_root\Veh_1_all\present_Voltage_Veh_1.mdf")),
)

VOLTAGE_CURRENT = re.compile(r"(?:voltage|volt|current|curr|ch\d+_(?:present|average))", re.I)


@dataclass
class Signal:
    name: str
    timestamps: np.ndarray
    values: np.ndarray
    edges: np.ndarray
    threshold: float


def all_names(mdf: MDF) -> list[str]:
    return [channel.name for group in mdf.groups for index, channel in enumerate(group.channels) if index]


def direction(name: str) -> str:
    if "/InPort/" in name:
        return "输入"
    if "/OutPort/" in name:
        return "输出"
    return "内部/未标记"


def edge_indices(values: np.ndarray) -> tuple[np.ndarray, float]:
    if len(values) < 2:
        return np.array([], dtype=int), float("nan")
    if not np.issubdtype(values.dtype, np.number):
        return np.flatnonzero(values[1:] != values[:-1]) + 1, float("nan")
    finite = values[np.isfinite(values)]
    if not len(finite):
        return np.array([], dtype=int), float("nan")
    # Recorder values are mostly piecewise constant.  This removes binary
    # floating-point noise without hiding a deliberate injection step.
    threshold = max(1e-8, max(1.0, float(np.max(np.abs(finite)))) * 1e-7)
    return np.flatnonzero(np.abs(np.diff(values)) > threshold) + 1, threshold


def load(mdf: MDF, name: str) -> Signal:
    signal = mdf.get(name)
    values = np.asarray(signal.samples)
    timestamps = np.asarray(signal.timestamps, dtype=float)
    edges, threshold = edge_indices(values)
    return Signal(name, timestamps, values, edges, threshold)


def values_summary(values: np.ndarray) -> str:
    if not np.issubdtype(values.dtype, np.number):
        unique = np.unique(values)
        if len(unique) <= 8:
            return "{" + ", ".join(item.decode(errors="replace") if isinstance(item, bytes) else str(item) for item in unique) + "}"
        return f"distinct={len(unique)}"
    finite = values[np.isfinite(values)]
    if not len(finite):
        return "无有效样本"
    unique = np.unique(finite)
    if len(unique) <= 8:
        return "{" + ", ".join(f"{value:g}" for value in unique) + "}"
    return f"min={np.min(finite):g}; max={np.max(finite):g}; distinct={len(unique)}"


def time_summary(signal: Signal, origin: float, limit: int = 10) -> str:
    items = [f"{signal.timestamps[index] - origin:.3f}" for index in signal.edges[:limit]]
    return ", ".join(items) + (" …" if len(signal.edges) > limit else "")


def near_count(source: Signal, target: Signal, window: float) -> tuple[int, str]:
    if not len(source.edges) or not len(target.edges):
        return 0, ""
    source_times = source.timestamps[source.edges]
    target_times = target.timestamps[target.edges]
    hits = []
    for event in source_times:
        matching = target_times[(target_times >= event) & (target_times <= event + window)]
        hits.extend(matching.tolist())
    hits = np.unique(hits)
    origin = source.timestamps[0]
    shown = ", ".join(f"{item - origin:.3f}" for item in hits[:10])
    return len(hits), shown + (" …" if len(hits) > 10 else "")


def analyse_one(layer: str, case: str, path: Path, out_dir: Path) -> dict[str, object]:
    mdf = MDF(path)
    names = all_names(mdf)
    signals = [load(mdf, name) for name in names]
    origin = min((signal.timestamps[0] for signal in signals if len(signal.timestamps)), default=0.0)
    dts = [float(np.median(np.diff(signal.timestamps))) for signal in signals if len(signal.timestamps) > 1]
    dt = float(np.median(dts)) if dts else float("nan")
    window = max(0.2, 2 * dt) if np.isfinite(dt) else 1.0

    signal_rows = []
    for signal in signals:
        numeric = np.issubdtype(signal.values.dtype, np.number)
        finite = signal.values[np.isfinite(signal.values)] if numeric else np.array([])
        signal_rows.append({
            "层": layer,
            "录波": case,
            "方向": direction(signal.name),
            "接口": signal.name,
            "最小值": f"{np.min(finite):g}" if len(finite) else "",
            "最大值": f"{np.max(finite):g}" if len(finite) else "",
            "变化次数": len(signal.edges),
            "变化时刻_s": time_summary(signal, origin),
            "取值摘要": values_summary(signal.values),
            "电压电流相关": "是" if VOLTAGE_CURRENT.search(signal.name) else "否",
        })

    # Only model input ports can prove that a fault was written.  The env
    # recorder exposes the analog signals as outputs, and those must never be
    # misclassified as an injection merely because their names contain Volt.
    candidates = [
        signal for signal in signals
        if direction(signal.name) == "输入" and VOLTAGE_CURRENT.search(signal.name) and len(signal.edges)
    ]
    outputs = [signal for signal in signals if direction(signal.name) == "输出"]
    responses = []
    for injected in candidates:
        for output in outputs:
            count, times = near_count(injected, output, window)
            # Rapidly changing continuous quantities (motor speed etc.) are
            # recorded separately but not offered as a causal candidate.
            if count and len(output.edges) <= max(12, len(injected.edges) * 3):
                responses.append({
                    "层": layer,
                    "录波": case,
                    "注入候选接口": injected.name,
                    "注入取值": values_summary(injected.values),
                    "注入边沿数": len(injected.edges),
                    "响应候选接口": output.name,
                    "响应取值": values_summary(output.values),
                    "响应总边沿数": len(output.edges),
                    "注入后窗口内边沿数": count,
                    "响应时刻_s": times,
                    "判读": "仅时间相邻；需重复工况验证因果",
                })

    stem = f"TS-13_{layer}_{case}"
    with (out_dir / f"{stem}_全接口统计.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(signal_rows[0]))
        writer.writeheader()
        writer.writerows(signal_rows)
    with (out_dir / f"{stem}_响应候选.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        fields = list(responses[0]) if responses else ["层", "录波", "注入候选接口", "注入取值", "注入边沿数", "响应候选接口", "响应取值", "响应总边沿数", "注入后窗口内边沿数", "响应时刻_s", "判读"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(responses)
    return {
        "layer": layer, "case": case, "path": path, "channels": len(signals), "inputs": candidates,
        "outputs": outputs, "responses": responses, "dt": dt, "window": window,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, default=ROOT / "output/TS_report/TS-13-全层电压电流故障")
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    results = [analyse_one(layer, case, path, args.out_dir) for layer, case, path in RECORDINGS]

    overview = []
    for result in results:
        overview.append({
            "层": result["layer"], "录波": result["case"], "文件": str(result["path"]), "接口数": result["channels"],
            "电压电流输入边沿接口数": len(result["inputs"]), "输出接口数": len(result["outputs"]),
            "响应候选对数": len(result["responses"]), "采样周期_s": f"{result['dt']:.6g}", "响应窗口_s": f"{result['window']:.6g}",
        })
    with (args.out_dir / "TS-13_录波覆盖与响应总表.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(overview[0]))
        writer.writeheader()
        writer.writerows(overview)

    lines = [
        "# TS-13 全层电压/电流故障注入：原始录波筛查",
        "",
        "本报告对 env、net 和 Veh 三层的九段录波分别分析，避免把不同实验段的绝对时间直接拼接。输入边沿证明写入发生；输出边沿仅在其后一个响应窗口内才列为候选，仍不能独自证明因果。",
        "",
        "## 录波覆盖与初筛",
        "",
        "|层|录波|接口数|发生边沿的电压/电流输入接口数|输出接口数|时间相邻响应候选对数|采样周期|响应窗口|",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in overview:
        lines.append(f"|{row['层']}|{row['录波']}|{row['接口数']}|{row['电压电流输入边沿接口数']}|{row['输出接口数']}|{row['响应候选对数']}|{row['采样周期_s']} s|{row['响应窗口_s']} s|")
    lines.extend([
        "",
        "## 使用边界",
        "",
        "- `present`、`average` 录波用于判断模拟电压通道写入和接口响应；`others` 录波用于判断其他电压/电流类输入（包括 CAN 量值或状态）是否实际变化。",
        "- 若某录波不存在 `InPort`/`OutPort` 标记，统计表仍保留该信号，但本脚本不会将其自动解释为注入或外部响应。",
        "- `响应候选.csv` 中的记录只代表时间上的先后相邻。故障结论还应同时满足：注入幅值/状态码已确认、响应方向合理、且在重复试验或同工况基线中可复现。",
        "",
        "## 文件说明",
        "",
        "- `TS-13_录波覆盖与响应总表.csv`：九段录波的总览。",
        "- 每段录波的 `全接口统计.csv`：所有已记录接口、范围、边沿与电压/电流相关标记。",
        "- 每段录波的 `响应候选.csv`：过滤连续运行量后留下的时间相邻候选。",
    ])
    (args.out_dir / "TS-13_全层电压电流故障注入初筛.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
