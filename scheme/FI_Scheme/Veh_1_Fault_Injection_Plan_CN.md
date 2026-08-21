# Veh_1 故障注入详细方案

模型接口元数据：
VCU_HIL_RCP/.em/Environments/env_1/env_1_Design/.ip/Models/Veh_1.json

模型包：
VCU_HIL_RCP/.em/Database/VCX/Base/Veh_1.vcx

依赖依据：
Veh_1_Output_Input_Dependency.csv
Veh_1_Input_Output_Impact.csv

## 1. 总体测试流程

每个测试用例建议使用相同的时序，避免把启动瞬态、状态机切换和故障响应混在一起。

1. 初始化：记录模型版本、环境名称、测试编号、HIL 运行周期、实际模型步长和测试时间。确认 Model_Disabled=0，且没有待处理复位。
2. 基线：保持正常输入至少 5 个模型步长，直到被测输出稳定。记录所有注入接口和观测接口。
3. 注入：一次只改变一个接口。记录时间戳、原始值、注入值、注入模式和持续时间。
4. 保持：至少保持 5 个模型步长。CAN 丢帧、冻结和超时故障应覆盖一个完整报文周期及超时判定时间。
5. 恢复：恢复原始输入，继续记录至少 5 个模型步长，确认是否恢复、锁存或需要复位。
6. 判定：检查数值变化、响应延迟、输出越界、冗余一致性、降级行为和恢复行为。

不要在脚本中直接假设 Veh_1 的固定步长。工程中出现过 Timer_5ms，但这不能单独证明 Veh_1 必然以 5 ms 运行。测试脚本应从当前 HIL 调度配置读取实际周期。

## 2. 建议执行顺序

优先执行 FI-03、FI-01、FI-06、FI-04 和 FI-10。这些用例分别覆盖动力请求、制动、扭矩限制、挡位和模型生命周期，能够较快验证整车模型的主故障传播链路。

第二批执行 FI-02、FI-05、FI-07、FI-08 和 FI-09。

最后执行 FI-11 至 FI-13。数字量、PWM 和电压反馈接口数量较多，当前静态表没有确认每个硬件通道到输出的确定关系，应采用单通道动态探测建立补充映射。

## 3. FI-01 制动踏板异常

### 注入接口

接口名：Veh_1.Driver.BrakePedal_perc

RefBlock：Veh_1/Driver/BrakePedal_perc

类型：Double。标量。非队列。

生成代码符号：Veh_1_B.VCar_Inport_n

### 注入方式

- 阶跃：从当前基线值阶跃到中间制动值，再恢复。
- 卡高：保持高制动值。
- 卡低：保持 0 或当前最低有效值。
- 越界：注入低于或高于当前 HIL 配置有效范围的值。
- 抖动：在相邻模型步长之间快速往返变化。
- 恢复：将输入恢复为基线值，确认输出是否解除。

百分比数值的有效范围应以当前 HIL 接口配置为准，不要仅根据接口名自行假设上限。

### 必须记录的输入

- Veh_1.Driver.BrakePedal_perc
- Veh_1.Driver.BrakeMode
- Veh_1.Driver.Gear_Button
- Veh_1.Driver.Key
- Veh_1.Driver.AccPedal_perc

### 必须记录的输出

- Veh_1.ToVCU.HW.Relay.Relay9.BrakeOpen1_Out
- Veh_1.ToVCU.HW.Relay.Relay12.BrakeOpen2_Out
- Veh_1.ToVCU.HW.Voltage Output.Voltage Output1.BRK_Main_Out
- Veh_1.ToVCU.HW.Voltage Output.Voltage Output5.BRK_Auxi_Out
- Veh_1.PlantModel.PlantModel.Vehicle1.Vehspeed
- Veh_1.ToVCU.powerCAN_out.SoftMCUDataToBus.MC_motor_Torque_AND_speed.MC_motor_speed_ToBus
- Veh_1.ToVCU.powerCAN_out.SoftMCUDataToBus.MC_motor_Torque_AND_speed.MC_busbar_current_ToBus
- Veh_1.ToVCU.powerCAN_out.SoftBMSDataToBus.BMS_HVBusVolt_Curr.BMS_HVBusCurr_ToBus

