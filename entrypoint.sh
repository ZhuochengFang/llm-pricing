#!/bin/bash
set -e

# 容器运行时通过 npm 全局安装 Claude Code
echo "==> Installing Claude Code via npm..."
npm install -g @anthropic-ai/claude-code
echo "==> Claude Code installed: $(claude --version 2>/dev/null || echo 'done')"

# 启动 FastAPI 应用
echo "==> Starting FastAPI server..."
exec uvicorn main:app --host 0.0.0.0 --port 8000
