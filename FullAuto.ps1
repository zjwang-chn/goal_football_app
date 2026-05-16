# 设置工作目录为脚本所在目录（即 xml 文件夹）
Set-Location -Path $PSScriptRoot

# 检查是否是 Git 仓库
if (-not (Test-Path ".git")) {
    Write-Host "错误：当前目录不是 Git 仓库！" -ForegroundColor Red
    exit 1
}

# 显示当前分支
$branch = git branch --show-current
if (-not $branch) {
    Write-Host "错误：无法获取当前分支" -ForegroundColor Red
    exit 1
}
Write-Host "当前分支: $branch" -ForegroundColor Cyan

# ========== 1. 拉取远程更新 ==========
Write-Host "`n[1/4] 正在拉取远程更新..." -ForegroundColor Yellow

# 暂存本地修改（包括未跟踪文件）
git stash push -u -m "Auto stash before pull" 2>&1 | Out-Null
$stashResult = $LASTEXITCODE

# 拉取并变基
git pull --rebase
if ($LASTEXITCODE -ne 0) {
    Write-Host "拉取失败，可能存在冲突！" -ForegroundColor Red
    if ($stashResult -eq 0) { git stash pop 2>&1 | Out-Null }
    exit 1
}

# 恢复暂存
if ($stashResult -eq 0) {
    git stash pop 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "警告：恢复本地修改时产生冲突，请手动处理。" -ForegroundColor Magenta
    }
}
Write-Host "拉取完成。" -ForegroundColor Green

# ========== 2. 执行数据处理 ==========
Write-Host "`n[2/4] 执行数据处理..." -ForegroundColor Yellow

# 调用原有的 DoTasks.ps1（在同一目录下）
& "$PSScriptRoot\DoTasks.ps1"
if ($LASTEXITCODE -ne 0) {
    Write-Host "数据处理失败，停止后续操作。" -ForegroundColor Red
    exit 1
}
Write-Host "数据处理完成。" -ForegroundColor Green

# ========== 3. 提交更改 ==========
Write-Host "`n[3/4] 提交更改到本地仓库..." -ForegroundColor Yellow

# 检查是否有更改
$status = git status --porcelain
if (-not $status) {
    Write-Host "没有需要提交的文件更改。" -ForegroundColor Gray
} else {
    Write-Host "待提交的文件：" -ForegroundColor Gray
    Write-Host $status
    git add -A
    if ($LASTEXITCODE -ne 0) { Write-Host "git add 失败"; exit 1 }

    $commitMsg = "Auto update: $(Get-Date -Format 'yyyyMMdd_HHmmss')"
    git commit -m $commitMsg
    if ($LASTEXITCODE -ne 0) { Write-Host "git commit 失败"; exit 1 }
    Write-Host "提交成功: $commitMsg" -ForegroundColor Green
}

# ========== 4. 推送到远程 ==========
Write-Host "`n[4/4] 推送到远程仓库..." -ForegroundColor Yellow
git push
if ($LASTEXITCODE -ne 0) {
    Write-Host "推送失败，请检查网络或权限。" -ForegroundColor Red
    exit 1
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "全部任务成功完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan