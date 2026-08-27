# draft 子目录 — 事件大纲生成

负责从宏观到微观生成每日事件大纲（Daily Draft），包含多个阶段的细化与优化。

## 核心文件

| 文件 | 说明 |
|------|------|
| `graph_generator.py` | 事件关系图生成 |
| `graph_refiner.py` | 事件关系图细化 |
| `timeline_gen.py` | 时间线生成 |
| `event_gen.py` | 事件生成 |
| `event_refiner.py` | 事件细化 |
| `event_tree.py` | 事件树结构 |
| `outline_optimizer.py` | 大纲优化 |
| `scheduler.py` | 日程调度（大规模） |
