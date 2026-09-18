# config 目录 — 配置文件

项目的运行时配置文件目录，集中存放 **LLM API** 与 **地图 API** 的密钥及地点分配 / 轨迹仿真相关的可调参数。

配置采用 JSON 格式。代码在多个模块中通过 `config/config.json` 读取，例如：

- `src/lifebench/utils/llm_call.py` — 读取 `llm` 段
- `src/lifebench/utils/maptool.py` — 读取 `map_tool` 段
- `src/lifebench/event/simulation/preparation.py` — 读取 `simulation_asset_preparation` 段
- `src/lifebench/event/simulation/generators/trajectory.py` 与 `src/lifebench/event/daily_simulator.py` — 读取 `trajectory_assignment` 段

## 文件

| 文件 | 说明 |
|------|------|
| `config.example.json` | 配置模板，含全部配置项及默认值，**不含真实密钥**。复制为 `config.json` 后填写。 |
| `config.json` | 实际生效的配置文件，包含真实密钥，**不应提交到版本库**。 |

> `config.json` 与 `config.example.json` 结构完全一致，仅密钥与个别运行值不同（如 `allocation_mode`、`feedback_mode`）。复制 `config.example.json` 为 `config.json` 后填写密钥即可。

---

## 配置项总览

顶层分为四个段：

```jsonc
{
  "llm": { ... },                          // LLM API
  "simulation_asset_preparation": { ... }, // 仿真共享资产预处理
  "trajectory_assignment": { ... },        // 地点分配与轨迹生成
  "map_tool": { ... }                      // 地图 API
}
```

---

## 1. `llm` — LLM API

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `api_key` | string | `""` | LLM 服务密钥。 |
| `base_url` | string | `https://api.deepseek.com` | OpenAI 兼容接口的 base URL。 |
| `default_model` | string | `deepseek-v4-flash` | 默认聊天模型，用于一般生成 / 结构化解码。 |
| `reason_model` | string | `deepseek-v4-pro` | 推理模型，用于需要更强推理能力的调用。 |
| `strip_think` | boolean | `false` | **开/关差异**：`true` 用正则剔除模型输出中的 `<think>…</think>` 标签（推理模型的思考过程），只保留正文；`false` 原样返回（`<think>` 内容会混进结果）。 |

---

## 2. `simulation_asset_preparation` — 仿真共享资产预处理

在**任何日期分片启动前**，由单进程生成或加载共享只读资产（模糊记忆、`persona_locations_v2` 地点资产），校验后冻结为本次运行共享，避免每个分片重复构建。

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enabled` | boolean | `true` | **主开关**。`true`：执行完整预处理（生成/加载模糊记忆 + 地点资产富化 + 写冻结快照 `asset_snapshot.json`）。`false`：跳过全部预处理，只做地点文档规范化，快照标记 `{enabled:false}`，不生成记忆也不生成参考 POI。 |
| `ensure_fuzzy_memory` | boolean | `true` | `true`：生成模糊长期记忆摘要（`monthly_summaries.json` / `cumulative_summaries.json`），已存在则直接复用。`false`：跳过，仿真中的模糊记忆为空。 |
| `ensure_location_opportunity_pool` | boolean | `true` | `true`：用地图 + LLM 为人物预生成「同城参考 POI」（需 `map_tool.api_key` 与 `llm.api_key` 都非空，否则静默降级为仅规范化）。`false`：不做富化，地点资产只保留规范化结果。 |
| `freeze_for_run` | boolean | `true` | 仅控制写入快照的 `frozen` 元数据标记。**注意**：该标记当前只被记录（`mind.asset_snapshot`），下游代码并未据此改变行为，实际无运行时开关效果。 |
| `strict_anchor_validation` | boolean | `true` | `true`：地点资产缺少可用核心锚点（`anchors` 为空）时抛出异常、停止创建日期分片。`false`：即使无锚点也继续（问题会推迟到后续阶段才暴露）。 |
| `allow_partial_optional_pois` | boolean | `true` | 地点池构建失败时的处理。`true`：降级为规范化地点，并在 manifest 里记录 `partial_failures`，不中断。`false`：构建失败直接抛异常、中止本次运行。 |

---

## 3. `trajectory_assignment` — 地点分配与轨迹生成

核心段，控制如何把每日事件计划落成带真实坐标、通行时间的地点链。

### 3.1 主开关与模式

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enabled` | boolean | `true` | **地理分配主开关**，决定走哪条生成链路。<br>`true`：完整链路——结构化停留意图（带校验重试）→ EPR/重力候选排序 → 预算筛选 → 行程协调，产出**结构化轨迹**（每站带真实坐标、腿带 distance/duration），并导出半小时位置。<br>`false`：退化链路——只做**单次** LLM 调用输出 `instruction`，经 `maptools` 转成**简化的 POI 路线字符串**；跳过 EPR/预算/协调与半小时导出，也不做结构校验重试。 |
| `allocation_mode` | string | `"full"` | 地点分配算法，仅当 `enabled=true` 时有意义。<br>`"full"`：数值分配——地图召回候选 → 重力/EPR 打分排序 → 预算筛选 → 行程协调，所有距离/通行时间由代码计算。<br>`"simple"`：朴素基线——由 LLM 配备地理工具**自行解析**每个事件的地点坐标，不做任何代码端数值计算（无 EPR/重力/预算），后续 adjust/回填/半小时导出走 `simple_adjust_trajectory`。 |
| `feedback_mode` | string | `"on"` | 无反馈基线开关，**仅叠加在 `allocation_mode="simple"` 上生效**。<br>`"on"`（默认）：主观思考与客观事件生成的 prompt 里**注入移动统计**（`behavior_history` 行为摘要、`trajectory_location_history` 地点注册表、当日移动软画像），人物近期移动模式会影响「今天打算做什么」。<br>`"none"`：临时置空这两个反馈载体并改用「无移动版」模板，使思考**只由 persona / plan / memory / state / environment 驱动**，完全不受近期移动轨迹影响；反思/记忆叙事通道与地理分配不受影响。 |

