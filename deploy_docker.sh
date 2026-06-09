#!/bin/bash
set -e

echo ""
echo "╔══════════════════════════════════════╗"
echo "║   网易云音乐工具箱 - Docker 部署   ║"
echo "╚══════════════════════════════════════╝"
echo ""

# [1/2] 构建并启动 Docker（含前端编译）
echo "[1/2] 构建 Docker 镜像并启动..."
docker-compose up --build -d

# [2/2] 检查容器状态
echo ""
echo "[2/2] 检查容器状态..."
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
