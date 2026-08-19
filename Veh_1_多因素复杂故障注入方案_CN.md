# Veh_1 多因素复杂故障注入方案（不依赖 CAN 扭矩请求注入）

## 1. 目的与约束

本方案将已验证可写入的驾驶员层接口组合为状态相关、时序相关和相互矛盾的复杂故障工况，用于验证车辆模型的制动优先、挡位互锁、钥匙上下电和故障恢复行为。

**硬性约束：不修改、不要求固定、也不将 `VCU_TqReqCmd` 作为试验前提。**该信号受 CAN 通信模型控制，目前不可注入；本方案的判定依据改为实际电机扭矩、母线电流、车速、继电器及主辅模拟量输出。若录波中存在 VCU 扭矩相关报文，可仅作为背景信息，不作为因果或通过判据。

当前 BMS 电压/电流与通用电压通道未发现对已记录输出的传播路径，故不纳入本阶段复杂故障源。它们仍可作为后续模型完善后的独立验证对象。

## 2. 可控注入接口

| 接口 | 角色 | 本方案用途 | 已知限制 |
| --- | --- | --- | --- |
| `Veh_1.Driver.AccPedal_perc` | 油门踏板百分比 | 卡滞、持续请求、松油门后残留 | 已验证可映射至 ACC 主/辅模拟量输出。 |
| `Veh_1.Driver.BrakePedal_perc` | 制动踏板百分比 | 制动请求、制动信号突失、与油门矛盾 | 已验证可映射至 BRK 主/辅模拟量和制动继电器。 |
| `Veh_1.Driver.Gear_Button` | 挡位码 | 跳变、候选非法码、驱动/抑制互锁 | 码值业务含义未取得；只按已观测码值行为描述。 |
| `Veh_1.Driver.Key` | 钥匙状态 | 突然熄火、失灵脉冲、恢复互锁 | 已验证会影响 `Model_Disabled_Out`。 |
| `Veh_1.Driver.BrakeMode` | 制动模式码 | 模式冻结与制动请求的组合 | 仅验证过固定为 0；枚举语义未知。 |
| `Veh_1.Driver.DriveMode` | 驾驶模式码 | 仅作工况记录/后续扩展 | 枚举和传播关系未确认，本轮不改写。 |

## 3. 通用工况与中止条件

### 3.1 驱动稳态前提

除 CF-06 外，各用例在以下前提成立后才开始注入：

```text
Key = 1
Gear_Button = 1（本方案中作为已观测到的驱动码；不解释为具体挡位名称）
AccPedal_perc = 50%
BrakePedal_perc = 0%
车辆已达到稳定正向速度，且前/后实际扭矩与 MC 母线电流连续 3 s 无明显跃变
```

不使用“油门不变”代替稳态判据；应以实际扭矩、母线电流和车速曲线判断。若基线阶段本身发生明显状态切换，应中止该次记录并重新建立基线。

### 3.2 中止与恢复

出现以下任一条件，立即停止后续阶段，恢复安全基线并继续录制至少 5 s：

- `Model_Disabled` 或 `Model_Reset` 非预期变化；
- 高压控制命令持续抖动、模型停止或录波中断；
- 车速/实际扭矩出现与注入序列无关的显著突变；
- 用例规定的恢复后仍存在未预期的持续驱动或继电器保持。

安全基线：`AccPedal_perc=0`、`BrakePedal_perc=0`、`Gear_Button=0`、`Key=0`。该动作仅作用于 HIL 仿真模型。

## 4. 统一待测接口集

### 4.1 必录上下文与注入接口

```text
Model_Disabled
Model_Reset
Veh_1.Driver.Key
Veh_1.Driver.Gear_Button
Veh_1.Driver.AccPedal_perc
Veh_1.Driver.BrakePedal_perc
Veh_1.Driver.BrakeMode
Veh_1.Driver.DriveMode
测试编号、阶段、原始值、注入值、恢复值、开始/结束时间
```

### 4.2 必录执行与动力响应

```text
Veh_1.ToVCU.HW.Voltage Output.Voltage Output1.BRK_Main_Out
Veh_1.ToVCU.HW.Voltage Output.Voltage Output5.BRK_Auxi_Out
Veh_1.ToVCU.HW.Relay.Relay9.BrakeOpen1_Out
Veh_1.ToVCU.HW.Relay.Relay12.BrakeOpen2_Out
Veh_1.ToVCU.HW.Voltage Output.Voltage Output7.ACC_Main_Out_Out
Veh_1.ToVCU.HW.Voltage Output.Voltage Output8.ACC_Auxi_Out_Out
Veh_1.ToVCU.HW.Relay.Relay25.Model_Disabled_Out
Veh_1.PlantModel.PlantModel.Powertrain.FMotor.Motor.MotTrq
Veh_1.PlantModel.PlantModel.Powertrain.RMotor.Motor.MotTrqManagement.RTrq
Veh_1.PlantModel.PlantModel.Driveline.RearMotSpd
Veh_1.PlantModel.PlantModel.Vehicle1.Vehspeed 
Veh_1.ToVCU.powerCAN_out.SoftMCUDataToBus.MC_motor_Torque_AND_speed.MC_motor_Torque_ToBus
Veh_1.ToVCU.powerCAN_out.SoftMCUDataToBus.MC_motor_Torque_AND_speed.MC_busbar_current_ToBus
Veh_1.ToVCU.powerCAN_out.SoftBMSDataToBus.BMS_HVBusVolt_Curr.BMS_HVBusCurr_ToBus
Veh_1.ToVCU.powerCAN_out.SoftMCUDataToBus.MC_General.MC_system_Fault_level_ToBus
```

