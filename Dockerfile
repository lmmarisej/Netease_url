# ============ 阶段1：编译前端 ============
FROM docker.m.daocloud.io/library/node:20-alpine AS frontend-builder
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ============ 阶段2：运行后端 ============
FROM docker.m.daocloud.io/library/python:3.12-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    -r requirements.txt

COPY backend/ ./backend/
COPY config/ ./config/
COPY --from=frontend-builder /frontend/dist/ ./frontend/dist/

# 备份默认配置（供 volume 挂载后首次启动使用）
RUN cp -r /app/config /app/config_defaults

RUN mkdir -p /app/logs /app/downloads

# 启动脚本：如果挂载的 config 目录为空，则从默认配置恢复
RUN printf '#!/bin/bash\n\
for f in /app/config_defaults/*.json; do\n\
  name=$(basename "$f")\n\
  if [ ! -f "/app/config/$name" ]; then\n\
    cp "$f" "/app/config/$name"\n\
  fi\n\
done\n\
if [ ! -d "/app/config/users" ]; then\n\
  cp -r /app/config_defaults/users /app/config/users 2>/dev/null || true\n\
fi\n\
exec python3 backend/main.py\n\
' > /entrypoint.sh && chmod +x /entrypoint.sh

ENV TZ=Asia/Shanghai
EXPOSE 5000
CMD ["/entrypoint.sh"]
