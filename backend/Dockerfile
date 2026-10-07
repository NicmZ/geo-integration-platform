# GEO Integration Platform 后端镜像
FROM python:3.11-slim

WORKDIR /app

# 超算/离线环境可用私有源：pip install -i https://pypi.tuna.tsinghua.edu.cn/simple
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY run.py .

EXPOSE 8001
ENV EXECUTOR=local
# Render/Railway 等平台会注入 PORT 环境变量，默认 8001
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8001}"]
