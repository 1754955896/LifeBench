import json
import os
import time
import argparse
from datetime import datetime, timedelta
from event.mind import *
from event.event_refiner import EventRefiner
from event.event_formatter import EventFormatter
from event.persona_address_generator import PersonaAddressGenerator
from utils.IO import *

# 命令行参数解析
parser = argparse.ArgumentParser(description='模拟生成模块')
parser.add_argument('--file-path', type=str, default='output/xujing/', help='数据文件路径')
parser.add_argument('--start-date', type=str, default='2025-01-01', help='开始日期')
parser.add_argument('--end-date', type=str, default='2025-12-31', help='结束日期')
parser.add_argument('--max-workers', type=int, default=30, help='最大并行线程数')
parser.add_argument('--interval-days', type=int, default=16, help='每个线程处理的天数')
parser.add_argument('--generate-data', type=int, default=1, help='是否生成数据')
parser.add_argument('--format-events', type=int, default=1, help='是否格式化事件')
parser.add_argument('--instance-id', type=int, default=0, help='人物实例ID')
args = parser.parse_args()

# 配置参数
file_path = args.file_path
start_date = args.start_date
end_date = args.end_date

# 执行时间记录
execution_times = {}
start_time_total = time.time()

# 控制参数：设置为1执行，0跳过
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

if generate_data:
    log("\n=== 开始数据生成流程 ===")
    start_time_generate = time.time()
    log(f"参数设置: 开始日期={start_date}, 结束日期={end_date}, 并行线程数={max_workers}, 区间大小={interval_days}天")
    monthly_file = os.path.join(file_path, "monthly_summaries.json")
    cumulative_file = os.path.join(file_path, "cumulative_summaries.json")
    year = int(start_date[:4])
    def convert(input_file, output_file):

        # 读取输入JSON文件
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 初始化事件数组
        events_array = []
        # 遍历每个月份
        for month, days in data.items():
            # 遍历每天的数据
            for day in days:
                date = day["date"]
                # 遍历当天的每个事件
                for event in day["events"]:
                    # 提取事件信息
                    event_info = {
                        "date": [date],
                        "name": event["name"],
                        "description": event["description"]
                    }
                    # 添加到事件数组
                    events_array.append(event_info)
        # 将事件数组写入输出JSON文件
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(events_array, f, ensure_ascii=False, indent=2)

        print(f"转换完成！共转换了 {len(events_array)} 个事件。")
        print(f"结果已保存到：{output_file}")
    if not os.path.exists(file_path + "event_transfer.json"):
        print(f"未找到event_transfer文件，开始转换...")
        convert(file_path + "daily_draft.json", file_path + "event_transfer.json")
    if not (os.path.exists(monthly_file) and os.path.exists(cumulative_file)):
        print(f"未找到fuzzymemory文件，开始生成该年的月度总结和累积总结...")
        event = read_json_file(file_path + "event_transfer.json")
        print(f"成功读取event_transfer文件，共{len(event)}个事件")
        fuzzy_memory_builder = FuzzyMemoryBuilder.get_instance(event, persona, file_path)
        fuzzy_memory_builder.build_all_summaries(year)
        print("fuzzymemory生成完成！")
    if not os.path.exists(file_path + "location.json"):
        print(f"未找到location.json文件，开始生成画像地址数据...")
        # 创建PersonaAddressGenerator实例
        address_generator = PersonaAddressGenerator()
        # 生成地址数据并保存到location.json
        address_generator.generate_and_save_address_data(
            persona_path=file_path + 'persona.json',
            output_path=file_path
        )
        print("画像地址数据生成完成！")

    # 3.1 创建MindController实例
    adjusted_events_path = file_path + "event_transfer.json"
    controller = MindController(
        data_dir=file_path,
        persona_file=file_path + 'persona.json',
        event_file=adjusted_events_path,
        daily_state_file=file_path + 'daily_draft.json',
        instance_id=args.instance_id,
        loc_data = file_path + 'location.json'
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