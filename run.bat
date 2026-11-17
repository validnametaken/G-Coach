@echo off
chcp 65001 >nul
echo ============================================
echo    G-Coach - Startup Script
echo ============================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [Error] Python not detected. Please install Python 3.10+ first.
    pause
    exit /b 1
)

:: Check dependencies
echo [1/2] Checking dependencies...
python -c "import PyQt6, pyperclip, keyboard, win32api, httpx, uiautomation, symspellpy" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing dependencies...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [Error] Failed to install dependencies.
        pause
        exit /b 1
    )
)

:: Start application
echo [2/2] Starting application...
python gcoach.py %*
set "APP_EXIT_CODE=%ERRORLEVEL%"

if not "%APP_EXIT_CODE%"=="0" pause
exit /b %APP_EXIT_CODE%
