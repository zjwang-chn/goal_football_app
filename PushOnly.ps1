# PushOnly.ps1 - 仅推送本地提交到远程（自动添加所有更改并生成提交信息）
Set-Location -Path $PSScriptRoot

# 检查是否有更改
$status = git status --porcelain
if (-not $status) {
    Write-Host "没有需要提交的文件更改。" -ForegroundColor Gray
    exit 0
}

Write-Host "待提交的文件：" -ForegroundColor Cyan
Write-Host $status

# 添加所有更改
git add -A
if ($LASTEXITCODE -ne 0) {
    Write-Host "git add 失败" -ForegroundColor Red
    exit 1
}

# 自动生成提交信息
$commitMsg = "Manual push: $(Get-Date -Format 'yyyyMMdd_HHmmss')"
git commit -m $commitMsg
if ($LASTEXITCODE -ne 0) {
    Write-Host "git commit 失败" -ForegroundColor Red
    exit 1
}

# 推送
git push
if ($LASTEXITCODE -ne 0) {
    Write-Host "推送失败，请检查网络或权限。" -ForegroundColor Red
    exit 1
}

Write-Host "推送成功！提交信息：$commitMsg" -ForegroundColor Green