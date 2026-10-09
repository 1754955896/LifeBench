# Daily Life Simulation Engine

A modular simulation engine extracted from `event/daily_simulator.py` (`MindController`). It evolves daily drafts into daily events with real locations, memory, and reflection.

The engine parallelizes date partitions while processing days sequentially within each partition. Each partition cold-starts with draft-predicted memory, evolves day by day, and maintains a transactional checkpoint for failure recovery and idempotent retries. `daily_simulator.py` remains the outer orchestration entry point and injects `Mind` instances through `mind_factory`.

## Core Files

| File | Description |
|------|-------------|
| `engine.py` | `DailySimulationEngine`: parallel date-partition driver and transactional checkpoints. |
| `preparation.py` | `SimulationAssetPreparer`: prepares immutable assets shared by date partitions in a single process, including fuzzy memory and `persona_locations_v2` location assets; validates and freezes them for the run. |
| `state.py` | Cognitive state data structures, including `CognitiveState` and `LongTermMemory`. |
| `activity_contract.py` | Structured bridge between subjective and objective generation, including stop intents. |
| `validation.py` | Daily schema and invariant validation. |
| `telemetry.py` | Telemetry: `manifest` for reproducibility metadata and `memory_trace` for retrieved/written memory IDs. |

## Subdirectories

| Directory | Description |
|-----------|-------------|
| `generators/` | Stage generators for thought, objective events, trajectories, and reflection. |
| `context/` | Structured context for subjective thought. |
| `geolocation/` | Constrained geolocation assignment, EPR/gravity ranking, itinerary reconciliation, and half-hour exports. |
| `memory/` | Structured memory storage, retrieval, consolidation, and embedding. |
| `activity/` | Activity normalization and daily itinerary planning. |
| `baseline/` | No-mobility feedback ablation baseline. |
