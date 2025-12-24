# 项目介绍

本项目是一个生成用户画像及其事件的模拟系统，能够根据用户画像生成结构化的事件树、模拟日常事件序列，并生成相应的手机数据。

## 项目结构

```
D:\pyCharmProjects\pythonProject4/
├── data/                      # 主要历史运行数据存储目录
├── event/                     # 事件生成核心代码目录
│   ├── local_models/          # 本地模型文件
│   ├── DM.py                  # 决策模型
│   ├── Prob_Model.py          # 概率模型
│   ├── event_formatter.py     # 事件格式化工具
│   ├── event_refiner.py       # 事件优化器
│   ├── event_schema.csv       # 事件模式定义CSV
│   ├── event schema.xlsx      # 事件模式定义Excel
│   ├── fuzzy_memory_builder.py# 模糊记忆构建器
│   ├── memory.py              # 记忆模块
│   ├── memory_file/           # 记忆文件存储
│   ├── mind.py                # 思维模拟模块
│   ├── phone_data_gen.py      # 手机数据生成器
│   ├── scheduler.py           # 事件调度器
│   ├── templates.py           # 对话prompt模板
│   ├── test_agent_chat.py     # 智能体聊天数据测试
│   └── xlsx_to_csv.py         # Excel转CSV工具
├── memory_file/               # 全局记忆文件目录
├── output/                    # 默认输入输出文件目录
│   └── persona.json           # 默认用户画像文件
├── output_case/               # 示例运行结果
│   ├── 2025-12-19/            # 示例日期运行结果
│   ├── logs/                  # 示例运行日志
│   ├── phone_data/            # 示例手机数据
│   ├── process/               # 示例中间处理文件
│   ├── cumulative_summaries.json # 累积总结数据
│   ├── daily_state.json       # 每日状态数据
│   ├── event_decompose_dfs.json # 事件树结构
│   ├── monthly_summaries.json # 月度总结数据
│   └── persona.json           # 示例用户画像
├── persona/                   # 用户画像生成模块
│   ├── eval/                  # 评估工具
│   ├── gen_utils/             # 生成工具
│   └── persona_gen.py         # 用户画像生成主脚本
├── pic/                       # 图片资源目录
├── utils/                     # 通用工具函数目录
│   ├── IO.py                  # IO操作工具
│   ├── dataprocess.py         # 数据处理工具
│   ├── llm_call.py            # LLM调用工具
│   ├── maptool.py             # 地图工具
│   └── random_ref.py          # 随机引用工具
├── event_gen.py               # 事件生成主脚本
├── persona_gen.py             # 用户画像生成脚本
├── phone_gen.py               # 手机数据生成主脚本
├── requirements.txt           # 项目依赖文件
├── simulator.py               # 事件模拟主脚本
└── README.md                  # 项目说明文档
```


## 运行前准备

1. **API配置**：编辑 `utils/llm_call` 文件，配置OpenAI API密钥
2. **清理旧数据**：删除项目memory_file目录下的 `personal_memories.json` 文件
3. **准备画像文件**：将 `persona.json` 文件放置在指定的存储目录（默认在 `output` 文件夹中）中

## 运行流程

如果你不知道下面的参数使用，可以不设置参数，使用默认参数直接运行即可，要保证你设置的输入输出文件夹（默认在 `output` 文件夹中）存在，且包含persona.json 文件，否则运行会报错。

### 步骤1：生成事件树
```bash
python event_gen.py [参数]
```
- **功能**：调用 `scheduler` 模块生成事件树并进行处理
- **参数说明**：
  - `--base-path`：基础数据路径（默认：output/）
  - `--process-path`：处理文件路径（默认：process/）
  - `--max-workers`：最大工作线程数（默认：CPU核心数×2）
  - `--skip-gen`：跳过事件生成步骤
  - `--skip-schedule`：跳过事件规划步骤
  - `--skip-decompose`：跳过事件分解步骤
  - `--skip-reorder`：跳过事件重排和ID分配步骤
  - `--only-reorder`：仅执行事件重排和ID分配步骤
- **输入**：用户画像（persona.json）
- **输出**：
  - `process/event_1.json`：原始生成的事件
  - `process/event_2.json`：调整后的事件
  - `event_decompose_dfs.json`：分解后的事件树（主题事件-原子事件）

