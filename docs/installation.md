# Installation

Run LifeBench directly from a cloned repository. All commands below assume the repository root; package installation with `pip install .` is not supported.

## Python Environment

```bash
git clone https://github.com/1754955896/LifeBench.git
cd LifeBench
conda create -n lifebench python=3.10
conda activate lifebench
python -m pip install -r requirements.txt
```

Python 3.10 and 3.11 are supported. Conda is optional; an existing isolated Python environment can also be used.

## Embedding Model

The simulator requires a local embedding model. Download it with the [Hugging Face Python API](https://huggingface.co/docs/huggingface_hub/package_reference/file_download#huggingface_hub.snapshot_download):

```bash
python -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='sentence-transformers/all-MiniLM-L6-v2', local_dir='src/lifebench/event/local_models/all-MiniLM-L6-v2', allow_patterns=['*.json', '*.txt', 'pytorch_model.bin', '1_Pooling/*'])"
```

The loader checks for `config.json`, `pytorch_model.bin`, `tokenizer_config.json`, and `vocab.txt` in `src/lifebench/event/local_models/all-MiniLM-L6-v2/`.

## Provider Configuration

For a new setup, copy the complete template:

```bash
python -c "from shutil import copyfile; copyfile('config/config.example.json', 'config/config.json')"
```

If `config/config.json` already exists, edit it instead. Set `llm.api_key`, `llm.base_url`, `llm.default_model`, `llm.reason_model`, and `map_tool.api_key` for your providers. Keep the remaining template sections.

LLM calls use an OpenAI-compatible endpoint. Set `default_model` and `reason_model` to the same model to use one throughout. Keep credentials in the ignored `config/config.json`; see the [runtime configuration reference](../config/README.md) for all options and the [map service guide](../src/lifebench/utils/README.md) for overseas service configuration.

Continue with [data generation](generation.md), or read the [CLI argument reference](configuration.md).
