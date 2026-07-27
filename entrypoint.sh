#!/bin/bash
set -e

# 容器运行时通过 npm 全局安装 Claude Code（超时 120 秒）
echo "==> Installing Claude Code via npm..."
if timeout 120 npm install -g @anthropic-ai/claude-code; then
    echo "==> Claude Code installed: $(claude --version 2>/dev/null || echo 'done')"
else
    echo "==> ERROR: Claude Code installation failed or timed out, skipping." >&2
fi

# 启动 FastAPI 应用
echo "==> Starting FastAPI server..."
exec uvicorn main:app --host 0.0.0.0 --port 8000
