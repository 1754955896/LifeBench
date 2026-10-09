# Legacy Memory Structures

Legacy memory implementation based on sentence-transformers.

## Files

| File | Description |
| --- | --- |
| `memory.py` | `MemoryModule`: centralized memory operations with optional singleton or multiple-instance use. |

> The daily simulation memory system now lives in [`event/simulation/memory/`](../simulation/memory/README.md), with `MemoryStore`, `FuzzyMemoryBuilder`, `build_short_memory`, and `EmbeddingModel`. This directory retains only the legacy `MemoryModule`.
