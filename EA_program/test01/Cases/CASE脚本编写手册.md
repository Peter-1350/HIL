# `.case` 测试脚本编写手册

本文档根据 `Cases/template.case`、`Cases/FI-01 制动踏板.case`、同目录现有可解析案例及 `demo/random_seed.py` 整理。它描述的是本项目已验证的 XML 结构和 Action 格式；没有在案例中出现的字段或 Action，不能据此推断为受工具支持。

## 1. 文件骨架

`.case` 是 UTF-8 编码的 XML。新建文件应从 `template.case` 开始，保持根节点的命名空间声明和七个顶层节点：

```xml
<?xml version="1.0"?>
<TestCase xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
          xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <ID>test_唯一32位十六进制字符串</ID>
  <Mapping />
  <Variables />
  <Constants />
  <Namespaces />
  <InitSteps />
  <StopSteps />
  <TestSteps />
</TestCase>
```

`ID` 及每个 `StepItem/@ID` 使用 `test_` 加 32 位十六进制字符，例如 `test_33a48904f64c4f1c830bdfd267a08fcd`。同一文件中的 Step ID 必须唯一。

目前样例只在 `TestSteps` 中放置步骤；`InitSteps`、`StopSteps` 可保留为空。`Constants` 在已核对的案例中也为空。

## 2. 映射（Mapping）

所有会被 `Write` 或 `Read` 引用的模型信号，都应先在 `Mapping` 中定义，并且后续的 `<Mapping>` 文本必须与 `<MappingItem Name="…">` **逐字符一致**。仅被 `.dr` Recorder 录制的信号不需要为了录波而加入 `.case/Mapping`。

```xml
<Mapping>
  <MappingItem Name="[0]: env_1/第三方模型/Veh_1/InputPort/Veh_1/Driver/BrakePedal_perc"
               Category="VCU_HIL : env_1">
    <RealTargetSource>env_1_Design/Veh_1/InPort/Veh_1.Driver.BrakePedal_perc</RealTargetSource>
    <_IsChecked>false</_IsChecked>
    <Target>VCU_HIL/[0]: env_1/第三方模型/Veh_1/InputPort/Veh_1/Driver/BrakePedal_perc</Target>
    <DataType>Float</DataType>
    <Unit>_</Unit>
    <Description />
    <RefCount>12</RefCount>
    <IsChecked>false</IsChecked>
  </MappingItem>
</Mapping>
```

要点：

- `Name` 是脚本侧路径；`RealTargetSource` 是设计模型侧路径；`Target` 为 `Category` 对应目标前缀加脚本侧路径。
- 不要从显示名称猜测路径。应从已导出的案例、模型接口或工具 UI 复制完整路径（空格、中英文、CAN 报文名和括号均是路径的一部分）。
- `DataType`、`Unit`、`Category` 应沿用模型接口的实际值。已见数据类型为 `Float`。
- `RefCount` 是工具维护的引用计数。案例通常与映射使用次数一致；手工生成时建议填入实际引用次数，并在工具中重新打开/保存后复核。

## 3. 变量与命名空间

读取值、函数返回值或表达式中使用的变量，应声明在 `Variables`，引用时写作 `$变量名`。不要为录波数据临时创建变量；录波器会持续保存其配置中全部信号的值变化。

```xml
<Variables>
  <VariableItem Name="Speed" DataType="Float" Description="">
    <InitialValue>0</InitialValue>
    <CurrentValue />
    <RefCount>0</RefCount>
  </VariableItem>
</Variables>
```

Python 扩展 Action 要求命名空间。例如 `RandomUniform` 的现有案例同时声明并在步骤中引用 `random_seed`：

```xml
<Namespaces>
  <NamespaceItem Name="random_seed"><RefCount>1</RefCount></NamespaceItem>
</Namespaces>
```

`random_seed` 是模块名（对应 `random_seed.py` 文件名去掉 `.py`），而不是函数名。该名称应同时出现在顶层 `Namespaces` 与对应扩展步骤的 `<NamespaceItem>` 中。

## 4. StepItem 通用规则

每个步骤位于 `TestSteps`，其最小公共字段如下：

