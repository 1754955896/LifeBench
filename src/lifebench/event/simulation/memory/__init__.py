# -*- coding: utf-8 -*-
"""每日模拟记忆子包：结构化记忆存储、检索、巩固与嵌入。

- store.py：MemoryStore（结构化存储，去单例，每分片独立实例）
- embedding.py：嵌入模型加载/编码
- retrieval.py：短期记忆检索/构建
- consolidation.py：状态型长记忆更新 + 草稿派生的模糊记忆（冷启动）
"""
from src.lifebench.event.simulation.memory.store import MemoryStore
from src.lifebench.event.simulation.memory.embedding import EmbeddingModel
from src.lifebench.event.simulation.memory.retrieval import build_short_memory
from src.lifebench.event.simulation.memory.consolidation import (
    update_long_term_memory,
    FuzzyMemoryBuilder,
)

__all__ = [
    "MemoryStore",
    "EmbeddingModel",
    "build_short_memory",
    "update_long_term_memory",
    "FuzzyMemoryBuilder",
]
