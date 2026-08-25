# 魔芋平台定价页面逆向分析报告

> 分析日期：2026-08-25
> 数据来源：`https://uat.moyu.info/pricing` 页面 HTML 及 JS Bundle 逆向 + API 实测

---

## 一、平台基础架构

| 项目 | 详情 |
|------|------|
| 平台名称 | 魔芋AI（`system_name: '魔芋AI'`） |
| 全称 | 魔芋AI大模型网关 / 全球大模型一站式调用及服务平台 |
| 底层系统 | **new-api / one-api 体系**（从代码结构、`model_ratio` / `group_ratio` / `channel` 等概念可确认） |
| 前端技术栈 | React + Semi UI（字节跳动开源组件库）+ Vite 构建 + i18n 国际化 |
| 货币系统 | `quota_per_unit = 1,000,000`，`quota_display_type = 'CNY'`，直接以 ¥ 显示 |
| 统计分析 | 百度统计（ID: `6b2c7a7b62782eb80fbb337a3ebacb5a`），注释预留 Google Analytics 和 Umami 位置（未启用） |
| 百度站点验证 | `codeva-6gSrIoM4QG` |
| 认证方式 | 支持用户名密码、GitHub OAuth、Discord OAuth、LinuxDo OAuth、OIDC、Telegram、Passkey、短信验证 |
| 支付方式 | Stripe、支付宝 |

### 前端资源文件

| 文件 | 用途 |
|------|------|
| `index-BrV6TmDo.js` (11MB) | 应用主入口 bundle |
| `react-core-D-liPAtk.js` | React 核心 |
| `semi-ui-0gQNYyWt.js` | Semi UI 组件库 |
| `tools-BW1QlQKQ.js` (75KB) | 工具函数 |
| `react-components-DtlgkInD.js` (28KB) | 业务组件 |
| `i18n-BrBfpQAM.js` (60KB) | 国际化翻译 |

---

## 二、API 端点清单（从 JS Bundle 中提取出 150+ 个）

### 定价核心 API

| 端点 | 用途 | 需认证 |
|------|------|--------|
| `GET /api/pricing` | 用户侧定价列表（模型广场页面） | 是 |
| `GET /api/model_pricing/overview` | 管理后台定价总览（含渠道成本、供应商成本） | 是 |
| `GET /api/model-cost/official-price` | 官方原价管理 | 是 |
| `GET /api/model-cost/exchange-rate` | 汇率配置 | 是 |
| `GET /api/model-cost/channel-vendor-map` | 渠道-供应商映射 | 是 |
| `POST /api/model-cost/sync-official-prices` | 同步官方价格 | 是 |
| `POST /api/model-cost/sync-platform-prices` | 同步平台价格 | 是 |
| `GET /api/model-cost/model-groups` | 模型分组 | 是 |
| `GET /api/status` | 系统状态（含 `quota_per_unit` 等） | **否** |
| `GET /api/setup` | 系统初始化状态 | **否** |
| `GET /api/notice` | 公告 | **否** |

### 模型与渠道 API

| 端点 | 用途 |
|------|------|
| `GET /api/models` | 模型列表 |
| `GET /api/models/?status_only=true` | 模型状态 |
| `GET /api/models/missing` | 缺失模型 |
| `POST /api/models/sync_upstream` | 同步上游模型 |
| `GET /api/channel/models` | 渠道模型列表 |
| `GET /api/channel/models_enabled` | 已启用渠道模型 |
| `GET /api/channel/fetch_models` | 从渠道拉取模型 |
| `GET /api/channel/model_channel_config` | 模型-渠道配置 |
| `GET /api/vendors/?page_size=1000` | 供应商列表 |
| `GET /api/vendors/grant-list` | 供应商授权列表 |

### 用户与分组 API

| 端点 | 用途 |
|------|------|
| `POST /api/user/login` | 用户登录（返回 `access_token`） |
| `GET /api/user/self` | 当前用户信息 |
| `GET /api/user/models` | 用户可用模型（支持 `model_type` 筛选） |
| `GET /api/user_model_ratio/` | 用户自定义倍率 |
| `GET /api/group/` | 分组列表 |
| `GET /api/group-cost/` | 分组成本 |
| `GET /api/group-discount` | 分组折扣 |

