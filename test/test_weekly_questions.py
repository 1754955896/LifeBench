import sys
import os
import json
import time

# 将项目根目录添加到Python路径
sys.path.append(os.path.abspath('.'))

from event.qa_generator import QAGenerator

# 加载测试数据
def load_test_data(persona_name="zhangmingyuan"):
    """
    加载指定人物的测试数据
    
    Args:
        persona_name: 人物名称，对应data目录下的文件夹名称
    
    Returns:
        persona_data: 用户画像数据
        daily_event_data: 日常事件数据
        event_tree_data: 事件树数据
    """
    data_dir = f'data/{persona_name}'
    
    # 从persona.json加载用户画像数据
    persona_path = os.path.join(data_dir, 'persona.json')
    with open(persona_path, 'r', encoding='utf-8') as f:
        persona_data = json.load(f)
    
    # 从daily_event.json加载日常事件数据
    daily_event_path = os.path.join(data_dir, 'daily_event.json')
    with open(daily_event_path, 'r', encoding='utf-8') as f:
        daily_event_data = json.load(f)
    
    # 从event_tree.json加载事件树数据
    event_tree_path = os.path.join(data_dir, 'event_tree.json')
    with open(event_tree_path, 'r', encoding='utf-8') as f:
        event_tree_data = json.load(f)
    
    return persona_data, daily_event_data, event_tree_data

# 测试按周生成问题功能
def test_weekly_questions():
    # 可以选择不同的人物进行测试
    persona_name = "zhangmingyuan"
    persona_data, daily_event_data, event_tree_data = load_test_data(persona_name)
    
    # 创建QAGenerator实例
    qa_generator = QAGenerator(
        persona=persona_data,
        daily_event=daily_event_data,
        draft_event=daily_event_data,
        event_tree=event_tree_data
    )
    
    # 测试按周生成问题（每周生成5个问题，单跳和多跳各约2-3个）
    print("\n=== 开始测试按周生成问题功能 ===")
    print(f"使用人物数据: {persona_name}")
    print(f"事件数据总数量: {len(daily_event_data)}")
    
    # 记录开始时间
    start_time = time.time()
    
    # 调用按周生成问题的方法
    all_questions = qa_generator.generate_questions_by_week(num_questions_per_week=5)
    
    # 记录结束时间
    end_time = time.time()
    
    print(f"\n总共生成问题数量: {len(all_questions)}")
    print(f"生成耗时: {end_time - start_time:.2f} 秒")
    
    # 统计问题类型
    question_types = {}
    for question in all_questions:
        q_type = question.get('type', '问答')
        question_types[q_type] = question_types.get(q_type, 0) + 1
    
    print(f"\n问题类型统计:")
    for q_type, count in question_types.items():
        print(f"  {q_type}: {count} 个")
    
    # 打印部分生成的问题
    print("\n=== 生成的部分问题 ===")
    for i, question in enumerate(all_questions[:15]):  # 打印前15个问题
        print(f"\n问题{i+1}:")
        print(f"类型: {question.get('type', '问答')}")
        print(f"问题: {question['question']}")
        if 'options' in question:
            print(f"选项: {', '.join(question['options'])}")
        print(f"答案: {question['answer']}")
        print(f"分值: {question['score_points']}")
    
    # 保存生成的问题到文件
    output_file = f'event/{persona_name}_weekly_generated_questions.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_questions, f, ensure_ascii=False, indent=2)
    
    print(f"\n所有问题已保存到 {output_file}")

if __name__ == "__main__":
    test_weekly_questions()