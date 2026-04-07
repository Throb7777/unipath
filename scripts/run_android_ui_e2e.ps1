param(
    [string]$RootDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$PythonExe = "C:\Users\Peter\anaconda3\python.exe",
    [string]$AdbExe = "C:\Users\Peter\AppData\Local\Android\Sdk\platform-tools\adb.exe",
    [int]$RelayPort = 18080,
    [string]$ApkPath = "",
    [string]$Url = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Stop-StaleRelayOnPort {
    param(
        [Parameter(Mandatory = $true)]
        [int]$Port
    )

    $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    foreach ($connection in $connections) {
        $processId = $connection.OwningProcess
        if (-not $processId) {
            continue
        }

        $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $processId" -ErrorAction SilentlyContinue
        $commandLine = $processInfo.CommandLine
        if ($commandLine -and $commandLine -match "(^| )(-m relay|run\.py start)( |$)") {
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
            Start-Sleep -Milliseconds 500
        }
    }
}

function Get-BoundsCenter {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Bounds
    )

    $match = [regex]::Match($Bounds, "\[(\d+),(\d+)\]\[(\d+),(\d+)\]")
    if (-not $match.Success) {
        throw "Unable to parse bounds: $Bounds"
    }

    $x1 = [int]$match.Groups[1].Value
    $y1 = [int]$match.Groups[2].Value
    $x2 = [int]$match.Groups[3].Value
    $y2 = [int]$match.Groups[4].Value

    return @([int](($x1 + $x2) / 2), [int](($y1 + $y2) / 2))
}

function Wait-ForRelayHealth {
    param(
        [Parameter(Mandatory = $true)]
        [string]$HealthUrl,
        [Parameter(Mandatory = $true)]
        [System.Diagnostics.Process]$RelayProcess
    )

    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Milliseconds 500
        try {
            $health = Invoke-RestMethod $HealthUrl -TimeoutSec 2
            if ($health.status -eq "ok") {
                return
            }
        } catch {
        }

        if ($RelayProcess.HasExited) {
            $stdout = $RelayProcess.StandardOutput.ReadToEnd()
            $stderr = $RelayProcess.StandardError.ReadToEnd()
            throw "Relay exited early.`nSTDOUT:`n$stdout`nSTDERR:`n$stderr"
        }
    }

    throw "Relay health check timed out: $HealthUrl"
}

function Wait-ForStatusActivity {
    param(
        [Parameter(Mandatory = $true)]
        [string]$AdbExePath
    )

    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Milliseconds 500
        $activityDump = ((& $AdbExePath shell dumpsys activity activities) -join "`n")
        if ($activityDump -match "topResumedActivity=.*SubmissionStatusActivity") {
            return $true
        }
    }

    return $false
}

function Get-LatestRelayTask {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RelayDirPath,
        [Parameter(Mandatory = $true)]
        [string]$PythonPath,
        [Parameter(Mandatory = $true)]
        [string]$ExpectedUrl
    )

    Push-Location $RelayDirPath
    try {
        $json = & $PythonPath run.py tasks list --json
    } finally {
        Pop-Location
    }

    if (-not $json) {
        return $null
    }

    $parsed = $json | ConvertFrom-Json
    if (-not $parsed) {
        return $null
    }
    $tasks =
        if ($parsed -is [System.Array]) {
            $parsed
        } elseif ($parsed.PSObject.Properties.Name -contains "tasks") {
            $parsed.tasks
        } else {
            @()
        }
    if (-not $tasks) {
        return $null
    }

    return $tasks | Where-Object { $_.normalizedUrl -eq $ExpectedUrl } | Select-Object -Last 1
}

if ([string]::IsNullOrWhiteSpace($Url)) {
    $Url = "https://example.com/android-ui-e2e-" + (Get-Date -Format "yyyyMMddHHmmss")
}

$androidStateDir = Join-Path $RootDir ".android-local"
$relayDir = Join-Path $RootDir "relay"
$runtimeDir = Join-Path $relayDir "runtime_android_ui_e2e"
$artifactDir = Join-Path $RootDir "tmp_android_ui_e2e"
$settingsXml = Join-Path $artifactDir "relay_settings.xml"
$windowDump = Join-Path $artifactDir "window_dump.xml"
$defaultApkPath = Join-Path $RootDir "Android\app\build\outputs\apk\debug\app-debug.apk"
$healthUrl = "http://127.0.0.1:$RelayPort/api/health"
$relayBaseUrl = "http://10.0.2.2:$RelayPort"

if (-not (Test-Path $PythonExe)) {
    throw "Python executable not found: $PythonExe"
}
if (-not (Test-Path $AdbExe)) {
    throw "adb executable not found: $AdbExe"
}
if ([string]::IsNullOrWhiteSpace($ApkPath)) {
    $ApkPath = $defaultApkPath
}

if (-not (Test-Path $ApkPath)) {
    throw "APK not found: $ApkPath"
}

