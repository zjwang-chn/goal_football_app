@echo off


echo ========================================
echo         Git 一键拉取脚本
echo ========================================

:: 检查是否是Git仓库
if not exist ".git" (
    echo [错误] 当前目录不是Git仓库！
    pause
    exit /b 1
)

:: 显示当前分支 (修复: --show-current)
for /f "delims=" %%i in ('git branch --show-current') do set branch=%%i
echo 当前分支: %branch%

echo.
echo 正在从远程仓库拉取最新代码...

:: 拉取并合并
git pull
if errorlevel 1 (
    echo.
    echo [错误] 拉取失败，可能存在冲突！
    echo 请手动解决冲突后重新运行
    pause
    exit /b 1
)

echo.
echo ========================================
echo  拉取成功！
echo ========================================
pause
