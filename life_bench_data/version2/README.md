---
license: apache-2.0
language:
  - zh
  - en
tags:
  - life-logging
  - personal-assistant
  - long-term-memory
  - episodic-memory
  - question-answering
  - multi-source
  - phone-data
  - locomo
size_categories:
  - 10K<n<100K
task_categories:
  - question-answering
pretty_name: LifeBench 2.0
---

# 🧠 LifeBench 2.0

> A life-logging benchmark dataset for long-term memory evaluation

LifeBench 2.0 collects a full year (2025-01-01 ~ 2025-12-31) of life data for **10 virtual users**, covering personas, daily life events, event trees, and **9 types of mobile-phone data** (SMS, calls, calendar, notes, photos, push notifications, fitness & health, contacts, and agent chat), together with **thousands of question-answer pairs annotated with evidence and score points**, for evaluating the long-term memory, temporal reasoning, and multi-hop QA capabilities of large language models. The dataset provides **Chinese (`data/`)** and **English (`data_en/`)** versions, as well as a standardized **LoCoMo conversational format (`locomo_format/`)**.

## 📊 Dataset Statistics

| Metric | Value |
|--------|-------|
| 👥 Users | 10 |
| 🌐 Languages | Chinese (`data/`) · English (`data_en/`) |
| 📅 Time span | 2025-01-01 ~ 2025-12-31 (full year) |
| 🗓️ Daily life events | 57,486 |
| 📱 Phone data records | 47,409 (9 data sources) |
| ❓ QA pairs (QA_all / locomo) | 3,380 |
| 💾 Data size | ~423 MB |

## 🏆 Leaderboard

Accuracy (%) of memory systems on LifeBench 2.0 and LoCoMo. **LifeBench Micro** is the accuracy over all questions, while **Macro** is the arithmetic mean of the nine category accuracies. **Gold Evidence†** feeds the annotated supporting evidence directly to the answer model (a reader under perfect retrieval) and is a reference upper bound — it is not a memory system and is excluded from the per-column best. **Bold** marks the best among memory systems in each column. LoCoMo excludes adversarial questions; `—` = not reported.

![LifeBench memory-system leaderboard — Macro accuracy (DeepSeek-V4-Flash)](leaderboard.svg)

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

## 📁 Directory Structure

```
version2/
├── README.md                         # This file
├── data/                             # Chinese multi-source data (10 users)
│   └── {user}/                       # One folder per user
│       ├── persona.json              # User profile
│       ├── daily_event.json          # Daily life events
│       ├── event_tree.json           # Event tree structure
│       ├── daily_draft.json          # Daily outline (organized by month)
│       ├── phone_data/               # Mobile-phone data (9 types)
│       │   ├── sms.json              # SMS
│       │   ├── call.json             # Call logs
│       │   ├── calendar.json         # Calendar
│       │   ├── note.json             # Notes
│       │   ├── photo.json            # Photos
│       │   ├── push.json             # Push notifications
│       │   ├── fitness_health.json   # Fitness & health
│       │   ├── contact.json          # Contacts
│       │   └── agent_chat.json       # Agent chat
│       └── QA_all/
│           └── QA.json               # QA pairs (with evidence & score points)
├── data_en/                          # English multi-source data (same structure as data/)
└── locomo_format/                    # LoCoMo conversational format
    ├── lifebench_locomo_conversation_format_v2.0_3380QA.json      # Chinese
    └── lifebench_locomo_conversation_format_v2.0_3380QA_en.json   # English
```

## 👥 User List

| # | User ID | Chinese Name | English Name |
|---|---------|--------------|--------------|
| 1 | `fenghaoran` | 冯浩然 | Feng Haoran |
| 2 | `leimingxuan` | 雷铭轩 | Lei Mingxuan |
| 3 | `lumingqiang` | 卢明强 | Lu Mingqiang |
| 4 | `maxiulan` | 马秀兰 | Ma Xiulan |
| 5 | `songyajing` | 宋雅静 | Song Yajing |
| 6 | `sunyuwei` | 孙雨薇 | Sun Yuwei |
| 7 | `yemingxuan` | 叶铭轩 | Ye Mingxuan |
| 8 | `yinhao` | 尹浩 | Yin Hao |
| 9 | `yuxiaowei` | 于晓薇 | Yu Xiaowei |
| 10 | `yuxiaowen` | 于晓雯 | Yu Xiaowen |

## 📄 File Descriptions

Each user folder (`data/{user}/` and `data_en/{user}/`) contains the following files:

| File | Description |
|------|-------------|
| `persona.json` | 👤 User profile: name, age, occupation, family, personality (MBTI), hobbies, etc. |
| `daily_event.json` | 📅 Daily life events: a chronological record of the user's life over a year |
| `event_tree.json` | 🌳 Event tree: hierarchical decomposition of complex events (`decompose`/`subevent`) |
| `daily_draft.json` | 🗂️ Daily outline: organized by month, with date attributes (weather/holiday/weekday) and daily overview |
| `phone_data/` | 📱 9 types of mobile-phone data (see table below) |
| `QA_all/QA.json` | ❓ QA pairs: question, answer, evidence chain, score points, question type |

