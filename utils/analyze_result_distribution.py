"""
统计 result 目录下所有文件中 is_correct、old_judge 和 human_judge 的分布差异
"""
import os
import json
from collections import Counter


def analyze_file(filepath):
    """
    分析单个文件中的 is_correct、old_judge 和 human_judge 分布
    
    Args:
        filepath: 文件路径
    
    Returns:
        dict: 包含统计信息的字典
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 确保数据是列表
        if not isinstance(data, list):
            return None
        
        is_correct_counter = Counter()
        old_judge_counter = Counter()
        human_judge_counter = Counter()
        combined_counter = Counter()
        
        for item in data:
            is_correct = item.get('is_correct', 'N/A')
            old_judge = item.get('old_judge', 'N/A')
            human_judge = item.get('human_judge', 'N/A')
            
            is_correct_counter[is_correct] += 1
            old_judge_counter[old_judge] += 1
            human_judge_counter[human_judge] += 1
            combined_counter[(is_correct, old_judge, human_judge)] += 1
        
        return {
            'filename': os.path.basename(filepath),
            'total': len(data),
            'is_correct_dist': dict(is_correct_counter),
            'old_judge_dist': dict(old_judge_counter),
            'human_judge_dist': dict(human_judge_counter),
            'combined_dist': {f"{k[0]} & {k[1]} & {k[2]}": v for k, v in combined_counter.items()}
        }
    
    except Exception as e:
        print(f"处理文件 {filepath} 时出错: {e}")
        return None


def main():
    # 目录路径
    dir_path = r"D:\pyCharmProjects\pythonProject4\result"
    
    print(f"正在扫描目录: {dir_path}")
    
    # 获取所有 JSON 文件
    json_files = [f for f in os.listdir(dir_path) if f.endswith('.json')]
    
    if not json_files:
        print("未找到 JSON 文件")
        return
    
    print(f"找到 {len(json_files)} 个 JSON 文件\n")
    
    # 统计所有文件
    all_results = []
    total_is_correct = Counter()
    total_old_judge = Counter()
    total_human_judge = Counter()
    total_combined = Counter()
    grand_total = 0
    
    for filename in sorted(json_files):
        filepath = os.path.join(dir_path, filename)
        result = analyze_file(filepath)
        
        if result:
            all_results.append(result)
            grand_total += result['total']
            
            # 累加统计
            for key, count in result['is_correct_dist'].items():
                total_is_correct[key] += count
            
            for key, count in result['old_judge_dist'].items():
                total_old_judge[key] += count
            
            for key, count in result['human_judge_dist'].items():
                total_human_judge[key] += count
            
            for key, count in result['combined_dist'].items():
                total_combined[key] += count
    
    # 输出每个文件的详细统计
    print("=" * 120)
    print("各文件详细统计")
    print("=" * 120)
    
    for result in all_results:
        print(f"\n文件: {result['filename']}")
        print(f"  总记录数: {result['total']}")
        
        print(f"  is_correct 分布:")
        for key, count in sorted(result['is_correct_dist'].items()):
            percentage = (count / result['total'] * 100) if result['total'] > 0 else 0
            print(f"    {key:<20} {count:>5} ({percentage:.2f}%)")
        
        print(f"  old_judge 分布:")
        for key, count in sorted(result['old_judge_dist'].items()):
            percentage = (count / result['total'] * 100) if result['total'] > 0 else 0
            print(f"    {key:<20} {count:>5} ({percentage:.2f}%)")
        
        print(f"  human_judge 分布:")
        for key, count in sorted(result['human_judge_dist'].items()):
            percentage = (count / result['total'] * 100) if result['total'] > 0 else 0
            print(f"    {key:<20} {count:>5} ({percentage:.2f}%)")
        
        print(f"  组合分布 (is_correct & old_judge & human_judge):")
        for key, count in sorted(result['combined_dist'].items()):
            percentage = (count / result['total'] * 100) if result['total'] > 0 else 0
            print(f"    {key:<60} {count:>5} ({percentage:.2f}%)")
    
    # 输出总体统计
    print("\n" + "=" * 120)
    print("总体统计汇总")
    print("=" * 120)
    print(f"总文件数: {len(all_results)}")
    print(f"总记录数: {grand_total}")
    
    print("\nis_correct 总体分布:")
    print("-" * 60)
    for key, count in sorted(total_is_correct.items()):
        percentage = (count / grand_total * 100) if grand_total > 0 else 0
        print(f"  {key:<20} {count:>8} ({percentage:.2f}%)")
    
    print("\nold_judge 总体分布:")
    print("-" * 60)
    for key, count in sorted(total_old_judge.items()):
        percentage = (count / grand_total * 100) if grand_total > 0 else 0
        print(f"  {key:<20} {count:>8} ({percentage:.2f}%)")
    
    print("\nhuman_judge 总体分布:")
    print("-" * 60)
    for key, count in sorted(total_human_judge.items()):
        percentage = (count / grand_total * 100) if grand_total > 0 else 0
        print(f"  {key:<20} {count:>8} ({percentage:.2f}%)")
    
    print("\n组合分布总体统计 (is_correct & old_judge & human_judge):")
    print("-" * 100)
    for key, count in sorted(total_combined.items()):
        percentage = (count / grand_total * 100) if grand_total > 0 else 0
        print(f"  {key:<70} {count:>8} ({percentage:.2f}%)")
    
    print("=" * 120)


if __name__ == "__main__":
    main()
