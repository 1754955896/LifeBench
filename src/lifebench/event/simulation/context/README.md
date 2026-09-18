# context 子目录 — 主观思考阶段的结构化上下文

为主观思考（thought）阶段构造精简、结构化的输入，不依赖规则去理解生活语义。

## 文件

| 文件 | 说明 |
|------|------|
| `daily.py` | `build_subjective_context` — 构造 thought 阶段的精简结构化输入。 |
| `activity_recommendation.py` | `build_activity_recommendation` — 生成「泛化指导 + 具体活动推荐」的移动参考层。 |
| `location_inspiration.py` | `build_location_inspiration_context` — 构建人物地点机会的紧凑、确定性日视图。 |
| `variation.py` | 跨日行为摘要与当日变化设定：`build_daily_behavior_record`、`build_day_variation_context`、`build_mobility_day_budget`、`lean_mobility_day_profile` 等。 |
