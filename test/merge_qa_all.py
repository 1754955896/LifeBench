# -*- coding: utf-8 -*-
"""
合并 QA_all 文件夹中所有 JSON 文件为一个 QA.json
"""
import json
import os
from collections import defaultdict


def merge_qa_files(qa_all_dir, output_path=None):
    """
    合并 QA_all 文件夹中所有 JSON 文件
    
    Args:
        qa_all_dir: QA_all 文件夹路径
        output_path: 输出文件路径（如果为 None，则保存到 qa_all_dir/QA.json）
    
    Returns:
        bool: 是否成功
    """
    if not os.path.exists(qa_all_dir):
        print(f"错误：文件夹不存在 - {qa_all_dir}")
        return False
    
    if output_path is None:
        output_path = os.path.join(qa_all_dir, "QA.json")
    
    print(f"正在扫描文件夹: {qa_all_dir}")
    
    # 获取所有 JSON 文件（排除 QA.json 本身）
    json_files = []
    for filename in sorted(os.listdir(qa_all_dir)):
        if filename.endswith('.json') and filename != 'QA.json':
            filepath = os.path.join(qa_all_dir, filename)
            if os.path.isfile(filepath):
                json_files.append((filename, filepath))
    
    if not json_files:
        print("未找到任何 JSON 文件")
        return False
    
    print(f"找到 {len(json_files)} 个 JSON 文件:")
    for filename, _ in json_files:
        print(f"  - {filename}")
    
    # 合并所有数据
    all_questions = []
    file_stats = {}
    
    for filename, filepath in json_files:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, list):
                question_count = len(data)
                all_questions.extend(data)
                file_stats[filename] = question_count
                print(f"✓ {filename}: {question_count} 个问题")
            else:
                print(f"⚠️ {filename}: 文件格式不是数组，跳过")
        
        except Exception as e:
            print(f"✗ {filename}: 读取失败 - {e}")
    
    print(f"\n合并完成:")
    print(f"  - 总问题数: {len(all_questions)}")
    print(f"  - 来源文件数: {len(file_stats)}")
    
    # 统计问题类型分布
    type_count = defaultdict(int)
    for qa in all_questions:
        q_type = qa.get('question_type', 'unknown')
        type_count[q_type] += 1
    
    print(f"\n问题类型分布:")
    for q_type, count in sorted(type_count.items()):
        print(f"  - {q_type}: {count} 个问题 ({count/len(all_questions)*100:.1f}%)")
    
    # 保存结果
    print(f"\n正在保存到: {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_questions, f, ensure_ascii=False, indent=2)
    
    print(f"✓ 合并完成！共 {len(all_questions)} 个问题")
    return True


def main():
    # 配置路径
    qa_all_dir = r"D:\pyCharmProjects\pythonProject4\fenghaoran\fenghaoran_copy\QA_all"
    
    print("="*80)
    print("开始合并 QA_all 文件夹中的所有 JSON 文件...")
    print("="*80)
    
    # 执行合并
    success = merge_qa_files(qa_all_dir)
    
    if success:
        print("\n" + "="*80)
        print("合并成功！")
        print("="*80)
        
        # 验证结果
        output_path = os.path.join(qa_all_dir, "QA.json")
        if os.path.exists(output_path):
            with open(output_path, 'r', encoding='utf-8') as f:
                result = json.load(f)
            print(f"\n验证: {output_path} 包含 {len(result)} 个问题")
    else:
        print("\n" + "="*80)
        print("合并失败！")
        print("="*80)


if __name__ == "__main__":
    main()
