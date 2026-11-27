# 容器化部署配置（本环境无 Docker，未构建验证；装好 Docker 后按 README 命令构建）
# 分层：先 COPY requirements 安装依赖，代码改动不会触发依赖重装（构建缓存优化）
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