### 故障描述与解释

模拟制动踏板传感器卡死、漂移、越界或抖动。静态依赖表确认制动踏板到两个制动继电器、两个制动电压输出、车辆速度和部分动力 CAN 输出存在传播路径。

### 判定标准

- BRK_Main_Out 和 BRK_Auxi_Out 的主辅通道应满足设计一致性。
- BrakeOpen1_Out 和 BrakeOpen2_Out 不应出现无输入依据的随机翻转。
- 卡高时应观察电机转矩和母线电流是否进入安全状态。
- 输入恢复后输出应在规定时间内恢复，或者进入设计明确的锁存/降级状态。
- 记录从注入到继电器、电压、车速和 CAN 输出变化的延迟。

## 4. FI-02 加速踏板异常

### 注入接口

接口名：Veh_1.Driver.AccPedal_perc

RefBlock：Veh_1/Driver/AccPedal_perc

类型：Double。标量。非队列。

生成代码符号：Veh_1_B.VCar_Inport_k

### 注入方式

- 0 到中间值阶跃，再恢复到 0。
- 高值冻结。
- 当前值冻结。
- 越界或非法浮点值。NaN/Inf 仅在 HIL 注入器和目标运行时允许时使用。
- 与 BrakePedal_perc 同时保持非零，验证冲突输入仲裁。

### 必须记录

输入：

- Veh_1.Driver.AccPedal_perc
- Veh_1.Driver.BrakePedal_perc
- Veh_1.Driver.Key
- Veh_1.Driver.DriveMode
- Veh_1.Driver.Gear_Button
- Veh_1.FromVCU.CAN.VCU_Body.GW_VCU_2.VCU_TqReqCmd

输出：

- Veh_1.ToVCU.HW.Voltage Output.Voltage Output7.ACC_Main_Out_Out
- Veh_1.ToVCU.HW.Voltage Output.Voltage Output8.ACC_Auxi_Out_Out
- Veh_1.PlantModel.PlantModel.Vehicle1.Vehspeed
- Veh_1.PlantModel.PlantModel.Powertrain.FMotor.Motor.MotTrq
- Veh_1.PlantModel.PlantModel.Powertrain.RMotor.Motor.MotTrqManagement.RTrq
- Veh_1.PlantModel.PlantModel.Driveline.FrontMotSpd
- Veh_1.PlantModel.PlantModel.Driveline.RearMotSpd

### 故障描述与解释

模拟加速踏板传感器卡高、卡低、漂移或超范围。当前静态分析明确解析到两个加速电压输出。车速、电机转矩和转速属于扩展观察量，实际变化还受 VCU 扭矩请求、驾驶模式、挡位和状态影响。

### 判定标准

- 主辅加速电压输出应符合设计一致性。
- 加速踏板异常时不能出现不受控制的正向电机转矩。
- 制动和加速同时注入时，应记录仲裁结果。
- 恢复后输出应回到基线或进入明确的降级状态。

## 5. FI-03 VCU 扭矩请求 CAN 异常

**你现在遇到的不是“小问题”，反而是已经定位到了 FI-03 真正应该在哪一层注入：CAN/网络源层，而不是 Veh_1 接收结果层。**

### 注入接口

接口名：Veh_1.FromVCU.CAN.VCU_Body.GW_VCU_2.VCU_TqReqCmd

RefBlock：Veh_1/FromVCU/CAN/VCU_Body/GW_VCU_2/VCU_TqReqCmd

类型：Double。标量。非队列。

生成代码符号：Veh_1_B.VCar_Inport_m

### 注入方式

- 越界：高于正常请求上限或低于正常请求下限。
- 冻结：保持最后一个有效请求。
- 丢帧：停止更新信号，模拟报文中断。
- 符号错误：将正请求改为负请求或反向请求。
- 突变：相邻两个模型步长之间施加大幅变化。
- 恢复：恢复正常 CAN 请求，记录恢复延迟。

### 必须记录的输入

