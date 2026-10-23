"""Opt-in prompt dispatch; legacy builders return byte-for-byte original prompts."""
from functools import wraps
import importlib
import inspect

from src.lifebench.utils.locale_context import international_run

_MODULES = {'base_profile': 'base_profile', 'profile_enrich': 'profile_enrich', 'address_places': 'address_places',
            'narrative': 'narrative', 'enrich': 'narrative', 'enrich_consistency': 'consistency',
            'persona_consistency': 'consistency', 'relation_plan': 'relation_plan',
            'contact_group': 'contact_group'}


def international_builder(builder):
    stage = builder.__name__.removeprefix('build_').removesuffix('_prompt')
    signature = inspect.signature(builder)
    @wraps(builder)
    def build(*args, **kwargs):
        body = builder(*args, **kwargs)
        if not international_run():
            return body
        bound = signature.bind(*args, **kwargs)
        bound.apply_defaults()
        module = importlib.import_module('.' + _MODULES.get(stage, 'common'), __name__)
        return module.render(stage, body, bound.arguments)
    return build
