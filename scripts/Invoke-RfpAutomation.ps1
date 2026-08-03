<#
.SYNOPSIS
    Triggers an RFP automation job over the local HTTP API. Designed to be run by Windows Task Scheduler.

.DESCRIPTION
    Fires the automation endpoint on the locally-running rfp-api service, then polls
    /automation/status until the job's run flag clears, so Task Scheduler's "Last Run
    Result" reflects the run finishing rather than just the request being accepted.

    Exit codes:
      0  - job ran to completion (or was already running; see -SkipIfRunning)
      1  - could not reach the API
      2  - job was already running and -SkipIfRunning was not set
      3  - job started but did not finish within -TimeoutMinutes

    NOTE: a 0 exit means the job *finished*, not that it succeeded. The run flag
    clears in a `finally`, so a crashed run also reports 0. Failure bundles land in
    backend\LOGS\ (failure_logger falls back to <cwd>\LOGS because no FAILURE_LOGS_DIR
    row exists in System Settings), and an alert goes to EMAIL_TO_AUTOMATION_FAILURE.

    This file is deliberately ASCII-only: Windows PowerShell 5.1 reads a BOM-less
    script as ANSI, which corrupts multi-byte characters and breaks parsing.

.EXAMPLE
    .\Invoke-RfpAutomation.ps1 -Job download
    .\Invoke-RfpAutomation.ps1 -Job sync -TimeoutMinutes 45
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('download', 'sync', 'sync-sp-dv', 'reminder')]
    [string]$Job,

    [string]$BaseUrl = 'http://127.0.0.1:8000',

    # Wait for the API to come up - covers the case where the server reboots and the
    # task fires before the rfp-api service has finished starting.
    [int]$StartupWaitSeconds = 120,

    [int]$TimeoutMinutes = 60,

    [int]$PollSeconds = 15,

    # Treat "already running" as success instead of an error.
    [switch]$SkipIfRunning,

    [string]$LogDir = 'C:\Bahra-Automation-RFP-System\backend\LOGS\scheduler'
)

$ErrorActionPreference = 'Stop'

# Endpoint + the /automation/status flag that reports this job as running.
$JobMap = @{
    'download'   = @{ Path = '/api/download-rfps-automation';  Flag = 'download_running';   Async = $true  }
    'sync'       = @{ Path = '/api/sync_portal_data';          Flag = 'sync_running';       Async = $true  }
    'sync-sp-dv' = @{ Path = '/api/sync-sharepoint-dataverse'; Flag = 'sync_sp_dv_running'; Async = $true  }
    'reminder'   = @{ Path = '/api/rfp-reminder';              Flag = $null;                Async = $false }
}

$spec = $JobMap[$Job]

if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}
$logFile = Join-Path $LogDir ("scheduler-{0}.log" -f (Get-Date -Format 'yyyy-MM'))

function Write-Log {
    param([string]$Message, [string]$Level = 'INFO')
    $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $line = "$stamp [$Level] [$Job] $Message"
    Write-Output $line
    Add-Content -Path $logFile -Value $line -Encoding utf8
}

function Get-AutomationStatus {
    try {
        return Invoke-RestMethod -Uri "$BaseUrl/api/automation/status" -Method Get -TimeoutSec 30
    } catch {
        return $null
    }
}

Write-Log "=== Starting '$Job' ==="

# --- 1. Wait for the API to be reachable ---------------------------------------
$deadline = (Get-Date).AddSeconds($StartupWaitSeconds)
$status = Get-AutomationStatus
while ($null -eq $status -and (Get-Date) -lt $deadline) {
    Write-Log "API not reachable at $BaseUrl - retrying in 10s" 'WARN'
    Start-Sleep -Seconds 10
    $status = Get-AutomationStatus
}
if ($null -eq $status) {
    Write-Log "API unreachable after $StartupWaitSeconds sec. Is the 'rfp-api' service running?" 'ERROR'
    exit 1
}

# --- 2. Fire the trigger --------------------------------------------------------
$httpStatus = $null
try {
    $resp = Invoke-WebRequest -Uri "$BaseUrl$($spec.Path)" -Method Get -TimeoutSec 900 -UseBasicParsing
    $httpStatus = [int]$resp.StatusCode
} catch [System.Net.WebException] {
    if ($_.Exception.Response) {
        $httpStatus = [int]$_.Exception.Response.StatusCode
    } else {
        Write-Log "Request failed: $($_.Exception.Message)" 'ERROR'
        exit 1
    }
} catch {
    Write-Log "Request failed: $($_.Exception.Message)" 'ERROR'
    exit 1
}

if ($httpStatus -eq 409) {
    # _RUN_STATE says this job is already in flight - a UI-triggered run, or the
    # previous scheduled run has overrun its window.
    if ($SkipIfRunning) {
        Write-Log "Already running - skipping this occurrence." 'WARN'
        exit 0
    }
    Write-Log "Already running - previous run may have overrun its schedule." 'ERROR'
    exit 2
}

if ($httpStatus -ne 202 -and $httpStatus -ne 200) {
    Write-Log "Unexpected HTTP $httpStatus from $($spec.Path)" 'ERROR'
    exit 1
}

# /rfp-reminder blocks and returns its result, so there is nothing to poll.
if (-not $spec.Async) {
    Write-Log "Completed (HTTP $httpStatus)."
    exit 0
}

Write-Log "Accepted (HTTP $httpStatus) - polling until the run flag clears."

# --- 3. Poll until the run flag clears ------------------------------------------
$started = Get-Date
$timeout = $started.AddMinutes($TimeoutMinutes)

# The trigger returns before the worker thread flips the flag; give it a moment so
# we don't read a stale "not running" and declare victory instantly.
Start-Sleep -Seconds 5

while ((Get-Date) -lt $timeout) {
    $status = Get-AutomationStatus

    if ($null -eq $status) {
        Write-Log "Lost contact with the API while polling - the service may have crashed mid-run." 'WARN'
        Start-Sleep -Seconds $PollSeconds
        continue
    }

    if (-not $status.($spec.Flag)) {
        $mins = [math]::Round(((Get-Date) - $started).TotalMinutes, 1)
        # "Finished" != "succeeded": _finish_operation clears the flag in a finally,
        # so a crashed run looks identical to a clean one from out here.
        Write-Log "Finished after $mins min (finished != succeeded - check backend\LOGS\ for a new failure folder)."
        exit 0
    }

    Write-Log "Running... $($status.progress)%"
    Start-Sleep -Seconds $PollSeconds
}

Write-Log "Did not finish within $TimeoutMinutes min - still running server-side, not killed." 'ERROR'
exit 3
