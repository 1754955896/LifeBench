# 画像阶段真实集成测试

使用两份完全虚构的人物输入：北京软件工程师、伦敦软件工程师。生成截止日期均为
2025-12-31，seed=42，各一人，保留正常联系人数量、地址落地和地点 sidecar。
国内不传地图选项，验证默认 Amap；海外显式选择 overseas。调用当前项目的真实 LLM
和地图配置，产生 API 用量费用，不使用模拟响应，不改动生产阶段顺序。

```powershell
.venv\Scripts\python.exe tests/persona_international_live/run_generation.py --case all
.venv\Scripts\python.exe tests/persona_international_live/test_outputs.py
```

可以用 `--case cn` 或 `--case gb` 单独执行。已有成功输出会拒绝覆盖；失败重跑会覆盖
generation.log 和 run_summary.json，生产失败日志为追加记录。`--prepare-only` 只准备输入。

每个国家目录保存 input.json、generation.log、run_summary.json；成功后另有完整画像
persona_list.json、persona_list_locations.json、基础画像 checkpoint 和 token_usage。
测试不会复制或输出 API Key。公共海外地图实例仅适合这种少量人工验证。

## 首次结果：优化前（2026-10-23）

用户明确授权数据外发及付费调用后，已执行两份虚构输入的真实生成。

| 样本 | 生产 CLI 结果 | 耗时 | 模型响应次数 | token | 产物 |
| --- | --- | --- | --- | --- | --- |
| 北京，默认 Amap | 成功，退出码 0 | 632.5 秒 | 30 | 139001 | 完整画像、23 联系人、8 地点 |
| 伦敦，overseas | 最终质量门禁失败，退出码 2 | 938.0 秒 | 42 | 207418 | 仅保留基础画像与核心地点证据，无正式完整输出 |

英国失败：两名邻居未通过 Camden 行政区一致性校验，且地址分配交通方式与明确偏好不一致。
雇主名称还存在中国公司形式套用、虚构租赁关系等内容问题。
详见 [REVIEW.md](REVIEW.md) 和 [RESULTS.md](RESULTS.md)。
首次沙箱内尝试因 APIConnectionError 失败；各目录 failures.jsonl 仍保留这些历史记录。
正式联网生成的结果以最新 run_summary.json 和 generation.log 为准。

输出检查会验证字段、年龄、联系人数量、叙述完整性、地点文件以及海外地区元数据。
尚未尝试生成时显示 SKIP；已经运行却缺失完整输出则明确 FAIL。本次预期为国内通过、英国失败。
生活习惯、职业和收入是否符合当地
背景还需逐项阅读生成结果，不能只凭结构测试认定合成效果。

`inspect_results.py` 只读取保存的产物并生成 RESULTS.md，不调用 API。
`REVIEW.md` 是本次人工审阅快照，重跑后需要重新审阅。本次未修改生产生成代码来规避失败。
已为本目录的 Python 脚本和 README 添加窄范围 Git 例外；生成画像、日志及测试报告继续忽略，
保存在本地，不会随普通 git add 自动纳入提交。本次新增实现尚未提交。

## 优化后的测试

**最新结果：国内与海外均通过。**北京 25 名联系人、9 个地点；伦敦 22 名联系人、13 个地点。
最新完整输出在 `optimized/cn/` 与 `optimized/gb/`，详见
[优化后人工评估](optimized/REVIEW.md) 与 [结果摘要](optimized/RESULTS.md)。
原 REVIEW.md 和首次产物保留为历史记录，租赁和学校等真实性问题已按用户要求调整为允许合成。

`test_optimizations.py` 为离线回归：比较默认提示词，以及基础/联系人阶段的调用轨迹和输出，
对照提交 `7f25d62`；另覆盖混合办公、行政层级、合成学校/租赁关系、通勤估算来源和配置指纹。

```powershell
.venv\Scripts\python.exe tests/persona_international_live/test_optimizations.py
.venv\Scripts\python.exe tests/persona_international_live/run_generation.py --case all --output-root tests/persona_international_live/optimized
.venv\Scripts\python.exe tests/persona_international_live/test_outputs.py --output-root tests/persona_international_live/optimized
```

