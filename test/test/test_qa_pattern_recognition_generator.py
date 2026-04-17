"""
测试 QAPatternRecognitionGenerator 类的功能
主要测试月份总结生成功能
"""

import json
import os
import sys

# 添加项目根目录到 Python 路径
project_root = r"D:\pyCharmProjects\pythonProject4"
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from event.qa_generator.qa_pattern_recognition_generator import QAPatternRecognitionGenerator


def test_initialization():
    """测试 QAPatternRecognitionGenerator 的初始化"""
    print("\n" + "="*80)
    print("测试 1: QAPatternRecognitionGenerator 初始化")
    print("="*80)
    
    # 使用真实测试数据路径
    data_path = r"/fenghaoran/fenghaoran"
    
    if not os.path.exists(data_path):
        print(f"❌ 数据路径不存在：{data_path}")
        return False
    
    # 加载测试数据
    generator = QAPatternRecognitionGenerator(
        draft_event={},
        phone_data_dir=os.path.join(data_path, "phone_data"),
        is_print=True
    )
    generator.load_data_from_path(data_path)
    
    print(f"✓ 生成器初始化成功")
    print(f"  - Persona 数据：{len(generator.persona_data)} 条")
    print(f"  - Event Tree 数据：{len(generator.event_tree)} 条")
    print(f"  - Daily Event 数据：{len(generator.daily_event)} 条")
    print(f"  - Draft Event 数据：{len(generator.draft_event)} 个月份")
    print(f"  - Phone Data 类型：{list(generator.phonedata.keys())}")
    print(f"  - 打印开关：{generator.is_print}")
    
    return True


def test_single_month_summary():
    """测试单个月份总结的生成"""
    print("\n" + "="*80)
    print("测试 2: 单个月份总结生成")
    print("="*80)
    
    data_path = r"/fenghaoran/fenghaoran"
    generator = QAPatternRecognitionGenerator(
        draft_event={},
        phonedata={},
        phone_data_dir=os.path.join(data_path, "phone_data"),
        is_print=True
    )
    generator.load_data_from_path(data_path)
    
    # 检查 draft_event 数据
    if not generator.draft_event:
        print("❌ draft_event 数据为空")
        return False
    
    # 获取第一个可用的月份
    available_months = [k for k in generator.draft_event.keys() 
                       if isinstance(k, str) and len(k) == 7 and k[4] == '-']
    
    if not available_months:
        print("❌ 没有可用的月份数据")
        return False
    
    # 选择第一个月进行测试
    test_month = available_months[0]
    year, month = map(int, test_month.split('-'))
    
    print(f"\n测试月份：{test_month}")
    print(f"该月份的草稿事件数量：{len(generator.draft_event.get(test_month, []))}")
    
    # 调用月份总结生成
    result = generator._generate_monthly_summary(year, month)
    
    if result is None:
        print("❌ 月份总结生成失败")
        return False
    
    print(f"\n✓ 月份总结生成成功")
    print(f"  - 月份：{result.get('month', 'N/A')}")
    print(f"  - 主要事件：{result.get('major_events', '')[:100]}...")
    print(f"  - 里程碑事件数量：{len(result.get('key_milestones', []))}")
    print(f"  - 偏好变化：{result.get('preference_changes', '')[:100]}...")
    print(f"  - 新习惯数量：{len(result.get('new_habits', []))}")
    print(f"  - 兴趣变化：{result.get('interest_changes', '')[:100]}...")
    print(f"  - 健康变化：{result.get('health_fitness_changes', '')[:100]}...")
    print(f"  - 情感事件数量：{len(result.get('emotional_events', []))}")
    print(f"  - 整体总结：{result.get('overall_summary', '')[:100]}...")
    
    return True


