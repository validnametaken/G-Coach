@echo off
chcp 65001 >nul
echo ============================================
echo    G-Coach - 启动脚本
echo ============================================
echo.

:: 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)

:: 检查依赖
echo [1/2] 检查依赖...
python -c "import PyQt6, pyperclip, keyboard, win32api, httpx, uiautomation, symspellpy" >nul 2>&1
if %errorlevel% neq 0 (
    echo 正在安装依赖...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [错误] 依赖安装失败。
        pause
        exit /b 1
    )
)

:: 启动
echo [2/2] 启动程序...
python gcoach.py %*
set "APP_EXIT_CODE=%ERRORLEVEL%"

if not "%APP_EXIT_CODE%"=="0" pause
exit /b %APP_EXIT_CODE%
