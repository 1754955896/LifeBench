# Runtime Configuration

This directory stores runtime configuration, including **LLM API** and **map API** keys and parameters for location assignment and trajectory simulation.

Configuration is JSON and is read from `config/config.json` by modules including:

- `src/lifebench/utils/llm_call.py`: reads `llm`.
- `src/lifebench/utils/maptool.py`: reads `map_tool`.
- `src/lifebench/event/simulation/preparation.py`: reads `simulation_asset_preparation`.
- `src/lifebench/event/simulation/generators/trajectory.py` and `src/lifebench/event/daily_simulator.py`: read `trajectory_assignment`.

## Files

| File | Description |
|------|-------------|
| `config.example.json` | Configuration template with all options and defaults, **without real keys**. Copy it to `config.json` and fill in the values. |
| `config.json` | Active runtime configuration containing real keys. **Do not commit this file.** |

> Use the same structure as `config.example.json`, changing API keys and runtime values such as `allocation_mode` and `feedback_mode` as needed.

---

## Configuration Overview

There are four top-level sections:

```jsonc
{
  "llm": { ... },                          // LLM API
  "simulation_asset_preparation": { ... }, // Shared simulation asset preparation
  "trajectory_assignment": { ... },        // Location assignment and trajectories
  "map_tool": { ... }                      // Map API
}
```

---

## 1. `llm`: LLM API

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `api_key` | string | `""` | LLM provider API key. |
| `base_url` | string | `https://api.deepseek.com` | Base URL of the OpenAI-compatible API. |
| `default_model` | string | `deepseek-v4-flash` | Default chat model for general generation and structured decoding. |
| `reason_model` | string | `deepseek-v4-pro` | Model for calls requiring stronger reasoning. |
| `strip_think` | boolean | `false` | `true`: removes `<think>...</think>` blocks from model output using a regular expression, retaining only the response body. `false`: returns the output unchanged, including any reasoning content. |

---

## 2. `simulation_asset_preparation`: Shared Asset Preparation

Before any date partition starts, a single process generates or loads shared read-only assets: fuzzy memory and `persona_locations_v2` location assets. It validates and freezes them for the run so individual partitions do not rebuild them.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | `true` | Main switch. `true`: generates or loads fuzzy memory, enriches location assets, and writes `asset_snapshot.json`. `false`: only normalizes location documents, marks the snapshot `{enabled:false}`, and generates neither memory nor reference POIs. |
| `ensure_fuzzy_memory` | boolean | `true` | `true`: generates fuzzy long-term memory summaries (`monthly_summaries.json` / `cumulative_summaries.json`), reusing existing files. `false`: skips generation, leaving simulation fuzzy memory empty. |
| `ensure_location_opportunity_pool` | boolean | `true` | `true`: uses maps and an LLM to pre-generate reference POIs in the persona's city. Both `map_tool.api_key` and `llm.api_key` must be nonempty; otherwise it silently falls back to normalization only. `false`: keeps normalized location assets without enrichment. |
| `freeze_for_run` | boolean | `true` | Controls only the snapshot's `frozen` metadata flag. The flag is recorded in `mind.asset_snapshot`; downstream code does not change behavior based on it, so it currently has no runtime switching effect. |
| `strict_anchor_validation` | boolean | `true` | `true`: raises an error and stops partition creation if location assets lack usable core anchors (`anchors` is empty). `false`: continues without anchors, potentially deferring failures to later stages. |
| `allow_partial_optional_pois` | boolean | `true` | Handles location pool construction failures. `true`: falls back to normalized locations and records `partial_failures` in the manifest without stopping. `false`: raises an error and aborts the run. |

---

## 3. `trajectory_assignment`: Location Assignment and Trajectories

Controls how daily event plans become location sequences with real coordinates and travel times.

