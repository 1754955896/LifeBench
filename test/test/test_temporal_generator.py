# -*- coding: utf-8 -*-
"""
时序 QA 生成器测试脚本 - 数据加载和总结生成测试
"""

import json
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from event.qa_generator.qa_temporal_generator import QATemporalGenerator


def load_test_data():
    """从 fenghaoran 目录加载测试数据"""
    test_data_dir = r"/fenghaoran/fenghaoran"
    
    # 加载 persona
    persona_path = os.path.join(test_data_dir, 'persona.json')
    if not os.path.exists(persona_path):
        print(f"错误：persona 文件不存在：{persona_path}")
        return None, None, None
    
    with open(persona_path, 'r', encoding='utf-8') as f:
        persona_data = json.load(f)
    
    # 加载 daily_event
    daily_event_path = os.path.join(test_data_dir, 'daily_event.json')
    if not os.path.exists(daily_event_path):
        print(f"错误：daily_event 文件不存在：{daily_event_path}")
        return None, None, None
    
    with open(daily_event_path, 'r', encoding='utf-8') as f:
        daily_event = json.load(f)
    
    # 加载 draft_event (daily_draft.json)
    draft_event_path = os.path.join(test_data_dir, 'daily_draft.json')
    if not os.path.exists(draft_event_path):
        print(f"错误：draft_event 文件不存在：{draft_event_path}")
        return None, None, None
    
    with open(draft_event_path, 'r', encoding='utf-8') as f:
        draft_event = json.load(f)
    
    return persona_data, daily_event, draft_event


