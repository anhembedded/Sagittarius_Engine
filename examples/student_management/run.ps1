#Requires -Version 5.1
<#
.SYNOPSIS
    Runs the Student Management sample app (engine reference implementation).

.DESCRIPTION
    Two modes:

      (default)   Launches the QML GUI (gui.py) — a real window backed by
                  pyside_mvc, booted as a genuine IExtension. See
                  docs/ui_extension_lifecycle.md for why QApplication must
                  exist before App.boot() runs.

      -Cli        Runs the argparse CLI (main.py) instead. Requires a
                  subcommand — enroll/update/remove/get/list/search/report —
                  forwarded via the trailing arguments. See main.py's own
                  --help for each subcommand's arguments.

    Resolves the interpreter in this order: an explicit -Python path, this
    repo's .venv, then whatever `python` is on PATH. Runs from the working
    tree (PYTHONPATH set to the repo root), not an installed copy, so a
    change to the engine or the sample is visible without reinstalling.

.PARAMETER Cli
    Run the CLI (main.py) instead of the GUI.

.PARAMETER Python
    Explicit interpreter to use, bypassing .venv discovery.

.PARAMETER Args
    Passed through verbatim to main.py when -Cli is set. Ignored otherwise.

.EXAMPLE
    .\examples\student_management\run.ps1
    Opens the roster GUI.

.EXAMPLE
    .\examples\student_management\run.ps1 -Cli list
    Lists all enrolled students via the CLI.

.EXAMPLE
    .\examples\student_management\run.ps1 -Cli enroll "Alice Nguyen" alice@example.com CS 3.7
    Enrolls a student via the CLI.
#>
[CmdletBinding()]
param(
    [switch]$Cli,
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
$entryScript = if ($Cli) { Join-Path $scriptDir "main.py" } else { Join-Path $scriptDir "gui.py" }

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
    if (-not $CliArgs -or $CliArgs.Count -eq 0) {
        throw "-Cli requires a subcommand (enroll/update/remove/get/list/search/report). " +
              "Example: .\run.ps1 -Cli list"
    }
    & $pythonExe $entryScript @CliArgs
}
else {
    if ($CliArgs -and $CliArgs.Count -gt 0) {
        Write-Warning "Ignoring extra arguments in GUI mode: $CliArgs. Pass -Cli to use them."
    }
    Write-Host "Opening the Student Management roster GUI. Close the window to exit."
    & $pythonExe $entryScript
}

if ($LASTEXITCODE -ne 0) {
    throw "$(Split-Path -Leaf $entryScript) exited with code $LASTEXITCODE — see the output above."
}