### 3.1 Main Switches and Modes

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | `true` | Main geographic assignment switch.<br>`true`: generates structured stop intents with validation retries, ranks candidates using EPR/gravity models, applies budgets, and reconciles the itinerary. Produces structured trajectories with real coordinates per stop, distance/duration per leg, and half-hour location exports.<br>`false`: makes a single LLM call for an `instruction`, converted by `maptools` into a simplified POI route string. Skips EPR, budgets, reconciliation, half-hour export, and structural validation retries. |
| `allocation_mode` | string | `"full"` | Assignment algorithm; applies only when `enabled=true`.<br>`"full"`: map candidate retrieval, gravity/EPR ranking, budget filtering, and itinerary reconciliation, with distances and travel times computed in code.<br>`"simple"`: an LLM with geographic tools resolves event coordinates itself, without numeric EPR/gravity/budget calculations in the assignment code. Subsequent adjustment, backfilling, and half-hour export use `simple_adjust_trajectory`. |
| `feedback_mode` | string | `"on"` | Feedback ablation switch; **applies only with `allocation_mode="simple"`**.<br>`"on"`: injects mobility statistics into subjective thought and objective event prompts (`behavior_history`, `trajectory_location_history`, and the daily soft mobility profile), so recent mobility affects daily intentions.<br>`"none"`: temporarily clears those two feedback containers and uses no-mobility templates, making thought depend only on persona, plan, memory, state, and environment. Reflection/memory narratives and geographic assignment are unaffected. |

### 3.2 Candidates and Budgets

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `seed` | integer | `0` | Global candidate-selection seed, combined with persona ID and date for reproducible sampling. |
| `candidate_limit` | integer | `18` | Maximum map candidates per non-fixed stop. Larger values increase candidate variety and map calls. |
| `route_top_k` | integer | `6` | Number of top candidates evaluated with real routes and the gravity model. |
| `budget_aware` | boolean | `true` | `true`: constrains candidates using remaining daily distance and travel-time soft budgets. Optional candidates exceeding the budget are removed or downweighted; required locations (`must_return`) produce warnings but are retained. `false`: selects using gravity/EPR scores without budget constraints. |
| `intent_retry_count` | integer | `2` | Local retries when stop-intent JSON fails validation. `0` means one attempt only. |

### 3.3 Validation and Retries

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `strict_validation` | boolean | `true` | `true`: incomplete geographic assignment or final itineraries raise an error, fail the day, and trigger a full-day engine retry instead of silently reporting success. `false`: silently falls back to a simplified route string or empty result without a full-day retry. |
| `accuracy_validation` | boolean | `false` | `true`: additionally checks external accuracy markers, including consistent city labels, `llm_plausible` fallback stops, and map-verified travel legs. `false`: checks only structural properties such as coordinates, connected legs, and itinerary completeness. |
| `final_itinerary_retry_count` | integer | `1` | Additional LLM retries when the final location/travel chain cannot be fully resolved. Total attempts equal this value plus one. |

### 3.4 `half_hour_export`: Half-Hour Locations

Exports 48 half-hour location samples per day from the final reconciled geographic facts.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | `true` | `true`: exports daily trajectories to JSONL on a half-hour grid (`sim/half_hour/half_hour_*.jsonl`) with longitude/latitude in both GCJ-02 and WGS-84. `false`: skips export. |
| `slot_minutes` | integer | `30` | Sampling interval in minutes. `30` gives 48 slots per day. |

### 3.5 `mobility_calibration`: Mobility and EPR Priors

Population priors for the exploration-preferential-return (EPR) model. These values are not hard overrides: personal observations are progressively incorporated according to `personalization_weight`, blending priors with empirical values as history grows.

