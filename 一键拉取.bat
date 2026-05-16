@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo         Git 一键拉取脚本
echo ========================================

cd /d "%~dp0"

if not exist ".git" (
    echo [错误] 当前目录不是Git仓库！
    exit /b 1
)

for /f "delims=" %%i in ('git branch --show-current 2^>nul') do set branch=%%i
if "%branch%"=="" (
    echo [错误] 无法获取当前分支
    exit /b 1
)
echo 当前分支: %branch%

echo 正在暂存所有本地修改...
git stash push -u -m "Auto stash before pull" >nul 2>&1
set stash_result=%errorlevel%

echo 正在从远程仓库拉取最新代码...
git pull --rebase
if errorlevel 1 (
    echo.
    echo [错误] 拉取失败，可能存在冲突！
    if !stash_result! equ 0 (
        echo 正在恢复之前的暂存...
        git stash pop >nul 2>&1
    )
    exit /b 1
)

if !stash_result! equ 0 (
    echo 恢复本地修改...
    git stash pop >nul 2>&1
    if errorlevel 1 (
        echo [警告] 恢复本地修改时产生冲突，请手动处理。
    )
)

echo.
echo ========================================
echo ✅ 拉取成功！
echo ========================================
exit /b 0