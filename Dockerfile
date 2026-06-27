# ============ 阶段1：编译前端 ============
FROM node:20-alpine AS frontend-builder
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# ============ 阶段2：运行后端 ============
FROM python:3.12-slim
WORKDIR /app

# 1. 优先安装依赖（利用缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2. 预装 wget（供 entrypoint 下载 PANNs 模型使用）
RUN apt-get update && apt-get install -y --no-install-recommends wget && \
    rm -rf /var/lib/apt/lists/*

# 3. 复制后端代码、下载脚本并备份默认配置
COPY backend/ ./backend/
COPY config/ ./config/
COPY download_models.py .

RUN cp -r /app/config /app/config_defaults && \
    mkdir -p /app/logs /app/downloads

# 4. 复制前端静态文件
COPY --from=frontend-builder /frontend/dist/ ./frontend/dist/

# 5. 复制启动脚本
COPY entrypoint.sh /entrypoint.sh

# 赋权并加一道防线：万一你以后不小心又把 entrypoint.sh 变成了 CRLF，这行命令会自动修复它
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

ENV TZ=Asia/Shanghai
ENV PYTHONUNBUFFERED=1
EXPOSE 5000
ENTRYPOINT ["/entrypoint.sh"]