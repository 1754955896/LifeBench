# version2 — 新版数据格式（多源格式）

## 目录结构

```
version2/
├── data/               # 中文版多源数据
└── multi_source_format/ # 多源格式 QA 数据
```

## 用户列表

| 用户名 | 说明 |
|--------|------|
| yuxiaowen | |

## 各用户数据文件说明

每位用户的数据包含以下文件：

| 文件/目录 | 说明 |
|-----------|------|
| `phone_data/` | 手机操作轨迹数据 |
| `QA_all/` | 全部问答对数据 |
| `daily_event.json` | 每日生活事件 |
| `event_tree.json` | 事件树结构 |
| `persona.json` | 用户画像 |
| `daily_draft.json` | 每日大纲 |

## multi_source_format 目录

多源格式数据将所有用户的 QA 数据合并为一个文件，包含完整的问答对、手机操作数据等。

| 文件 | 说明 |
|------|------|
| `lifebench_multi_source_format_yuxiaowen.json` | yuxiaowen 的多源格式 QA 数据 |