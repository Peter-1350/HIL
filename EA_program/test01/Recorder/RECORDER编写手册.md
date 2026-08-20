# `.dr` Recorder 文件编写手册

本文根据本项目的空模板 `VCU_HIL_RCP/.em/EEProject/.ee/Data Recorder/template.dr`、`Recorder/FI-01-制动踏板.dr` 及 `Recorder` 目录下其他已存在的 `.dr` 文件整理。`.dr` 是独立于 `.case` 的 UTF-8（无 BOM）JSON 录波器配置：它定义“采什么、多久采一次、文件写到哪里”，而 `.case` 通过 `StartRecorder` / `StopRecorder` 决定“何时录”。

## 1. 编写原则

每个故障用例的 Recorder 至少应覆盖以下四类信号：

| 类别 | 必录内容 | 作用 |
| --- | --- | --- |
| 注入源 | 所有被 `.case` 的 `Write` 改写的接口 | 证明实际写入值、持续时间和最终恢复值。 |
| 工况上下文 | Key、挡位、油门、制动、驾驶模式等会影响解释的输入 | 排除“工况不一致”导致的伪响应。 |
| 直接响应 | 被测部件的直接输出、状态位、继电器/电压输出、实际扭矩等 | 判断注入是否到达目标支路。 |
| 系统响应 | 车速、轮速/电机转速、母线电流等 | 判断影响是否传播至车辆/能量层，并支持安全性分析。 |

不要只录写入端，也不要只录远端车速。FI-01 同时记录了制动踏板输入、Key/挡位/油门等上下文、制动继电器与主辅制动电压等直接响应，以及 `Vehspeed`、MC/BMS 母线电流、实际扭矩等系统响应。

## 2. 文件骨架

新建 Recorder 应复制空 `template.dr`，而不是从零手写。模板保存了当前项目的类型信息、项目 ID、DAQ 容器和未启用的触发器。

```json
{
  "$type": "Kunyi.VCar.HIL.EE.Recorder.Entities.Recorder, Kunyi.VCar.HIL.EE.Recorder",
  "Lang": "zh-hans",
  "Id": "[新的Recorder GUID]",
  "Name": "[用例名].dr",
  "RtpcIp": "[目标RTPC地址]",
  "RtpcPort": 8888,
  "IpProjectId": "[当前HIL项目ID]",
  "EeProjectId": "[当前EE项目ID]",
  "Type": 0,
  "Host": null,
  "FileConfig": { "...": "..." },
  "DAQList": { "$type": "...", "$values": [ { "...": "..." } ] },
  "StartTrigger": { "...": "..." },
  "StopTrigger": { "...": "..." },
  "ConditionType": 0,
  "Edge": { "...": "..." },
  "Platform": 0
}
```

注意：`$type` 和 `$values` 是序列化格式的真实字段，不能删除、改名或将 `$values` 改为普通数组。JSON 不支持注释和尾随逗号。

### 2.1 必须使用无 BOM 的 UTF-8

Recorder 服务在 StartRecorder/StopRecorder 时以严格 `utf-8` 读取 `.dr` JSON；文件开头的 UTF-8 BOM（十六进制 `EF BB BF`）会被当作非法首字符，报错：

```text
Unexpected UTF-8 BOM (decode using utf-8-sig): line 1 column 1 (char 0)
```

因此 `.dr` 必须保存为 **UTF-8 without BOM**。已验证可用的 FI-01 和 FI-09 Recorder 均直接以 `{` 开头；不能以 BOM 开头。

Windows PowerShell 5.1 的 `Set-Content -Encoding UTF8` 会写入 BOM，不能直接用于生成 `.dr`。若需以脚本重写文件，应显式使用无 BOM 编码，例如：

```powershell
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
[System.IO.File]::WriteAllText($drPath, $jsonText, $utf8NoBom)
```

可用下面的只读检查确认文件头；正确结果应为 `7B`（紧凑 JSON）或 `7B-0D-0A` / `7B-0A`（格式化 JSON），绝不能是 `EF-BB-BF`：

