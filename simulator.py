import json
import os
import time
import argparse
from datetime import datetime, timedelta
from event.mind import *
from event.event_refiner import EventRefiner
from event.event_formatter import EventFormatter
from utils.IO import *

# 命令行参数解析
parser = argparse.ArgumentParser(description='模拟生成模块')
parser.add_argument('--file-path', type=str, default='output/', help='数据文件路径')
parser.add_argument('--start-date', type=str, default='2025-01-01', help='开始日期')
parser.add_argument('--end-date', type=str, default='2025-12-31', help='结束日期')
parser.add_argument('--max-workers', type=int, default=30, help='最大并行线程数')
parser.add_argument('--interval-days', type=int, default=16, help='每个线程处理的天数')
parser.add_argument('--refine-events', type=int, default=1, help='是否执行事件精炼')
parser.add_argument('--generate-data', type=int, default=1, help='是否生成数据')
parser.add_argument('--format-events', type=int, default=1, help='是否格式化事件')
args = parser.parse_args()

# 配置参数
file_path = args.file_path
start_date = args.start_date
end_date = args.end_date

# 执行时间记录
execution_times = {}
start_time_total = time.time()

# 控制参数：设置为1执行，0跳过
refine_events = args.refine_events  # 是否执行事件精炼
generate_data = args.generate_data  # 是否生成数据
format_events = args.format_events  # 是否格式化事件

# 处理参数
max_workers = args.max_workers  # 最大并行线程数
interval_days = args.interval_days  # 每个线程处理的天数

# 中断保存文件路径
INTERRUPT_FILE = file_path + "process/interrupt_state.json"

# 日志函数
def log(message):
    log_line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    print(log_line.strip())

# 确保必要的目录存在
os.makedirs(os.path.join(file_path, "process"), exist_ok=True)

# 1. 读取基础数据
persona = read_json_file(file_path + 'persona.json')
log(f"成功读取人物画像数据")

# 读取每日状态数据
daily_state = None
try:
    daily_state = read_json_file(file_path + 'daily_state.json')
    log("成功读取每日状态数据")
except FileNotFoundError:
    log("未找到每日状态数据文件")
except Exception as e:
    log(f"读取每日状态数据失败: {str(e)}")

# 2. 事件精炼
if refine_events:
    log("=== 开始事件精炼流程 ===")
    start_time_refine = time.time()
    # 2.1 读取原始事件文件
    json_data_e = read_json_file(file_path + "event_decompose_dfs.json")
    log(f"成功读取原始事件文件，共{len(json_data_e)}个事件")
    
    # 2.2 使用Mind初始化上下文
    mind = Mind(file_path, persona=persona, event=json_data_e, daily_state=daily_state)
    mind.initialize(json_data_e, persona, start_date, daily_state=daily_state)
    log("Mind初始化完成")
    
    # 2.3 使用EventRefiner进行事件调整
    log("开始事件调整...")
    refiner = EventRefiner(persona=persona, events=mind.events)
    
    # 调用event_refiner的annual_event_refine方法处理全年事件调整
    log(f"开始处理{start_date}至{end_date}的事件调整...")
    mind.events = refiner.annual_event_refine(
        mind.events, 
        start_date, 
        end_date, 
        mind.context, 
        max_workers
    )
    log(f"所有区间调整完成")
    
    # 2.4 保存调整后的事件
    adjusted_events_path = file_path + "process/event_decompose_1.json"
    with open(adjusted_events_path, "w", encoding="utf-8") as f:
        json.dump(mind.events, f, ensure_ascii=False, indent=2)
    log(f"\n调整后的事件已保存到: {adjusted_events_path}")
    log(f"事件精炼完成，共调整{len(mind.events)}个事件")
    
    end_time_refine = time.time()
    execution_times['event_refine'] = end_time_refine - start_time_refine
    log(f"事件精炼流程耗时: {execution_times['event_refine']:.2f}秒")
    log("=== 事件精炼流程完成 ===")
else:
    log("跳过事件精炼流程")

# 3. 数据生成
if generate_data:
    log("\n=== 开始数据生成流程 ===")
    start_time_generate = time.time()
    log(f"参数设置: 开始日期={start_date}, 结束日期={end_date}, 并行线程数={max_workers}, 区间大小={interval_days}天")
    monthly_file = os.path.join(file_path, "monthly_summaries.json")
    cumulative_file = os.path.join(file_path, "cumulative_summaries.json")
    year = int(start_date[:4])
    if not (os.path.exists(monthly_file) and os.path.exists(cumulative_file)):
        print(f"未找到fuzzymemory文件，开始生成该年的月度总结和累积总结...")
        event = read_json_file(file_path + "process/event_decompose_1.json")
        fuzzy_memory_builder = FuzzyMemoryBuilder.get_instance(event, persona, file_path)
        fuzzy_memory_builder.build_all_summaries(year)
        print("fuzzymemory生成完成！")
    # 3.1 创建MindController实例
    adjusted_events_path = file_path + "process/event_decompose_1.json"
    controller = MindController(
        data_dir=file_path,
        persona_file=file_path + 'persona.json',
        event_file=adjusted_events_path,
        daily_state_file=file_path + 'daily_state.json'
    )
    
    # 3.2 执行多线程并行处理
    results = controller.run_daily_event_with_threading(
        start_date=start_date,
        end_date=end_date,
        max_workers=max_workers,
        interval_days=interval_days
    )
    
    # 3.3 统计结果
    total_days = len(results)
    success_count = sum(1 for result in results if result[1])
    failed_count = total_days - success_count
    
    log(f"\n=== 数据生成结果 ===")
    log(f"总天数: {total_days}")
    log(f"成功天数: {success_count}")
    log(f"失败天数: {failed_count}")
    log(f"成功率: {(success_count / total_days * 100):.1f}%")
    
    # 3.4 检查是否有失败的日期
    failed_dates = [result[0] for result in results if not result[1]]
    if failed_dates:
        log(f"\n失败的日期: {', '.join(failed_dates)}")
    
    end_time_generate = time.time()
    execution_times['data_generate'] = end_time_generate - start_time_generate
    log(f"数据生成流程耗时: {execution_times['data_generate']:.2f}秒")
    log("=== 数据生成流程完成 ===")
else:
    log("跳过数据生成流程")

# 4. 事件格式化
if format_events:
    log("\n=== 开始事件格式化流程 ===")
    start_time_format = time.time()
    
    # 4.1 创建EventFormatter实例
    formatter = EventFormatter(data_dir=file_path)
    
    # 4.2 执行格式化
    formatter.run(max_workers=max_workers)
    
    end_time_format = time.time()
    execution_times['event_format'] = end_time_format - start_time_format
    log(f"事件格式化流程耗时: {execution_times['event_format']:.2f}秒")
    log("=== 事件格式化流程完成 ===")
else:
    log("跳过事件格式化流程")

# 计算并显示总执行时间
end_time_total = time.time()
execution_times['total'] = end_time_total - start_time_total

log("\n=== 执行时间统计 ===")
for process, duration in execution_times.items():
    if process == 'total':
        log(f"总执行时间: {duration:.2f}秒 ({duration/60:.2f}分钟)")
    else:
        log(f"{process.replace('_', ' ').title()}耗时: {duration:.2f}秒")

log("\n✅ 所有流程执行完成！")