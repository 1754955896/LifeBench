# Shared Utilities

Common utilities reused throughout the project.

## Files

| File | Description |
| --- | --- |
| `llm_call.py` | LLM call wrappers. |
| `structured_llm.py` | Structured LLM calls with JSON Schema decoding. |
| `utils_io.py` | Input/output utilities. |
| `dataprocess.py` | Data processing utilities. |
| `date_utils.py` | Date and time utilities, including `TimeSpec` and date iteration. |
| `json_utils.py` | JSON utilities such as `remove_json_wrapper`. |
| `maptool.py` | Map utilities, including address resolution and distance calculations. |
| `overseas_maptool.py` | OSM-backed replacement for the map tool; supports Nominatim/Photon, Overpass/Photon, and optional Valhalla. See the implementation and usage below. |
| `overseas_runtime.py` | Shared CLI map selection, child-process argument forwarding, and overseas WGS-84 export settings. |
| `random_ref.py` | Random reference utilities. |

## 海外地图工具

`overseas_maptool.py` 提供 `OverseasMapMaintenanceTool`，也导出同名兼容入口
`MapMaintenanceTool` 和别名 `OSMMapMaintenanceTool`。不需要高德 Key，依赖项目已有的
`requests`。保留旧工具全部公开方法及主要返回字段，查询失败仍返回 `None` / `[]`。

### 使用

```python
from src.lifebench.utils.overseas_maptool import MapMaintenanceTool

tool = MapMaintenanceTool(
    country_code="GB",                     # 每个实例固定一个目标国家，ISO alpha-2
    nominatim_url="http://localhost:8080",  # 自建或托管 Nominatim 根地址
    overpass_url="http://localhost:8081/api/interpreter",  # 完整 interpreter 地址
    valhalla_url="http://localhost:8002",   # 可选；不配置则路线返回 None
    user_agent="LifeBench/1.0 (your-contact)",
    requests_per_second=2,
    timeout_seconds=30,
)

poi = tool.get_poi("British Museum", city="London")
homes = tool.search_poi_candidates("住宅小区", city="London", limit=20)
nearby = tool.search_around_candidates(
    location="-0.127600,51.507200",  # 经度,纬度，WGS-84
    keywords="咖啡馆", city="London", radius=3000,
)
if poi and nearby:
    route = tool.route_between_pois(poi, nearby[0], "walking")
```

上面的 localhost 地址是部署示例，代码不会自动启动地图服务或下载地图。
服务地址必须显式配置；实现不预置免费公共后端。
`api_key` 参数仍可传入以兼容旧构造调用，但会被忽略，不会发送到 OSM 服务。

### 通过运行脚本选择地图工具

`scripts/run/persona_gen.py`、`scripts/run/simulator.py`、`scripts/run.py` 和
`scripts/run_all.py` 支持 `--map-tool amap|overseas`，默认 `amap`。选择海外地图时必须
同时传入 `--map-config` 指定 JSON 配置文件。批量和总流程脚本会显式向模拟器子进程传递
这两个参数，不使用启动钩子、额外启动器或环境变量。海外运行会在进程内适配 WGS-84
坐标转换和导出，防止重复偏移。

```powershell
# 默认使用高德，沿用原参数
python scripts/run/persona_gen.py --help

# 海外画像生成；继续附加原来的输入、输出等参数
python scripts/run/persona_gen.py --map-tool overseas --map-config config/overseas_map.demo.json

# 海外事件模拟
python scripts/run/simulator.py --map-tool overseas --map-config your-map.json --file-path data/example/

# 总流程及批量运行使用相同参数
python scripts/run.py --map-tool overseas --map-config your-map.json --base-path data/example/
python scripts/run_all.py --map-tool overseas --map-config your-map.json --persona-folder input/
```

