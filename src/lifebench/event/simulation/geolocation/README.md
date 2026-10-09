# Constrained Geolocation Assignment

Constrained geolocation assignment for V1 event simulation. Converts daily plans into location sequences with real coordinates, travel modes, and travel times, then exports the final unified geographic facts as sidecar data for events.

## Files

| File | Description |
|------|-------------|
| `allocator.py` | `TrajectoryAllocator`: jointly selects locations, travel modes, and travel times in stop order. |
| `selector.py` | Deterministic EPR-lite and gravity-model candidate ranking. |
| `candidate_provider.py` | Candidate retrieval: prioritizes the persona catalog and uses map APIs for exploratory locations. |
| `catalog.py` | `flatten_location_data`: normalizes persona addresses into a reusable location catalog. |
| `epr.py` | `EPRProfile` / `build_personal_epr_profile`: personalized exploration-preferential-return parameters. |
| `mode.py` | Travel mode selection under persona constraints and map travel-time queries. |
| `models.py` | Stable assignment data structures, including `TrajectoryAssignment` and `PlausibleLocationSpec`. |
| `intent_adapter.py` | `parse_stop_intents`: unifies new stop intents and legacy instruction JSON as StopIntent objects. |
| `reconciliation.py` | Merges final locations and travel legs from trajectory adjustment into the geographic sidecar. |
| `injection.py` | `render_assignment_summary`: renders structured assignments as trajectory references for downstream LLMs to prioritize. |
| `export.py` | `attach_event_geodata` / `build_location_records`: converts assignments into geographic sidecars for final events. |
| `registry.py` | Location registry across days, preserving location IDs and coordinates for the same semantic place. |
| `timeslot.py` | `build_half_hour_trajectory`: exports the final unified geographic facts as 48 half-hour location samples per day. |
| `validator.py` | Checks structural and numeric completeness without keyword inference or rewriting LLM narratives. |
| `coordinates.py` | GCJ-02 and WGS-84 coordinate comparison and conversion. |
| `baseline.py` | Simple baseline v3: agentic geographic assignment using an LLM with geographic function-calling tools. |