```xml
<StepItem ID="test_..." Name="显示名称" TestType="TCG 或 TCS">
  <Path>/父组/父控制结构</Path>
  <Action>Action名称</Action>
  <!-- 有参数时放 Parameter；部分 Read 有 Expectation -->
  <Value />
  <Comment>可选说明</Comment>
  <IsCommented>false</IsCommented>
</StepItem>
```

- `TCG` 为结构/控制节点（Group、While、Loop、IfThenElse）；`TCS` 为执行节点（Write、Read、Wait、RandomUniform、录波操作）。
- `Path` 指向父节点而不是本节点。顶层步骤为 `/`；若 Group 名为 `场景A`，其子步骤为 `/场景A`；While 的子步骤为 `/场景A/While`。
- 兄弟步骤在 XML 中的先后顺序就是执行顺序。`Path` 只建立层级，不能代替排序。
- XML 特殊字符必须转义：表达式中的 `<`、`<=` 分别写成 `&lt;`、`&lt;=`；文本中的 `&` 写成 `&amp;`。
- `Name` 是 UI 名称；同类型步骤可重复命名为 `Write`、`Wait`、`Read`。`Comment` 用于人类可读说明。

## 5. 已验证 Action 模板

以下模板中的方括号内容是占位符，生成实际文件时必须替换；不要将方括号原样写入 XML。

### Group：分组

```xml
<StepItem ID="test_[id]" Name="[场景名称]" TestType="TCG">
  <Path>/</Path><Action>Group</Action><Value />
  <Comment /><IsCommented>false</IsCommented>
</StepItem>
```

用于组织场景，不含 `Parameter`。子步骤的 `Path` 为 `/<场景名称>`。

### Write：写入模型信号

```xml
<StepItem ID="test_[id]" Name="Write" TestType="TCS">
  <Path>/[父路径]</Path><Action>Write</Action>
  <Parameter xsi:type="Parameter">
    <Text>[映射路径] = [值或$变量]</Text>
    <Metadata xsi:type="Metadata">
      <Mapping>[映射路径]</Mapping><Constant />
      <IsValueInExpression>true</IsValueInExpression>
      <Value>[值或$变量]</Value><IsPythonMethod>false</IsPythonMethod>
    </Metadata>
  </Parameter>
  <Value /><Comment>[说明]</Comment><IsCommented>false</IsCommented>
</StepItem>
```

示例值可为 `100`、`-50` 或 `$random_temp`。`Text`、`Metadata/Mapping` 与 `Metadata/Value` 必须和实际写入内容同步修改。

### Wait：等待

```xml
<StepItem ID="test_[id]" Name="Wait" TestType="TCS">
  <Path>/[父路径]</Path><Action>Wait</Action>
  <Parameter xsi:type="Parameter">
    <Text>[时长] ms</Text>
    <Metadata xsi:type="WaitMetadata"><Duration>[时长]</Duration><Unit>ms</Unit></Metadata>
  </Parameter>
  <Value /><Comment /><IsCommented>false</IsCommented>
</StepItem>
```

现有案例使用 `ms`。`Text` 的数值、`Duration` 和 `Unit` 要保持一致。

### Read：读取、保存或判定

> **提示：Recorder 与 Read 的职责不同。** 凡是为了记录写入值、待测信号或整个测试过程中的信号变化，应将信号加入配套 `.dr`，由 Recorder（录波文件）连续采样；**不应**为数据记录目的在 `.case` 中插入 `Read`。`Read` 只在测试逻辑需要立刻取得一个值时使用：将该值保存到变量供 `While` / `IfThenElse` / 后续 `Write` 使用，或对该次读取进行 `Expectation` 判定。

**只读取并保存至变量：**

```xml
<StepItem ID="test_[id]" Name="Read" TestType="TCS">
  <Path>/[父路径]</Path><Action>Read</Action>
  <Parameter xsi:type="Parameter">
    <Text>Mapping = [映射路径], Timeout = [超时ms]</Text>
    <Metadata xsi:type="ReadMetadata">
      <CanSaveValue>true</CanSaveValue><CanEvaluation>false</CanEvaluation>
      <Mapping>[映射路径]</Mapping><Variable>[变量名]</Variable>
      <Constant /><Value /><Timeout>[超时ms]</Timeout>
    </Metadata>
  </Parameter>
  <Value>[变量名]</Value><Comment>[说明]</Comment><IsCommented>false</IsCommented>
</StepItem>
```

