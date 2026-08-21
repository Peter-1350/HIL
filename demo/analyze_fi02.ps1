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
            $null -ne $config -and (Get-Content -LiteralPath $config.FullName -Raw).Contains('ACC_Main_Out_Out')
        } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($null -eq $candidate) { throw 'No FI-02 TMP recording was found.' }
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
        '*Gear_Button' { 'Gear_Button'; break }
        '*BrakePedal_perc' { 'BrakePedal_perc'; break }
        '*Driver.DriveMode' { 'DriveMode'; break }
        '*VCU_TqReqCmd' { 'VCU_TqReqCmd'; break }
        '*ACC_Main_Out_Out' { 'ACC_Main_Out'; break }
        '*ACC_Auxi_Out_Out' { 'ACC_Auxi_Out'; break }
        '*Vehicle1.Vehspeed*' { 'Vehspeed'; break }
        '*MotTrqManagement.RTrq' { 'RTrq'; break }
        '*FMotor.Motor.MotTrq' { 'FMotTrq'; break }
        '*Driveline.RearMotSpd' { 'RearMotSpd'; break }
        '*Driveline.FrontMotSpd' { 'FrontMotSpd'; break }
        '*Driver.Key' { 'Key'; break }
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

$pedalRuns = @()
$runStart = 0
for ($index = 1; $index -le $rows.Count; $index++) {
    $endOfRun = $index -eq $rows.Count -or [math]::Abs($rows[$index].AccPedal_perc - $rows[$index - 1].AccPedal_perc) -gt 1e-9
    if ($endOfRun) {
        $window = @($rows[$runStart..($index - 1)])
        $pedalRuns += [pscustomobject]@{
            Run = $pedalRuns.Count + 1
            StartIndex = $runStart
            EndIndex = $index
            StartSeconds = ($rows[$runStart].RawTime - $rows[0].RawTime) / 1000000.0
            EndSeconds = ($rows[$index - 1].RawTime - $rows[0].RawTime) / 1000000.0
            Pedal = $rows[$runStart].AccPedal_perc
            Gear = Get-WindowStats $window 'Gear_Button'
            BrakePedal = Get-WindowStats $window 'BrakePedal_perc'
            Key = Get-WindowStats $window 'Key'
            TqReq = Get-WindowStats $window 'VCU_TqReqCmd'
            ACCMain = Get-WindowStats $window 'ACC_Main_Out'
            ACCAux = Get-WindowStats $window 'ACC_Auxi_Out'
            VehicleSpeed = Get-WindowStats $window 'Vehspeed'
            FrontMotorTorque = Get-WindowStats $window 'FMotTrq'
            RearMotorTorque = Get-WindowStats $window 'RTrq'
            FrontMotorSpeed = Get-WindowStats $window 'FrontMotSpd'
            RearMotorSpeed = Get-WindowStats $window 'RearMotSpd'
        }
        $runStart = $index
    }
}

$mainError = 0.0
$auxError = 0.0
$frontTorqueRequestError = 0.0
$rearTorqueRequestError = 0.0
foreach ($row in $rows) {
    $clampedPedal = [math]::Min([math]::Max($row.AccPedal_perc, 0), 100)
    $expectedMain = 1.0 + 0.03 * $clampedPedal
    $mainError = [math]::Max($mainError, [math]::Abs($row.ACC_Main_Out - $expectedMain))
    $auxError = [math]::Max($auxError, [math]::Abs($row.ACC_Auxi_Out - $expectedMain / 2.0))
    $frontTorqueRequestError = [math]::Max($frontTorqueRequestError, [math]::Abs($row.FMotTrq - $row.VCU_TqReqCmd))
    $rearTorqueRequestError = [math]::Max($rearTorqueRequestError, [math]::Abs($row.RTrq - $row.VCU_TqReqCmd))
}

[pscustomobject]@{
    TmpPath = $TmpPath
    ConfigPath = $ConfigPath
    RecordSize = $recordSize
    RecordCount = $rows.Count
    FirstRawTime = $rows[0].RawTime
    LastRawTime = $rows[-1].RawTime
    SampleIntervalMicroseconds = $rows[1].RawTime - $rows[0].RawTime
    DurationSeconds = ($rows[-1].RawTime - $rows[0].RawTime) / 1000000.0
    Summary = $summary
    PedalRuns = $pedalRuns
    MaxACCMainMappingError = $mainError
    MaxACCAuxMappingError = $auxError
    MaxFrontTorqueRequestDifference = $frontTorqueRequestError
    MaxRearTorqueRequestDifference = $rearTorqueRequestError
} | ConvertTo-Json -Depth 6