优化运行保存于 `optimized/`，原测试产物保留。按用户最新要求，国际模式允许合理虚构，
检查重点为内部一致性，不以虚构公司/学校不能检索为失败原因。

英国 `attempt1/` 保留一次过于严格的办公场所类型检查失败，`attempt2/` 保留联系人校验重试耗尽的记录。
后续可用 `--case gb --resume-relations` 复用已成功的基础画像，只继续现有联系人生成方法；
会保留原 checkpoint，另写 `basic_checkpoint_migrated.json` 统一行政区元数据。
`attempt3/` 保存出生地地理编码失败的记录。`trace_generation.py` 记录真实结构化调用阶段、
校验错误和响应；续跑允许按完整提示词哈希复用成功响应，先重新运行当前校验器。
日志明确区分 `live_api` 与 `recorded_real_response`，不将复用结果计为新的联网调用；凭据会脱敏。

## 一个月的完整流程测试

代码快照已提交为 `a3d4de6`。使用 `optimized/gb/` 中成功生成的虚构伦敦人物，
独立测试 2026-01-01 至 2026-01-31 的生活生成。运行时调用真实 API，不复用画像
测试的 LLM 响应；包含草稿、每日模拟、事件匹配、月报、手机数据和 QA。

```powershell
.venv\Scripts\python.exe tests/persona_international_live/run_month.py
.venv\Scripts\python.exe tests/persona_international_live/check_month.py
.venv\Scripts\python.exe tests/persona_international_live/test_month_regressions.py
```

输出保存在 `monthly_2026_01/`，主日志为 `pipeline.log`，结束后写入
`run_summary.json`。检查脚本验证实际产物与 31 天覆盖情况，结果保存为
`validation.json`；进程退出码 0 本身不代表测试通过。
再次运行会按生产脚本的文件检查点续跑，因此应结合日志区分首次生成与续跑。

测试准备时发现后续阶段仍需根目录的 `persona_context.json`，已修正国际模式下
的文件归档规则，避免模拟完成后移走地区上下文；该修正晚于上述提交快照。

真实测试还暴露了两个问题：英文单引号被旧 JSON 修复规则破坏，以及从月度规划
检查点恢复时缺失 `yearly_summary`。已分别修复国际模式 JSON 解析和摘要恢复，
并增加空大纲停止检查。`attempt1/` 保留首次解析失败，
`attempt2/` 保留空大纲续跑记录，后续运行复用成功的月度规划和分解结果。

`attempt3/` 保留海外路线查询失败导致缺日的模拟记录。根据允许合理合成的要求，
国际模拟在路线不可用时可使用 `utils/route_estimation.py` 粗略估算，保留交通方式，
明确标记 `source=synthetic_route_estimate`、`map_verified=false`、估算方法和低置信度。
非法坐标、未知交通方式、跨国可行性问题仍不接受。默认 Amap 回退行为不变。
相关离线回归共 31 项，包括国际 JSON 清理保留重音字符和其他语言的 Unicode 文本。
重新模拟使用干净状态，避免把失败日期之后的记忆带回更早日期。
另外修正同一建筑内活动切换与英国行政名称差异产生的地理误报。最终检查器会使用修正后的
规则重新检查原始地理产物，单独记录生成时旧检查器的诊断数量，不改写原始诊断或模型输出。

`attempt4/` 保存首次完成全部 31 天模拟后的格式化问题：模拟入口没有传递起止日期，
格式化器仍按默认 2025 年过滤，得到空事件文件；事件匹配也固定筛选 2025 年。
已将这两个调用统一到本次时间范围，并为无格式化事件与空每日事件文件增加失败检查。
复用成功模拟可执行 `run_month.py --resume-format`，调用项目原生
`simulator.py --generate-data 0` 重新格式化，再恢复后续主流程，不重新模拟生活内容。
海外通行叙述未匹配到 sidecar 路段时，导出标记为 `narrative_unverified`、
`map_verified=false`，不补写未经证实的坐标或距离。本次已格式化的 4 条此类记录
已只补充该来源标记，保留原文、日期和事件 ID；原文件留存备份及变更说明。

