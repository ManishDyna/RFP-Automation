<#
.SYNOPSIS
    Registers the RFP automation scheduled tasks on the production server.

.DESCRIPTION
    Creates one Windows Scheduled Task per automation job, all calling
    Invoke-RfpAutomation.ps1 against the local rfp-api service on 127.0.0.1:8000.

    Replaces the 'Bahra-E-binding-cron-job' Power Automate flow, which fires every
    6 hours at a devtunnel URL (https://0vv8220f-8000.inc1.devtunnels.ms) that no
    longer serves. TURN THAT FLOW OFF before enabling these tasks.

    Run this from an ELEVATED PowerShell session on the server (192.168.111.192).
    Re-running it replaces the existing tasks, so it is safe to re-run after edits.

.PARAMETER UseSystem
    Run as SYSTEM. Fine here because the task only makes a localhost HTTP call and
    writes a log file. It does NOT run Playwright; the rfp-api service does that
    under its own identity.

.PARAMETER ServiceAccount
    Alternative to -UseSystem: a domain account, e.g. 'BAHRA\svc-rfp'. Needs
    "Log on as a batch job" rights. You will be prompted for the password.

.EXAMPLE
    .\Register-RfpSchedules.ps1 -UseSystem
    .\Register-RfpSchedules.ps1 -UseSystem -WhatIf     # preview without registering
#>
[CmdletBinding(DefaultParameterSetName = 'System', SupportsShouldProcess = $true)]
param(
    [Parameter(ParameterSetName = 'Account', Mandatory = $true)]
    [string]$ServiceAccount,

    [Parameter(ParameterSetName = 'System')]
    [switch]$UseSystem,

    [string]$ScriptPath = 'C:\Bahra-Automation-RFP-System\scripts\Invoke-RfpAutomation.ps1',

    [string]$TaskFolder = '\Bahra-RFP'
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path $ScriptPath)) {
    throw "Runner not found at $ScriptPath. Deploy the scripts\ folder to the server first."
}

# ---------------------------------------------------------------------------
# Schedule definitions. Times are SERVER-LOCAL.
#
# The server runs Arab Standard Time (Riyadh). The old Power Automate flow was
# set to India Standard Time, which is UTC+5:30 vs Riyadh's UTC+3 - so its
# "12:00" fired at 09:30 Riyadh. These times are Riyadh times; they are NOT a
# literal carry-over of the old flow's clock.
#
# SCOPE: download + reminder + sync. The reminder job was originally left on
# Power Automate, but that flow fires at the same dead devtunnel as the other
# two, so reminders were not sending at all. It is now registered here.
#
# TURN ALL THREE FLOWS OFF before enabling these tasks, or both fire:
#   Bahra-E-binding-cron-job            -> /download-rfps-automation
#   Bahra-sync-open-rfp-status-cron-job -> /api/sync_portal_data
#   Bahra-RFP-Reminder-Emails-Cron-job  -> /api/rfp-reminder
# ---------------------------------------------------------------------------
$Schedules = @(
    @{
        Name        = 'RFP-Download-OpenRFPs'
        Job         = 'download'
        Description = 'Discovers and downloads new RFPs from all supplier portals. Replaces the Bahra-E-binding-cron-job flow.'
        # Every 6 hours, matching the old flow's cadence.
        # Four explicit daily triggers rather than -Once -RepetitionInterval: a
        # repetition trigger with no -RepetitionDuration yields an empty Duration
        # with StopAtDurationEnd=True, which can stop repeating after one cycle.
        Triggers    = @(
            (New-ScheduledTaskTrigger -Daily -At '00:00')
            (New-ScheduledTaskTrigger -Daily -At '06:00')
            (New-ScheduledTaskTrigger -Daily -At '12:00')
            (New-ScheduledTaskTrigger -Daily -At '18:00')
        )
        Timeout     = 90
    },
    @{
        Name        = 'RFP-Sync-Portal'
        Job         = 'sync'
        Description = 'Syncs RFP status/deadlines from the portals back into Dataverse.'
        # Offset from the download runs so two Playwright sessions do not hit the
        # same portal at once. download and sync use separate _RUN_STATE flags,
        # so the 409 guard would NOT stop them colliding.
        Triggers    = @(
            (New-ScheduledTaskTrigger -Daily -At '03:00')
            (New-ScheduledTaskTrigger -Daily -At '09:00')
            (New-ScheduledTaskTrigger -Daily -At '15:00')
            (New-ScheduledTaskTrigger -Daily -At '21:00')
        )
        Timeout     = 60
    },
    @{
        Name        = 'RFP-Reminder-Emails'
        Job         = 'reminder'
        Description = 'Sends 3-day / 1-day deadline reminder emails to bidders. Replaces the Bahra-RFP-Reminder-Emails-Cron-job flow.'
        # Twice daily during working hours. The job is window-based (deadline
        # <=72h / <=24h) and idempotent per stage via the Reminder_3Day_Sent /
        # Reminder_1Day_Sent flags, so a second run cannot double-send - it only
        # halves how long an RFP sits in a window before anyone is chased.
        # Offset from download/sync so it is not queued behind a Playwright run.
        Triggers    = @(
            (New-ScheduledTaskTrigger -Daily -At '08:00')
            (New-ScheduledTaskTrigger -Daily -At '16:00')
        )
        # /api/rfp-reminder is synchronous, so this only sizes ExecutionTimeLimit;
        # the runner's own cap is Invoke-WebRequest -TimeoutSec 900.
        Timeout     = 30
    }
)

