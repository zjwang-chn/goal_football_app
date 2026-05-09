@echo off
:: ========== Git 自动推送（防交互） ==========
echo [额外步骤] 开始 Git 提交与推送...

:: 设置行尾符自动转换
git config core.autocrlf true

cd /d "%XML_PATH%"

:: 先拉取远程更新（自动合并，避免冲突）
echo 正在拉取远程更新...
git pull --rebase --autostash
pause