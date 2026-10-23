"""Test-only telemetry around real structured calls; does not replace responses."""
import hashlib
import json
from pathlib import Path
import re
import threading
from copy import deepcopy


def install(folder, replay_successes=False):
    from src.lifebench.utils.structured_llm import StructuredLLMCaller, StructuredCallResult, _validation_errors
    root = Path(__file__).resolve().parents[2]
    config_path = root / 'config/config.json'
    config = json.loads(config_path.read_text(encoding='utf-8-sig')) if config_path.exists() else {}
    secrets = [config.get(section, {}).get('api_key') for section in ('llm', 'map_tool')]
    path = Path(folder) / 'structured_calls.jsonl'
    cache = {}
    if replay_successes and path.exists():
        for line in path.read_text(encoding='utf-8').splitlines():
            record = json.loads(line)
            if record.get('success') and 'data' in record:
                cache[record['prompt_hash']] = record
    original = StructuredLLMCaller.call_json_object
    lock = threading.Lock()
    def write(record):
        text = json.dumps(record, ensure_ascii=False, default=str)
        for value in secrets:
            if value:
                text = text.replace(value, '[REDACTED]')
        with lock, path.open('a', encoding='utf-8') as stream:
            stream.write(text + '\n')
    def traced(self, prompt, *args, **kwargs):
        match = re.search(r'\[PERSONA_INTERNATIONAL_STAGE:([^]]+)\]', prompt)
        stage = match.group(1) if match else 'legacy'
        record = {'stage': stage, 'prompt_hash': hashlib.sha256(prompt.encode()).hexdigest()}
        try:
            cached = cache.get(record['prompt_hash'])
            validator = kwargs.get('validator', args[0] if args else None)
            if cached and not _validation_errors(validator, deepcopy(cached['data'])):
                data = deepcopy(cached['data'])
                record.update(success=True, attempts=0, validation_errors=[], data=data, response_source='recorded_real_response')
                write(record)
                print('复用已成功的真实响应：' + stage, flush=True)
                return StructuredCallResult(data, 0, record['prompt_hash'])
            result = original(self, prompt, *args, **kwargs)
            record.update(success=True, attempts=result.attempts, validation_errors=result.errors, data=result.data, response_source='live_api')
            write(record)
            return result
        except Exception as error:
            record.update(success=False, error_type=type(error).__name__, errors=getattr(error, 'errors', []))
            write(record)
            raise
    StructuredLLMCaller.call_json_object = traced
