<#
.SYNOPSIS
    Elemes LMS Management Launcher for Windows PowerShell
    Default virtualenv selalu berada di parent folder (..\venv) agar elemes tetap bersih
#>

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ParentDir = Split-Path -Parent $ScriptDir

$VenvDir = Join-Path $ParentDir "venv"
if (Test-Path (Join-Path $ParentDir ".venv\Scripts\python.exe")) {
    $VenvDir = Join-Path $ParentDir ".venv"
}
$VenvPy = Join-Path $VenvDir "Scripts\python.exe"

# 1. Buat virtualenv di parent jika belum ada
if (-not (Test-Path $VenvPy) -and ($env:ELEMES_NO_VENV -ne "1")) {
    Write-Host "📦 Menyiapkan virtualenv di parent folder (..\venv)..." -ForegroundColor Cyan
    & python -m venv $VenvDir
}

# 2. Pastikan dependensi rich terpasang di venv
if (Test-Path $VenvPy) {
    & $VenvPy -c "import rich" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "📦 Memasang dependensi CLI (rich) ke ..\venv..." -ForegroundColor Cyan
        $ReqFile = Join-Path $ScriptDir "requirements-cli.txt"
        if (Test-Path $ReqFile) {
            & $VenvPy -m pip install -q -r $ReqFile
        } else {
            & $VenvPy -m pip install -q "rich>=13.0.0"
        }
    }
    & $VenvPy (Join-Path $ScriptDir "elemes.py") $args
} else {
    & python (Join-Path $ScriptDir "elemes.py") $args
}
