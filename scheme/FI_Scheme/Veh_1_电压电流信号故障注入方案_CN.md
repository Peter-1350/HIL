# Veh_1 电压/电流信号故障注入实验方案

## 1. 目标与边界

本方案从驾驶员层输入故障扩展到能源系统接口层，覆盖模拟电压采样、BMS 电压/电流报文、BMS 限流与故障状态，以及 DC/DC 电压控制命令。目标是验证：量值异常能否被检测、能量和扭矩能否进入预期降级状态，以及故障清除后是否正确恢复或锁存。

`Veh_1` 顶层中，以下两类信号必须严格区分：

- **可注入输入**：`Veh_1.FromVCU...`，可通过 HIL/SDK 写入。
- **观测输出**：`Veh_1.ToVCU...`，如 `BMS_HVBusVolt_ToBus`；它们是模型计算结果，不能直接作为顶层注入点。

当前静态依赖解析没有找到 24 路硬件模拟电压输入到外部输出的确定数据路径。因此，Ch1–Ch24 的实际业务含义尚未确认；必须先做 EV-00 通道探测，不能直接假设某个 ChN 就是高压、电池或低压传感器。

## 2. 接口分层

| 层级 | 用途 | 可注入接口 | 说明 |
| --- | --- | --- | --- |
| 硬件模拟量 | 传感器电压采样故障 | `Veh_1.FromVCU.HW.Voltage Input.Y_ChN_Present_Voltage`、`Veh_1.FromVCU.HW.Voltage Input.Y_ChN_Average_Voltage`，`N=1…24` | 48 个 `Double` 输入；通道功能未知，先探测。 |
| BMS 测量报文 | 电池包/直流母线电压和电流测量错误 | `...GW_BMS_3.BMS_BattVolt`、`...GW_BMS_3.BMS_DCBusVoltage`、`...GW_BMS_3.BMS_BatteryCurrent` | `FromVCU.CAN` 顶层输入；需依据 DBC 确认单位、缩放、有效范围和电流正负方向。 |
| BMS 能力/诊断报文 | 限流、欠压、过压、采样故障 | `...GW_BMS_1.BMS_MaxChgCurr`、`...BMS_MaxDischgCurr`；`...GW_BMS_7.BMS_UnderVoltageSts`、`BMS_OverVoltageSts`、`BMS_OverCurrtSts` 等 | 状态码的 0/1/枚举含义需 DBC 确认。 |
| DC/DC 控制报文 | 输出电压请求或限值异常 | `...VCU_DCDC_Ctrl.VCU_DCDC_output_voltage_request`、`...VCU_DCDC_max_output_volt_Limit`、`...VCU_DCDC_min_out_volt_Limit` | 属于**命令异常**，不是传感器测量异常。 |

下文中以 `V0`、`I0` 表示该信号在稳定基线窗口的中位数；以 `Vmin`、`Vmax`、`Imin`、`Imax` 表示 DBC/标定确认后的工程边界。所有写入值必须先经过这些边界约束。

## 3. 故障用例矩阵

### 3.1 阶段 A：硬件模拟电压通道探测与故障

| 编号 | 故障类型 | 注入接口 | 注入值/波形 | 目的与判定 |
| --- | --- | --- | --- | --- |
| EV-00 | 通道功能探测 | 对每个 `N=1…24`，先写 `Y_ChN_Present_Voltage`，再写 `Y_ChN_Average_Voltage` | 基线 2 s；单变量阶跃 `x=V0±10%×(Vmax-Vmin)` 保持 2 s；恢复 3 s。每次只改一个标量。 | 找到发生变化的继电器、模拟量、CAN 状态或诊断输出，建立 ChN→功能映射。无响应不等于通道无效，可能仅在特定工况使用。 |
| EV-01 | 同步欠压/掉零 | 已映射的 ChN 的 Present 与 Average | `Present=Average=max(Vmin,V0-20%×(Vmax-Vmin))`；可追加 `Vmin` 保持 3 s。 | 验证低压阈值、降级动作、诊断与恢复。 |
| EV-02 | 同步过压 | 已映射的 ChN 的 Present 与 Average | `Present=Average=min(Vmax,V0+20%×(Vmax-Vmin))`；不得写入超过 DBC 物理上限的值。 | 验证过压检测及执行器安全状态。 |
| EV-03 | 瞬时/平均值不一致 | 已映射的 ChN 对 | `Present=V0-20%量程`，`Average=V0`，保持 3 s；随后交换两者。 | 验证双通道交叉检查或滤波一致性诊断。 |
| EV-04 | 卡滞/冻结 | 已映射的 ChN 对 | 在正常变化工况采样 `Vhold=V(t0)`，两个量固定为 `Vhold` 5–10 s；随后恢复实时基线。 | 验证信号新鲜度、合理性检查和恢复策略。 |
| EV-05 | 抖动/噪声 | 已映射的 ChN 对 | `x(t)=clamp(V0+0.05×量程×square(5 Hz),Vmin,Vmax)`，持续 5 s；Present/Average 同步或仅 Present 抖动各做一次。 | 验证去抖、滤波及误触发风险。20 ms 采样下建议不高于 5 Hz。 |