def test_time_questions_generation():
    """测试时序问题生成（包括排序、时间差、持续时长、次数统计）"""
    print("\n" + "="*80)
    print("开始测试时序问题生成")
    print("="*80)
    
    # Step 1: 加载测试数据
    print("\n[Step 1] 加载测试数据...")
    persona_data, daily_event, draft_event = load_test_data()
    
    if not all([persona_data, daily_event, draft_event]):
        print("❌ 数据加载失败")
        return False
    
    print(f"✅ 数据加载成功")
    
    # Step 2: 初始化生成器
    print("\n[Step 2] 初始化时序 QA 生成器...")
    generator = QATemporalGenerator(
        persona_data=persona_data,
        daily_event=daily_event,
        draft_event=draft_event,
        phone_data_dir=os.path.join(r"/fenghaoran/fenghaoran", "phone_data"),
        is_print=True
    )
    print("✅ 生成器初始化完成")
    
    # Step 3: 从文件读取全年总结数据（节约测试成本）
    print("\n[Step 3] 从文件读取全年总结数据...")
    yearly_summary_path = os.path.join(r"/fenghaoran/fenghaoran", "test_output", "test_yearly_summaries_and_groups.json")
    
    if not os.path.exists(yearly_summary_path):
        print(f"⚠️  文件不存在：{yearly_summary_path}")
        print("   将重新生成全年总结...")
        yearly_summaries, event_groups = generator._generate_yearly_summaries(2025)
        
        if not yearly_summaries:
            print("❌ 全年总结生成失败")
            return False
    else:
        print(f"✅ 找到已有数据文件：{yearly_summary_path}")
        with open(yearly_summary_path, 'r', encoding='utf-8') as f:
            yearly_data = json.load(f)
        
        yearly_summaries = yearly_data.get('yearly_summaries', [])
        event_groups = yearly_data.get('event_groups', {})
        
        if not yearly_summaries:
            print("❌ 文件中没有有效的全年总结数据")
            return False
    
    print(f"✅ 全年总结数据加载成功，共 {len(yearly_summaries)} 个月")
    
    # Step 4: 测试时序问题生成（包含四类问题）
    print("\n[Step 4] 测试时序问题生成（排序、时间差、持续时长、次数统计）...")
    all_questions = generator._generate_temporal_sequence_questions(yearly_summaries, 2025, event_groups)
    
    if not all_questions:
        print("⚠️  未生成任何时序问题")
        return True  # 不算失败，只是没有生成问题
    
    print(f"\n✅ 成功生成 {len(all_questions)} 个时序问题")
    
    # Step 5: 统计各类问题数量
    print("\n[Step 5] 统计各类问题数量...")
    type_counts = {}
    for q in all_questions:
        qtype = q.get('question_type', 'unknown')
        type_counts[qtype] = type_counts.get(qtype, 0) + 1
    
    print(f"问题类型分布：")
    for qtype, count in sorted(type_counts.items()):
        print(f"  - {qtype}: {count} 个")
    
    # Step 6: 显示生成的问题详情（每类显示前2个）
    print("\n[Step 6] 显示生成的问题详情（每类前2个）...")
    displayed_types = set()
    for i, question in enumerate(all_questions, 1):
        qtype = question.get('question_type', 'unknown')
        
        # 每类只显示前2个
        if qtype not in displayed_types:
            displayed_types.add(qtype)
            display_count = 0
        
        # 检查该类是否已经显示了2个
        type_displayed_count = sum(1 for q in all_questions[:i] if q.get('question_type') == qtype)
        if type_displayed_count > 2:
            continue
        
        print(f"\n{'-'*80}")
        print(f"问题 {i} [{qtype}]:")
        print(f"  问题: {question.get('question', '')[:150]}...")
        print(f"  答案: {question.get('answer', '')[:150]}...")
        print(f"  提问时间: {question.get('ask_time', 'N/A')}")
        
        # 根据问题类型显示特定字段
        if qtype == 'temporal_sorting':
            if 'correct_order' in question:
                print(f"  正确顺序: {question['correct_order']}")
            print(f"  使用事件数: {len(question.get('events_used', []))}")
        elif qtype == 'temporal_time_diff':
            if 'time_diff_days' in question:
                print(f"  时间差: {question['time_diff_days']} 天")
            if 'reasoning_description' in question:
                print(f"  推理说明: {question['reasoning_description']}")
        elif qtype == 'temporal_duration':
            if 'duration_days' in question:
                print(f"  持续天数: {question['duration_days']}")
            if 'actual_start_date' in question and 'actual_end_date' in question:
                print(f"  实际日期: {question['actual_start_date']} 至 {question['actual_end_date']}")
        elif qtype == 'frequency_count':
            if 'group_name' in question:
                print(f"  事件组: {question['group_name']}")
            if 'question_type_detail' in question:
                print(f"  详细类型: {question['question_type_detail']}")
    
    # Step 7: 保存测试结果
    print("\n[Step 7] 保存测试结果...")
    output_dir = os.path.join(r"/fenghaoran/fenghaoran", "test_output")
    os.makedirs(output_dir, exist_ok=True)
    
    temporal_output_path = os.path.join(output_dir, "test_temporal_questions.json")
    with open(temporal_output_path, 'w', encoding='utf-8') as f:
        json.dump(all_questions, f, ensure_ascii=False, indent=2)
    print(f"✅ 时序问题已保存到：{temporal_output_path}")
    
    # 统计信息
    print(f"\n统计信息：")
    print(f"  - 总问题数: {len(all_questions)}")
    print(f"  - 问题类型分布: {type_counts}")
    
    print("\n" + "="*80)
    print("✅ 时序问题生成测试成功完成！")
    print("="*80)
    return True


