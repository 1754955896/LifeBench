# GitHub 仓库改进要求

**适用仓库：** LifeBench（version2 分支）  
**作者：** Zihao  
**DDL：** 下周一前完成所有改进并推送

---

这份文档列出了当前仓库存在的具体问题及改进要求。这些不是风格建议，是一个能被别人使用的合格 GitHub 仓库的基本标准。

---

## 0. 为什么这件事重要

一个 GitHub 仓库不只是你自己的代码存档，它是你和别人协作、让别人理解并使用你工作的唯一界面。一个混乱的仓库传达的信息是：这个项目不值得信任。

具体来说，如果一个新人打开这个仓库：
- 他不知道从哪里开始运行
- 他不知道 `event/copy/` 是什么，敢不敢删
- 他运行时发现 API key 是写死的，但已经暴露在 git 历史里
- 他看到 `fenghaoran_copy/` 不知道这是不是有用的数据

这些问题每一条都会让协作者放弃。

---

## 一、安全问题（必须立即修复）

### 1.1 API Key 硬编码并提交到仓库

**问题：** `config.json` 包含真实 API key，且已提交到 git。

```json
{
  "llm": {
    "api_key": "sk-76bd3e29019f4a518a410abf5f915bd7"
  },
  "map_tool": {
    "api_key": "e8f87eef67cfe6f83e68e7a65b9b848b"
  }
}
```

**后果：** 任何能访问这个仓库的人都可以使用你的 API 额度。这些 key 在 git 历史里会永久存在，即使你删掉文件也没用。

**要求：**
1. 立即去 DeepSeek 和地图平台撤销这两个 key，重新申请
2. 将 `config.json` 加入 `.gitignore`
3. 创建 `config.example.json`，把所有 key 替换为占位符：
   ```json
   {
     "llm": {
       "api_key": "YOUR_DEEPSEEK_API_KEY_HERE",
       "base_url": "https://api.deepseek.com"
     },
     "map_tool": {
       "api_key": "YOUR_MAP_API_KEY_HERE"
     }
   }
   ```
4. 在 README 中说明：复制 `config.example.json` → `config.json` 并填入自己的 key

---

## 二、.gitignore 缺失（必须修复）

**问题：** 仓库根目录没有 `.gitignore`，导致以下文件全部被 git 追踪：

- `.idea/`：IDE 配置文件，每个人的环境不同，这些文件提交后会给协作者制造冲突
- `__pycache__/` 和 `.pyc` 文件：Python 编译缓存，平台相关，不应提交
- `event/local_models/`：包含模型权重（`model.safetensors`、`pytorch_model.bin` 等大型二进制文件），这些文件不应进入 git，应单独下载

**要求：** 在根目录创建 `.gitignore`，至少包含：

```
# IDE
.idea/
.vscode/
*.iml

# Python
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
*.egg-info/

# 配置（包含 key）
config.json

# 模型权重
event/local_models/

# 本地输出（不提交生成结果）
*.log
```

---

## 三、Commit 规范问题

### 3.1 Commit 信息无意义

**当前仓库的 commit 历史：**

```
904aef9  new version 20260423:add QA generator
97c075c  new version
96660ea  add readme
1b21dbb  add atomic type
96650a9  add en
bc51e3a  add en
af37990  add en
b9ad928  add en
4c97fd1  add en
...（连续 10+ 个 "add en"）
a92cd7d  final-2026.02.10
0a7fc0a  final-2026.02.09
6e5c68f  final-2026.02.09
```

这样的 commit 历史等于没有历史。当你需要排查某个 bug 是什么时候引入的，或者协作者想理解你做了什么改动，这些信息没有任何帮助。

**要求：** 每次 commit 的信息必须能回答"改了什么、为什么改"：

| 坏的写法 | 好的写法 |
|---|---|
| `new version` | `feat(qa): add 9 QA generator classes with pluggable interface` |
| `add en` | `data: add English persona data for users 1-3` |
| `final-2026.02.09` | `fix(scheduler): resolve event overlap in holiday periods` |
| `add readme` | `docs: add README with setup instructions and dataset overview` |

