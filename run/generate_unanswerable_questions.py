# -*- coding: utf-8 -*-
"""
不可回答问题生成器 - 运行脚本
并行对12个月生成，每个月生成5个问题
"""

import sys
import os
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from event.qa_generator.qa_unanswerable_generator import QAUnanswerableGenerator


def main():
    """主函数"""
    
    print("\n" + "="*80)
    print("不可回答问题生成器")
    print("="*80)
    print(f"启动时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80 + "\n")
    
    # 1. 创建生成器实例
    generator = QAUnanswerableGenerator(is_print=False)  # 设置为 False 以减少输出
    
    # 2. 加载数据
    data_path = r"D:\pyCharmProjects\pythonProject4\fenghaoran\fenghaoran"
    print(f"正在加载数据：{data_path}")
    generator.load_data_from_path(data_path)
    
    # 3. 检查数据
    if not generator.persona_data:
        print("错误：用户画像数据为空")
        return
    
    if not generator.draft_event:
        print("错误：草稿事件数据为空")
        return
    
    print(f"✓ 数据加载成功")
    print(f"  - 用户画像字段：{len(generator.persona_data)} 个")
    print(f"  - 可用月份：{len(generator.draft_event)} 个\n")
    
    # 4. 生成问题
    year = 2025
    num_questions_per_month = 5
    
    print("="*80)
    print(f"开始生成 {year} 年的不可回答问题")
    print(f"目标：每个月生成 {num_questions_per_month} 个问题")
    print(f"预计总问题数：{12 * num_questions_per_month} 个")
    print("="*80 + "\n")
    
    start_time = datetime.now()
    
    # 调用 QAGen 方法（内部使用多线程并行处理12个月）
    questions = generator.QAGen(year=year, num_questions_per_month=num_questions_per_month)
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    # 5. 显示统计信息
    print("\n" + "="*80)
    print("生成完成统计")
    print("="*80)
    print(f"总问题数：{len(questions)}")
    print(f"耗时：{duration:.2f} 秒")
    
    if questions:
        # 统计问题类型
        qa_count = sum(1 for q in questions if q.get('type') == 'question_answer')
        mc_count = sum(1 for q in questions if q.get('type') == 'multiple_choice')
        
        print(f"\n问题类型分布：")
        print(f"  - 问答题：{qa_count} 个 ({qa_count/len(questions)*100:.1f}%)")
        print(f"  - 选择题：{mc_count} 个 ({mc_count/len(questions)*100:.1f}%)")
        
        # 按月份统计
        month_stats = {}
        for q in questions:
            ask_time = q.get('ask_time', '')
            if ask_time:
                month_stats[ask_time] = month_stats.get(ask_time, 0) + 1
        
        print(f"\n按提问时间分布：")
        for month_key in sorted(month_stats.keys()):
            print(f"  - {month_key}: {month_stats[month_key]} 个问题")
    
    # 6. 保存结果
    output_dir = r"D:\pyCharmProjects\pythonProject4\result"
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = os.path.join(output_dir, f"unanswerable_questions_{timestamp}.json")
    
    generator.save_questions(questions, output_path)
    
    print(f"\n结果已保存到：{output_path}")
    
    # 7. 显示示例
    if questions:
        print("\n" + "="*80)
        print("示例问题展示（前3个）")
        print("="*80)
        
        for i, q in enumerate(questions[:3], 1):
            print(f"\n--- 问题 {i} ---")
            print(f"问题：{q.get('question', '')}")
            print(f"类型：{q.get('type', '')}")
            print(f"答案：{q.get('answer', '')}")
            print(f"提问时间：{q.get('ask_time', '')}")
            
            if q.get('type') == 'multiple_choice' and 'options' in q:
                print("选项：")
                for opt in q['options']:
                    marker = " ✓" if opt['option'] == q.get('answer') else ""
                    print(f"  {opt['option']}. {opt['content']}{marker}")
    
    print("\n" + "="*80)
    print("任务完成！")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
