# event 模块 — 事件与问答数据生成

负责生成用户日常生活事件、手机操作轨迹及对应的问答对。

## 核心文件

| 文件 | 说明 |
|------|------|
| `daily_simulator.py` | 每日生活事件模拟器（核心调度） |
| `phone_data_gen.py` | 手机操作数据生成 |
| `all_qa_generator.py` | 问答对生成器 |
| `draft_gen.py` | 每日大纲（daily draft）生成 |
| `data_edit.py` | 数据编辑与修正工具 |
| `event_formatter.py` | 事件数据格式化 |
| `event_schema.csv` | 事件数据 Schema 定义 |

## 子目录

| 目录 | 说明 |
|------|------|
| `simulation/` | 每日生活模拟引擎（日期分片并行、地理分配、记忆、反思） |
| `draft/` | 事件大纲生成相关脚本（Graph、Timeline、Refiner 等） |
| `edit/` | 多 Agent 数据编辑管线（规划、执行、反思、批评等 Agent） |
| `phone_generator/` | 手机各类型数据生成器（聊天、通话、健康、相册等） |
| `qa_generator/` | 各类型 QA 生成器（单跳、多跳、时序、冲突等） |
| `memory_structure/` | 记忆结构构建（模糊记忆、记忆类） |
| `tools/` | 工具函数（事件匹配、地址生成、xlsx 转 csv 等） |
| `templates/` | 提示词模板 |
| `local_models/` | 本地 embedding 模型（all-MiniLM-L6-v2） |