**读取并进行数值判定：**

```xml
<StepItem ID="test_[id]" Name="Read" TestType="TCS">
  <Path>/[父路径]</Path><Action>Read</Action>
  <Parameter xsi:type="Parameter">
    <Text>Mapping = [映射路径], Timeout = [超时ms]</Text>
    <Metadata xsi:type="ReadMetadata">
      <CanSaveValue>false</CanSaveValue><CanEvaluation>true</CanEvaluation>
      <Mapping>[映射路径]</Mapping><Constant /><Value /><Timeout>[超时ms]</Timeout>
    </Metadata>
  </Parameter>
  <Value />
  <Expectation xsi:type="ExpectationOption">
    <Comparison xsi:type="NumericComparison" Type="">
      <Measure>OperatingForce</Measure><Operator>==</Operator><Value>[期望值]</Value>
      <ToleranceType>None</ToleranceType><ToleranceValue />
    </Comparison>
  </Expectation>
  <Comment>[说明]</Comment><IsCommented>false</IsCommented>
</StepItem>
```

案例也存在“保存并判定”：将两项 `Can...` 都设为 `true`，同时保留 `<Variable>`、步骤 `<Value>` 和 `<Expectation>`。已验证比较符为 `==`，其他算子或容差写法需要先提供工具导出的样例。

### While：条件循环

```xml
<StepItem ID="test_[id]" Name="While" TestType="TCG">
  <Path>/[父路径]</Path><Action>While</Action>
  <Parameter xsi:type="Parameter">
    <Text>$[变量] &lt;= [阈值]</Text>
    <Metadata xsi:type="WhileMetadata">
      <Expression>$[变量] &lt;= [阈值]</Expression>
      <ExpressionEditMode>Easy</ExpressionEditMode>
    </Metadata>
  </Parameter>
  <Value /><Comment /><IsCommented>false</IsCommented>
</StepItem>
```

子步骤的父路径是 `/<父路径>/While`。循环体应更新参与条件的变量，并加入合理的 `Wait`，避免无终止的忙循环。

### Loop：定时循环

```xml
<StepItem ID="test_[id]" Name="Loop" TestType="TCG">
  <Path>/[父路径]</Path><Action>Loop</Action>
  <Parameter xsi:type="Parameter">
    <Text>[时长] ms</Text>
    <Metadata xsi:type="LoopMetadata">
      <CanSaveValue>false</CanSaveValue><LoopMode>Time</LoopMode>
      <LoopDurationUnit>ms</LoopDurationUnit><LoopCount>[时长]</LoopCount>
    </Metadata>
  </Parameter>
  <Value /><Comment /><IsCommented>false</IsCommented>
</StepItem>
```

这里只验证了 `LoopMode=Time` 的格式；`LoopCount` 在该模式下实际承载时长。

### IfThenElse：条件分支

条件节点、Then 和 Else 三者都使用 Action `IfThenElse`，区别在于第一个节点带条件参数：

```xml
<StepItem ID="test_[id1]" Name="If" TestType="TCG">
  <Path>/[父路径]</Path><Action>IfThenElse</Action>
  <Parameter xsi:type="Parameter">
    <Text>$[变量] == [值]</Text>
    <Metadata xsi:type="IfThenElseMetadata">
      <Condition>$[变量] == [值]</Condition><ExpressionEditMode>Easy</ExpressionEditMode>
    </Metadata>
  </Parameter>
  <Value /><Comment /><IsCommented>false</IsCommented>
</StepItem>
<StepItem ID="test_[id2]" Name="Then" TestType="TCG">
  <Path>/[父路径]/If</Path><Action>IfThenElse</Action>
  <Value /><Comment /><IsCommented>false</IsCommented>
</StepItem>
<StepItem ID="test_[id3]" Name="Else" TestType="TCG">
  <Path>/[父路径]/If</Path><Action>IfThenElse</Action>
  <Value /><Comment /><IsCommented>false</IsCommented>
</StepItem>
```

分支中的业务步骤再以 `/<父路径>/If/Then` 或 `/<父路径>/If/Else` 为父路径。现有案例在 Else 下额外放置 `Group`，这不是上面结构本身必需的字段。

### RandomUniform：Python 扩展 Action 示例

