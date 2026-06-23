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

# 3. 检查并下载 PANNs 模型（用 volume 持久化，仅首次下载）
PANNS_DIR="/root/panns_data"
PANNS_MODEL="$PANNS_DIR/Cnn14_mAP=0.431.pth"
if [ ! -f "$PANNS_MODEL" ] || [ "$(stat -c%s "$PANNS_MODEL" 2>/dev/null || echo 0)" -lt 300000000 ]; then
  echo "[entrypoint] PANNs 模型未找到或不完整，开始下载 (~430MB)..."
  python3 /app/download_panns.py
  echo "[entrypoint] PANNs 模型下载完成"
else
  echo "[entrypoint] PANNs 模型已存在，跳过下载"
fi

# 4. 启动后端主程序
exec python3 backend/main.py