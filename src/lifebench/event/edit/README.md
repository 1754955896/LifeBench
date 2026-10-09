# Data Editing Agents

Uses multiple LLM agents to critique, plan, execute, and reflect on edits to generated event data.

## Agent Roles

| File | Description |
| --- | --- |
| `planning_agent.py` | Planning agent: prepares data editing plans. |
| `execution_agent.py` | Execution agent: performs editing operations. |
| `critic_agent.py` | Critic agent: identifies data issues. |
| `reflection_agent.py` | Reflection agent: evaluates edits and proposes improvements. |
| `writing_agent.py` | Writing agent: generates text. |
| `data_query_tool.py` | Data query utilities. |

## Interfaces

| File | Description |
| --- | --- |
| `draft_edit_interface.py` / `phone_edit_interface.py` | Interfaces for the two editing pipelines. |