### 日志与报表 API

| 端点 | 用途 |
|------|------|
| `GET /api/report/model-summary` | 模型使用汇总 |
| `GET /api/report/token-summary` | Token 使用汇总 |
| `GET /api/report/consume-summary` | 消费汇总 |
| `GET /api/report/topup-summary` | 充值汇总 |
| `GET /api/report/stats/consume` | 消费统计 |
| `GET /api/report/stats/recharge` | 充值统计 |
| `GET /api/metrics/model` | 模型性能指标 |
| `GET /api/metrics/health-board` | 健康面板 |
| `GET /api/error-report/list` | 错误报告 |

### 其他 API

| 端点 | 用途 |
|------|------|
| `GET /api/token-plan/recharge-tiers` | Token 充值套餐阶梯 |
| `GET /api/deployments` | 部署列表 |
| `GET /api/deployments/price-estimation` | 部署价格估算 |
| `GET /api/smart-app/` | 智能应用 |
| `GET /api/permission/matrix` | 权限矩阵 |
| `GET /api/option/` | 系统选项配置 |
| `POST /api/option/rest_model_ratio` | 重置模型倍率 |

---

## 三、数据模型 — 每条模型记录的完整字段

### `/api/pricing` 返回结构

**顶层字段：**

```json
{
  "success": true,
  "message": "",
  "data": [...],                    // 模型列表（202 条）
  "vendors": [...],                 // 供应商列表（24 个）
  "group_ratio": {...},             // 分组倍率映射（18 个分组）
  "usable_group": {...},            // 可用分组
  "supported_endpoint": {...},      // 支持的端点类型定义
  "auto_groups": [...],             // 自动分组
  "user_model_ratio": {...},        // 用户自定义倍率
  "group_discounts": [...],         // 分组折扣规则
  "kling_v3_price": {...},          // 可灵 V3 特殊定价
  "vidu_resolution_price": {...},   // Vidu 分辨率定价
  "video_resolution_price": {...},  // 通用视频分辨率定价
  "image_resolution_price": {...},  // 图片分辨率定价
  "realtime_audio_price": {...},    // 实时音频定价
  "text_real_price": {...}          // 文本真实价格（分时定价）
}
```

**`/api/model_pricing/overview` 额外返回：**

```
channel_details        - 每个模型在每个分组下的渠道详情（含渠道成本价）
channel_suppliers      - 每个模型的渠道供应商名称
channel_label_dict     - 渠道标签到公司名的映射
cache_ratio            - 每个模型的缓存命中折扣倍率
cache_creation_ratio   - 每个模型的缓存创建倍率
```

### 模型记录字段

**基础字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `model_name` | string | 模型名称 |
| `vendor_id` | int | 供应商 ID（关联 vendors 表） |
| `model_type` | int | 模型类型：0=未设置, 1=文本, 2=图片生成, 3=视频生成, 4=语音生成 |
| `quota_type` | int | 计费类型：0=按量(token), 1=按次, 2=按秒 |
| `model_ratio` | float | 模型倍率（`quota_type=0` 时有效） |
| `completion_ratio` | float | 补全倍率（输出/输入的比率） |
| `model_price` | float | 固定价格（`quota_type=1` 按次或 `2` 按秒时有效） |
| `description` | string | 模型描述（109 个模型有描述） |
| `featured` | int | 是否推荐（12 个模型标记为推荐） |
| `owner_by` | string | 所有者 |
| `enable_groups` | list | 可用分组列表 |
| `supported_endpoint_types` | list | 支持的端点类型 |
| `icon` | string | 模型图标 |
| `tags` | list | 标签 |

**官方价格字段（104 个模型有数据）：**

| 字段 | 说明 |
|------|------|
| `official_input_price` | 官方输入原价 (¥/M tokens) |
| `official_output_price` | 官方输出原价 (¥/M tokens) |
| `official_price` | 官方固定原价（按次/按秒时使用） |

