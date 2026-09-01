# persona 模块 — 用户人设数据生成与管理

负责生成用户画像（Persona）数据，包括基础信息、性格特征、日常习惯等。

## 核心文件

| 文件 | 说明 |
|------|------|
| `persona_gen.py` | Persona 数据生成主脚本 |
| `personas.json` | 生成的 personas 数据文件 |
| `pipeline.py` | 分阶段生成与并发编排 |
| `constraints.py` | 年龄、BMI、MBTI 和亲属年龄约束 |
| `output_adapter.py` | 转换并锁定旧版 JSON 输出契约 |
| `source_normalizer.py` | 使用结构化 LLM 从任意字段或文本中抽取明确事实与软线索 |
| `canonicalizer.py` | 将稀疏事实转换为固定 27 字段画像骨架并锁定输入事实 |
| `diversity.py` | 运行种子、结构化差异度和多样性门槛 |

## 子目录

| 目录 | 说明 |
|------|------|
| `persona_file/` | Persona 参考文件与最终数据（`complete_profiles.json`、`final.json`、`refer.json` 等） |
| `prompts/` | 按基础画像、叙事、关系计划和联系人拆分的提示词模板 |
| `eval/` | Persona 评估脚本（`eval.py`、`eval_circle.py`、`eval_relation.py`） |

## 任意输入与差异化生成

任意输入模式先通过 LLM 将数据规范化为明确事实、软线索和原始描述，再补全固定画像结构。明确事实不会在后续阶段被修改；年龄和 BMI 仍由代码计算。

```powershell
python scripts/run/persona_gen.py `
  --input-mode auto `
  --input-format auto `
  --file-path data/persona/ `
  --input-file sparse_profiles.json `
  --output-file persona_list.json `
  --variants-per-input 3 `
  --diversity high
```

支持 `json`、`jsonl`、`csv`、`tsv`、`txt` 和 `xlsx` 容器格式。Excel 读取需要环境中已有 `openpyxl`。最终仍输出标准画像列表，不包含抽取置信度、字段锁、variant id 或其他内部数据。

Python 调用：

```python
outputs = generator.generate_from_any(
    "住在杭州余杭，从事互联网工作并喜欢户外。",
    variants_per_input=3,
    diversity="high",
    seed=None,
)
```

`seed=None` 会为每次调用创建新的运行种子；设置固定 seed 可复用同一套参考采样与变体提示。实际模型返回能否逐字复现还取决于模型服务端的采样实现。

## 地址落地与 location 数据

Persona CLI 默认在基础结构生成后调用地图服务，将居住地和日常工作地落到真实 POI。行政区和用户明确提供的地址事实不会被跨区域修改；地图返回的真实街道、门牌会回写画像，然后叙事和关系阶段继续使用这份冻结地址。

地址分配不是分别取搜索第一项，而是先建立住宅/工作地候选池，再按行政区匹配、地址完整度、批次复用惩罚和通勤合理性联合评分。直线距离用于廉价预筛，只对最优的 2 组候选调用路线 API；最终从高分候选中按 seed 加权抽样。因此固定 seed 可复现，同一模糊输入在不同运行 seed 下可以得到差异较大但仍合理的地点组合。

常去地点由画像先规划为 `daily`、`weekly`、`monthly` 三种频率，分别采用近距离、中距离和城市范围搜索半径。周边搜索直接使用 POI 返回的坐标和行政信息，不再对候选逐条地理编码；同一人物内禁止重复，批次内则按“住宅少共享、单位可适度共享、公共场所允许共享”的强度进行复用惩罚。

地图工具默认在所有生成线程间统一控制为 3 QPS，并对 `10014/10015/10019/10020/10021/10029` 等短时限流错误进行指数退避重试。日额度错误不会反复重试。若最终成功落地的常去地点少于 3 个，本次人物生成会明确失败并留下失败记录，不再静默输出不完整 sidecar。

画像文件为 `person.json` 时，批量地址 sidecar 默认写为 `person_locations.json`，其外层数组与画像数组严格对齐：

```json
[
  [
    {
      "name": "居住地·某小区",
      "location": "120.000000,30.000000",
      "formatted_address": "浙江省杭州市余杭区某路1号",
      "city": "杭州市",
      "district": "余杭区",
      "streetName": "某路",
      "streetNumber": "1号",
      "description": "人物的日常居住地"
    }
  ]
]
```

`scripts/run_all.py` 会把每项写入对应人物目录的 `location.json`。因此 simulator 检测到文件已存在后不会再次随机生成。旧数据没有 sidecar 时仍保留 simulator 的兼容兜底。

如本地没有地图 API 或只需离线调试，可在 Persona CLI 使用 `--skip-location-generation`；也可用 `--location-output` 指定 sidecar 路径。

关系圈中的学校、体育场馆和有明确线下集合点的兴趣圈会在联系人生成前落到真实 POI，并作为 `关系圈固定地` 写入同一 location sidecar。体育、健身和线下兴趣地点必须从住宅坐标周边查询：每日活动使用约 3 km 半径，每周活动约 6 km，其他线下兴趣通常限制在 7～8 km；半径内没有合适 POI 时生成失败，不会降级成全城随机场馆。联系人住宅随后根据圈子类型、共享地点、工作地、原行政区线索和批次占用率从真实住宅候选池分配；出生地的省、市、区也会通过地图地理编码验证。非同住联系人不会优先复用同一住宅 POI。

每个画像还会规划至少一个 `scope=city` 的城市级公共地点，例如与其兴趣匹配的博物馆、城市公园、图书馆、体育中心或历史地标。这类 monthly 低频地标是住宅生活半径规则的明确例外。城市级地点与住宅/工作地周边的 daily、weekly 场所一同写入 location sidecar；健身、球类、跑步、阅读和兴趣班等高频项目则强制以居住地为搜索基点。

只需要住宅/工作分配时可以直接调用公开接口：

```python
from src.lifebench.persona import PersonaAddressService

service = PersonaAddressService()
grounded, core_pois = service.allocate_persona_addresses(
    profile,
    seed=20260901,
    mobility_profile={"primary_transport": "transit", "explicit": True},
    reserved_addresses=existing_personas_or_locations,
)

batch_results = service.allocate_persona_batch(
    profiles,
    seeds=[20260901, 20260902],
    reserved_addresses=existing_personas_or_locations,
)
```

CLI 可通过 `--reserved-address-file` 读取已有画像或 location JSON，将其中主画像及 relation 住宅加入占用池，以减少不同运行批次之间的小区和办公地点重复。
