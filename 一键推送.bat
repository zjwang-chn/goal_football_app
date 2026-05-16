@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo        Git 一键上传脚本
echo ========================================

:: 切换到脚本所在目录（即仓库根目录）
cd /d "%~dp0"

:: 检查是否是Git仓库
if not exist ".git" (
    echo [错误] 当前目录不是Git仓库！
    echo 请确保 .git 文件夹存在于 %~dp0
    exit /b 1
)

:: 显示当前分支
for /f "delims=" %%i in ('git branch --show-current 2^>nul') do set "branch=%%i"
if "%branch%"=="" (
    echo [错误] 无法获取当前分支
    exit /b 1
)
echo 当前分支: %branch%

:: 检查是否有文件更改
git status --porcelain > "%temp%\_git_status.txt"
set "has_changes="
for /f "usebackq delims=" %%i in ("%temp%\_git_status.txt") do set "has_changes=1"
del /f /q "%temp%\_git_status.txt" >nul 2>&1

if not defined has_changes (
    echo [提示] 没有需要提交的文件更改
    exit /b 0
)

:: 显示更改状态
echo.
echo 待提交的文件:
git status --short

:: 自动生成提交信息（日期时间）
for /f "tokens=1-3 delims=/ " %%a in ('date /t') do set "today=%%a%%b%%c"
for /f "tokens=1-2 delims=: " %%a in ('time /t') do set "now=%%a%%b"
set "commit_msg=Auto update: %today%_%now%"
echo 提交信息: %commit_msg%

:: 执行 add
git add -A
if errorlevel 1 (
    echo [错误] git add 失败！
    exit /b 1
)

:: 执行 commit
git commit -m "%commit_msg%"
if errorlevel 1 (
    echo [错误] git commit 失败！
    exit /b 1
)

:: 执行 push
git push
if errorlevel 1 (
    echo [错误] git push 失败！
    exit /b 1
)

echo.
echo ========================================
echo ✅ 推送成功！
echo ========================================
exit /b 0