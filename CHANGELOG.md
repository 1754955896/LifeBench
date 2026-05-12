# Changelog

本项目的所有重要变更都将记录在此文件中。

## 2026-05-11

### QA生成器修复

#### qa_unanswerable_generator.py
- 添加 `evidence` 字段为空数组，确保问题数据包含必要字段

### 手机数据格式修正

#### phone_operation_generator.py
- 修改 `faceRecognition` 字段从数组类型改为字符串类型
- 更新模板定义和格式说明中的 `faceRecognition` 描述
- 确保生成的照片数据符合字符串格式要求

### 数据目录文档更新

#### life_bench_data/README.md
- 更新目录结构说明，区分 version1（旧版单源格式）和 version2（新版多源格式）
- 详细说明各版本的数据文件结构

#### life_bench_data/version1/README.md
- 新增版本1说明文档
- 包含目录结构、用户列表、各用户数据文件说明

#### life_bench_data/version2/README.md
- 新增版本2说明文档
- 包含目录结构、用户列表、多源格式数据说明

---

## 2026-05-09

### 路径处理与项目结构优化

#### run.py
- 优化路径处理逻辑，确保 base-path 解析为绝对路径并添加项目根目录到 sys.path

#### simulator.py
- 确保 file_path 以 / 结尾，优化路径拼接

#### all_qa_generator.py
- 增加并行 LLM 调用以重新分类问答对类型，优化类型统计逻辑

#### daily_simulator.py
- 增加中文转拼音功能，优化记忆文件命名和配置文件加载路径

#### outline_optimizer.py
- 修改优化后的 daily_draft 保存路径

#### memory.py
- 延迟初始化记忆管理器，优化模型路径设置

#### phone_data_gen.py
- 增加类型均匀采样逻辑，优化手机数据采样过程

#### templates/
- 更新模板输出格式，确保 JSON 格式一致性

#### persona_address_generator.py
- 优化配置文件加载路径，确保使用项目根目录下的 config.json

### 事件匹配分析功能

#### run.py (事件匹配分析)
- 添加事件匹配分析功能，处理 daily_event 等文件的匹配字段

#### check_event_matching.py
- 修改匹配分析标准，增强匹配条件的灵活性
- 禁用未匹配生成选项以优化事件匹配逻辑

### 手机数据生成器改进

#### phone_operation_generator.py
- 添加不支持操作类型转换功能，确保生成的数据符合支持类型
- 添加 agent_chat 类型支持及字段校验
- 优化手机数据生成逻辑

### QA生成器修复

#### qa_unanswerable_generator.py
- 修复问题生成逻辑，确保必要字段正确设置

#### QAGenerator
- 更新已有文件加载逻辑，添加分类处理说明
- 添加知识更新类型处理，确保分类结果包含知识更新
- 更新问题类型描述，增强模式识别和隐藏信息的定义
- 更新问题类型说明，增强对时间推理和知识更新的描述

#### QACausalGenerator
- 添加手机操作数据时分配 phone_id，确保唯一性
- 优化证据处理逻辑，扁平化证据结构以提高可读性

#### QAHiddenInfoGenerator
- 修改证据提取逻辑，直接返回数据，简化结构

#### template_qa.py
- 修复无回答问题模板的格式，移除多余字段

### 文档更新

#### README.md
- 更新使用说明，简化脚本路径，确保用户更易于执行命令
- 添加使用示例和命令行参数说明

### 检查脚本

#### 新增脚本
- `scripts/add_summarized_info.py`: 为 phone_data 目录下的 calendar, note, photo, push 文件添加 summarized_info 字段

### 数据转换脚本

#### 01convert_to_multi_source_yuxiaowen.py
- 修复 evidence 中的 raw_data 嵌套 data 字段问题
- 当 evidence 本身有嵌套的 data 字段时，展开取内层内容

---

## 2026-05-08

### QA生成器改进

#### qa_harmful_memory_generator.py
- 重构 `_generate_privacy_phone_operations` 方法，使用规划 + phone_op_generator.generate 模式
- LLM 先生成操作计划（operation_type + generation_hint），再调用 phone_op_generator.generate 执行

#### qa_unanswerable_generator.py
- 修改输出格式对齐 format1（required_events_id）
- 移除 required_events 字段，直接设置 required_events_id = []

#### qa_knowledge_updating_generator.py
- 添加 phone_id_counters 和 phone_id_lock 初始化
- 在 `_add_generated_phone_data` 中添加 phone_id 分配逻辑

#### all_qa_generator.py
- 修改加载已有问题文件后统一经过分类处理
- `classify_single_qa` 新增：如果原类型是 Knowledge_update，确保分类结果中包含 Knowledge_update

### 手机数据生成改进

#### phone_operation_generator.py
- 添加 ALLOWED_FIELDS 常量，定义各数据类型允许的字段
- `_parse_result` 和 `_fix_single_format` 添加清理多余字段逻辑

#### phone_data_gen.py
- 修复为未匹配原子事件生成数据时缺少 atomic_id 的问题
- 重命名阶段新增：如果 atomic_id 字段缺失，补充为空数组 []

### 检查脚本

#### 新增脚本
- `scripts/check_phone_data_format.py`: 检查手机数据格式一致性
- `scripts/compare_phone_data_count.py`: 对比新旧手机数据类型数量
- `scripts/check_qa_data_format.py`: 检查QA数据格式一致性

### 文档更新

#### README.md
- 新增 Usage 部分（完整流程、分步运行、命令行参数）
- 新增 Configuration 配置说明
- 新增 Directory Structure 目录结构
- 新增 Checkpoint 说明（断点续跑机制）

### check_event_matching.py
- main 函数中加载 daily_event_data 后检查是否已有 atomic_id 字段，如有则跳过所有处理

---

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

### 硬路径地址修改
- 更新代码中所有硬路径地址为相对路径，提升代码的可移植性和环境适应性

### singlehopQA的asktime约束
- 在`qa_single_generator.py`中添加逻辑，确保生成的单跳问题（single-hop question）的提问时间（ask_time）满足以下约束：
  - 所有引用的必需事件（required_events_id）其发生日期必须在提问时间之前。
  - 如果设计的问题中引用的最晚事件发生在 ask_time 之后，LLM 应主动将 ask_time 调整到该事件所在月份之后（YYYY-MM 格式，最晚为 2025-12），以确保时间逻辑一致。
