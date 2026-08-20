# Veh_1 多输入—单输出复杂故障注入候选

## 结论

从 `Veh_1_Output_Input_Dependency.csv` 的静态数据流关系中，筛得 6 个由两个及以上外部输入间接影响的单输出接口。所有 6 项均包含 `VCU_TqReqCmd`；该信号受当前不可修改的 CAN 通信模型控制。因此，以下关系可以用于解释和观测多因素响应，但不能在现有条件下直接宣称为“所有输入均可控”的复杂故障注入试验。

静态依赖表示生成代码中的数据传播路径，不等同于已在运行工况下验证的因果响应。

## 候选关系

|单输出接口|静态关联的输入接口|当前可注入性|适合作为复杂响应目标的程度|说明|
|---|---|---|---|---|
|`Veh_1.PlantModel.PlantModel.Vehicle1.Vehspeed`|`BrakeMode`、`BrakePedal_perc`、`Gear_Button`、`VCU_TqReqCmd`、`SteeringWheelAngle_rad`|制动踏板、挡位可写；转角待验证；制动模式枚举待确认；扭矩请求不可写|高|输入种类最多，且车速可综合反映纵向/挡位/转向工况。|
|`Veh_1.ToVCU.powerCAN_out.SoftBMSDataToBus.BMS_HVBusVolt_Curr.BMS_HVBusCurr_ToBus`|`BrakeMode`、`BrakePedal_perc`、`Gear_Button`、`VCU_TqReqCmd`|制动踏板、挡位可写；制动模式待确认；扭矩请求不可写|中|可观测制动与挡位状态变化下的母线电流响应；此前电压/BMS通道试验未发现注入通路，不能将其视为电气内部故障注入端。|
|`Veh_1.PlantModel.PlantModel.Driveline.RearMotSpd`|`BrakeMode`、`Gear_Button`、`VCU_TqReqCmd`|挡位可写；制动模式待确认；扭矩请求不可写|中|适合观察挡位—制动模式交互对传动系转速的影响。|
|`Veh_1.PlantModel.PlantModel.Powertrain.RMotor.Motor.MotTrqManagement.RTrq`|`BrakeMode`、`Gear_Button`、`VCU_TqReqCmd`|挡位可写；制动模式待确认；扭矩请求不可写|中|适合做扭矩路径的响应观测，但不能排除 VCU 扭矩请求的共同影响。|
|`Veh_1.ToVCU.powerCAN_out.SoftMCUDataToBus.MC_motor_Torque_AND_speed.MC_motor_speed_ToBus`|`BrakePedal_perc`、`VCU_TqReqCmd`|制动踏板可写；扭矩请求不可写|低|只有一个当前确定可控的输入，不构成可控的多输入注入。|
|`Veh_1.ToVCU.powerCAN_out.SoftMCUDataToBus.MC_motor_Torque_AND_speed.MC_busbar_current_ToBus`|`BrakePedal_perc`、`VCU_TqReqCmd`|制动踏板可写；扭矩请求不可写|低|同上；适合作为制动注入的伴随观测量。|

## 当前最接近可执行的复杂注入

### CFI-A：转向角—制动踏板—挡位对车速的组合响应

注入端：

1. `Veh_1.Driver.BrakePedal_perc`
2. `Veh_1.Driver.Gear_Button`
3. `Veh_1.ToModelbase.FromDriverManeuver.SteeringWheelAngle_rad`（先做单变量可达性验证）

主要观测端：

1. `Veh_1.PlantModel.PlantModel.Vehicle1.Vehspeed`
2. `Veh_1.PlantModel.PlantModel.Driveline.RearMotSpd`
3. `Veh_1.PlantModel.PlantModel.Powertrain.RMotor.Motor.MotTrqManagement.RTrq`
4. `Veh_1.ToVCU.powerCAN_out.SoftBMSDataToBus.BMS_HVBusVolt_Curr.BMS_HVBusCurr_ToBus`

该项的三个因素具有相互独立的物理意义，避免把“长期保持合法油门值”误称为油门卡滞。`VCU_TqReqCmd` 不修改，只作为未控背景量全程记录；分析时仅比较其相近区间，或将其变化作为混杂因素标记。

前置条件：在稳定行驶中，单独改变转向角后，至少应确认 `Vehspeed`、横摆/横向相关量或轮速中存在可重复响应。若无响应，则不应进入三因素组合试验。

### CFI-B：挡位—制动模式对扭矩/后电机转速的组合响应

注入端：

1. `Veh_1.Driver.Gear_Button`
2. `Veh_1.Driver.BrakeMode`

主要观测端：

1. `Veh_1.PlantModel.PlantModel.Powertrain.RMotor.Motor.MotTrqManagement.RTrq`
2. `Veh_1.PlantModel.PlantModel.Driveline.RearMotSpd`
3. `Veh_1.PlantModel.PlantModel.Vehicle1.Vehspeed`

该方案仅在明确 `BrakeMode` 的枚举、可写性与各取值物理语义后成立。当前已知数据仅覆盖 `BrakeMode=0`，不能擅自把其他编码当作正常/故障制动模式。

## 不应采用的解释

- 不将固定于一个合法油门开度的操作称为“油门卡滞”；除非另有独立的驾驶员期望油门参考信号可用于证明两者不一致。
- 不将 `VCU_TqReqCmd` 当作注入端、组合故障因素或保持常量的控制量；它当前不可直接操控。
- 不因静态依赖表出现 BMS/母线电流输出，便认定电压电流内部故障通路已经可用。既有 TS-12 测试只支持“当前已测暴露通道未观察到响应”的结论。

## 推荐的验证顺序

1. 在正常转弯或阶跃转向工况下，记录并核验 `SteeringWheelAngle_rad` 的运行时响应路径。
2. 获取 `BrakeMode` 的枚举定义，分别验证每个候选编码在不注入其他量时的影响。
3. 仅对已分别验证有效的输入做 2 因素/3 因素组合；每次保持 `VCU_TqReqCmd` 的背景波形可比，并全程记录该量。
4. 采用 20 ms 采样；组合切换前后各保留不少于 3 s 的稳定窗口，以便区分阶跃瞬态与稳态响应。
