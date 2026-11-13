@echo off
echo ============================================
echo   AMB Terminal - Setup & Launch
echo ============================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install Python 3.10+ from python.org
    pause
    exit /b 1
)

echo [1/3] Installing dependencies...
pip install -r requirements.txt --quiet

echo [2/3] Dependencies installed.
echo [3/3] Starting AMB Terminal...
echo.
echo NOTE: To close the terminal, click Settings (top right) -> Close Terminal
echo       or press F12
echo.

python main.py

pause