**阶梯定价字段（`using_tiered_pricing=true` 时）：**

| 字段 | 说明 |
|------|------|
| `using_tiered_pricing` | 是否启用阶梯定价 |
| `tier_input_ratio_used` | 阶梯输入倍率 |
| `tier_output_ratio_used` | 阶梯输出倍率 |
| `tier_completion_ratio_used` | 阶梯补全倍率 |

**阶梯定价 tiers 结构：**

```json
{
  "model_name": {
    "enabled": true,
    "tiers": [
      {
        "start_tokens": 0,
        "end_tokens": 1000000,
        "ratio": 1.0,
        "completion_ratio": 1.5
      },
      {
        "start_tokens": 1000000,
        "end_tokens": 0,
        "ratio": 0.8,
        "completion_ratio": 1.2
      }
    ]
  }
}
```

**特殊定价字段：**

| 字段 | 说明 |
|------|------|
| `cache_ratio` | 缓存命中折扣倍率（默认 0.1） |
| `cache_creation_ratio` | 缓存创建倍率（默认 1.25） |
| `audio_input_ratio` | 音频输入倍率 |
| `audio_output_ratio` | 音频输出倍率 |
| `silent_ratio` | 静音倍率 |
| `image_generation_call_price` | 图片生成单次价格 |
| `resolution_ratio` | 分辨率倍率 |
| `resolution_4k_ratio` | 4K 分辨率倍率 |
| `video_input_ratio` | 视频输入倍率 |
| `resolution_video_input_ratio` | 分辨率视频输入倍率 |
| `text_real_price` | 真实文本价格标记（布尔值） |
| `file_search` | 文件搜索支持标记 |

---

## 四、价格计算公式（从 JS 逆向）

### 按量计费 (quota_type=0)

```
输入价格 = model_ratio × group_ratio × user_model_ratio × (1M / quota_per_unit)
输出价格 = model_ratio × completion_ratio × group_ratio × user_model_ratio × (1M / quota_per_unit)
```

由于 `quota_per_unit = 1,000,000`，所以 `1M / quota_per_unit = 1`，价格直接等于 `model_ratio × group_ratio`（¥/M tokens）。

### 按次计费 (quota_type=1)

```
价格 = model_price × group_ratio × user_model_ratio  (¥/次)
```

### 按秒计费 (quota_type=2)

```
价格 = model_price × group_ratio × user_model_ratio  (¥/秒)
```

### 缓存计费

```
缓存命中价格 = 输入价格 × cache_ratio (默认 0.1，即 1 折)
缓存创建价格 = 输入价格 × cache_creation_ratio (默认 1.25，即 1.25 倍)
```

### 货币转换

前端支持三种显示模式：
- `USD` — 以 $ 显示，使用 `usd_exchange_rate`（当前为 1）
- `CNY` — 以 ¥ 显示（当前使用此模式）
- `TOKENS` — 直接显示 token 数量
- `CUSTOM` — 自定义货币符号和汇率

---

## 五、分组与折扣体系

### 分组倍率（18 个分组）

| 分组名 | 倍率 | 说明 |
|--------|------|------|
| default | 1.0 | 默认分组 |
| Lite(2折特惠组) | 0.8 | 8 折 |
| Lite(3折特惠组) | 0.3 | 3 折特惠 |
| Lite-Claude | 0.612 | Claude 专用优惠（约 6.1 折） |
| Lite-GPT | 0.68 | GPT 专用优惠（约 6.8 折） |
| Lite-gemini | 0.459 | Gemini 专用优惠（约 4.6 折） |
| Lite-banana-pro(gemini-3-pro-image-preview)特惠 | 0.4 | Gemini 3 Pro 图像特惠 |
| Lite-banana2(gemini-3.1-flash-image-preview)特惠 | 0.4 | Gemini 3.1 Flash 图像特惠 |
| max-claude | 1.75 | Claude 高级（1.75 倍） |
| max-claude-opus-4.7 | 1.4707 | Opus 4.7 专用 |
| max-gemini | 1.2 | Gemini 高级 |
| max-gpt | 1.93 | GPT 高级（1.93 倍） |
| WJ200团队号 | 1.0 | 团队号 |
| openclaw | 1.0 | |
| sd2-asset分组 | 1.0 | Seedance 2 资产分组 |
| banana-sd2-asset分组 | 1.0 | |
| comefusion-sd2-asset分组 | 1.0 | |
| suansuan-sd2-asset分组 | 1.0 | |