**Commit 信息格式规范：**

```
<类型>(<范围>): <简短描述>

# 类型：feat / fix / refactor / docs / data / test / chore
# 范围：涉及的模块，如 qa / phone / scheduler / pipeline
# 简短描述：动词开头，说清楚做了什么
```

### 3.2 Commit 频率过低

一个月只有 1-2 次 commit，说明你把大量改动攒在一起提交。这使得：
- 每次 commit 包含几十个文件的改动，无法 review
- 出问题时无法定位到具体改动
- 协作者无法了解进展

**要求：** 每完成一个独立的改动（一个 bug fix、一个新功能、一个模块重构）就 commit 一次。一天多次 commit 是正常的，几周一次是不正常的。

---

## 四、命名规范问题

### 4.1 文件命名不一致

当前仓库中混用了多种命名风格：

| 文件 | 问题 |
|---|---|
| `Interface_1.py`、`Interface_2.py` | 首字母大写 + 数字编号，既不是类名也不是函数名 |
| `QA_gen.py`、`QaGenerator.py` | 同一概念有两种写法 |
| `phone_gen.py` | 存在于根目录和 `run/` 目录（重复） |
| `GraphGenerator.py`、`GraphRefiner.py` | 类名风格用在了文件名上 |

**要求：** Python 文件名统一使用 `snake_case`（小写加下划线）。具体改动：

- `Interface_1.py` → `draft_edit_interface.py`（或更能说明用途的名字）
- `Interface_2.py` → `phone_edit_interface.py`
- `QA_gen.py` → `qa_gen.py`
- `QaGenerator.py` → `qa_generator.py`（或合并到 `__init__.py`）
- `GraphGenerator.py` → `graph_generator.py`
- `GraphRefiner.py` → `graph_refiner.py`

名字要能说明**用途**，不要用 `Interface_1`、`Interface_2` 这种靠数字区分的名字——下个月你自己都不记得 1 和 2 分别是什么。

### 4.2 目录命名问题

| 目录 | 问题 |
|---|---|
| `event/copy/` | "copy" 是临时操作的产物，不是一个模块 |
| `fenghaoran_copy/`、`fenghaoran_reorganized/` | 工作过程中的临时目录被提交 |
| `fenghaoran/` | 用真实人名命名样本数据目录 |

**要求：**
- `event/copy/` 删除或将其内容合并到正确位置
- `fenghaoran_copy/`、`fenghaoran_reorganized/` 直接删除
- 样本数据目录改为 `examples/` 或 `sample_data/`，子目录用 `user_001/`、`user_002/` 命名，不要用真实人名

---

## 五、目录结构与文档问题

### 5.1 子目录没有说明文档

打开这个仓库，除了根目录的 README，每个子目录都没有任何说明。一个新协作者面对以下目录时完全不知道该怎么理解：

```
event/copy/          # 这是什么？是备份？是旧版本？
event/draft/         # draft 是草稿的意思，但这里面是 pipeline 核心模块
event/edit/          # 编辑什么？怎么用？
event/tools/         # 工具，什么工具？
lib/                 # 前端 JS 库放在这里是为什么？
persona/             # 和 data/ 什么关系？
test/output/         # 为什么测试输出要提交到仓库？
```

**要求：** 以下目录必须各自有一个 `README.md`，至少说明：这个目录是什么、包含什么文件、怎么使用：

- `event/` — 整个事件生成模块的入口说明
- `event/draft/` — 大纲生成相关模块
- `event/edit/` — 编辑 agent 使用说明
- `event/phone_generator/` — 手机数据生成各类说明
- `event/qa_generator/` — QA 生成器插件说明，如何新增一个生成器
- `event/templates/` — 模板文件组织说明
- `event/tools/` — 各工具脚本用途
- `run/` — 各入口脚本用途和参数说明
- `utils/` — 工具函数说明

### 5.2 根目录 README 不完整

当前 README 说明了"是什么"，但缺少：

