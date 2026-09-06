@echo off
REM Elemes LMS Management Launcher for Windows (Command Prompt)
REM Default virtualenv selalu berada di parent folder (..\venv) agar elemes tetap bersih

set SCRIPT_DIR=%~dp0
set PARENT_DIR=%SCRIPT_DIR%..
set VENV_DIR=%PARENT_DIR%\venv
if exist "%PARENT_DIR%\.venv\Scripts\python.exe" (
    set VENV_DIR=%PARENT_DIR%\.venv
)
set VENV_PYTHON=%VENV_DIR%\Scripts\python.exe

REM 1. Buat virtualenv di parent jika belum ada
if not exist "%VENV_PYTHON%" (
    if not "%ELEMES_NO_VENV%"=="1" (
        echo [INFO] Menyiapkan virtualenv di parent folder (..\venv)...
        python -m venv "%VENV_DIR%"
    )
)

REM 2. Pastikan dependensi rich terpasang di venv
if exist "%VENV_PYTHON%" (
    "%VENV_PYTHON%" -c "import rich" >nul 2>&1
    if errorlevel 1 (
        echo [INFO] Memasang dependensi CLI (rich) ke ..\venv...
        if exist "%SCRIPT_DIR%requirements-cli.txt" (
            "%VENV_PYTHON%" -m pip install -q -r "%SCRIPT_DIR%requirements-cli.txt"
        ) else (
            "%VENV_PYTHON%" -m pip install -q "rich>=13.0.0"
        )
    )
    "%VENV_PYTHON%" "%SCRIPT_DIR%elemes.py" %*
) else (
    python "%SCRIPT_DIR%elemes.py" %*
)