def test_time_difference_questions():
    """测试时间差计算问题生成"""
    print("\n" + "="*80)
    print("开始测试时间差计算问题生成")
    print("="*80)
    
    # Step 1: 加载测试数据
    print("\n[Step 1] 加载测试数据...")
    persona_data, daily_event, draft_event = load_test_data()
    
    if not all([persona_data, daily_event, draft_event]):
        print("❌ 数据加载失败")
        return False
    
    print(f"✅ 数据加载成功")
    
    # Step 2: 初始化生成器
    print("\n[Step 2] 初始化时序 QA 生成器...")
    generator = QATemporalGenerator(
        persona_data=persona_data,
        daily_event=daily_event,
        draft_event=draft_event,
        phone_data_dir=os.path.join(r"/fenghaoran/fenghaoran", "phone_data"),
        is_print=True
    )
    print("✅ 生成器初始化完成")
    
    # Step 3: 从文件读取全年总结数据（节约测试成本）
    print("\n[Step 3] 从文件读取全年总结数据...")
    yearly_summary_path = os.path.join(r"/fenghaoran/fenghaoran", "test_output", "test_yearly_summaries_and_groups.json")
    
    if not os.path.exists(yearly_summary_path):
        print(f"⚠️  文件不存在：{yearly_summary_path}")
        print("   将重新生成全年总结...")
        yearly_summaries, event_groups = generator._generate_yearly_summaries(2025)
        
        if not yearly_summaries:
            print("❌ 全年总结生成失败")
            return False
    else:
        print(f"✅ 找到已有数据文件：{yearly_summary_path}")
        with open(yearly_summary_path, 'r', encoding='utf-8') as f:
            yearly_data = json.load(f)
        
        yearly_summaries = yearly_data.get('yearly_summaries', [])
        event_groups = yearly_data.get('event_groups', {})
        
        if not yearly_summaries:
            print("❌ 文件中没有有效的全年总结数据")
            return False
    
    print(f"✅ 全年总结数据加载成功，共 {len(yearly_summaries)} 个月")
    
    # Step 4: 收集所有事件
    print("\n[Step 4] 收集全年所有事件...")
    all_events = []
    for summary in yearly_summaries:
        month = summary.get('month', '')
        important_events = summary.get('important_events', [])
        for event in important_events:
            all_events.append({
                'date': event.get('date', ''),
                'description': event.get('event_description', ''),
                'month': month
            })
    
    print(f"✅ 共收集 {len(all_events)} 个事件")
    
    if len(all_events) < 2:
        print("⚠️  事件数量不足，无法生成时间差问题")
        return True
    
    # Step 5: 测试时间差问题生成
    print("\n[Step 5] 测试时间差问题生成...")
    time_diff_questions = generator._generate_time_difference_questions(all_events, 2025)
    
    if not time_diff_questions:
        print("⚠️  未生成任何时间差问题")
        return True  # 不算失败，只是没有生成问题
    
    print(f"\n✅ 成功生成 {len(time_diff_questions)} 个时间差计算问题")
    
    # Step 6: 显示生成的问题详情
    print("\n[Step 6] 显示生成的问题详情...")
    for i, question in enumerate(time_diff_questions, 1):
        print(f"\n{'-'*80}")
        print(f"问题 {i}:")
        print(f"  问题: {question.get('question', '')}")
        print(f"  答案: {question.get('answer', '')}")
        print(f"  提问时间: {question.get('ask_time', 'N/A')}")
        
        # 显示时间差信息
        if 'time_diff_days' in question:
            print(f"  时间差: {question['time_diff_days']} 天")
        if 'reasoning_description' in question:
            print(f"  推理说明: {question['reasoning_description']}")
        if 'event1_date' in question and 'event2_date' in question:
            print(f"  事件1日期: {question['event1_date']}")
            print(f"  事件2日期: {question['event2_date']}")
        if 'required_events_id' in question:
            print(f"  所需事件ID: {question['required_events_id']}")
    
    # Step 7: 保存测试结果
    print("\n[Step 7] 保存测试结果...")
    output_dir = os.path.join(r"/fenghaoran/fenghaoran", "test_output")
    os.makedirs(output_dir, exist_ok=True)
    
    time_diff_output_path = os.path.join(output_dir, "test_time_difference_questions.json")
    with open(time_diff_output_path, 'w', encoding='utf-8') as f:
        json.dump(time_diff_questions, f, ensure_ascii=False, indent=2)
    print(f"✅ 时间差问题已保存到：{time_diff_output_path}")
    
    # 统计信息
    print(f"\n统计信息：")
    print(f"  - 总问题数: {len(time_diff_questions)}")
    
    print("\n" + "="*80)
    print("✅ 时间差计算问题生成测试成功完成！")
    print("="*80)
    return True