“丢帧”不能仅靠写固定数值模拟；若 SDK 支持停止特定 CAN/IO 更新或报文使能，应另做通信超时用例。若无该能力，EV-04 冻结只能证明数值卡滞，不能证明超时处理。

### 3.2 阶段 B：BMS 电压/电流测量与诊断故障

| 编号 | 故障类型 | 注入接口 | 注入值/波形 | 关键观测与预期 |
| --- | --- | --- | --- | --- |
| EV-10 | 电池包电压偏低/偏高 | `Veh_1.FromVCU.CAN.VCU_Body.GW_BMS_3.BMS_BattVolt` | 低：`max(Vmin,0.90×V0)`；高：`min(Vmax,1.10×V0)`；各保持 3 s。阈值附近再以 1% 步进扫描。 | 观察 BMS 欠/过压告警、BMS 模式、可充放电能力、VCU 扭矩限制与继电器策略。 |
| EV-11 | 直流母线电压骤降/骤升 | `Veh_1.FromVCU.CAN.VCU_Body.GW_BMS_3.BMS_DCBusVoltage` | `V0→0.8×V0` 的阶跃 1 s，恢复；`V0→1.2×V0` 的阶跃 1 s，恢复。仅在 `Vmin/Vmax` 内执行。 | 观察 MC 母线电压/电流、扭矩、BMS/MC 故障等级及高压状态。 |
| EV-12 | 电池电流零偏、比例偏差、符号错误 | `Veh_1.FromVCU.CAN.VCU_Body.GW_BMS_3.BMS_BatteryCurrent` | 零偏：`I=I0+0.1×Ispan`；比例：`I=1.2×I0`；符号错误：`I=-I0`。`Ispan` 与符号约定须由 DBC/基线确认。 | 观察 BMS 电流、SOC、功率限制、过流状态与 MCU 母线电流的一致性。 |
| EV-13 | 充/放电能力虚低 | `...GW_BMS_1.BMS_MaxChgCurr` 或 `...BMS_MaxDischgCurr` | 从 `I0` 逐步降为 `0.75×I0→0.50×I0→0`，每级 3 s；一次只改一个限值。 | 观察 `BMS_max_*current_ToBus`、允许扭矩/充电电流、车速和故障等级；0 值应触发安全限扭或禁止相应能量流。 |
| EV-14 | 电压状态与量值矛盾 | `...GW_BMS_7.BMS_UnderVoltageSts`、`BMS_OverVoltageSts`、`BMS_CellOverVoltageSts`、`BMS__CellUnderVoltageSts` | 量值保持正常 `V0`，单独将一个状态由正常码置故障码，保持 3 s 后恢复。 | 验证 VCU 是否相信 BMS 告警，是否避免只依据量值而忽略故障位。状态码含义未确认前不得默认故障码为 `1`。 |
| EV-15 | 电流采样/过流状态 | `...GW_BMS_7.BMS_CurrSampleErr`、`BMS_Currsensor_CommuErr`、`BMS_OverCurrtSts`、`BMS_OverChgCurrSts` | 与 EV-14 相同：正常测量值下单个故障状态置位，再恢复。 | 观察 BMS 告警、功率/扭矩限制、继电器命令及恢复是否锁存。 |

完整前缀如下，表中省略的前缀均为：`Veh_1.FromVCU.CAN.VCU_Body`。

- ### 3.3 阶段 C：DC/DC 电压控制命令异常 -

