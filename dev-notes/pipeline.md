# Pipeline & Data Flow

Last updated: 2026-02-27

## End-to-End Flow

```
data/person.json
      │
      ▼
run_all.py ──► run.py (per user)
                  │
                  ├─ Stage 1: Persona Generation
                  │     run/persona_gen.py → persona/persona_gen.py
                  │     Output: persona.json
                  │
                  ├─ Stage 2: Draft Generation
                  │     run/draft_gen.py → event/scheduler.py, event/mind.py
                  │     Output: daily_draft.json  (12 months × ~30 days, outline only)
                  │
                  ├─ Stage 3: Event Simulation
                  │     run/event_gen.py → event/scheduler.py
                  │     Output: daily_event.json  (full timestamped events)
                  │
                  ├─ Stage 4: Event Refinement
                  │     run/simulator.py → event/event_refiner.py, event/fuzzy_memory_builder.py
                  │     Output: validated daily_event.json, summary/all_monthly_health_reports.json
                  │
                  ├─ Stage 5: Phone Data Generation  (parallel, ThreadPoolExecutor)
                  │     run/phone_gen.py → event/phone_data_gen.py
                  │     Output: phone_data/YYYY-MM-DD.json  (7 op types per day)
                  │
                  └─ Stage 6: QA Generation
                        run/QA_gen.py → event/qa_generator.py
                          ├─ qa_single_generator.py   → single-hop factual QA
                          ├─ qa_muti_generator.py     → multi-hop pattern QA
                          └─ qa_reasoning_generator.py → reasoning/inference QA
                        Output: QA/QA_clean.json
```

## Skip Logic

Each stage in `run.py` checks if its output file already exists before running.
This makes the pipeline fully resumable after interruption.

| Stage | Skip condition |
|-------|---------------|
| Draft gen | `daily_draft.json` exists |
| Event gen | `daily_event.json` exists |
| Phone gen | `phone_data/` dir non-empty |
| QA gen | `QA/QA_clean.json` exists |

## Key Data Formats

### Input: `data/person.json`
Array of persona seed objects. Key fields:
- name, birth, age, gender, education, job, occupation
- home_address, workplace (province/city/district/street)
- salary, body (height/weight/BMI), family, personality (MBTI + traits)
- hobbies, favorite_foods

### `daily_draft.json`
```json
{
  "2025-01": [{
    "date": "2025-01-01",
    "date_attribute": { "weather": "...", "holiday": "...", "week": "Wednesday" },
    "daily_overview": "...",
    "events": [{ "name": "...", "description": "..." }],
    "state": { "体重": 55.0, "起床时间": "08:30", "睡觉时间": "23:00" }
  }]
}
```

### `daily_event.json`
```json
[{
  "event_id": 1,
  "name": "Morning Awakening",
  "date": ["2025-01-01 08:30:00 to 2025-01-01 09:00:00"],
  "type": "Personal Life",
  "description": "...",
  "participant": [{ "name": "Yu Xiaowei", "relation": "Self" }],
  "location": "Bedroom at Home"
}]
```

### `phone_data/YYYY-MM-DD.json`
Mixed array of 7 operation types:

| type | Key fields |
|------|-----------|
| `call` | phoneNumber, contactName, datetime, datetime_end, direction (0=out/1=in), call_result |
| `sms` | phoneNumber, contactName, datetime, direction, content |
| `note` | title, content, datetime |
| `calendar` | title, start_time, end_time, location, notes |
| `photo` | datetime, location, description, tags |
| `push` | app_name, title, content, datetime |
| `agent_chat` | conversation (multi-turn, user+assistant) |

### `QA/QA_clean.json`
```json
[{
  "question": "...",
  "options": [{ "option": "A", "content": "..." }, ...],
  "answer": "C",
  "required_events": [{ "event_id": 33, "event_name": "..." }],
  "evidence": [{ "type": "agent_chat", "id": 3 }, { "type": "call", "id": 9 }],
  "ask_time": "2025-01",
  "question_type": "Information Extraction|Multi-hop|Reasoning",
  "score_points": [...]
}]
```

### QA Types

| Type | Description | Complexity |
|------|-------------|-----------|
| Single-hop | Direct factual retrieval from one event | Low |
| Multi-hop | Pattern recognition across multiple events | Medium |
| Reasoning | Causal/motivational inference | High |
| User Modeling | Personality, preferences, habits | High |
| Updating | Temporal change tracking | High |

## LLM Usage

- Model: `deepseek-chat` (standard) + `deepseek-reasoner` (complex reasoning tasks)
- Interface: `utils/llm_call.py` — OpenAI-compatible SDK
- Functions: `llm_call()`, `llm_call_reason()`, `llm_call_j()` (JSON mode)
- Prompts: Defined as inline strings in `event/templates.py` and sibling template files

## Memory System

`event/memory.py` uses sentence-transformers (`all-MiniLM-L6-v2`) for:
- Semantic similarity search over events
- Date-based memory retrieval
- Supporting QA evidence linking
