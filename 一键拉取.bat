@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo         Git 一键拉取脚本
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
for /f "delims=" %%i in ('git branch --show-current 2^>nul') do set branch=%%i
if "%branch%"=="" (
    echo [错误] 无法获取当前分支
    exit /b 1
)
echo 当前分支: %branch%

:: 暂存本地修改，避免拉取冲突
echo 正在暂存本地修改...
git stash push -m "Auto stash before pull" --keep-index 2>nul
if errorlevel 1 (
    echo [警告] stash 失败，可能没有需要暂存的内容。
)

:: 拉取并变基
echo 正在从远程仓库拉取最新代码...
git pull --rebase
if errorlevel 1 (
    echo.
    echo [错误] 拉取失败，可能存在冲突！
    git stash pop 2>nul
    echo 请手动解决冲突后重新运行
    exit /b 1
)

:: 恢复暂存的修改
echo 恢复本地修改...
git stash pop 2>nul
if errorlevel 1 (
    echo [警告] stash pop 产生冲突，请手动处理。
)

echo.
echo ========================================
echo ✅ 拉取成功！
echo ========================================
exit /b 0