### 3.2 候选与预算

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `seed` | integer | `0` | 候选选择的全局随机种子，与人物 ID、日期共同决定可复现的抽样结果。 |
| `candidate_limit` | integer | `18` | 每个非固定停留点召回的地图候选上限。调大→候选更丰富但地图调用更多。 |
| `route_top_k` | integer | `6` | 进入真实路线 / 重力模型计算的前 k 个候选。 |
| `budget_aware` | boolean | `true` | `true`：用当日剩余距离与通行时间软预算约束候选——超预算的非必选候选被剔除/降权；必选地点（`must_return`）只告警、不删除。`false`：不做预算约束，候选纯按重力/EPR 分数选。 |
| `intent_retry_count` | integer | `2` | 生成停留意图（stop intent）JSON 未通过校验时的局部重试次数。`0` = 只尝试一次。 |

### 3.3 校验与重试

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `strict_validation` | boolean | `true` | `true`：地理分配或最终行程不完整时**抛异常 → 当日失败 → 引擎整日重试**，禁止静默回退为「成功」数据。`false`：失败时静默降级（退回简化路线字符串或空结果），不触发整日重试。 |
| `accuracy_validation` | boolean | `false` | 是否启用**外部精度**校验。`true`：额外检查城市标签是否一致、`llm_plausible` 兜底停留点、地图已验证的通行腿。`false`：只做结构校验（坐标是否存在、腿是否连通、行程是否完整），忽略这些外部精度标签。 |
| `final_itinerary_retry_count` | integer | `1` | 最终地点—通行链无法完整解析时的额外 LLM 重试次数（总尝试 = 该值 + 1）。 |

### 3.4 `half_hour_export` — 半小时位置导出