| 编号 | 故障类型 | 注入接口 | 注入值/波形 | 关键观测与预期 |
| --- | --- | --- | --- | --- |
| EV-20 | 输出电压请求偏置/阶跃 | `Veh_1.FromVCU.CAN.VCU_Power.VCU_DCDC_Ctrl.VCU_DCDC_output_voltage_request` | 在请求值 `V0` 基础上做 `±5%`、`±10%` 阶跃，各保持 3 s；限于确认的工程范围。 | 观察 `DCDC_output_Voltage_ToBus`、`DCDC_output_current_ToBus`、`DCDC_Fault_level_ToBus`。 |
| EV-21 | 电压请求冻结 | 同 EV-20 | 在正常请求变化过程中保持 `Vhold=V(t0)` 5 s，再恢复。 | 验证输出是否跟随旧命令、是否产生请求新鲜度/合理性诊断。 |
| EV-22 | 上下限约束收窄 | `...VCU_DCDC_max_output_volt_Limit`、`...VCU_DCDC_min_out_volt_Limit` | 保持 `Vmin_limit ≤ Vmax_limit`；先将最大值降至请求附近，再恢复。不得构造“最小值大于最大值”，除非协议明确支持该非法码测试。 | 验证限幅优先级与 DCDC 输出是否越过限制。 |

## 4. 每个用例的最小记录集

### 4.1 必录上下文与注入量

```text
Model_Disabled
Model_Reset
Veh_1.Driver.Key
Veh_1.Driver.Gear_Button
Veh_1.Driver.AccPedal_perc
Veh_1.Driver.BrakePedal_perc
测试编号、目标接口、原始值、注入值、开始/结束时间、写入周期
```

### 4.2 能源系统响应

```text
Veh_1.ToVCU.powerCAN_out.SoftBMSDataToBus.BMS_HVBusVolt_Curr.BMS_HVBusVolt_ToBus
Veh_1.ToVCU.powerCAN_out.SoftBMSDataToBus.BMS_HVBusVolt_Curr.BMS_HVBusCurr_ToBus
Veh_1.ToVCU.powerCAN_out.SoftBMSDataToBus.BMS_HVBusVolt_Curr.BMS_SOC_ToBus
Veh_1.ToVCU.powerCAN_out.SoftBMSDataToBus.BMS_Capability.BMS_max_charge_current_ToBus
Veh_1.ToVCU.powerCAN_out.SoftBMSDataToBus.BMS_Capability.BMS_max_discharge_current_ToBus
Veh_1.ToVCU.powerCAN_out.SoftBMSDataToBus.BMS_Capability.BMS_max_charge_voltage_ToBus
Veh_1.ToVCU.powerCAN_out.SoftBMSDataToBus.BMS_Capability.BMS_max_discharge_voltage_ToBus
Veh_1.ToVCU.powerCAN_out.SoftBMSDataToBus.BMS_General.BMS_mode_ToBus
```

### 4.3 动力、安全与 DC/DC 响应

```text
Veh_1.ToVCU.powerCAN_out.SoftMCUDataToBus.MC_motor_Torque_AND_speed.MC_busbar_Voltage_ToBus
Veh_1.ToVCU.powerCAN_out.SoftMCUDataToBus.MC_motor_Torque_AND_speed.MC_busbar_current_ToBus
Veh_1.ToVCU.powerCAN_out.SoftMCUDataToBus.MC_motor_Torque_AND_speed.MC_motor_Torque_ToBus
Veh_1.ToVCU.powerCAN_out.SoftMCUDataToBus.MC_General.MC_system_Fault_level_ToBus
Veh_1.ToVCU.powerCAN_out.SoftDCDCDataToBus.DCDC_General.DCDC_input_Voltage_ToBus
Veh_1.ToVCU.powerCAN_out.SoftDCDCDataToBus.DCDC_General.DCDC_output_Voltage_ToBus
Veh_1.ToVCU.powerCAN_out.SoftDCDCDataToBus.DCDC_General.DCDC_input_current_ToBus
Veh_1.ToVCU.powerCAN_out.SoftDCDCDataToBus.DCDC_General.DCDC_output_current_ToBus
Veh_1.ToVCU.powerCAN_out.SoftDCDCDataToBus.DCDC_General.DCDC_Fault_level_ToBus
Veh_1.PlantModel.PlantModel.Powertrain.FMotor.Motor.MotTrq
Veh_1.PlantModel.PlantModel.Powertrain.RMotor.Motor.MotTrqManagement.RTrq
Veh_1.PlantModel.PlantModel.Vehicle1.Vehspeed
```

同时记录下列 VCU→模型命令，才能判断“故障发生后 VCU 是否发起保护”，而不仅是观察模型输出：

