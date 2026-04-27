# persona 模块 — 用户人设数据生成与管理

负责生成用户画像（Persona）数据，包括基础信息、性格特征、日常习惯等。

## 核心文件

| 文件 | 说明 |
|------|------|
| `persona_gen.py` | Persona 数据生成主脚本 |
| `personas.json` | 生成的 personas 数据文件 |

## 子目录

| 目录 | 说明 |
|------|------|
| `persona_file/` | Persona 参考文件与最终数据（`complete_profiles.json`、`final.json`、`refer.json` 等） |
| `gen_utils/` | Persona 生成工具模板（`template.py`） |
| `eval/` | Persona 评估脚本（`eval.py`、`eval_circle.py`、`eval_relation.py`） |
