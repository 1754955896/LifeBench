import json
import os


def count_operations_in_file(file_path):
    """
    统计单个JSON文件中的操作数目
    :param file_path: JSON文件路径
    :return: 操作数目
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if isinstance(data, list):
            return len(data)
        else:
            # 如果不是数组，可能是单个对象
            return 1
    except json.JSONDecodeError as e:
        print(f"JSON解析错误 ({file_path}): {e}")
        return 0
    except Exception as e:
        print(f"处理错误 ({file_path}): {e}")
        return 0


if __name__ == "__main__":
    # 目录路径
    phone_data_dir = "data/xujing/phone_data/"
    
    if not os.path.exists(phone_data_dir):
        print(f"目录不存在: {phone_data_dir}")
        exit(1)
    
    # 排除的文件名
    excluded_files = ["contact.json"]
    
    # 统计每个文件的操作数目
    total_count = 0
    file_counts = {}
    
    for filename in os.listdir(phone_data_dir):
        if filename.endswith(".json") and filename not in excluded_files:
            file_path = os.path.join(phone_data_dir, filename)
            count = count_operations_in_file(file_path)
            file_counts[filename] = count
            total_count += count
    
    # 输出结果
    print("各文件操作数目统计：")
    for filename, count in file_counts.items():
        print(f"  {filename}: {count}")
    
    print(f"\n总操作数目: {total_count}")