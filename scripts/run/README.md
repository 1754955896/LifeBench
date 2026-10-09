# Standalone Generation Scripts

These scripts run individual stages of data generation for debugging or targeted execution without rerunning the entire pipeline from persona generation.

From the repository root, run `python scripts/run/<script>.py [arguments]`. Pass values as `--argument value` and enable boolean switches with `--flag`. Each script adds the repository root to `sys.path`; relative data paths still follow that script's path-handling rules.

First install the dependencies and configure the APIs as described in the [main README](../../README.md#-environment-configuration). Use the scripts directly from the cloned repository; no LifeBench package installation is required. Pass your own data directory explicitly instead of relying on machine-specific defaults.

## Script Overview

| File | Description |
|------|-------------|
| [`persona_gen.py`](#1-persona_genpy-persona-generation) | Persona generation. |
| [`draft_gen.py`](#2-draft_genpy-timeline-draft-generation) | Annual timeline and daily draft generation. |
| [`phone_gen.py`](#3-phone_genpy-phone-data-generation) | Phone data generation and post-processing. |
| [`simulator.py`](#4-simulatorpy-life-simulation) | Daily event simulation and formatting. |
| [`qa_gen.py`](#5-qa_genpy-question-answer-generation) | Question-answer pair generation. |

> Typical pipeline order: `persona_gen` -> `draft_gen` -> `simulator` -> `phone_gen` -> `qa_gen`. Each script can run independently when its input data is available.

---

## 1. `persona_gen.py`: Persona Generation

Generates personas with two input modes: legacy `canonical` features, or arbitrary input normalized by an LLM in `auto` mode.

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--file-path` | string | `data/persona/` | Data directory; reference, input, and output filenames are relative to it. |
| `--start` | int | `0` | First persona index, inclusive. |
| `--end` | int | `1` | End persona index, exclusive: `[start, end)`. |
| `--ref-file` | string | `profile_ref.json` | Reference database filename. |
| `--input-file` | string | `processed_features.json` | Input features filename. |
| `--output-file` | string | `persona_list.json` | Output persona filename. |
| `--as-of-date` | string | `2021-12-31` | Reference date for age and other derived persona values. |
| `--seed` | int | `None` | Reference sampling seed; `None` leaves it unfixed. |
| `--max-workers` | int | `None` | Maximum parallel threads; `None` uses the default. |
| `--max-stage-retries` | int | `2` | Maximum retries for a failed LLM stage. |
| `--keep-checkpoints` | flag | off | Retains intermediate persona files for debugging. |
| `--input-mode` | `canonical`/`auto` | `canonical` | `canonical` uses legacy feature input; `auto` normalizes arbitrary input with an LLM. |
| `--input-format` | string | `auto` | Input container format: `auto`/`json`/`jsonl`/`csv`/`tsv`/`txt`/`xlsx`. |
| `--variants-per-input` | int | `1` | Number of distinct personas generated per arbitrary input record. |
| `--diversity` | `low`/`medium`/`high` | `high` | Diversity level for arbitrary-input personas. |
| `--skip-location-generation` | flag | off | Skips real-world address grounding and location sidecar generation during persona generation. |
| `--location-output` | string | `None` | Location sidecar filename; defaults to `<output>_locations.json`. |
| `--reserved-address-file` | string | `None` | Existing persona or location JSON whose addresses are reserved to reduce reuse across batches. |

---

## 2. `draft_gen.py`: Timeline Draft Generation

Generates annual timeline drafts and daily outlines, with configurable month ranges and interactive refinement.

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--base-path` | string | `D:\pyCharmProjects\pythonProject4\tests/tests/data_output/yuxiaowen` | Base data directory, which must contain `persona.json`. |
| `--process-path` | string | `process/` | Processing directory relative to `base-path`; also stores outputs other than daily state. |
| `--instance-id` | int | `0` | Persona instance ID. |
| `--max-workers` | int | `None` | Maximum worker threads; defaults to CPU cores multiplied by two. |
| `--interactive` | flag | off | Iterative plot refinement with the LLM. Stops when user input contains the two-character Chinese stop phrase, Unicode `U+7ED3 U+675F` (meaning "finish"). |
| `--year` | int | `2025` | Year to generate. |
| `--start-month` | int | `1` | Starting month, from 1 to 12. |
| `--months` | int | `12` | Number of consecutive months from `start-month`, from 1 to 12. |

---

## 3. `phone_gen.py`: Phone Data Generation

Generates calendar entries, SMS, photos, notes, push notifications, calls, fitness/health records, assistant conversations, and other phone data. Post-processing classifies and sorts records and adds `phone_id`.

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--file-path` | string | `D:\pyCharmProjects\pythonProject4\tests/data_output/fenghaoran/fenghaoran/` | Data directory. |
| `--start-time` | string | `2025-01-01` | Start date. |
| `--end-time` | string | `2025-01-01` | End date. |
| `--max-workers` | int | `40` | Maximum parallel threads. |
| `--phone-count-min` | int | `2` | Minimum daily record count for sampling. |
| `--phone-count-max` | int | `7` | Maximum daily record count for sampling. |
| `--phone-count-weekly-max` | int | `30` | Maximum weekly record count for sampling. |
| `--no-sample` | flag | off | Keeps all generated records without daily count sampling. |
| `--process-only` | flag | off | Only classifies, sorts, and adds `phone_id`; does not generate new data. |

> By default, daily sampling draws a count from `[phone-count-min, phone-count-max]`. Weeks exceeding `phone-count-weekly-max` are proportionally reduced. `--no-sample` skips these constraints.

---

## 4. `simulator.py`: Life Simulation

Generates daily events with real-world geographic matching and formats the resulting events.

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--file-path` | string | `data/fenghaoran/` | Data directory. |
| `--start-date` | string | `2025-01-01` | Start date. |
| `--end-date` | string | `2025-12-31` | End date. |
| `--max-workers` | int | `30` | Maximum parallel threads. |
| `--interval-days` | int | `13` | Number of days processed per thread. |
| `--generate-data` | int | `1` | Generate data (`1`) or skip generation (`0`). |
| `--format-events` | int | `1` | Format events (`1`) or skip formatting (`0`). |
| `--instance-id` | int | `0` | Persona instance ID. |
| `--real-geo` | int | `1` | `1` enables real-world geographic matching. `0` skips real geographic searches and lets the LLM assign locations during adjustment. |

---

## 5. `qa_gen.py`: Question-Answer Generation

Generates different types of question-answer pairs from timeline data.

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--data-path` | string | `D:\pyCharmProjects\pythonProject4\tests/tests/data_output/yuxiaowen/` | User data directory containing `persona.json`, `event_tree.json`, and other required files. |
| `--year` | int | `2025` | Year for question generation. |

> If `process/rich_timeline.json` exists, the script loads `same_theme_arr` (themes) and `frequency_id_groups` (event groups) for multi-hop and related questions.
