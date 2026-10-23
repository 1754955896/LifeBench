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