`Vehspeed ` 的接口名末尾带一个空格，应直接从信号浏览器复制到录波配置，避免手工输入时丢失空格。

## 5. 多因素用例

### CF-01：油门卡滞与制动请求冲突

**故障目的**：验证制动请求是否能够覆盖持续的加速请求，以及油门卡滞恢复后是否存在残余驱动。

| 阶段 | 注入接口和值 | 保持时间 | 预期观察 |
| --- | --- | ---: | --- |
| 基线 | `Acc=50`、`Brake=0`、`Gear=1`、`Key=1` | ≥3 s | ACC 主/辅输出稳定，存在正向驱动。 |
| A：油门卡滞 | 保持 `Acc=50`，标记为冻结；其他不变 | 3 s | 确认持续加速请求成立。 |
| B：制动叠加 | `Brake: 0→50` | 3 s | BRK 主/辅输出和双继电器应激活；观察实际扭矩/电流是否撤除或下降。 |
| C：紧急制动 | `Brake: 50→100`，`Acc` 仍固定 50 | 3 s | 观察制动优先、扭矩和车速响应。 |
| D：部分恢复 | `Brake: 100→0`，`Acc` 仍固定 50 | 3 s | 验证油门卡滞的残余驱动是否重新出现。 |
| E：完全恢复 | `Acc: 50→0` | ≥5 s | 输出、电流和车速行为恢复至无驱动状态。 |

**判定重点**：在 B/C 阶段，不能只看 BRK 输出是否变化；还应确认实际扭矩与母线电流不会保持不受控的正向驱动。

### CF-02：油门卡滞下的挡位抑制码短脉冲

**故障目的**：验证车辆在持续加速请求下，对已观测到可抑制动力的挡位码切换是否安全、可恢复。

FI-04 的 20 ms 记录显示，码 `2` 或 `3` 与实际扭矩/电流快速撤除同现；本方案仅将其称为“抑制码”，不解释其具体挡位语义。

| 阶段 | 注入接口和值 | 保持时间 | 预期观察 |
| --- | --- | ---: | --- |
| 基线 / A | 同 CF-01 的 `Acc=50` 卡滞状态 | ≥3 s | 实际扭矩、电流和车速稳定。 |
| B：挡位脉冲 | `Gear_Button: 1→2→1` | 码 2 保持 1 s；恢复后 3 s | 观察实际扭矩、电流是否受抑制，恢复 1 后是否受控恢复。 |
| C：重复 | `Gear_Button: 1→3→1` | 同上 | 对比码 2 与码 3 的响应和恢复延迟。 |
| D：解除卡滞 | `Acc: 50→0` | ≥5 s | 确认无残余动力。 |

**判定重点**：实际扭矩与母线电流的变化应在挡位边沿后出现；若在边沿前已变化，本轮不做因果判定。

### CF-03：候选非法挡位码与持续加速请求

**故障目的**：复核 FI-04 中码 `5`、`-1` 在持续加速下仍保持正向驱动的风险迹象。

| 阶段 | 注入接口和值 | 保持时间 | 预期观察 |
| --- | --- | ---: | --- |
| 基线 / A | `Key=1`、`Gear=1`、`Acc=50`、`Brake=0` | ≥3 s | 建立正常驱动基线。 |
| B | `Gear_Button: 1→5` | 3 s | 记录扭矩、电流、车速是否受抑制。 |
| C | `Gear_Button: 5→-1` | 3 s | 记录码切换后的动力状态。 |
| D | `Gear_Button: -1→1` | 3 s | 记录恢复轨迹。 |
| E | `Acc: 50→0` | ≥5 s | 结束并确认无残余驱动。 |

**判定重点**：在取得挡位枚举前，不将 `5/-1` 正式称为非法码；若项目定义确认其为非法而仍持续驱动，应升级为高优先级安全问题。

### CF-04：行驶中钥匙失灵脉冲与油门卡滞

**故障目的**：验证钥匙突然失效或短暂恢复时，模型禁用、高压控制和动力输出的时序，以及恢复后是否错误地在油门持续请求下直接恢复驱动。

