@echo off
cd /d "C:\Users\52483\Desktop\R.9\xml"
git add .
git commit -m "自动化提交 %date% %time%"
git push
pause