@echo off
echo [额外步骤] 开始 Git 提交与推送...

:: 设置行尾符自动转换（避免 LF->CRLF 警告）
git config core.autocrlf true

cd /d C:\Users\52483\Desktop\R.9\xml

:: 添加所有变更
git add .

:: 提交（若没有变更则跳过）
git commit -m "自动化提交 %date% %time%" 2>nul
if errorlevel 1 (
    echo 没有需要提交的变更，跳过 commit
)

:: 推送并自动应答 n（避免卡在 "Should I try again?"）
echo n | git push

:: 检查推送结果
if errorlevel 1 (
    echo 警告：Git 推送失败，请稍后手动执行 push
) else (
    echo Git 推送成功！
)
echo ========================================

echo 程序将在10秒后自动关闭...
echo ========================================
::timeout /t 10 /nobreak >nul

endlocal