```xml
<StepItem ID="test_[id]" Name="[步骤名]" TestType="TCS">
  <NamespaceItem xsi:type="NamespaceItem" Name="random_seed"><RefCount>1</RefCount></NamespaceItem>
  <Path>/[父路径]</Path><Action>RandomUniform</Action>
  <Parameter xsi:type="Parameter">
    <Text>min_value = [最小值], max_value = [最大值]</Text>
    <Metadata xsi:type="FuncMetadata">
      <CanSaveValue>true</CanSaveValue><CanEvaluation>false</CanEvaluation>
      <Variable>[结果变量]</Variable><Constant /><Value />
      <MetadataCollection>
        <DicMetadata><Key>min_value</Key><Value>[最小值]</Value></DicMetadata>
        <DicMetadata><Key>max_value</Key><Value>[最大值]</Value></DicMetadata>
      </MetadataCollection>
    </Metadata>
  </Parameter>
  <Value>[结果变量]</Value><Comment>[说明]</Comment><IsCommented>false</IsCommented>
</StepItem>
```

这是 Python 扩展 Action，而非内置 Action。其函数本体是 `demo/random_seed.py` 中的 `RandomUniform`：

```python
def RandomUniform(min_value=0.0, max_value=100.0):
    return random.uniform(min_value, max_value)
```

`<Action>RandomUniform</Action>` 对应函数名，`NamespaceItem Name="random_seed"` 对应模块名。结果变量须预先在 `Variables` 声明；随后可用 `Write` 将 `$[结果变量]` 写入映射。

### StartRecorder / StopRecorder：录波器控制

```xml
<StepItem ID="test_[id]" Name="StartRecorder" TestType="TCS">
  <Path>/[父路径]</Path><Action>StartRecorder</Action>
  <Parameter xsi:type="Parameter">
    <Text>BaseName=[名称], RecorderFile=[文件.dr], StopFirstAndThenStart=True</Text>
    <Metadata xsi:type="RecorderStartMetadata">
      <StopFirstAndThenStart>true</StopFirstAndThenStart><Action>Start</Action>
      <RecorderFile>[文件.dr]</RecorderFile><RecorderID>[录波器GUID]</RecorderID>
      <RecorderBaseName>[名称]</RecorderBaseName>
    </Metadata>
  </Parameter>
  <Value /><Comment /><IsCommented>false</IsCommented>
</StepItem>

<StepItem ID="test_[id]" Name="StopRecorder" TestType="TCS">
  <Path>/[父路径]</Path><Action>StopRecorder</Action>
  <Parameter xsi:type="Parameter">
    <Text>RecorderFile=[文件.dr]</Text>
    <Metadata xsi:type="RecorderStopMetadata">
      <Action>Stop</Action><RecorderFile>[文件.dr]</RecorderFile><RecorderID>[同一录波器GUID]</RecorderID>
    </Metadata>
  </Parameter>
  <Value /><Comment /><IsCommented>false</IsCommented>
</StepItem>
```

以当前 `FI-01 制动踏板.case` 为准，推荐在顶层测试步骤的开头启动、末尾停止 Recorder：

```xml
<StepItem ID="test_[id]" Name="StartRecorder" TestType="TCS">
  <Path>/</Path><Action>StartRecorder</Action>
  <Parameter xsi:type="Parameter">
    <Text>BaseName=FI-01, RecorderFile=FI-01-制动踏板.dr, StopFirstAndThenStart=True</Text>
    <Metadata xsi:type="RecorderStartMetadata">
      <StopFirstAndThenStart>true</StopFirstAndThenStart><Action>Start</Action>
      <RecorderFile>FI-01-制动踏板.dr</RecorderFile>
      <RecorderID>f11e4aff-4ca2-4034-a20c-7f2e6ad055e8</RecorderID>
      <RecorderBaseName>FI-01</RecorderBaseName>
    </Metadata>
  </Parameter>
  <Value /><Comment /><IsCommented>false</IsCommented>
</StepItem>
```

`RecorderFile` 和 `RecorderID` 必须取自同一已配置 `.dr`，且 Start 与对应 Stop 的这两个字段必须相同。`BaseName` / `RecorderBaseName` 为 StartRecorder 的运行配置，`Text` 与 Metadata 必须一致；它可以不同于 `.dr/FileConfig/BaseName`，FI-01 即为 `FI-01` 与 `FI-01-制动踏板` 的不同组合。不要自行伪造 `RecorderID`。

