# memory_structure 子目录 — 旧版记忆模块

旧版记忆结构（基于 sentence-transformers 的全局单例记忆模块）。

## 文件

| 文件 | 说明 |
|------|------|
| `memory.py` | `MemoryModule` — 记忆模块（全局单例/多例可选，统一管理记忆操作）。 |

> 注意：新版每日模拟的记忆系统已迁至 [`event/simulation/memory/`](../simulation/memory/README.md)（`MemoryStore` / `FuzzyMemoryBuilder` / `build_short_memory` / `EmbeddingModel`）。本目录仅保留旧版 `MemoryModule`。
