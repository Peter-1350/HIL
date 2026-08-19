# Veh_1 接口依赖关系表使用说明

模型：`VCU_HIL_RCP/.em/Environments/env_1/env_1_Design/.ip/Models/Veh_1.json`

模型包：`VCU_HIL_RCP/.em/Database/VCX/Base/Veh_1.vcx`

## 生成结果

| 内容 | 数量 |
|---|---:|
| 输入接口 | 692 |
| 输出接口 | 574 |
| 接口目录行 | 1266 |
| 输出→输入关系行 | 33 |
| 参数/状态主导输出行 | 548 |
| 需要运行时验证的未解析输出行 | 6 |

## 文件对应关系

`Veh_1_Interface_Catalog.csv`：全部输入和输出接口的目录，包括方向、类型、接口路径、分组、生成代码内部符号和解释备注。

`Veh_1_Output_Input_Dependency.csv`：以输出为主键方向，每行表示一个输出到输入的静态数据依赖。重点字段如下：

- `OutputName` / `OutputRefBlock`：输出接口名称和模型路径。
- `InputName` / `InputRefBlock`：可注入的输入接口名称和模型路径；`<none>` 表示没有追溯到外部输入。
- `DependencyKind`：`Indirect input dependency` 表示经过中间变量传播；`Parameter/state only` 表示当前静态路径只到参数或状态；`Unresolved static path` 表示需要运行时试验补充。
- `DependencyConfidence`：本表关系来自生成代码静态数据流，不能替代 HIL 动态验证。
- `Explanation` / `FaultInjectionHint`：关系解释和注入建议。

`Veh_1_Input_Output_Impact.csv`：输入到输出的反向索引，适合先选一个输入，再确定需要监测的输出集合。

## 当前识别到的代表性关系

| 故障注入输入 | 重点观测输出 | 备注 |
|---|---|---|
| `Veh_1.Driver.BrakePedal_perc` | `Relay12.BrakeOpen2_Out`、`Relay9.BrakeOpen1_Out`、`Voltage Output1.BRK_Main_Out`、`Voltage Output5.BRK_Auxi_Out` | 制动踏板输入链路 |
| `Veh_1.Driver.AccPedal_perc` | `Voltage Output7.ACC_Main_Out_Out`、`Voltage Output8.ACC_Auxi_Out_Out` | 加速踏板到加速传感器输出 |
| `Veh_1.Driver.DriveMode` | `Relay8.DriveMode_Out` | 驾驶模式输出链路 |
| `Veh_1.Driver.Key` | `Relay25.Model_Disabled_Out` | 钥匙/模型使能相关链路 |
| `Veh_1.FromVCU.CAN.VCU_Body.GW_VCU_2.VCU_TqReqCmd` | 前后电机转矩、前后电机转速、车辆速度及相关动力 CAN 输出 | 通过动力请求和状态计算间接传播 |
| `Veh_1.FromVCU.CAN.VCU_Power.VCU_MC_TrqCtrl.VCU_Target_output_MaxTorque` | `MC_Status.MC_max_Torque_Limit_ToBus` | 动力域最大转矩限制链路 |
| `Veh_1.ToModelbase.FromDriverManeuver.SteeringWheelAngle_rad` | 车辆速度及车辆动力学相关状态 | 模型基础物理反馈链路，需结合工况验证 |

## 注入建议

建议使用 `Veh_1_Input_Output_Impact.csv` 选择单个输入，依次进行阶跃、越界、冻结、恢复和丢帧注入；同时记录输入原值、注入值、持续时间、恢复时间，以及对应输出的变化量和响应延迟。

静态依赖只说明生成代码中存在数据传播路径。条件分支、限幅、参数覆盖、状态机和跨步状态可能使输出不变化、延迟变化或只在特定工况下变化，因此 `Parameter/state only` 和 `Unresolved static path` 不应直接理解为“输入与输出完全无关”。
