# No-Mobility Feedback Baseline

Wraps the ablation workflow with a read-only switch while leaving the source feedback logic intact. The `no-mobility` baseline removes mobility considerations from both subjective thought and objective event generation.

## Files

| File | Description |
|------|-------------|
| `no_feedback.py` | `generate_subjective_thought_no_feedback` / `generate_objective_events_no_feedback`: subjective and objective generation without mobility feedback. |
| `templates_no_mobility.py` | Subjective and objective prompt templates without mobility considerations. |
