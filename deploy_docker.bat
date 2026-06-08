@echo off
chcp 65001 >nul
echo.
echo ╔══════════════════════════════════════╗
echo ║   网易云音乐工具箱 - Docker 部署   ║
echo ╚══════════════════════════════════════╝
echo.

echo [1/3] 编译前端 Vue 应用...
cd /d "%~dp0frontend"
call npm run build
if %ERRORLEVEL% NEQ 0 (
    echo [错误] 前端编译失败！
    pause
    exit /b 1
)
cd /d "%~dp0"

echo.
echo [2/3] 构建 Docker 镜像并启动...
docker-compose up --build -d
if %ERRORLEVEL% NEQ 0 (
    echo [错误] Docker 部署失败！
    pause
    exit /b 1
)

echo.
echo [3/3] 检查容器状态...
docker-compose ps

echo.
echo ╔══════════════════════════════════════╗
echo ║   部署完成！访问 http://localhost:5000   ║
echo ╚══════════════════════════════════════╝
echo.
echo 常用命令:
echo   查看日志: docker-compose logs -f
echo   停止服务: docker-compose down
echo   重启服务: docker-compose restart
echo.
