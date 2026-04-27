# edit 子目录 — 多 Agent 数据编辑管线

使用多个 LLM Agent 对生成的事件数据进行批评、规划、执行和反思，以提高数据质量。

## Agent 角色

| 文件 | 说明 |
|------|------|
| `planning_agent.py` | 规划 Agent — 制定数据编辑计划 |
| `execution_agent.py` | 执行 Agent — 执行具体编辑操作 |
| `critic_agent.py` | 批评 Agent — 发现数据中的问题 |
| `reflection_agent.py` | 反思 Agent — 评估编辑效果并提出改进 |
| `writing_agent.py` | 写作 Agent — 负责具体文本生成 |
| `data_query_tool.py` | 数据查询工具 |

## 接口

| 文件 | 说明 |
|------|------|
| `Interface_1.py` / `Interface_2.py` | 两条不同的编辑管线接口 |
