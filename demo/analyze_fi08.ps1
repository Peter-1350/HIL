param(
    [string]$TmpPath = '',
    [string]$ConfigPath = ''
)

$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($TmpPath)) {
    $root = 'D:\TOOL\KunyiSoftwares\VcarEERecorder\recorder_root'
    $candidate = Get-ChildItem -LiteralPath $root -Recurse -File -Filter '*.tmp' |
        Where-Object {
            $config = Get-ChildItem -LiteralPath $_.DirectoryName -File -Filter '*_config.json' |
                Sort-Object LastWriteTime -Descending |
                Select-Object -First 1
            $null -ne $config -and (Get-Content -LiteralPath $config.FullName -Raw).Contains('MC_MaxToque_Limit_ToBus')
        } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($null -eq $candidate) { throw 'No FI-08 TMP recording was found.' }
    $TmpPath = $candidate.FullName
}
if ([string]::IsNullOrWhiteSpace($ConfigPath)) {
    $candidate = Get-ChildItem -LiteralPath (Split-Path -Parent $TmpPath) -File -Filter '*_config.json' |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($null -eq $candidate) { throw 'No recorder configuration JSON was found.' }
    $ConfigPath = $candidate.FullName
}

$parsedConfig = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
$configs = @($parsedConfig | Sort-Object Index)
$recordSize = ($configs | ForEach-Object { $_.Offset + $_.Length } | Measure-Object -Maximum).Maximum
$signalNames = foreach ($config in $configs) {
    switch -Wildcard ($config.Signal.Name) {
        '*AccPedal_perc' { 'AccPedal_perc'; break }
        '*Driver.BrakeMode*' { 'BrakeMode'; break }
        '*BrakePedal_perc' { 'BrakePedal_perc'; break }
        '*Driver.DriveMode' { 'DriveMode'; break }
        '*Gear_Button' { 'Gear_Button'; break }
        '*Driver.Key' { 'Key'; break }
        '*Vehicle1.Vehspeed*' { 'Vehspeed'; break }
        '*Driveline.FrontMotSpd' { 'FrontMotSpd'; break }
        '*Driveline.RearMotSpd' { 'RearMotSpd'; break }
        '*FMotor.Motor.MotTrqManagement.FTrq' { 'FTrq'; break }
        '*FMotor.Motor.MotTrq' { 'FMotTrq'; break }
        '*MotTrqManagement.RTrq' { 'RTrq'; break }
        '*MC_motor_Torque_ToBus' { 'MCMotorTorque'; break }
        '*MC_motor_speed_ToBus' { 'MCMotorSpeed'; break }
        '*MC_busbar_current_ToBus' { 'MCBusCurrent'; break }
        '*MC_MaxToque_Limit_ToBus' { 'MCMaxTorqueLimit'; break }
        '*MC_max_Torque_Limit_ToBus' { 'MCStatusTorqueLimit'; break }
        '*BMS_HVBusCurr_ToBus' { 'BMSBusCurrent'; break }
        '*BRK_Main_Out' { 'BRKMain'; break }
        '*BRK_Auxi_Out' { 'BRKAux'; break }
        '*ACC_Main_Out_Out' { 'ACCMain'; break }
        '*ACC_Auxi_Out_Out' { 'ACCAux'; break }
        '*BrakeOpen1_Out' { 'BrakeOpen1'; break }
        '*BrakeOpen2_Out' { 'BrakeOpen2'; break }
        default { $config.Signal.Name }
    }
}
if (($signalNames | Select-Object -Unique).Count -ne $signalNames.Count) { throw 'Duplicate normalized signal name.' }

$bytes = [IO.File]::ReadAllBytes($TmpPath)
if (($bytes.Length % $recordSize) -ne 0) { throw "Unexpected TMP size $($bytes.Length); record size is $recordSize." }
$count = [int]($bytes.Length / $recordSize)
$rows = for ($index = 0; $index -lt $count; $index++) {
    $base = $index * $recordSize
    $row = [ordered]@{ Index = $index; RawTime = [BitConverter]::ToInt64($bytes, $base) }
    for ($signalIndex = 0; $signalIndex -lt $signalNames.Count; $signalIndex++) {
        $row[$signalNames[$signalIndex]] = [BitConverter]::ToDouble($bytes, $base + $configs[$signalIndex].Offset)
    }
    [pscustomobject]$row
}

function Get-WindowStats {
    param([object[]]$WindowRows, [string]$Signal)
    $values = @($WindowRows | ForEach-Object { [double]$_.$Signal })
    [pscustomobject]@{
        Start = $values[0]
        End = $values[-1]
        Min = ($values | Measure-Object -Minimum).Minimum
        Max = ($values | Measure-Object -Maximum).Maximum
        Average = ($values | Measure-Object -Average).Average
    }
}