def test_duration_analysis_questions():
    """测试持续时长分析问题生成"""
    print("\n" + "="*80)
    print("开始测试持续时长分析问题生成")
    print("="*80)
    
    # Step 1: 加载测试数据
    print("\n[Step 1] 加载测试数据...")
    persona_data, daily_event, draft_event = load_test_data()
    
    if not all([persona_data, daily_event, draft_event]):
        print("❌ 数据加载失败")
        return False
    
    print(f"✅ 数据加载成功")
    
    # Step 2: 初始化生成器
    print("\n[Step 2] 初始化时序 QA 生成器...")
    generator = QATemporalGenerator(
        persona_data=persona_data,
        daily_event=daily_event,
        draft_event=draft_event,
        phone_data_dir=os.path.join(r"/fenghaoran/fenghaoran", "phone_data"),
        is_print=True
    )
    print("✅ 生成器初始化完成")
    
    # Step 3: 从文件读取全年总结数据（节约测试成本）
    print("\n[Step 3] 从文件读取全年总结数据...")
    yearly_summary_path = os.path.join(r"/fenghaoran/fenghaoran", "test_output", "test_yearly_summaries_and_groups.json")
    
    if not os.path.exists(yearly_summary_path):
        print(f"⚠️  文件不存在：{yearly_summary_path}")
        print("   将重新生成全年总结...")
        yearly_summaries, event_groups = generator._generate_yearly_summaries(2025)
        
        if not yearly_summaries:
            print("❌ 全年总结生成失败")
            return False
    else:
        print(f"✅ 找到已有数据文件：{yearly_summary_path}")
        with open(yearly_summary_path, 'r', encoding='utf-8') as f:
            yearly_data = json.load(f)
        
        yearly_summaries = yearly_data.get('yearly_summaries', [])
        event_groups = yearly_data.get('event_groups', {})
        
        if not yearly_summaries:
            print("❌ 文件中没有有效的全年总结数据")
            return False
    
    print(f"✅ 全年总结数据加载成功，共 {len(yearly_summaries)} 个月")
    
    # Step 4: 收集所有事件
    print("\n[Step 4] 收集全年所有事件...")
    all_events = []
    for summary in yearly_summaries:
        month = summary.get('month', '')
        important_events = summary.get('important_events', [])
        for event in important_events:
            all_events.append({
                'date': event.get('date', ''),
                'description': event.get('event_description', ''),
                'month': month
            })
    
    print(f"✅ 共收集 {len(all_events)} 个事件")
    
    # Step 5: 测试持续时长分析问题生成
    print("\n[Step 5] 测试持续时长分析问题生成...")
    duration_questions = generator._generate_duration_analysis_questions(all_events, 2025)
    
    if not duration_questions:
        print("⚠️  未生成任何持续时长分析问题")
        return True  # 不算失败，只是没有生成问题
    
    print(f"\n✅ 成功生成 {len(duration_questions)} 个持续时长分析问题")
    
    # Step 6: 显示生成的问题详情
    print("\n[Step 6] 显示生成的问题详情...")
    for i, question in enumerate(duration_questions, 1):
        print(f"\n{'-'*80}")
        print(f"问题 {i}:")
        print(f"  问题: {question.get('question', '')}")
        print(f"  答案: {question.get('answer', '')}")
        print(f"  提问时间: {question.get('ask_time', 'N/A')}")
        
        # 显示评分点
        if 'score_points' in question:
            print(f"  评分点:")
            for sp in question['score_points']:
                print(f"    - {sp.get('description', '')}: {sp.get('score', 0)}分")
        
        # 显示所需事件ID
        if 'required_events_id' in question:
            print(f"  所需事件ID: {question['required_events_id']}")
    
    # Step 7: 保存测试结果
    print("\n[Step 7] 保存测试结果...")
    output_dir = os.path.join(r"/fenghaoran/fenghaoran", "test_output")
    os.makedirs(output_dir, exist_ok=True)
    
    duration_output_path = os.path.join(output_dir, "test_duration_analysis_questions.json")
    with open(duration_output_path, 'w', encoding='utf-8') as f:
        json.dump(duration_questions, f, ensure_ascii=False, indent=2)
    print(f"✅ 持续时长分析问题已保存到：{duration_output_path}")
    
    # 统计信息
    print(f"\n统计信息：")
    print(f"  - 总问题数: {len(duration_questions)}")
    
    print("\n" + "="*80)
    print("✅ 持续时长分析问题生成测试成功完成！")
    print("="*80)
    return True


