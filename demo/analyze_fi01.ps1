param(
    [string]$TmpPath = '',
    [string]$ConfigPath = ''
)

$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($TmpPath)) {
    $recorderRoot = 'D:\TOOL\KunyiSoftwares\VcarEERecorder\recorder_root'
    $candidate = Get-ChildItem -LiteralPath $recorderRoot -Recurse -File -Filter '*.tmp' |
        Where-Object { $_.Name -like 'FI-01-*' } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($null -eq $candidate) { throw 'No FI-01 TMP recording file was found under the recorder root.' }
    $TmpPath = $candidate.FullName
}
if ([string]::IsNullOrWhiteSpace($ConfigPath)) {
    $configCandidate = Get-ChildItem -LiteralPath (Split-Path -Parent $TmpPath) -File -Filter '*_config.json' |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($null -eq $configCandidate) { throw 'No recorder configuration JSON was found beside the TMP file.' }
    $ConfigPath = $configCandidate.FullName
}
$parsedConfig = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
$signalConfigs = @($parsedConfig | Sort-Object Index)
$recordSize = ($signalConfigs | ForEach-Object { $_.Offset + $_.Length } | Measure-Object -Maximum).Maximum
$signalNames = @()
foreach ($config in $signalConfigs) {
    $signalName = switch -Wildcard ($config.Signal.Name) {
        '*Vehicle1.Vehspeed*' { 'Vehspeed'; break }
        '*BMS_HVBusCurr_ToBus' { 'BMS_HVBusCurr'; break }
        '*MC_busbar_current_ToBus' { 'MC_busbar_current'; break }
        '*MC_motor_speed_ToBus' { 'MC_motor_speed'; break }
        '*BrakeOpen1_Out' { 'BrakeOpen1'; break }
        '*BrakeOpen2_Out' { 'BrakeOpen2'; break }
        '*BRK_Main_Out' { 'BRK_Main'; break }
        '*BRK_Auxi_Out' { 'BRK_Auxi'; break }
        '*BrakePedal_perc' { 'BrakePedal_perc'; break }
        '*AccPedal_perc' { 'AccPedal_perc'; break }
        '*Driver.BrakeMode*' { 'BrakeMode'; break }
        '*Driver.DriveMode' { 'DriveMode'; break }
        '*Gear_Button' { 'Gear_Button'; break }
        '*Driver.Key' { 'Key'; break }
        default { $config.Signal.Name }
    }
    if ($signalNames -contains $signalName) { throw "Duplicate normalized signal name: $signalName" }
    $signalNames += $signalName
}
$bytes = [IO.File]::ReadAllBytes($TmpPath)
if (($bytes.Length % $recordSize) -ne 0) { throw "Unexpected TMP size: $($bytes.Length) is not divisible by $recordSize." }

$rows = @()
$count = [int]($bytes.Length / $recordSize)
for ($index = 0; $index -lt $count; $index++) {
    $offset = $index * $recordSize
    $row = [ordered]@{ Index = $index; RawTime = [BitConverter]::ToInt64($bytes, $offset) }
    for ($signalIndex = 0; $signalIndex -lt $signalNames.Count; $signalIndex++) {
        $row[$signalNames[$signalIndex]] = [BitConverter]::ToDouble($bytes, $offset + $signalConfigs[$signalIndex].Offset)
    }
    $rows += [pscustomobject]$row
}

$summary = @()
foreach ($signal in $signalNames) {
    $measure = $rows | Measure-Object -Property $signal -Minimum -Maximum -Average
    $maxChange = 0.0
    $maxChangeIndex = 0
    $changeCount = 0
    for ($index = 1; $index -lt $rows.Count; $index++) {
        $change = [Math]::Abs($rows[$index].$signal - $rows[$index - 1].$signal)
        if ($change -gt 1.0e-9) { $changeCount++ }
        if ($change -gt $maxChange) { $maxChange = $change; $maxChangeIndex = $index }
    }
    $summary += [pscustomobject]@{
        Signal = $signal
        First = $rows[0].$signal
        Last = $rows[-1].$signal
        Min = $measure.Minimum
        Max = $measure.Maximum
        Average = $measure.Average
        ChangeCount = $changeCount
        MaxStepChange = $maxChange
        MaxStepChangeIndex = $maxChangeIndex
    }
}

