# Event and QA Generation

Generates daily life events, phone activity records, and associated question-answer pairs.

## Core Files

| File | Description |
| --- | --- |
| `daily_simulator.py` | Daily life simulator and main orchestration. |
| `phone_data_gen.py` | Phone activity data generation. |
| `all_qa_generator.py` | Question-answer pair generation. |
| `draft_gen.py` | Daily draft generation. |
| `data_edit.py` | Data editing and correction. |
| `event_formatter.py` | Event data formatting. |
| `event_schema.csv` | Event schema definition. |

## Subdirectories

| Directory | Description |
| --- | --- |
| `simulation/` | Daily simulation engine with parallel date partitions, geolocation, memory, and reflection. |
| `draft/` | Event outline generation, including graphs, timelines, and refinement. |
| `edit/` | Data editing pipeline with planning, execution, reflection, and critic agents. |
| `phone_generator/` | Phone data generators for chat, calls, health, photos, and other sources. |
| `qa_generator/` | QA generators for single-hop, multi-hop, temporal, conflict, and other question types. |
| `memory_structure/` | Legacy memory structures and memory module. |
| `tools/` | Utilities for event matching, address generation, and Excel-to-CSV conversion. |
| `templates/` | Prompt templates. |
| `local_models/` | Local embedding models, such as all-MiniLM-L6-v2. |