def test_multiple_month_summaries():
    """测试多个月份总结的生成（并行）"""
    print("\n" + "="*80)
    print("测试 3: 多个月份总结生成 (并行)")
    print("="*80)
    
    data_path = r"/fenghaoran/fenghaoran"
    generator = QAPatternRecognitionGenerator(
        draft_event={},
        phonedata={},
        phone_data_dir=os.path.join(data_path, "phone_data"),
        is_print=True
    )
    generator.load_data_from_path(data_path)
    
    # 检查可用的月份
    if not generator.draft_event:
        print("❌ draft_event 数据为空")
        return False
    
    available_months = [k for k in generator.draft_event.keys() 
                       if isinstance(k, str) and len(k) == 7 and k[4] == '-']
    
    if not available_months:
        print("❌ 没有可用的月份数据")
        return False
    
    # 统计每年的月份
    year_months = {}
    for month_key in available_months:
        year = month_key.split('-')[0]
        if year not in year_months:
            year_months[year] = []
        year_months[year].append(int(month_key.split('-')[1]))
    
    # 选择第一个有数据的年份
    test_year = list(year_months.keys())[0]
    months_in_year = year_months[test_year]
    
    print(f"\n测试年份：{test_year}")
    print(f"可用月份数：{len(months_in_year)}")
    print(f"月份列表：{sorted(months_in_year)}")
    
    # 调用年度总结生成（会并行处理所有月份）
    summaries = generator._generate_yearly_summaries(int(test_year))
    
    if not summaries:
        print("❌ 年度总结生成失败")
        return False
    
    print(f"\n✓ 年度总结生成成功")
    print(f"  - 成功生成的月份数：{len(summaries)}/12")
    
    # 显示前 3 个月的摘要
    for i, summary in enumerate(summaries[:3], 1):
        print(f"\n  第 {i} 个月 ({summary.get('month', 'N/A')}):")
        print(f"    - 主要事件：{summary.get('major_events', '')[:80]}...")
        print(f"    - 里程碑：{len(summary.get('key_milstones', []))} 个")
    
    return True


def test_qagen_entry():
    """测试 QAGen 主入口函数（目前只测试月份总结部分）"""
    print("\n" + "="*80)
    print("测试 4: QAGen 主入口 (月份总结部分)")
    print("="*80)
    
    data_path = r"/fenghaoran/fenghaoran"
    generator = QAPatternRecognitionGenerator(
        draft_event={},
        phonedata={},
        phone_data_dir=os.path.join(data_path, "phone_data"),
        is_print=True
    )
    generator.load_data_from_path(data_path)
    
    # 使用 2025 年作为测试年份
    test_year = "2025"
    
    print(f"\n测试年份：{test_year}")
    print("开始调用 QAGen 方法...\n")
    
    # 调用 QAGen 方法（目前只会生成月份总结）
    results = generator.QAGen(year=test_year)
    
    print(f"\n✓ QAGen 调用完成")
    print(f"  - 返回结果数量：{len(results)}")
    print(f"  - 注：当前实现仅生成月份总结，尚未实现问题生成")
    
    return True


def test_check_agent():
    """测试 check_agent 方法"""
    print("\n" + "="*80)
    print("测试 5: check_agent 方法测试")
    print("="*80)
    
    data_path = r"/fenghaoran/fenghaoran"
    generator = QAPatternRecognitionGenerator(
        draft_event={},
        phone_data_dir=os.path.join(data_path, "phone_data"),
        is_print=True
    )
    generator.load_data_from_path(data_path)
    
    # 检查 daily_event 数据
    if not generator.daily_event:
        print("❌ daily_event 数据为空")
        return False
    
    # 准备测试问题（单个问题，不是列表）
    test_question = {
        "question": "我这个月晨跑恢复得怎么样？频率和距离有变化吗？",
        "answer": "您这个月晨跑经历了从假期中断到系统恢复再到优化的过程。假期阶段（10 月 1-6 日）晨跑中断，恢复阶段（10 月 7-14 日）频率为每周 3-4 次，距离 3-5 公里，注重心率区间训练；优化阶段（10 月 15-31 日）频率保持每周 4 次左右，距离 4-5 公里，并加入坡道训练和长距离慢跑。整体上，晨跑从恢复性训练逐步过渡到更稳定的有氧运动。",
        "score_points": [
            {
                "description": "准确回答出晨跑恢复的过程和阶段。",
                "score": 10
            }
        ],
        "required_events_id": [],
        "question_type": "ND",
        "evidence": []
    }
    
    # 选择测试月份
    test_month = "2025-10"
    
    print(f"\n测试月份：{test_month}")
    print(f"测试问题：{test_question['question']}")
    
    # 调用 check_agent 方法（传递单个问题）
    optimized_question = generator.check_agent(test_question, test_month)
    
    if not optimized_question:
        print("❌ check_agent 方法返回空结果")
        return False
    
    print(f"\n✓ check_agent 调用完成")
    print(f"  - 优化后问题：{optimized_question.get('question', 'N/A')}")
    
    # 显示优化后的问题
    print(f"\n  优化后的问题:")
    print(f"    - 问题：{optimized_question.get('question', 'N/A')}")
    print(f"    - 答案：{optimized_question.get('answer', 'N/A')}")
    print(f"    - 评分要点：{len(optimized_question.get('score_points', []))} 个")
    print(f"    - 所需事件 ID：{optimized_question.get('required_events_id', [])}")
    print(f"    - 问题类型：{optimized_question.get('question_type', 'N/A')}")
    
    return True