```powershell
$bytes = Get-Content -LiteralPath $drPath -Encoding Byte -TotalCount 3
[BitConverter]::ToString($bytes)
```

## 3. 顶层标识与文件输出

### 3.1 Recorder 身份与项目绑定

- `Id`：Recorder 的 GUID。每个 `.dr` 应唯一。若复制已有 Recorder，必须生成新的 GUID。
- `Name`：Recorder 文件名，例如 `FI-01-制动踏板.dr`。它是 `.case` 中 `StartRecorder` / `StopRecorder` 的 `RecorderFile` 值。
- `RtpcIp`、`RtpcPort`：录波服务端点。空模板的 `RtpcIp=null`，FI-01 为 `192.168.3.199:8888`；应以目标工程实际连接配置为准。
- `IpProjectId`、`EeProjectId`：项目绑定 ID。它们不能从另一个工程随意照搬；新工程应从该工程导出的模板或由工具重新保存的文件取得。

### 3.2 FileConfig

FI-01 使用的配置如下：

```json
"FileConfig": {
  "$type": "Kunyi.VCar.HIL.EE.Recorder.Entities.FileConfig, Kunyi.VCar.HIL.EE.Recorder",
  "BaseName": "FI-01-制动踏板",
  "Dir": "D:\\TOOL\\KunyiSoftwares\\VcarEERecorder\\recorder_root\\FI-01-制动踏板",
  "Format": 0,
  "DevideBy": 0,
  "DevideSize": 500,
  "DevideTime": 60,
  "CsvColumns": null
}
```

`BaseName` 是输出数据的基础名，通常与 `Name` 去掉 `.dr` 后一致；`Dir` 是录波服务所在机器上的目录，不是本仓库目录。`Format=0`、`DevideBy=0`、`DevideSize=500`、`DevideTime=60` 为当前已验证案例的原值；其枚举含义和其他分卷模式未由样例证明，应在 UI 中配置后再导出，不要猜测数值。

## 4. DAQ 通道与采样周期

信号位于 `DAQList.$values`。空模板和现有 FI Recorder 都包含一个名为 `DAQ` 的通道：

