"""
测试 QASingleGenerator 类的功能
包括对 Select Agent、Search Agent、Evaluation Agent、Design Agent 的独立测试
"""

import json
import os
import sys
from datetime import datetime

# 添加项目根目录到 Python 路径
project_root = r"D:\pyCharmProjects\pythonProject4"
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from event.qa_generator.qa_single_generator import QASingleGenerator


def test_initialization():
    """测试 QASingleGenerator 的初始化"""
    print("\n" + "="*80)
    print("测试 1: QASingleGenerator 初始化")
    print("="*80)
    
    # 使用真实测试数据路径
    data_path = r"/fenghaoran/fenghaoran"
    
    if not os.path.exists(data_path):
        print(f"❌ 数据路径不存在：{data_path}")
        return False
    
    # 测试 is_print=False 的情况
    generator = QASingleGenerator(
        phone_data_dir=os.path.join(data_path, "phone_data"),
        is_print=False  # 不打印 LLM 输出
    )
    generator.load_data_from_path(data_path)
    
    print(f"✓ 生成器初始化成功 (is_print=False)")
    print(f"  - Persona 数据：{len(generator.persona_data)} 条")
    print(f"  - Event Tree 数据：{len(generator.event_tree)} 条")
    print(f"  - Daily Event 数据：{len(generator.daily_event)} 条")
    print(f"  - Draft Event 数据：{len(generator.draft_event)} 个月份")
    print(f"  - Phone Data 类型：{list(generator.phonedata.keys())}")
    print(f"  - 打印开关：{generator.is_print}")
    
    return True


def test_select_agent():
    """测试 Select Agent 的功能"""
    print("\n" + "="*80)
    print("测试 2: Select Agent")
    print("="*80)
    
    data_path = r"/fenghaoran/fenghaoran"
    # 使用 is_print=True 来查看 LLM 输出
    generator = QASingleGenerator(is_print=True)
    generator.load_data_from_path(data_path)
    
    # 测试 6 月份的 Select Agent
    year = 2025
    month = 6
    
    print(f"\n测试月份：{year}-{month:02d}")
    result = generator.select_agent(year, month)
    
    if not result:
        print("❌ Select Agent 未返回结果")
        return False
    
    print(f"✓ Select Agent 返回成功")
    print(f"  - 时间段数量：{len(result)}")
    
    for i, item in enumerate(result, 1):
        print(f"\n  时间段 {i}:")
        print(f"    - 日期范围：{item['dates'][0]} 到 {item['dates'][-1]}")
        print(f"    - 目标事件：{item.get('target_event', {})}")
        print(f"    - 问题草稿：{item.get('question_draft', '')[:100]}...")
        print(f"    - 策略叙述：{item.get('strategy_narrative', '')[:100]}...")
    
    return True


def test_search_agent_mode1():
    """测试 Search Agent 的模式 1（基于 atomic_id 搜索 event_tree）"""
    print("\n" + "="*80)
    print("测试 3: Search Agent - 模式 1 (基于 atomic_id)")
    print("="*80)
    
    data_path = r"/fenghaoran/fenghaoran"
    generator = QASingleGenerator()
    generator.load_data_from_path(data_path)
    
    # 构造一个测试场景
    dates = ["2025-03-15", "2025-03-16", "2025-03-17"]
    target_event = {
        "event_id": "evt_001",
        "event_name": "医学研讨会",
        "event_type": "会议"
    }
    question_draft = "冯浩然的医学研讨会是什么时候？"
    
    print(f"\n测试参数:")
    print(f"  - 日期范围：{dates}")
    print(f"  - 目标事件：{target_event['event_name']}")
    print(f"  - 问题草稿：{question_draft}")
    
    result = generator.search_agent(dates, target_event, question_draft)
    
    if not result:
        print("❌ Search Agent 未返回结果")
        return False
    
    print(f"✓ Search Agent 返回成功")
    print(f"  - 结果类型：{list(result.keys())}")
    
    if 'events' in result:
        print(f"  - 事件数量：{len(result['events'])}")
    
    return True


