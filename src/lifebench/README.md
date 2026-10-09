# LifeBench Package

Core modules for data generation.

## Modules

| Directory | Description |
| --- | --- |
| `event/` | Event and QA generation, including schedules, phone data, and question-answer pairs. |
| `persona/` | Persona generation and management. |
| `utils/` | Shared LLM, I/O, and map utilities. |
| `memory_file/` | Memory data files. |

## Event Subdirectories

| Directory | Description |
| --- | --- |
| `simulation/` | Daily simulation engine with parallel date partitions, geolocation, memory, and reflection. |
| `draft/` | Event outline generation, including graphs, timelines, and refinement. |
| `edit/` | Data editing pipeline with planning, execution, reflection, and critic agents. |
| `phone_generator/` | Phone data generators for chat, calls, health, photos, and other sources. |
| `qa_generator/` | QA generators for single-hop, multi-hop, temporal, conflict, and other question types. |
| `memory_structure/` | Legacy memory structures and memory module. |
| `tools/` | Utilities for event matching, address generation, and Excel-to-CSV conversion. |
| `templates/` | Prompt templates; see [templates/README.md](event/templates/README.md). |
| `local_models/` | Local embedding models, such as all-MiniLM-L6-v2. |
