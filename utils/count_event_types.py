"""
统计 event_tree.json 中事件类型的数目分布
"""
import json
from collections import Counter


def extract_event_types(events, type_counter=None):
    """
    递归提取所有事件的类型
    
    参数:
        events: 事件列表
        type_counter: 计数器
    
    返回:
        Counter: 事件类型计数
    """
    if type_counter is None:
        type_counter = Counter()
    
    for event in events:
        # 获取事件类型
        event_type = event.get("type", "未知类型")
        type_counter[event_type] += 1
        
        # 递归处理子事件

    
    return type_counter


def main():
    # 文件路径
    file_path = r"D:\pyCharmProjects\pythonProject4\fenghaoran\fenghaoran\event_tree.json"
    
    print(f"正在加载文件: {file_path}")
    
    # 加载 JSON 文件
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            events_data = json.load(f)
        print(f"成功加载文件，共 {len(events_data)} 个顶层事件")
    except Exception as e:
        print(f"加载文件失败: {e}")
        return
    
    # 统计事件类型分布
    print("\n正在统计事件类型分布...")
    type_counter = extract_event_types(events_data)
    
    # 按数量降序排序
    sorted_types = type_counter.most_common()
    
    # 输出统计结果
    print("\n" + "="*60)
    print("事件类型数目分布统计")
    print("="*60)
    print(f"{'排名':<6} {'事件类型':<30} {'数量':<10} {'占比':<10}")
    print("-"*60)
    
    total_events = sum(type_counter.values())
    for rank, (event_type, count) in enumerate(sorted_types, 1):
        percentage = (count / total_events * 100) if total_events > 0 else 0
        print(f"{rank:<6} {event_type:<30} {count:<10} {percentage:.2f}%")
    
    print("-"*60)
    print(f"{'总计':<36} {total_events:<10} 100.00%")
    print("="*60)
    
    # 输出详细统计信息
    print(f"\n总事件数: {total_events}")
    print(f"事件类型数: {len(type_counter)}")
    print(f"平均每个类型的事件数: {total_events / len(type_counter):.2f}" if type_counter else "N/A")


if __name__ == "__main__":
    main()
