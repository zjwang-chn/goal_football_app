# PullOnly.ps1 - 仅拉取远程更新，不提交任何本地更改
Set-Location -Path $PSScriptRoot

Write-Host "正在拉取远程更新..." -ForegroundColor Cyan

# 暂存本地修改（避免拉取冲突）
git stash push -u -m "auto stash before pull" 2>&1 | Out-Null
$stashed = $LASTEXITCODE -eq 0

# 拉取并变基
git pull --rebase
if ($LASTEXITCODE -ne 0) {
    Write-Host "拉取失败，请检查网络或手动处理冲突。" -ForegroundColor Red
    if ($stashed) { git stash pop 2>&1 | Out-Null }
    exit 1
}

# 恢复暂存
if ($stashed) {
    git stash pop 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "警告：恢复本地修改时产生冲突，请手动处理。" -ForegroundColor Yellow
    }
}

Write-Host "拉取成功！" -ForegroundColor Green