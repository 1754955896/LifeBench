# Codebase Structure

Last updated: 2026-02-27

## Repo Root

```
LifeBench/
├── config.json             # API keys (DeepSeek LLM + map tool)
├── requirements.txt        # Python dependencies
├── README.md               # Original project README
├── run_all.py              # Batch entry point: loops over data/person.json
├── run.py                  # Single-user pipeline orchestrator
│
├── data/                   # Input: place person.json here
├── output/                 # Generated output per user
├── life_bench_data/        # Pre-generated benchmark data (10 EN + 10 CN users)
│   ├── data_en/            # English users
│   └── data_cn/            # Chinese users
│
├── run/                    # Pipeline step scripts (called by run.py)
│   ├── draft_gen.py        # Stage 2: yearly outline
│   ├── event_gen.py        # Stage 3: detailed events
│   ├── simulator.py        # Stage 4: refinement + health reports + fuzzy memory
│   ├── phone_gen.py        # Stage 5: phone data (parallel)
│   ├── QA_gen.py           # Stage 6: QA generation
│   └── persona_gen.py      # Stage 1: persona
│
├── event/                  # Core synthesis logic
│   ├── scheduler.py        # Event scheduling & conflict resolution (280KB)
│   ├── mind.py             # Agent mental model & decision making (83KB)
│   ├── event_refiner.py    # Event validation & health reports (68KB)
│   ├── event_formatter.py  # Event formatting utilities
│   ├── phone_data_gen.py   # Phone operation generation (140KB)
│   ├── memory.py           # Sentence-transformer embeddings, semantic search
│   ├── qa_generator.py     # QA orchestrator
│   ├── qa_single_generator.py    # Single-hop QA (56KB)
│   ├── qa_muti_generator.py      # Multi-hop QA (74KB)
│   ├── qa_reasoning_generator.py # Reasoning QA (77KB)
│   ├── fuzzy_memory_builder.py   # Fuzzy/approximate memory construction
│   ├── persona_address_generator.py
│   ├── Prob_Model.py        # Probability models for event distributions
│   ├── event_schema.csv     # Event taxonomy (categories + atomic actions)
│   ├── templates.py         # LLM prompts - main (160KB)
│   ├── template_s.py        # LLM prompts - supplementary (124KB)
│   ├── template2.py         # LLM prompts - additional (72KB)
│   ├── template3.py         # LLM prompts - additional (127KB)
│   └── local_models/        # Sentence transformer model (all-MiniLM-L6-v2)
│
├── persona/                 # Persona generation
│   ├── persona_gen.py
│   ├── gen_utils/
│   └── persona_file/
│
└── utils/                   # Shared utilities
    ├── llm_call.py          # DeepSeek API wrapper (OpenAI-compatible)
    ├── IO.py                # JSON read/write helpers
    ├── maptool.py           # Address/map lookups
    ├── dataprocess.py       # Data processing helpers
    ├── random_ref.py        # Random selection utilities
    └── count_*.py           # Dataset analysis scripts
```

## Per-User Output Structure

```
output/<name>_<id>/
├── persona.json                       # Full user profile
├── daily_draft.json                   # Yearly outline (per month → per day)
├── daily_event.json                   # All events with timestamps
├── location.json                      # Real addresses for event locations
├── our.json                           # Memory system eval format
├── phone_data/                        # One JSON per date
│   └── YYYY-MM-DD.json                # Mixed phone ops for that day
├── QA/
│   └── QA_clean.json                  # Final merged QA pairs
└── summary/
    └── all_monthly_health_reports.json
```

## Module Size Notes (large files = high complexity)

| File | Size | Notes |
|------|------|-------|
| `event/scheduler.py` | 280KB | Most complex — event tree + scheduling logic |
| `event/templates.py` | 160KB | All main LLM prompts as inline strings |
| `event/template_s.py` | 124KB | Supplementary prompts |
| `event/template3.py` | 127KB | Additional prompts |
| `event/phone_data_gen.py` | 140KB | 7 phone op type generators |
| `event/template2.py` | 72KB | Additional prompts |
| `event/qa_reasoning_generator.py` | 77KB | Reasoning QA logic |
| `event/qa_muti_generator.py` | 74KB | Multi-hop QA logic |
| `event/mind.py` | 83KB | Agent decision model |
| `event/event_refiner.py` | 68KB | Validation + health reports |
