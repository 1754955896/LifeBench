import json
import os
from collections import defaultdict


def count_operations_in_file(file_path):
    """
    统计单个JSON文件中的操作类型数目分布
    :param file_path: JSON文件路径
    :return: 总操作数目和类型计数字典
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        type_counts = defaultdict(int)
        total = 0
        
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and 'type' in item:
                    type_counts[item['type']] += 1
                    total += 1
        elif isinstance(data, dict) and 'type' in data:
            type_counts[data['type']] += 1
            total = 1
        
        return total, dict(type_counts)
    except json.JSONDecodeError as e:
        print(f"JSON解析错误 ({file_path}): {e}")
        return 0, {}
    except Exception as e:
        print(f"处理错误 ({file_path}): {e}")
        return 0, {}


if __name__ == "__main__":
    # 目录路径
    phone_data_dir = "../data/xujing/phone_data/"
    
    if not os.path.exists(phone_data_dir):
        print(f"目录不存在: {phone_data_dir}")
        exit(1)
    
    # 排除的文件名
    excluded_files = ["contact.json"]
    
    # 统计每个文件的操作数目和类型分布
    total_count = 0
    file_counts = {}
    overall_type_counts = defaultdict(int)
    
    for filename in os.listdir(phone_data_dir):
        if filename.endswith(".json") and filename not in excluded_files:
            file_path = os.path.join(phone_data_dir, filename)
            file_total, type_counts = count_operations_in_file(file_path)
            file_counts[filename] = {
                'total': file_total,
                'type_counts': type_counts
            }
            total_count += file_total
            
            # 汇总到总体类型计数
            for operation_type, count in type_counts.items():
                overall_type_counts[operation_type] += count
    
    # 输出每个文件的统计结果
    print("各文件操作数目及类型分布统计：")
    for filename, stats in file_counts.items():
        print(f"\n{filename}:")
        print(f"  总操作数目: {stats['total']}")
        print(f"  类型分布:")
        for operation_type, count in stats['type_counts'].items():
            print(f"    - {operation_type}: {count} ({count/stats['total']*100:.1f}%)")
    
    # 输出总体统计结果
    print("\n" + "="*50)
    print("总体操作数目及类型分布统计：")
    print(f"总操作数目: {total_count}")
    print(f"类型分布:")
    for operation_type, count in sorted(overall_type_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {operation_type}: {count} ({count/total_count*100:.1f}%)")