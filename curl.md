# 查询所有名称含 "gpt-4o" 的模型（跨所有平台）
```bash
curl -H "X-API-Key: <key>" "http://localhost:8000/api/external/prices?model=gpt-4o"
```

# 查询 claude 相关模型
```bash
curl -H "X-API-Key: <key>" "http://localhost:8000/api/external/prices?model=claude"
```

# 精确到某个供应商 + 模型
```bash
curl -H "X-API-Key: <key>" "http://localhost:8000/api/external/prices?provider=DeepSeek&model=deepseek-r1"
```

# 组合筛选：Anthropic 在 official 平台的 claude-sonnet
```bash
curl -H "X-API-Key: <key>" "http://localhost:8000/api/external/prices?provider=Anthropic&platform=official&model=sonnet"
```

# 查看数据是否有更新
```bash
curl -H "X-API-Key: <key>" "http://localhost:8000/api/external/status"
```