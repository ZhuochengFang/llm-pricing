# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在本仓库中工作时提供指引。

## 项目概述

LLM 定价仪表盘 — 一个用于展示和比较各大 AI 厂商模型定价的 Web 应用。价格从 OpenRouter API 和云雾 AI 平台实时获取，若获取失败则回退到 `pricing_data.py` 中的静态数据。支持多平台价格对比、价格历史趋势图、Excel/CSV 导出。

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

## 项目文件结构

```
llm-pricing/
├── Dockerfile                 # Docker 镜像构建文件
├── docker-compose.yml         # 编排文件：应用服务 + PostgreSQL 数据库
├── entrypoint.sh              # 容器入口脚本：安装 Claude Code 后启动 uvicorn
├── CLAUDE.md                  # 本文件：项目指引文档
├── check.md                   # 运维检查清单与改进备忘
├── index.html                 # （无关文件，非项目代码）
│
├── backend/                   # 后端代码（FastAPI + Python 3.12）
│   ├── main.py                # 应用入口：API 路由、生命周期管理、定时任务调度
│   ├── pricing_data.py        # 内存数据存储：合并多平台数据、排序、slug 生成、历史查询
│   ├── price_fetcher.py       # OpenRouter 价格抓取器：拉取 API 数据并归一化为 $/1M tokens
│   ├── yunwu_fetcher.py       # 云雾 AI 价格抓取器：拉取云雾 API 并换算 model_ratio 为价格
│   ├── model_matcher.py       # 跨平台模型名匹配：将不同平台的同一模型归一化到规范名称
│   ├── database.py            # PostgreSQL 数据库模块：连接池、建表、批量写入、查询、清理
│   ├── csv_exporter.py        # 每日 CSV 快照导出器：定时导出并清理过期文件
│   ├── migrate_json_to_pg.py  # 一次性迁移脚本：将 JSON 历史数据导入 PostgreSQL
│   ├── requirements.txt       # Python 依赖清单
│   └── data/                  # 运行时数据目录（Docker 卷挂载）
│       ├── refresh.log        # 刷新日志（自动生成）
│       └── llm_prices_*.csv   # 每日价格快照（自动生成）
│
├── frontend/                  # 前端代码（原生 HTML/CSS/JS，无构建步骤）
│   ├── index.html             # 主页：定价表格，支持搜索、筛选、排序
│   ├── script.js              # 主页逻辑：加载数据、渲染表格、处理筛选排序和刷新
│   ├── style.css              # 全局样式：暗色主题、供应商/平台徽章颜色、响应式布局
│   ├── history.html           # 历史价格页面：Chart.js 折线图容器
│   └── history.js             # 历史页逻辑：加载历史 API 数据并绘制多平台趋势图
│
└── test_script/               # 早期原型脚本（未使用，与主项目无关）
    ├── monitor.py             # 独立价格监控原型（使用 SQLite + aiohttp）
    └── website.py             # 独立 Flask 仪表盘原型（读取 monitor.py 的数据库）
```

## 各文件详细说明

### 基础设施

| 文件 | 说明 |
|------|------|
| `Dockerfile` | 基于 Ubuntu 22.04 构建镜像，安装 Python 3 和 Node.js 20，复制后端到 `/app`、前端到 `/app/static/`，暴露 8000 端口 |
| `docker-compose.yml` | 定义两个服务：`db`（PostgreSQL 16）和 `app`（应用）。使用命名卷 `price-data`（挂载 `/app/data`）和 `pgdata`（数据库持久化）。开发时 bind-mount `./backend` 和 `./frontend` 实现热更新 |
| `entrypoint.sh` | 容器入口：安装 Claude Code（npm），然后 `exec uvicorn main:app --host 0.0.0.0 --port 8000` |

### 后端模块

