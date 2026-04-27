# qa_generator 子目录 — 问答对生成器

生成多种类型的问答对，用于测试 Agent 记忆系统的不同能力。

## 生成器

| 文件 | 说明 |
|------|------|
| `base_generator.py` | QA 生成基类 |
| `qa_single_generator.py` | 单跳问答生成 |
| `qa_multi_hop_generator.py` | 多跳推理问答生成 |
| `qa_temporal_generator.py` | 时序推理问答生成 |
| `qa_knowledge_updating_generator.py` | 知识更新型问答生成 |
| `qa_conflict_generator.py` | 冲突记忆问答生成 |
| `qa_harmful_memory_generator.py` | 有害记忆问答生成 |
| `qa_hidden_info_generator.py` | 隐藏信息问答生成 |
| `qa_pattern_recognition_generator.py` | 模式识别问答生成 |
| `qa_unanswerable_generator.py` | 不可回答型问答生成 |
| `qa_causal_generator.py` | 因果推理问答生成 |
| `phone_operation_generator.py` | 手机操作类问答生成 |
