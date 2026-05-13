@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo Git 一键上传脚本
echo ========================================

:: 检查是否是Git仓库
if not exist ".git" (
echo [错误] 当前目录不是Git仓库！
pause
exit /b 1
)

:: 显示当前分支
for /f "delims=" %%i in ('git branch --show-current 2^>nul') do set "branch=%%i"
if "%branch%"=="" (
echo [错误] 无法获取当前分支
pause
exit /b 1
)
echo 当前分支: %branch%

:: 检查是否有文件更改
git status --porcelain > "%temp%_git_status.txt"
set "has_changes="
for /f "usebackq delims=" %%i in ("%temp%_git_status.txt") do set "has_changes=1"
del /f /q "%temp%_git_status.txt" >nul 2>&1

if not defined has_changes (
echo.
echo [提示] 没有需要提交的文件更改
echo ========================================
pause
exit /b 0
)

:: 显示更改状态
echo.
echo 待提交的文件:
git status --short

:: 获取提交信息
echo.
set /p commit_msg="请输入提交信息（直接回车使用默认信息）: "
if "%commit_msg%"=="" (
set "commit_msg=Update: %date% %time%"
)

echo.
echo 正在提交并推送...

:: 执行 add
git add -A
if errorlevel 1 (
echo [错误] git add 失败！
pause
exit /b 1
)

:: 执行 commit
git commit -m "%commit_msg%"
if errorlevel 1 (
echo [错误] git commit 失败！
pause
exit /b 1
)

:: 执行 push
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