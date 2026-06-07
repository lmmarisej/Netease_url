# 网易云音乐定时同步 - 配置向导
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  网易云音乐定时同步 - 快速配置" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查Cookie
if (-not (Test-Path "cookie.txt")) {
    Write-Host "[1/3] Cookie配置" -ForegroundColor Yellow
    Write-Host "需要先登录网易云音乐" -ForegroundColor White
    Write-Host "  1. 二维码登录（推荐）" -ForegroundColor White
    Write-Host "  2. 跳过" -ForegroundColor White
    Write-Host ""
    $choice = Read-Host "请选择 (1 或 2)"
    
    if ($choice -eq "1") {
        Write-Host ""
        Write-Host "正在启动二维码登录..." -ForegroundColor Green
        python qr_login.py
    }
} else {
    Write-Host "[1/3] 发现Cookie文件" -ForegroundColor Green
}

Write-Host ""
Write-Host "[2/3] 歌单ID配置" -ForegroundColor Yellow
Write-Host "从URL获取ID: https://music.163.com/#/playlist?id=你的ID" -ForegroundColor White
Write-Host "多个ID用逗号分隔: 123,456,789" -ForegroundColor White
Write-Host ""
$playlistId = Read-Host "请输入歌单ID"

if ([string]::IsNullOrWhiteSpace($playlistId)) {
    Write-Host "错误: 歌单ID不能为空！" -ForegroundColor Red
    pause
    exit 1
}

Write-Host ""
Write-Host "[3/3] 同步间隔配置" -ForegroundColor Yellow
Write-Host "  1. 每60秒（测试用）" -ForegroundColor White
Write-Host "  2. 每5分钟" -ForegroundColor White
Write-Host "  3. 每小时" -ForegroundColor White
Write-Host ""
$intervalChoice = Read-Host "请选择 (1-3)"

if ($intervalChoice -eq "1") {
    $syncInterval = 60
} elseif ($intervalChoice -eq "2") {
    $syncInterval = 300
} else {
    $syncInterval = 3600
}

Write-Host ""
Write-Host "正在应用配置..." -ForegroundColor Green

# 更新.env文件
$envContent = Get-Content .env -Encoding UTF8
$envContent = $envContent -replace 'PLAYLIST_IDS=.*', "PLAYLIST_IDS=$playlistId"
$envContent = $envContent -replace 'SYNC_INTERVAL=.*', "SYNC_INTERVAL=$syncInterval"
$envContent = $envContent -replace 'DOWNLOADS_DIR=.*', 'DOWNLOADS_DIR=downloads'
$envContent | Set-Content .env -Encoding UTF8

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  配置完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "当前设置:" -ForegroundColor White
Write-Host "  - 歌单ID: $playlistId" -ForegroundColor White
Write-Host "  - 同步间隔: $syncInterval 秒" -ForegroundColor White
Write-Host "  - 下载目录: downloads" -ForegroundColor White
Write-Host ""
Write-Host "现在可以启动服务:" -ForegroundColor Green
Write-Host "  python main.py" -ForegroundColor Yellow
Write-Host ""
pause
