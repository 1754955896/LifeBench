# geolocation 子目录 — 约束式地理位置分配

V1 事件模拟的约束式地理位置分配：把每日事件计划落成带真实坐标、交通方式与通行时间的地点链，并把最终统一地理事实导出为事件可消费的 sidecar。

## 核心文件

| 文件 | 说明 |
|------|------|
| `allocator.py` | `TrajectoryAllocator` — 按停留顺序联合选择地点、交通方式与通行时间。 |
| `selector.py` | 确定性的 EPR-lite + 重力模型候选排序。 |
| `candidate_provider.py` | 候选地点召回：画像目录优先，探索地点由地图 API 提供。 |
| `catalog.py` | 将画像地址归一化为可复用地点目录（`flatten_location_data`）。 |
| `epr.py` | `EPRProfile` / `build_personal_epr_profile` — 个体化 exploration-preferential-return 参数。 |
| `mode.py` | 画像约束下的交通方式选择和地图时长查询。 |
| `models.py` | 轨迹分配使用的稳定数据结构（`TrajectoryAssignment`、`PlausibleLocationSpec`）。 |
| `intent_adapter.py` | `parse_stop_intents` — 把新版停留意图和旧版 instruction JSON 统一成 StopIntent。 |
| `reconciliation.py` | 将轨迹调整后的最终地点与移动链合并进地理 sidecar。 |
| `injection.py` | `render_assignment_summary` — 把结构化分配渲染为供下游 LLM 优先采用的轨迹参考。 |
| `export.py` | `attach_event_geodata` / `build_location_records` — 将轨迹分配转为最终事件可消费的地理 sidecar。 |
| `registry.py` | 跨日地点注册表：让同一语义地点稳定复用 location_id 与坐标。 |
| `timeslot.py` | `build_half_hour_trajectory` — 把最终统一地理事实导出为一天 48 个半小时位置样本。 |
| `validator.py` | 轨迹结构与数值完整性检查（不做关键词推断或改写 LLM 叙事）。 |
| `coordinates.py` | 坐标系转换：GCJ-02 与 WGS-84 对比/互转。 |
| `baseline.py` | simple 基线 v3：LLM 配备地理工具（function calling）的 agentic 地理分配。 |