| 文件 | 说明 |
|------|------|
| `main.py` | FastAPI 应用入口。**API 路由**：`GET /api/prices`（价格列表）、`GET /api/status`（状态）、`POST /api/refresh`（手动刷新）、`GET /api/export`（Excel 下载）、`GET /api/history`（按参数查历史）、`GET /api/history/{slug}`（按 slug 查历史）。**生命周期**：启动时初始化数据库连接池、执行首次价格抓取；关闭时释放资源。**定时任务**：每日 CST 09:00–22:00 每小时刷新价格、00:05 导出 CSV、UTC 03:00 清理过期历史。将 `frontend/` 挂载为 `/static`，`index.html` 作为兜底路由 |
| `pricing_data.py` | 内存数据存储中心。维护静态兜底数据 `PRICING_DATA`（22 个模型）和来自 OpenRouter / 云雾的实时数据。**核心功能**：`get_prices()` 合并多平台数据并按供应商→模型系列→版本号→变体→平台排序；通过 `_build_slug_index()` 为每个模型生成 URL slug；通过 `model_matcher` 实现跨平台别名映射；`get_history()` / `get_history_by_slug()` 查询历史数据时自动合并所有别名 |
| `price_fetcher.py` | OpenRouter 抓取器。从 `openrouter.ai/api/v1/models` 拉取数据，通过 `PROVIDER_MAP`（7 个供应商前缀）过滤已知厂商，跳过免费/nitro/floor 变体（含 `:` 的模型名），将 per-token 价格换算为 $/1M tokens |
| `yunwu_fetcher.py` | 云雾 AI 抓取器。从 `yunwu.ai/api/pricing` 拉取数据，用正则 `PROVIDER_PATTERNS` 从模型名识别供应商。价格换算逻辑：`quota_type=0` 时使用 `model_ratio × BASE_RATE_PER_MILLION`（one-api 体系，ratio=1 ≈ $2/1M tokens）；`quota_type≠0` 时直接使用 `model_price` |
| `model_matcher.py` | 跨平台模型名匹配。`MANUAL_ALIASES` 手动映射已知差异（如 `deepseek-reasoner` → `deepseek-r1`）。`normalize_model_name()` 自动处理：去除日期后缀、统一数字分隔符（`3-5` → `3.5`）、移除 `-instruct` 等变体标记。`build_alias_map()` 将两个平台的模型按规范名分组，为同时出现在两个平台的模型建立双向映射 |
| `database.py` | PostgreSQL 模块（asyncpg）。管理连接池（2-10 连接），自动创建 `price_history` 表（字段：platform、provider、model、input_price、output_price、recorded_at）及两个索引。`insert_history_batch()` 使用 COPY 协议批量写入。`query_history()` 查询最近 7 天数据（最多 1008 点）。`cleanup_old_history()` 删除过期记录 |
| `csv_exporter.py` | 每日导出 `llm_prices_YYYY-MM-DD.csv` 到 `data/` 目录（已存在则跳过），并清理 7 天前的旧文件 |
| `migrate_json_to_pg.py` | 一次性迁移脚本。将旧版 JSON 格式历史数据（`price_history.json`，键格式 `platform\|provider\|model` 或 `provider\|model`）导入 PostgreSQL。使用 COPY 协议批量插入 |

### 前端页面

| 文件 | 说明 |
|------|------|
| `index.html` | 主页结构：标题栏（含 Refresh 按钮）、搜索框、平台/供应商筛选按钮区、可排序的定价表格（列：平台、供应商、模型、输入价格、输出价格、上下文窗口）|
| `script.js` | 主页逻辑。从 `/api/prices` 加载数据，渲染可排序/可筛选的表格。默认使用后端排序（供应商→模型→版本→平台），点击列头可按该列排序（升序→降序→恢复默认）。点击行跳转到 `/{slug}` 历史页面。Refresh 按钮触发 `/api/refresh` 后自动下载 Excel。每 10 分钟自动刷新 |
| `style.css` | 暗色主题样式。供应商徽章颜色（OpenAI 绿、Anthropic 琥珀、DeepSeek 靛蓝、Google 蓝、Mistral 橙、Meta 蓝、Qwen 紫）。平台徽章（OpenRouter 紫、Yunwu 天蓝）。数据来源标记（live 绿、static 灰）。响应式断点 600px |
| `history.html` | 历史页结构：返回链接、标题、Chart.js canvas 容器、状态栏。从 CDN 加载 Chart.js 4.4.1 |
| `history.js` | 历史页逻辑。通过 URL slug 或查询参数确定模型，从 `/api/history` 加载数据。使用 Chart.js 绘制多平台折线图（OpenRouter 蓝/橙实线，Yunwu 绿/粉虚线），Y 轴格式 `$X.XX`。每 10 分钟自动刷新 |

