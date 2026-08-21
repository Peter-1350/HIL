"""CASE 扩展：加速踏板单次正弦振荡与速度门控。

所有函数均返回一个 Float，便于在 .case 的 FuncMetadata 中保存至变量。
模块状态只保存“当前一次振荡”的参数与采样序号；每次故障前必须调用
ResetRandomSine()，不可跨故障事件复用状态。
"""

import math
import random
import time


_rng = random.Random()
_state = {
    "center": 30.0,
    "amplitude": 0.0,
    "frequency": 2.0,
    "sample_period_s": 0.020,
    "index": 0,
}
_gate = {
    "target": 0.0,
    "tolerance": 0.1,
    "stable_duration_s": 2.0,
    "deadline": 0.0,
    "stable_since": None,
}
_speed_ready_gate = {
    "minimum_speed": 60.0,
    "stable_duration_s": 1.0,
    "deadline": 0.0,
    "stable_since": None,
}
_stop_gate = {
    "stop_speed": 0.0,
}
_ready_retry = {
    "attempts": 0,
    "max_attempts": 3,
}


def SetRandomSeed(seed=20260821.0):
    """设置可重现实验批次的随机种子，并返回该种子。"""
    _rng.seed(int(seed))
    return float(seed)


def ResetRandomSine(
    center=30.0,
    min_amplitude=2.0,
    max_amplitude=15.0,
    frequency_hz=2.0,
    sample_period_ms=20.0,
):
    """开始一次新的正弦故障，并返回本次随机振幅。

    每次调用会重新抽取振幅。频率、中心值和采样周期由 CASE 固定传入，
    以便第一阶段只回溯振幅。实际标签仍以 Oracle Recorder 录到的序列为准。
    """
    lower = min(float(min_amplitude), float(max_amplitude))
    upper = max(float(min_amplitude), float(max_amplitude))
    _state["center"] = float(center)
    _state["amplitude"] = _rng.uniform(lower, upper)
    _state["frequency"] = max(0.0, float(frequency_hz))
    _state["sample_period_s"] = max(0.001, float(sample_period_ms) / 1000.0)
    _state["index"] = 0
    return _state["amplitude"]


def NextSineSample(dummy=0.0):
    """返回当前振荡点并推进一个固定采样周期，结果限制在踏板 0–100%。"""
    time_s = _state["index"] * _state["sample_period_s"]
    value = _state["center"] + _state["amplitude"] * math.sin(
        2.0 * math.pi * _state["frequency"] * time_s
    )
    _state["index"] += 1
    return max(0.0, min(100.0, value))


def IsNearValue(value=0.0, target=0.0, tolerance=0.1):
    """在 value 位于 target±tolerance 内时返回 1.0，否则返回 0.0。"""
    return 1.0 if abs(float(value) - float(target)) <= abs(float(tolerance)) else 0.0


def ResetNearValueGate(
    target=0.0,
    tolerance=0.1,
    stable_duration_ms=2000.0,
    timeout_ms=30000.0,
):
    """重置“值持续接近目标”的门控状态，返回 0.0（等待中）。"""
    now = time.monotonic()
    _gate["target"] = float(target)
    _gate["tolerance"] = abs(float(tolerance))
    _gate["stable_duration_s"] = max(0.0, float(stable_duration_ms) / 1000.0)
    _gate["deadline"] = now + max(0.0, float(timeout_ms) / 1000.0)
    _gate["stable_since"] = None
    return 0.0


def UpdateNearValueGate(value=0.0):
    """返回 0=继续等待、1=稳定就绪、-1=超时。

    用于 CASE 的 While 条件。它采用执行器单调时钟；在非实时或加速仿真中，
    应用 Oracle 的仿真时间复核门控是否真的持续满足。
    """
    now = time.monotonic()
    if now > _gate["deadline"]:
        return -1.0
    is_near = abs(float(value) - _gate["target"]) <= _gate["tolerance"]
    if not is_near:
        _gate["stable_since"] = None
        return 0.0
    if _gate["stable_since"] is None:
        _gate["stable_since"] = now
        return 1.0 if _gate["stable_duration_s"] == 0.0 else 0.0
    return 1.0 if now - _gate["stable_since"] >= _gate["stable_duration_s"] else 0.0