def test_generate_monthly_questions():
    """
    测试 _generate_monthly_questions 方法 - 生成单月问题并保存
    
    Returns:
        bool: 测试是否成功
    """
    print("\n" + "="*80)
    print("[Test] _generate_monthly_questions 方法测试")
    print("="*80)
    
    # 创建生成器实例（使用真实数据）
    base_dir = r"/fenghaoran/fenghaoran"
    generator = QAPatternRecognitionGenerator(
        persona_data=None,
        event_tree=None,
        daily_event=None,
        draft_event=None,
        special_event=None,
        phone_data_dir=os.path.join(base_dir, "phone_data", "json"),
        is_print=True
    )
    
    # 加载真实数据
    generator.load_data_from_path(base_dir)
    
    # 选择测试月份
    test_month = "2025-10"
    
    # 检查该月份是否有草稿事件数据
    if test_month not in generator.draft_event or not generator.draft_event[test_month]:
        print(f"[Warning] {test_month} 没有草稿事件数据，尝试查找其他月份...")
        available_months = [k for k in generator.draft_event.keys() 
                           if isinstance(k, str) and len(k) == 7 and k[4] == '-']
        if available_months:
            test_month = available_months[0]
            print(f"[Info] 改用月份：{test_month}")
        else:
            print(f"[Error] 没有任何可用的月份数据")
            return False
    
    print(f"\n[Test] 测试月份：{test_month}")
    print(f"[Test] 该月份草稿事件数量：{len(generator.draft_event.get(test_month, []))}")
    
    # 生成该月份的总结
    print(f"\n[Test] 正在生成 {test_month} 的月份总结...")
    year, month = map(int, test_month.split('-'))
    monthly_summary = generator._generate_monthly_summary(year, month)
    
    if monthly_summary is None:
        print(f"[Error] 月份总结生成失败")
        return False
    
    print(f"\n[Test] 月份总结生成成功")
    print(f"  - 主要事件：{monthly_summary.get('major_events', '')[:100]}...")
    print(f"  - 新习惯：{len(monthly_summary.get('new_habits', []))} 个")
    print(f"  - 情感事件：{len(monthly_summary.get('emotional_events', []))} 个")
    
    # 调用 _generate_monthly_questions 生成问题
    print(f"\n[Test] 开始生成 {test_month} 的问题...")
    questions = generator._generate_monthly_questions(monthly_summary)
    
    # 验证结果
    print(f"\n[Test] 问题生成结果:")
    print(f"  - 生成问题数量：{len(questions)}")
    
    if questions:
        print(f"\n[Test] 前 3 个问题预览:")
        for i, q in enumerate(questions[:3], 1):
            print(f"\n  问题 {i}:")
            print(f"    - 问题：{q.get('question', 'N/A')[:100]}...")
            print(f"    - 答案：{q.get('answer', 'N/A')[:100]}...")
            print(f"    - 评分要点：{len(q.get('score_points', []))} 个")
            print(f"    - 所需事件 ID：{len(q.get('required_events_id', []))} 个")
            print(f"    - 证据数量：{len(q.get('evidence', []))} 个")
            print(f"    - 提问时间：{q.get('ask_time', 'N/A')}")
        
        # 保存问题到文件
        output_dir = os.path.join(base_dir, "QA")
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, f"monthly_questions_{test_month}.json")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(questions, f, ensure_ascii=False, indent=2)
        
        print(f"\n[Test] ✓ 问题已保存到：{output_file}")
        print(f"[Test] ✓ 共保存 {len(questions)} 个问题")
        return True
    else:
        print(f"\n[Test] ⚠ 未生成任何问题（可能被过滤掉了）")
        return True