`attempt5/` 保存手机和 QA 的旧时间范围问题：照片/通信/推送/笔记校验器强制 2025 年，
QA 单跳等生成器固定遍历全年，并存在提问日期上限写死为 2025-12-31 的逻辑。
已按本次生成日期校验手机年份，QA 按已有生活数据月份调度，并把部分年份的时间范围
通过线程上下文传入提示词。完整 2025 年的默认范围和校验年份保持原值。
修复后重新生成手机与 QA，复用已验证的生活、大纲和事件匹配产物；联系人沿用原 22 人。

`attempt6/` 保留 QA 内部独立手机证据生成器仍强制 2025 年的记录；该校验也已修正，
并接受 agent_chat 的 YYYY-MM-DD 日期契约。已按语法树扫描固定年份比较，补齐回归。
只继续 QA 可用 `run_month.py --resume-qa`；本次先从已验证的真实手机原始产物经原生
`phone_gen.py --process-only` 恢复手机文件，再执行此续跑。未重新调用 LLM 生成生活或手机。

`attempt7/` 保存 QA 时间语义和旧断点的复核记录。生活/手机事实限定在生成月份，QA 可按
原有记忆评测方式在当年年底回顾这些事实，不能为缺失月份另造生活事实。
旧 QA 缓存只保存问题，配套新增手机证据未持久化，直接跳过会丢失证据；已增加
`process/qa_checkpoints/`，原子保存问题、手机数据和 ID 计数，并校验输入/代码/地区/时间
指纹与前一阶段链条。没有配套断点的旧问题缓存会重生成。
本次之前未配套保存证据的两类 QA 已归档并重跑，后续续跑可恢复完整证据。

### 本次月度测试结论（2026-10-24）

**生活生成跑通，完整 QA 数据质量检查未通过。** 通过多次修复和检查点续跑完成真实
伦敦人物 2026 年 1 月流程，最终进程退出码为 0；不是修复后从空目录一次执行成功。

| 检查 | 结果 |
| --- | --- |
| 每日大纲、生活模拟、事件日期覆盖 | 31/31 天，无缺日或越界 |
| 每日事件 | 620 条，ID 唯一 |
| 月报 | 1 份（2026-01） |
| 手机活动（不含 22 名联系人） | 基础 190 条；QA 后最终 967 条 |
| 手机活动日期 | 全部在 2026 年 1 月，覆盖 31 天 |
| QA | 9 类生成器完成，147 条候选、最终 143 条 |
| QA 事实对应的事件 ID | 全部存在 |
| QA 与最终手机证据一致性 | **未通过**：39 个问题有 119 次悬空引用，涉及 29 条证据 |
| 离线回归 | 月度修复 31 项、画像兼容 24 项、地图分配 56 项，全通过 |

原有 QA 证据精炼步骤允许删除手机记录，但此前问题保留旧证据；问题生成当时存在的记录
可能不在最终手机数据中。该问题不是海外地址搜索失败。本次保留全部原始 QA 和证据，
没有把被删除记录强行补回，也没有删题掩盖问题。`check_month.py` 已加入最终证据一致性
检查，当前应退出 1，`validation.json` 中 `life_artifacts_success=true`、`success=false`。
5 道 Unanswerable 的证据为空符合原有任务定义，不因此判错。

通行事件包含 128 条地图核验、34 条估算、4 条叙述未核验；估算不代表真实公交班次可用。
事件匹配阶段还有 3 次模型 JSON 解析失败，已按原逻辑保留为未匹配，属于质量提示。
QA 可以在 2026 年稍晚日期回顾 1 月事实；这不等于生成了其他月份生活。

详细报告在本地 `monthly_2026_01/REVIEW.md`，最终检查在 `validation.json`；大体积生成
产物、日志和人物输入继续忽略，不纳入提交。仅本轮最终 QA 续跑耗时约 114 分钟，
`stage_times.json` 中其他阶段为复用检查点的耗时，不能据此推断完整首次运行速度。