$registered = @()
$failed = @()

if ($PSCmdlet.ParameterSetName -eq 'System') {
    $principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
    $cred = $null
} else {
    $cred = Get-Credential -UserName $ServiceAccount -Message "Password for $ServiceAccount"
    $principal = $null
}

foreach ($s in $Schedules) {
    $argList = @(
        '-NoProfile'
        '-NonInteractive'
        '-ExecutionPolicy Bypass'
        "-File `"$ScriptPath`""
        "-Job $($s.Job)"
        "-TimeoutMinutes $($s.Timeout)"
        '-SkipIfRunning'
    ) -join ' '

    $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $argList

    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -MultipleInstances IgnoreNew `
        -ExecutionTimeLimit (New-TimeSpan -Minutes ($s.Timeout + 15)) `
        -RestartCount 2 `
        -RestartInterval (New-TimeSpan -Minutes 10)

    $taskPath = "$TaskFolder\"

    if (-not $PSCmdlet.ShouldProcess("$taskPath$($s.Name)", "Register scheduled task -> $($s.Job)")) {
        continue
    }

    # Remove first so re-running this script is idempotent.
    $existing = Get-ScheduledTask -TaskName $s.Name -TaskPath $taskPath -ErrorAction SilentlyContinue
    if ($existing) {
        Unregister-ScheduledTask -TaskName $s.Name -TaskPath $taskPath -Confirm:$false
        Write-Host "Removed existing task: $($s.Name)"
    }

    $params = @{
        TaskName    = $s.Name
        TaskPath    = $taskPath
        Action      = $action
        Trigger     = $s.Triggers
        Settings    = $settings
        Description = $s.Description
    }

    if ($principal) {
        $params['Principal'] = $principal
    } else {
        $params['User']     = $cred.UserName
        $params['Password'] = $cred.GetNetworkCredential().Password
        $params['RunLevel'] = 'Highest'
    }

    # -ErrorAction Stop is required: Register-ScheduledTask is a CIM cmdlet and its
    # errors do NOT reliably honour $ErrorActionPreference, so without this the
    # script sails past an "Access is denied" and reports success it did not achieve.
    try {
        Register-ScheduledTask @params -ErrorAction Stop | Out-Null
    } catch {
        Write-Host "FAILED to register $($s.Name): $($_.Exception.Message)" -ForegroundColor Red
        $failed += $s.Name
        continue
    }

    # Trust nothing: confirm the task is actually there before claiming success.
    $check = Get-ScheduledTask -TaskName $s.Name -TaskPath $taskPath -ErrorAction SilentlyContinue
    if (-not $check) {
        Write-Host "FAILED: $($s.Name) reported no error but does not exist." -ForegroundColor Red
        $failed += $s.Name
        continue
    }

    Write-Host "Registered: $taskPath$($s.Name)  ->  $($s.Job)  [$($check.Triggers.Count) trigger(s)]" -ForegroundColor Green
    $registered += $s.Name
}

if ($failed.Count -gt 0) {
    Write-Host ""
    Write-Host "$($failed.Count) task(s) FAILED to register: $($failed -join ', ')" -ForegroundColor Red
    Write-Host "Are you running this in an ELEVATED PowerShell session?" -ForegroundColor Red
    exit 1
}

if ($registered.Count -eq 0) {
    Write-Host "Nothing was registered." -ForegroundColor Yellow
    exit 0
}

Write-Host ""
Write-Host "All $($registered.Count) task(s) registered and verified." -ForegroundColor Green
Write-Host "Verify with:" -ForegroundColor Cyan
Write-Host "  Get-ScheduledTask -TaskPath '$TaskFolder\' | Format-Table TaskName, State"
Write-Host "  Get-ScheduledTaskInfo -TaskPath '$TaskFolder\' -TaskName 'RFP-Sync-Portal'"
Write-Host ""
Write-Host "Test a safe job first (RFP-Reminder sends real bidder email):" -ForegroundColor Yellow
Write-Host "  Start-ScheduledTask -TaskPath '$TaskFolder\' -TaskName 'RFP-Sync-Portal'"
