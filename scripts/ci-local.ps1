#Requires -Version 5.1
<#
.SYNOPSIS
    Local CI runner - mirrors the GitHub Actions CI pipeline for Sagittarius Engine.

.DESCRIPTION
    Runs Ruff lint, Ruff format check, Mypy static type check, Pytest with
    coverage, and the architecture-boundary tests, in that order.

    Every step runs regardless of earlier failures — failures accumulate and
    are reported together at the end, so one run tells you everything that's
    red instead of one failure per run (see TASK-028).

    The full run is captured to a timestamped log file under logs/, plus a
    logs/ci-local-latest.log pointer to the most recent run. Console output
    can be truncated or piped through `tail` and still hide a real failure —
    context/testing.md documents this trap; this script is what makes it
    unreachable instead of just warned about.

.PARAMETER SkipLint
    Skip Ruff lint, Ruff format check, and Mypy static type check steps.

.PARAMETER SkipTests
    Skip Pytest and the architecture-boundary test steps.

.PARAMETER Full
    Explicit alias for the default behavior: lint + format + mypy + full test
    suite with the coverage gate enforced.

.PARAMETER AllowLogWarnings
    A green exit code is not proof a run was clean — this script scans the
    captured pytest log for WARNING/ERROR/CRITICAL records after the test
    step and fails the gate if any are found. Set this only to triage a run
    whose hits are already understood and recorded, never as the normal way
    to get a green build.

.EXAMPLE
    .\scripts\ci-local.ps1                # Full: lint + mypy + tests (default)
    .\scripts\ci-local.ps1 -SkipLint       # Tests only
    .\scripts\ci-local.ps1 -SkipTests      # Lint + mypy only
#>
[CmdletBinding()]
param(
    [switch]$SkipLint,
    [switch]$SkipTests,
    [switch]$Full,
    [switch]$AllowLogWarnings
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Name)
    Write-Host ""
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
    Write-Host "  ▶  $Name" -ForegroundColor Cyan
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Name)
    Write-Host "  ✅  $Name passed" -ForegroundColor Green
}

function Write-Failure {
    param([string]$Name)
    Write-Host "  ❌  $Name FAILED" -ForegroundColor Red
}

