@echo off
chcp 65001 >nul
title TianFuWubi

rem 直接以源码方式运行（不打包，便于调试）
where python >nul 2>nul
if errorlevel 1 (
    echo 未找到 python，请先安装 Python 3.8+
    pause
    exit /b 1
)

start "" pythonw main.py
