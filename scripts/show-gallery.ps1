#Requires -Version 5.1
<#
.SYNOPSIS
    Runs the Sagittarius UI Engine Widget Kit gallery.

.DESCRIPTION
    Two modes, both driven by scripts/render_gallery_snapshot.py:

      (default)   Opens a real, interactive window. Hover, press, focus and
                  the AppModal open/close cycle only exist here — a PNG
                  cannot show them, so this is the mode that actually
                  verifies the kit rather than just proving it parses.

      -Snapshot   Renders offscreen and writes a PNG. For CI, for attaching
                  to a review, and for machines with no display.

    Resolves the interpreter in this order: an explicit -Python path, this
    repo's .venv, then whatever `python` is on PATH.

.PARAMETER Snapshot
    Render headlessly to a PNG instead of opening a window.

.PARAMETER Output
    PNG path for -Snapshot. Defaults to gallery_snapshot.png in the repo root.

.PARAMETER Python
    Explicit interpreter to use, bypassing .venv discovery. Useful when the
    only environment with PySide6 installed lives elsewhere (e.g. a
    consuming app's venv).

.EXAMPLE
    .\scripts\show-gallery.ps1
    Opens the interactive gallery window.

.EXAMPLE
    .\scripts\show-gallery.ps1 -Snapshot
    Writes gallery_snapshot.png.

.EXAMPLE
    .\scripts\show-gallery.ps1 -Snapshot -Output docs/assets/kit.png
#>
[CmdletBinding()]
param(
    [switch]$Snapshot,
    [string]$Output,
    [string]$Python
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$repoRoot = Split-Path -Parent $scriptDir
$renderScript = Join-Path $scriptDir "render_gallery_snapshot.py"

if (-not (Test-Path $renderScript)) {
    throw "Cannot find $renderScript — run this from a full checkout of Sagittarius_Engine."
}

# Interpreter discovery. Join-Path is used with two arguments only: the
# three-plus-argument form is PowerShell 7+ and silently breaks the 5.1
# compatibility this script declares above (the same defect BUG-029 hit in
# the consuming app's build-native-chart.ps1).
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

# The gallery imports sagittarius_engine from the working tree, not from an
# installed copy, so a change to the kit is visible without reinstalling.
$env:PYTHONPATH = $repoRoot

if ($Snapshot) {
    if (-not $Output) {
        $Output = Join-Path $repoRoot "gallery_snapshot.png"
    }
    # Offscreen is required, not merely convenient: grabFramebuffer() on a
    # machine with no display otherwise fails rather than producing a PNG.
    $env:QT_QPA_PLATFORM = "offscreen"
    Write-Host "Rendering gallery snapshot -> $Output"
    & $pythonExe $renderScript $Output
}
else {
    # Deliberately NOT forcing a platform here: the whole point of this mode
    # is a real window on the real display server.
    Write-Host "Opening the Widget Kit gallery. Close the window to exit."
    & $pythonExe $renderScript "--show"
}

if ($LASTEXITCODE -ne 0) {
    throw "Gallery exited with code $LASTEXITCODE — see the QML errors above."
}