New-Item -ItemType Directory -Force -Path $androidStateDir | Out-Null
Stop-StaleRelayOnPort -Port $RelayPort
if (Test-Path $artifactDir) {
    Remove-Item $artifactDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $artifactDir | Out-Null

if (Test-Path $runtimeDir) {
    try {
        Remove-Item $runtimeDir -Recurse -Force
    } catch {
        Start-Sleep -Milliseconds 500
        Remove-Item $runtimeDir -Recurse -Force
    }
}
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

$env:ANDROID_SDK_HOME = $androidStateDir
$env:ANDROID_USER_HOME = $androidStateDir
$env:WORKSPACE_DIR = $runtimeDir
$env:HOST = "0.0.0.0"
$env:PORT = "$RelayPort"
$env:EXECUTOR_KIND = "mock"
$env:DEFAULT_MODE = "link_only_v1"
$env:WEB_UI_LOCAL_ONLY = "false"
$env:AUTH_TOKEN = ""

$relayPsi = New-Object System.Diagnostics.ProcessStartInfo
$relayPsi.FileName = $PythonExe
$relayPsi.Arguments = "run.py start --host 0.0.0.0 --port $RelayPort"
$relayPsi.WorkingDirectory = $relayDir
$relayPsi.UseShellExecute = $false
$relayPsi.RedirectStandardOutput = $true
$relayPsi.RedirectStandardError = $true

foreach ($key in @(
    "WORKSPACE_DIR",
    "HOST",
    "PORT",
    "EXECUTOR_KIND",
    "DEFAULT_MODE",
    "WEB_UI_LOCAL_ONLY",
    "AUTH_TOKEN"
)) {
    $relayPsi.Environment[$key] = [Environment]::GetEnvironmentVariable($key)
}

$relayProc = [System.Diagnostics.Process]::Start($relayPsi)

try {
    Wait-ForRelayHealth -HealthUrl $healthUrl -RelayProcess $relayProc

    $deviceOutput = ((& $AdbExe devices) -join "`n")
    if ($deviceOutput -notmatch "emulator-\d+\s+device") {
        throw "No emulator device connected.`n$deviceOutput"
    }

    & $AdbExe uninstall com.peter.paperharvestshare | Out-Null
    & $AdbExe install -r $ApkPath | Out-Null
    & $AdbExe shell pm clear com.peter.paperharvestshare | Out-Null

    @"
<?xml version='1.0' encoding='utf-8' standalone='yes' ?>
<map>
    <string name="relay_base_url">$relayBaseUrl</string>
    <string name="relay_auth_token"></string>
    <string name="connection_type">emulator</string>
    <string name="selected_mode_id">link_only_v1</string>
    <string name="selected_mode_label">Link Only</string>
    <string name="selected_mode_description">Process the shared link without article-specific extraction.</string>
</map>
"@ | Set-Content -Encoding UTF8 $settingsXml

    & $AdbExe push $settingsXml /data/local/tmp/relay_settings.xml | Out-Null
    $runAsMkdir = ((& $AdbExe shell run-as com.peter.paperharvestshare mkdir -p shared_prefs 2>&1) -join "`n")
    if ($runAsMkdir -match "not debuggable" -or $runAsMkdir -match "unknown package") {
        throw "The installed APK does not support run-as settings injection. Use a debuggable APK build for this automation script."
    }
    $runAsCopy = ((& $AdbExe shell run-as com.peter.paperharvestshare cp /data/local/tmp/relay_settings.xml shared_prefs/relay_settings.xml 2>&1) -join "`n")
    if ($runAsCopy -match "not debuggable" -or $runAsCopy -match "unknown package") {
        throw "The installed APK does not support run-as settings injection. Use a debuggable APK build for this automation script."
    }

    & $AdbExe shell am force-stop com.peter.paperharvestshare | Out-Null
    & $AdbExe shell am start -a android.intent.action.SEND -t text/plain -e android.intent.extra.TEXT $Url -n com.peter.paperharvestshare/.ui.ShareReceiverActivity | Out-Null
    Start-Sleep -Seconds 2

    & $AdbExe shell uiautomator dump /sdcard/window_dump.xml | Out-Null
    & $AdbExe pull /sdcard/window_dump.xml $windowDump | Out-Null
    [xml]$uiXml = Get-Content $windowDump
    $submitNode = $uiXml.SelectSingleNode("//node[@resource-id='com.peter.paperharvestshare:id/submitButton']")
    if (-not $submitNode) {
        throw "submitButton not found in UI dump"
    }
    if ($submitNode.enabled -ne "true") {
        throw "submitButton is disabled"
    }

    $submitCenter = Get-BoundsCenter -Bounds $submitNode.bounds
    & $AdbExe shell input tap $submitCenter[0] $submitCenter[1] | Out-Null

    $matchedTask = $null
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Milliseconds 500
        $matchedTask = Get-LatestRelayTask -RelayDirPath $relayDir -PythonPath $PythonExe -ExpectedUrl $Url
        if ($matchedTask -and $matchedTask.status -eq "completed") {
            break
        }
    }

    if (-not $matchedTask) {
        throw "Relay never received the submitted URL: $Url"
    }
    if ($matchedTask.status -ne "completed") {
        throw "Relay task did not complete. status=$($matchedTask.status)"
    }

    $statusVisible = Wait-ForStatusActivity -AdbExePath $AdbExe

    [pscustomobject]@{
        relayTaskId = $matchedTask.taskId
        relayStatus = $matchedTask.status
        statusActivityVisible = $statusVisible
        submittedUrl = $Url
        runtimeDir = $runtimeDir
        artifactDir = $artifactDir
    } | ConvertTo-Json -Depth 5
} finally {
    if ($relayProc -and -not $relayProc.HasExited) {
        $relayProc.Kill()
        $relayProc.WaitForExit()
    }
}