### 📱 Phone Data Sources (phone_data/)

| File | Description | Records (10 users total) |
|------|-------------|--------------------------|
| `agent_chat.json` | 🤖 Agent chat | 8,177 |
| `calendar.json` | 📅 Calendar | 6,011 |
| `call.json` | 📞 Call logs | 3,947 |
| `contact.json` | 👤 Contacts | 244 |
| `fitness_health.json` | 🏃 Fitness & health | 3,641 |
| `note.json` | 📝 Notes | 7,836 |
| `photo.json` | 📷 Photos | 5,604 |
| `push.json` | 🔔 Push notifications | 6,026 |
| `sms.json` | 💬 SMS | 5,923 |

## ❓ QA Data

The dataset provides **two** representations of the QA pairs:

1. **`QA_all/QA.json`** (per user, **3,380** in total): individual QA pairs with the fields
   `question`, `answer`, `evidence` (evidence chain), `score_points`, `question_type` (e.g. `Single_hop`), `required_events_id`, and `ask_time`.

2. **`locomo_format/`** (**3,380** QA, 10 samples): converted to the LoCoMo conversational format; each sample contains `sample_id`, `conversation` (two-speaker dialogue), and `qa`.

> Each user has 326–354 QA pairs; see the individual user folders for details.

## 🧾 Data Format Examples

### 👤 persona.json (user profile)

```json
{
  "name": "Yu Xiaowen",
  "birth": "1997-12-29",
  "age": 24,
  "nationality": "Han",
  "gender": "Female",
  "education": "Undergraduate degree (formal higher education).",
  "job": "Resident physician",
  "occupation": "Zhengzhou Central Hospital",
  "salary": 120000.0,
  "body": { "height": 163, "weight": 50.0, "BMI": 18.8 },
  "personality": { "mbti": "ISFJ", "traits": ["Benevolence", "Social responsibility orientation", "Personal growth orientation"] },
  "hobbies": ["city walk", "Read books/newspapers/magazines", "Listen to European classical music", "Badminton", "Made pottery (hand building)."]
}
```

### 📅 daily_event.json (daily event)

```json
{
  "event_id": "1",
  "name": "New Year's Eve dinner and New Year's goal sharing",
  "date": ["2025-01-01 00:00:00 to 2025-01-01 02:30:00"],
  "type": "Relationships",
  "description": "In the early morning, she had a New Year's Eve dinner at home with close friends Zhang Jing and Sun Yue...",
  "participant": [
    { "name": "Yu Xiaowen", "relation": "self" },
    { "name": "Zhang Jing", "relation": "close friend" }
  ],
  "location": "No. 89, Jingsan Road, Jinshui District, Zhengzhou City, Henan Province...",
  "atomic_id": ["1-1"]
}
```

### 🌳 event_tree.json (event tree)

```json
{
  "name": "Systematic fund investment and financial planning adjustments.",
  "date": ["2025-06-10"],
  "type": "Finance",
  "event_id": 229,
  "participant": [{ "name": "self", "relation": "self" }],
  "location": "unknown",
  "decompose": 1,
  "subevent": [
    { "event_id": "229-2", "name": "Execute systematic fund investment", "type": "Finance", "decompose": 0 }
  ]
}
```

### ❓ QA_all/QA.json (QA pair)

```json
{
  "question": "At noon on the day my dad had a stroke, I remember I had just taken out my lunchbox and had only eaten a few bites when my mom called... How long exactly did that call last?",
  "answer": "2 minutes (12:13-12:15)",
  "required_events_id": ["248", "248"],
  "ask_time": "2025-06-20",
  "question_type": ["Single_hop"],
  "score_points": [
    { "description": "Identified the call record with mother Li Xiuying (12:13-12:15).", "score": 4 },
    { "description": "Correctly calculated the call duration as 2 minutes.", "score": 3 }
  ],
  "evidence": [
    { "type": "call", "phoneNumber": "+8618739081234", "contactName": "Li Xiuying", "datetime": "2025-01-15 12:13:00" }
  ]
}
```

### 💬 locomo_format (LoCoMo conversational format)

```json
{
  "sample_id": "Yu Xiaowei",
  "conversation": {
    "speaker_a": "Yu Xiaowei",
    "speaker_b": "Yu Xiaowei's Assistant",
    "session_1": [
      { "speaker": "Yu Xiaowei", "dia_id": "2025-01-01_agent_chat0", "text": "..." }
    ]
  },
  "qa": [ ... ]
}
```

## 📥 Loading

```python
from datasets import load_dataset

# Load the entire dataset (including the JSON files under data/ and data_en/)
ds = load_dataset("C1754955896/Lifebenchv2.0")

# Or read a single JSON file directly
import json
with open("data/yuxiaowen/persona.json", encoding="utf-8") as f:
    persona = json.load(f)
```

## 📌 Notes

- **Two QA representations**: `QA_all/QA.json` (per user) and `locomo_format/` (merged conversational format) both contain **3,380** QA pairs — the former is the original annotated format, the latter is the LoCoMo conversational format.
- **License**: Apache-2.0.