```json
"DAQList": {
  "$type": "System.Collections.ObjectModel.ObservableCollection`1[[Kunyi.VCar.HIL.EE.Recorder.Entities.DAQChannel, Kunyi.VCar.HIL.EE.Recorder]], System.ObjectModel",
  "$values": [
    {
      "$type": "Kunyi.VCar.HIL.EE.Recorder.Entities.DAQChannel, Kunyi.VCar.HIL.EE.Recorder",
      "Id": "[DAQ数值ID]",
      "ProjectId": "[当前HIL项目ID]",
      "EnviromentId": "[当前环境ID]",
      "NodeId": null,
      "Name": "DAQ",
      "Cycle": 200,
      "Enabled": true,
      "SignalList": { "$type": "...", "$values": [] }
    }
  ]
}
```

已检查的 Recorder 均为单 DAQ：FI-01 至 FI-04 使用 `Cycle=200`，FI-05、FI-08 使用 `Cycle=100`。该数值是工具的采样周期配置；本项目采用 `100` 或 `200`，具体时间单位请以 Recorder UI 显示为准。涉及短暂变化、延迟或边沿时应优先选用项目已验证的较短周期，并在分析报告中记录实际周期。

`EnviromentId` 的拼写在文件中就是 `EnviromentId`，不得擅自改为 `EnvironmentId`。它与 `ProjectId`、`Identifier.HilProjectID` 必须来自同一目标工程。

## 5. SignalItem：一个信号的合法组成

每个录波信号都是 `SignalList.$values` 中的一个 `SignalItem`。应从同方向的既有信号复制完整对象，再同步替换所有路径字段：

```json
{
  "$type": "Kunyi.VCar.HIL.EE.Recorder.Entities.SignalItem, Kunyi.VCar.HIL.EE.Recorder",
  "Name": null,
  "InstanceName": null,
  "Identifier": {
    "$type": "Kunyi.VCar.HIL.EE.Entity.SignalDefine.Models.SignalIdentifier, Kunyi.VCar.HIL.EE.Entity",
    "HilProjectID": "[当前HIL项目ID]",
    "HilSystemID": null,
    "HilSystemName": "env_1_Design",
    "InstanceName": "Veh_1",
    "Category": [0输入 / 1输出],
    "Name": "Veh_1.[完整模型接口名]"
  },
  "DisplayName": "[末级显示名]",
  "FullName": "[HIL项目ID]/Veh_1/[InPort或OutPort]/Veh_1.[完整模型接口名]",
  "Enabled": true,
  "TableItems": {
    "$type": "System.Collections.ObjectModel.ObservableCollection`1[[System.String, System.Private.CoreLib]], System.ObjectModel",
    "$values": []
  },
  "IsTable": false,
  "ValueType": 0,
  "Converter": {
    "$type": "Kunyi.VCar.HIL.EE.Entity.SignalDefine.Converters.NothingConverter, Kunyi.VCar.HIL.EE.Entity",
    "Name": "Veh_1_IDENTICAL",
    "Unit": null,
    "ConversionType": "IDENTICAL",
    "PhyType": 0
  },
  "Descriptor": {
    "$type": "Kunyi.VCar.HIL.EE.Entity.SignalDefine.TypeDescriptors.ScalarDescriptor, Kunyi.VCar.HIL.EE.Entity",
    "Name": "Veh_1_[InPort或OutPort]_Veh_1.[完整模型接口名]",
    "BaseType": 9,
    "IsComplexType": false,
    "MinValue": -1.7976931348623157e+308,
    "MaxValue": 1.7976931348623157e+308,
    "Value": null,
    "ByteOrder": 0,
    "DefaultValue": null
  }
}
```

从 FI-01 可推得以下规则：

- `Category=0` 对应 `InPort` 输入；`Category=1` 对应 `OutPort` 输出。
- `Identifier.Name` 以 `Veh_1.` 开始；`FullName` 使用斜杠并包含项目 ID、`Veh_1/InPort` 或 `Veh_1/OutPort`；`Descriptor.Name` 使用下划线前缀和点号路径。
- `DisplayName` 通常为末级信号名，如 `Vehspeed `、`BrakePedal_perc`、`FTrq`；它只影响显示，但应与接口语义一致。
- 路径末尾空格是实际接口名的一部分。例如 FI-01 的 `Veh_1.PlantModel.PlantModel.Vehicle1.Vehspeed ` 和 `Veh_1.Driver.BrakeMode ` 均带尾随空格；复制/填写时必须保留，不能自动 trim。
- `ValueType`、`Descriptor.BaseType`、`Converter` 与数据类型相关。虽然当前多条 Double 标量均采用 `BaseType=9`，但不应把该结论外推至 Bool、枚举、数组或总线信号。此类信号应由工具添加一次后再复制其完整结构。

仅修改 `Identifier.Name` 并不足以形成可用信号；`Category`、`FullName`、`Descriptor.Name` 和项目/环境 ID 必须同步。最可靠做法是在 Recorder UI 中添加一次目标信号，再将导出的完整 `SignalItem` 作为后续脚本生成模板。

## 6. 输入与输出信号示例

FI-01 中的输入（写入端）示例：

```text
Identifier.Category = 0
Identifier.Name     = Veh_1.Driver.BrakePedal_perc
FullName            = [项目ID]/Veh_1/InPort/Veh_1.Driver.BrakePedal_perc
Descriptor.Name     = Veh_1_InPort_Veh_1.Driver.BrakePedal_perc
```

FI-01 中的输出（待测端）示例：

```text
Identifier.Category = 1
Identifier.Name     = Veh_1.PlantModel.PlantModel.Vehicle1.Vehspeed 
FullName            = [项目ID]/Veh_1/OutPort/Veh_1.PlantModel.PlantModel.Vehicle1.Vehspeed 
Descriptor.Name     = Veh_1_OutPort_Veh_1.PlantModel.PlantModel.Vehicle1.Vehspeed 
```

为 FI-09 转向角内部接口探测配置 Recorder 时，最小建议集为：

```text
注入端：Veh_1.ToModelbase.FromDriverManeuver.SteeringWheelAngle_rad
工况：Veh_1.Driver.Key、Veh_1.Driver.Gear_Button、Veh_1.Driver.AccPedal_perc、Veh_1.Driver.BrakePedal_perc、Veh_1.Driver.DriveMode
直接/系统响应：Vehspeed、FrontMotSpd、RearMotSpd、FTrq、RTrq
推荐交叉验证：MC_busbar_current_ToBus、BMS_HVBusCurr_ToBus
```

上述信号名来自模型接口目录；正式生成 `.dr` 时仍应在目标工程的 Recorder UI 中确认其实际 `InPort` / `OutPort` 与完整 SignalItem 元数据。

## 7. 与 `.case` 的关联

`.dr` 内没有 case 文件名，也没有自动启动逻辑。要让用例控制录波，需要在 `.case` 中添加 Recorder Action：

```xml
<Action>StartRecorder</Action>
<!-- RecorderFile 必须等于 .dr 的 Name，RecorderID 必须等于 .dr 的 Id -->
<Text>BaseName=FI-01-制动踏板, RecorderFile=FI-01-制动踏板.dr, StopFirstAndThenStart=True</Text>

