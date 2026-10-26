# Executable Scripts

Main executable scripts for the project.

## Running from the Repository

Use a cloned repository with dependencies installed as described in the [main README](../docs/installation.md). Run commands from the repository root:

```bash
# Process all personas in input/person.json
python scripts/run_all.py

# Process a single prepared persona
python scripts/run.py --base-path output/fenghaoran
```

The supported workflow uses these scripts directly. No installed console command or LifeBench package installation is required. See [run/README.md](run/README.md) for individual generation stages and their arguments.

## Map Selection

`run.py` and `run_all.py` accept `--map-tool amap|overseas|auto` (default: `amap`).
For overseas or automatic routing, also pass `--map-config <JSON file>`; these options
are forwarded to draft, simulation, phone-data and QA subprocesses. Each persona's
`home_address.country_code` determines residence; individual addresses may specify
other destination countries. For example:

```powershell
python scripts/run.py --base-path output/example --map-tool overseas --map-config config/overseas_map.demo.json
```

The demo configuration uses public services for small manual checks. Configure your
own service endpoints for batch generation; see [map configuration](../src/lifebench/utils/README.md).

## Files

| File | Description |
| --- | --- |
| `run.py` | Main pipeline runner. |
| `run_all.py` | Batch runner for the complete data generation pipeline across all personas. |

## Subdirectories

| Directory | Description |
| --- | --- |
| `run/` | Standalone scripts for QA, persona and phone data generation, and simulation. |
