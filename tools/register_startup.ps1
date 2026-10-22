param([Parameter(Mandatory=$true)][string]$ProjectRoot,
      [Parameter(Mandatory=$true)][string]$PythonExe,
      [Parameter(Mandatory=$true)][string]$Account,
      [Parameter(Mandatory=$true)][string]$TaskName)
$ErrorActionPreference = 'Stop'
$resultPath = Join-Path $ProjectRoot 'state\startup_task_result.json'
try {
    if (!(Test-Path -LiteralPath $PythonExe -PathType Leaf)) { throw 'Python executable is missing.' }
    $launcher = Join-Path $ProjectRoot 'project_launcher.py'
    if (!(Test-Path -LiteralPath $launcher -PathType Leaf)) { throw 'Project launcher is missing.' }
    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existing -and $existing.Description -ne ('IZZI Library: ' + $ProjectRoot)) { throw 'A different task already uses this name.' }
    $credential = Get-Credential -UserName $Account -Message 'IZZI: Windows password for starting before sign-in. Use your password, not Windows Hello PIN.'
    if ($null -eq $credential) { throw 'Setup cancelled.' }
    $expected = ([System.Security.Principal.NTAccount]$Account).Translate([System.Security.Principal.SecurityIdentifier]).Value
    $actual = ([System.Security.Principal.NTAccount]$credential.UserName).Translate([System.Security.Principal.SecurityIdentifier]).Value
    if ($expected -ne $actual) { throw 'Use the current project Windows account.' }
    $action = New-ScheduledTaskAction -Execute $PythonExe -Argument ('-u "' + $launcher + '"') -WorkingDirectory $ProjectRoot
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $trigger.Delay = 'PT30S'
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
    # The password is handed to Windows Task Scheduler, never saved in the project.
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -User $Account -Password $credential.GetNetworkCredential().Password -RunLevel Limited -Description ('IZZI Library: ' + $ProjectRoot) -Force | Out-Null
    $result = @{ok=$true; task=$TaskName; account=$Account; message='Installed: starts 30 seconds after Windows boot, before sign-in.'}
} catch {
    $result = @{ok=$false; task=$TaskName; account=$Account; message=$_.Exception.Message}
} finally {
    $credential = $null
}
New-Item -ItemType Directory -Path (Split-Path $resultPath) -Force | Out-Null
$result | ConvertTo-Json | Set-Content -LiteralPath $resultPath -Encoding UTF8
