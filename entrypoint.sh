#!/bin/sh

# 1. 如果挂载的 config 目录为空，则从默认配置恢复 json 文件
for f in /app/config_defaults/*.json; do
  name=$(basename "$f")
  if [ ! -f "/app/config/$name" ]; then
    cp "$f" "/app/config/$name"
  fi
done

# 2. 恢复 users 目录
if [ ! -d "/app/config/users" ]; then
  cp -r /app/config_defaults/users /app/config/users 2>/dev/null || true
fi

# 3. 检查并下载模型（用 volume 持久化，仅首次下载）
echo "[entrypoint] 检查模型文件..."
python3 /app/download_models.py
echo "[entrypoint] 模型检查完成"

# 4. 启动后端主程序
exec python3 backend/main.py