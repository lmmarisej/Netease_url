FROM docker.m.daocloud.io/library/python:3.12-slim
WORKDIR /app

# 安装依赖（使用阿里云镜像加速）
COPY requirements.txt .
RUN pip install --no-cache-dir \
    -i https://mirrors.aliyun.com/pypi/simple/ \
    -r requirements.txt

# 复制项目文件
COPY main.py entrypoint.sh ./
COPY code/ ./code/
COPY config/ ./config/
COPY templates/ ./templates/

# 创建运行时目录
RUN chmod +x /app/entrypoint.sh && \
    mkdir -p /app/logs /app/downloads

ENV TZ=Asia/Shanghai
EXPOSE 5000
CMD ["/app/entrypoint.sh"]
