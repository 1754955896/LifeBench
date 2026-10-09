# Structured Simulation Memory

Structured memory storage, retrieval, consolidation, and embedding for daily simulation. This differs from the legacy `MemoryModule` in `event/memory_structure/`. `MemoryStore` is not a singleton: each date partition has its own instance.

## Files

| File | Description |
|------|-------------|
| `store.py` | `MemoryStore`: structured memory storage. |
| `embedding.py` | `EmbeddingModel`: embedding model loading and encoding. |
| `retrieval.py` | `build_short_memory`: retrieves short-term memories from MemoryStore to construct the single structured short-term memory context. |
| `consolidation.py` | `FuzzyMemoryBuilder`: draft-derived fuzzy memory for cold starts. |
