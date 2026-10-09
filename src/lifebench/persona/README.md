# Persona Generation and Management

Generates user personas, including basic information, personality traits, and daily habits.

## Core Files

### Entry Points and Orchestration

| File | Description |
|------|-------------|
| `persona_gen.py` | `PersonaGenerator`: main persona generation entry point. |
| `pipeline.py` | `PersonaPipeline`: staged generation and concurrent orchestration. |
| `stages.py` | Stage functions for base profiles, narratives, enrichment, consistency, relationship slots, contact groups, and variant blueprints. |
| `run_record.py` | `PersonaRunRecord`: generation run records. |

### Data Models

| File | Description |
|------|-------------|
| `internal_models.py` | Internal structures: `InternalPersona`, `InternalContact`, `RelationSlot`, `CircleAnchor`, `PersonaResult`, and `BatchResult`. |
| `source_models.py` | Source structures: `NormalizedSource` and `CanonicalSeed`. |
| `variant_models.py` | `VariantBlueprint`: blueprint for a distinct persona variant. |

### Source Processing

| File | Description |
|------|-------------|
| `source_io.py` | `load_source_records`: reads arbitrary input sources. |
| `source_normalizer.py` | `SourceNormalizer`: uses structured LLM calls to extract explicit facts and soft cues from arbitrary fields or text. |
| `canonicalizer.py` | Converts sparse facts into a fixed 27-field profile skeleton and locks input facts. |
| `normalization.py` | Normalizes structured LLM responses, including contact addresses, relationship groups, and relationship plans. |

### Constraints, Diversity, and Sampling

| File | Description |
|------|-------------|
| `constraints.py` | Age, BMI, MBTI, and relative-age constraints. |
| `diversity.py` | Run seeds, structured distance measures, and diversity thresholds. |
| `sampling.py` | `PersonaReferenceSampler`: reference-pool sampling and derived seeds. |

### Grounding, Validation, and Output

| File | Description |
|------|-------------|
| `address_generation.py` | `PersonaAddressService`: grounds home, workplace, frequently visited places, and city landmarks. |
| `grounding.py` | Grounding context and consistency checks, including mobility profiles, employer anchors, social circles, and semantic quality errors. |
| `validation.py` | Validates profile keys, internal personas, and output contracts. |
| `output_adapter.py` | Converts to and preserves the legacy JSON output contract. |
| `local_io.py` | Atomic JSON writes and failure records. |

### Data Files

| File | Description |
|------|-------------|
| `personas.json` | Generated persona data. |

## Subdirectories

| Directory | Description |
|-----------|-------------|
| `persona_file/` | Persona reference files and final data, such as `complete_profiles.json`, `final.json`, and `refer.json`. |
| `prompts/` | Templates for base profiles, narratives, relationship plans, and contacts; see [prompts/README.md](prompts/README.md). |
| `eval/` | Persona evaluation scripts: `eval.py`, `eval_circle.py`, `eval_relation.py`, `metrics.py`, and `quality_gate.py`. |
| `tests/` | Persona unit tests; see [tests/README.md](tests/README.md). |

## Arbitrary Input and Diverse Variants

Arbitrary-input mode first uses an LLM to normalize input into explicit facts, soft cues, and original descriptions, then fills the fixed profile structure. Later stages do not modify explicit facts. Age and BMI are still calculated in code.

```powershell
python scripts/run/persona_gen.py `
  --input-mode auto `
  --input-format auto `
  --file-path data/persona/ `
  --input-file sparse_profiles.json `
  --output-file persona_list.json `
  --variants-per-input 3 `
  --diversity high
