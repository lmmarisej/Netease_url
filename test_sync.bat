@echo off
chcp 65001 >nul
echo ========================================
echo   Netease Music Sync - Local Test
echo ========================================
echo.

echo [Step 1] Upgrade pip...
python -m pip install --upgrade pip
echo.

echo [Step 2] Install dependencies (using Tsinghua mirror)...
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 (
    echo.
    echo ERROR: Failed to install dependencies!
    echo Please check your network connection or install manually.
    pause
    exit /b 1
)
echo.

echo [Step 3] Check required files...
if not exist "cookie.txt" (
    echo WARNING: cookie.txt not found
    echo Please run qr_login.py to login with QR code
    echo.
)

if not exist "playlist_sync.py" (
    echo ERROR: playlist_sync.py not found
    pause
    exit /b 1
)

echo All files check passed
echo.

echo [Step 4] Configure test environment...
echo Please edit .env file and set:
echo   - ENABLE_SYNC=true
echo   - PLAYLIST_IDS=your_playlist_id
echo   - COOKIE in cookie.txt
echo.
pause

echo.
echo [Step 5] Start service for testing...
echo Press Ctrl+C to stop
echo.
python main.py
