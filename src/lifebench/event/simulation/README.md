# simulation 子目录 — 每日生活模拟引擎

从 `event/daily_simulator.py`（MindController）抽出的模块化模拟引擎，负责把每日大纲（daily draft）逐步演化成带真实地点、记忆与反思的逐日事件。

引擎以**日期分片**为并行粒度：分片之间并行、分片内逐日串行；每个分片冷启动（用草稿预测记忆），内部再逐日演化，并维护一个事务 checkpoint 用于失败续跑与重试幂等。`daily_simulator.py` 仍是最外层调度入口，通过 `mind_factory` 注入 `Mind` 实例。

## 核心文件

| 文件 | 说明 |
|------|------|
| `engine.py` | `DailySimulationEngine` — 每日模拟引擎：日期分片并行驱动器 + 事务 checkpoint。 |
| `preparation.py` | `SimulationAssetPreparer` — 单进程预处理所有日期分片共享的不可变资产（模糊记忆、地点资产 `persona_locations_v2`），校验后冻结为本次运行共享。 |
| `state.py` | 认知状态数据结构（`CognitiveState` / `LongTermMemory` 等）。 |
| `activity_contract.py` | 主观生成与客观生成之间的结构化桥接（结构化停留意图等）。 |
| `validation.py` | 逐日校验：schema 与不变量校验。 |
| `telemetry.py` | 遥测：`manifest`（可复现元数据）+ `memory_trace`（检索/写入命中 ID）。 |

## 子目录

| 目录 | 说明 |
|------|------|
| `generators/` | 各阶段生成器（主观思考、客观事件、轨迹、反思） |
| `context/` | 主观思考阶段的结构化上下文构造 |
| `geolocation/` | 约束式地理位置分配（EPR/重力、轨迹协调、半小时导出） |
| `memory/` | 结构化记忆存储 / 检索 / 巩固 / 嵌入 |
| `activity/` | 活动规范化与全天出行链预规划 |
| `baseline/` | 无移动反馈（no-mobility）消融基线 |