| 阶段 | 注入接口和值 | 保持时间 | 预期观察 |
| --- | --- | ---: | --- |
| 基线 / A | `Key=1`、`Gear=1`、`Acc=50`、`Brake=0` | ≥3 s | 正常驱动基线。 |
| B：失灵脉冲 | `Key: 1→0→1`；0 保持 200 ms | 恢复后 ≥5 s | `Model_Disabled_Out`、实际扭矩、电流、车速和继电器输出的撤除/恢复次序。 |
| C：卡滞解除 | `Acc: 50→0` | ≥5 s | 验证恢复后不应遗留持续动力。 |

**判定重点**：钥匙脉冲时，油门保持 50%，因而恢复阶段是对“重新使能门控”的检验；不能只根据 Key 回到 1 判断恢复成功。

### CF-05：制动信号突失与油门卡滞的序列故障

**故障目的**：模拟制动输入已经有效、随后信号突然丢失，同时加速请求保持的危险序列；验证制动输出、动力恢复和车辆惯性之间的关系。

| 阶段 | 注入接口和值 | 保持时间 | 预期观察 |
| --- | --- | ---: | --- |
| 基线 / A | `Key=1`、`Gear=1`、`Acc=50`、`Brake=0` | ≥3 s | 正常驱动。 |
| B：制动请求 | `Brake: 0→100`，`Acc` 仍为 50 | 3 s | 双 BRK 输出和制动继电器激活；实际扭矩/电流下降。 |
| C：制动信号突失 | `Brake: 100→0`，`Acc` 仍固定 50 | 3 s | 观察制动执行撤除后动力是否按模型设计恢复。 |
| D：解除油门卡滞 | `Acc: 50→0` | ≥5 s | 结束。 |

**说明**：该用例模拟的是“模型所接收的制动信号突失”，不等同于现实车辆机械制动已经失效；真实机械制动状态未由此接口表达。

### CF-06：挡位抑制状态中的钥匙脉冲与恢复互锁

**故障目的**：在已抑制动力的状态下引入钥匙脉冲，检查 Key 恢复后是否错误绕过挡位互锁而立即恢复驱动。

| 阶段 | 注入接口和值 | 保持时间 | 预期观察 |
| --- | --- | ---: | --- |
| 基线 | `Key=1`、`Gear=1`、`Acc=50`、`Brake=0` | ≥3 s | 正常驱动。 |
| A：进入抑制码 | `Gear: 1→2` | 2 s | 确认实际扭矩/电流进入已观测抑制状态。 |
| B：钥匙脉冲 | `Key: 1→0→1`，`Gear` 维持 2，0 保持 200 ms | 恢复后 3 s | 检查 `Model_Disabled_Out` 与动力是否仍被挡位状态抑制。 |
| C：显式恢复挡位 | `Gear: 2→1` | 3 s | 仅在恢复码 1 后观察动力恢复。 |
| D：结束 | `Acc: 50→0` | ≥5 s | 确认无残余动力。 |

## 6. 脚本逻辑总览

脚本只写入第 2 节的驾驶员层接口；不得向任何 `VCU_TqReqCmd` 接口写值。建议将每个用例编排为阶段化事件表，而不是并发随机赋值。

```python
def run_complex_case(case):
    connect_from_config()                       # IP、工程和权限均从配置读取
    restore_safe_baseline()                     # Acc=0, Brake=0, Gear=0, Key=0
    apply(case.preconditions)                   # 建立 Key/Gear/Acc 驱动工况
    wait_until_drive_state_stable(min_s=3)      # 根据实际扭矩、电流、车速判定

    recorder_start(case.record_signals, dt_s=0.02)
    try:
        for phase in case.phases:
            write_only(phase.injection_values) # 一次写入该阶段定义的驾驶员接口
            hold(phase.duration_s)
            annotate(phase.name, phase.values)
            if abort_condition_detected():
                break
    finally:
        restore_safe_baseline()
        hold(5)
        recorder_stop()
        export_metadata_and_log()
```

`wait_until_drive_state_stable()` 不读取或控制 `VCU_TqReqCmd`；应使用实际扭矩、MC/BMS 母线电流和车速的最近 3 s 波动范围判断。每个阶段均需写入日志模板中的 `InjectionMode`、`InterfaceName`、`OriginalValue`、`InjectedValue`、`RecoveredValue`、`ResponseDelay` 与 `RecoveryDelay`。

## 7. 记录与结论规则

1. 任一用例至少重复 3 次；对每次试验单独输出事件时序，禁止把多次运行直接拼接。
2. 先证明输入值已写入，再判断执行器响应，最后判断车速和能量响应；三层结论不能混用。
3. 未记录实际扭矩、电流或继电器时，不判定“安全响应通过”。
4. 挡位码只按数据中已观测到的响应分类；取得 DBC/枚举后再映射为具体挡位与非法码。
5. 若 CAN 控制导致试验期间存在不可解释的扭矩变化，则标记为“CAN 背景混杂，因果未判定”，而非归因于故障接口。
