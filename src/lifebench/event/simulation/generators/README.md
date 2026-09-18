# generators 子目录 — 每日模拟各阶段生成器

将 `Mind` 中的 4 个生成方法迁出为独立模块，`Mind` 保留薄委托方法。各函数第一个参数 `mind` 为 `Mind` 实例（Duck-typed）。子包采用**惰性导出**，避免阶段间导入耦合。

## 生成器

| 文件 | 说明 |
|------|------|
| `thought.py` | `generate_subjective_thought` — 主观思考生成器：生成拟人化的当日主观安排（计划如何执行、想安排什么活动）。 |
| `objective.py` | `generate_objective_events` — 客观事件生成器：结合日程与合理性，对全天事件进行调整、补充与优化。 |
| `trajectory.py` | `generate_poi_route` / `adjust_event_trajectory` — 轨迹生成器：真实 POI 定位与事件轨迹调整。 |
| `reflection.py` | `generate_reflection` — 反思生成器：生成记忆摘要、活动统计与下一日上下文。 |