$transitions = @()
foreach ($signal in @('BrakeOpen1', 'BrakeOpen2', 'BRK_Main', 'BRK_Auxi')) {
    for ($index = 1; $index -lt $rows.Count; $index++) {
        if ([Math]::Abs($rows[$index].$signal - $rows[$index - 1].$signal) -gt 1.0e-9) {
            $transitions += [pscustomobject]@{
                Signal = $signal
                Index = $index
                RawTime = $rows[$index].RawTime
                Previous = $rows[$index - 1].$signal
                Current = $rows[$index].$signal
            }
        }
    }
}

function Get-WindowStats {
    param([object[]]$WindowRows, [string]$Signal)
    $values = @($WindowRows | ForEach-Object { [double]$_.$Signal })
    [pscustomobject]@{
        Start = $values[0]
        End = $values[$values.Count - 1]
        Min = ($values | Measure-Object -Minimum).Minimum
        Max = ($values | Measure-Object -Maximum).Maximum
        Average = ($values | Measure-Object -Average).Average
    }
}

$brakeEvents = @()
$eventStart = $null
for ($index = 0; $index -lt $rows.Count; $index++) {
    $isActive = $rows[$index].BrakeOpen1 -gt 0
    if ($isActive -and $null -eq $eventStart) { $eventStart = $index }
    if ((-not $isActive) -and $null -ne $eventStart) {
        $activeRows = @($rows[$eventStart..($index - 1)])
        $brakeEvents += [pscustomobject]@{
            Event = $brakeEvents.Count + 1
            StartIndex = $eventStart
            EndIndex = $index
            StartSeconds = ($rows[$eventStart].RawTime - $rows[0].RawTime) / 1000000.0
            EndSeconds = ($rows[$index].RawTime - $rows[0].RawTime) / 1000000.0
            ActiveDurationSeconds = ($rows[$index].RawTime - $rows[$eventStart].RawTime) / 1000000.0
            Relay1Start = $rows[$eventStart].BrakeOpen1
            Relay2Start = $rows[$eventStart].BrakeOpen2
            BRKMain = Get-WindowStats $activeRows 'BRK_Main'
            BRKAux = Get-WindowStats $activeRows 'BRK_Auxi'
            VehicleSpeed = Get-WindowStats $activeRows 'Vehspeed'
            MotorSpeed = Get-WindowStats $activeRows 'MC_motor_speed'
            MotorBusbarCurrent = Get-WindowStats $activeRows 'MC_busbar_current'
            BMSBusCurrent = Get-WindowStats $activeRows 'BMS_HVBusCurr'
        }
        $eventStart = $null
    }
}

$relayMismatchCount = @($rows | Where-Object { $_.BrakeOpen1 -ne $_.BrakeOpen2 }).Count
$voltageRatioError = @($rows | ForEach-Object { [Math]::Abs($_.BRK_Main - 2.0 * $_.BRK_Auxi) } | Measure-Object -Maximum).Maximum

[pscustomobject]@{
    RecordSize = $recordSize
    TmpPath = $TmpPath
    ConfigPath = $ConfigPath
    RecordCount = $rows.Count
    FirstRawTime = $rows[0].RawTime
    LastRawTime = $rows[-1].RawTime
    TickDeltaFirst = $rows[1].RawTime - $rows[0].RawTime
    TickDeltaTotal = $rows[-1].RawTime - $rows[0].RawTime
    Summary = $summary
    BrakeTransitions = $transitions
    BrakeEvents = $brakeEvents
    RelayMismatchCount = $relayMismatchCount
    MaxBrakeVoltageRatioError = $voltageRatioError
    FirstRows = @($rows | Select-Object -First 3)
    LastRows = @($rows | Select-Object -Last 3)
} | ConvertTo-Json -Depth 6