def test_frequency_count_questions():
    """测试次数统计问题生成"""
    print("\n" + "="*80)
    print("开始测试次数统计问题生成")
    print("="*80)
    
    # Step 1: 加载测试数据
    print("\n[Step 1] 加载测试数据...")
    persona_data, daily_event, draft_event = load_test_data()
    
    if not all([persona_data, daily_event, draft_event]):
        print("❌ 数据加载失败")
        return False
    
    print(f"✅ 数据加载成功")
    
    # Step 2: 初始化生成器
    print("\n[Step 2] 初始化时序 QA 生成器...")
    generator = QATemporalGenerator(
        persona_data=persona_data,
        daily_event=daily_event,
        draft_event=draft_event,
        phone_data_dir=os.path.join(r"/fenghaoran/fenghaoran", "phone_data"),
        is_print=True
    )
    print("✅ 生成器初始化完成")
    
    # Step 3: 从文件读取全年总结数据和事件分组（节约测试成本）
    print("\n[Step 3] 从文件读取全年总结数据和事件分组...")
    yearly_summary_path = os.path.join(r"/fenghaoran/fenghaoran", "test_output", "test_yearly_summaries_and_groups.json")
    
    if not os.path.exists(yearly_summary_path):
        print(f"⚠️  文件不存在：{yearly_summary_path}")
        print("   将重新生成全年总结和事件分组...")
        yearly_summaries, event_groups = generator._generate_yearly_summaries(2025)
        
        if not yearly_summaries:
            print("❌ 全年总结生成失败")
            return False
    else:
        print(f"✅ 找到已有数据文件：{yearly_summary_path}")
        with open(yearly_summary_path, 'r', encoding='utf-8') as f:
            yearly_data = json.load(f)
        
        yearly_summaries = yearly_data.get('yearly_summaries', [])
        event_groups = yearly_data.get('event_groups', {})
        
        if not yearly_summaries:
            print("❌ 文件中没有有效的全年总结数据")
            return False
    
    print(f"✅ 全年总结数据加载成功，共 {len(yearly_summaries)} 个月")
    
    # 显示事件分组信息
    if event_groups and event_groups.get('event_groups'):
        groups = event_groups['event_groups']
        print(f"✅ 事件分组数据加载成功，共 {len(groups)} 个事件组")
        print(f"\n事件组列表：")
        for i, group in enumerate(groups[:10], 1):  # 只显示前10个
            group_name = group.get('group_name', 'N/A')
            events = group.get('events', [])
            print(f"  {i}. {group_name}: {len(events)} 个事件")
    else:
        print("⚠️  没有事件分组数据，无法生成次数统计问题")
        return True
    
    # Step 4: 测试次数统计问题生成
    print("\n[Step 4] 测试次数统计问题生成...")
    frequency_questions = generator._generate_frequency_count_questions(event_groups, 2025)
    
    if not frequency_questions:
        print("⚠️  未生成任何次数统计问题")
        return True  # 不算失败，只是没有生成问题
    
    print(f"\n✅ 成功生成 {len(frequency_questions)} 个次数统计问题")
    
    # Step 4.5: 对每个问题调用 evidence_refine 补充手机操作数据
    print("\n[Step 4.5] 对生成的问题调用 evidence_refine 补充手机操作数据...")
    refined_questions = []
    for i, question in enumerate(frequency_questions, 1):
        print(f"\n处理第 {i}/{len(frequency_questions)} 个问题...")
        refined_question = generator.evidence_refine(question)
        refined_questions.append(refined_question)
    
    frequency_questions = refined_questions
    print(f"\n✅ 完成 {len(frequency_questions)} 个问题的证据优化")
    
    # Step 5: 显示生成的问题详情
    print("\n[Step 5] 显示生成的问题详情...")
    for i, question in enumerate(frequency_questions, 1):
        print(f"\n{'-'*80}")
        print(f"问题 {i}:")
        print(f"  问题: {question.get('question', '')}")
        print(f"  答案: {question.get('answer', '')}")
        
        # 显示评分点
        if 'score_points' in question:
            print(f"  评分点:")
            for sp in question['score_points']:
                print(f"    - {sp.get('description', '')}: {sp.get('score', 0)}分")
        
        # 显示所需事件ID
        if 'required_events_id' in question:
            print(f"  所需事件ID: {question['required_events_id']}")
    
    # Step 6: 保存测试结果
    print("\n[Step 6] 保存测试结果...")
    output_dir = os.path.join(r"/fenghaoran/fenghaoran", "test_output")
    os.makedirs(output_dir, exist_ok=True)
    
    frequency_output_path = os.path.join(output_dir, "test_frequency_count_questions.json")
    with open(frequency_output_path, 'w', encoding='utf-8') as f:
        json.dump(frequency_questions, f, ensure_ascii=False, indent=2)
    print(f"✅ 次数统计问题已保存到：{frequency_output_path}")
    
    # 统计信息
    print(f"\n统计信息：")
    print(f"  - 总问题数: {len(frequency_questions)}")
    
    # 统计问题类型分布
    type_detail_counts = {}
    for q in frequency_questions:
        detail_type = q.get('question_type_detail', 'unknown')
        type_detail_counts[detail_type] = type_detail_counts.get(detail_type, 0) + 1
    
    print(f"  - 问题类型分布:")
    for detail_type, count in sorted(type_detail_counts.items()):
        print(f"    {detail_type}: {count} 个")
    
    print("\n" + "="*80)
    print("✅ 次数统计问题生成测试成功完成！")
    print("="*80)
    return True


