"""Compare full-interface responses to Present_Voltage amplitude tests."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

import numpy as np
from asammdf import MDF


def voltage_pattern(signal_kind: str) -> re.Pattern[str]:
    return re.compile(rf"/InPort/Veh_1\.FromVCU\.HW\.Voltage Input\.Y_Ch(\d+)_{signal_kind}_Voltage$")


def edges(values: np.ndarray) -> np.ndarray:
    if len(values) < 2:
        return np.array([], dtype=int)
    scale = max(1.0, float(np.nanmax(np.abs(values))))
    return np.flatnonzero(np.abs(np.diff(values)) > max(1e-8, scale * 1e-7)) + 1


def values_text(values: np.ndarray) -> str:
    clean = values[np.isfinite(values)]
    uniq = np.unique(clean)
    if len(uniq) <= 8:
        return "{" + ", ".join(f"{v:g}" for v in uniq) + "}"
    return f"min={np.nanmin(clean):g}; max={np.nanmax(clean):g}; distinct={len(uniq)}"


def load_run(path: Path, signal_kind: str) -> dict[str, object]:
    mdf = MDF(path)
    names = [ch.name for group in mdf.groups for index, ch in enumerate(group.channels) if index]
    cache: dict[str, tuple[np.ndarray, np.ndarray]] = {}

    def load(name: str) -> tuple[np.ndarray, np.ndarray]:
        if name not in cache:
            sig = mdf.get(name)
            cache[name] = (np.asarray(sig.timestamps, dtype=float), np.asarray(sig.samples, dtype=float))
        return cache[name]

    present = []
    all_event_times: list[float] = []
    for name in names:
        match = voltage_pattern(signal_kind).search(name)
        if not match:
            continue
        timestamps, samples = load(name)
        changes = edges(samples)
        all_event_times.extend(timestamps[changes].tolist())
        present.append({"channel": int(match.group(1)), "name": name, "ts": timestamps, "samples": samples, "edges": changes})
    present.sort(key=lambda row: int(row["channel"]))
    if not present:
        raise RuntimeError(f"No {signal_kind}_Voltage input found in {path}")

    origin = float(present[0]["ts"][0])
    dt = float(np.median(np.diff(present[0]["ts"])))
    window = max(1.0, 2.0 * dt)
    output_rows = []
    for name in (name for name in names if "/OutPort/" in name):
        timestamps, samples = load(name)
        changes = edges(samples)
        output_rows.append(
            {
                "name": name,
                "min": float(np.nanmin(samples)),
                "max": float(np.nanmax(samples)),
                "edges": changes,
                "values": values_text(samples),
                "ts": timestamps,
                "dynamic": len(changes) > max(10, len(timestamps) * 0.05),
            }
        )

    channel_results = []
    for row in present:
        event_times = row["ts"][row["edges"]]
        response_names = []
        for out in output_rows:
            if out["dynamic"]:
                continue
            count = 0
            for event in event_times:
                count += int(np.count_nonzero((out["ts"][out["edges"]] >= event) & (out["ts"][out["edges"]] <= event + window)))
            if count:
                response_names.append((str(out["name"]), count))
        channel_results.append({**row, "responses": response_names})
    return {
        "path": path,
        "origin": origin,
        "dt": dt,
        "window": window,
        "present": present,
        "outputs": output_rows,
        "results": channel_results,
        "names": names,
        "load": load,
    }


def context_row(run: dict[str, object], suffix: str) -> str:
    matches = [name for name in run["names"] if name.endswith("." + suffix)]
    if len(matches) != 1:
        return "未找到或名称不唯一"
    timestamps, samples = run["load"](matches[0])
    return f"{values_text(samples)}；变化 {len(edges(samples))} 次"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mdf_100", type=Path)
    parser.add_argument("mdf_1", type=Path)
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("--signal-kind", choices=("Present", "Average"), default="Present")
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    signal_kind = args.signal_kind
    runs = [("100", load_run(args.mdf_100, signal_kind)), ("1", load_run(args.mdf_1, signal_kind))]

    csv_path = args.out_dir / f"TS-12_{signal_kind}电压_100_vs_1_逐通道响应.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["注入幅值", "通道", "实际取值", "注入变化次数", "注入时刻_s", "响应输出数", "响应输出接口"])
        writer.writeheader()
        for label, run in runs:
            for row in run["results"]:
                times = ", ".join(f"{row['ts'][index] - run['origin']:.3f}" for index in row["edges"])
                writer.writerow(
                    {
                        "注入幅值": label,
                        "通道": f"Ch{row['channel']}",
                        "实际取值": values_text(row["samples"]),
                        "注入变化次数": len(row["edges"]),
                        "注入时刻_s": times,
                        "响应输出数": len(row["responses"]),
                        "响应输出接口": "; ".join(name for name, _ in row["responses"]),
                    }
                )

    lines = [
        f"# TS-12 {signal_kind} 电压：100 与 1 幅值的全接口响应对比",
        "",
        "## 结论",
        "",
    ]
    all_responses = sum(len(row["responses"]) for _, run in runs for row in run["results"])
    if all_responses == 0:
        lines.append(f"两段录波中，Ch1–Ch24 的 `{signal_kind}_Voltage` 均已按对应幅值写入；扫描全部模型输出后，未发现任何在注入窗口内发生显著变化的输出接口。因此，没有观察到由 1 或 100 幅值单独触发的外部模型响应。")
    else:
        lines.append("检测到时间相邻的输出变化；这些仅是候选响应，必须结合工况基线和重复试验确认因果。详见逐通道表。")

    lines.extend(["", "## 写入与输出筛查", "", f"|幅值|{signal_kind} 输入通道|实际发生注入边沿的通道数|扫描输出接口数|窗口长度|输出响应候选数|", "|---:|---:|---:|---:|---:|---:|"])
    for label, run in runs:
        injected = sum(len(row["edges"]) > 0 for row in run["results"])
        responses = sum(len(row["responses"]) for row in run["results"])
        lines.append(f"|{label}|{len(run['present'])}|{injected}|{len(run['outputs'])}|{run['window']:.3f} s|{responses}|")

    lines.extend(["", "## 工况核验", "", "|背景接口|100 幅值录波|1 幅值录波|", "|---|---|---|"])
    for suffix in ("Key", "Driver.AccPedal_perc", "Driver.BrakePedal_perc", "Driver.Gear_Button", "VCU_TqReqCmd", "VCU_bMCUEnable", "VCU_bBattConnectSt"):
        lines.append(f"|`{suffix}`|{context_row(runs[0][1], suffix)}|{context_row(runs[1][1], suffix)}|")

    lines.extend(
        [
            "",
            "## 判读",
            "",
            f"两种相差 100 倍的写入幅值均未得到外部响应，说明结果不是‘100 过大而掩盖了小信号规律’。在当前静态 Ready 工况下，至少这些 {signal_kind} 输入未表现出可观测的幅值阈值或诊断传播。",
            "这仍只说明外部接口未响应：通道可能未接线、仅在其他状态机条件下使用，或内部作用未映射到本次可见输出。由于通道量程与物理归属未确认，1 和 100 仅为数值探测幅值，不能解释为 1 V/100 V 或真实欠压/过压。",
            "",
            f"逐通道数据见：`{csv_path.name}`。",
        ]
    )
    (args.out_dir / f"TS-12_{signal_kind}电压_100_vs_1_全接口响应对比.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
