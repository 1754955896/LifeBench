# memory 子目录 — 结构化记忆存储 / 检索 / 巩固 / 嵌入

每日模拟使用的结构化记忆系统（区别于 `event/memory_structure/` 中的旧版 `MemoryModule`）。`MemoryStore` 去单例，每个日期分片独立实例。

## 文件

| 文件 | 说明 |
|------|------|
| `store.py` | `MemoryStore` — 结构化记忆存储。 |
| `embedding.py` | `EmbeddingModel` — 嵌入模型加载与编码。 |
| `retrieval.py` | `build_short_memory` — 短期记忆检索：从 MemoryStore 构建唯一的结构化短期记忆上下文。 |
| `consolidation.py` | `FuzzyMemoryBuilder` — 草稿派生的模糊记忆（冷启动）。 |
