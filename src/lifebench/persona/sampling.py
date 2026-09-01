"""Reproducible reference sampling local to persona synthesis."""

import hashlib
import random
import secrets
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class SampledReference:
    person: Dict[str, Any]
    ref_index: int


def derived_seed(seed: Optional[int], source_index: int, stage: str) -> Optional[int]:
    if seed is None:
        return None
    payload = "%s:%s:%s" % (seed, source_index, stage)
    return int(hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16], 16)


def derived_variant_seed(
    seed: Optional[int], source_index: int, variant_index: int, stage: str,
    run_seed: Optional[int] = None,
) -> Optional[int]:
    effective_seed = run_seed if run_seed is not None else seed
    if effective_seed is None:
        return None
    payload = "%s:%s:%s:%s" % (effective_seed, source_index, variant_index, stage)
    return int(hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16], 16)


def _resolve_run_seed(seed: Optional[int]) -> int:
    """返回恒为整数的运行种子，保证 seed=None 时抽样仍可复现且各阶段一致。"""
    return int(seed) if seed is not None else secrets.randbits(63)


class PersonaReferenceSampler:
    def __init__(self, refer_data: Dict[str, Any], seed: Optional[int] = None, run_seed: Optional[int] = None):
        self.refer_data = refer_data
        self.seed = seed
        self.run_seed = run_seed if run_seed is not None else _resolve_run_seed(seed)

    def select_for_person(self, key: str, count: int, source_index: int) -> List[Any]:
        items = self.refer_data.get(key)
        if not isinstance(items, list) or not items:
            raise ValueError("参考数据缺少非空数组: %s" % key)
        if count < 0 or count > len(items):
            raise ValueError("%s 的采样数量非法: %s" % (key, count))
        rng = random.Random(derived_seed(self.run_seed, source_index, "reference:" + key))
        return rng.sample(items, count)

    def select_for_variant(
        self, key: str, count: int, source_index: int, variant_index: int,
        run_seed: Optional[int] = None,
    ) -> List[Any]:
        items = self.refer_data.get(key)
        if not isinstance(items, list) or not items:
            raise ValueError("参考数据缺少非空数组: %s" % key)
        if count < 0 or count > len(items):
            raise ValueError("%s 的采样数量非法: %s" % (key, count))
        seed = derived_variant_seed(self.run_seed, source_index, variant_index, "reference:" + key, run_seed)
        return random.Random(seed).sample(items, count)

    def references_for_person(self, source_index: int) -> Dict[str, List[str]]:
        return {
            "hobbies": self.select_for_person("兴趣", 12, source_index),
            "aim": self.select_for_person("目标规划", 6, source_index),
            "traits": self.select_for_person("价值观", 6, source_index),
        }

    def references_for_variant(
        self, source_index: int, variant_index: int, run_seed: Optional[int] = None,
    ) -> Dict[str, List[str]]:
        return {
            "hobbies": self.select_for_variant("兴趣", 12, source_index, variant_index, run_seed),
            "aim": self.select_for_variant("目标规划", 6, source_index, variant_index, run_seed),
            "traits": self.select_for_variant("价值观", 6, source_index, variant_index, run_seed),
        }


def sample_from_reference_pool(
    pool: List[Dict[str, Any]],
    target_count: int,
    required_indices: Optional[List[int]] = None,
    exclude_indices: Optional[List[int]] = None,
    seed: Optional[int] = None,
) -> List[SampledReference]:
    required = list(required_indices or [])
    excluded = list(exclude_indices or [])
    if target_count < 0:
        raise ValueError("target_count 不能小于 0")
    if len(required) != len(set(required)):
        raise ValueError("required_indices 不能包含重复索引")
    if len(excluded) != len(set(excluded)):
        raise ValueError("exclude_indices 不能包含重复索引")
    overlap = set(required) & set(excluded)
    if overlap:
        raise ValueError("required_indices 与 exclude_indices 冲突: %s" % sorted(overlap))
    total = len(pool)
    invalid = [index for index in required + excluded if index < 0 or index >= total]
    if invalid:
        raise ValueError("参考索引越界: %s" % sorted(set(invalid)))
    if len(required) > target_count:
        raise ValueError("required_indices 数量不能超过 target_count")
    available = [index for index in range(total) if index not in set(required) and index not in set(excluded)]
    remaining = target_count - len(required)
    if remaining > len(available):
        raise ValueError("参考池不足：需要 %d，实际可用 %d" % (remaining, len(available)))
    rng = random.Random(seed)
    selected = required + rng.sample(available, remaining)
    return [SampledReference(pool[index], index) for index in selected]
