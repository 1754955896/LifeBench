"""
统计 refer.json 中每个数组字段的元素数目
"""
import json
from collections import Counter


def count_array_elements(data, prefix="", array_stats=None):
    """
    递归统计 JSON 数据中每个数组字段的元素数目
    
    参数:
        data: JSON 数据（字典或列表）
        prefix: 字段前缀（用于嵌套结构）
        array_stats: 统计结果字典
    
    返回:
        dict: 数组字段统计信息 {字段名: [元素数目列表]}
    """
    if array_stats is None:
        array_stats = {}
    
    if isinstance(data, dict):
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            
            # 如果值是列表，统计其长度
            if isinstance(value, list):
                if full_key not in array_stats:
                    array_stats[full_key] = []
                array_stats[full_key].append(len(value))
                
                # 如果列表中包含字典，递归分析列表中的每个字典
                for item in value:
                    if isinstance(item, dict):
                        count_array_elements(item, f"{full_key}[]", array_stats)
            
            # 如果值是字典，递归处理
            elif isinstance(value, dict):
                count_array_elements(value, full_key, array_stats)
    
    elif isinstance(data, list):
        # 如果顶层是列表，遍历每个元素
        for item in data:
            if isinstance(item, dict):
                count_array_elements(item, prefix, array_stats)
    
    return array_stats


def main():
    # 文件路径
    file_path = r"D:\pyCharmProjects\pythonProject4\persona\persona_file\refer.json"
    
    print(f"正在加载文件: {file_path}")
    
    # 加载 JSON 文件
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"成功加载文件")
    except Exception as e:
        print(f"加载文件失败: {e}")
        return
    
    # 统计数组字段元素数目
    print("\n正在统计数组字段元素数目...")
    array_stats = count_array_elements(data)
    
    if not array_stats:
        print("\n未找到任何数组字段")
        return
    
    # 输出统计结果
    print("\n" + "="*100)
    print("refer.json 数组字段元素数目统计")
    print("="*100)
    print(f"{'排名':<6} {'字段名':<50} {'记录数':<10} {'最小':<8} {'最大':<8} {'平均':<8} {'总和':<10}")
    print("-"*100)
    
    # 计算统计信息并排序
    stats_summary = []
    for field_name, counts in array_stats.items():
        total_records = len(counts)
        min_count = min(counts)
        max_count = max(counts)
        avg_count = sum(counts) / len(counts) if counts else 0
        total_count = sum(counts)
        stats_summary.append((field_name, total_records, min_count, max_count, avg_count, total_count))
    
    # 按总和降序排序
    stats_summary.sort(key=lambda x: x[5], reverse=True)
    
    for rank, (field_name, total_records, min_count, max_count, avg_count, total_count) in enumerate(stats_summary, 1):
        print(f"{rank:<6} {field_name:<50} {total_records:<10} {min_count:<8} {max_count:<8} {avg_count:<8.2f} {total_count:<10}")
    
    print("-"*100)
    print(f"总数组字段数: {len(stats_summary)}")
    print("="*100)
    
    # 输出详细分布
    print("\n各字段详细分布:")
    print("-"*100)
    for field_name, counts in sorted(array_stats.items()):
        counter = Counter(counts)
        most_common = counter.most_common(5)
        dist_str = ", ".join([f"{count}个({freq}次)" for count, freq in most_common])
        print(f"{field_name:<50} 分布: {dist_str}")


if __name__ == "__main__":
    main()