def test_search_agent_mode2():
    """测试 Search Agent 的模式 2（基于月份的 draft_event 分析）"""
    print("\n" + "="*80)
    print("测试 4: Search Agent - 模式 2 (基于月份)")
    print("="*80)
    
    data_path = r"/fenghaoran/fenghaoran"
    generator = QASingleGenerator()
    generator.load_data_from_path(data_path)
    
    # 构造一个测试场景
    dates = ["2025-03-15", "2025-03-16", "2025-03-17"]
    target_event = {
        "event_id": "evt_002",
        "event_name": "健身训练",
        "event_type": "健身"
    }
    question_draft = "冯浩然在 3 月中旬的健身活动有哪些？"
    
    print(f"\n测试参数:")
    print(f"  - 日期范围：{dates}")
    print(f"  - 目标事件：{target_event['event_name']}")
    print(f"  - 问题草稿：{question_draft}")
    
    result = generator.search_agent(dates, target_event, question_draft)
    
    if not result:
        print("❌ Search Agent 未返回结果")
        return False
    
    print(f"✓ Search Agent 返回成功")
    print(f"  - 结果类型：{list(result.keys())}")
    
    if 'month_analyses' in result:
        print(f"  - 分析的月份数：{result.get('total_months_analyzed', 0)}")
        if result['month_analyses']:
            print(f"  - 第一个分析月份：{result['month_analyses'][0].get('month', 'N/A')}")
    
    return True


def test_evaluation_agent():
    """测试 Evaluation Agent 的功能"""
    print("\n" + "="*80)
    print("测试 5: Evaluation Agent")
    print("="*80)
    
    data_path = r"/fenghaoran/fenghaoran"
    generator = QASingleGenerator()
    generator.load_data_from_path(data_path)
    
    # 构造一个测试问题
    question = {
        'question': '冯浩然在 2025 年 3 月参加了什么重要会议？',
        'strategy_narrative': '通过时间范围和事件类型来检索会议信息'
    }
    
    search_result = {
        'events': [
            {
                'event_id': 'evt_001',
                'event_name': '医学研讨会',
                'date': '2025-03-15'
            }
        ]
    }
    
    print(f"\n测试问题：{question['question']}")
    print(f"搜索到的事件数：{len(search_result['events'])}")
    
    result = generator.evaluation_agent(question, search_result)
    
    if not result:
        print("❌ Evaluation Agent 未返回结果")
        return False
    
    print(f"✓ Evaluation Agent 返回成功")
    print(f"  - 质量合格：{'是' if result['is_qualified'] else '否'}")
    print(f"  - 评分：{result.get('score', 0)}/10")
    print(f"  - 优点：{len(result.get('strengths', []))} 条")
    print(f"  - 不足：{len(result.get('weaknesses', []))} 条")
    print(f"  - 改进建议：{len(result.get('improvement_suggestions', []))} 条")
    
    return True


def test_design_agent():
    """测试 Design Agent 的功能"""
    print("\n" + "="*80)
    print("测试 6: Design Agent")
    print("="*80)
    
    data_path = r"/fenghaoran/fenghaoran"
    generator = QASingleGenerator()
    generator.load_data_from_path(data_path)
    
    # 构造一个测试问题和反馈
    question = {
        'question': '冯浩然在 2025 年 3 月参加了什么重要会议？',
        'strategy_narrative': '通过时间范围和事件类型来检索会议信息',
        'target_event': {
            'event_id': 'evt_001',
            'event_name': '医学研讨会',
            'event_type': '会议'
        },
        'evidence': []
    }
    
    feedback = """
    【搜索结果】
    {
        "events": [
            {"event_id": "evt_001", "event_name": "医学研讨会", "date": "2025-03-15"}
        ]
    }
    
    【评估反馈】
    - 评分：6/10
    - 质量合格：否
    - 优点：['问题清晰', '有明确的时间范围']
    - 不足：['难度较低', '缺乏挑战性']
    - 改进建议：['可以通过间接方式描述事件', '增加推理难度']
    """
    
    print(f"\n当前问题：{question['question']}")
    print(f"反馈摘要：评分 6/10，需要改进")
    
    new_question, should_continue = generator.design_agent(question, feedback)
    
    if not new_question:
        print("❌ Design Agent 未返回结果")
        return False
    
    print(f"✓ Design Agent 返回成功")
    print(f"  - 新问题：{new_question.get('question', '')[:100]}...")
    print(f"  - 预期答案：{new_question.get('answer', '')[:100]}...")
    print(f"  - 得分点数量：{len(new_question.get('score_points', []))}")
    print(f"  - Evidence 数量：{len(new_question.get('evidence', []))}")
    print(f"  - 是否需要继续迭代：{'是' if should_continue else '否'}")
    
    # 打印生成的手机操作数据
    if new_question.get('evidence'):
        print(f"\n  生成的 Evidence:")
        for ev in new_question['evidence'][:3]:  # 只显示前 3 个
            print(f"    - 类型：{ev.get('type')}, ID: {ev.get('id')}")
    
    return True