从最终协调后的唯一地理事实，导出一天 48 个半小时粒度位置样本。

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enabled` | boolean | `true` | `true`：把当天轨迹按半小时网格导出为 JSONL（`sim/half_hour/half_hour_*.jsonl`，含经纬度、GCJ-02/WGS-84 双坐标系）。`false`：跳过导出。 |
| `slot_minutes` | integer | `30` | 采样网格步长（分钟）。`30` → 每天 48 个槽位。 |

### 3.5 `mobility_calibration` — 移动画像 / EPR 参数先验

EPR（exploration-preferential-return，探索-偏回访）模型的人群先验。这些值**不是硬覆盖**：随着个人历史增加，会按 `personalization_weight` 逐渐吸收个人观测，最终在 `[先验, 经验值]` 间混合。下表给出取值方向与效果。

| 配置项 | 类型 | 默认值 | 取值范围 | 说明（调大/调小的效果） |
|--------|------|--------|----------|------|
| `rho` | float | `0.52` | 0.10–0.90 | 探索概率基础先验。**调大**→人物更爱去新地点；**调小**→更倾向回访已知地点。 |
| `gamma` | float | `0.24` | 0.05–0.80 | 探索概率对去重地点数的衰减指数。**调大**→地点越多时探索概率降得越快，越早转入回访。 |
| `return_exponent` | float | `0.85` | 0.50–1.80 | 回访候选权重中「访问频次」的幂指数。**调大**→高频地点回访权重更占优。 |
| `distance_beta` | float | `1.60` | 0.80–2.50 | 距离核（截断幂律）的幂指数。**调大**→远距离候选惩罚更重，越偏好就近。 |
| `distance_cutoff_km` | float | `24.0` | 5–150 | 距离核的指数截止（km）。**调大**→更能容忍远距离目的地。 |
| `distance_cutoff_multiplier` | float | `3.0` | 1.5–6.0 | 经验截止值 = 特征单程距离 × 该乘数。 |
| `epr_count_scope` | string | `"blended"` | `global` / `context` / `blended` | 探索概率中去重地点数 D 的口径：`global` 用全局可回访数，`context` 用当前回访池大小，`blended` 几何混合两者。 |
| `epr_global_count_weight` | float | `0.35` | 0–1 | `blended` 口径下全局数量的权重（`1` 退化为 `global`，`0` 退化为 `context`）。 |
| `urban_candidate_share` | float | `0.35` | 0.15–0.70 | 偏好为「城区」时保留的候选比例。 |
| `personalization_weight` | float | `0.50` | 0–1 | 个人历史覆盖先验的强度上限（随观测天数 / 30 渐进吸收）。**调大**→个体差异更快显现；**调小**→更依赖人群先验。 |
| `selection_temperature` | float | `0.75` | 0.25–2.0 | 候选排序抽样温度。**调大**→更随机（接近均匀）；**调小**→更确定（趋近贪心取最高权重）。 |
| `preference_boost` | float | `1.5` | 0–4 | 对「偏好候选」的权重倍增幅度。**调大**→越尊重人物的地点偏好。 |
| `repetition_fatigue_step` | float | `0.10` | 0–0.50 | 每连续复访 1 天，探索概率的提升步长。**调大**→连续去同一地点后更快「腻了」去探索。 |
| `repetition_fatigue_cap` | float | `0.30` | 0–1 | 复访疲劳提升的上限。 |

### 3.6 `mobility_distribution_targets` — 日型抽样权重

工作日 / 休息日的日型（archetype）抽样权重。用于按日期抽取当日移动画像，历史信号只在此基础上温和修正。

**工作日 `weekday_archetype_weights`：**

| 键 | 默认值 | 含义 |
|----|--------|------|
| `low_mobility` | 0.18 | 低流动 / 居家 |
| `routine_commute` | 0.31 | 常规通勤 |
| `commute_with_errand` | 0.22 | 通勤 + 办事 |
| `evening_activity` | 0.14 | 晚间活动 |
| `social_or_leisure` | 0.08 | 社交 / 休闲 |
| `exploratory` | 0.04 | 探索 |
| `citywide_leisure` | 0.03 | 跨城区休闲 |

**休息日 `weekend_archetype_weights`：**

| 键 | 默认值 | 含义 |
|----|--------|------|
| `home_recovery` | 0.23 | 居家恢复 |
| `local_leisure` | 0.24 | 本地休闲 |
| `social_activity` | 0.17 | 社交活动 |
| `exercise_outing` | 0.12 | 运动外出 |
| `exploratory` | 0.08 | 探索 |
| `citywide_leisure` | 0.09 | 跨城区休闲 |
| `long_distance` | 0.07 | 远距离 |

> 权重只要求相对比例有意义，无需归一化为 1；代码会对各键做 `max(0.0, value)` 裁剪。**调大**某日型权重→该类型日子出现得更频繁。

### 3.7 `location_opportunity_pool` — 同城地点灵感池

人物级同城参考 POI 预生成与每日地点灵感抽样参数。

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enabled` | boolean | `true` | `true`：启用地点灵感池（预生成 + 每日抽样）。`false`：跳过，不生成参考 POI 也不做灵感抽样。 |
| `refresh` | boolean | `false` | `true`：**强制重新生成**（忽略缓存）。`false`：输入与生成版本未变则复用缓存。 |
| `preseed_target_count` | integer | `60` | 预生成地点池的目标数量。 |
| `per_query_limit` | integer | `6` | 每次地图搜索的候选上限（代码裁剪到 1–20）。 |
| `daily_familiar_quota` | [int, int] | `[3, 5]` | 每日「熟悉地点」灵感数量的随机区间。 |
| `daily_citywide_quota` | [int, int] | `[3, 6]` | 每日「跨城区地点」灵感数量的随机区间。 |
| `daily_social_quota` | [int, int] | `[0, 1]` | 每日「社交地点」灵感数量的随机区间。 |

---

## 4. `map_tool` — 地图 API

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `api_key` | string | `""` | 地图服务密钥（用于 POI 检索、地理编码、通行信息等）。为空时相关功能（如 `ensure_location_opportunity_pool` 富化）会静默降级。 |

---

## 快速开始

```bash
# 1. 基于模板生成本地配置
cp config/config.example.json config/config.json

# 2. 填写真实密钥（不要提交 config.json）
#   config/config.json
#   ├── llm.api_key     → 你的 LLM 密钥
#   └── map_tool.api_key → 你的地图服务密钥
```
