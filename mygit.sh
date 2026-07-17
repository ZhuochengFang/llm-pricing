#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "用法: $0 <github_owner/github_repo>"
  echo "示例: $0 ZhuochengFang/llm-pricing"
  exit 1
fi

REPO_PATH="$1"
REMOTE_URL="git@github.com:${REPO_PATH}.git"

if [[ "$REPO_PATH" != */* ]]; then
  echo "参数格式错误：请使用 owner/repo 格式。"
  exit 1
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git init
  echo "已初始化本地 Git 仓库。"
else
  echo "当前目录已是 Git 仓库，跳过 git init。"
fi

if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "$REMOTE_URL"
  echo "已更新 origin -> $REMOTE_URL"
else
  git remote add origin "$REMOTE_URL"
  echo "已添加 origin -> $REMOTE_URL"
fi

git branch -M main
echo "已将默认分支设置为 main。"
echo "完成。可使用以下命令推送："
echo "git add . && git commit -m 'init' && git push -u origin main"