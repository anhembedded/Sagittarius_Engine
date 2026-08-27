#Requires -Version 5.1
<#
.SYNOPSIS
    Opens the runtime state console (EPIC-007C/E) against a running app.

.DESCRIPTION
    Three modes:

      -Attach <uri>   Opens the console against an already-running app. The
                      everyday mode. Pass a token in the URI's query string
                      the same way sagittarius-trace does
                      (ws://host:port?token=...).

      -Demo           Starts examples/student_management/run.ps1
                      -Console -DemoFaults as a child process, waits for its
                      port to accept connections, opens the console against
                      it, and stops the child when the console window
                      closes -- including if the console itself throws. One
                      command, one keystroke.

      -Snapshot       No window: prints one text snapshot via
                      `sagittarius-trace snapshot` and exits. Requires
                      -Attach. The CI/SSH path -- EPIC-007C's own renderer,
                      not reimplemented here.

    Resolves the interpreter in this order: an explicit -Python path, this
    repo's .venv, then whatever `python` is on PATH. Runs from the working
    tree (PYTHONPATH set to the repo root), not an installed copy.

.PARAMETER Attach
    ws://host:port[?token=...] of a running TraceServer. Required with
    -Snapshot; ignored (with a warning) under -Demo, which builds its own.

.PARAMETER Demo
    Start examples/student_management with -Console -DemoFaults, attach to
    it, and stop it when the console closes.

.PARAMETER Snapshot
    Print one text snapshot instead of opening a window. Requires -Attach.

.PARAMETER Python
    Explicit interpreter to use, bypassing .venv discovery.

.EXAMPLE
    .\scripts\run-console.ps1 -Demo
    The whole demo — sample app with seeded faults, plus the console — one command.

.EXAMPLE
    .\scripts\run-console.ps1 -Attach ws://127.0.0.1:8781
    Attaches to an app someone else started.

.EXAMPLE
    .\scripts\run-console.ps1 -Attach "ws://127.0.0.1:9001?token=dev-only"
    With a token, as a consumer would.

.EXAMPLE
    .\scripts\run-console.ps1 -Snapshot -Attach ws://127.0.0.1:8781
    No display server: one text snapshot, then exit.
#>
[CmdletBinding()]
param(
    [string]$Attach,
    [switch]$Demo,
    [switch]$Snapshot,
    [string]$Python
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$repoRoot = Split-Path -Parent $scriptDir

if (-not $Demo -and -not $Attach) {
    throw "Pass -Attach <uri> or -Demo. Example: .\scripts\run-console.ps1 -Demo"
}
if ($Snapshot -and -not $Attach) {
    throw "-Snapshot requires -Attach <uri>."
}
if ($Demo -and $Attach) {
    Write-Warning "-Attach has no effect with -Demo (the demo builds its own URI); ignoring."
}

# Interpreter discovery. Join-Path is used with two arguments only: the
# three-plus-argument form is PowerShell 7+ and silently breaks the 5.1
# compatibility this script declares above.
if ($Python) {
    $pythonExe = $Python
}
else {
    $venvWindows = Join-Path (Join-Path $repoRoot ".venv") "Scripts"
    $venvWindows = Join-Path $venvWindows "python.exe"
    $venvPosix = Join-Path (Join-Path $repoRoot ".venv") "bin"
    $venvPosix = Join-Path $venvPosix "python"

    if (Test-Path $venvWindows) {
        $pythonExe = $venvWindows
    }
    elseif (Test-Path $venvPosix) {
        $pythonExe = $venvPosix
    }
    else {
        $pythonExe = "python"
        Write-Warning "No .venv found under $repoRoot — falling back to 'python' on PATH."
    }
}

$env:PYTHONPATH = $repoRoot

function Wait-ForPort {
    <#
    Polls a TCP connect attempt until it succeeds or $TimeoutSeconds elapses
    -- never a fixed sleep, which passes on a fast machine and fails on a
    slow one (EPIC-007E section 5's own stated reasoning).
    #>
    param(
        [string]$TargetHost,
        [int]$TargetPort,
        [int]$TimeoutSeconds = 15
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $client = New-Object System.Net.Sockets.TcpClient
            $client.Connect($TargetHost, $TargetPort)
            $client.Close()
            return
        }
        catch {
            Start-Sleep -Milliseconds 100
        }
    }
    throw "Timed out after ${TimeoutSeconds}s waiting for port $TargetPort to accept connections."
}

$demoProcess = $null
try {
    if ($Demo) {
        $demoPort = 8781
        $demoScript = Join-Path (Join-Path $repoRoot "examples") "student_management"
        $demoScript = Join-Path $demoScript "console.py"
        if (-not (Test-Path $demoScript)) {
            throw "Cannot find $demoScript — run this from a full checkout of Sagittarius_Engine."
        }
        Write-Host "Starting examples/student_management with seeded faults on port $demoPort..."
        $demoProcess = Start-Process -FilePath $pythonExe `
            -ArgumentList @($demoScript, "--port", $demoPort, "--demo-faults") `
            -PassThru -NoNewWindow

        Wait-ForPort -TargetHost "127.0.0.1" -TargetPort $demoPort
        $Attach = "ws://127.0.0.1:$demoPort"
    }

    $consoleScript = Join-Path (Join-Path $repoRoot "tools") "state_console"
    $consoleScript = Join-Path $consoleScript "main.py"
    if (-not (Test-Path $consoleScript)) {
        throw "Cannot find $consoleScript — run this from a full checkout of Sagittarius_Engine."
    }

    if ($Snapshot) {
        Write-Host "Requesting one snapshot from $Attach..."
        & $pythonExe -m sagittarius_engine.extensions.audit.cli snapshot $Attach
    }
    else {
        Write-Host "Opening the runtime state console against $Attach. Close the window to exit."
        & $pythonExe $consoleScript $Attach
    }

    if ($LASTEXITCODE -ne 0) {
        throw "$(Split-Path -Leaf $consoleScript) exited with code $LASTEXITCODE — see the output above."
    }
}
finally {
    if ($demoProcess -and -not $demoProcess.HasExited) {
        Write-Host "Stopping the demo app (pid $($demoProcess.Id))..."
        Stop-Process -Id $demoProcess.Id -Force
    }
}
