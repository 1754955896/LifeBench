# lifebench 子包

核心代码模块，包含数据生成的各个子模块。

## 子模块

| 目录 | 说明 |
|------|------|
| `event/` | 事件与 QA 数据生成，包括日程、手机数据、问答对等 |
| `persona/` | 用户人设（Persona）数据的生成与管理 |
| `utils/` | 通用工具：LLM 调用、IO 处理、地图工具等 |
| `memory_file/` | 记忆结构文件 |

### event/ 子模块详细结构

| 目录 | 说明 |
|------|------|
| `simulation/` | 每日生活模拟引擎（日期分片并行、地理分配、记忆、反思） |
| `draft/` | 事件大纲生成相关脚本（Graph、Timeline、Refiner 等） |
| `edit/` | 多 Agent 数据编辑管线（规划、执行、反思、批评等 Agent） |
| `phone_generator/` | 手机各类型数据生成器（聊天、通话、健康、相册等） |
| `qa_generator/` | 各类型 QA 生成器（单跳、多跳、时序、冲突等） |
| `memory_structure/` | 记忆结构构建（模糊记忆、记忆类） |
| `tools/` | 工具函数（事件匹配、地址生成、xlsx 转 csv 等） |
| `templates/` | 提示词模板（详见 [templates/README.md](event/templates/README.md)） |
| `local_models/` | 本地 embedding 模型（all-MiniLM-L6-v2） |