- 完整的环境配置步骤（Python 版本要求？需要下载 `local_models/`？怎么下？）
- 运行一个完整例子的步骤（从 persona 到 QA 输出）
- 目录结构说明（各文件夹是什么）
- 如何在已有数据基础上运行特定阶段（checkpoint 机制）
- 如何扩展新的 QA 生成器

**要求：** 补充 README，使一个完全没有看过代码的人能在 30 分钟内跑起来第一个例子。

---

## 六、代码与工程问题

### 6.1 硬编码的本地路径

`run_all.py` 中存在：

```python
sys.path.append('D:\pyCharmProjects\pythonProject4')
```

这是你本地 Windows 机器的绝对路径。任何其他人运行这段代码都会静默失败（`sys.path.append` 不会报错，只是路径不生效）。

**要求：** 删除所有硬编码路径，改用相对路径或动态计算项目根目录：

```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
```

### 6.2 重复文件

`phone_gen.py` 在根目录和 `run/` 目录各存在一份。两份是否一致？哪个是最新的？

**要求：** 保留一份，删除另一份，根目录不应该存放属于某个子模块的脚本。

### 6.3 测试输出提交到仓库

`test/output/` 和 `test/process/` 包含大量生成的 JSON 数据文件，这些是运行测试产生的输出，不应提交到 git。

**要求：**
- 将 `test/output/` 和 `test/process/` 加入 `.gitignore`
- 已提交的内容用 `git rm -r --cached test/output/ test/process/` 从追踪中移除

### 6.4 前端依赖直接放在仓库里

`lib/` 目录包含 `tom-select`、`vis-9.1.2` 等第三方 JS 库的完整代码。这些是第三方库，不应提交到自己的仓库。

**要求：** 如果确实需要这些库，改用 CDN 引用或 npm/yarn 管理，并将 `lib/` 加入 `.gitignore`。如果只是临时用的，直接删除。

### 6.5 依赖版本管理不规范

`requirements.txt` 中大多数依赖没有固定版本：

```
openai          # 哪个版本？openai 1.x 和 0.x 接口完全不同
holidays        # 无版本
numpy           # 无版本
sentence_transformers  # 无版本
transformers==4.37.0  # 只有这一个固定了版本
```

**要求：** 所有依赖固定版本。方法：在你的开发环境中运行 `pip freeze | grep -E "openai|holidays|numpy|pandas|sentence_transformers|transformers|pyarrow|pypinyin|pyvis"` 查看当前版本，然后更新 `requirements.txt`。

---

## 七、协作规范

### 7.1 没有 CONTRIBUTING 说明

如果有人想参与贡献，他不知道：
- 应该从哪个分支开发
- PR 的流程是什么
- 新增 QA 生成器需要遵循什么接口

**要求（可选，但建议）：** 创建 `CONTRIBUTING.md`，说明分支策略和贡献流程。

### 7.2 分支命名

`version2` 不是好的分支名，它没有说明这个分支的目的和状态。

**供参考的分支命名习惯：**
- `main` / `master`：稳定版本，随时可以运行
- `dev`：开发主干
- `feat/qa-generator`：特定功能开发
- `fix/phone-data-schema`：特定 bug 修复

---

## 改进优先级

| 优先级 | 问题 | 原因 |
|---|---|---|
| **立即** | API Key 泄露（1.1） | 安全风险，别人在用你的额度 |
| **本周内** | 添加 `.gitignore`（二） | 防止更多垃圾文件进入 |
| **本周内** | 删除 `event/copy/`、`fenghaoran_copy/`（四） | 清理无效文件 |
| **本周内** | 修复硬编码路径（6.1） | 代码在别人机器上跑不起来 |
| **下周前** | 补全子目录 README（5.1） | 协作者看得懂才能用 |
| **下周前** | 规范 commit 信息（三） | 从下一次 commit 开始执行 |
| **下周前** | 补全根目录 README（5.2） | 让别人能独立运行 |
| **下周前** | 统一命名规范（四） | 整理后再交付 |

---

最后说一点：这些问题不是因为你写代码写得不好，而是因为没有把"让别人能用"当成工作的一部分。代码质量和仓库质量是两件事，两件事都要做好。
