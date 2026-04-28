# Event Templates 模块

本模块包含所有 LLM 调用所使用的 prompt 模板，按功能划分。

## 文件说明

| 文件 | 功能 | 使用场景 |
|------|------|---------|
| [template_mr.py](template_mr.py) | MonthlyRefiner 月度优化器模板 | 、月度事件优化 |
| [template_refiner.py](template_refiner.py) | 生活变化分析与事件优化模板 | 事件扩展优化 |
| [template_edit.py](template_edit.py) | 事件编辑模板 | 数据修改、筛选 |
| [template_scheduler.py](template_scheduler.py) | 大纲规划模板 | 每日日程安排 |
| [template_temporal.py](template_temporal.py) | 时序QA模板 | QA生成 |
| [template_nd.py](template_nd.py) | NDQA模板 | QA生成 |
| [template_qa.py](template_qa.py) | 通用问答模板 | QA 生成 |
| [templates.py](templates.py) | 通用模板 | 通用 prompt |
| [README.md](README.md) | 本文档 | 模块说明 |
