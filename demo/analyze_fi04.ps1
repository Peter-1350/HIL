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
            $null -ne $config -and (Get-Content -LiteralPath $config.FullName -Raw).Contains('MC_motor_Torque_ToBus')
        } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($null -eq $candidate) { throw 'No FI-04 TMP recording was found.' }
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
        '*VCU_TqReqCmd' { 'VCU_TqReqCmd'; break }
        '*Driveline.RearMotSpd' { 'RearMotSpd'; break }
        '*MotTrqManagement.RTrq' { 'RTrq'; break }
        '*Vehicle1.Vehspeed*' { 'Vehspeed'; break }
        '*FMotor.Motor.MotTrqManagement.FTrq' { 'FTrq'; break }
        '*FMotor.Motor.MotTrq' { 'FMotTrq'; break }
        '*Driveline.FrontMotSpd' { 'FrontMotSpd'; break }
        '*MC_motor_Torque_ToBus' { 'MCMotorTorque'; break }
        '*MC_motor_speed_ToBus' { 'MCMotorSpeed'; break }
        '*MC_busbar_current_ToBus' { 'MCBusCurrent'; break }
        '*BMS_HVBusCurr_ToBus' { 'BMSBusCurrent'; break }
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

$gearRuns = @()
$runStart = 0
for ($index = 1; $index -le $rows.Count; $index++) {
    $endOfRun = $index -eq $rows.Count -or [math]::Abs($rows[$index].Gear_Button - $rows[$index - 1].Gear_Button) -gt 1e-9
    if ($endOfRun) {
        $window = @($rows[$runStart..($index - 1)])
        $gearRuns += [pscustomobject]@{
            Run = $gearRuns.Count + 1
            StartIndex = $runStart
            EndIndex = $index
            StartSeconds = ($rows[$runStart].RawTime - $rows[0].RawTime) / 1000000.0
            EndSeconds = ($rows[$index - 1].RawTime - $rows[0].RawTime) / 1000000.0
            Gear = $rows[$runStart].Gear_Button
            Key = Get-WindowStats $window 'Key'
            AccPedal = Get-WindowStats $window 'AccPedal_perc'
            BrakePedal = Get-WindowStats $window 'BrakePedal_perc'
            TqReq = Get-WindowStats $window 'VCU_TqReqCmd'
            RTrq = Get-WindowStats $window 'RTrq'
            FTrq = Get-WindowStats $window 'FTrq'
            FMotTrq = Get-WindowStats $window 'FMotTrq'
            VehicleSpeed = Get-WindowStats $window 'Vehspeed'
            RearMotorSpeed = Get-WindowStats $window 'RearMotSpd'
            FrontMotorSpeed = Get-WindowStats $window 'FrontMotSpd'
            MCMotorTorque = Get-WindowStats $window 'MCMotorTorque'
            MCMotorSpeed = Get-WindowStats $window 'MCMotorSpeed'
            MCBusCurrent = Get-WindowStats $window 'MCBusCurrent'
            BMSBusCurrent = Get-WindowStats $window 'BMSBusCurrent'
        }
        $runStart = $index
    }
}

$rTrqRequestError = 0.0
$fTrqRequestError = 0.0
$fMotTrqFTrqError = 0.0
foreach ($row in $rows) {
    $rTrqRequestError = [math]::Max($rTrqRequestError, [math]::Abs($row.RTrq - $row.VCU_TqReqCmd))
    $fTrqRequestError = [math]::Max($fTrqRequestError, [math]::Abs($row.FTrq - $row.VCU_TqReqCmd))
    $fMotTrqFTrqError = [math]::Max($fMotTrqFTrqError, [math]::Abs($row.FMotTrq - $row.FTrq))
}

[pscustomobject]@{
    TmpPath = $TmpPath
    ConfigPath = $ConfigPath
    RecordSize = $recordSize
    RecordCount = $rows.Count
    SampleIntervalMicroseconds = $rows[1].RawTime - $rows[0].RawTime
    DurationSeconds = ($rows[-1].RawTime - $rows[0].RawTime) / 1000000.0
    Summary = $summary
    GearRuns = $gearRuns
    MaxRTrqRequestDifference = $rTrqRequestError
    MaxFTrqRequestDifference = $fTrqRequestError
    MaxFMotTrqFTrqDifference = $fMotTrqFTrqError
} | ConvertTo-Json -Depth 6
