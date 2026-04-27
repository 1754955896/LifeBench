# life_bench_data 目录 — 基准数据集

存放 LifeBench 基准数据集，包含 10 位用户的一年生活数据，有中英文两个版本。

## 子目录

| 目录 | 说明 |
|------|------|
| `data/` | 中文版数据（fenghaoran、yuxiaowen 等 10 位用户） |
| `data_en/` | 英文版数据（与 `data/` 结构相同） |
| `locomo_format/` | 转换为 locomo 格式的 QA 数据 |

## 各用户数据文件说明

每位用户的数据包含以下文件：

| 文件 | 说明 |
|------|------|
| `phone_data/` | 手机操作轨迹数据 |
| `QA/` | 问答对数据 |
| `summary/` | 月度总结 |
| `daily_event.json` | 每日生活事件 |
| `location.json` | 真实城市地址 |
| `persona.json` | 用户画像 |
| `daily_draft.json` | 每日大纲 |

## locomo 格式数据

| 文件 | 说明 |
|------|------|
| `our.json` | 中文版 locomo 格式 QA 数据 |
| `our_en.json` | 英文版 locomo 格式 QA 数据 |
