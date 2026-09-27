@echo off
chcp 65001 >nul
setlocal

echo ============================================
echo   TianFuWubi  Windows 版  一键编译
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [错误] 未找到 python，请先安装 Python 3.8+ 并勾选 Add to PATH
    pause
    exit /b 1
)

python --version
echo.

echo [1/4] 检查 PyInstaller ...
python -c "import PyInstaller" >nul 2>nul
if errorlevel 1 (
    echo       未安装，正在安装（首次需要联网）...
    python -m pip install --upgrade pip
    python -m pip install pyinstaller
    if errorlevel 1 (
        echo [错误] PyInstaller 安装失败
        pause
        exit /b 1
    )
)
echo       OK
echo.

echo [2/4] 清理旧产物 ...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist TianFuWubi.exe del /q TianFuWubi.exe
echo       OK
echo.

echo [3/4] 语法自检 ...
python -m py_compile main.py engine.py db.py config.py sounds.py winapi.py ui_keyboard.py ui_phrase.py ui_settings.py
if errorlevel 1 (
    echo [错误] 语法检查未通过
    pause
    exit /b 1
)
echo       OK
echo.

echo [4/4] 正在打包（约 1-3 分钟）...
python -m PyInstaller TianFuWubi.spec --noconfirm --clean
if errorlevel 1 (
    echo [错误] 打包失败
    pause
    exit /b 1
)

if exist dist\TianFuWubi.exe (
    copy /y dist\TianFuWubi.exe TianFuWubi.exe >nul
    echo.
    echo ============================================
    echo   编译完成：TianFuWubi.exe
    echo ============================================
    echo.
    echo 用法：
    echo   1. 双击 TianFuWubi.exe 启动（主控窗会自动最小化到任务栏）
    echo   2. 按 Ctrl+Space 呼出输入面板
    echo   3. 打字 → 数字/空格选词 → 自动粘贴到原来的窗口
    echo.
    echo 提示：首次使用建议在设置里确认热键没被其它程序占用。
) else (
    echo [错误] 未生成 exe
)

echo.
pause