### 分组级别折扣

| 分组 | 模型匹配 | 折扣 |
|------|---------|------|
| default | `gpt` | 52% |
| default | `claude` | 60% |
| max-claude | (全部) | 100% |

---

## 六、供应商列表（24 个 vendors）

| ID | 名称 | 有图标 |
|----|------|--------|
| 1 | DeepSeek | 是 |
| 2 | 阿里巴巴 | 是 |
| 3 | Gemini | 是 |
| 4 | OpenAI | 是 |
| 5 | 安全大模型 | 否 |
| 6 | Google | 否 |
| 7 | Anthropic | 是 |
| 8 | 快手 | 是 |
| 9 | Moonshot | 是 |
| 10 | 月之暗面 | 否 |
| 11 | 即梦 | 是 |
| 12 | 字节跳动 | 是 |
| 14 | MiniMax | 是 |
| 15 | Vidu | 是 |
| 16 | 小米 | 否 |
| 17 | xAI | 是 |
| 18 | Grok | 否 |
| 19 | Grok (xAI) | 是 |
| 20 | 智谱 | 是 |
| 21 | 智谱 | 是 |
| 22 | Meta | 是 |
| 23 | 压测测试供应商 | 否 |
| 24 | go | 否 |
| 25 | qqqq | 否 |

---

## 七、渠道供应商（30 个后端渠道）

管理后台 API (`/api/model_pricing/overview`) 暴露了每个模型通过哪个渠道供应商提供服务及其成本价格。

| 渠道标签 | 公司全称 |
|---------|---------|
| 中国电信 | 中国电信股份有限公司广州越秀区分公司 |
| 华为云 | 华为云大模型即服务平台 |
| 火山 | 北京火山引擎科技有限公司 |
| 阿里 | 阿里云百炼 |
| 阿里PolarDB-X | 阿里PolarDB-X |
| 腾讯云 | 腾讯云大模型 |
| 腾讯云(清智) | 北京清程极智科技有限公司 |
| 智谱 | 北京智谱华章科技股份有限公司 |
| MiniMax | 上海稀宇科技有限公司 |
| deepseek | DeepSeek深度求索 |
| 生数 | 北京生数科技股份有限公司 |
| Bananarouter | 广州趣流科技有限公司 |
| Mirrmart | 成都爱国产数字科技有限公司 |
| 云雾 | 重庆云之雾网络科技有限公司 |
| cheaptokens | cheaptokens |
| pixverse | pixverse |
| 伊登 | 美塔智能（香港）有限公司 |
| 凌速科技 | 凌速科技 |
| 天翼云 | 天翼云 |
| 博特智能 | 博特智能 |
| 沁诚 | 上海沁诚信息科技有限公司 |
| 火豹 | 火豹(四川)科技有限公司 |
| 聚变方成 | 广州聚变方成科技有限公司 |
| 迁聚 | 广州米姆信息科技有限公司 |
| 鲸纬 | 福州市鲸纬传媒科技有限公司 |
| 万界 | — |
| 代理 | — |
| 江城 | — |
| 灵妙 | — |
| 深圳勒杜鹃 | — |

---

## 八、支持的端点类型

| 端点类型 | 路径 | 方法 |
|---------|------|------|
| `openai` | `/v1/chat/completions` | POST |
| `openai-response` | `/v1/responses` | POST |
| `anthropic` | `/v1/messages` | POST |
| `gemini` | `/v1beta/models/{model}:generateContent` | POST |
| `image-generation` | `/v1/images/generations` | POST |
| `video` | `/v1/video/generations` | POST |
| `realtime` | `/v1/realtime` | WSS |

---

## 九、模型统计数据（当前 202 个模型）

### 按计费类型分布

