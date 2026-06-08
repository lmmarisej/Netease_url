FROM docker.m.daocloud.io/library/python:3.12-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    -r requirements.txt

COPY backend/ ./backend/
COPY config/ ./config/
COPY frontend/dist/ ./frontend/dist/

RUN mkdir -p /app/logs /app/downloads

ENV TZ=Asia/Shanghai
EXPOSE 5000
CMD ["python3", "backend/main.py"]
