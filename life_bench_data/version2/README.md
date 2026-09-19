---
license: apache-2.0
language:
  - zh
  - en
tags:
  - life-logging
  - personal-assistant
  - long-term-memory
  - episodic-memory
  - question-answering
  - multi-source
  - phone-data
  - locomo
size_categories:
  - 10K<n<100K
task_categories:
  - question-answering
pretty_name: LifeBench 2.0
---

# 🧠 LifeBench 2.0

> 面向长期记忆评测的生活日志基准数据集 · **A Chinese Life-Logging Benchmark for Long-Term Memory Evaluation**

LifeBench 2.0 收集了 **10 位虚拟用户** 一整年（2025-01-01 ～ 2025-12-31）的完整生活数据，涵盖人物画像、每日生活事件、事件树、以及 **9 类手机操作数据**（短信、通话、日历、笔记、照片、推送、运动健康、联系人、智能助手对话），并配套 **数千条带证据与评分点标注的问答对**，用于评测大语言模型的长期记忆、时间推理与多跳问答能力。数据集提供 **中文（`data/`）** 与 **英文（`data_en/`）** 两个版本，以及转换为 **LoCoMo 对话格式（`locomo_format/`）** 的标准化版本。

## 📊 Dataset Statistics · 数据统计

| 指标 | 数值 |
|------|------|
| 👥 用户数 | 10 |
| 🌐 语言 | 中文（`data/`）· 英文（`data_en/`） |
| 📅 时间跨度 | 2025-01-01 ～ 2025-12-31（全年） |
| 🗓️ 每日生活事件 | 57,486 条 |
| 📱 手机数据记录 | 47,409 条（9 类数据源） |
| ❓ 问答对（QA_all / locomo） | 3,380 条 |
| 💾 数据体积 | 约 423 MB |

## 📁 Directory Structure · 目录结构

```
version2/
├── README.md                         # 本说明文档
├── data/                             # 中文版多源数据（10 位用户）
│   └── {user}/                       # 每位用户一个目录
│       ├── persona.json              # 用户画像
│       ├── daily_event.json          # 每日生活事件
│       ├── event_tree.json           # 事件树结构
│       ├── daily_draft.json          # 每日大纲（按月组织）
│       ├── phone_data/               # 手机操作数据（9 类）
│       │   ├── sms.json              # 短信
│       │   ├── call.json             # 通话记录
│       │   ├── calendar.json         # 日历
│       │   ├── note.json             # 笔记
│       │   ├── photo.json            # 照片
│       │   ├── push.json             # 推送通知
│       │   ├── fitness_health.json   # 运动健康
│       │   ├── contact.json          # 联系人
│       │   └── agent_chat.json       # 智能助手对话
│       └── QA_all/
│           └── QA.json               # 问答对（含证据与评分点）
├── data_en/                          # 英文版多源数据（结构与 data/ 一致）
└── locomo_format/                    # LoCoMo 对话格式
    ├── lifebench_locomo_conversation_format_v2.0_3380QA.json      # 中文
    └── lifebench_locomo_conversation_format_v2.0_3380QA_en.json   # 英文
```

## 👥 User List · 用户列表

| # | 用户 ID | 中文姓名 | 英文姓名 |
|---|---------|----------|----------|
| 1 | `fenghaoran` | 冯浩然 | Feng Haoran |
| 2 | `leimingxuan` | 雷铭轩 | Lei Mingxuan |
| 3 | `lumingqiang` | 卢明强 | Lu Mingqiang |
| 4 | `maxiulan` | 马秀兰 | Ma Xiulan |
| 5 | `songyajing` | 宋雅静 | Song Yajing |
| 6 | `sunyuwei` | 孙雨薇 | Sun Yuwei |
| 7 | `yemingxuan` | 叶铭轩 | Ye Mingxuan |
| 8 | `yinhao` | 尹浩 | Yin Hao |
| 9 | `yuxiaowei` | 于晓薇 | Yu Xiaowei |
| 10 | `yuxiaowen` | 于晓雯 | Yu Xiaowen |

## 📄 File Descriptions · 文件说明

每位用户的目录（`data/{user}/` 与 `data_en/{user}/`）包含以下文件：

| 文件 | 说明 |
|------|------|
| `persona.json` | 👤 用户画像：姓名、年龄、职业、家庭、性格（MBTI）、兴趣爱好等 |
| `daily_event.json` | 📅 每日生活事件列表：按时间顺序记录用户一年的生活轨迹 |
| `event_tree.json` | 🌳 事件树：将复杂事件层级分解为子事件（`decompose`/`subevent`） |
| `daily_draft.json` | 🗂️ 每日大纲：按月组织，含日期属性（天气/节假日/星期）与当日概览 |
| `phone_data/` | 📱 9 类手机操作数据，见下表 |
| `QA_all/QA.json` | ❓ 问答对：问题、答案、证据链、评分点、问题类型 |

