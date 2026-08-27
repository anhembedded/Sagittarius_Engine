#Requires -Version 5.1
<#
.SYNOPSIS
    Runs the Student Management sample app (engine reference implementation).

.DESCRIPTION
    Three modes:

      (default)   Launches the GUI (gui.py) — a real window backed by
                  pyside_mvc, booted as a genuine IExtension. See
                  docs/ui_extension_lifecycle.md for why QApplication must
                  exist before App.boot() runs. QML by default; pass
                  -QtWidget for the QWidget rendering backend instead
                  (TASK-037) — same Presenter/ViewModel either way, picked
                  via gui.py's own --qtwidget flag.

      -Cli        Runs the argparse CLI (main.py) instead. Requires a
                  subcommand — enroll/update/remove/get/list/search/report —
                  forwarded via the trailing arguments. See main.py's own
                  --help for each subcommand's arguments.

      -Console    Runs the app headlessly (console.py) with the runtime
                  state console attached (EPIC-007C/D) instead of the GUI or
                  CLI. Blocks until Ctrl+C. Read it from another terminal
                  with `sagittarius-trace snapshot`. -DemoFaults additionally
                  attaches DemoFaultsExtension, seeding one instance of
                  everything the engine's diagnostics claim to detect.

    Resolves the interpreter in this order: an explicit -Python path, this
    repo's .venv, then whatever `python` is on PATH. Runs from the working
    tree (PYTHONPATH set to the repo root), not an installed copy, so a
    change to the engine or the sample is visible without reinstalling.

.PARAMETER Cli
    Run the CLI (main.py) instead of the GUI.

.PARAMETER QtWidget
    GUI mode only: render with the QWidget backend (WidgetRosterView)
    instead of the default QML one. Ignored (with a warning) under -Cli or
    -Console, neither of which has a rendering backend to pick.

.PARAMETER Console
    Run headlessly with the runtime state console attached (console.py)
    instead of the GUI or CLI.

.PARAMETER ConsolePort
    -Console only: the port the console listens on. Default 8781.

.PARAMETER ConsoleToken
    -Console only: require this token on `?token=` to connect. Omitted by
    default — matches `StateConsoleExtension`'s own default of no auth on
    loopback.

.PARAMETER DemoFaults
    -Console only: also attach `DemoFaultsExtension` — EPIC-007D §2.2.

.PARAMETER Python
    Explicit interpreter to use, bypassing .venv discovery.

.PARAMETER Args
    Passed through verbatim to main.py when -Cli is set. Ignored otherwise.

.EXAMPLE
    .\examples\student_management\run.ps1
    Opens the roster GUI (QML backend).

.EXAMPLE
    .\examples\student_management\run.ps1 -QtWidget
    Opens the roster GUI with the QWidget backend instead.

.EXAMPLE
    .\examples\student_management\run.ps1 -Cli list
    Lists all enrolled students via the CLI.

.EXAMPLE
    .\examples\student_management\run.ps1 -Cli enroll "Alice Nguyen" alice@example.com CS 3.7
    Enrolls a student via the CLI.

.EXAMPLE
    .\examples\student_management\run.ps1 -Console
    Boots the app headlessly with the runtime state console attached on 8781.

.EXAMPLE
    .\examples\student_management\run.ps1 -Console -DemoFaults
    Same, with one instance of every diagnosed fault seeded for the demo.

.EXAMPLE
    .\examples\student_management\run.ps1 -Console -ConsolePort 9001 -ConsoleToken dev-only
    Non-default port, with token auth required to connect.
#>
[CmdletBinding()]
param(
    [switch]$Cli,
    [switch]$QtWidget,
    [switch]$Console,
    [int]$ConsolePort = 8781,
    [string]$ConsoleToken,
    [switch]$DemoFaults,
    [string]$Python,
    # Explicit Position, under CmdletBinding, so this is the ONLY positional
    # parameter — without it, $Python (declared with no Position of its own)
    # silently steals the first trailing token ("-Cli list" bound "list" to
    # $Python, leaving $CliArgs empty). Verified both orderings work with
    # this in place: `-Cli enroll Alice` and `-Python <path> -Cli list`.
    [Parameter(Position = 0, ValueFromRemainingArguments = $true)]
    [string[]]$CliArgs
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$repoRoot = Split-Path -Parent (Split-Path -Parent $scriptDir)
$entryScript = if ($Cli) { Join-Path $scriptDir "main.py" }
elseif ($Console) { Join-Path $scriptDir "console.py" }
else { Join-Path $scriptDir "gui.py" }

if (-not (Test-Path $entryScript)) {
    throw "Cannot find $entryScript — run this from a full checkout of Sagittarius_Engine."
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

# main.py/gui.py import via `from examples.student_management...` — absolute
# imports rooted at the repo root, not the sample's own directory.
$env:PYTHONPATH = $repoRoot

if ($Cli) {
    if ($QtWidget) {
        Write-Warning "-QtWidget has no effect under -Cli (no rendering backend to pick); ignoring."
    }
    if ($Console -or $ConsoleToken -or $DemoFaults) {
        Write-Warning "-Console/-ConsoleToken/-DemoFaults have no effect under -Cli; ignoring."
    }
    if (-not $CliArgs -or $CliArgs.Count -eq 0) {
        throw "-Cli requires a subcommand (enroll/update/remove/get/list/search/report). " +
              "Example: .\run.ps1 -Cli list"
    }
    & $pythonExe $entryScript @CliArgs
}
elseif ($Console) {
    if ($QtWidget) {
        Write-Warning "-QtWidget has no effect under -Console (no rendering backend to pick); ignoring."
    }
    if ($CliArgs -and $CliArgs.Count -gt 0) {
        Write-Warning "Ignoring extra arguments in -Console mode: $CliArgs."
    }
    $consoleArgs = @("--port", $ConsolePort)
    if ($ConsoleToken) {
        $consoleArgs += @("--token", $ConsoleToken)
    }
    if ($DemoFaults) {
        $consoleArgs += "--demo-faults"
    }
    & $pythonExe $entryScript @consoleArgs
}
else {
    if ($CliArgs -and $CliArgs.Count -gt 0) {
        Write-Warning "Ignoring extra arguments in GUI mode: $CliArgs. Pass -Cli to use them."
    }
    if ($ConsoleToken -or $DemoFaults) {
        Write-Warning "-ConsoleToken/-DemoFaults have no effect without -Console; ignoring."
    }
    $backend = if ($QtWidget) { "QWidget" } else { "QML" }
    Write-Host "Opening the Student Management roster GUI ($backend backend). Close the window to exit."
    if ($QtWidget) {
        & $pythonExe $entryScript --qtwidget
    }
    else {
        & $pythonExe $entryScript
    }
}

if ($LASTEXITCODE -ne 0) {
    throw "$(Split-Path -Leaf $entryScript) exited with code $LASTEXITCODE — see the output above."
}