| quota_type | 含义 | 数量 |
|------------|------|------|
| 0 | 按量计费 (token) | 141 |
| 1 | 按次计费 | 22 |
| 2 | 按秒计费 | 39 |

### 按模型类型分布

| model_type | 含义 | 数量 |
|------------|------|------|
| 0 | 未设置 | 38 |
| 1 | 文本模型 | 86 |
| 2 | 图片生成模型 | 25 |
| 3 | 视频生成模型 | 50 |
| 4 | 语音生成模型 | 2 |
| 5 | 未知 | 1 |

### 数据丰富度

| 指标 | 数量 |
|------|------|
| 总模型数 | 202 |
| 有官方原价 | 104 |
| 有描述 | 109 |
| 标记为推荐 | 12 |

---

## 十、特殊定价机制详解

### 1. DeepSeek 分时定价 (text_real_price)

DeepSeek V4 系列实行高峰/非高峰价格区分：

| 模型 | 高峰时段 | 非高峰输入 | 高峰输入 | 非高峰输出 | 高峰输出 | 缓存命中(非高峰) | 缓存命中(高峰) |
|------|---------|-----------|---------|-----------|---------|----------------|---------------|
| deepseek-v4-flash | 9-12, 14-18 | ¥1.5/M | ¥3/M | ¥4.5/M | ¥9/M | ¥0.05/M | ¥1/M |
| deepseek-v4-pro | 9-12 | ¥9.6/M | ¥19.2/M | ¥9.6/M | ¥19.2/M | ¥0.15/M | ¥3/M |
| DeepSeek-V4-Flash-20260731 | 9-12, 14-18 | ¥4.5/M | ¥9/M | ¥13.5/M | ¥27/M | ¥0.15/M | ¥0.3/M |
| DeepSeek-V4-Pro-0813 | 9-12, 14-18 | ¥1.5/M | ¥3/M | ¥4.5/M | ¥9/M | ¥0.05/M | ¥0.1/M |

### 2. 图片分辨率定价 (image_resolution_price)

| 模型 | 1K 输入 | 2K 输入 | 1K 输出 | 2K 输出 |
|------|--------|--------|--------|--------|
| qwen-image-3.0 | ¥0.02 | ¥0.02 | ¥0.18 | ¥0.18 |
| qwen-image-3.0-pro | ¥0.02 | ¥0.02 | ¥0.25 | ¥0.50 |
| wan2.6-image | — | — | ¥0.20 | ¥0.20 |

### 3. 视频分辨率定价 (video_resolution_price)

| 模型 | 480p | 720p | 1080p |
|------|------|------|-------|
| happyhorse-1.0-t2v | — | ¥0.90 | ¥1.60 |
| happyhorse-1.1-i2v | ¥0.45 | ¥0.90 | ¥1.20 |
| happyhorse-1.1-r2v | ¥0.45 | ¥0.90 | ¥1.20 |

### 4. Vidu 分辨率定价 (vidu_resolution_price)

| 模型 | 540p | 720p | 1080p |
|------|------|------|-------|
| viduq3-pro | ¥0.31 | ¥0.63 | ¥0.75 |
| viduq3-turbo | ¥0.22 | ¥0.34 | ¥0.41 |

### 5. 可灵 V3 定价 (kling_v3_price)

按「模式 × 类型 × 音频 × 运动控制」组合定价（以 kling-v3 为例）：

| 组合 | std 模式 | pro 模式 |
|------|---------|---------|
| 文生视频(无音频) | ¥0.60 | — |
| 文生视频(有音频) | ¥0.80 | — |
| 图生视频(无音频) | ¥0.60 | — |
| 图生视频(有音频) | ¥0.80 | — |
| 运动控制 | 有 | — |

### 6. 实时音频定价 (realtime_audio_price)

| 模型 | 文本输入 | 文本输出 | 音频输入 | 音频输出 | 文本缓存 | 音频缓存 |
|------|---------|---------|---------|---------|---------|---------|
| doubao-realtime-v1.2.6.1 | ¥10/M | ¥80/M | ¥80/M | ¥300/M | ¥5/M | ¥5/M |

---

## 十一、前端页面路由