`StartRecorder` / `StopRecorder` 报 `Unexpected UTF-8 BOM` 时，通常不是 Action 格式错误，而是 `.dr` JSON 带有 UTF-8 BOM。Recorder 服务要求 `.dr` 为 UTF-8 **无 BOM**；检查和修复方法见 `Recorder/RECORDER编写手册.md` 的“必须使用无 BOM 的 UTF-8”。

## 6. Python 扩展 Action 的合法添加方式

Python 扩展由三部分共同组成：**可被执行器导入的 Python 模块**、**`.case` 顶层命名空间声明**、**带 `FuncMetadata` 的函数步骤**。仅把 Action 名写进 `.case` 并不能提供函数本体。

### 6.1 编写模块

创建一个模块文件，例如 `demo/signal_tools.py`。模块文件名、模块名和函数名都应使用 Python 合法标识符（字母、数字、下划线，且不能以数字开头）；不要使用空格、连字符或中文作为模块/函数名。

```python
# demo/signal_tools.py
def Clamp(value, lower=0.0, upper=100.0):
    """将 value 限制在 [lower, upper] 内，并返回一个数值。"""
    return max(lower, min(value, upper))
```

约定与限制：

- 函数必须定义在模块顶层，函数名与将写入 `<Action>` 的名称完全一致，且大小写敏感。
- 形参名是 `.case` 的参数键名；本例为 `value`、`lower`、`upper`。优先使用带默认值的简单标量参数，以便工具生成和调用。
- 当前可验证的格式是“返回一个值，并保存至一个 `Float` 变量”。复杂对象、多返回值、异步函数、异常处理和无返回值的副作用函数尚无成功案例，使用前需要先由工具导出样例验证。
- 模块在导入时应避免写入信号、启动线程、访问网络等副作用。`random_seed.py` 在导入时以当前纳秒设置随机种子，意味着每次运行结果不同；若测试需要可重复性，应把种子设计成显式参数或使用固定种子。
- `random_seed.py` 使用的 `random`、`time` 属于 Python 标准库，无额外安装依赖。若自定义模块依赖第三方包，必须将该包装入**测试工具实际使用的 Python 环境**，不能只安装在开发机的其他 Python 环境。

### 6.2 部署与命名空间声明

确保模块已部署到测试执行器可导入的位置，然后在 `.case` 顶层添加模块名：

```xml
<Namespaces>
  <NamespaceItem Name="signal_tools"><RefCount>1</RefCount></NamespaceItem>
</Namespaces>
```

本项目的 `RandomUniform` 使用 `demo/random_seed.py`，但 `.case` 本身不保存模块的绝对路径或 Python 搜索路径；它只保存 `random_seed` 这个模块名。因此，`demo` 是当前项目的源文件位置，是否能被目标测试工具自动搜索仍须通过一次导入/执行验证。若工具未发现模块，应将其放到工具配置的脚本目录，或将模块目录加入该工具进程的 Python 搜索路径，而不是修改 `.case` 中的模块名。

### 6.3 在 `.case` 中调用函数

为返回值声明变量，并用 `FuncMetadata` 添加步骤。通用模板如下：

```xml
<Variables>
  <VariableItem Name="clamped_value" DataType="Float" Description="">
    <InitialValue>0</InitialValue><CurrentValue /><RefCount>0</RefCount>
  </VariableItem>
</Variables>

<StepItem ID="test_[唯一ID]" Name="Clamp" TestType="TCS">
  <NamespaceItem xsi:type="NamespaceItem" Name="signal_tools">
    <RefCount>1</RefCount>
  </NamespaceItem>
  <Path>/[父路径]</Path>
  <Action>Clamp</Action>
  <Parameter xsi:type="Parameter">
    <Text>value = [输入值], lower = [下限], upper = [上限]</Text>
    <Metadata xsi:type="FuncMetadata">
      <CanSaveValue>true</CanSaveValue>
      <CanEvaluation>false</CanEvaluation>
      <Variable>clamped_value</Variable><Constant /><Value />
      <MetadataCollection>
        <DicMetadata><Key>value</Key><Value>[输入值]</Value></DicMetadata>
        <DicMetadata><Key>lower</Key><Value>[下限]</Value></DicMetadata>
        <DicMetadata><Key>upper</Key><Value>[上限]</Value></DicMetadata>
      </MetadataCollection>
    </Metadata>
  </Parameter>
  <Value>clamped_value</Value>
  <Comment>调用 signal_tools.Clamp</Comment>
  <IsCommented>false</IsCommented>
</StepItem>
```

