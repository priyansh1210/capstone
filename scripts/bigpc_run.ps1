# Heavy runs for the big PC. Logs every step to memory\RUNLOG.md and memory\logs\.
# Usage (from the repo root, after scripts\setup.ps1):
#   powershell -ExecutionPolicy Bypass -File scripts\bigpc_run.ps1            # everything
#   powershell -ExecutionPolicy Bypass -File scripts\bigpc_run.ps1 -Workers 6 -SkipPrepare
param(
    [int]$Workers = 0,
    [switch]$SkipPrepare,
    [switch]$SkipTests,
    [switch]$SkipCalibrate,
    [switch]$SkipSmoke,
    [switch]$SkipBenchmark
)
$ErrorActionPreference = "Continue"   # native stderr (warnings) must not abort the script
Set-Location (Split-Path $PSScriptRoot -Parent)
$py = ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { Write-Error "Run scripts\setup.ps1 first"; exit 1 }
$env:PYTHONWARNINGS = "ignore"
$env:PYTHONUNBUFFERED = "1"
New-Item -ItemType Directory -Force memory\logs, memory\machines | Out-Null
$utf8 = New-Object System.Text.UTF8Encoding($false)   # UTF-8 without BOM (PS 5.1 Tee-Object writes UTF-16)
function Write-Utf8([string]$path, [string]$text, [switch]$Append) {
    $full = Join-Path (Get-Location) $path
    if ($Append) { [IO.File]::AppendAllText($full, $text, $utf8) } else { [IO.File]::WriteAllText($full, $text, $utf8) }
}

# ---- machine profile ---------------------------------------------------------
$cpu = Get-CimInstance Win32_Processor
$cores = ($cpu | Measure-Object -Property NumberOfCores -Sum).Sum
$threads = ($cpu | Measure-Object -Property NumberOfLogicalProcessors -Sum).Sum
$ramGB = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1)
if ($Workers -le 0) {
    # each worker fits with 2 threads and needs ~2 GB; keep ~4 GB for the OS
    $Workers = [math]::Max(1, [math]::Min([math]::Floor($threads / 2), [math]::Floor(($ramGB - 4) / 2)))
    $Workers = [math]::Min($Workers, 8)
}
$host_ = $env:COMPUTERNAME
$pyver = & $py -c "import sys; print(sys.version.split()[0])"
$pkgs = & $py -c "import numpy, pandas, sklearn, river, streamlit, scipy, pyarrow; print(f'numpy {numpy.__version__}, pandas {pandas.__version__}, scikit-learn {sklearn.__version__}, river {river.__version__}, streamlit {streamlit.__version__}, scipy {scipy.__version__}, pyarrow {pyarrow.__version__}')"
$gpu = (Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name) -join "; "
@"
# $host_ (big PC)

- CPU: $(($cpu | Select-Object -First 1).Name.Trim()), $cores cores / $threads threads
- RAM: $ramGB GB; GPU: $gpu (not used: CPU-only models by design)
- OS: $((Get-CimInstance Win32_OperatingSystem).Caption)
- Python $pyver; $pkgs
- Workers used: $Workers
"@ | ForEach-Object { Write-Utf8 "memory\machines\$host_.md" $_ }
Write-Host "Machine $host_ : $cores cores / $threads threads, $ramGB GB RAM -> $Workers workers"

function Add-RunLog([string]$step, [string]$cmd, [double]$minutes, [string]$outcome) {
    $line = "| $(Get-Date -Format 'yyyy-MM-dd HH:mm') | $host_ | $step | ``$cmd`` | $([math]::Round($minutes, 1)) min | $outcome |"
    Write-Utf8 "memory\RUNLOG.md" "$line`n" -Append
}

function Invoke-Step([string]$name, [string[]]$cmdArgs) {
    $log = "memory\logs\$name.log"
    $cmdText = "amm " + ($cmdArgs -join " ")
    Write-Host "`n=== $name : $cmdText  (log: $log)" -ForegroundColor Cyan
    $sw = [Diagnostics.Stopwatch]::StartNew()
    Write-Utf8 $log ""
    & $py -m amm @cmdArgs 2>&1 | ForEach-Object {
        $l = "$_"
        Write-Host $l
        Write-Utf8 $log "$l`n" -Append
    }
    $code = $LASTEXITCODE
    $sw.Stop()
    $outcome = if ($code -eq 0) { "ok" } else { "FAILED (exit $code)" }
    Add-RunLog $name $cmdText $sw.Elapsed.TotalMinutes $outcome
    if ($code -ne 0) {
        Write-Host "Step $name failed - commit memory\ (logs + RUNLOG) and push so the laptop can diagnose." -ForegroundColor Red
        exit $code
    }
}

if (-not $SkipPrepare)   { Invoke-Step "prepare_data" @("prepare-data") }
if (-not $SkipTests)     { Invoke-Step "tests"        @("test") }
if (-not $SkipCalibrate) { Invoke-Step "calibrate"    @("calibrate", "--workers", "$Workers") }
if (-not $SkipSmoke)     { Invoke-Step "smoke"        @("smoke", "--workers", "$Workers") }
if (-not $SkipBenchmark) { Invoke-Step "benchmark"    @("benchmark", "--workers", "$Workers") }

# checksum comparison with the laptop (same raw inputs?)
$cmp = & $py -c "import json; a={f['name']:f['sha256'] for f in json.load(open('memory/laptop_SOURCES.json'))['files']}; b={f['name']:f['sha256'] for f in json.load(open('data/raw/SOURCES.json'))['files']}; d=[n for n in a if a.get(n)!=b.get(n)]; print(f'raw files compared: {len(a)}; differing or missing: {len(d)} {d[:5]}')"
Write-Host $cmp
Write-Utf8 "memory\logs\checksum_compare.log" "$cmp`n"

Write-Host "`nDone. Now commit and push the results:" -ForegroundColor Green
Write-Host "  git add memory reports configs/frozen_policy.yaml"
Write-Host "  git commit -m `"Big PC: calibration + benchmark results`""
Write-Host "  git push"