### 步骤2：模拟每日事件
```bash
python simulator.py [参数]
```
- **功能**：调用 `mind` 模块进一步调整事件并模拟日常行为
- **参数说明**：
  - `--file-path`：数据文件路径（默认：output/）
  - `--start-date`：开始日期（默认：2025-01-01）
  - `--end-date`：结束日期（默认：2025-12-31）
  - `--max-workers`：最大并行线程数（默认：30）
  - `--interval-days`：每个线程处理的天数（默认：16）
  - `--refine-events`：是否执行事件精炼（0：否，1：是，默认：1）
  - `--generate-data`：是否生成数据（0：否，1：是，默认：1）
  - `--format-events`：是否格式化事件（0：否，1：是，默认：1）
- **输入**：
  - 用户画像（persona.json）
  - 事件树文件（event_decompose_dfs.json）
  - 每日状态文件（daily_state.json，可选）
- **输出**：
  - `process/event_decompose_1.json`：进一步调整后的事件树（如果执行事件精炼）
  - 格式化后的每日事件（如果执行事件格式化）

### 步骤3：生成手机数据
```bash
python phone_gen.py [参数]
```
- **功能**：基于模拟事件生成手机数据
- **参数说明**：
  - `--file-path`：数据文件路径（默认：output/）
  - `--start-time`：开始日期（默认：2025-01-01）
  - `--end-time`：结束日期（默认：2025-12-31）
  - `--max-workers`：最大并行线程数（默认：32）
- **输入**：
  - 用户画像（persona.json）
  - 事件数据（output.json）
  - 联系人数据（phone_data/contact.json，可选）
- **输出**：
  - `phone_data/contact.json`：联系人数据
  - `phone_data/event_call.json`：通话记录
  - `phone_data/event_gallery.json`：相册记录
  - `phone_data/event_note.json`：笔记记录
  - `phone_data/event_push.json`：推送通知记录
  - `phone_data/event_fitness_health.json`：运动健康数据

## 默认配置

### 数据存储
- 所有数据的输入输出默认存储在 `output/` 文件夹
- 中间数据默认存储在 `output/process/` 文件夹
- 历史版本数据存储在 `data/` 文件夹中

### 核心模块
- **event_gen.py**：
  - 默认基础路径：`output/`
  - 默认处理路径：`process/`
  - 默认线程数：CPU核心数×2
  - 默认跳过已存在的输出文件

- **simulator.py**：
  - 默认文件路径：`output/`
  - 默认时间范围：2025-01-01 至 2025-12-31
  - 默认最大并行线程数：30
  - 默认每个线程处理天数：16
  - 默认执行事件格式化，事件精炼和数据生成

- **phone_gen.py**：
  - 默认文件路径：`output/`
  - 默认时间范围：2025-01-01 至 2025-12-31
  - 默认最大并行线程数：32
  - 默认生成数据类型：通话、相册、笔记、推送、运动健康

### prompt模板
- prompt模板定义在 `event/templates.py` 中

## 输出文件说明

### 事件生成模块
- **process/event_1.json**：原始事件生成结果
- **process/event_2.json**：经过调整的事件
- **event_decompose_dfs.json**：事件树结构，包含主题事件和原子事件的层级关系，已排序并分配ID

### 事件模拟模块
- **process/event_decompose_1.json**：进一步优化后的事件树（仅当执行事件精炼时生成）
- **monthly_summaries.json**：月度总结数据（仅当生成数据时创建）
- **cumulative_summaries.json**：累积总结数据（仅当生成数据时创建）
- **output/outputs.json**:每日模拟的最终输出
- **XXXX-XX-XX/* **:每日模拟的中间文件
  
### 手机数据模块
- **phone_data/contact.json**：联系人数据
- **phone_data/event_call.json**：通话和短信记录
- **phone_data/event_gallery.json**：相册记录
- **phone_data/event_note.json**：笔记和日历记录
- **phone_data/event_push.json**：推送通知记录
- **phone_data/event_fitness_health.json**：运动健康数据

## 日志系统

- 运行日志默认存储在 `output/log` 文件夹中
- 记录系统运行状态、错误信息和关键操作
- 支持调试和问题排查

## 扩展与定制

### 事件模板扩展
- 在 `event/templates.py` 中添加新的事件模板
- 遵循现有的模板格式和参数要求

### 模型定制
- 本地模型存储在 `event/local_models/` 目录
- 支持添加自定义的事件生成模型

### 数据格式调整
- 根据需要修改事件和手机数据的JSON格式
- 确保各模块间的数据兼容性
