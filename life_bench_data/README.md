# LifeBench Benchmark Dataset

This directory provides the LifeBench v2.0 benchmark: life events, phone records, and question-answer pairs for 10 virtual users over 2025, in Chinese and English. The current repository contains only `version2/`.

## Dataset Size

All counts below are for a single language version. The Chinese and English versions have the same record counts and are not added together.

| Item | Count |
|------|-------|
| Virtual users | 10 |
| Daily life events | 57,486 |
| Phone records | 47,409 across 9 data sources |
| Question-answer pairs | 3,380 |

## Directory Structure

| Path | Description |
|------|-------------|
| [version2/data/](version2/data/) | Chinese multi-source data organized by user. |
| [version2/data_en/](version2/data_en/) | English multi-source data with the same directory structure. |
| [version2/locomo_format/](version2/locomo_format/) | Chinese and English LoCoMo conversational data. |
| [version2/README.md](version2/README.md) | Detailed dataset documentation, field examples, and leaderboard. |
| [version2/leaderboard.svg](version2/leaderboard.svg) | Leaderboard chart. |

Both `data/` and `data_en/` contain these 10 user directories:

```text
fenghaoran/
leimingxuan/
lumingqiang/
maxiulan/
songyajing/
sunyuwei/
yemingxuan/
yinhao/
yuxiaowei/
yuxiaowen/
```

## Per-User Files

Each `version2/data/{user}/` and `version2/data_en/{user}/` directory contains:

| File | Description |
|------|-------------|
| `persona.json` | User profile. |
| `daily_event.json` | Array of daily life events. |
| `event_tree.json` | Event tree structure. |
| `daily_draft.json` | Daily outlines. |
| `QA_all/QA.json` | The user's question-answer pairs, including questions, answers, evidence, and scoring points. |
| `phone_data/` | Phone records from the nine sources listed below. |

### Phone Records

| File | Description |
|------|-------------|
| `phone_data/agent_chat.json` | Conversations with an intelligent assistant. |
| `phone_data/calendar.json` | Calendar entries and schedules. |
| `phone_data/call.json` | Call records. |
| `phone_data/contact.json` | Contacts. |
| `phone_data/fitness_health.json` | Fitness and health records. |
| `phone_data/note.json` | Notes. |
| `phone_data/photo.json` | Photo-related records. |
| `phone_data/push.json` | Push notifications. |
| `phone_data/sms.json` | SMS messages. |

## LoCoMo Conversational Format

`version2/locomo_format/` contains two JSON files:

| File | Description |
|------|-------------|
| [lifebench_locomo_conversation_format_v2.0_3380QA.json](version2/locomo_format/lifebench_locomo_conversation_format_v2.0_3380QA.json) | Chinese version. |
| [lifebench_locomo_conversation_format_v2.0_3380QA_en.json](version2/locomo_format/lifebench_locomo_conversation_format_v2.0_3380QA_en.json) | English version. |

Each file is a top-level array containing 10 user samples and 3,380 question-answer pairs in total. Each sample contains `sample_id`, `conversation`, and `qa` fields.

The per-user `QA_all/QA.json` files and the LoCoMo files provide two representations of the QA data. Do not count them as additional question-answer pairs.
