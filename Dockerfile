# Dockerfile for LLM Pricing Dashboard
# 使用 Ubuntu 22.04 作为基础镜像，同时支持 FastAPI 后端和 Claude Code
FROM docker.io/library/ubuntu:22.04

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
    xz-utils \
    && rm -rf /var/lib/apt/lists/*

# 2. 安装 Node.js 20
RUN curl -fsSL https://nodejs.org/dist/v20.18.0/node-v20.18.0-linux-x64.tar.xz \
    | tar -xJ -C /usr/local --strip-components=1 \
    && node -v && npm -v

# 3. 验证 python
RUN python3 --version

# 4. 安装 Python 依赖
WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# 5. 复制应用代码
COPY CLAUDE.md /app/CLAUDE.md
COPY check.md /app/check.md
COPY backend/ .
COPY frontend/ /app/static/

# 6. 创建数据目录和日志目录
RUN mkdir -p /app/backend/data /app/backend/logs
ENV PRICE_DB_PATH=/app/backend/data/daily_prices.db

# 7. 复制启动脚本
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# 8. 设置claude
RUN mkdir -p /root/.claude
COPY .claude/settings.json /root/.claude/settings.json
EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