<Action>StopRecorder</Action>
<Text>RecorderFile=FI-01-制动踏板.dr</Text>
```

`StartRecorder` 与 `StopRecorder` 的 `RecorderFile` 必须等于 `.dr/Name`；两者 Metadata 中的 `RecorderID` 必须等于 `.dr/Id`；Start 的 `RecorderBaseName` 与 `.dr/FileConfig/BaseName` 一致。它们是三个独立但必须同步的标识。

录波器可在用例开始前启动，也可只覆盖注入窗口。若需要保留基线和恢复行为，应在基线开始前启动，在最终恢复观察结束后停止。

## 8. 触发器与未验证字段

模板及已检查的所有现有 Recorder 都具有 `StartTrigger`、`StopTrigger` 和 `Edge` 节点，但三者均为 `Enabled=false`，条件列表为空。它们的 `ConditionType`、比较符、边沿和延迟的合法取值未从当前项目样例验证。

因此，普通 `.case` 驱动录波应保留这些节点原样且禁用。若需要条件触发，应在 UI 中配置一条可运行的触发器后导出最小 `.dr`，再将对应 JSON 结构补入本手册；不要从字段名猜测枚举数值。

## 9. 推荐生成流程与交付检查

1. 复制 `template.dr`，生成新 `Id`，修改 `Name`、`FileConfig.BaseName` 和录波服务输出目录。
2. 从当前目标工程或同项目既有 Recorder 复制 `DAQ` 的 `ProjectId`、`EnviromentId`、连接信息和完整 `SignalItem` 骨架。
3. 先加入所有 `.case/Write` 写入端，再加入工况上下文、直接响应和系统响应；按上述四类分组检查。
4. 选择项目已验证的 `Cycle`（当前为 100 或 200），避免因采样过慢漏掉故障边沿。
5. 保持触发器禁用，除非已有 UI 导出的有效触发器样例。
6. 在 `.case` 中同步填写 Recorder 的 `Name`、`Id`、`BaseName`，执行一次短录波并核查输出文件和信号列。

交付前检查：

- JSON 能解析；所有 `$type`、`$values` 容器仍存在。
- `.dr/Id` 唯一，`Name`、`BaseName`、输出目录符合本用例命名。
- 项目 ID、环境 ID、RTPC 信息属于当前实际工程。
- 每个 SignalItem 的 `Identifier`、`FullName`、`Descriptor`、输入输出方向相互一致；没有遗漏路径尾随空格。
- 录波信号同时包含注入源、工况、直接响应和系统响应。
- `.case` 的 Start/Stop Recorder 元数据与 `.dr` 三项标识完全一致。
