@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo         Git 一键上传脚本
echo ========================================

:: 检查是否是Git仓库
if not exist ".git" (
    echo [错误] 当前目录不是Git仓库！
    pause
    exit /b 1
)

:: 显示当前分支
for /f "delims=" %%i in ('git branch --show-current') do set branch=%%i
echo 当前分支: %branch%

:: 检查是否有文件更改
git status --porcelain > temp_status.txt
set /p status=<temp_status.txt
del temp_status.txt 2>nul

if "%status%"=="" (
    echo [提示] 没有需要提交的文件更改
    pause
    exit /b 0
)

:: 显示更改状态
echo.
echo 待提交的文件:
git status --short
echo.

:: 获取提交信息
set /p commit_msg="请输入提交信息（直接回车使用默认信息）: "
if "%commit_msg%"=="" (
    set commit_msg=Update:%date% %time%
)

echo.
echo 正在提交并推送...

:: 执行 add -> commit -> push
git add -A
if errorlevel 1 (
    echo [错误] git add 失败！
    pause
    exit /b 1
)

git commit -m "%commit_msg%"
if errorlevel 1 (
    echo [错误] git commit 失败！
    pause
    exit /b 1
)

git push
if errorlevel 1 (
    echo [错误] git push 失败！
    pause
    exit /b 1
)

echo.
echo ========================================
echo ✅ 推送成功！
echo ========================================
pause