`config/overseas_map.demo.json` 选择 Photon 公共实例进行地址/POI 检索，并用 Valhalla
公共实例计算路线，仅适合人工小规模验证。它们不保证可用性或无上限配额；批量运行应
把配置地址换成自建或合适的托管实例。公共实例使用说明：
[Photon](https://photon.komoot.io/)、[Valhalla](https://valhalla.github.io/valhalla/#demo-server)。

可选配置 `photon_url` 替代 `nominatim_url`，`poi_backend="photon"` 替代 Overpass POI 查询。
两种地址解析器只能选择一种。Photon 城市检索需要有行政区域 extent，示例用
`city_aliases={"London":"Greater London","伦敦":"Greater London"}` 解决城市节点没有边界的问题。
其他城市可按实际行政区域配置别名。仍支持 Nominatim + Overpass；`overpass_method`
可设 `GET` 或 `POST`（默认）。Valhalla 路线使用 POST JSON。

Photon POI 使用索引中的主要类别，支持的标签少于完整 Overpass；未知/未索引类别可能
没有候选。周边检索会在响应上再次限制国家、城市范围和半径；最近候选不足时不会扩大范围。
Photon 的 API 使用类别 include 参数；reverse 不支持 countrycode/bbox 请求参数，所以
国家和城市限制在返回后检查。行政层级、门牌完整度与高德不完全一致。

配置错误会报错退出，不会静默使用国内服务。选择仅作用于本次运行；子进程通过命令行参数
显式选择地图工具，不会修改已打开的 Python/Jupyter 进程。
请勿将旧 GCJ-02 数据混入该海外运行。地图替换不改变原来的节假日、文化提示或人物字段，
完整海外合成质量仍需单独验证。

画像生成支持已有的依赖注入：

```python
from src.lifebench.persona.address_generation import PersonaAddressService
from src.lifebench.persona.persona_gen import PersonaGenerator

address_service = PersonaAddressService(map_tool=tool)
generator = PersonaGenerator(
    ref_json_file_path="your-reference.json",
    address_service=address_service,
)
```

直接导入新工具时使用上述依赖注入；使用运行脚本时由地图参数触发实例替换。

### 方法和返回值

| 方法 | 实现 |
| --- | --- |
| `amap_geocode(address, city=None)` / `geocode(...)` | Nominatim `/search` 或 Photon `/api/`，兼容旧方法名 |
| `get_poi(keyword, city=None)` | 搜索候选并取首个；保留候选自身坐标 |
| `search_poi_candidates(keyword, city=None, limit=20, types=None)` | 具名地点使用 Nominatim/Photon，类别使用 Overpass/Photon |
| `search_around_candidates(...)` | Overpass 或 Photon 半径搜索，校验半径并按距离排序 |
| `search_around_poi_random(...)` / `set_random_seed(...)` | 复用旧实现，支持固定种子 |
| `route_between_pois(...)` | Valhalla，距离米、耗时秒 |
| `get_duration_between_pois(...)` | 路线耗时秒；失败返回 `None` |
| `process_route(...)` / `process_route_bycode(...)` | 复用旧批量路线方法 |
| `process_instruction_route(...)` | 复用旧类型 1/2/3 指令及错误汇总，并补上坐标系标记 |
| `extract_route_summary(...)` / `extract_poi_route_simplified(...)` | 复用旧输出适配 |
| `clear_expired_cache()` | 清理过期结果缓存 |

地理编码保留 `country/province/city/district/street/number/location/formatted_address`
及空的 `citycode/adcode`。POI 保留 `id/name/location/address/structured_address/type/typecode/`
`pname/cityname/adname/distance_m/geocode`，新增 `source`、`country_code`、
`coordinate_system="WGS-84"`、`attribution` 和 `position_kind`。
路线保留 `duration_seconds/distance_meters/mode`。不把 OSM 标签伪装成高德数字类型码。

### 类别与地理约束

- 内置常见中英文类别，如住宅小区、办公楼、超市、咖啡馆、健身房、公园和学校。
  内置映射见 `CATEGORIES`；仅通用类别转为标签查询，具名地点不会仅因含“博物馆”等后缀而泛化。
- `types="amenity=cafe|shop=bakery"` 表示两个 OSM 标签的 **OR** 查询。
  未知类型、旧高德数字类型码明确返回失败；不会静默退成任意地点。
- 类别搜索必须传 `city`，周边搜索必须传坐标。类别查询不支持全国无界扫描。
- Nominatim 请求限制国家，响应再次核对 `country_code`。城市先解析为 bounding box，
  再限制文本查询和候选坐标。城市解析失败即失败，不退回全球搜索。
- Overpass 使用目标国家行政边界 area 过滤。自建区域实例必须导入目标国家边界，
  并构建 Overpass area 数据；缺失边界/area 时可能返回空集。城市范围是外接矩形，
  不代表精确市界；明确街道/行政区和具体场所要求仍应由调用方检查。
- 每次 Overpass 最多返回 500 个元素，候选池有上限；距离排序只针对已召回候选，
  不能保证是数据库内全部地点中的最近 N 个。极密集区域可缩小半径。
- OSM 缺少的门牌和行政区保持空值，不编造。way/relation 的返回点可能是几何中心，
  `position_kind="geometry_center"` 表示它不是已验证的入口或住宅门牌。
- 未知名称不自动翻译；具体店名推荐当地语言或英文，可通过 `language` 选择结果语言。

### 路线与坐标限制

默认路线支持 `driving/walking/bicycling`。公交默认返回 `None`；只有后端已构建公交数据时，
才可设置 `enable_transit=True` 使用 Valhalla multimodal。没有公交时刻表和日期适配时，
不应宣称支持真实公交通勤。不配置 Valhalla、无路线或无合法响应时不估算时间。

本工具输入、输出一律 WGS-84。已有画像地点或路线输入如明确标记 GCJ-02，将拒绝使用；
未标记的坐标按 WGS-84 解释。旧管线有以 GCJ-02 为默认的坐标导出逻辑，完整海外模拟
接入时需同步尊重坐标系标记，不能再次对 WGS-84 坐标执行 GCJ-02 转换；运行脚本选择海外工具时已做进程内适配。

### 运行与使用政策

HTTP 请求包含应用标识、超时和实例级全局节流；429/502/503/504 有有限次数退避重试。
异常日志不输出 URL、响应正文或凭据。结果在实例内存缓存，支持清理和复制隔离；
多实例/多进程的总配额应由部署方的共享代理控制。缓存不跨进程持久化。

持续批量合成建议部署目标区域的 Nominatim、Overpass 和可选 Valhalla 服务。
Nominatim 的社区公共服务最高 1 请求/秒，批量及系统性查询受严格限制；
本实现拒绝将 `nominatim.openstreetmap.org` 配成批量后端。公共 Overpass 和路线演示服务
也有公平使用限制，不能视为稳定的无限免费后端。数据集导出应保留 OSM 来源和归属，
并按 ODbL 要求处理实际提取的地理数据。

官方资料：

- [Nominatim Search API](https://nominatim.org/release-docs/latest/api/Search/)
- [Nominatim 公共服务使用政策](https://operations.osmfoundation.org/policies/nominatim/)
- [Overpass 文档](https://dev.overpass-api.de/overpass-doc/en/)
- [Valhalla 路线 API](https://valhalla.github.io/valhalla/api/route/api-reference/)
