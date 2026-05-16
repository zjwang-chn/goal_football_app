@echo off
title 文件处理任务
echo 正在启动 PowerShell 脚本，请稍候...
echo.

:: 切换到脚本所在目录（防止路径问题）
cd /d "%~dp0"

:: 执行 PowerShell 脚本，并保持窗口等待
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0DoTasks.ps1"

echo.
echo 脚本执行完毕。请按任意键关闭窗口...
pause > nul