### 📱 手机数据源（phone_data/）

| 文件 | 中文含义 | 记录数（10 用户合计） |
|------|----------|------------------------|
| `agent_chat.json` | 🤖 智能助手对话 | 8,177 |
| `calendar.json` | 📅 日历 | 6,011 |
| `call.json` | 📞 通话记录 | 3,947 |
| `contact.json` | 👤 联系人 | 244 |
| `fitness_health.json` | 🏃 运动健康 | 3,641 |
| `note.json` | 📝 笔记 | 7,836 |
| `photo.json` | 📷 照片 | 5,604 |
| `push.json` | 🔔 推送通知 | 6,026 |
| `sms.json` | 💬 短信 | 5,923 |

## ❓ QA 数据说明

数据集提供 **两种** 问答对表示：

1. **`QA_all/QA.json`**（每用户，合计 **3,380** 条）：逐条问答，字段包括
   `question`、`answer`、`evidence`（证据链）、`score_points`（评分点）、`question_type`（如 `Single_hop`）、`required_events_id`、`ask_time`。

2. **`locomo_format/`**（**3,380** 条，10 个样本）：转换为 LoCoMo 对话格式，每个样本含 `sample_id`、`conversation`（双角色对话）与 `qa`。

> 各用户 QA 数量为 326～354 条不等，详情见各用户目录。

## 🧾 Data Format Examples · 格式示例

### 👤 persona.json（用户画像）

```json
{
  "name": "于晓雯",
  "birth": "1997-12-29",
  "age": 24,
  "nationality": "汉",
  "gender": "女",
  "education": "大学本科",
  "job": "住院医师",
  "occupation": "郑州市中心医院",
  "salary": 120000.0,
  "body": { "height": 163, "weight": 50.0, "BMI": 18.8 },
  "personality": { "mbti": "ISFJ", "traits": ["仁慈", "社会责任导向", "个人成长导向"] },
  "hobbies": ["city walk", "读书", "羽毛球", "做陶艺"]
}
```

### 📅 daily_event.json（每日事件）

```json
{
  "event_id": "1",
  "name": "跨年聚餐与新年目标分享",
  "date": ["2025-01-01 00:00:00至2025-01-01 02:30:00"],
  "type": "Relationships",
  "description": "凌晨时分，与闺蜜张静、孙悦在家中跨年聚餐……",
  "participant": [
    { "name": "于晓雯", "relation": "自己" },
    { "name": "张静", "relation": "闺蜜" }
  ],
  "location": "河南省郑州市金水区经三路89号……",
  "atomic_id": ["1-1"]
}
```

### 🌳 event_tree.json（事件树）

```json
{
  "name": "基金定投与理财规划调整",
  "date": ["2025-06-10"],
  "type": "Finance",
  "event_id": 229,
  "participant": [{ "name": "自己", "relation": "自己" }],
  "location": "未知",
  "decompose": 1,
  "subevent": [
    { "event_id": "229-2", "name": "执行基金定投", "type": "Finance", "decompose": 0 }
  ]
}
```

### ❓ QA_all/QA.json（问答对）

```json
{
  "question": "我爸脑梗那天中午……具体通话了多久来着？",
  "answer": "2分钟（12:13-12:15）",
  "required_events_id": ["248", "248"],
  "ask_time": "2025-06-20",
  "question_type": ["Single_hop"],
  "score_points": [
    { "description": "识别出与母亲李秀英的通话记录（12:13-12:15）", "score": 4 },
    { "description": "正确计算通话时长为2分钟", "score": 3 }
  ],
  "evidence": [
    { "type": "call", "phoneNumber": "+8618739081234", "contactName": "李秀英", "datetime": "2025-01-15 12:13:00" }
  ]
}
```

### 💬 locomo_format（LoCoMo 对话格式）

```json
{
  "sample_id": "于晓薇",
  "conversation": {
    "speaker_a": "于晓薇",
    "speaker_b": "于晓薇的Assistant",
    "session_1": [
      { "speaker": "于晓薇", "dia_id": "2025-01-01_agent_chat0", "text": "..." }
    ]
  },
  "qa": [ ... ]
}
```

## 📥 Loading · 加载方式

```python
from datasets import load_dataset

# 加载整个数据集（含 data/ 与 data_en/ 下的 JSON 文件）
ds = load_dataset("C1754955896/Lifebenchv2.0")

# 或直接读取单个 JSON 文件
import json
with open("data/yuxiaowen/persona.json", encoding="utf-8") as f:
    persona = json.load(f)
```

## 📌 注意事项 · Notes

- **问答对的两份表示**：`QA_all/QA.json`（逐用户）与 `locomo_format/`（合并后的对话格式）均为 **3,380** 条问答，前者为原始标注格式，后者为 LoCoMo 对话格式。
- **许可证**：Apache-2.0。