```

Supported container formats are `json`, `jsonl`, `csv`, `tsv`, `txt`, and `xlsx`. Reading Excel requires `openpyxl` in the environment. The final output remains a standard list of personas, without extraction confidence, field locks, variant IDs, or other internal data.

Python example:

```python
outputs = generator.generate_from_any(
    "Lives in Yuhang, Hangzhou, works in the internet industry, and enjoys the outdoors.",
    variants_per_input=3,
    diversity="high",
    seed=None,
)
```

`seed=None` creates a new run seed for each call. A fixed seed reuses the same reference sampling and variant prompts. Exact reproduction of model responses also depends on the provider's sampling implementation.

## Address Grounding and Location Data

By default, the persona CLI calls map services after generating the base structure to ground homes and regular workplaces in real POIs. It preserves administrative areas and explicit user-provided address facts. Real streets and building numbers returned by the map service are written back to the persona, and narrative and relationship stages continue with these frozen addresses.

Address assignment builds joint home/work candidate pools rather than independently selecting the first search result. Candidates are scored by administrative-area match, address completeness, batch reuse penalties, and commute plausibility. Straight-line distance provides a low-cost prefilter; route APIs are called only for the top two candidate pairs. Seeded weighted sampling then selects among high-scoring candidates. A fixed seed supports reproducibility, while different run seeds can produce substantially different but plausible location combinations from the same vague input.

Frequently visited places are first planned at `daily`, `weekly`, and `monthly` frequencies, using nearby, medium-range, and citywide search radii respectively. Nearby searches use POI coordinates and administrative information directly instead of geocoding every candidate again. Duplicate places are prohibited within one persona. Across a batch, reuse penalties discourage shared homes most strongly, allow moderate workplace sharing, and permit public-place sharing.

The map tool limits requests to 3 QPS across all generation threads by default. It retries temporary rate-limit errors such as `10014/10015/10019/10020/10021/10029` with exponential backoff, but does not repeatedly retry daily-quota errors. If fewer than three frequently visited places are successfully grounded, persona generation fails explicitly and records the failure instead of silently emitting an incomplete sidecar.

For a profile file named `person.json`, the batch location sidecar defaults to `person_locations.json`. Its outer array aligns exactly with the persona array. Illustrative record:

```json
[
  [
    {
      "name": "Home at Example Residential Community",
      "location": "120.000000,30.000000",
      "formatted_address": "No. 1 Example Road, Yuhang District, Hangzhou, Zhejiang",
      "city": "Hangzhou",
      "district": "Yuhang",
      "streetName": "Example Road",
      "streetNumber": "1",
      "description": "The persona's regular home"
    }
  ]
]
```

`scripts/run_all.py` writes each entry to the corresponding persona directory as `location.json`. The simulator reuses an existing file instead of randomly generating addresses again. Legacy data without a sidecar still uses the simulator's compatibility fallback.

Use `--skip-location-generation` in the persona CLI when no map API is available or for offline debugging. Use `--location-output` to specify the sidecar path.

Schools, sports venues, and interest groups with a defined physical meeting place are grounded in real POIs before contact generation and written to the same location sidecar as fixed social-circle locations. The runtime label is represented by JSON escapes `\u5173\u7cfb\u5708\u56fa\u5b9a\u5730`. Sports, fitness, and offline interest locations must be searched around the home's coordinates: roughly 3 km for daily activities, 6 km for weekly activities, and typically 7-8 km for other offline interests. If no suitable POI is found within the radius, generation fails instead of falling back to a random venue elsewhere in the city.

Contact homes are then assigned from real residential candidate pools based on circle type, shared places, workplaces, original administrative-area cues, and batch occupancy. Birthplace province, city, and district are also verified through map geocoding. Contacts who do not live together are not preferentially assigned the same residential POI.

Each persona also plans at least one `scope=city` public location, such as a museum, city park, library, sports center, or historic landmark matching their interests. These low-frequency `monthly` landmarks are an explicit exception to the home-radius rules. They are written to the sidecar alongside `daily` and `weekly` places near home or work. Frequent activities such as fitness, ball sports, running, reading, and classes must use the home as their search origin.

For home/work assignment only, call the public API directly:

```python
from src.lifebench.persona import PersonaAddressService

service = PersonaAddressService()
grounded, core_pois = service.allocate_persona_addresses(
    profile,
    seed=20260901,
    mobility_profile={"primary_transport": "transit", "explicit": True},
    reserved_addresses=existing_personas_or_locations,
)

batch_results = service.allocate_persona_batch(
    profiles,
    seeds=[20260901, 20260902],
    reserved_addresses=existing_personas_or_locations,
)
```

The CLI accepts `--reserved-address-file` to load existing persona or location JSON. It adds the primary personas' and their relations' homes to the occupied-address pool, reducing residential and workplace reuse across separate runs.