## 关键细节

- 项目无测试套件
- 当前价格保存在 `pricing_data.py` 的模块级全局变量中，用于快速读取
- 价格历史存储在 PostgreSQL 的 `price_history` 表中，7 天保留窗口
- 根目录的 `index.html` 与本项目无关（似乎是一个缓存的 Google 页面）
- 支持的供应商：OpenAI、Anthropic、Google、DeepSeek、Mistral、Meta、Qwen
- 支持的平台：OpenRouter、云雾 AI (Yunwu)
- 刷新日志写入 `data/refresh.log`，通过 `[SCHEDULED]`、`[MANUAL]`、`[STARTUP]` 标签区分触发来源
- 模型排序规则：供应商（固定顺序）→ 模型系列名称 → 版本号（升序）→ 变体名 → 平台（OpenRouter 优先）
- 前端默认保持后端排序，用户可点击列头切换排序方式

## 已知问题与排查记录

### 云雾 AI (yunwu.ai) 连接失败（2026-07-30 发现）

**现象：** Docker 容器内 `yunwu_fetcher` 无法连接 yunwu.ai，错误为 `All connection attempts failed`（TCP 连接超时）。OpenRouter 不受影响。

**根因分析：**
- yunwu.ai 的 IP（`107.181.166.244`）从主机直连也超时（`curl --noproxy '*'` 确认），需要走代理才能访问
- 主机上 mihomo 代理（`127.0.0.1:7890`）可正常代理访问 yunwu.ai
- Docker 容器内没有代理环境变量，且代理仅监听 `127.0.0.1`，容器无法访问
- openrouter.ai 可直连，不受此影响

**如需修复，有以下方案：**

1. **方案 A：docker-compose.yml 添加代理**（推荐）
   - 将 mihomo 的 `bind-address` 改为 `0.0.0.0`（允许 Docker 网络访问）
   - 在 `docker-compose.yml` 的 `app.environment` 中添加：
     ```
     HTTPS_PROXY: "http://host.docker.internal:7890"
     HTTP_PROXY: "http://host.docker.internal:7890"
     NO_PROXY: "localhost,127.0.0.1,db"
     ```

2. **方案 B：使用 `network_mode: host`**
   - app 容器使用主机网络，直接访问 `localhost:7890` 代理
   - 需要同时：将 `DATABASE_URL` 改为 `localhost`、给 db 服务添加 `ports: "5432:5432"`
   - 缺点：失去 Docker 网络隔离

3. **方案 C：等待恢复**
   - 可能是 yunwu.ai 临时的网络/DNS 变更，过一阵可能恢复直连

   **最终采用了方案A进行修复，在docker容器环境下，主机需要开启代理**

**诊断命令备忘：**
```bash
# 从容器内测试连接
docker compose exec app bash -c "curl -v --connect-timeout 10 https://yunwu.ai/api/pricing 2>&1 | head -20"

# 从主机测试直连（不走代理）
curl --noproxy '*' --connect-timeout 10 -sI https://yunwu.ai/api/pricing

# 查看代理监听地址
ss -tlnp | grep ':7890'

# 查看容器内是否有代理环境变量
docker compose exec app env | grep -i proxy

# 查看最近的刷新日志
docker compose logs --tail=50 app | grep -iE "yunwu|error|fail"
```
