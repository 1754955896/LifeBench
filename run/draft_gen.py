from event.scheduler import Scheduler
from utils import IO
import os
import json
import argparse
import multiprocessing
import time
from datetime import datetime,timedelta
import sys

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
    parser = argparse.ArgumentParser(description='年度时间线草稿生成系统')
    
    # 路径参数
    parser.add_argument('--base-path', type=str, default='output/',
                        help='基础数据路径')
    parser.add_argument('--process-path', type=str, default='process/',
                        help='处理文件路径（相对于base-path，同时作为除每日状态外的其他数据输出路径）')
    parser.add_argument('--instance-id', type=int, default=0,
                        help='人物实例ID')
    
    # 线程/进程参数
    parser.add_argument('--max-workers', type=int, default=None,
                        help='最大工作线程数（默认：CPU核心数×2）')
    
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
        
        # 将median_path设置为process_path
        meidan_path = process_file_path
        
        # 初始化时间记录字典
        execution_times = {
            'yearly_draft_gen': 0
        }
        
        # 计算默认线程数
        cpu_count = multiprocessing.cpu_count()
        default_workers = cpu_count * 2
        
        # 线程数配置
        max_workers = args.max_workers or default_workers
        
        # 打印系统配置
        print(f"系统配置：")
        print(f"- CPU核心数: {cpu_count}")
        print(f"- 最大工作线程数: {max_workers}")
        print(f"- 基础数据路径: {base_file_path}")
        print(f"- 处理文件路径: {process_file_path}")
        print(f"- 除每日状态外的其他数据输出路径: {meidan_path}")
        
        # 确保目录存在
        ensure_directory_exists(process_file_path)
        
        # 读取人物画像
        persona_file = os.path.join(base_file_path, 'persona.json')
        persona = read_json_file(persona_file)

        # 初始化调度器
        scheduler = Scheduler(persona, base_file_path)
        
        # 配置线程数
        if hasattr(scheduler, 'max_workers'):
            scheduler.max_workers = max_workers
        
        # 生成年度时间线草稿
        daily_status_file = os.path.join(base_file_path, 'daily_status.json')
        if not os.path.exists(daily_status_file):
            print('\n开始生成年度时间线草稿...')
            draft_start_time = time.time()
            scheduler.generate_yearly_timeline_draft(persona, base_file_path, meidan_path)
            draft_end_time = time.time()
            execution_times['yearly_draft_gen'] = draft_end_time - draft_start_time
            print(f'年度时间线草稿生成完成-------------------------- (耗时: {timedelta(seconds=execution_times["yearly_draft_gen"])})')
        else:
            print(f'\n跳过年度时间线草稿生成步骤 - 输出文件 {daily_status_file} 已存在')
        
        # 记录总结束时间
        total_end_time = time.time()
        total_execution_time = total_end_time - total_start_time
        
        # 打印执行时间汇总
        print('\n执行时间汇总：')
        print(f'- 总执行时间: {timedelta(seconds=total_execution_time)}')
        if 'yearly_draft_gen' in execution_times and execution_times['yearly_draft_gen'] > 0:
            print(f'- 年度时间线草稿生成时间: {timedelta(seconds=execution_times["yearly_draft_gen"])})')
        
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