# Contributing to LifeBench

## Development Setup

Follow the [installation guide](docs/installation.md) and run commands from the repository root. Keep API credentials in the ignored `config/config.json`.

## Repository Layout

- `src/lifebench/`: persona, event, phone-data, and QA implementation.
- `scripts/`: integrated and standalone generation entry points.
- `docs/`: user guides and documentation assets.
- `apps/`: local viewer and static leaderboard.
- `life_bench_data/`: released benchmark data and format documentation.
- `input/` and `output/`: inputs and generation working directories.

Use descriptive `snake_case` names for Python modules and image assets. Keep existing CLI paths and released data fields compatible when reorganizing code.

## Changes

Describe the purpose, affected commands, and verification in pull requests. Update relevant guides when changing arguments, paths, or output formats. Keep detailed setup and parameter reference material in `docs/`; the main README introduces the project and common workflows.

Tests under `tests/` remain ignored for local work. Do not add generated outputs, model weights, credentials, or local test artifacts. The viewer includes its existing application checks:

```bash
node --test apps/viewer/viewer.test.cjs
```

For documentation changes, verify local links and image paths and run `git diff --check`. For code changes, verify the affected workflow and document any external services required.
