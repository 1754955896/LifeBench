# Generation Arguments

Runtime JSON configuration is documented in [config/README.md](../config/README.md). The tables below describe CLI arguments; run commands from the repository root.

## Simulation Runner

The following options control the integrated single-person runner, `scripts/run.py`:

| Argument | Description | Default |
|----------|-------------|---------|
| `--base-path` | Directory containing `persona.json` | `fenghaoran/` |
| `--process-path` | Intermediate output directory relative to `base-path`; retain the default for the documented workflow | `process/` |
| `--instance-id` | Persona instance ID | `0` |
| `--max-workers` | Worker limit passed to draft generation and simulation; phone generation uses its own setting | automatic |
| `--year` | Simulation year | `2025` |
| `--months` | Number of months, starting in January (1-12) | `12` |
| `--generate-phone-data` | Generate phone data (0/1) | `1` |
| `--generate-monthly-report` | Generate monthly reports (0/1) | `1` |
| `--generate-qa` | Generate QA data (0/1) | `1` |
| `--interactive` | Interactive draft refinement | off |
| `--no-phone-sample` | Keep all generated phone records without sampling | off |
| `--dry-run` | Write placeholder files without generating | off |

To omit QA generation, add `--generate-qa 0`. Other stage switches assume that any data required by later stages is already available. The batch runner accepts a different set of arguments; see [batch generation](generation.md#batch-generation).

## Persona Generator

The following options control `scripts/run/persona_gen.py`:

| Argument | Description | Default |
|----------|-------------|---------|
| `--file-path` | Directory containing the input and reference files and receiving generated files | `data/persona/` |
| `--ref-file` | Reference database filename, relative to `file-path`; required by both input modes | `profile_ref.json` |
| `--input-file` | Source-record filename, relative to `file-path` | `processed_features.json` |
| `--input-mode` | `canonical` expects structured feature records; `auto` normalizes natural-language descriptions or structured records and preserves explicit facts | `canonical` |
| `--input-format` | Input container format: `auto`, `json`, `jsonl`, `csv`, `tsv`, `txt`, or `xlsx` | `auto` |
| `--start`, `--end` | Zero-based, end-exclusive source-record range | `0`, `1` |
| `--variants-per-input` | Number of persona variants generated from each source record in `auto` mode | `1` |
| `--diversity` | Variant diversity in `auto` mode: `low`, `medium`, or `high` | `high` |
| `--seed` | Seed for local reference sampling and weighted choices | unset |
| `--as-of-date` | Reference date used to derive age and other date-dependent values | `2021-12-31` |
| `--output-file` | Generated persona-list filename, relative to `file-path` | `persona_list.json` |
| `--skip-location-generation` | Skip grounded address generation and the location sidecar | off |

The default range processes only the first source record, so increase `--end` when supplying more records. A fixed `--seed` makes local sampling repeatable, but does not guarantee identical LLM responses, map results, or final profiles across runs. Excel input additionally requires `openpyxl`; a text file is treated as one source record. See the [persona guide](../src/lifebench/persona/README.md) and [persona CLI reference](../scripts/run/README.md#1-persona_genpy-persona-generation) for complete schemas and advanced options.