- Veh_1.FromVCU.CAN.VCU_Body.GW_VCU_2.VCU_TqReqCmd
- Veh_1.FromVCU.CAN.VCU_Power.VCU_MC_TrqCtrl.VCU_Target_output_MaxTorque
- Veh_1.Driver.AccPedal_perc
- Veh_1.Driver.BrakePedal_perc
- Veh_1.Driver.BrakeMode
- Veh_1.Driver.Gear_Button
- Veh_1.Driver.DriveMode
- Veh_1.Driver.Key

### 必须记录的输出

- Veh_1.PlantModel.PlantModel.Powertrain.FMotor.Motor.MotTrq
- Veh_1.PlantModel.PlantModel.Powertrain.FMotor.Motor.MotTrqManagement.FTrq
- Veh_1.PlantModel.PlantModel.Powertrain.RMotor.Motor.MotTrqManagement.RTrq
- Veh_1.PlantModel.PlantModel.Driveline.FrontMotSpd
- Veh_1.PlantModel.PlantModel.Driveline.RearMotSpd
- Veh_1.PlantModel.PlantModel.Vehicle1.Vehspeed
- Veh_1.ToVCU.powerCAN_out.SoftMCUDataToBus.MC_General.MC_MaxToque_Limit_ToBus
- Veh_1.ToVCU.powerCAN_out.SoftMCUDataToBus.MC_motor_Torque_AND_speed.MC_motor_Torque_ToBus
- Veh_1.ToVCU.powerCAN_out.SoftMCUDataToBus.MC_motor_Torque_AND_speed.MC_motor_speed_ToBus
- Veh_1.ToVCU.powerCAN_out.SoftMCUDataToBus.MC_motor_Torque_AND_speed.MC_busbar_current_ToBus
- Veh_1.ToVCU.powerCAN_out.SoftBMSDataToBus.BMS_HVBusVolt_Curr.BMS_HVBusCurr_ToBus

### 故障描述与解释

模拟 VCU 动力请求报文越界、冻结、丢失、符号翻转或瞬时突变。该输入是当前静态分析中影响范围最清晰的输入之一，传播到前后电机转矩、前后电机转速、车辆速度和多个动力 CAN 输出。

### 判定标准

- 实际电机转矩不得无条件超过有效最大扭矩限制。
- 丢帧后不能无限期保持旧请求，除非这是设计明确的保持策略。
- 前后电机状态和 CAN 报文应保持合理一致性。
- 负请求不应导致未授权的反向驱动。
- 恢复后应记录请求恢复到转矩恢复的延迟。

## 6. FI-04 挡位输入异常

注入接口：Veh_1.Driver.Gear_Button

RefBlock：Veh_1/Driver/Gear_Button

生成代码符号：Veh_1_B.VCar_Inport_n5

### 注入方式

- 非法挡位码。
- 行驶中挡位跳变。
- 挡位卡死。
- 与 DriveMode、BrakeMode 和 BrakePedal_perc 不一致。
- 短脉冲挡位请求。

### 必须记录

输入：

- Veh_1.Driver.Gear_Button
- Veh_1.Driver.DriveMode
- Veh_1.Driver.BrakeMode
- Veh_1.Driver.Key
- Veh_1.Driver.BrakePedal_perc
- Veh_1.Driver.AccPedal_perc
- Veh_1.FromVCU.CAN.VCU_Body.GW_VCU_2.VCU_TqReqCmd

输出：

- Veh_1.PlantModel.PlantModel.Driveline.RearMotSpd
- Veh_1.PlantModel.PlantModel.Powertrain.RMotor.Motor.MotTrqManagement.RTrq
- Veh_1.PlantModel.PlantModel.Vehicle1.Vehspeed
- Veh_1.ToVCU.powerCAN_out.SoftBMSDataToBus.BMS_HVBusVolt_Curr.BMS_HVBusCurr_ToBus
- FI-03 中列出的电机转矩、转速和动力 CAN 输出

### 故障描述与解释

模拟挡位开关卡死、非法编码或挡位跳变。静态路径确认其会传播到后电机转矩、后电机转速和车辆速度相关状态。

### 判定标准

- 非法挡位应被拒绝或进入安全状态。
- 不应因为非法挡位产生不合理驱动力。
- 挡位恢复后状态机应退出故障或进入明确锁存状态。
- 记录挡位变化到后电机状态变化的延迟。

## 7. FI-05 制动模式输入异常

