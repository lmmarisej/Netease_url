@echo off
echo ========================================
echo   Netease Music Sync - Setup Wizard
echo ========================================
echo.

if not exist "cookie.txt" (
    echo [1/3] Cookie Setup
    echo Please login first:
    echo   1. QR Code Login
    echo   2. Skip
    echo.
    set /p choice="Choice (1 or 2): "
    
    if "%choice%"=="1" (
        python qr_login.py
    )
) else (
    echo [1/3] Cookie file found
)

echo.
echo [2/3] Playlist ID
echo Example: https://music.163.com/#/playlist?id=1234567890
echo.
set /p pid="Enter playlist ID: "

if "%pid%"=="" (
    echo Error: ID cannot be empty!
    pause
    exit /b 1
)

echo.
echo [3/3] Sync Interval
echo   1. 60 seconds (test)
echo   2. 5 minutes
echo   3. 1 hour
echo.
set /p interval="Choice (1-3): "

if "%interval%"=="1" (
    set sec=60
) else if "%interval%"=="2" (
    set sec=300
) else (
    set sec=3600
)

echo.
echo Applying config...

powershell -Command "(Get-Content .env) -replace 'PLAYLIST_IDS=.*', 'PLAYLIST_IDS=%pid%' | Set-Content .env"
powershell -Command "(Get-Content .env) -replace 'SYNC_INTERVAL=.*', 'SYNC_INTERVAL=%sec%' | Set-Content .env"
powershell -Command "(Get-Content .env) -replace 'DOWNLOADS_DIR=.*', 'DOWNLOADS_DIR=downloads' | Set-Content .env"

echo.
echo ========================================
echo   Done!
echo ========================================
echo.
echo Playlist: %pid%
echo Interval: %sec% seconds
echo.
echo Start service:
echo   python main.py
echo.
pause
