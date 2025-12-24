import json
import os
from datetime import datetime


def count_bottom_events(events, start_date=None, end_date=None):
    """
    递归统计底层事件数目，可按日期范围筛选
    :param events: 事件列表或单个事件对象
    :param start_date: 开始日期（格式：YYYY-MM-DD），如果为None则不筛选开始日期
    :param end_date: 结束日期（格式：YYYY-MM-DD），如果为None则不筛选结束日期
    :return: 底层事件数目
    """
    count = 0
    
    # 如果是单个事件对象，转为列表处理
    if isinstance(events, dict):
        events = [events]
    
    # 将日期转换为datetime对象用于比较
    start_dt = None
    end_dt = None
    
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
        except ValueError:
            print(f"开始日期格式错误: {start_date}，应为YYYY-MM-DD格式")
            return 0
    
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            print(f"结束日期格式错误: {end_date}，应为YYYY-MM-DD格式")
            return 0
    
    # 确保开始日期不晚于结束日期
    if start_dt and end_dt and start_dt > end_dt:
        print(f"开始日期 {start_date} 不能晚于结束日期 {end_date}")
        return 0
    
    def is_event_in_date_range(event, start_dt, end_dt):
        """
        检查事件是否在指定日期范围内发生
        """
        # 收集事件涉及的所有日期
        event_dates = []
        
        # 检查子事件的date字段（数组）
        if 'date' in event:
            for date_str in event['date']:
                try:
                    event_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                    event_dates.append(event_date)
                except ValueError:
                    continue
        
        # 检查顶级事件的start_time和end_time
        if 'start_time' in event and 'end_time' in event:
            try:
                start = datetime.strptime(event['start_time'], '%Y-%m-%d').date()
                end = datetime.strptime(event['end_time'], '%Y-%m-%d').date()
                # 对于有时间范围的事件，将整个范围内的日期都考虑进去
                event_dates.append(start)
                event_dates.append(end)
            except ValueError:
                pass
        
        # 检查单个时间字段
        for time_field in ['start_time', 'end_time']:
            if time_field in event:
                try:
                    event_date = datetime.strptime(event[time_field], '%Y-%m-%d').date()
                    event_dates.append(event_date)
                except ValueError:
                    continue
        
        # 如果事件没有日期信息，不筛选
        if not event_dates:
            return True
        
        # 检查是否有任何日期在指定范围内
        for event_date in event_dates:
            # 检查事件日期是否在筛选范围内
            in_start_range = not start_dt or event_date >= start_dt
            in_end_range = not end_dt or event_date <= end_dt
            if in_start_range and in_end_range:
                return True
        
        return False
    
    for event in events:
        # 检查是否有子事件或是否可分解
        has_subevent = 'subevent' in event and event['subevent']
        
        if not has_subevent:
            # 没有子事件或不可分解，是底层事件
            if is_event_in_date_range(event, start_dt, end_dt):
                count += 1
        else:
            # 有子事件且可分解，递归统计子事件
            count += count_bottom_events(event['subevent'], start_date, end_date)
    
    return count


if __name__ == "__main__":
    import sys
    
    # 文件路径
    file_path = "../data/xujing/event_update.json"
    
    # 检查文件是否存在
    if not os.path.exists(file_path):
        print(f"文件不存在: {file_path}")
        print("正在尝试使用备用路径...")
        # 尝试使用备用路径
        alt_file_path = "../data/xujing/event_update.json"
        if os.path.exists(alt_file_path):
            file_path = alt_file_path
            print(f"使用备用路径: {file_path}")
        else:
            print(f"备用路径也不存在: {alt_file_path}")
            exit(1)
    
    # 获取日期范围参数（如果提供）
    start_date = '2025-01-01'
    end_date = '2025-01-31'
    
    if len(sys.argv) == 2:
        # 只提供了一个日期，作为开始日期和结束日期（即单个日期筛选）
        start_date = sys.argv[1]
        end_date = sys.argv[1]
        print(f"筛选日期: {start_date}")
    elif len(sys.argv) > 2:
        # 提供了开始日期和结束日期
        start_date = sys.argv[1]
        end_date = sys.argv[2]
        print(f"筛选日期范围: {start_date} 至 {end_date}")
    
    try:
        # 读取JSON文件
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 统计底层事件数目
        bottom_events_count = count_bottom_events(data, start_date, end_date)
        
        if start_date and end_date:
            if start_date == end_date:
                print(f"在 {start_date} 发生的底层事件总数: {bottom_events_count}")
            else:
                print(f"在 {start_date} 至 {end_date} 期间发生的底层事件总数: {bottom_events_count}")
        else:
            print(f"底层事件总数: {bottom_events_count}")
            
    except json.JSONDecodeError as e:
        print(f"JSON解析错误: {e}")
    except Exception as e:
        print(f"处理错误: {e}")