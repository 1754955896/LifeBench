# Generate a life history

Run all commands from the repository root after completing [installation](installation.md).

## Run a Simulation

After setup, create a new output directory, copy a complete sample persona, and generate a full year:

```bash
python -c "from pathlib import Path; Path('output/fenghaoran').mkdir(parents=True, exist_ok=True)"
python -c "from shutil import copyfile; copyfile('life_bench_data/version2/data/fenghaoran/persona.json', 'output/fenghaoran/persona.json')"
python scripts/run.py --base-path output/fenghaoran --year 2025 --months 12
```

For an existing run, retain its persona and rerun only the final command with the same time range. The output directory contains daily drafts, daily events, an event tree, phone records, and `QA_all/QA.json`. Choose a separate directory for a different persona or time range.

## Generate New Personas

To create new personas, provide source descriptions and run `scripts/run/persona_gen.py` before the simulation. The generator expands each record into a complete profile with relationships and grounded locations.

The example below creates one source description and generates three variants. First supply your reference database at `input/generated/refer.json`, using the schema in the [persona guide](../src/lifebench/persona/README.md). Local reference databases under `persona_file/` are ignored and are not included in a clone. Run the file preparation commands once in a new working directory:

```bash
python -c "from pathlib import Path; Path('input/generated').mkdir(parents=True, exist_ok=True)"
python -c "import json; from pathlib import Path; Path('input/generated/descriptions.json').write_text(json.dumps(['Lives in Yuhang, Hangzhou, works in the internet industry, and enjoys the outdoors.'], indent=2), encoding='utf-8')"
python scripts/run/persona_gen.py --file-path input/generated --ref-file refer.json --input-mode auto --input-format json --input-file descriptions.json --output-file person.json --start 0 --end 1 --variants-per-input 3 --diversity high --seed 42 --as-of-date 2025-01-01
```

This writes `input/generated/person.json` and its aligned `person_locations.json`. Run all generated personas with the batch runner:

```bash
python scripts/run_all.py --persona-folder input/generated --year 2025
```

## Generate QA from Existing Data

To generate QA from an existing generated user directory, run the standalone QA script from the repository root:

```bash
python scripts/run/qa_gen.py --data-path output/fenghaoran
```

Replace `output/fenghaoran` with the directory containing the generated `persona.json`, `daily_draft.json`, `daily_event.json`, `event_tree.json`, and `phone_data/`. Keep the accompanying `process/` directory and any generated `special_event.json` in place. Configure the LLM provider as described in [installation](installation.md).

The script defaults to 2025. If the generated data uses another year, supply the matching `--year` value.

The script generates nine question categories and writes the final question-answer pairs to `QA_all/QA.json` under the supplied directory. Each record includes the question, answer, scoring points, required event IDs, categories, evidence, and ask time. Additional phone evidence is saved in `phone_data/new/`; use this directory together with the final QA file.

## Batch Generation

The batch runner reads a `person.json` array and, when present, an aligned `person_locations.json` from the selected input directory:

```bash
# Process the 10 sample personas in input/person.json
python scripts/run_all.py

# Process positions 1 through 5, inclusive
python scripts/run_all.py --start-id 1 --end-id 5

# Generate all stages except QA
python scripts/run_all.py --generate-qa 0
```

Batch-specific options are `--persona-folder` (default `input/`), `--start-id`, and `--end-id` (both default to `0`, meaning no bound at that end). It also accepts `--process-path`, `--max-workers`, the three `--generate-*` switches, `--year`, and `--dry-run`. It always processes full years and does not accept `--base-path`, `--instance-id`, `--months`, `--interactive`, or `--no-phone-sample`.

For selected stages, see the [standalone script reference](../scripts/run/README.md). These scripts do not perform every orchestration step in `scripts/run.py`, which also handles event matching, intermediate-file organization, and monthly reports. When calling the phone stage separately, specify the full date range:

```bash
python scripts/run/phone_gen.py --file-path output/fenghaoran/ --start-time 2025-01-01 --end-time 2025-12-31
```

To resume, rerun the original command with the same input, output directory, persona range, and time range. The integrated runner checks existing draft, event, and report files; other stages have their own reuse rules. File existence is not a completeness check. Use a new output directory for a fresh generation instead of selectively deleting dependent artifacts.
