import json
import os


def count_bottom_events(events):
    """
    递归统计底层事件数目
    :param events: 事件列表或单个事件对象
    :return: 底层事件数目
    """
    count = 0
    
    # 如果是单个事件对象，转为列表处理
    if isinstance(events, dict):
        events = [events]
    
    for event in events:
        # 检查是否有子事件或是否可分解
        has_subevent = 'subevent' in event and event['subevent']
        
        if not has_subevent:
            # 没有子事件或不可分解，是底层事件
            count += 1
        else:
            # 有子事件且可分解，递归统计子事件
            count += count_bottom_events(event['subevent'])
    
    return count


if __name__ == "__main__":
    # 文件路径
    file_path = "output/process/event_decompose_1.json"
    
    if not os.path.exists(file_path):
        print(f"文件不存在: {file_path}")
        exit(1)
    
    try:
        # 读取JSON文件
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 统计底层事件数目
        bottom_events_count = count_bottom_events(data)
        
        print(f"底层事件总数: {bottom_events_count}")
        
    except json.JSONDecodeError as e:
        print(f"JSON解析错误: {e}")
    except Exception as e:
        print(f"处理错误: {e}")