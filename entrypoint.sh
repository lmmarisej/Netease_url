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

# 3. 启动后端主程序
exec python3 backend/main.py