必须保持以下名称和参数的一致性：

- 文件 `signal_tools.py` → 顶层和步骤级 `NamespaceItem/@Name` 为 `signal_tools`。
- `def Clamp(...)` → 步骤的 `<Action>` 为 `Clamp`。
- Python 形参名 → 每个 `<DicMetadata>/<Key>`；例如 `lower` 必须与函数形参 `lower` 相同。
- 返回变量 `clamped_value` → `FuncMetadata/Variable`、StepItem 的 `<Value>` 和顶层 `VariableItem/@Name` 三处一致。
- `Parameter/Text` 只是 UI 可读文本，但也应按相同顺序完整镜像实际 `MetadataCollection`，避免显示与执行不一致。

### 6.4 接入和验证顺序

1. 编写并在目标 Python 版本下独立调用函数，确认返回类型与预期一致。
2. 将模块及其依赖部署到测试执行器可导入的位置。
3. 以函数模块名添加顶层 `Namespaces/NamespaceItem`，并声明返回变量。
4. 添加带同一模块名的步骤级 `NamespaceItem`，使用 `Action=函数名`、`FuncMetadata` 和一项一个的 `DicMetadata` 参数。
5. 先建立只调用一次的最小案例，导入工具并执行；确认工具能发现 Action、参数绑定正确且结果写入变量后，再组合进循环、条件和信号写入逻辑。

## 7. 生成一个新用例的推荐顺序

1. 复制 `template.case`，生成新的根 `ID`。
2. 从模型或已导出案例复制要用的全部 `MappingItem`，而不是手写接口路径。
3. 补充变量和所需命名空间。
4. 先插入顶层 `Group`，再按照层级和执行顺序追加子 `StepItem`。
5. 需要全程录波的信号全部配置在配套 `.dr`；若由用例控制录波，在首个业务步骤前加入顶层 `StartRecorder`，在最终恢复等待后加入顶层 `StopRecorder`。
6. 每个 `Write` / `Read` 中将 `Text`、`Metadata` 和 `Value` 同步替换；只在后续逻辑需要变量值或即时判定时添加 `Read`。
7. 用 XML 解析器检查格式，再在目标工具中导入、保存和执行一次；工具能验证模型映射、录波器 ID 与其内部元数据。

## 8. 交付前检查清单

- XML 可解析；根节点带 `xmlns:xsi` 和 `xmlns:xsd`。
- 根 ID 和所有 Step ID 不重复。
- 每个被读写的 Mapping 均已定义，路径精确匹配。
- 每个 `$变量` 都已在 `Variables` 中声明；函数所需命名空间已经声明。
- `Path` 是父路径，且父节点存在；XML 中的步骤排序符合预期执行顺序。
- `Read` 的保存/判定开关、`Variable`、步骤 `Value`、`Expectation` 彼此一致。
- 不存在仅为“记录/观察”而添加的 `Read`；这些信号已加入对应 `.dr` 的 SignalList。
- Start/Stop Recorder 的 `RecorderFile`、`RecorderID` 指向同一真实录波器，并且 `Text` 与 Metadata 一致。
- 所有 `<Text>` 是对应 Metadata 的可读镜像，避免 UI 显示和实际执行元数据不一致。
- 每个 Python 扩展模块均可由目标执行器导入，函数名、形参名、模块名和 `FuncMetadata` 键名完全一致。

## 9. 需要补充样例的范围

当前手册足以生成并修改上述 10 类 Action 的案例。若后续要生成未出现的 Action，或要使用未见的模式，请提供由工具成功导出的最小 `.case` 示例（一个 Action 及其所需 Mapping/Variable/Namespace 即可）。尤其建议补充：其他函数 Action、非 `Time` 的 Loop、其他 Read 比较/容差形式、常量引用、Python 方法及异常/错误处理类步骤。
