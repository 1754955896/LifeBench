# LifeBench: A Benchmark for Long-Horizon Multi-Source Memory

LifeBench is a benchmark designed for evaluating personalized agent memory systems. It comprises detailed character profile data, a full-year dataset covering all daily life activities of individuals, digital trace (mobile phone operation) data corresponding to real-life scenarios, and the associated question-answering data.

## Overview

![LifeBench Overview](pic/PIC_INTRO.png)

## Dataset

The dataset can be found in the `life_bench_data` folder, available in both English and Chinese versions. The dataset contains data from 10 users, with each user having the following files:

- **`phone_data`**: Mobile phone operation data
- **`QA`**: Question-answering data
- **`summary`**: Monthly summaries
- **`daily_event.json`**: Daily activities
- **`location.json`**: Real city addresses
- **`persona.json`**: User profile
- **`daily_draft.json`**: Daily granular outline