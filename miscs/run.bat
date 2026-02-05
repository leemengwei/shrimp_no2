@echo off
echo ========================================
echo   Polymarket 实时数据展示应用启动
echo ========================================
echo.

REM 检查 Python 是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误: 未找到 Python
    echo 请先安装 Python: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo ✓ Python 已安装

REM 检查依赖是否安装
pip list | findstr flask >nul 2>&1
if errorlevel 1 (
    echo.
    echo 📦 正在安装依赖...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ❌ 依赖安装失败
        pause
        exit /b 1
    )
    echo ✓ 依赖安装完成
) else (
    echo ✓ 依赖已安装
)

echo.
echo 🚀 正在启动应用...
echo.
echo 📊 访问地址: http://localhost:5000
echo.
echo 💡 按 Ctrl+C 停止应用
echo.

python app.py
