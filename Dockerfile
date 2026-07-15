# Dockerfile for LLM Pricing Dashboard
# 使用 Ubuntu 22.04 作为基础镜像，同时支持 FastAPI 后端和 Claude Code
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# 1. 安装系统基础依赖 + Python 3 + pip
RUN apt-get update && apt-get install -y \
    curl \
    git \
    jq \
    python3 \
    python3-pip \
    ca-certificates \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# 2. 使用 NodeSource 安装 Node.js 20（自带 npm）
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# 3. 验证 node / npm / python
RUN node -v && npm -v && python3 --version

# 4. 安装 Python 依赖
WORKDIR /app
COPY backend/requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# 5. 复制应用代码
COPY backend/ .
COPY frontend/ /app/static/

# 6. 创建数据目录
RUN mkdir -p /app/data
ENV PRICE_DB_PATH=/app/data/daily_prices.db

# 7. 复制启动脚本
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