def test_phone_operation_generation():
    """测试手机操作生成功能"""
    print("\n" + "="*80)
    print("测试 7: 手机操作生成")
    print("="*80)
    
    data_path = r"/fenghaoran/fenghaoran"
    generator = QASingleGenerator()
    generator.load_data_from_path(data_path)
    
    # 记录初始数据量
    initial_counts = {k: len(v) for k, v in generator.phonedata.items()}
    print(f"\n初始数据量:")
    for op_type, count in initial_counts.items():
        print(f"  - {op_type}: {count} 条")
    
    # 测试删除操作
    to_delete = []
    if 'sms' in generator.phonedata and generator.phonedata['sms']:
        first_sms = generator.phonedata['sms'][0]
        to_delete.append({
            'type': 'sms',
            'phone_id': first_sms.get('phone_id', '')
        })
    
    if to_delete:
        print(f"\n测试删除操作：删除 {len(to_delete)} 条数据")
        generator._delete_phone_operations(to_delete)
        
        # 验证删除结果
        final_count = len(generator.phonedata.get('sms', []))
        print(f"  - 删除后 sms 数量：{final_count}")
    
    # 测试生成操作
    to_generate = [
        {
            'type': 'sms',
            'content_summary': '冯浩然与张医生讨论医学研讨会的时间和地点'
        },
        {
            'type': 'calendar',
            'content_summary': '2025 年 3 月 15 日参加医学研讨会，地点在医院会议室'
        }
    ]
    
    question = {
        'question': '测试问题',
        'target_event': {'event_id': 'test_001'}
    }
    
    print(f"\n测试生成操作：生成 {len(to_generate)} 条数据")
    generated_ops = generator._generate_planned_operations(to_generate, question)
    print(f"  - 实际生成数量：{len(generated_ops)}")
    
    # 验证生成结果
    final_counts = {k: len(v) for k, v in generator.phonedata.items()}
    print(f"\n最终数据量:")
    for op_type, count in final_counts.items():
        change = count - initial_counts.get(op_type, 0)
        print(f"  - {op_type}: {count} 条 ({change:+d})")
    
    return True


def test_full_pipeline():
    """测试完整的 Agentic 流程"""
    print("\n" + "="*80)
    print("测试 8: 完整 Agentic 流程")
    print("="*80)
    
    data_path = r"/fenghaoran/fenghaoran"
    generator = QASingleGenerator()
    generator.load_data_from_path(data_path)
    
    year = 2025
    month = 3
    
    print(f"\n测试月份：{year}-{month:02d}")
    print("开始执行完整流程...\n")
    
    # 调用 generate_monthly_qa
    monthly_qa = generator.generate_monthly_qa(year, month)
    
    if not monthly_qa:
        print("❌ 完整流程未生成任何问题")
        return False
    
    print(f"\n✓ 完整流程执行成功")
    print(f"  - 生成问题数量：{len(monthly_qa)}")
    
    if monthly_qa:
        first_qa = monthly_qa[0]
        print(f"\n  第一个问题示例:")
        print(f"    - 问题：{first_qa.get('question', '')[:100]}...")
        print(f"    - 答案：{first_qa.get('answer', '')[:100]}...")
        print(f"    - 问题类型：{first_qa.get('question_type', '')}")
        print(f"    - Evidence 数量：{len(first_qa.get('evidence', []))}")
        print(f"    - 提问时间：{first_qa.get('ask_time', '')}")
    
    return True


def main():
    """主测试函数"""
    print("\n" + "="*80)
    print("开始运行 QASingleGenerator 测试")
    print("="*80)
    
    tests = [
        # ("初始化测试", test_initialization),
        # ("Select Agent 测试", test_select_agent),
        # ("Search Agent 模式 1 测试", test_search_agent_mode1),
        # ("Search Agent 模式 2 测试", test_search_agent_mode2),
        # ("Evaluation Agent 测试", test_evaluation_agent),
        # ("Design Agent 测试", test_design_agent),
        # ("手机操作生成测试", test_phone_operation_generation),
        ("完整流程测试", test_full_pipeline)
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
