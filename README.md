# LifeBench: A Benchmark for Long-Horizon Multi-Source Memory

[![🤗 Hugging Face Dataset](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Dataset-orange?style=flat-square)](https://huggingface.co/datasets/C1754955896/Lifebenchv2.0)
[![arXiv](https://img.shields.io/badge/arXiv-2603.03781-b31b1b?style=flat-square)](https://arxiv.org/abs/2603.03781)

LifeBench is a benchmark designed for evaluating personalized agent memory systems. It comprises:
- Detailed character profile data
- A full-year dataset covering all daily life activities of individuals
- Digital trace (mobile phone operation) data corresponding to real-life scenarios
- Associated question-answering data

The main objectives of our dataset are as follows:

1. **Challenging and comprehensive question-answering and online interaction tasks** (with interleaved memory augmentation, memory retrieval, and answering)
2. **Long-term, realistic and rich personal life data and digital traces**
3. **Automated pipeline** for data generation and question design, supporting large-scale applications

## 🌐 Overview
![LifeBench Overview](pic/PIC_INTRO.png)
Existing benchmarks mainly focus on dialogue scenarios and lack diverse digital traces. Furthermore, current datasets do not cover continuous, long-term life sequences of an individual, but only concentrate on major events. In contrast, we model continuous data that covers an individual's entire life over the course of one year.


### 🧩 Question Categories

LifeBench contains 9 categories of questions:

| Question Category | English Name | Description |
|-------------------|--------------|-------------|
| **Single-hop Reasoning** | Single_hop | Direct information extraction questions based on a single event or mobile phone operation record |
| **Multi-hop Reasoning** | Multi_hop | Complex questions requiring integration of multiple event information and multi-source data correlation analysis |
| **Temporal Reasoning** | Temporal | Questions involving analysis of time dimensions such as event chronology, time intervals, and frequency |
| **Non-declarative Memory** | Non-declarative | Questions identifying user behavior patterns, habit preferences, personality traits, and other patterned information |
| **Knowledge Update Reasoning** | Knowledge_update | Questions tracking changes in user knowledge, hobbies, status, etc. over time, assessing memory update capability |
| **Causal Reasoning** | Causal | Questions analyzing causal relationships between events, behavioral triggers, and chain reactions |
| **Conflict Detection** | Conflict | Questions identifying logical contradictions and time conflicts in mobile data or information |
| **Hidden Information Mining** | Hidden_info | Questions extracting implicit information through correlation analysis of multi-source data |
| **Unanswerable** | Unanswerable | Questions that cannot be answered based on existing data, used for evaluating model refusal capability |

Each question contains: question content, answer, score points (for evaluation), required event IDs, ask time, and other fields.

## 📦 Dataset

The dataset is available on the Hugging Face Hub:

- 🤗 **LifeBench v2.0** — [https://huggingface.co/datasets/C1754955896/Lifebenchv2.0](https://huggingface.co/datasets/C1754955896/Lifebenchv2.0)

It is also included in this repository under [`life_bench_data/version2/`](life_bench_data/version2/), available in both Chinese (`data/`) and English (`data_en/`) versions. The dataset contains data from 10 users; each user has the following files:

- **`persona.json`**: User profile
- **`daily_event.json`**: Daily activities
- **`event_tree.json`**: Hierarchical event tree
- **`daily_draft.json`**: Daily granular outline
- **`phone_data/`**: Mobile phone operation data (9 sources: sms, call, calendar, note, photo, push, fitness_health, contact, agent_chat)
- **`QA_all/QA.json`**: Question-answering data

### 🧠 Memory Benchmark Support

For the convenience of conducting memory benchmark tests on existing memory systems (primarily for locomo), we have converted the QA data into the locomo input format. 

## 🚀 Usage
![Data Synthesis Framework](pic/pic.png)

### ⚙️ Environment Configuration

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Embedding Model Preparation** (Optional, for memory system)
   Download embedding models to `src/lifebench/event/local_models/` for local similarity search:

   ```bash
   pip install huggingface-hub
   huggingface-cli download sentence-transformers/all-MiniLM-L6-v2 --local-dir src/lifebench/event/local_models/all-MiniLM-L6-v2
   ```


3. **Configuration File**
   - Create `config/config.json` (copy from `config.example.json`)
   - Configure LLM API and map API keys

   ```json
   {
     "llm": {
       "api_key": "your_api_key_here",
       "base_url": "https://api.deepseek.com",
       "default_model": "deepseek-v4-flash",
       "reason_model": "deepseek-v4-pro",
       "strip_think": false
     },
     "simulation_asset_preparation": { "enabled": true, "...": "..." },
     "trajectory_assignment": { "enabled": true, "...": "..." },
     "map_tool": {
       "api_key": "your_map_api_key_here"
     }
   }
   ```

   | Config Key | Description | Required |
   |------------|-------------|----------|
   | `llm.api_key` | LLM API key | Yes |
   | `llm.base_url` | LLM API endpoint (support OpenAI-compatible format) | Yes |
   | `llm.default_model` | Default model for general generation | No |
   | `llm.reason_model` | Reasoning model for complex tasks | No |
   | `llm.strip_think` | Strip `<think>…</think>` from reasoning-model output | No |
   | `simulation_asset_preparation` | Shared-asset preprocessing (fuzzy memory, POI pool) | No |
   | `trajectory_assignment` | Location/trajectory generation parameters | No |
   | `map_tool.api_key` | Map API key (for address generation) | No |

   > **Full configuration reference**: see [`config/README.md`](config/README.md) for every option and its default.

   **Supports any LLM provider compatible with the OpenAI API format** (e.g., DeepSeek, Claude, GPT-4) by configuring different `base_url` and `model` values.

   **Model Selection Strategy**: `default_model` and `reason_model` are designed to **reduce generation costs**.
   - Simple tasks (short context, non-complex reasoning): automatically call `default_model`
   - Long-context tasks (complex reasoning, multi-step generation): automatically call `reason_model`
   - If you do not want to differentiate, configure both fields as the **same model**

### 🛠️ Data Preparation

#### Batch Mode Data Preparation

Merge all persona data into an array and save to `input/person.json`:

```json
[
  {
    "name": "Zhang San",
    "age": 30,
    ...
  },
  {
    "name": "Li Si",
    "age": 25,
    ...
  }
]
```

#### Single Persona Data Preparation

Create a persona folder under `output` and place the persona data:

```
output/
└── fenghaoran/           # Persona folder
    └── persona.json      # Persona data
```

### ▶️ Running

#### Batch Mode

```bash
# Run the complete generation pipeline (process all personas in input/person.json)
python run_all.py

# Specify persona ID range
python run_all.py --start-id 1 --end-id 5

# Skip QA generation (phone data, monthly reports, etc. are still generated)
python run_all.py --generate-qa 0
```

#### Single Persona Mode

**Run all at once with run.py:**

```bash
cd scripts
python run.py --base-path output/fenghaoran
```

**Run step by step:**

```bash
cd scripts

# 1. Generate daily event drafts
python run/draft_gen.py --base-path output/fenghaoran

# 2. Simulate daily activities
python run/simulator.py --file-path output/fenghaoran/

# 3. Generate phone operation data
python run/phone_gen.py --file-path output/fenghaoran/

# 4. Generate question-answer pairs
python run/qa_gen.py --data-path output/fenghaoran/
```

> Each step accepts additional arguments — see [`scripts/run/README.md`](scripts/run/README.md) for the full list.


### 🎛️ Command Line Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `--base-path` | Base data path | `fenghaoran/` |
| `--process-path` | Process file path (relative to `base-path`) | `process/` |
| `--instance-id` | Persona instance ID | `0` |
| `--max-workers` | Max worker threads | auto (CPU cores × 2) |
| `--generate-phone-data` | Generate phone data (0/1) | `1` |
| `--generate-monthly-report` | Generate monthly reports (0/1) | `1` |
| `--generate-qa` | Generate QA data (0/1) | `1` |
| `--year` | Year for generated data | `2025` |
| `--months` | Number of months to generate | `12` |
| `--interactive` | Interactive draft optimization | off |
| `--no-phone-sample` | Keep all generated phone data (skip sampling) | off |
| `--dry-run` | Write placeholder files without generating | off |

`run_all.py` additionally accepts `--persona-folder` (default `input/`), `--start-id`, `--end-id`, and `--dry-run`.

## 📁 Directory Structure

```
lifebench/
├── config/
│   ├── config.example.json    # Config template (all options + defaults)
│   └── config.json            # Actual config (create manually; not committed)
├── input/
│   └── person.json            # Input persona data (batch mode)
├── output/                    # Generated data output
│   └── {pinyin}_{id}/         # Per-person folder (e.g. feng_haoran_1)
│       ├── persona.json       # User persona
│       ├── daily_draft.json   # Daily drafts
│       ├── daily_event.json   # Daily events
│       ├── event_tree.json    # Event tree
│       ├── location.json      # Location data
│       ├── phone_data/        # Phone operation data
│       │   ├── sms.json
│       │   ├── call.json
│       │   ├── calendar.json
│       │   ├── contact.json
│       │   ├── note.json
│       │   ├── photo.json
│       │   ├── push.json
│       │   ├── agent_chat.json
│       │   └── fitness_health.json
│       ├── summary/           # Monthly health reports
│       ├── QA_all/            # QA data aggregation
│       │   └── QA.json
│       └── process/           # Intermediate files
├── scripts/
│   ├── run_all.py             # Batch runner
│   ├── run.py                 # Integrated generator
│   └── run/                   # Step-by-step scripts
│       ├── persona_gen.py
│       ├── draft_gen.py
│       ├── simulator.py
│       ├── phone_gen.py
│       └── qa_gen.py
├── src/lifebench/
│   ├── event/
│   │   ├── draft/             # Draft generation
│   │   ├── edit/              # Edit interface
│   │   ├── local_models/      # Local embedding models
│   │   ├── memory_structure/  # Memory structure
│   │   ├── phone_generator/   # Phone data generator
│   │   ├── qa_generator/      # QA generator
│   │   ├── simulation/        # Life simulation engine
│   │   ├── templates/         # Templates
│   │   └── tools/             # Utilities
│   ├── memory_file/           # Temporary memory files (cleaned after run)
│   ├── persona/               # Persona module
│   └── utils/                 # Helper functions
├── life_bench_data/           # Released dataset (version1 / version2)
├── tests/                     # Test data
├── requirements.txt
├── pyproject.toml
└── README.md
```

## 💾 Checkpoint

The pipeline supports resumable execution. Intermediate results are saved to base_path directory.

### 📋 Checkpoints by Stage

| Stage | Check File | Description |
|-------|-----------|-------------|
| **1. draft_gen** | `{base_path}/daily_draft.json` | Daily draft data |
| **2. simulator** | `{base_path}/daily_event.json` | Simulated daily events (also `event_tree.json`) |
| **3. event_matching** | — (always runs) | Adds match fields to events |
| **4. monthly_report** | `{base_path}/summary/all_monthly_health_reports.json` | Monthly health reports |
| **5. phone_gen** | `{base_path}/phone_data/contact.json` | Phone operation data |
| **6. qa_gen** | `{base_path}/QA_all/QA.json` | Merged QA data |

> `persona_gen` is a separate pre-step that produces `input/person.json` for batch mode; it is not part of `run.py`'s per-person flow.

### 🔁 Resume Mechanism

- `run.py` automatically checks for existing files in `base_path/`
- If critical files exist, the corresponding stage is skipped
- To force regeneration, delete the files in the corresponding directory

## 📖 Citation

If you use LifeBench in your research, please cite our paper and dataset:

- 📄 **Paper**: [arXiv:2603.03781](https://arxiv.org/abs/2603.03781)
- 🤗 **Dataset**: [C1754955896/Lifebenchv2.0](https://huggingface.co/datasets/C1754955896/Lifebenchv2.0)
