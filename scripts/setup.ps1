# Create the virtual environment and install dependencies (Windows PowerShell).
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\setup.ps1 [-SystemSitePackages]
param([switch]$SystemSitePackages)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path .venv)) {
    if ($SystemSitePackages) { python -m venv --system-site-packages .venv } else { python -m venv .venv }
}
$py = ".venv\Scripts\python.exe"
& $py -m pip install --upgrade pip
& $py -m pip install -r requirements.txt
# Make the `amm` package importable. Editable install needs the `wheel` package;
# if that is unavailable (offline), fall back to a .pth path entry.
& $py -m pip install -e . --no-deps
if ($LASTEXITCODE -ne 0) {
    $site = & $py -c "import sysconfig; print(sysconfig.get_paths()['purelib'])"
    (Resolve-Path src).Path | Out-File -Encoding ascii "$site\amm-src.pth"
    Write-Host "Editable install unavailable; wrote $site\amm-src.pth"
}
& $py -c "import amm, river, sklearn; print('ok: amm', amm.__version__, '| river', river.__version__, '| sklearn', sklearn.__version__)"
