#!/bin/bash
set -e

echo ""
echo "╔══════════════════════════════════════╗"
echo "║   网易云音乐工具箱 - 更新部署      ║"
echo "╚══════════════════════════════════════╝"
echo ""

# [1/4] 暂存本地配置变更
echo "[1/4] 备份本地配置..."
if [ -f "config/users/admin/push_config.json" ]; then
    cp config/users/admin/push_config.json config/users/admin/push_config.json.bak
fi
if [ -f "config/users/admin/cookies.json" ]; then
    cp config/users/admin/cookies.json config/users/admin/cookies.json.bak
fi

# [2/4] 拉取最新代码
echo "[2/4] 拉取最新代码..."
git stash push -m "auto-stash-before-update" 2>/dev/null || true
git pull origin main
git stash pop 2>/dev/null || true

# [3/4] 恢复本地配置
echo "[3/4] 恢复本地配置..."
[ -f "config/users/admin/push_config.json.bak" ] && cp config/users/admin/push_config.json.bak config/users/admin/push_config.json
[ -f "config/users/admin/cookies.json.bak" ] && cp config/users/admin/cookies.json.bak config/users/admin/cookies.json

# [4/4] 重建并启动容器
echo "[4/4] 重建 Docker 容器..."
docker compose down
docker compose up --build -d

echo ""
echo "╔════════════════════════════════════════════╗"
echo "║  更新完成！访问 http://localhost:5000    ║"
echo "╚════════════════════════════════════════════╝"
