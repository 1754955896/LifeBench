# Changelog

本项目的所有重要变更都将记录在此文件中。

##  2026-04-27

### 项目结构重构

#### 新增文件
- `CHANGELOG.md`: 项目变更日志文件，记录所有重要更新历史
- `CONTRIBUTING.md`: 贡献指南文档，规范代码提交流程和开发标准  
- `.gitignore`: Git版本控制忽略规则配置文件

#### 目录结构调整（标准化项目布局）

**核心代码迁移至 `src/lifebench/` 包结构：**
- `event/` → `src/lifebench/event/`
  - 事件生成与调度系统代码（包含日常模拟器、事件格式化器等）
  - 手机数据生成器模块（phone_data_gen.py及相关子模块）
  - QA问答生成系统（QaGenerator.py及qa_generator子目录）
  - 记忆结构处理模块（memory_structure/）
  - 数据编辑与模板系统（data_edit.py, templates/, edit/）
  - 草稿生成工具（draft_gen.py, draft/）
  
- `persona/` → `src/lifebench/persona/`
  - 人物画像生成核心逻辑（persona_gen.py）
  - 画像评估模块（eval/）
  - 生成工具函数库（gen_utils/）
  - 画像数据存储（persona_file/）
  
- `memory_file/` → `src/lifebench/memory_file/`
  - 个人记忆数据存储目录，存放生成的记忆文件
  
- `utils/` → `src/lifebench/utils/`
  - 通用工具类库（IO.py, llm_call.py, maptool.py, dataprocess.py等）
  - LLM调用封装、地图工具、数据处理等基础功能模块

**脚本文件迁移至 `scripts/` 目录：**
- `run/` → `scripts/run/`
  - 各阶段独立运行脚本（QA_gen.py, draft_gen.py, persona_gen.py, phone_gen.py, simulator.py等）
- `run.py` → `scripts/run.py`
  - 主运行脚本入口
- `run_all.py` → `scripts/run_all.py`
  - 全流程自动化执行脚本

**新建标准化输入输出目录：**
- `input/`: 统一输入数据目录，存放待处理的原始数据（如person.json等配置文件）
- `output/`: 统一输出数据目录，存放生成的结果数据和中间产物


### contactName字段硬校验
- 添加对`phone_generator/communication_generator.py`中contactName字段的硬校验，确保数据一致性


