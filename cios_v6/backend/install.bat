@echo off
REM ─────────────────────────────────────────────────────────
REM  CIOS Backend — Windows Install Script
REM  Double-click this file OR run in VS Code terminal
REM ─────────────────────────────────────────────────────────

echo.
echo  ======================================
echo   CIOS Backend — Installing...
echo  ======================================
echo.

REM Check Python version
python --version 2>NUL
if errorlevel 1 (
    echo ERROR: Python not found. Install Python 3.11+ from https://python.org
    pause
    exit /b 1
)

REM Upgrade pip first (CRITICAL — old pip causes Rust/build errors)
echo [1/4] Upgrading pip...
python -m pip install --upgrade pip --quiet
echo  Done.

REM Create virtual environment
echo [2/4] Creating virtual environment...
python -m venv venv
echo  Done.

REM Activate venv
echo [3/4] Activating virtual environment...
call venv\Scripts\activate.bat

REM Install all packages (pre-built wheels only, no compilation)
echo [4/4] Installing packages (this takes 1-2 minutes)...
pip install -r requirements.txt --only-binary :all: --quiet

if errorlevel 1 (
    echo.
    echo  Retrying without --only-binary flag...
    pip install -r requirements.txt --quiet
)

echo.
echo  ======================================
echo   Installation complete!
echo  ======================================
echo.
echo  Next steps:
echo    copy .env.example .env
echo    venv\Scripts\activate
echo    python -m uvicorn app.main:app --reload --port 8000
echo.
pause