### 公开页面

| 路由 | 说明 |
|------|------|
| `/` | 首页 |
| `/pricing` | 模型广场（定价页面，需登录） |
| `/token-plan` | Token 优惠套餐 |
| `/agent-market` | 智能体市场 |
| `/app-square` | 应用广场 |
| `/docs` | 开发文档 |
| `/contact` | 关于/联系 |
| `/login` | 登录 |
| `/register` | 注册 |

### 管理后台页面

| 路由 | 说明 |
|------|------|
| `/console` | 控制台首页 |
| `/console/channel` | 渠道接入管理 |
| `/console/models` | 模型管理 |
| `/console/model-pricing` | 模型定价管理 |
| `/console/model-cost` | 计费管理 |
| `/console/model-metrics` | 模型指标 |
| `/console/model-monitor/health` | 模型健康监控 |
| `/console/vendor` | 供应商管理 |
| `/console/user` | 用户管理 |
| `/console/token` | 令牌管理 |
| `/console/log` | 消费日志 |
| `/console/group-cost` | 分组成本 |
| `/console/group-discount` | 分组折扣 |
| `/console/profit-calc` | 利润计算 |
| `/console/revenue-share` | 分成管理 |
| `/console/setting` | 系统设置 |
| `/console/deployment` | 部署管理 |
| `/console/playground` | 对话 Playground |
| `/console/image-playground` | 图片 Playground |
| `/console/video-playground` | 视频 Playground |

---

## 十二、`/api/status` 完整返回数据

该端点无需认证，返回平台配置信息：

```json
{
  "system_name": "魔芋AI",
  "quota_per_unit": 1000000,
  "quota_display_type": "CNY",
  "price": 1,
  "usd_exchange_rate": 1,
  "display_in_currency": true,
  "custom_currency_symbol": "¤",
  "custom_currency_exchange_rate": 1,
  "server_address": "https://10.12.186.147",
  "passkey_display_name": "魔芋AI",
  "passkey_rp_id": "10.12.186.147",
  "passkey_origins": "https://10.12.186.147",
  "start_time": 1787304950,
  "stripe_unit_price": 8,
  "email_verification": true,
  "sms_enabled": true,
  "captcha_enabled": true,
  "checkin_enabled": true,
  "enable_drawing": true,
  "enable_task": true,
  "enable_data_export": true,
  "enable_batch_update": true,
  "home_maintenance_mode": true,
  "uptime_kuma_enabled": true,
  "docs_link": "/developer-docs/index.html",
  "data_export_default_time": "hour"
}
```

---

## 十三、对当前 `moyu_fetcher.py` 的改进启示

当前 fetcher 只使用了 `/api/pricing` 的基础字段（`model_name`、`model_ratio`、`completion_ratio`、`quota_type`、`model_price`）。从 JS 分析可知还有以下**未利用的数据**：

### 可立即利用的

1. **`vendor_id` → vendor name 映射** — `/api/pricing` 返回 `vendors` 数组，可直接从 `vendor_id` 获取供应商名称，比当前的正则匹配更准确
2. **`model_type`** — 可区分文本(1)/图片(2)/视频(3)/语音(4)模型，用于前端筛选
3. **`official_input_price` / `official_output_price`** — 官方原价，可展示平台折扣率
4. **`description`** — 109 个模型有详细中文描述
5. **`supported_endpoint_types`** — 可知模型支持的 API 接口类型
6. **`enable_groups`** — 可用分组信息

### 进阶利用

7. **`/api/model_pricing/overview`** — 返回渠道成本价（`channel_details`），可对比售价与成本
8. **分时定价 (`text_real_price`)** — DeepSeek V4 系列的高峰/非高峰价格
9. **阶梯定价** — `using_tiered_pricing` 及 `tier_*_ratio_used` 字段
10. **缓存定价** — `cache_ratio`（默认 0.1）和 `cache_creation_ratio`（默认 1.25）
11. **分组倍率 (`group_ratio`)** — 了解不同分组的价格差异
12. **分组折扣 (`group_discounts`)** — 特定分组对特定模型的额外折扣