$summary = foreach ($signal in $signalNames) {
    $values = @($rows | ForEach-Object { [double]$_.$signal })
    $measure = $values | Measure-Object -Minimum -Maximum -Average
    $changes = 0
    for ($index = 1; $index -lt $values.Count; $index++) {
        if ([math]::Abs($values[$index] - $values[$index - 1]) -gt 1e-9) { $changes++ }
    }
    [pscustomobject]@{ Signal = $signal; First = $values[0]; Last = $values[-1]; Min = $measure.Minimum; Max = $measure.Maximum; Average = $measure.Average; ChangeCount = $changes }
}

$keyRuns = @()
$runStart = 0
for ($index = 1; $index -le $rows.Count; $index++) {
    $endOfRun = $index -eq $rows.Count -or [math]::Abs($rows[$index].Key - $rows[$index - 1].Key) -gt 1e-9
    if ($endOfRun) {
        $window = @($rows[$runStart..($index - 1)])
        $keyRuns += [pscustomobject]@{
            Run = $keyRuns.Count + 1
            StartIndex = $runStart
            EndIndex = $index
            StartSeconds = ($rows[$runStart].RawTime - $rows[0].RawTime) / 1000000.0
            EndSeconds = ($rows[$index - 1].RawTime - $rows[0].RawTime) / 1000000.0
            Key = $rows[$runStart].Key
            Gear = Get-WindowStats $window 'Gear_Button'
            AccPedal = Get-WindowStats $window 'AccPedal_perc'
            BrakePedal = Get-WindowStats $window 'BrakePedal_perc'
            VehicleSpeed = Get-WindowStats $window 'Vehspeed'
            FrontMotorTorque = Get-WindowStats $window 'FMotTrq'
            MCMotorTorque = Get-WindowStats $window 'MCMotorTorque'
            MCBusCurrent = Get-WindowStats $window 'MCBusCurrent'
            BMSBusCurrent = Get-WindowStats $window 'BMSBusCurrent'
            MCMaxTorqueLimit = Get-WindowStats $window 'MCMaxTorqueLimit'
            MCStatusTorqueLimit = Get-WindowStats $window 'MCStatusTorqueLimit'
        }
        $runStart = $index
    }
}

$fallingEdges = @()
for ($index = 1; $index -lt $rows.Count; $index++) {
    if ($rows[$index - 1].Key -gt 0 -and $rows[$index].Key -le 0) {
        $zeroIndex = $null
        for ($searchIndex = $index; $searchIndex -lt $rows.Count; $searchIndex++) {
            if ([math]::Abs($rows[$searchIndex].MCMotorTorque) -lt 1.0) { $zeroIndex = $searchIndex; break }
        }
        $fallingEdges += [pscustomobject]@{
            Index = $index
            TimeSeconds = ($rows[$index].RawTime - $rows[0].RawTime) / 1000000.0
            TorqueAtEdge = $rows[$index].MCMotorTorque
            FirstZeroTorqueIndex = $zeroIndex
            ZeroTorqueDelaySeconds = if ($null -ne $zeroIndex) { ($rows[$zeroIndex].RawTime - $rows[$index].RawTime) / 1000000.0 } else { $null }
        }
    }
}

$brkMainError = 0.0
$brkAuxError = 0.0
$accMainError = 0.0
$accAuxError = 0.0
$relayMismatchCount = 0
foreach ($row in $rows) {
    $brake = [math]::Min([math]::Max($row.BrakePedal_perc, 0), 100)
    $acc = [math]::Min([math]::Max($row.AccPedal_perc, 0), 100)
    $expectedBrk = 1.0 + 0.03 * $brake
    $expectedAcc = 1.0 + 0.03 * $acc
    $brkMainError = [math]::Max($brkMainError, [math]::Abs($row.BRKMain - $expectedBrk))
    $brkAuxError = [math]::Max($brkAuxError, [math]::Abs($row.BRKAux - $expectedBrk / 2.0))
    $accMainError = [math]::Max($accMainError, [math]::Abs($row.ACCMain - $expectedAcc))
    $accAuxError = [math]::Max($accAuxError, [math]::Abs($row.ACCAux - $expectedAcc / 2.0))
    if ($row.BrakeOpen1 -ne $row.BrakeOpen2) { $relayMismatchCount++ }
}

[pscustomobject]@{
    TmpPath = $TmpPath
    ConfigPath = $ConfigPath
    RecordSize = $recordSize
    RecordCount = $rows.Count
    SampleIntervalMicroseconds = $rows[1].RawTime - $rows[0].RawTime
    DurationSeconds = ($rows[-1].RawTime - $rows[0].RawTime) / 1000000.0
    Summary = $summary
    KeyRuns = $keyRuns
    FallingEdges = $fallingEdges
    MaxBRKMainMappingError = $brkMainError
    MaxBRKAuxMappingError = $brkAuxError
    MaxACCMainMappingError = $accMainError
    MaxACCAuxMappingError = $accAuxError
    RelayMismatchCount = $relayMismatchCount
} | ConvertTo-Json -Depth 6
