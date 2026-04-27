@echo off
setlocal enabledelayedexpansion

REM ===============================================
REM   完整自动化流程：下载 + 归档 + 按日期整理 + Git推送
REM ===============================================

set "BASE_PATH=C:\Users\52483\Desktop\R.9"
set "R8_PATH=%BASE_PATH%\R8"
set "XML_PATH=%BASE_PATH%\xml"
set "TARGET_BASE=%BASE_PATH%\DATA\20990909_235959"

echo ========================================
echo     开始执行完整自动化流程
echo ========================================
echo.

:: 步骤1：30秒倒计时准备
echo [1/7] 准备阶段 - 30秒倒计时...
echo 请确认以下程序将被关闭：
echo   - Excel
echo   - Edge浏览器
echo.
echo 选择：
echo   [1] 立即运行
echo   [2] 退出运行
echo.
echo (30秒后无操作将自动继续运行)
echo.

choice /c 12 /n /t 30 /d 1 /m "请选择操作"

if errorlevel 2 (
    echo 用户选择退出运行。
    exit /b 0
)

:: 步骤2：关闭Excel
echo [2/7] 关闭Excel...
call "%R8_PATH%\close_excel.bat" 2>nul
if errorlevel 1 echo 警告：关闭Excel脚本执行失败，请手动关闭

:: 步骤3：关闭Edge
echo [3/7] 关闭Edge...
call "%R8_PATH%\close_edge.bat" 2>nul
if errorlevel 1 echo 警告：关闭Edge脚本执行失败

:: 步骤4：仅删除 XML 文件夹下的所有 XML 文件（保留其他文件）
echo [4/7] 删除 XML 文件夹中的 XML 文件...
if exist "%XML_PATH%" (
    del /q "%XML_PATH%\*.xml" 2>nul
    echo 已删除所有 XML 文件，其他文件已保留。
) else (
    mkdir "%XML_PATH%"
    echo 已创建 XML 文件夹。
)

:: 步骤5：执行下载操作（使用 Python 脚本）
echo [5/7] 执行下载操作...
python "%XML_PATH%\pyautogui_download_optimized.py"
if errorlevel 1 (
    echo 错误：Python脚本执行失败，请检查环境或脚本路径
    exit /b 1
)

:: 等待下载完成
echo 等待下载完成...
timeout /t 5 /nobreak >nul

:: 步骤6：生成时间戳并移动文件
echo [6/7] 归档文件到时间戳文件夹...

:: 检查XML文件夹是否存在
if not exist "%XML_PATH%" (
    echo 错误：XML文件夹不存在
    exit /b 1
)

:: 检查文件数量
set "file_count=0"
for %%f in ("%XML_PATH%\*.*") do (
    if exist "%%f" set /a file_count+=1
)

echo 文件夹内文件数量：!file_count!

if !file_count! neq 8 (
    echo 警告：文件数量不等于8，当前数量：!file_count!
    echo 继续执行，但请检查下载是否完整...
)

:: 生成时间戳 (格式：年月日_时分秒)
for /f "tokens=2 delims==" %%I in ('wmic OS Get localdatetime /value 2^>nul') do set datetime=%%I
if "%datetime%"=="" (
    :: 备用方案：使用date和time命令
    set "year=%date:~0,4%"
    set "month=%date:~5,2%"
    set "day=%date:~8,2%"
    set "hour=%time:~0,2%"
    set "minute=%time:~3,2%"
    set "second=%time:~6,2%"
) else (
    set "year=%datetime:~0,4%"
    set "month=%datetime:~4,2%"
    set "day=%datetime:~6,2%"
    set "hour=%datetime:~8,2%"
    set "minute=%datetime:~10,2%"
    set "second=%datetime:~12,2%"
)
set "timestamp=%year%%month%%day%_%hour%%minute%%second%"

:: 创建时间戳文件夹（在XML文件夹内）
set "timestamp_folder=%XML_PATH%\%timestamp%"
mkdir "!timestamp_folder!" 2>nul

if not exist "!timestamp_folder!" (
    echo 错误：创建时间戳文件夹失败
    exit /b 1
)

:: 复制所有 XML 文件到时间戳文件夹（原文件保留）
set "copied_count=0"
for %%f in ("%XML_PATH%\*.xml") do (
    copy "%%f" "!timestamp_folder!\" >nul
    if !errorlevel! equ 0 (
        set /a copied_count+=1
        echo 已复制：%%~nxf
    )
)

echo 已移动 !moved_count! 个文件到时间戳文件夹：%timestamp%

:: 步骤7：按日期整理到目标目录
echo [7/7] 按日期整理到目标目录...

:: 获取当前日期用于目标路径
set "target_date_path=%TARGET_BASE%\%year%\%month%\%day%"

echo 目标路径：%target_date_path%

:: 创建目标目录
mkdir "%target_date_path%" 2>nul

if not exist "%target_date_path%\" (
    echo 错误：创建目标目录失败
    exit /b 1
)

:: 移动时间戳文件夹到目标目录
echo 移动时间戳文件夹到目标目录...
move "!timestamp_folder!" "%target_date_path%\" >nul

if errorlevel 1 (
    echo 错误：移动文件夹失败
    exit /b 1
) else (
    echo 成功！文件已保存到：%target_date_path%\%timestamp%\
)

:: 最终统计
echo.
echo ========================================
echo           流程执行完成！
echo ========================================
echo.
echo [统计信息]
echo   下载文件数：!moved_count!
echo   时间戳文件夹：%timestamp%
echo   最终保存路径：%target_date_path%\%timestamp%\
echo.

:: ========== 新增：Git 自动推送 ==========
echo [额外步骤] 开始 Git 提交与推送...
cd /d "%XML_PATH%"
git add .
git commit -m "自动化提交 %date% %time%"
git push
if errorlevel 1 (
    echo 警告：Git 推送失败，请检查网络或仓库配置
) else (
    echo Git 推送成功！
)
echo ========================================

echo 程序将在10秒后自动关闭...
echo ========================================
timeout /t 10 /nobreak >nul

endlocal
exit /b 0