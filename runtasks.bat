@echo off
title 文件处理任务 - 全自动
echo 正在启动完整流程：拉取 -> 处理 -> 推送
echo.

:: 切换到仓库根目录（即 xml 文件夹）
cd /d "C:\Users\52483\Desktop\R.9\xml"

:: 1. 拉取最新数据
echo [1/3] 执行拉取...
call "%~dp0一键拉取.bat"
if errorlevel 1 (
    echo 拉取失败，停止后续操作。
    pause
    exit /b 1
)

:: 2. 执行数据处理脚本
echo [2/3] 执行数据处理...
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0DoTasks.ps1"
if errorlevel 1 (
    echo 数据处理出错，停止推送。
    pause
    exit /b 1
)

:: 3. 推送处理后的内容
echo [3/3] 执行推送...
call "%~dp0一键推送.bat"
if errorlevel 1 (
    echo 推送失败，请检查网络或权限。
    pause
    exit /b 1
)

echo.
echo 全部任务完成。
pause