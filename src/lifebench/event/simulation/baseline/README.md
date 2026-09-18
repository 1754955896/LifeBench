# baseline 子目录 — 无移动反馈（no-mobility）消融基线

在不动源码反馈逻辑的前提下，用只读开关包装新的消融过程。`no-mobility` 基线切断「地理移动 → 客观/主观思考」的全部移动考量。

## 文件

| 文件 | 说明 |
|------|------|
| `no_feedback.py` | `generate_subjective_thought_no_feedback` / `generate_objective_events_no_feedback` — 切断移动考量的主观/客观生成。 |
| `templates_no_mobility.py` | no-mobility（无移动考量）版主观/客观提示词模板。 |
