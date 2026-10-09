# LifeBench: A Benchmark for Long-Horizon Multi-Source Memory

[![🤗 Hugging Face Dataset](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Dataset-orange?style=flat-square)](https://huggingface.co/datasets/C1754955896/Lifebenchv2.0)
[![arXiv](https://img.shields.io/badge/arXiv-2603.03781-b31b1b?style=flat-square)](https://arxiv.org/abs/2603.03781)
[![GitHub](https://img.shields.io/badge/GitHub-LifeBench__eval-181717?style=flat-square&logo=github)](https://github.com/1754955896/LifeBench_eval)

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
Existing benchmarks mainly focus on dialogue scenarios and lack diverse digital traces. Furthermore, current datasets do not cover continuous, long-term life sequences of an individual, but only concentrate on major events. In contrast, we model continuous data that covers an individual's entire life over the course of one year. Existing datasets fail to realistically simulate humans and lack dynamically fluctuating personal preferences. Furthermore, they insufficiently model real-world information. Benchmarks such as LoCoMo and LongMemEval are nearing saturation, making it difficult to identify the strengths of memory systems.


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

## 🏆 Leaderboard

Accuracy (%) on LifeBench and LoCoMo. **LifeBench Micro** is the accuracy over all questions, while **Macro** is the arithmetic mean of the nine category accuracies. **Gold Evidence†** feeds the annotated supporting evidence directly to the answer model (a reader under perfect retrieval) and is a reference upper bound — it is not a memory system and is excluded from the per-column best. **Bold** marks the best among memory systems in each column. LoCoMo excludes adversarial questions; `—` = not reported.

![LifeBench memory-system leaderboard — Macro accuracy (DeepSeek-V4-Flash)](pic/leaderboard.svg)

<table>
  <thead>
    <tr>
      <th>Base LLM</th>
      <th>Memory System</th>
      <th>SH</th><th>MH</th><th>TR</th><th>ND</th><th>KU</th><th>CR</th><th>CD</th><th>HI</th><th>UA</th><th>Micro</th><th>Macro</th><th>LoCoMo</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td rowspan="10">DeepSeek-V4-Flash</td>
      <td>Mem0</td>
      <td>78.09</td><td>41.41</td><td>32.45</td><td>48.48</td><td>75.84</td><td>52.55</td><td>78.07</td><td>32.47</td><td>55.73</td><td>61.54</td><td>55.01</td><td>85.32</td>
    </tr>
    <tr>
      <td>Cognee</td>
      <td>71.69</td><td>37.07</td><td>27.36</td><td>45.44</td><td>72.49</td><td>43.16</td><td>68.63</td><td>30.93</td><td><b>92.14</b></td><td>63.17</td><td>54.32</td><td>81.12</td>
    </tr>
    <tr>
      <td>Hindsight</td>
      <td>83.43</td><td>53.98</td><td>44.34</td><td><b>58.75</b></td><td>85.09</td><td><b>67.83</b></td><td>80.66</td><td><b>49.48</b></td><td>75.56</td><td>71.98</td><td><b>66.57</b></td><td>82.83</td>
    </tr>
    <tr>
      <td>MemU</td>
      <td>60.34</td><td>23.87</td><td>17.92</td><td>23.19</td><td>47.30</td><td>30.29</td><td>62.26</td><td>23.20</td><td>90.77</td><td>52.75</td><td>42.13</td><td>80.26</td>
    </tr>
    <tr>
      <td>MemOS</td>
      <td>72.94</td><td>32.91</td><td>26.98</td><td>33.65</td><td>71.47</td><td>40.21</td><td>68.63</td><td>35.57</td><td>88.89</td><td>61.51</td><td>52.36</td><td>79.40</td>
    </tr>
    <tr>
      <td>EverMemOS</td>
      <td>71.76</td><td>48.55</td><td>38.30</td><td>54.75</td><td>81.23</td><td>59.25</td><td>67.45</td><td>34.02</td><td>85.30</td><td>66.04</td><td>60.07</td><td>80.69</td>
    </tr>
    <tr>
      <td>MindMemOS</td>
      <td>79.83</td><td>42.04</td><td>42.45</td><td>35.36</td><td>69.67</td><td>38.07</td><td><b>84.67</b></td><td>26.80</td><td>84.10</td><td>67.37</td><td>55.89</td><td>86.70</td>
    </tr>
    <tr>
      <td>Zep</td>
      <td>77.78</td><td>49.46</td><td>46.23</td><td>43.92</td><td>73.78</td><td>53.89</td><td>83.25</td><td>39.69</td><td>54.53</td><td>63.85</td><td>58.06</td><td><b>88.84</b></td>
    </tr>
    <tr>
      <td>GraphRAG</td>
      <td>22.10</td><td>12.93</td><td>12.83</td><td>19.77</td><td>16.97</td><td>15.01</td><td>11.08</td><td>10.31</td><td>88.38</td><td>30.50</td><td>23.26</td><td>82.72</td>
    </tr>
    <tr>
      <td><i>Gold Evidence†</i></td>
      <td>98.14</td><td>94.85</td><td>94.91</td><td>93.73</td><td>96.14</td><td>94.10</td><td>98.11</td><td>93.30</td><td>100.00</td><td>97.28</td><td>95.92</td><td>—</td>
    </tr>
    <tr>
      <td rowspan="2">GLM-5.2</td>
      <td>Hindsight</td>
      <td><b>85.60</b></td><td>53.62</td><td>45.85</td><td>56.65</td><td>83.55</td><td>66.76</td><td>80.90</td><td>40.72</td><td>84.79</td><td><b>74.41</b></td><td>66.49</td><td>—</td>
    </tr>
    <tr>
      <td>EverMemOS</td>
      <td>79.64</td><td><b>58.95</b></td><td><b>59.25</b></td><td><b>58.75</b></td><td>84.83</td><td>57.64</td><td>78.54</td><td>40.72</td><td>71.45</td><td>70.95</td><td>65.53</td><td>—</td>
    </tr>
    <tr>
      <td rowspan="2">Qwen-3.8-MAX</td>
      <td>Hindsight</td>
      <td>83.30</td><td>50.72</td><td>38.87</td><td>54.94</td><td>83.29</td><td>64.88</td><td>82.08</td><td>44.85</td><td>85.30</td><td>72.31</td><td>65.36</td><td>—</td>
    </tr>
    <tr>
      <td>EverMemOS</td>
      <td>73.49</td><td>55.06</td><td>55.09</td><td>54.37</td><td><b>86.38</b></td><td>55.50</td><td>72.17</td><td>43.81</td><td>86.84</td><td>69.32</td><td>64.75</td><td>—</td>
    </tr>
  </tbody>
</table>

> **SH** Single-hop · **MH** Multi-hop · **TR** Temporal · **ND** Non-declarative · **KU** Knowledge update · **CR** Causal · **CD** Conflict detection · **HI** Hidden information · **UA** Unanswerable · **Micro** micro-average · **Macro** macro-average (across the 9 categories). † = Gold Evidence reference (perfect retrieval).
>
> 📊 **Interactive version** — sort and explore the full results at [C1754955896/Lifebench-Leaderboard](https://huggingface.co/spaces/C1754955896/Lifebench-Leaderboard).

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

LifeBench runs directly from a cloned repository. Install the third-party dependencies and run the scripts from the repository root; installing LifeBench with `pip install .` or `pip install -e .` is not a supported workflow.

1. **Clone the Repository**
   ```bash
   git clone https://github.com/1754955896/user-personal-data-sys.git
   cd user-personal-data-sys
   ```

   All commands below assume this working directory, which contains `README.md`, `requirements.txt`, and `scripts/`.

2. **Install Dependencies**
   ```bash
   python -m pip install -r requirements.txt
   ```

3. **Embedding Model Preparation** (Required for life simulation)
   The simulator loads a local embedding model through `MemoryStore`. Download it before running `scripts/run/simulator.py` or a full generation pipeline. Reading the released JSON dataset or using the local data viewer does not require this model.

   ```bash
   python -m pip install huggingface-hub
   huggingface-cli download sentence-transformers/all-MiniLM-L6-v2 --local-dir src/lifebench/event/local_models/all-MiniLM-L6-v2
   ```

   The model directory must include `config.json`, `pytorch_model.bin`, `tokenizer_config.json`, and `vocab.txt`; the loader raises an error if required files are missing.

4. **Configuration File**
   For a new setup, copy the complete [configuration template](config/config.example.json):

   ```bash
   python -c "from shutil import copyfile; copyfile('config/config.example.json', 'config/config.json')"
   ```

   If `config/config.json` already exists, edit it directly instead of copying over it. Set `llm.api_key`, `llm.base_url`, and the model names for your provider, and set `map_tool.api_key` for map-backed address generation. Keep the remaining template sections and adjust them as needed. The local configuration contains credentials and is excluded from Git.

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

The repository includes [input/person.json](input/person.json), a ready-to-use JSON array containing 10 complete personas. The default batch command reads this file directly.

For custom input, keep the same array structure and provide complete persona objects, including their nested fields. Use a [released persona](life_bench_data/version2/data/fenghaoran/persona.json) as a full reference, or follow the [persona generation guide](src/lifebench/persona/README.md). To keep custom input separate, place a `person.json` file in another directory and pass that directory with `--persona-folder`.

#### Single Persona Data Preparation

For a new single-person run, create an output directory and copy the complete [Feng Haoran persona](life_bench_data/version2/data/fenghaoran/persona.json):

```bash
python -c "from pathlib import Path; Path('output/fenghaoran').mkdir(parents=True, exist_ok=True)"
python -c "from shutil import copyfile; copyfile('life_bench_data/version2/data/fenghaoran/persona.json', 'output/fenghaoran/persona.json')"
```

For an existing run, keep its current `persona.json`. A new directory starts with:

```
output/
└── fenghaoran/           # Persona folder
    └── persona.json      # Persona data
```

### ▶️ Running

Run these commands from the repository root after configuring the APIs and preparing the persona data.

#### Batch Mode

```bash
# Run the complete generation pipeline (process all personas in input/person.json)
python scripts/run_all.py

# Specify persona ID range
python scripts/run_all.py --start-id 1 --end-id 5

# Skip QA generation (phone data, monthly reports, etc. are still generated)
python scripts/run_all.py --generate-qa 0
```

#### Single Persona Mode

**Run all at once with `scripts/run.py`:**

```bash
python scripts/run.py --base-path output/fenghaoran
```

**Run step by step for the full year 2025:**

```bash
# 1. Generate daily event drafts
python scripts/run/draft_gen.py --base-path output/fenghaoran

# 2. Simulate daily activities
python scripts/run/simulator.py --file-path output/fenghaoran/

# 3. Generate phone operation data
python scripts/run/phone_gen.py --file-path output/fenghaoran/ --start-time 2025-01-01 --end-time 2025-12-31

# 4. Generate question-answer pairs
python scripts/run/qa_gen.py --data-path output/fenghaoran/
```

> Each step accepts additional arguments — see [`scripts/run/README.md`](scripts/run/README.md) for the full list.


### 🎛️ Command Line Arguments

#### Single-Person Pipeline: `scripts/run.py`

The following options apply to the integrated single-person runner:

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

#### Batch Pipeline: `scripts/run_all.py`

The batch runner accepts the following options. It runs full years and does not accept `--base-path`, `--instance-id`, `--months`, `--interactive`, or `--no-phone-sample`.

| Argument | Description | Default |
|----------|-------------|---------|
| `--persona-folder` | Directory containing `person.json`; relative paths resolve from the repository root | `input/` |
| `--start-id` | First persona position to process (1-based, inclusive); `0` starts at the beginning | `0` |
| `--end-id` | Last persona position to process (1-based, inclusive); `0` processes through the end | `0` |
| `--process-path` | Intermediate data directory relative to each persona's output directory | `process/` |
| `--max-workers` | Max worker threads passed to the single-person runner | auto (CPU cores × 2) |
| `--generate-phone-data` | Generate phone data (0/1) | `1` |
| `--generate-monthly-report` | Generate monthly reports (0/1) | `1` |
| `--generate-qa` | Generate QA data (0/1) | `1` |
| `--year` | Year for generated data | `2025` |
| `--dry-run` | Write placeholder files without generating | off |

For stage-specific arguments, see [`scripts/run/README.md`](scripts/run/README.md).

### 🎯 Evaluation

The evaluation script lives in a separate repository: [LifeBench_eval](https://github.com/1754955896/LifeBench_eval) — this is the entry point for running benchmark evaluations on memory systems.

## 📁 Directory Structure

Main directories and files included in the repository:

```text
user-personal-data-sys/
├── config/                   # Configuration template and reference
├── input/
│   └── person.json           # Complete sample personas for batch mode
├── output/                   # Destination for locally generated results
├── scripts/
│   ├── run_all.py            # Batch runner
│   ├── run.py                # Integrated single-person runner
│   └── run/                  # Individual generation stages
├── src/lifebench/            # Persona, event, memory, and utility modules
├── life_bench_data/
│   └── version2/
│       ├── data/             # Chinese multi-source dataset
│       ├── data_en/          # English multi-source dataset
│       └── locomo_format/    # Chinese and English conversational exports
├── html/                     # Local browser-based data viewer
├── hf_space_leaderboard/     # Interactive leaderboard assets
├── pic/                      # Documentation images
├── requirements.txt
├── pyproject.toml
├── LICENSE
└── README.md
```

Generated persona directories and intermediate results appear under `output/` when the pipeline runs. See the [dataset layout](life_bench_data/README.md), [source module guide](src/lifebench/README.md), and [script reference](scripts/README.md) for details.

To inspect the released data locally, open [`html/index.html`](html/index.html) in Chrome or Edge and select a persona directory such as `life_bench_data/version2/data/fenghaoran/`. No backend or generation API is needed; see the [viewer guide](html/README.md).

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
