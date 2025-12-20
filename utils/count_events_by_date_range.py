import json
from datetime import datetime
import argparse


def count_and_extract_events_by_date_range(json_file, start_date_str, end_date_str):
    """
    统计并抽取指定日期范围内的事件
    
    参数:
        json_file: JSON文件路径
        start_date_str: 起始日期，格式为"YYYY-MM-DD"
        end_date_str: 结束日期，格式为"YYYY-MM-DD"
    
    返回:
        tuple: (指定日期范围内的事件总数, 抽取的事件列表)
    """
    # 解析输入的日期字符串为datetime对象
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    
    # 读取并解析JSON文件
    with open(json_file, 'r', encoding='utf-8') as f:
        events = json.load(f)
    
    # 初始化事件计数器和抽取的事件列表
    total_events = 0
    extracted_events = []
    
    # 遍历所有事件
    for event in events:
        # 检查事件是否有date字段
        if 'date' not in event or not event['date']:
            continue
        
        # 获取事件的日期时间范围字符串
        date_range_str = event['date'][0]
        
        # 解析日期时间范围
        try:
            # 分割起始时间和结束时间
            start_time_str, end_time_str = date_range_str.split('至')
            
            # 解析起始时间和结束时间
            event_start_datetime = datetime.strptime(start_time_str.strip(), "%Y-%m-%d %H:%M:%S")
            event_end_datetime = datetime.strptime(end_time_str.strip(), "%Y-%m-%d %H:%M:%S")
            
            # 提取日期部分
            event_start_date = event_start_datetime.date()
            event_end_date = event_end_datetime.date()
            
            # 检查事件是否在指定日期范围内
            # 只要事件的起始日期小于等于结束日期，并且事件的结束日期大于等于起始日期，就认为事件在范围内
            if event_start_date <= end_date.date() and event_end_date >= start_date.date():
                total_events += 1
                extracted_events.append(event)
        except ValueError:
            # 如果日期格式解析失败，跳过该事件
            continue
    
    return total_events, extracted_events


def save_events_to_json(events, output_file):
    """
    将事件列表保存到JSON文件
    
    参数:
        events: 事件列表
        output_file: 输出JSON文件路径
    """
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(events, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(description='统计并抽取指定日期范围内的事件')
    parser.add_argument('--json_file', type=str, default='D:\\pyCharmProjects\\pythonProject4\\output\\outputs.json',
                        help='JSON文件路径')
    parser.add_argument('--start_date', type=str, required=True,
                        help='起始日期，格式为"YYYY-MM-DD"')
    parser.add_argument('--end_date', type=str, required=True,
                        help='结束日期，格式为"YYYY-MM-DD"')
    parser.add_argument('--output_file', type=str, default=None,
                        help='输出JSON文件路径，用于保存抽取的事件')
    
    # 解析命令行参数
    args = parser.parse_args()
    
    # 统计并抽取事件
    event_count, extracted_events = count_and_extract_events_by_date_range(args.json_file, args.start_date, args.end_date)
    
    # 输出结果
    print(f"从{args.start_date}到{args.end_date}的事件总数为: {event_count}")
    
    # 如果指定了输出文件，保存抽取的事件
    if args.output_file:
        save_events_to_json(extracted_events, args.output_file)
        print(f"已将抽取的事件保存到文件: {args.output_file}")
    else:
        # 默认输出文件路径
        default_output_file = f"extracted_events_{args.start_date}_{args.end_date}.json"
        save_events_to_json(extracted_events, default_output_file)
        print(f"已将抽取的事件保存到默认文件: {default_output_file}")