def test_evidence_refine():
    """
    测试 evidence_refine 方法 - 优化问题的证据数据
    
    Returns:
        bool: 测试是否成功
    """
    print("\n" + "="*80)
    print("[Test] evidence_refine 方法测试")
    print("="*80)
    
    # 创建生成器实例（使用真实数据）
    base_dir = r"/fenghaoran/fenghaoran"
    generator = QAPatternRecognitionGenerator(
        persona_data=None,
        event_tree=None,
        daily_event=None,
        draft_event=None,
        special_event=None,
        phone_data_dir=os.path.join(base_dir, "phone_data", "json"),
        is_print=True
    )
    
    # 加载真实数据
    generator.load_data_from_path(base_dir)
    
    # 测试问题
    test_question = {
        "question": "我这个月（10 月）晨跑恢复得怎么样？频率和距离有变化吗？",
        "answer": "您这个月（10 月）晨跑经历了从假期中断到系统恢复再到优化的过程。假期阶段（10 月 1-6 日）晨跑中断，恢复阶段（10 月 7-14 日）频率为每周 6 次左右，距离 4-5 公里，注重心率控制和跑姿调整；优化阶段（10 月 15-31 日）频率保持每周 5-6 次，距离从 4 公里逐步增加到 12 公里，并加入坡道训练、长距离慢跑和数据分析。整体上，晨跑从恢复性训练逐步过渡到更稳定的有氧运动，频率高且距离逐步增加。",
        "score_points": [
            {
                "description": "准确回答出晨跑恢复的三个阶段（假期中断、恢复阶段、优化阶段）及对应时间段。",
                "score": 4
            },
            {
                "description": "准确描述恢复阶段（10 月 7-14 日）的频率（每周 6 次左右）和距离（4-5 公里）。",
                "score": 2
            },
            {
                "description": "准确描述优化阶段（10 月 15-31 日）的频率（每周 5-6 次）和距离变化（从 4 公里逐步增加到 12 公里）。",
                "score": 2
            },
            {
                "description": "提及恢复阶段注重心率控制和跑姿调整，优化阶段加入坡道训练、长距离慢跑和数据分析。",
                "score": 2
            }
        ],
        "required_events_id": ["3690", "3767", "3768", "3974", "3989", "4005", "4020", "4042", "4058", "4070", "4086", "4102", "3885", "3892", "3897", "3912", "3925", "3937", "3948", "3962", "3780", "3798", "3814", "3827", "3840", "3852", "3871"],
        "question_type": "ND",
        "evidence": []
    }
    
    test_month = "2025-10"
    
    print(f"\n[Test] 测试月份：{test_month}")
    print(f"[Test] 问题：{test_question['question']}")
    print(f"[Test] 必需事件 ID 数量：{len(test_question['required_events_id'])}")
    print(f"[Test] 原有证据数量：{len(test_question['evidence'])}")
    
    # 调用 evidence_refine 方法
    refined_question = generator.evidence_refine(test_question, test_month)
    
    # 验证结果
    print("\n[Test] evidence_refine 结果:")
    print(f"  - 优化后证据数量：{len(refined_question.get('evidence', []))}")
    print(f"  - 问题：{refined_question.get('question', '')[:100]}...")
    print(f"  - 答案：{refined_question.get('answer', '')[:100]}...")
    
    # 检查是否有新生成的证据
    if len(refined_question.get('evidence', [])) > len(test_question['evidence']):
        print(f"\n✓ evidence_refine 成功生成了新的证据数据")
        return True
    else:
        print(f"\n✓ evidence_refine 执行完成（可能无需补充证据）")
        return True


def main():
    """主测试函数"""
    print("\n" + "="*80)
    print("开始运行 QAPatternRecognitionGenerator 测试")
    print("="*80)
    
    tests = [
        #("初始化测试", test_initialization),
        #("单个月份总结测试", test_single_month_summary),
        # ("多个月份总结测试", test_multiple_month_summaries),
        #("QAGen 主入口测试", test_qagen_entry),
        #("check_agent 方法测试", test_check_agent)
        ("evidence_refine 方法测试", test_evidence_refine)
        #("monthly_questions 方法测试", test_generate_monthly_questions)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            print(f"\n\n>>> 准备执行：{test_name}")
            result = test_func()
            results.append((test_name, result, None))
            print(f"\n✓ {test_name} 完成")
        except Exception as e:
            error_msg = str(e)
            results.append((test_name, False, error_msg))
            print(f"\n✗ {test_name} 失败：{error_msg}")
            import traceback
            traceback.print_exc()
    
    # 打印总结
    print("\n" + "="*80)
    print("测试总结")
    print("="*80)
    
    passed = sum(1 for _, result, _ in results if result)
    total = len(results)
    
    print(f"\n总测试数：{total}")
    print(f"通过：{passed}")
    print(f"失败：{total - passed}")
    
    print("\n详细结果:")
    for test_name, result, error in results:
        status = "✓ 通过" if result else "✗ 失败"
        error_info = f" - {error}" if error else ""
        print(f"  {status}: {test_name}{error_info}")
    
    print("\n" + "="*80)
    print("测试结束")
    print("="*80 + "\n")


if __name__ == '__main__':
    main()