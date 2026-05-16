# 任务1：移动 HisData 下的子文件夹（不移动文件）
$srcHisData = "C:\Users\52483\Desktop\R.9\xml\HisData"
$destData   = "C:\Users\52483\Desktop\R.9\DATA\20990909_235959"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "任务1：移动 HisData 下的子文件夹" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

if (-not (Test-Path $srcHisData)) {
    Write-Host "错误：源文件夹不存在 - $srcHisData" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $destData)) {
    New-Item -ItemType Directory -Path $destData -Force | Out-Null
    Write-Host "已创建目标文件夹：$destData" -ForegroundColor Green
}

$folders = Get-ChildItem -Path $srcHisData -Directory
if ($folders.Count -eq 0) {
    Write-Host "源文件夹下没有子文件夹，无需移动" -ForegroundColor Yellow
} else {
    foreach ($f in $folders) {
        $destSub = Join-Path $destData $f.Name
        if (Test-Path $destSub) {
            Write-Host "跳过（目标已存在）：$($f.Name)" -ForegroundColor Yellow
        } else {
            Move-Item -Path $f.FullName -Destination $destData -Force
            Write-Host "已移动：$($f.Name)" -ForegroundColor Green
        }
    }
}

Write-Host "`n任务1完成" -ForegroundColor Cyan

# 任务2：删除 data 下三天前的 .json 文件
$dataFolder = "C:\Users\52483\Desktop\R.9\xml\data"

Write-Host "`n==========================================" -ForegroundColor Cyan
Write-Host "任务2：删除 data 文件夹中三天前的 .json 文件" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

if (-not (Test-Path $dataFolder)) {
    Write-Host "错误：data 文件夹不存在 - $dataFolder" -ForegroundColor Red
    exit 1
}

$limitDate = (Get-Date).AddDays(-3).ToString("yyyyMMdd")
Write-Host "当前日期：$(Get-Date -Format 'yyyy-MM-dd')" -ForegroundColor Gray
Write-Host "三天前日期边界：$limitDate（文件日期 < 此值则删除）" -ForegroundColor Yellow

$jsonFiles = Get-ChildItem -Path $dataFolder -Filter "*.json"
if ($jsonFiles.Count -eq 0) {
    Write-Host "data 文件夹下没有 .json 文件" -ForegroundColor Yellow
} else {
    foreach ($file in $jsonFiles) {
        $name = $file.BaseName
        if ($name -match '(\d{8})') {
            $fileDate = $matches[1]
            if ($fileDate -lt $limitDate) {
                Remove-Item -Path $file.FullName -Force
                Write-Host "已删除：$($file.Name)  (日期 $fileDate < $limitDate)" -ForegroundColor Red
            } else {
                Write-Host "保留：$($file.Name)  (日期 $fileDate >= $limitDate)" -ForegroundColor Green
            }
        } else {
            Write-Host "跳过（无8位日期）：$($file.Name)" -ForegroundColor Gray
        }
    }
}

Write-Host "`n任务2完成" -ForegroundColor Cyan
Write-Host "=========================================="