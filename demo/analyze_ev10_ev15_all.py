"""Analyse full-interface MDF recordings for EV-10 to EV-15.

The script is deliberately conservative: it flags only output changes that are
temporally close to an injected BMS signal edge. A flag is an observation,
not proof of a causal path.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np
from asammdf import MDF


EV_SUFFIXES = {
    "EV-10": ["BMS_BattVolt"],
    "EV-11": ["BMS_DCBusVoltage"],
    "EV-12": ["BMS_BatteryCurrent"],
    "EV-13": ["BMS_MaxChgCurr", "BMS_MaxDischgCurr"],
    "EV-14": [
        "BMS_UnderVoltageSts",
        "BMS_OverVoltageSts",
        "BMS_CellOverVoltageSts",
        "BMS__CellUnderVoltageSts",
    ],
    "EV-15": [
        "BMS_CurrSampleErr",
        "BMS_Currsensor_CommuErr",
        "BMS_OverCurrtSts",
        "BMS_OverChgCurrSts",
    ],
}


def find_channel(names: list[str], suffix: str) -> str | None:
    hits = [name for name in names if name.endswith("." + suffix)]
    if len(hits) != 1:
        return None
    return hits[0]


def compact_values(values: np.ndarray) -> str:
    values = values[np.isfinite(values)]
    uniq = np.unique(values)
    if len(uniq) <= 8:
        return "{" + ", ".join(f"{x:g}" for x in uniq) + "}"
    return f"min={np.min(values):g}; max={np.max(values):g}; distinct={len(uniq)}"


def change_indices(values: np.ndarray) -> np.ndarray:
    if len(values) < 2:
        return np.array([], dtype=int)
    # Ignore numerical solver jitter while retaining real BMS analog/state
    # steps. The tolerance is far below the 10/-10 values used in this test.
    scale = max(1.0, float(np.nanmax(np.abs(values))))
    return np.flatnonzero(np.abs(np.diff(values)) > max(1e-8, scale * 1e-7)) + 1


def format_times(ts: np.ndarray, indices: np.ndarray, origin: float, limit: int = 12) -> str:
    shown = [f"{ts[i] - origin:.3f}" for i in indices[:limit]]
    return ", ".join(shown) + (" …" if len(indices) > limit else "")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mdf", type=Path)
    parser.add_argument("out_dir", type=Path)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    mdf = MDF(args.mdf)
    names = [ch.name for group in mdf.groups for idx, ch in enumerate(group.channels) if idx]
    selected: dict[str, tuple[np.ndarray, np.ndarray]] = {}

    def load(name: str) -> tuple[np.ndarray, np.ndarray]:
        if name not in selected:
            sig = mdf.get(name)
            selected[name] = (np.asarray(sig.timestamps, dtype=float), np.asarray(sig.samples, dtype=float))
        return selected[name]

    injections: list[dict[str, object]] = []
    all_edge_times: list[float] = []
    for ev, suffixes in EV_SUFFIXES.items():
        for suffix in suffixes:
            name = find_channel(names, suffix)
            if name is None:
                injections.append({"ev": ev, "suffix": suffix, "name": "<not found>", "active": False})
                continue
            ts, values = load(name)
            edges = change_indices(values)
            all_edge_times.extend(ts[edges].tolist())
            injections.append(
                {
                    "ev": ev,
                    "suffix": suffix,
                    "name": name,
                    "active": len(edges) > 0,
                    "ts": ts,
                    "values": values,
                    "edges": edges,
                }
            )

    if not all_edge_times:
        raise SystemExit("No EV-10~EV-15 input transitions detected in the MDF.")

    all_edge_times = sorted(set(all_edge_times))
    ref_ts = next(row["ts"] for row in injections if "ts" in row)
    origin = float(ref_ts[0])
    dt = float(np.median(np.diff(ref_ts))) if len(ref_ts) > 1 else float("nan")
    # A one-second causal search window covers five samples even for 200 ms
    # recording; use two samples as a minimum for slower recordings.
    response_window = max(1.0, 2 * dt)

    outputs = [name for name in names if "/OutPort/" in name]
    input_names = {str(row["name"]) for row in injections}
    output_summaries: list[dict[str, object]] = []
    for name in outputs:
        ts, values = load(name)
        edges = change_indices(values)
        near = []
        for event_time in all_edge_times:
            hit = edges[(ts[edges] >= event_time) & (ts[edges] <= event_time + response_window)]
            if len(hit):
                near.extend(hit.tolist())
        near = np.unique(near)
        output_summaries.append(
            {
                "name": name,
                "minimum": float(np.nanmin(values)),
                "maximum": float(np.nanmax(values)),
                "edges": len(edges),
                "near_edges": len(near),
                "near_times": format_times(ts, near, origin),
                "values": compact_values(values),
            }
        )

    # Outputs with transitions near *all* observed edges are usually running
    # signals, not fault responses. Keep only discrete/low-transition signals
    # with one or more transition near an EV edge for the candidate list.
    candidates = [
        row
        for row in output_summaries
        if row["near_edges"] and row["edges"] <= max(8, len(all_edge_times) * 2)
    ]

    csv_path = args.out_dir / "TS-12_EV10-EV15_全接口输出变化筛查.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["输出接口", "最小值", "最大值", "总变化次数", "注入后窗口内变化次数", "窗口内变化时刻_s", "取值摘要"],
        )
        writer.writeheader()
        for row in output_summaries:
            writer.writerow(
                {
                    "输出接口": row["name"],
                    "最小值": f"{row['minimum']:g}",
                    "最大值": f"{row['maximum']:g}",
                    "总变化次数": row["edges"],
                    "注入后窗口内变化次数": row["near_edges"],
                    "窗口内变化时刻_s": row["near_times"],
                    "取值摘要": row["values"],
                }
            )

    lines = [
        "# TS-12 EV-10～EV-15：全接口响应复核",
        "",
        "## 结论",
        "",
        "本次全接口录波中，EV-10～EV-15 的写入是否成功，以各输入通道的实际变化为准。"
        "将每个输入变化时刻后的 %.3f s 设为响应窗口，并扫描所有模型输出接口。" % response_window,
        "候选仅表示时间上相邻的变化，不能单独证明因果；连续变化的行驶量不视为故障响应。",
        "",
        "## 注入通道核验",
        "",
        "|用例|输入信号|实际取值|变化次数|变化时刻（相对录波起点，s）|是否写入|",
        "|---|---|---|---:|---|---|",
    ]
    for row in injections:
        if "ts" not in row:
            lines.append(f"|{row['ev']}|`{row['suffix']}`|通道未找到|—|—|否|")
            continue
        lines.append(
            f"|{row['ev']}|`{row['name']}`|{compact_values(row['values'])}|{len(row['edges'])}|"
            f"{format_times(row['ts'], row['edges'], origin)}|{'是' if row['active'] else '否'}|"
        )

    lines.extend(
        [
            "",
            "## 输出接口筛查结果",
            "",
            f"- 已扫描模型输出接口：{len(outputs)} 个。",
            f"- 输出在任一注入后窗口内发生显著变化：{sum(1 for r in output_summaries if r['near_edges'])} 个。",
            f"- 可作为离散响应候选（低变化次数且时间相邻）：{len(candidates)} 个。",
            "",
        ]
    )
    if candidates:
        lines.extend(
            [
                "|候选输出接口|取值摘要|窗口内变化时刻 (s)|判读|",
                "|---|---|---|---|",
            ]
        )
        for row in candidates:
            lines.append(
                f"|`{row['name']}`|{row['values']}|{row['near_times']}|"
                "仅时间相邻，需与同工况未注入基线复核。|"
            )
    else:
        lines.append("未发现满足筛选条件的离散输出响应候选。")

    lines.extend(
        [
            "",
            "## 判定边界",
            "",
            "若写入通道发生明确阶跃，而与 BMS/MC/高压状态、扭矩、继电器或故障指示有关的输出均未在窗口内出现可重复变化，则本次录波支持“这些暴露的 EV-10～EV-15 输入在当前工况下未接入可观测控制路径”的结论。",
            "这不能证明整个车辆模型不存在电压电流逻辑；仍可能是 CAN 信号未被模型消费、对应工况未使能，或内部变化未映射到外部接口。",
            "",
            f"详细逐接口筛查表：`{csv_path.name}`。",
        ]
    )
    (args.out_dir / "TS-12_EV10-EV15_全接口响应复核.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
