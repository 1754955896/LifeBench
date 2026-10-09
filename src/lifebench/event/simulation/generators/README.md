# Daily Simulation Generators

Four generation methods have been extracted from `Mind` into separate modules, with thin delegation methods retained in `Mind`. The first argument, `mind`, is a duck-typed `Mind` instance. The package uses lazy exports to avoid import coupling between stages.

## Files

| File | Description |
|------|-------------|
| `thought.py` | `generate_subjective_thought`: human-like daily intentions, including how to carry out plans and which activities to arrange. |
| `objective.py` | `generate_objective_events`: adjusts, supplements, and refines daily events based on schedules and plausibility. |
| `trajectory.py` | `generate_poi_route` / `adjust_event_trajectory`: real-world POI resolution and event trajectory adjustment. |
| `reflection.py` | `generate_reflection`: memory summaries, activity statistics, and context for the following day. |
