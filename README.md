# LifeBench: A Benchmark for Long-Horizon Multi-Source Memory

LifeBench is a benchmark designed for evaluating personalized agent memory systems. It comprises:
- Detailed character profile data
- A full-year dataset covering all daily life activities of individuals
- Digital trace (mobile phone operation) data corresponding to real-life scenarios
- Associated question-answering data

The main objectives of our dataset are as follows:

1. **Challenging question-answering and interactive tasks**
   We aim to design comprehensive, continuous, and dense scenarios that cover real-life interactions between humans and agents/mobile devices, posing rigorous challenges to agent/device interaction capabilities. 
   The current version includes tasks such as single-hop reasoning, multi-hop reasoning, temporal and memory-updating reasoning, and non-declarative memory reasoning. 
   In future work, we plan to introduce additional challenging settings, including conflicting memories, harmful memories (involving privacy and bias), and the ability to retain important memories under massive memory loads.

2. **Long-term, full-coverage personal life and digital trace data**
   Such data can be applied to a wide range of fields, including recommendation systems, research on services for vulnerable groups, game NPC generation, and general data training, rather than being limited to the evaluation of agent memory systems. 
   Therefore, constructing high-quality, realistic, and plausible datasets of this kind is of great importance.

## Example of the data
![LifeBench Example](pic/PIC_BENCH.png)
## Overview
![LifeBench Overview](pic/PIC_INTRO.png)
Existing benchmarks mainly focus on dialogue scenarios and lack diverse digital traces. Furthermore, current datasets do not cover continuous, long-term life sequences of an individual, but only concentrate on major events. In contrast, we model continuous data that covers an individual’s entire life over the course of one year.


## Dataset

The dataset can be found in the `life_bench_data` folder, available in both English and Chinese versions. The dataset contains data from 10 users, with each user having the following files:

- **`phone_data`**: Mobile phone operation data
- **`QA`**: Question-answering data
- **`summary`**: Monthly summaries
- **`daily_event.json`**: Daily activities
- **`location.json`**: Real city addresses
- **`persona.json`**: User profile
- **`daily_draft.json`**: Daily granular outline

### Memory Benchmark Support

For the convenience of conducting memory benchmark tests on existing memory systems (primarily for locomo), we have converted the QA data into the locomo input format. The converted data can be found in `our.json`.

## Data Synthesis Framework Usage
![Data Synthesis Framework](pic/pic.png)
1. **Environment Configuration**: 
   - Run `pip install -r requirements.txt` to install dependencies
   - Configure LLM API and map API keys in `config.json`

2. **Prepare Persona Data**: 
   - Create a persona array (supports multiple users and custom formats)
   - Save it as `data/person.json`

3. **Generate Data**: 
   - Execute `python run_all.py` to start the data synthesis process