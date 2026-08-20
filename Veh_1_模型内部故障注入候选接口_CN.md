# Veh_1 模型内部故障注入候选接口

## 1. 结论

将“持续合法油门”改称为“油门卡滞”不会产生新故障：若没有独立的驾驶员期望或第二冗余踏板量证明油门本应变化，录波数据与合法恒定油门没有区别。因此，不应继续通过驾驶员层接口的任意组合来人为增加故障复杂度。

在当前顶层可写接口中，下一阶段应优先转向 `Veh_1.ToModelbase.*` 的**车辆物理耦合输入**。它们位于车辆动力学、底盘或执行器模型的输入侧，能够表达转向、驱动扭矩、EPB 制动力、悬架外力和助力转向异常，而非驾驶员命令异常。

但是，除转向角外，静态依赖解析尚未找到这些接口到顶层输出的确定路径。因此它们是“高价值候选注入端”，不是已验证可用的故障端；必须先完成单通道可达性探测。

## 2. 候选接口与优先级

| 优先级 | 候选注入接口 | 物理含义/可模拟故障 | 静态证据 | 首轮观测接口 |
| --- | --- | --- | --- | --- |
| P1 | `Veh_1.ToModelbase.FromDriverManeuver.SteeringWheelAngle_rad` | 转向角偏置、符号反转、卡滞、抖动 | 已解析到 `Vehspeed` 的静态数据路径 | `Vehspeed `、`FrontMotSpd`、`RearMotSpd`、前后实际扭矩、MC/BMS 母线电流 |
| P1 | `Veh_1.ToModelbase.FromCAN.FrontTrqCmd1` | 前轴扭矩执行偏置、冻结、反向或突变 | 顶层输入已确认；尚无确定输出路径 | `FMotor.MotTrq`、`FTrq`、`FrontMotSpd`、`Vehspeed `、MC 电流 |
| P1 | `Veh_1.ToModelbase.FromCAN.RearTrqCmd` | 后轴扭矩执行偏置、冻结、反向或突变 | 顶层输入已确认；尚无确定输出路径 | `RTrq`、`RearMotSpd`、`Vehspeed `、MC/BMS 电流 |
| P2 | `Veh_1.ToModelbase.FromFCC_model.EPB_Force_RL` | 左后 EPB 卡滞施加/释放延迟 | 顶层输入已确认；尚无确定输出路径 | `Vehspeed `、后轴转速、后轴扭矩、MC/BMS 电流；最好增加后轮速/制动力观测 |
| P2 | `Veh_1.ToModelbase.FromFCC_model.EPB_Force_RR` | 右后 EPB 卡滞施加/释放延迟；与左后形成不对称制动 | 同上 | 同上 |
| P2 | `Veh_1.ToModelbase.FromFCC_model.Force_SusWext_1L/1R/2L/2R` | 单角外力突变、左右不对称路面扰动 | 顶层输入已确认；尚无确定输出路径 | 车速、轮速、转矩；最好增加横摆/侧向/悬架位移观测 |
| P3 | `Veh_1.ToModelbase.FromEPS_model.EPSActuator_AN_IN_PowerSteeringTorque` | 助力转向扭矩丢失、偏置或反向 | 顶层输入已确认；尚无确定输出路径 | 需补录横摆角速度、侧向加速度、方向盘角；现有输出不足 |
| P3 | `Veh_1.ToModelbase.FromDriverManeuver.DecelZoneSet` | 驾驶工况减速区错误、延迟或卡滞 | 顶层输入已确认；语义未确认 | `Vehspeed `、扭矩、电流、制动输出 |

下列接口不应当作车辆内部物理故障优先源：

- `Model_Disabled`、`Model_Reset`：属于仿真环境生命周期控制，适合测试模型复位鲁棒性，不等同于车辆内部部件故障。
- `Veh_1.FromVCU.HW.Digital Input.Y_DI_ChN_On_Off_Status`：36 路可写，但通道功能未知；先做单通道筛选。
- `Veh_1.FromVCU.HW.PWM Input.Y_ChN_PWM_In_*`：180 个可写标量，但通道功能未知；与已无响应的通用电压通道类似，暂列低优先级。
- `Veh_1.FromVCU.CAN.*`：`VCU_TqReqCmd` 所在 CAN 通信模型当前不可调整；不作为本阶段注入源。

