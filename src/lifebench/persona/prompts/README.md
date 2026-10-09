# Persona Prompt Templates

Persona generation prompts organized by stage. Prompt builders expose `build_*_prompt` functions returning complete stage prompts; `contracts.py` centralizes structured output contracts as JSON Schemas.

## Files

| File | Description |
|------|-------------|
| `base_profile.py` | `build_base_profile_prompt`: base profile generation. |
| `narrative.py` | `build_narrative_prompt`: narratives about daily habits and personality. |
| `relation_plan.py` | `build_relation_plan_prompt`: social circle planning. |
| `contact_group.py` | `build_contact_group_prompt`: contact group generation. |
| `input_normalization.py` | `build_input_normalization_prompt`: arbitrary input normalization and extraction of facts and soft cues. |
| `enrich.py` | `build_enrich_prompt` / `build_enrich_consistency_prompt`: profile enrichment and consistency. |
| `profile_enrich.py` | `build_profile_enrich_prompt`: further profile enrichment. |
| `consistency.py` | `build_persona_consistency_prompt`: persona consistency validation. |
| `repair.py` | `build_repair_prompt`: persona repair. |
| `variant_blueprint.py` | `build_variant_blueprint_prompt`: diverse variant blueprint generation. |
| `address_places.py` | `build_address_places_prompt`: grounding addresses and frequently visited places. |
| `common.py` | `render_common_rules`: common rules shared across stages. |
| `contracts.py` | Structured output contracts: `profile_output_contract`, `persona_shape_contract`, `narrative_output_contract`, `relation_plan_output_contract`, and `contact_group_output_contract`. |
