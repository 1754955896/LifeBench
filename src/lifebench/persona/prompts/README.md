# prompts 子目录 — Persona 提示词模板

按阶段拆分的 Persona 生成提示词模板。每个文件暴露一个 `build_*_prompt` 函数，返回该阶段的完整 prompt；`contracts.py` 集中定义各阶段的结构化输出契约（JSON Schema）。

## 文件

| 文件 | 说明 |
|------|------|
| `base_profile.py` | `build_base_profile_prompt` — 基础画像生成。 |
| `narrative.py` | `build_narrative_prompt` — 叙事（日常习惯/性格）生成。 |
| `relation_plan.py` | `build_relation_plan_prompt` — 关系圈规划。 |
| `contact_group.py` | `build_contact_group_prompt` — 联系人分组生成。 |
| `input_normalization.py` | `build_input_normalization_prompt` — 任意输入规范化（事实/软线索抽取）。 |
| `enrich.py` | `build_enrich_prompt` / `build_enrich_consistency_prompt` — 画像充实与一致性。 |
| `profile_enrich.py` | `build_profile_enrich_prompt` — 画像再充实。 |
| `consistency.py` | `build_persona_consistency_prompt` — 画像一致性校验。 |
| `repair.py` | `build_repair_prompt` — 画像修复。 |
| `variant_blueprint.py` | `build_variant_blueprint_prompt` — 差异化变体蓝图生成。 |
| `address_places.py` | `build_address_places_prompt` — 地址/常去地点落地。 |
| `common.py` | `render_common_rules` — 各阶段共享的通用规则片段。 |
| `contracts.py` | 各阶段结构化输出契约（`profile_output_contract`、`persona_shape_contract`、`narrative_output_contract`、`relation_plan_output_contract`、`contact_group_output_contract`）。 |