## 3. 单通道可达性探测：先验证，再组合

### 3.0 被动正常工况筛选：用于排序，不用于下结论

在写入探测值之前，可以先记录候选接口在“正常但具有相应物理激励”的工况下是否非零或变化。这是低成本的优先级筛选方法：有自然变化的接口优先做注入探测；全程恒零的接口暂时降级。

但它**不能单独证明模型是否完善**：

- 接口非零/变化，只能说明其上游有写入；不能证明下游模型使用该值；
- 接口恒零，可能是模型未连接，也可能只是当前工况没有激活该物理支路；
- 接口恒定非零，可能是标定偏置、初始化值或稳态载荷，仍需要阶跃注入判断是否可达。

| 候选接口类别 | 被动筛选应使用的正常激励工况 | “有价值”的自然表现 | 恒零时的正确解释 |
| --- | --- | --- | --- |
| `SteeringWheelAngle_rad` | 低速左右转向或小幅正弦转向；直线行驶不够 | 随转向方向正负变化 | 直线工况为零是正常现象，不能判为未连接。 |
| `FrontTrqCmd1` / `RearTrqCmd` | 正常加速—匀速—松油门的速度循环 | 与驱动阶段同向变化，松油门后回落 | 可能未与外部扭矩源耦合，也可能当前动力链未启用。 |
| `EPB_Force_RL/RR` | 明确施加与释放 EPB 的驻车工况 | 施加时上升、释放时下降；左右应具有合理关系 | 普通行驶中为零通常正常；必须进入驻车制动工况。 |
| `Force_SusWext_*`、弹簧/阻尼力 | 不平路/起伏路或悬架运动工况 | 随车轮运动或路面扰动变化 | 平路匀速为零不代表支路不存在。 |
| `EPSActuator_AN_IN_PowerSteeringTorque` | 低速转向、泊车或蛇形工况 | 随方向盘负载变化 | 直线匀速下为零或极小是正常现象。 |
| `DecelZoneSet` | 含减速区/停车区的驾驶任务 | 进入减速区前后状态改变 | 若当前驾驶任务没有减速区，恒零无结论。 |

推荐对每个候选端按以下三级标记：

```text
S1：自然变化且与对应物理工况一致 → 优先做单通道阶跃/冻结注入
S2：恒定非零或变化与工况不一致 → 先核对单位、初始化和上游来源
S3：在“已激励的对应工况”中仍恒零 → 暂列未驱动/未接线候选，再做一次小阶跃确认
```

被动筛选录波应同时记录候选输入本身、其直接物理输出以及工况触发量。采样周期建议 20 ms；每种正常激励工况至少维持 5–10 s。

### 3.1 通用流程

每个候选接口都采用下列顺序；一个接口没有通过探测，就不进入多因素用例。

```text
建立稳态基线 3 s
→ 单独注入小幅阶跃 2 s
→ 恢复基线 3 s
→ 注入中幅阶跃 2 s
→ 恢复基线 3 s
→ 注入冻结或符号反转 2 s
→ 恢复基线 5 s
```

注入幅值不能凭空指定。读取接口稳定基线 `x0` 后，以模型/标定允许范围 `[xmin, xmax]` 定义量程 `R=xmax-xmin`：

```text
小幅阶跃：x0 ± 0.05R
中幅阶跃：x0 ± 0.20R
冻结：保持 x(t0)
符号反转：仅在量值允许正负方向且已确认语义时执行 x=-x0
```

对扭矩、力和转向角，未获取量程/单位前只执行小幅阶跃，不执行大幅或反向写入。

### 3.2 转向角探测（首选）

```text
接口：Veh_1.ToModelbase.FromDriverManeuver.SteeringWheelAngle_rad
基线：0 rad 或当前稳定角度
步骤：0 → +小角度 → 0 → -小角度 → 0 → 冻结/缓慢漂移
```

该接口是目前唯一具有明确静态输出依赖证据的内部候选端：`SteeringWheelAngle_rad → Vehspeed `。不过，现有顶层输出没有横摆、侧偏和轮胎力，故即使车速无变化，也不能证明转向支路无效；应优先补录横摆角速度、侧向加速度、横向速度、前轮转角或轮胎侧向力。