def test_data_loading_and_summary():
    """测试数据加载和月度总结生成"""
    print("="*80)
    print("开始测试数据加载和总结生成")
    print("="*80)
    
    # Step 1: 加载测试数据
    print("\n[Step 1] 加载测试数据...")
    persona_data, daily_event, draft_event = load_test_data()
    
    if not all([persona_data, daily_event, draft_event]):
        print("❌ 数据加载失败")
        return False
    
    print(f"✅ 数据加载成功")
    print(f"  - Persona 数据：{len(str(persona_data))} 字符")
    print(f"  - Daily Event：{len(daily_event) if isinstance(daily_event, list) else '非列表'} 条记录")
    print(f"  - Draft Event：{len(draft_event) if isinstance(draft_event, dict) else '非字典'} 个月份")
    
    # 显示 draft_event 的月份信息
    if isinstance(draft_event, dict):
        months = sorted(draft_event.keys())
        print(f"  - 月份范围：{months[0] if months else '无'} 至 {months[-1] if months else '无'}")
        print(f"  - 各月份事件数量：")
        for month in months[:5]:  # 只显示前5个月
            events = draft_event[month]
            count = len(events) if isinstance(events, list) else 0
            print(f"    {month}: {count} 个事件")
        if len(months) > 5:
            print(f"    ... 还有 {len(months) - 5} 个月份")
    
    # Step 2: 初始化生成器
    print("\n[Step 2] 初始化时序 QA 生成器...")
    generator = QATemporalGenerator(
        persona_data=persona_data,
        daily_event=daily_event,
        draft_event=draft_event,
        phone_data_dir=os.path.join(r"../../fenghaoran/fenghaoran", "phone_data"),
        is_print=True
    )
    print("✅ 生成器初始化完成")
    
    # Step 3: 测试全年总结生成和事件分组
    print("\n[Step 3] 测试全年总结生成和事件分组...")
    yearly_summaries, event_groups = generator._generate_yearly_summaries(2025)
    
    if not yearly_summaries:
        print("❌ 全年总结生成失败")
        return False
    
    print(f"✅ 全年总结生成成功")
    print(f"  - 生成了 {len(yearly_summaries)} 个月的总结")
    
    # 显示事件分组结果
    if event_groups and 'event_groups' in event_groups:
        groups = event_groups['event_groups']
        print(f"  - 识别了 {len(groups)} 个事件组")
        
        # 显示前5个事件组
        if groups:
            print(f"  - 事件组示例（前5个）：")
            for i, group in enumerate(groups[:5], 1):
                group_name = group.get('group_name', 'N/A')
                event_count = group.get('event_count', 0)
                time_dist = group.get('time_distribution', 'N/A')
                print(f"    {i}. {group_name}: {event_count} 个事件")
                print(f"       时间分布: {time_dist[:60]}...")
    
    # Step 4: 保存测试结果
    print("\n[Step 4] 保存测试结果...")
    output_dir = os.path.join(r"/fenghaoran/fenghaoran", "test_output")
    os.makedirs(output_dir, exist_ok=True)
    
    # 保存全年总结和事件分组
    yearly_output_path = os.path.join(output_dir, "test_yearly_summaries_and_groups.json")
    yearly_result = {
        'year': 2025,
        'yearly_summaries': yearly_summaries,
        'event_groups': event_groups
    }
    with open(yearly_output_path, 'w', encoding='utf-8') as f:
        json.dump(yearly_result, f, ensure_ascii=False, indent=2)
    print(f"✅ 全年总结和事件分组已保存到：{yearly_output_path}")
    
    print("\n" + "="*80)
    print("✅ 测试成功完成！")
    print("="*80)
    return True


if __name__ == "__main__":
    try:
        success = test_frequency_count_questions()
        if not success:
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试失败：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