```text
Veh_1.FromVCU.CAN.VCU_Power.VCU_BMS_Ctrl.VCU_BMS_target_state
Veh_1.FromVCU.CAN.VCU_Power.VCU_BMS_Ctrl.VCU_charge_relay_control
Veh_1.FromVCU.CAN.VCU_Power.VCU_BMS_Ctrl.VCU_Discharge_relay_control
Veh_1.FromVCU.CAN.VCU_Power.VCU_MC_TrqCtrl.VCU_Target_output_Torque
Veh_1.FromVCU.CAN.VCU_Power.VCU_MC_TrqCtrl.VCU_Target_output_MaxTorque
```

## 5. 实验流程

1. **定义标定与安全边界**：从 DBC/标定表取得单位、比例、正常范围、状态码、极性和阈值。未获得这些信息时，只执行 EV-00，不执行高压/电流极值。
2. **建立基线**：车辆静止、挡位 N/P、油门为 0、制动有效；按用例要求完成 Key 上电或 DC/DC 工作态。稳定记录至少 5 s，计算 `V0`、`I0`。
3. **单故障注入**：一次只写一个量值或一个状态位；双通道一致性用例例外，但必须将其标为“同步双通道”。
4. **保持与记录**：采样周期建议 20 ms。阶跃类至少保持 3 s；冻结类 5–10 s；每个波形记录注入前后各至少 3 s。
5. **恢复**：先恢复原始基线值，再保持 5 s；检查故障是否自动恢复或锁存。
6. **结束条件**：出现非预期正扭矩、继电器状态不合理、模型停机或通信异常时，立即停止注入、恢复所有目标值并结束录波。
7. **复核**：同一用例最少重复 3 次；区分“输入本身已写入”“模型输出变化”“VCU 已作出安全响应”三个结论等级。

## 6. HIL 脚本结构概览

下面是设备 SDK 无关的控制结构；将 `connect`、`write`、`read`、`recorder_*` 替换为昆易 SDK 中已验证的具体调用即可。设备 IP、项目名、通道写权限和录波配置不在方案中假定。

```python
def run_case(case, context, recorder_signals):
    connect(HIL_IP)                           # 从配置读取，不硬编码
    load_or_confirm_project("Veh_1")
    set_context(context)                      # Key/挡位/踏板仅作为工况，不是故障对象
    restore_all(case.targets, baseline_values)
    wait_stable(seconds=5)

    baseline = read_window(case.targets + recorder_signals, seconds=5)
    injection = build_waveform(case, baseline, dbc_limits)

    recorder_start(case.id, recorder_signals, sample_period_s=0.02)
    try:
        for point in injection:               # 每 20 ms 或设定写入周期执行
            write(point.interface, point.value)
            sleep(point.dt)
        wait(seconds=3)                       # 记录故障保持后的响应
    finally:
        restore_all(case.targets, baseline)   # 无论异常与否均执行恢复
        wait(seconds=5)                       # 记录恢复或锁存状态
        recorder_stop()
        export_case_metadata(case, baseline, injection)
        disconnect()
```

`build_waveform()` 必须执行：工程上/下限钳位、单位转换、单变量互斥校验、禁止写入输出接口校验，以及状态码白名单校验。对 EV-03 和 EV-22 这类双接口用例，应在元数据中记录两个接口及其同步关系。

## 7. 结果判定

| 结论等级 | 条件 |
| --- | --- |
| 注入成功 | 录波中目标输入实际达到设定值，且保持时间符合用例。 |
| 检测成功 | 相应 BMS/MC/DC-DC 告警、故障等级或诊断输出在预期时间内变化。 |
| 安全响应成功 | 故障等级变化伴随合理的限流、限扭、继电器撤除或禁止能量流；不能仅凭某个告警位置位判定。 |
| 恢复成功 | 清除注入后，系统按设计自动恢复或保持设计规定的锁存状态。 |
| 未验证 | 目标接口写入成功但无静态/动态响应映射，或状态码、物理范围尚未由 DBC/标定确认。 |

## 8. 执行顺序建议

优先顺序为：EV-00 → EV-03/EV-04 → EV-10/EV-12 → EV-13/EV-15 → EV-20。这样先确认模拟通道归属和双通道诊断，再进入会影响高压能力、扭矩和 DC/DC 输出的用例。所有电压/电流阈值类测试应在 DBC 和标定范围确认后执行。