### 3.3 前/后扭矩执行链探测

```text
前轴：Veh_1.ToModelbase.FromCAN.FrontTrqCmd1
后轴：Veh_1.ToModelbase.FromCAN.RearTrqCmd
```

这两个接口不是 `VCU_TqReqCmd`，而是 Modelbase 物理车辆侧的前/后轴扭矩耦合输入。首轮分别单独测试，绝不同时改变：

```text
驾驶员油门、制动、挡位与 Key 保持不变
记录接口当前基线 x0
写入 x0 + 0.05R，保持 2 s，恢复
仅在观测到对应轴实际扭矩/轮速变化后，才做冻结或反向测试
```

首轮必须记录：

```text
Veh_1.PlantModel.PlantModel.Powertrain.FMotor.Motor.MotTrq
Veh_1.PlantModel.PlantModel.Powertrain.FMotor.Motor.MotTrqManagement.FTrq
Veh_1.PlantModel.PlantModel.Powertrain.RMotor.Motor.MotTrqManagement.RTrq
Veh_1.PlantModel.PlantModel.Driveline.FrontMotSpd
Veh_1.PlantModel.PlantModel.Driveline.RearMotSpd
Veh_1.PlantModel.PlantModel.Vehicle1.Vehspeed 
Veh_1.ToVCU.powerCAN_out.SoftMCUDataToBus.MC_motor_Torque_AND_speed.MC_busbar_current_ToBus
Veh_1.ToVCU.powerCAN_out.SoftBMSDataToBus.BMS_HVBusVolt_Curr.BMS_HVBusCurr_ToBus
```

### 3.4 EPB 左右不对称制动力探测

```text
Veh_1.ToModelbase.FromFCC_model.EPB_Force_RL
Veh_1.ToModelbase.FromFCC_model.EPB_Force_RR
```

推荐先在车辆静止或极低速状态下测试单侧力的置位/恢复；确认不会导致模型异常后，再进入低速匀速工况。初次只改变一侧，避免把左右不对称效应与输入写入失败混淆。

## 4. 只有在探测成功后才成立的复杂故障

复杂故障的最低要求是：至少两个注入端均已通过单通道可达性验证，且第二个因素能够改变第一个因素的传播路径。以下是可成立的候选组合。

| 复杂故障 | 前提 | 注入序列 | 目标 |
| --- | --- | --- | --- |
| CMI-01 转向传感器偏置＋后轴扭矩执行偏置 | 转向角、`RearTrqCmd` 均已验证 | 稳定行驶下施加小转向角偏置；再施加后轴扭矩偏置/冻结 | 验证转弯载荷下的扭矩执行偏差是否影响速度、后轴转速和能耗。 |
| CMI-02 单侧 EPB 卡滞＋后轴扭矩残留 | EPB 单侧力、`RearTrqCmd` 均已验证 | 先保持 RL 或 RR EPB 力；再施加后轴扭矩小偏置；分别恢复 | 模拟制动拖滞与驱动扭矩残留的机械—动力耦合故障。 |
| CMI-03 单角路面外力突变＋转向角冻结 | 单角外力、转向角均已验证，且补录横向观测 | 外力阶跃后冻结转向角；随后恢复转向 | 模拟路面扰动与转向传感器卡滞的底盘耦合故障。 |

若两个内部候选端中只有一个通过可达性验证，不应硬凑“双故障”。此时更有价值的是对该单端执行偏置、冻结、渐变、抖动、延迟释放和恢复锁存做完整故障谱。

## 5. 对“模型未完善”的判据

若一个候选端满足以下全部条件仍无输出响应，才可将其列为“当前顶层模型未接线/未实现的内部支路”：

1. 写入值已由同一顶层接口回读确认；
2. 输入单位、量程和符号已确认；
3. 已在对应的有效工况下保持至少 2 s；
4. 记录了该物理支路的直接输出，而非仅记录车速等远端量；
5. 阶跃、冻结和恢复均未产生可重复响应。

当前通用电压和 BMS 电压/电流测试尚不完全满足第 2、4 项，因此适合表述为“未发现可观测传播路径”，而非“整个内部电气逻辑不存在”。