def ResetVehicleReadyGate(
    speed_target=0.0,
    speed_tolerance=0.1,
    stable_duration_ms=2000.0,
    timeout_ms=30000.0,
):
    """重置“Ready 灯亮且车速稳定”的联合门控，返回 0.0。"""
    return ResetNearValueGate(
        target=speed_target,
        tolerance=speed_tolerance,
        stable_duration_ms=stable_duration_ms,
        timeout_ms=timeout_ms,
    )


def UpdateVehicleReadyGate(speed=0.0, ready_light=0.0):
    """返回 0=继续等待、1=Ready 且车速稳定、-1=超时、-2=Ready 丢失。"""
    now = time.monotonic()
    if now > _gate["deadline"]:
        return -1.0
    if float(ready_light) != 1.0:
        _gate["stable_since"] = None
        return -2.0
    return UpdateNearValueGate(speed)


def ResetSpeedReachedReadyGate(
    minimum_speed=60.0,
    stable_duration_ms=1000.0,
    timeout_ms=90000.0,
):
    """重置“Ready 正常且车速达到下限”的门控。

    与“接近某一固定车速”不同，该门控在车速达到 minimum_speed 后保持
    stable_duration_ms 即通过，因此适用于车辆仍在缓慢加速的工况。
    """
    now = time.monotonic()
    _speed_ready_gate["minimum_speed"] = float(minimum_speed)
    _speed_ready_gate["stable_duration_s"] = max(
        0.0, float(stable_duration_ms) / 1000.0
    )
    _speed_ready_gate["deadline"] = now + max(0.0, float(timeout_ms) / 1000.0)
    _speed_ready_gate["stable_since"] = None
    return 0.0


def UpdateSpeedReachedReadyGate(speed=0.0, ready_light=0.0):
    """返回 0=等待、1=达到目标、-1=超时、-2=Ready 丢失。"""
    now = time.monotonic()
    if now > _speed_ready_gate["deadline"]:
        return -1.0
    if float(ready_light) != 1.0:
        _speed_ready_gate["stable_since"] = None
        return -2.0
    if float(speed) < _speed_ready_gate["minimum_speed"]:
        _speed_ready_gate["stable_since"] = None
        return 0.0
    if _speed_ready_gate["stable_since"] is None:
        _speed_ready_gate["stable_since"] = now
        return 1.0 if _speed_ready_gate["stable_duration_s"] == 0.0 else 0.0
    return (
        1.0
        if now - _speed_ready_gate["stable_since"]
        >= _speed_ready_gate["stable_duration_s"]
        else 0.0
    )


def ResetVehicleStoppedGate(stop_speed=0.0):
    """重置停车门控；该门控不设置超时，避免车辆未停即进入下一轮。"""
    _stop_gate["stop_speed"] = float(stop_speed)
    return 0.0


def UpdateVehicleStoppedGate(speed=0.0):
    """返回 0=继续制动，1=车速已小于等于停车阈值。"""
    return 1.0 if float(speed) <= _stop_gate["stop_speed"] else 0.0


def ResetReadyRetry(ready_light=0.0, max_attempts=3.0):
    """开始一轮上电重试；Ready 已亮时直接返回 1。"""
    _ready_retry["attempts"] = 0
    _ready_retry["max_attempts"] = max(1, int(float(max_attempts)))
    return 1.0 if float(ready_light) == 1.0 else 0.0


def UpdateReadyRetry(ready_light=0.0):
    """登记一次上电结果：1=Ready，0=重试，-1=次数耗尽。"""
    if float(ready_light) == 1.0:
        return 1.0
    _ready_retry["attempts"] += 1
    return (
        -1.0
        if _ready_retry["attempts"] >= _ready_retry["max_attempts"]
        else 0.0
    )
