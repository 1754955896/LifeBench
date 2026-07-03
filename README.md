# LifeBench: A Benchmark for Long-Horizon Multi-Source Memory

LifeBench is a benchmark designed for evaluating personalized agent memory systems. It comprises:
- Detailed character profile data
- A full-year dataset covering all daily life activities of individuals
- Digital trace (mobile phone operation) data corresponding to real-life scenarios
- Associated question-answering data

The main objectives of our dataset are as follows:

1. **Challenging and comprehensive question-answering and online interaction tasks** (with interleaved memory augmentation, memory retrieval, and answering)
2. **Long-term, realistic and rich personal life data and digital traces**
3. **Automated pipeline** for data generation and question design, supporting large-scale applications

## Overview
![LifeBench Overview](pic/PIC_INTRO.png)
Existing benchmarks mainly focus on dialogue scenarios and lack diverse digital traces. Furthermore, current datasets do not cover continuous, long-term life sequences of an individual, but only concentrate on major events. In contrast, we model continuous data that covers an individual's entire life over the course of one year.


### Question Categories

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

## Dataset

The dataset can be found in the `life_bench_data/version1` folder, available in both English and Chinese versions. The dataset contains data from 10 users, with each user having the following files:

- **`phone_data`**: Mobile phone operation data
- **`QA`**: Question-answering data
- **`summary`**: Monthly summaries
- **`daily_event.json`**: Daily activities
- **`location.json`**: Real city addresses
- **`persona.json`**: User profile
- **`daily_draft.json`**: Daily granular outline

### Memory Benchmark Support

For the convenience of conducting memory benchmark tests on existing memory systems (primarily for locomo), we have converted the QA data into the locomo input format. 

## Usage
![Data Synthesis Framework](pic/pic.png)

### Environment Configuration

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
       "reason_model": "deepseek-v4-pro"
     },
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
   | `map_tool.api_key` | Map API key (for address generation) | No |

   **支持任意兼容 OpenAI API 格式的 LLM 服务商**（如 DeepSeek、Claude、GPT-4 等），通过配置不同的 `base_url` 和 `model` 即可切换。

   **模型选择策略**：`default_model` 和 `reason_model` 的设计是为了**减少生成成本**。
   - 简单任务（短上下文、非复杂推理）：自动调用 `default_model`
   - 长上下文任务（复杂推理、多步骤生成）：自动调用 `reason_model`
   - 若不想区分，可将两个字段配置为**同一个 model**

### Data Preparation

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

### Running

#### Batch Mode

```bash
# Run the complete generation pipeline (process all personas in input/person.json)
python run_all.py

# Specify persona ID range
python run_all.py --start-id 1 --end-id 5

# Generate phone data only, skip QA generation
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
python run/simulator.py --base-path output/fenghaoran

# 3. Generate phone operation data
python run/phone_gen.py --base-path output/fenghaoran

# 4. Generate question-answer pairs
python run/qa_gen.py --base-path output/fenghaoran
```


### Command Line Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `--base-path` | Base data path | `fenghaoran/` |
| `--process-path` | Process file path (relative) | `process/` |
| `--instance-id` | Persona instance ID | `0` |
| `--max-workers` | Max worker threads | `CPU cores × 2` |
| `--generate-phone-data` | Generate phone data (0/1) | `1` |
| `--generate-monthly-report` | Generate monthly reports (0/1) | `1` |
| `--generate-qa` | Generate QA data (0/1) | `1` |
| `--year` | Year for generated data | `2025` |

## Directory Structure

```
lifebench/
├── config/
│   ├── config.example.json    # Config template
│   └── config.json           # Actual config (create manually)
├── input/
│   └── person.json           # Input persona data
├── output/                    # Generated data output
│   └── {pinyin_name}_id/    # Per-person folder
│       ├── persona.json      # User persona
│       ├── daily_draft.json   # Daily drafts
│       ├── daily_event.json   # Daily events
│       ├── event_tree.json    # Event tree
│       ├── location.json      # Location data
│       ├── phone_data/        # Phone operation data
│       │   ├── sms.json
│       │   ├── call.json
│       │   ├── calendar.json
│       │   ├── note.json
│       │   ├── photo.json
│       │   ├── push.json
│       │   ├── agent_chat.json
│       │   └── fitness_health.json
│       ├── QA_all/            # QA data aggregation
│       │   └── QA.json
│       └── process/          # Intermediate files
├── scripts/
│   ├── run_all.py           # Batch runner
│   ├── run.py               # Integrated generator
│   └── run/                  # Step-by-step scripts
│       ├── persona_gen.py
│       ├── draft_gen.py
│       ├── simulator.py
│       ├── phone_gen.py
│       └── qa_gen.py
├── src/lifebench/
│   ├── event/
│   │   ├── draft/           # Draft generation
│   │   ├── edit/            # Edit interface
│   │   ├── memory_structure/ # Memory structure
│   │   ├── phone_generator/  # Phone data generator
│   │   ├── qa_generator/    # QA generator
│   │   ├── templates/        # Templates
│   │   └── tools/           # Utilities
│   ├── persona/             # Persona module
│   └── utils/               # Helper functions
├── tests/                   # Test data
├── requirements.txt
└── README.md
```

## Checkpoint

The pipeline supports resumable execution. Intermediate results are saved to base_path directory.

### Checkpoints by Stage

| Stage | Output Directory | Check File | Description |
|-------|-----------------|------------|-------------|
| **1. persona_gen** | `{base_path}/` | `persona.json` | User persona data |
| **2. draft_gen** | `{base_path}/process/` | `daily_draft.json` | Daily draft data |
| **3. simulator** | `{base_path}/process/` | `event_tree.json`, `daily_event.json` | Simulated events |
| **4. phone_gen** | `{base_path}/phone_data/` | `contact.json` | Phone operation data |
| **5. qa_gen** | `{base_path}/QA_all/` | `QA.json` | Merged QA data |

### Resume Mechanism

- `run.py` automatically checks for existing files in `base_path/`
- If critical files exist, the corresponding stage is skipped
- To force regeneration, delete the files in the corresponding directory
