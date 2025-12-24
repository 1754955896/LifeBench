from event.scheduler import Scheduler
from utils import IO
import os
import json
import argparse
import multiprocessing
import time
from datetime import datetime,timedelta


def ensure_directory_exists(directory):
    """确保目录存在，如果不存在则创建"""
    if not os.path.exists(directory):
        os.makedirs(directory)


def read_json_file(file_path):
    """读取JSON文件，添加错误处理"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"错误：文件 {file_path} 不存在")
        raise
    except json.JSONDecodeError:
        print(f"错误：文件 {file_path} 不是有效的JSON格式")
        raise


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='事件生成与规划系统')
    
    # 路径参数
    parser.add_argument('--base-path', type=str, default='output/',
                        help='基础数据路径')
    parser.add_argument('--process-path', type=str, default='process/',
                        help='处理文件路径（相对于base-path）')
    parser.add_argument('--instance-id', type=int, default=0,
                        help='人物实例ID')
    
    # 线程/进程参数
    parser.add_argument('--max-workers', type=int, default=None,
                        help='最大工作线程数（默认：CPU核心数×2）')
    parser.add_argument('--decompose-workers', type=int, default=None,
                        help='事件分解的最大工作线程数（默认：与max-workers相同）')
    parser.add_argument('--schedule-workers', type=int, default=None,
                        help='事件规划的最大工作线程数（默认：与max-workers相同）')
    
    # 功能控制参数
    parser.add_argument('--skip-gen', action='store_true',
                        help='跳过事件生成步骤')
    parser.add_argument('--skip-schedule', action='store_true',
                        help='跳过事件规划步骤')
    parser.add_argument('--skip-decompose', action='store_true',
                        help='跳过事件分解步骤')
    parser.add_argument('--skip-reorder', action='store_true',
                        help='跳过事件重排和ID分配步骤')
    parser.add_argument('--only-reorder', action='store_true',
                        help='仅执行事件重排和ID分配步骤，跳过其他所有步骤')
    
    return parser.parse_args()


def main():
    """主函数"""
    args = parse_args()
    
    try:
        # 记录总开始时间
        total_start_time = time.time()
        
        # 参数配置
        base_file_path = args.base_path
        process_file_path = os.path.join(base_file_path, args.process_path)
        
        # 初始化时间记录字典
        execution_times = {
            'event_gen': 0,
            'event_schedule': 0,
            'event_decompose': 0,
            'event_reorder': 0
        }
        
        # 仅执行重排步骤的情况
        if args.only_reorder:
            print("仅执行事件重排和ID分配步骤...")
            event_decompose_file = os.path.join(base_file_path, 'event_decompose_dfs.json')
            if os.path.exists(event_decompose_file):
                # 读取人物画像（调度器需要）
                persona_file = os.path.join(base_file_path, 'persona.json')
                persona = read_json_file(persona_file)
                # 初始化调度器
                scheduler = Scheduler(persona, base_file_path)
                
                print('开始重排事件并分配id...')
                reorder_start_time = time.time()
                decomposed_events = read_json_file(event_decompose_file)
                
                # 定义递归函数处理层级事件排序和id分配
                def sort_and_assign_ids_recursive(events, parent_id="", level=0):
                    """
                    递归地对事件进行排序并分配id
                    :param events: 事件列表
                    :param parent_id: 父事件id
                    :param level: 当前层级
                    :return: 排序并分配id后的事件列表
                    """
                    # 按开始时间排序
                    sorted_events = sorted(events, key=lambda x: scheduler.extract_date_from_text(x.get("start_time", "")))
                    
                    # 分配id并递归处理子事件
                    for idx, event in enumerate(sorted_events, start=1):
                        # 生成层级id
                        if parent_id:
                            event["event_id"] = f"{parent_id}-{idx}"
                        else:
                            event["event_id"] = idx
                        
                        # 合并start_time和end_time为date字段
                        start_time = event.get("start_time", "")
                        end_time = event.get("end_time", "")
                        if start_time and end_time:
                            # 提取日期部分（去除时间）
                            start_date = start_time.split(" ")[0] if " " in start_time else start_time
                            end_date = end_time.split(" ")[0] if " " in end_time else end_time
                            # 格式化为["开始日期至结束日期"]
                            event["date"] = [f"{start_date}至{end_date}"]
                        
                        # 递归处理子事件
                        if "subevent" in event and event["subevent"]:
                            event["subevent"] = sort_and_assign_ids_recursive(event["subevent"], event["event_id"], level + 1)
                    
                    return sorted_events
                
                # 处理事件
                refined_events = sort_and_assign_ids_recursive(decomposed_events)
                
                # 保存结果
                with open(event_decompose_file, 'w', encoding='utf-8') as f:
                    json.dump(refined_events, f, ensure_ascii=False, indent=2)
                
                reorder_end_time = time.time()
                execution_times['event_reorder'] = reorder_end_time - reorder_start_time
                print(f'事件重排并分配id完成-------------------------- (耗时: {timedelta(seconds=execution_times["event_reorder"])})')
            else:
                print(f"错误：{event_decompose_file} 文件不存在，无法进行事件重排")
                raise FileNotFoundError(f"{event_decompose_file} not found")
        else:
            # 计算默认线程数
            cpu_count = multiprocessing.cpu_count()
            default_workers = cpu_count * 2
            
            # 线程数配置
            max_workers = args.max_workers or default_workers
            decompose_workers = args.decompose_workers or max_workers
            schedule_workers = args.schedule_workers or max_workers
            
            print(f"系统配置：")
            print(f"- CPU核心数: {cpu_count}")
            print(f"- 最大工作线程数: {max_workers}")
            print(f"- 事件分解线程数: {decompose_workers}")
            print(f"- 事件规划线程数: {schedule_workers}")
            print(f"- 基础数据路径: {base_file_path}")
            print(f"- 处理文件路径: {process_file_path}")
            
            # 确保目录存在
            ensure_directory_exists(process_file_path)
            
            # 读取人物画像
            persona_file = os.path.join(base_file_path, 'persona.json')
            persona = read_json_file(persona_file)

            # 初始化调度器 - 传递线程数配置
            scheduler = Scheduler(persona, base_file_path)
            
            # 配置线程数
            # 注意：需要确保Scheduler类支持这些属性设置
            if hasattr(scheduler, 'max_workers'):
                scheduler.max_workers = max_workers
            if hasattr(scheduler, 'decompose_workers'):
                scheduler.decompose_workers = decompose_workers
            if hasattr(scheduler, 'schedule_workers'):
                scheduler.schedule_workers = schedule_workers
        
        # 生成事件
        event_1_file = os.path.join(process_file_path, 'event_1.json')
        if not args.skip_gen and not os.path.exists(event_1_file):
            print('\n开始生成事件...')
            gen_start_time = time.time()
            scheduler.main_gen_event()
            gen_end_time = time.time()
            execution_times['event_gen'] = gen_end_time - gen_start_time
            print(f'事件生成完成-------------------------- (耗时: {timedelta(seconds=execution_times["event_gen"])})')
        elif os.path.exists(event_1_file):
            print(f'\n跳过事件生成步骤 - 输出文件 {event_1_file} 已存在')
        else:
            print('\n跳过事件生成步骤')

        # 规划事件
        event_2_file = os.path.join(process_file_path, 'event_2.json')
        if not args.skip_schedule and not os.path.exists(event_2_file):
            print('开始规划事件...')
            schedule_start_time = time.time()
            if os.path.exists(event_1_file):
                json_data = read_json_file(event_1_file)
                # 传递线程数参数给规划方法
                scheduler.main_schedule_event(json_data, base_file_path)
                schedule_end_time = time.time()
                execution_times['event_schedule'] = schedule_end_time - schedule_start_time
                print(f'事件规划完成-------------------------- (耗时: {timedelta(seconds=execution_times["event_schedule"])})')
            else:
                print(f"错误：{event_1_file} 文件不存在，无法进行事件规划")
                raise FileNotFoundError(f"{event_1_file} not found")
        elif os.path.exists(event_2_file):
            print(f'跳过事件规划步骤 - 输出文件 {event_2_file} 已存在')
        else:
            print('跳过事件规划步骤')
        
        # 分解事件
        event_decompose_file = os.path.join(base_file_path, 'event_decompose_dfs.json')
        if not args.skip_decompose and not os.path.exists(event_decompose_file):
            print('开始分解事件...')
            decompose_start_time = time.time()
            if os.path.exists(event_2_file):
                json_data = read_json_file(event_2_file)
                # 传递线程数参数给分解方法
                scheduler.main_decompose_event(json_data, base_file_path)
                decompose_end_time = time.time()
                execution_times['event_decompose'] = decompose_end_time - decompose_start_time
                print(f'事件分解完成-------------------------- (耗时: {timedelta(seconds=execution_times["event_decompose"])})')
            else:
                print(f"错误：{event_2_file} 文件不存在，无法进行事件分解")
                raise FileNotFoundError(f"{event_2_file} not found")
        elif os.path.exists(event_decompose_file):
            print(f'跳过事件分解步骤 - 输出文件 {event_decompose_file} 已存在')
        else:
            print('跳过事件分解步骤')
        
        # 重排事件并分配id（单独步骤）
        if not args.skip_reorder and os.path.exists(event_decompose_file):
            print('开始重排事件并分配id...')
            reorder_start_time = time.time()
            decomposed_events = read_json_file(event_decompose_file)
            
            # 定义递归函数处理层级事件排序和id分配
            def sort_and_assign_ids_recursive(events, parent_id="", level=0):
                """
                递归地对事件进行排序并分配id
                :param events: 事件列表
                :param parent_id: 父事件id
                :param level: 当前层级
                :return: 排序并分配id后的事件列表
                """
                # 按开始时间排序
                sorted_events = sorted(events, key=lambda x: scheduler.extract_date_from_text(x.get("start_time", "")))
                
                # 分配id并递归处理子事件
                for idx, event in enumerate(sorted_events, start=1):
                    # 生成层级id
                    if parent_id:
                        event["event_id"] = f"{parent_id}-{idx}"
                    else:
                        event["event_id"] = idx
                    
                    # 合并start_time和end_time为date字段
                    start_time = event.get("start_time", "")
                    end_time = event.get("end_time", "")
                    if start_time and end_time:
                        # 提取日期部分（去除时间）
                        start_date = start_time.split(" ")[0] if " " in start_time else start_time
                        end_date = end_time.split(" ")[0] if " " in end_time else end_time
                        # 格式化为["开始日期至结束日期"]
                        event["date"] = [f"{start_date}至{end_date}"]
                    
                    # 递归处理子事件
                    if "subevent" in event and event["subevent"]:
                        event["subevent"] = sort_and_assign_ids_recursive(event["subevent"], event["event_id"], level + 1)
                
                return sorted_events
            
            # 处理事件
            refined_events = sort_and_assign_ids_recursive(decomposed_events)
            
            # 保存结果
            with open(event_decompose_file, 'w', encoding='utf-8') as f:
                json.dump(refined_events, f, ensure_ascii=False, indent=2)
            
            reorder_end_time = time.time()
            execution_times['event_reorder'] = reorder_end_time - reorder_start_time
            print(f'事件重排并分配id完成-------------------------- (耗时: {timedelta(seconds=execution_times["event_reorder"])})')
        elif args.skip_reorder:
            print('跳过事件重排和ID分配步骤')
            
        # 记录总结束时间
        total_end_time = time.time()
        total_execution_time = total_end_time - total_start_time
        
        # 打印执行时间汇总
        print('\n执行时间汇总：')
        print(f'- 总执行时间: {timedelta(seconds=total_execution_time)}')
        if 'event_gen' in execution_times and execution_times['event_gen'] > 0:
            print(f'- 事件生成时间: {timedelta(seconds=execution_times["event_gen"])}')
        if 'event_schedule' in execution_times and execution_times['event_schedule'] > 0:
            print(f'- 事件规划时间: {timedelta(seconds=execution_times["event_schedule"])}')
        if 'event_decompose' in execution_times and execution_times['event_decompose'] > 0:
            print(f'- 事件分解时间: {timedelta(seconds=execution_times["event_decompose"])}')
        if 'event_reorder' in execution_times and execution_times['event_reorder'] > 0:
            print(f'- 事件重排时间: {timedelta(seconds=execution_times["event_reorder"])}')
        
        print('\n所有操作完成！')
            
    except KeyboardInterrupt:
        print('\n程序被用户中断')
        exit(0)
    except Exception as e:
        print(f"程序执行出错：{str(e)}")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == '__main__':
    main()