#: A green exit code from pytest doesn't mean the run was clean — something
#: can log an ERROR mid-test and the assertion still happen to pass. Scans
#: the captured log for Engine's own record shape (std_logger.py:
#: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"), not bare words —
#: pytest's own output says "warnings summary" and "ERROR" for collection
#: errors, which are not application log records.
function Invoke-RunLogScan {
    param([string]$LogFile, [string]$Label)

    if (-not (Test-Path $LogFile)) {
        Write-Host "  ⚠️  $Label — no log file captured at $LogFile" -ForegroundColor Yellow
        return $false
    }

    $hits = Select-String -Path $LogFile -Pattern '- (WARNING|ERROR|CRITICAL) -'
    if (-not $hits -or $hits.Count -eq 0) {
        Write-Host "  ✅  $Label — no WARNING/ERROR/CRITICAL log records" -ForegroundColor Green
        return $false
    }

    Write-Host ""
    Write-Host "  🔎  $Label — $($hits.Count) problem-level log record(s) found:" -ForegroundColor Yellow
    foreach ($level in @('CRITICAL', 'ERROR', 'WARNING')) {
        $ofLevel = $hits | Where-Object { $_.Line -match "- $level -" }
        if ($ofLevel.Count -gt 0) {
            Write-Host "     $level : $($ofLevel.Count)" -ForegroundColor Yellow
        }
    }
    Write-Host ""
    # Distinct messages only — one real defect can log the same line on
    # every iteration of a loop, and dozens of copies hide the other hits.
    $hits |
        ForEach-Object { $_.Line.Trim() } |
        Select-Object -Unique |
        Select-Object -First 25 |
        ForEach-Object { Write-Host "     $_" -ForegroundColor DarkYellow }
    Write-Host ""
    Write-Host "  Every hit should be investigated: either a real defect, or an" -ForegroundColor Yellow
    Write-Host "  understood expected condition. Full log: $LogFile" -ForegroundColor DarkGray
    return $true
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot  = Split-Path -Parent $scriptDir

# context/testing.md's documented trap, made unreachable: every step's full
# output is captured to a real file automatically, so nobody — human or AI —
# has to remember to redirect manually or avoid `| tail`.
$logsDir = Join-Path $repoRoot "logs"
if (-not (Test-Path $logsDir)) { New-Item -ItemType Directory -Path $logsDir -Force | Out-Null }
$transcriptLog = Join-Path $logsDir "ci-local-$(Get-Date -Format 'yyyyMMdd-HHmmss').log"
$latestLogPointer = Join-Path $logsDir "ci-local-latest.log"
$transcriptStarted = $false
try {
    Start-Transcript -Path $transcriptLog -Force | Out-Null
    $transcriptStarted = $true
} catch {
    Write-Warning "Could not start full-run transcript ($($_.Exception.Message)) — output will only reach the console."
}

$isWindowsOs = if (Test-Path variable:IsWindows) { $IsWindows } else { $true }
$venvBinSubdir = if ($isWindowsOs) { "Scripts" } else { "bin" }
$exeSuffix     = if ($isWindowsOs) { ".exe" } else { "" }
$tempDir = [System.IO.Path]::GetTempPath().TrimEnd('/', '\')

$venvRoot = if (Test-Path (Join-Path $repoRoot ".venv")) { Join-Path $repoRoot ".venv" } else { $null }
$venvBinDir = if ($venvRoot) { Join-Path $venvRoot $venvBinSubdir } else { $null }
$pytestExe = if ($venvBinDir) { Join-Path $venvBinDir "pytest$exeSuffix" } else { "pytest" }
$ruffExe   = if ($venvBinDir) { Join-Path $venvBinDir "ruff$exeSuffix" } else { "ruff" }
$mypyExe   = if ($venvBinDir) { Join-Path $venvBinDir "mypy$exeSuffix" } else { "mypy" }

if (-not $venvRoot) {
    Write-Warning "Virtual environment not found at $repoRoot\.venv. Using system Python/tools."
}

$failed = @()

#: TASK-021 req. 5 — requirements-dev.txt pins ruff and mypy to the versions CI
#: installs, but nothing ever checked that the *local* tools match. They drifted
#: silently (local ruff 0.16.4 / mypy 2.3.1 vs CI's 0.15.20 / 2.1.0 on
#: 2026-08-23), which means a green local gate is not evidence CI will be green:
#: ruff's default rule set widens every release, and a newer mypy reports errors
#: an older one does not. This is a warning, not a failure — it must not block
#: someone who deliberately runs a newer tool — but the drift is now visible
#: instead of invisible.
function Test-ToolchainPins {
    $reqFile = Join-Path $repoRoot "requirements-dev.txt"
    if (-not (Test-Path $reqFile)) { return }

    $checks = @(
        @{ Name = "ruff"; Exe = $ruffExe; Args = @("--version") },
        @{ Name = "mypy"; Exe = $mypyExe; Args = @("--version") }
    )

    foreach ($check in $checks) {
        $pinLine = Select-String -Path $reqFile -Pattern "^$($check.Name)==(.+)$"
        if (-not $pinLine) { continue }
        $pinned = $pinLine.Matches[0].Groups[1].Value.Trim()

        try {
            $raw = & $check.Exe @($check.Args) 2>&1 | Select-Object -First 1
        } catch {
            Write-Host "  ⚠️  $($check.Name) — not runnable; cannot compare against pin $pinned" -ForegroundColor Yellow
            continue
        }

        $m = [regex]::Match([string]$raw, '(\d+\.\d+\.\d+)')
        if (-not $m.Success) { continue }
        $installed = $m.Groups[1].Value

        if ($installed -ne $pinned) {
            Write-Host "  ⚠️  $($check.Name) $installed installed, but requirements-dev.txt pins $pinned" -ForegroundColor Yellow
            Write-Host "      A green run here is not proof CI is green. Reinstall with:" -ForegroundColor DarkGray
            Write-Host "      pip install -r requirements-dev.txt" -ForegroundColor DarkGray
        } else {
            Write-Host "  ✅  $($check.Name) $installed matches the CI pin" -ForegroundColor Green
        }
    }
}

if (-not $SkipLint) {
    Write-Step "Toolchain — local versions vs requirements-dev.txt pins"
    Test-ToolchainPins
}

# ---------------------------------------------------------------------------
# Lint
# ---------------------------------------------------------------------------
if (-not $SkipLint) {
    Write-Step "Ruff — Lint Check (ruff check sagittarius_engine tests examples tools)"
    Push-Location $repoRoot
    try {
        & $ruffExe check sagittarius_engine tests examples tools
        if ($LASTEXITCODE -ne 0) { $failed += "Ruff Lint"; Write-Failure "Ruff Lint" }
        else { Write-Success "Ruff Lint" }
    } catch {
        $failed += "Ruff Lint"; Write-Failure "Ruff Lint"
        Write-Host $_.Exception.Message -ForegroundColor Yellow
    } finally { Pop-Location }

    Write-Step "Ruff — Format Check (ruff format --check sagittarius_engine tests examples tools)"
    Push-Location $repoRoot
    try {
        & $ruffExe format --check sagittarius_engine tests examples tools
        if ($LASTEXITCODE -ne 0) { $failed += "Ruff Format"; Write-Failure "Ruff Format" }
        else { Write-Success "Ruff Format" }
    } catch {
        $failed += "Ruff Format"; Write-Failure "Ruff Format"
        Write-Host $_.Exception.Message -ForegroundColor Yellow
    } finally { Pop-Location }

    Write-Step "Mypy — Static Type Check"
    Push-Location $repoRoot
    try {
        & $mypyExe sagittarius_engine tests examples tools --ignore-missing-imports --follow-imports=skip
        if ($LASTEXITCODE -ne 0) { $failed += "Mypy"; Write-Failure "Mypy" }
        else { Write-Success "Mypy" }
    } catch {
        $failed += "Mypy"; Write-Failure "Mypy"
        Write-Host $_.Exception.Message -ForegroundColor Yellow
    } finally { Pop-Location }
}

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
if (-not $SkipTests) {
    $env:QT_QPA_PLATFORM = "offscreen"

    $runLogFile = Join-Path $tempDir "ci_local_run_$([System.Diagnostics.Process]::GetCurrentProcess().Id).log"
    if (Test-Path $runLogFile) { Remove-Item $runLogFile -Force -ErrorAction SilentlyContinue }

    Write-Step "Pytest — Full Suite (coverage gated at 80%)"
    Push-Location $repoRoot
    try {
        # examples/student_management/tests/ added here 2026-08-23: neither
        # this gate nor .github/workflows/ci.yml's "examples" job ever ran
        # it -- that job's own tests/test_examples.py is misleadingly named
        # and only runs unrelated stress tests + the benchmark script, never
        # the sample app's own ~48 tests. They had been silently unprotected
        # by any CI/gate since the app was built (EPIC-002).
        & $pytestExe tests/ examples/student_management/tests/ `
            --ignore=tests/runtime/benchmark_runtime.py `
            --cov=sagittarius_engine --cov-report=xml --cov-report=term-missing --cov-fail-under=80 `
            -q 2>&1 | Tee-Object -FilePath $runLogFile
        if ($LASTEXITCODE -ne 0) { $failed += "Tests"; Write-Failure "Tests" }
        else { Write-Success "Tests" }
    } catch {
        $failed += "Tests"; Write-Failure "Tests"
        Write-Host $_.Exception.Message -ForegroundColor Yellow
    } finally { Pop-Location }

    Write-Step "Pytest — Architecture Boundary Tests"
    Push-Location $repoRoot
    try {
        & $pytestExe tests/test_architecture.py -v 2>&1 | Tee-Object -FilePath $runLogFile -Append
        if ($LASTEXITCODE -ne 0) { $failed += "Architecture Tests"; Write-Failure "Architecture Tests" }
        else { Write-Success "Architecture Tests" }
    } catch {
        $failed += "Architecture Tests"; Write-Failure "Architecture Tests"
        Write-Host $_.Exception.Message -ForegroundColor Yellow
    } finally { Pop-Location }

    Write-Step "Run Log Scan (WARNING / ERROR / CRITICAL)"
    $hasLogProblems = Invoke-RunLogScan -LogFile $runLogFile -Label "Run log"
    if ($hasLogProblems) {
        if ($AllowLogWarnings) {
            Write-Host "  ⚠️  -AllowLogWarnings set — not failing the run." -ForegroundColor Yellow
        } else {
            $failed += "Log Scan"; Write-Failure "Log Scan"
        }
    }
}

$exitCode = if ($failed.Count -eq 0) { 0 } else { 1 }

if ($transcriptStarted) {
    try { Stop-Transcript | Out-Null } catch {}
    Copy-Item -Path $transcriptLog -Destination $latestLogPointer -Force -ErrorAction SilentlyContinue
}

# Machine-readable summary, always the LAST thing printed. Truncated or
# tail'd console output can hide a real failure entirely (context/testing.md)
# — never trust a status claimed from anything earlier in the stream without
# opening LOG_FILE first.
Write-Host ""
Write-Host "===CI_LOCAL_RESULT==="
Write-Host "RESULT: $(if ($exitCode -eq 0) { 'PASS' } else { 'FAIL' })"
Write-Host "FAILED_STEPS: $(if ($failed.Count -eq 0) { 'none' } else { $failed -join ',' })"
Write-Host "LOG_FILE: $transcriptLog"
Write-Host "LOG_FILE_LATEST: $latestLogPointer"
Write-Host "INSTRUCTION: Do not report PASS/FAIL from this console output alone. Read LOG_FILE (grep for FAILED, ERROR, Traceback) before declaring the gate green."
Write-Host "===END_CI_LOCAL_RESULT==="

exit $exitCode
