# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在本仓库中工作时提供指引。

## 项目概述

LLM 定价仪表盘 — 一个用于展示和比较各大 AI 厂商模型定价的 Web 应用。价格从 OpenRouter API 实时获取，若获取失败则回退到 `pricing_data.py` 中的静态数据。

## 开发命令

```bash
# 安装依赖（建议使用 venv 虚拟环境）
cd backend && pip install -r requirements.txt

# 启动开发服务器（在 backend/ 目录下执行，需要先启动 PostgreSQL）
cd backend && uvicorn main:app --reload --port 8000

# 使用 Docker 运行（推荐，自动启动 PostgreSQL）
docker compose up --build

# 迁移现有 JSON 数据到 PostgreSQL（仅需执行一次）
docker compose exec app python migrate_json_to_pg.py /app/data/price_history.json
```

应用运行在 8000 端口。前端访问路径为 `/`，API 路径为 `/api/*`。

## 架构

**后端**（FastAPI，Python 3.12）：
- `backend/main.py` — FastAPI 应用，使用 lifespan 管理生命周期。API 端点：`GET /api/prices`（获取价格）、`GET /api/status`（获取状态）、`POST /api/refresh`（手动刷新）、`GET /api/export`（下载 Excel）、`GET /api/history`（查询历史）、`GET /api/history/{slug}`（按 slug 查询历史）。将 `frontend/` 挂载为 `/static`，并将 `index.html` 作为兜底路由。
- `backend/pricing_data.py` — 内存中的定价数据存储。包含静态兜底数据（`PRICING_DATA`）和由抓取器更新的可变状态（`_live_data`）。历史价格数据通过 `database.py` 存储在 PostgreSQL 中。
- `backend/database.py` — PostgreSQL 数据库模块（使用 asyncpg）。管理连接池、批量插入历史数据、查询历史、定期清理过期数据（7 天保留窗口）。
- `backend/price_fetcher.py` — 异步抓取器，从 OpenRouter（`/api/v1/models`）拉取模型数据，通过 `PROVIDER_MAP` 过滤已知厂商，并将价格归一化为 $/1M tokens。
- `backend/csv_exporter.py` — 每日 CSV 快照导出器。每天 00:05 自动导出当日价格到 `data/` ��录，并清理 7 天前的旧文件。

**前端**（原生 HTML/CSS/JS，无构建步骤）：
- `frontend/index.html`、`frontend/script.js`、`frontend/style.css` — 主页面，调用 `/api/prices` 渲染可排序、可筛选的价格表格。刷新按钮触发 `/api/refresh` 后自动下载 Excel 文件。
- `frontend/history.html`、`frontend/history.js` — 历史价格页面，使用 Chart.js 绘制价格趋势折线图。支持通过 slug 路径或查询参数访问。

**定时任务**：APScheduler 每日中国时间 09:00–22:00 每小时刷新价格。首次抓取在应用启动时执行。每日 00:05 导出 CSV 快照。每日 UTC 03:00 清理过期历史数据。刷新日志 `refresh.log` 中通过 `[SCHEDULED]`、`[MANUAL]`、`[STARTUP]` 标签区分触发来源。

**数据库**：PostgreSQL 16，通过 docker-compose 部署。仅存储价格历史数据（`price_history` 表），7 天保留窗口。当前价格保存在内存中用于快速读取。连接字符串通过 `DATABASE_URL` 环境变量配置。

**部署**：Dockerfile 将 `backend/` 复制到 `/app`，`frontend/` 复制到 `/app/static/`。`docker-compose.yml` 包含 PostgreSQL 服务和应用服务，暴露 8000 端口，使用命名卷挂载 `/app/data`（CSV/日志）和 `pgdata`（数据库）。

## 关键细节

- 项目无测试套件。
- 价格历史存储在 PostgreSQL 数据库中（`price_history` 表），当前价格保存在 `pricing_data.py` 的模块级全局变量中。
- 根目录的 `index.html` 与本项目无关（似乎是一个缓存的 Google 页面）。
- 支持的厂商：OpenAI、Anthropic、Google、DeepSeek、Mistral、Meta。
- 刷新日志写入 `data/refresh.log`，失败时会额外生成错误日志文件。
