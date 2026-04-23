# -*- coding: utf-8 -*-
"""
提取 QA.json 文件中每个问题类别的示例
"""
import json
import os
from collections import defaultdict


def extract_qa_examples(qa_file_path, examples_per_type=10):
    """
    从 QA.json 文件中提取每个问题类别的示例
    
    Args:
        qa_file_path: QA.json 文件路径
        examples_per_type: 每个类别提取的示例数量
    
    Returns:
        dict: {question_type: [examples]}
    """
    # 加载 QA 数据
    with open(qa_file_path, 'r', encoding='utf-8') as f:
        qa_data = json.load(f)
    
    print(f"加载了 {len(qa_data)} 个问题")
    
    # 按问题类型分组
    questions_by_type = defaultdict(list)
    for qa in qa_data:
        q_type = qa.get('question_type', 'unknown')
        questions_by_type[q_type].append(qa)
    
    print(f"\n发现 {len(questions_by_type)} 种问题类型:")
    for q_type, questions in sorted(questions_by_type.items()):
        print(f"  - {q_type}: {len(questions)} 个问题")
    
    # 提取每个类型的示例
    examples = {}
    for q_type, questions in questions_by_type.items():
        # 取前 examples_per_type 个
        selected = questions[:examples_per_type]
        examples[q_type] = []
        
        for qa in selected:
            example = {
                'question': qa.get('question', ''),
                'answer': qa.get('answer', ''),
                'required_events_id': qa.get('required_events_id', [])
            }
            examples[q_type].append(example)
    
    return examples


def save_examples_to_file(examples, output_path):
    """
    将示例保存到文件
    
    Args:
        examples: 提取的示例字典
        output_path: 输出文件路径
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(examples, f, ensure_ascii=False, indent=2)
    print(f"\n示例已保存到: {output_path}")


def print_examples(examples):
    """
    打印示例到控制台
    
    Args:
        examples: 提取的示例字典
    """
    print("\n" + "="*80)
    print("问题类别示例")
    print("="*80)
    
    for q_type, qa_list in sorted(examples.items()):
        print(f"\n{'='*80}")
        print(f"问题类型: {q_type} (共 {len(qa_list)} 个示例)")
        print(f"{'='*80}")
        
        for idx, qa in enumerate(qa_list, 1):
            print(f"\n--- 示例 {idx} ---")
            print(f"问题: {qa['question']}")
            print(f"答案: {qa['answer']}")
            print(f"相关事件ID: {qa['required_events_id']}")


def main():
    # 配置路径
    qa_file_path = r"D:\pyCharmProjects\pythonProject4\fenghaoran\fenghaoran_copy\example1\QA.json"
    output_path = r"D:\pyCharmProjects\pythonProject4\fenghaoran\fenghaoran_copy\example1\qa_examples_by_type.json"
    
    print("="*80)
    print("开始提取 QA 示例...")
    print("="*80)
    
    # 检查文件是否存在
    if not os.path.exists(qa_file_path):
        print(f"错误: 文件不存在 - {qa_file_path}")
        return
    
    # 提取示例
    examples = extract_qa_examples(qa_file_path, examples_per_type=10)
    
    # 打印到控制台
    print_examples(examples)
    
    # 保存到文件
    save_examples_to_file(examples, output_path)
    
    print("\n" + "="*80)
    print("提取完成！")
    print("="*80)


if __name__ == "__main__":
    main()
