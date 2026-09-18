# run 子目录 — 各模块独立运行脚本

支持**分模块独立运行**的数据生成脚本，便于调试和单独执行某个环节，避免每次都从 `persona` 全量重跑。

所有脚本都通过 `python scripts/run/<脚本名>.py [参数]` 运行，参数用 `--参数名 值` 传入（布尔开关用 `--flag` 直接开启）。运行前会各自把项目根目录加入 `sys.path`，因此**从任意目录执行均可**。

## 脚本总览

| 文件 | 说明 |
|------|------|
| [`persona_gen.py`](#1-persona_genpy--人物画像生成) | Persona（人设）生成 |
| [`draft_gen.py`](#2-draft_genpy--年度时间线草稿生成) | 年度时间线草稿（每日大纲）生成 |
| [`phone_gen.py`](#3-phone_genpy--手机数据生成) | 手机数据生成与后处理 |
| [`simulator.py`](#4-simulatorpy--生活模拟器) | 生活模拟器（每日事件 + 事件格式化） |
| [`qa_gen.py`](#5-qa_genpy--问答对生成) | QA（问答对）生成 |

> 典型的数据链路顺序：`persona_gen` → `draft_gen` → `phone_gen` / `simulator` → `qa_gen`（各脚本相互独立，可单跑）。

---

## 1. `persona_gen.py` — 人物画像生成

生成人物画像（persona），支持两种输入模式：旧标准的 `canonical` 特征输入，或用 LLM 规范化**任意输入**（`auto` 模式）。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--file-path` | string | `data/persona/` | 数据文件目录，参考库/输入/输出文件均相对此目录。 |
| `--start` | int | `0` | 开始生成的人物索引（含）。 |
| `--end` | int | `1` | 结束生成的人物索引（不含，即左闭右开 `[start, end)`）。 |
| `--ref-file` | string | `profile_ref.json` | 参考数据库文件名。 |
| `--input-file` | string | `processed_features.json` | 输入特征文件名。 |
| `--output-file` | string | `persona_list.json` | 输出人物画像文件名。 |
| `--as-of-date` | string | `2021-12-31` | 画像年龄等派生值的基准日期。 |
| `--seed` | int | `None` | 参考数据采样的随机种子（`None` 表示不固定）。 |
| `--max-workers` | int | `None` | 并行线程上限（`None` 用默认值）。 |
| `--max-stage-retries` | int | `2` | 单个 LLM 阶段失败时的最大重试次数。 |
| `--keep-checkpoints` | flag | 关 | 保留中间画像文件，便于排查。 |
| `--input-mode` | `canonical`/`auto` | `canonical` | `canonical` 使用旧标准特征输入；`auto` 用 LLM 规范化任意输入。 |
| `--input-format` | string | `auto` | 任意输入的容器格式：`auto`/`json`/`jsonl`/`csv`/`tsv`/`txt`/`xlsx`。 |
| `--variants-per-input` | int | `1` | 每条任意输入生成的差异化画像数量。 |
| `--diversity` | `low`/`medium`/`high` | `high` | 任意输入画像的差异等级。 |
| `--skip-location-generation` | flag | 关 | 跳过画像阶段的真实地址落地与 location sidecar 生成。 |
| `--location-output` | string | `None` | location sidecar 文件名；默认 `<output>_locations.json`。 |
| `--reserved-address-file` | string | `None` | 已有画像或 location JSON，其地址加入占用池，减少跨批次地址重复。 |

---

## 2. `draft_gen.py` — 年度时间线草稿生成

生成一年的时间线草稿（每日大纲），支持分月区间和交互模式。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--base-path` | string | `D:\pyCharmProjects\pythonProject4\tests/tests/data_output/yuxiaowen` | 基础数据路径（须含 `persona.json`）。 |
| `--process-path` | string | `process/` | 处理文件路径，相对 `base-path`，同时作为除每日状态外的其他数据输出路径。 |
| `--instance-id` | int | `0` | 人物实例 ID。 |
| `--max-workers` | int | `None` | 最大工作线程数（默认 CPU 核心数 × 2）。 |
| `--interactive` | flag | 关 | 交互模式：情节优化时迭代与 LLM 交互，直到用户输入包含「结束」。 |
| `--year` | int | `2025` | 生成数据的年份。 |
| `--start-month` | int | `1` | 起始月份，取值 1–12。 |
| `--months` | int | `12` | 从 `start-month` 起连续生成的月数，取值 1–12。 |

---

## 3. `phone_gen.py` — 手机数据生成

生成手机数据（日历/短信/照片/笔记/推送/通话/运动健康/助手对话等），并做后处理（分类、排序、加 `phone_id`）。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--file-path` | string | `D:\pyCharmProjects\pythonProject4\tests/data_output/fenghaoran/fenghaoran/` | 数据文件路径。 |
| `--start-time` | string | `2025-01-01` | 开始日期。 |
| `--end-time` | string | `2025-01-01` | 结束日期。 |
| `--max-workers` | int | `40` | 最大并行线程数。 |
| `--phone-count-min` | int | `2` | 每天手机数据最小条数（采样用）。 |
| `--phone-count-max` | int | `7` | 每天手机数据最大条数（采样用）。 |
| `--phone-count-weekly-max` | int | `30` | 每周手机数据最大条数（采样用）。 |
| `--no-sample` | flag | 关 | 不控制每日条数，保留全部生成数据（跳过采样）。 |
| `--process-only` | flag | 关 | 仅执行数据后处理（分类/排序/加 `phone_id`），不生成新数据。 |

> **采样逻辑**：默认每天按 `[phone-count-min, phone-count-max]` 随机抽样，超 `phone-count-weekly-max` 的周按比例压缩。`--no-sample` 跳过该约束。

---

## 4. `simulator.py` — 生活模拟器

生活模拟器：生成每日事件（含真实地理匹配）并格式化事件。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--file-path` | string | `data/fenghaoran/` | 数据文件路径。 |
| `--start-date` | string | `2025-01-01` | 开始日期。 |
| `--end-date` | string | `2025-12-31` | 结束日期。 |
| `--max-workers` | int | `30` | 最大并行线程数。 |
| `--interval-days` | int | `13` | 每个线程处理的天数。 |
| `--generate-data` | int | `1` | 是否生成数据（`1` 生成，`0` 跳过）。 |
| `--format-events` | int | `1` | 是否格式化事件（`1` 格式化，`0` 跳过）。 |
| `--instance-id` | int | `0` | 人物实例 ID。 |
| `--real-geo` | int | `1` | 是否开启真实地理匹配（`1` 开启；`0` 关闭，跳过真实地理搜索，由 LLM 在 adjust 阶段统一分配地点）。 |

---

## 5. `qa_gen.py` — 问答对生成

从时间线数据生成各类问答对（QA）。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--data-path` | string | `D:\pyCharmProjects\pythonProject4\tests/tests/data_output/yuxiaowen/` | 用户数据路径，需含 `persona.json`、`event_tree.json` 等文件。 |
| `--year` | int | `2025` | 生成问答的年份。 |

> 若 `process/rich_timeline.json` 存在，会自动加载其中的 `same_theme_arr`（主题）与 `frequency_id_groups`（事件组）用于多跳/关联类问题。
