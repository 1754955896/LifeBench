# Executable Scripts

Main executable scripts for the project.

## Running from the Repository

Use a cloned repository with dependencies installed as described in the [main README](../README.md#-environment-configuration). Run commands from the repository root:

```bash
# Process all personas in input/person.json
python scripts/run_all.py

# Process a single prepared persona
python scripts/run.py --base-path output/fenghaoran
```

The supported workflow uses these scripts directly. No installed console command or LifeBench package installation is required. See [run/README.md](run/README.md) for individual generation stages and their arguments.

## Files

| File | Description |
| --- | --- |
| `run.py` | Main pipeline runner. |
| `run_all.py` | Batch runner for the complete data generation pipeline across all personas. |

## Subdirectories

| Directory | Description |
| --- | --- |
| `run/` | Standalone scripts for QA, persona and phone data generation, and simulation. |
