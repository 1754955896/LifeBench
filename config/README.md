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