| Option | Type | Default | Range | Effect |
|--------|------|---------|-------|--------|
| `rho` | float | `0.52` | 0.10-0.90 | Base exploration probability prior. Higher values favor new places; lower values favor known places. |
| `gamma` | float | `0.24` | 0.05-0.80 | Decay exponent for exploration probability as the number of distinct locations grows. Higher values shift toward returning sooner. |
| `return_exponent` | float | `0.85` | 0.50-1.80 | Exponent applied to visit frequency in return-candidate weights. Higher values favor frequently visited locations. |
| `distance_beta` | float | `1.60` | 0.80-2.50 | Exponent of the truncated power-law distance kernel. Higher values penalize distant candidates more strongly. |
| `distance_cutoff_km` | float | `24.0` | 5-150 | Exponential cutoff of the distance kernel in kilometers. Higher values tolerate more distant destinations. |
| `distance_cutoff_multiplier` | float | `3.0` | 1.5-6.0 | Empirical cutoff equals characteristic one-way distance multiplied by this value. |
| `epr_count_scope` | string | `"blended"` | `global` / `context` / `blended` | Definition of distinct-location count D for exploration probability: `global` uses all returnable locations, `context` uses the current return pool, and `blended` combines both geometrically. |
| `epr_global_count_weight` | float | `0.35` | 0-1 | Weight of the global count in `blended` mode. `1` reduces to `global`; `0` reduces to `context`. |
| `urban_candidate_share` | float | `0.35` | 0.15-0.70 | Candidate share retained when the preference is for urban areas. |
| `personalization_weight` | float | `0.50` | 0-1 | Maximum influence of personal history over priors, gradually incorporated based on observed days divided by 30. Higher values reveal individual differences sooner; lower values rely more on population priors. |
| `selection_temperature` | float | `0.75` | 0.25-2.0 | Sampling temperature for ranked candidates. Higher values approach uniform randomness; lower values approach greedy selection of the highest weight. |
| `preference_boost` | float | `1.5` | 0-4 | Multiplicative boost for preferred candidates. Higher values give more weight to persona location preferences. |
| `repetition_fatigue_step` | float | `0.10` | 0-0.50 | Exploration probability increment per consecutive return day. Higher values encourage exploration sooner after repeated visits. |
| `repetition_fatigue_cap` | float | `0.30` | 0-1 | Maximum repetition-fatigue boost. |

### 3.6 `mobility_distribution_targets`: Daily Archetype Weights

Weekday and weekend archetype weights used to sample the daily mobility profile. Historical signals make only mild adjustments to these base weights.

**Weekdays: `weekday_archetype_weights`**

| Key | Default | Meaning |
|-----|---------|---------|
| `low_mobility` | 0.18 | Low mobility or staying home |
| `routine_commute` | 0.31 | Routine commute |
| `commute_with_errand` | 0.22 | Commute with errands |
| `evening_activity` | 0.14 | Evening activity |
| `social_or_leisure` | 0.08 | Social or leisure activity |
| `exploratory` | 0.04 | Exploration |
| `citywide_leisure` | 0.03 | Leisure across the city |

**Weekends: `weekend_archetype_weights`**

| Key | Default | Meaning |
|-----|---------|---------|
| `home_recovery` | 0.23 | Recovery at home |
| `local_leisure` | 0.24 | Local leisure |
| `social_activity` | 0.17 | Social activity |
| `exercise_outing` | 0.12 | Exercise outing |
| `exploratory` | 0.08 | Exploration |
| `citywide_leisure` | 0.09 | Leisure across the city |
| `long_distance` | 0.07 | Long-distance travel |

> Only relative weights matter; they do not need to sum to one. Each value is clamped with `max(0.0, value)`. Increasing an archetype's weight makes it more frequent.

### 3.7 `location_opportunity_pool`: Local POI Inspiration

Parameters for pre-generating reference POIs in the persona's city and sampling daily location inspiration.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | `true` | `true`: enables POI pre-generation and daily inspiration sampling. `false`: skips both. |
| `refresh` | boolean | `false` | `true`: forces regeneration, ignoring the cache. `false`: reuses cached data if inputs and the generator version are unchanged. |
| `preseed_target_count` | integer | `60` | Target number of pre-generated locations. |
| `per_query_limit` | integer | `6` | Maximum candidates per map search, clamped to 1-20 in code. |
| `daily_familiar_quota` | [int, int] | `[3, 5]` | Random range for the number of familiar-location suggestions each day. |
| `daily_citywide_quota` | [int, int] | `[3, 6]` | Random range for the number of citywide-location suggestions each day. |
| `daily_social_quota` | [int, int] | `[0, 1]` | Random range for the number of social-location suggestions each day. |

---

## 4. `map_tool`: Map API

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `api_key` | string | `""` | Map API key for POI retrieval, geocoding, and travel information. When empty, related features such as `ensure_location_opportunity_pool` enrichment silently fall back to reduced functionality. |

---

## Quick Start

```bash
# 1. Create the local configuration from the template
cp config/config.example.json config/config.json

# 2. Fill in real API keys in config/config.json (do not commit this file)
#    llm.api_key: your LLM API key
#    map_tool.api_key: your map API key
```
