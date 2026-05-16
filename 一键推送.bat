@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo        Git 一键上传脚本
echo ========================================

cd /d "%~dp0"

if not exist ".git" (
    echo [错误] 当前目录不是Git仓库！
    exit /b 1
)

for /f "delims=" %%i in ('git branch --show-current 2^>nul') do set "branch=%%i"
if "%branch%"=="" (
    echo [错误] 无法获取当前分支
    exit /b 1
)
echo 当前分支: %branch%

git status --porcelain > "%temp%\_git_status.txt"
set "has_changes="
for /f "usebackq delims=" %%i in ("%temp%\_git_status.txt") do set "has_changes=1"
del /f /q "%temp%\_git_status.txt" >nul 2>&1

if not defined has_changes (
    echo [提示] 没有需要提交的文件更改
    exit /b 0
)

echo.
echo 待提交的文件:
git status --short

for /f "tokens=1-3 delims=/ " %%a in ('date /t') do set "today=%%a%%b%%c"
for /f "tokens=1-2 delims=: " %%a in ('time /t') do set "now=%%a%%b"
set "commit_msg=Auto update: %today%_%now%"
echo 提交信息: %commit_msg%

git add -A
if errorlevel 1 (
    echo [错误] git add 失败！
    exit /b 1
)

git commit -m "%commit_msg%"
if errorlevel 1 (
    echo [错误] git commit 失败！
    exit /b 1
)

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