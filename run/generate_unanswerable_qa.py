"""
调用 QAUnanswerableGenerator 为 fenghaoran_copy 生成不可回答问题
"""

import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from event.qa_generator.qa_unanswerable_generator import QAUnanswerableGenerator


def main():
    """主函数"""
    
    # 数据路径
    data_path = r"D:\pyCharmProjects\pythonProject4\fenghaoran\fenghaoran_copy"
    phone_data_dir = os.path.join(data_path, "phone_data")
    
    print("="*80)
    print("开始生成不可回答问题")
    print(f"数据路径: {data_path}")
    print("="*80)
    
    # 初始化生成器
    print("\n[Step 1] 初始化生成器...")
    generator = QAUnanswerableGenerator(
        phone_data_dir=phone_data_dir,
        is_print=True
    )
    
    # 加载数据
    print("\n[Step 2] 加载数据...")
    generator.load_data_from_path(data_path)
    print("✓ 数据加载完成")
    
    # 生成问题
    print("\n[Step 3] 生成问题...")
    questions = generator.QAGen(year=2025, num_questions_per_month=5)
    
    if not questions:
        print("\n⚠️  未生成任何问题")
        return
    
    print(f"\n✓ 成功生成 {len(questions)} 个不可回答问题")
    
    # 保存结果
    output_path = os.path.join(data_path, "unanswerable_qa.json")
    print(f"\n[Step 4] 保存结果到: {output_path}")
    
    try:
        import json
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(questions, f, ensure_ascii=False, indent=2)
        print(f"✓ 成功保存 {len(questions)} 个问题")
        
        # 显示文件大小
        file_size = os.path.getsize(output_path) / (1024 * 1024)  # MB
        print(f"✓ 文件大小: {file_size:.2f} MB")
        
    except Exception as e:
        print(f"✗ 保存失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 统计信息
    print(f"\n{'='*80}")
    print("生成完成统计")
    print(f"{'='*80}")
    
    # 按月份统计
    month_stats = {}
    for q in questions:
        ask_time = q.get('ask_time', '')
        if ask_time:
            month_stats[ask_time] = month_stats.get(ask_time, 0) + 1
    
    print(f"\n各月份问题分布:")
    for month in sorted(month_stats.keys()):
        print(f"  - {month}: {month_stats[month]} 个问题")
    
    print(f"\n总计: {len(questions)} 个问题")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