注入接口：Veh_1.Driver.BrakeMode

说明：Veh_1.json 中该接口名称带有尾随空格。使用接口时应以 RefBlock 为准。

RefBlock：Veh_1/Driver/BrakeMode

生成代码符号：Veh_1_B.VCar_Inport

### 注入方式

- 合法模式间切换。
- 非法模式码。
- 模式卡死。
- 模式跳变。
- 与 BrakePedal_perc 不一致。

### 必须记录

输入：BrakeMode、BrakePedal_perc、Gear_Button、Key、AccPedal_perc、VCU_TqReqCmd。

输出：RearMotSpd、RTrq、Vehspeed、BMS_HVBusCurr_ToBus、BrakeOpen1_Out、BrakeOpen2_Out、BRK_Main_Out、BRK_Auxi_Out。

### 故障描述与解释

模拟制动模式编码错误或模式切换异常。实际输出受模式值、踏板值和状态机状态共同影响，因此应使用多个模式码和多个基线工况测试。

### 判定标准

- 非法模式不应产生危险转矩。
- 制动模式和制动踏板之间的仲裁逻辑应明确。
- 主辅制动输出不能出现无依据的不一致。
- 恢复后模式、继电器和动力状态应同步恢复。

## 8. FI-06 最大输出扭矩限制异常

注入接口：Veh_1.FromVCU.CAN.VCU_Power.VCU_MC_TrqCtrl.VCU_Target_output_MaxTorque

RefBlock：Veh_1/FromVCU/CAN/VCU_Power/VCU_MC_TrqCtrl/VCU_Target_output_MaxTorque

生成代码符号：Veh_1_B.VCar_Inport_lk

### 注入方式

- 限制值突然下降。
- 限制值冻结。
- 注入负值或零值。
- 注入超过物理上限的值。
- 与 VCU_TqReqCmd 不一致。

### 必须记录

输入：该限制值、VCU_TqReqCmd、AccPedal_perc、BrakePedal_perc、Gear_Button、DriveMode。

输出：

- Veh_1.ToVCU.powerCAN_out.SoftMCUDataToBus.MC_Status.MC_max_Torque_Limit_ToBus
- Veh_1.PlantModel.PlantModel.Powertrain.FMotor.Motor.MotTrq
- Veh_1.PlantModel.PlantModel.Powertrain.RMotor.Motor.MotTrqManagement.RTrq
- Veh_1.PlantModel.PlantModel.Vehicle1.Vehspeed
- Veh_1.ToVCU.powerCAN_out.SoftMCUDataToBus.MC_motor_Torque_AND_speed.MC_busbar_current_ToBus

### 故障描述与解释

模拟动力控制器最大允许扭矩限制报文错误。重点比较扭矩请求、最大限制和实际电机转矩三者关系，而不是只观察限制报文是否变化。

### 判定标准

- 实际转矩不能越过有效限制。
- 限制值突降后转矩应按设计降低或进入保护状态。
- 限制值恢复后实际转矩恢复应有明确延迟和斜率。
- 负值和超上限值应被拒绝、限幅或进入降级。

## 9. FI-07 驾驶模式异常

注入接口：Veh_1.Driver.DriveMode

RefBlock：Veh_1/Driver/DriveMode

生成代码符号：Veh_1_B.VCar_Inport_nt

### 注入方式

- 非法模式码。
- 运行中模式跳变。
- 模式冻结。
- 与挡位和钥匙状态不一致。

### 必须记录

输入：DriveMode、Key、Gear_Button、BrakeMode、AccPedal_perc、BrakePedal_perc。

输出：

- Veh_1.ToVCU.HW.Relay.Relay8.DriveMode_Out
- Veh_1.PlantModel.PlantModel.Vehicle1.Vehspeed
- Veh_1.PlantModel.PlantModel.Powertrain.FMotor.Motor.MotTrq
- Veh_1.PlantModel.PlantModel.Powertrain.RMotor.Motor.MotTrqManagement.RTrq
- 全部动力 CAN 状态输出

### 故障描述与解释

静态依赖明确指向 Relay8.DriveMode_Out。非法模式还可能触发状态机保护，因此要同时记录模式输入、继电器输出和车辆状态。

### 判定标准

