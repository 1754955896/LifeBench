# config 目录 — 配置文件

项目llm api和地图api配置文件目录。

## 文件

| 文件 | 说明 |
|------|------|
| `config.example.json` | 配置文件模板，包含 LLM API 密钥、地图 API 等配置项的示例 |
| `config.json` | 实际配置文件（不提交到版本库） |

## 配置项说明

### llm

| 配置项 | 说明 | 示例 |
|--------|------|------|
| `api_key` | LLM API 密钥 | `xxx` |
| `base_url` | API base URL | `https://api.deepseek.com` |
| `default_model` | 默认聊天模型 | `deepseek-v4-flash` |
| `reason_model` | 推理模型 | `deepseek-v4-pro` |
| `strip_think` | 是否去除推理模型输出的 think 标签内容 | `false` |

### map_tool

| 配置项 | 说明 | 示例 |
|--------|------|------|
| `api_key` | 地图 API 密钥 | `xxx` |

### trajectory_assignment

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `enabled` | 是否启用 V1 约束式地点分配；关闭后仅接受旧版路线格式 | `true` |
| `seed` | 候选选择的全局随机种子，与人物和日期共同决定可复现结果 | `0` |
| `candidate_limit` | 每个非固定停留点召回的地图候选上限 | `12` |
| `route_top_k` | 进入真实路线计算的重力模型候选数 | `4` |
| `final_itinerary_retry_count` | 最终地点—通行链无法完整解析时的额外 LLM 重试次数 | `1` |
| `strict_validation` | 地理分配或最终行程不完整时令当日失败并触发引擎重试，禁止静默回退为成功数据 | `true` |
