#!/bin/bash
set -e

echo ""
echo "╔══════════════════════════════════════╗"
echo "║   网易云音乐工具箱 - Docker 部署   ║"
echo "╚══════════════════════════════════════╝"
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# [1/3] 编译前端
echo "[1/3] 编译前端 Vue 应用..."
cd "$SCRIPT_DIR/frontend"
npm run build
cd "$SCRIPT_DIR"

# [2/3] 构建并启动 Docker
echo ""
echo "[2/3] 构建 Docker 镜像并启动..."
docker-compose up --build -d

# [3/3] 检查容器状态
echo ""
echo "[3/3] 检查容器状态..."
docker-compose ps

echo ""
echo "╔════════════════════════════════════════════╗"
echo "║  部署完成！访问 http://localhost:5000     ║"
echo "╚════════════════════════════════════════════╝"
echo ""
echo "常用命令:"
echo "  查看日志: docker-compose logs -f"
echo "  停止服务: docker-compose down"
echo "  重启服务: docker-compose restart"
echo ""