- 非法模式被拒绝或进入降级。
- Relay8 输出与内部模式状态一致。
- 模式恢复后继电器和动力状态同步恢复。

## 10. FI-08 钥匙输入异常

注入接口：Veh_1.Driver.Key

RefBlock：Veh_1/Driver/Key

生成代码符号：Veh_1_B.VCar_Inport_a

### 注入方式

- 运行中断开。
- 运行中突然置有效。
- 短脉冲。
- 卡高或卡低。

### 必须记录

输入：Key、Model_Disabled、Model_Reset、DriveMode、Gear_Button、BrakePedal_perc。

输出：

- Veh_1.ToVCU.HW.Relay.Relay25.Model_Disabled_Out
- Vehspeed
- 前后电机转矩和转速
- 全部硬件输出
- 全部动力 CAN 输出

### 故障描述与解释

静态依赖显示 Key 会传播到模型禁用相关继电器。需要动态确认 Key 是否还通过环境层影响模型运行。

### 判定标准

- Relay25 输出符合设计。
- 不出现半复位或部分输出停止。
- 恢复后模型和输出恢复行为明确。
- 如果需要 Model_Reset 才能恢复，应记录为设计的锁存行为。

## 11. FI-09 转向盘角度模型基础输入异常

注入接口：Veh_1.ToModelbase.FromDriverManeuver.SteeringWheelAngle_rad

RefBlock：Veh_1/ToModelbase/FromDriverManeuver/SteeringWheelAngle_rad

生成代码符号：Veh_1_B.SteeringWheelAnglerad

### 注入方式

- 突变。
- 冻结。
- 符号反转。
- 缓慢漂移。
- 高频抖动。

### 必须记录

输入：转向角、Gear_Button、DriveMode、BrakePedal_perc、AccPedal_perc、VCU_TqReqCmd。

输出：静态表明确关联 Vehspeed；建议同时记录 FrontMotSpd、RearMotSpd、前后电机转矩和动力 CAN 输出。

### 故障描述与解释

该接口来自模型基础/驾驶员操纵链路，不是普通 VCU CAN 命令。静态结果只解析到 Vehspeed，不能据此推断横向状态已经作为 Veh_1 输出暴露。

### 判定标准

- 车速和动力状态变化应与工况合理。
- 不应因转向角异常产生不合理电机转矩。
- 恢复后无持续残留偏差。
- 若需要横摆角速度、侧向速度或轮胎力观测，应在更高层模型或 HIL 系统中补充观测点。

## 12. FI-10 模型禁用/复位异常

### 注入接口

- Model_Disabled：UInt8。元数据范围 0–255。RefBlock 为 InputPort/Model_Disabled。
- Model_Reset：UInt8。元数据范围 0–255。RefBlock 为 InputPort/Model_Reset。

这两个接口由环境包装层提供，在 Veh_1 生成代码的普通 Veh_1_B 输入成员中没有单独映射，因此静态表不能给出精确的输出集合。

### 注入方式

- Model_Disabled 置有效并保持，再恢复无效。
- Model_Reset 施加单步脉冲。
- Model_Reset 施加长脉冲。
- 连续复位。
- 禁用期间触发复位。
- 复位期间解除禁用。

### 必须记录

- Model_Disabled 和 Model_Reset 实际回读值。
- 全部 574 个 Veh_1 输出。
- 至少包括 Vehspeed、FrontMotSpd、RearMotSpd、FMotor.MotTrq、FTrq、RTrq。
- 全部硬件输出和全部 CAN 输出。
- HIL 运行状态、模型实例状态、复位完成标志或错误码。

### 故障描述与解释

重点不是单个输出，而是模型是否停止更新、保持最后值、回到初始状态、出现半复位，或解除故障后仍然锁存。

### 判定标准

- 禁用状态下模型输出行为一致。
- 复位后内部状态和输出回到设计初始状态。
- 不出现部分状态复位、部分状态保持的半复位现象。
- 恢复时间和锁存性符合设计。

## 13. FI-11 至 FI-13 硬件反馈动态探测

### 接口族

数字输入：

Veh_1.FromVCU.HW.Digital Input.Y_DI_ChN_On_Off_Status

共 36 个标量接口。

