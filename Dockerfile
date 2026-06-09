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

RUN mkdir -p /app/logs /app/downloads

ENV TZ=Asia/Shanghai
EXPOSE 5000
CMD ["python3", "backend/main.py"]