PWM 输入：

Veh_1.FromVCU.HW.PWM Input.Y_ChN_PWM_In_Amplitude

Veh_1.FromVCU.HW.PWM Input.Y_ChN_PWM_In_Duty_Ratio

Veh_1.FromVCU.HW.PWM Input.Y_ChN_PWM_In_Frequency

共 60 组、180 个标量接口。

电压输入：

Veh_1.FromVCU.HW.Voltage Input.Y_ChN_Present_Voltage

Veh_1.FromVCU.HW.Voltage Input.Y_ChN_Average_Voltage

共 24 组、48 个标量接口。

### 动态探测方法

1. 选择一个通道，例如 DI Ch1 或一组 PWM/Voltage 通道。
2. 先记录正常输入和全部输出。
3. 只改变一个标量。PWM 三元组每次只改变幅值、占空比或频率中的一个。
4. 记录所有变化的输出，建立实际注入接口到实际响应输出的映射。
5. 对发生响应的通道重复冻结、恢复、越界和通道不一致试验。
6. 将动态映射补充到单独的测试数据库，不要直接覆盖静态依赖表。

### 通用故障描述

模拟硬件反馈通道发生单通道异常。保持其他输入不变，对目标通道施加翻转、卡死、越界或丢失故障，观察执行器输出、继电器、CAN 状态和诊断输出是否出现预期的故障检测、降级或安全状态；同时验证故障恢复后输出是否恢复以及是否存在锁存。

### 判定重点

- 故障是否被检测。
- 对应执行器是否进入安全状态。
- 主辅或 Present/Average 通道不一致时是否产生诊断。
- PWM 输出是否出现不受控的占空比或频率。
- 电压异常时是否出现危险供电输出。
- 恢复后是否自动恢复或按照设计锁存。

## 14. 统一记录信号集

### 每个用例都必须记录

- 测试时间戳和模型步号。
- 测试编号和注入接口。
- RefBlock 和生成代码符号。
- 原始值、注入值、恢复值。
- 注入模式、开始时间、结束时间和持续时间。
- Model_Disabled 和 Model_Reset。
- Key、DriveMode、Gear_Button、BrakeMode、BrakePedal_perc、AccPedal_perc。
- VCU_TqReqCmd 和 VCU_Target_output_MaxTorque，动力类故障必须记录。

### 推荐全局输出集

车辆状态：

- Vehspeed
- FrontMotSpd
- RearMotSpd

电机状态：

- FMotor.Motor.MotTrq
- FMotor.Motor.MotTrqManagement.FTrq
- RMotor.Motor.MotTrqManagement.RTrq

动力 CAN：

- MC_motor_Torque_ToBus
- MC_motor_speed_ToBus
- MC_busbar_current_ToBus
- MC_MaxToque_Limit_ToBus
- MC_max_Torque_Limit_ToBus
- BMS_HVBusCurr_ToBus

制动和加速硬件：

- BRK_Main_Out
- BRK_Auxi_Out
- ACC_Main_Out_Out
- ACC_Auxi_Out_Out
- BrakeOpen1_Out
- BrakeOpen2_Out

模式和使能：

- DriveMode_Out
- Model_Disabled_Out
- 相关 CAN 报文使能输出

## 15. 统一判定指标

每个用例至少输出以下指标：

- 响应延迟：注入时刻到第一个有效输出变化的时间。
- 峰值偏差：输出相对基线的最大绝对偏差。
- 保持行为：冻结或丢帧时输出是跟随、保持、超时归零还是降级。
- 越界行为：是否出现超出接口或物理约束的输出。
- 一致性：主辅制动、前后电机、CAN 报文与内部状态是否一致。
- 恢复时间：恢复输入后回到基线或安全状态的时间。
- 锁存性：输入恢复后故障是否仍保持。
- 安全性：是否产生不应有的驱动转矩、错误使能或危险继电器状态。

建议每条波形至少具备以下记录字段：

TestID、Timestamp、ModelStep、InjectionMode、InterfaceName、RefBlock、OriginalValue、InjectedValue、RecoveredValue、OutputName、OutputRefBlock、BaselineValue、PeakValue、ResponseDelay、RecoveryDelay、PassFail、Description、Evidence

