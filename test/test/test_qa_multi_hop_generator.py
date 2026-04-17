"""
多跳问题生成器测试脚本
直接调用关键方法并打印结果，人工观察
"""

import json
import os
import sys
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from event.qa_generator.qa_multi_hop_generator import QAMultiHopGenerator


def load_test_data():
    """加载测试数据"""
    base_dir = r'/fenghaoran/fenghaoran'
    
    # 加载 daily_event
    daily_event_path = os.path.join(base_dir, 'daily_event.json')
    with open(daily_event_path, 'r', encoding='utf-8') as f:
        daily_event = json.load(f)
    print(f"✓ 加载 daily_event: {len(daily_event)} 条记录")
    
    # 加载 event_tree
    event_tree_path = os.path.join(base_dir, 'event_tree.json')
    with open(event_tree_path, 'r', encoding='utf-8') as f:
        event_tree = json.load(f)
    print(f"✓ 加载 event_tree: {len(event_tree)} 条记录")
    
    # 加载 draft_event
    draft_event_path = os.path.join(base_dir, 'daily_draft.json')
    with open(draft_event_path, 'r', encoding='utf-8') as f:
        draft_event = json.load(f)
    print(f"✓ 加载 draft_event: {len(draft_event)} 个月份")
    
    # 加载 phonedata（从 phone_data 目录）
    phone_data_dir = os.path.join(base_dir, 'phone_data')
    phonedata = {}
    if os.path.exists(phone_data_dir):
        for filename in os.listdir(phone_data_dir):
            if filename.endswith('.json') and filename != 'fitness_health.json':
                filepath = os.path.join(phone_data_dir, filename)
                key = filename.replace('.json', '')
                with open(filepath, 'r', encoding='utf-8') as f:
                    phonedata[key] = json.load(f)
        print(f"✓ 加载 phonedata: {list(phonedata.keys())}")
    
    return daily_event, event_tree, draft_event, phonedata, phone_data_dir


def test_select_agent(generator, year, month):
    """测试 Select Agent"""
    print("\n" + "="*60)
    print("测试 1: Select Agent - 选择目标事件")
    print("="*60)
    
    results = generator.select_agent(year, month)
    
    if not results:
        print("✗ 未返回结果")
        return None
    
    result = results[0]
    print(f"\n日期范围: {result['dates']}")
    print(f"Daily events 数量: {len(result.get('daily_events_in_range', []))}")
    
    target_event = result.get('target_event', {})
    print(f"\n目标事件:")
    print(json.dumps(target_event, ensure_ascii=False, indent=2))
    
    analysis_text = result.get('analysis_text', '')
    print(f"\n分析文本 (前300字):")
    print(analysis_text[:300] + "..." if len(analysis_text) > 300 else analysis_text)
    
    return result


def test_search_agent_mode1(generator, target_event):
    """测试 Search Agent 模式 1: 基于 atomic_id"""
    print("\n" + "="*60)
    print("测试 2: Search Agent (模式 1) - 基于 atomic_id 搜索")
    print("="*60)
    
    atomic_id = target_event.get('atomic_id')
    if not atomic_id:
        print("⚠ 目标事件没有 atomic_id，跳过此测试")
        return None
    
    print(f"\n搜索 atomic_id: {atomic_id}")
    leaf_events = generator._search_by_atomic_id(atomic_id, target_event)
    
    print(f"\n找到 {len(leaf_events)} 个叶子节点事件:")
    for i, event in enumerate(leaf_events[:5], 1):  # 只显示前5个
        print(f"{i}. {event.get('name', '')} (ID: {event.get('atomic_id', '')})")
    
    if len(leaf_events) > 5:
        print(f"   ... 还有 {len(leaf_events) - 5} 个事件")
    
    return leaf_events


def test_search_agent_mode2(generator, dates, target_event):
    """测试 Search Agent 模式 2: 基于 draft_event"""
    print("\n" + "="*60)
    print("测试 3: Search Agent (模式 2) - 基于 draft_event 搜索")
    print("="*60)
    
    target_month = dates[0][:7]  # YYYY-MM
    print(f"\n搜索月份: {target_month}")
    
    events = generator._search_by_draft_event(dates, target_event)
    
    print(f"\n找到 {len(events)} 个事件:")
    for i, event in enumerate(events[:10], 1):  # 只显示前10个
        holiday = event.get('holiday', '')
        holiday_str = f" [{holiday}]" if holiday else ""
        print(f"{i}. {event.get('name', '')}{holiday_str}")
    
    if len(events) > 10:
        print(f"   ... 还有 {len(events) - 10} 个事件")
    
    return events


def test_extract_leaf_events(generator):
    """测试提取叶子节点"""
    print("\n" + "="*60)
    print("测试 4: 提取叶子节点")
    print("="*60)
    
    # 使用 event_tree 的前几个节点作为测试
    test_nodes = generator.event_tree[:3] if isinstance(generator.event_tree, list) else []
    
    if not test_nodes:
        print("⚠ 没有可用的测试数据")
        return []
    
    print(f"\n测试节点数: {len(test_nodes)}")
    
    leaf_events = generator._extract_leaf_events(test_nodes)
    
    print(f"\n提取到 {len(leaf_events)} 个叶子节点:")
    for i, event in enumerate(leaf_events[:10], 1):
        print(f"{i}. {event.get('name', '')} (ID: {event.get('atomic_id', '')})")
    
    if len(leaf_events) > 10:
        print(f"   ... 还有 {len(leaf_events) - 10} 个事件")
    
    return leaf_events


def test_inference_agent(generator, select_result, search_result):
    """测试 Inference Agent"""
    print("\n" + "="*60)
    print("测试 5: Inference Agent - 构建推理链条")
    print("="*60)
    
    target_event = select_result.get('target_event', {})
    daily_events = select_result.get('daily_events_in_range', [])
    
    print(f"\n目标事件: {target_event.get('name', '')}")
    print(f"Daily events: {len(daily_events)} 条")
    print(f"Search result: {len(search_result) if isinstance(search_result, list) else 'N/A'} 条")
    
    # 生成初始推理图
    print("\n正在生成初始推理图...")
    initial_graph = generator._generate_initial_inference_graph(
        target_event, search_result, daily_events
    )
    
    print(f"\n初始推理图:")
    print(f"  - 节点数: {len(initial_graph.get('nodes', []))}")
    print(f"  - 边数: {len(initial_graph.get('edges', []))}")
    print(f"  - 推理路径数: {len(initial_graph.get('reasoning_paths', []))}")
    
    if initial_graph.get('nodes'):
        print(f"\n所有节点 ({len(initial_graph['nodes'])} 个):")
        for i, node in enumerate(initial_graph['nodes'], 1):
            name = node.get('name', '')
            time = node.get('time', '')
            source = node.get('source', '')
            entity = node.get('entity', '')
            print(f"  {i}. {name}")
            if time:
                print(f"     时间: {time}")
            if entity:
                print(f"     实体: {entity}")
            if source:
                print(f"     来源: {source}")
    
    if initial_graph.get('edges'):
        print(f"\n所有边 ({len(initial_graph['edges'])} 条):")
        for i, edge in enumerate(initial_graph['edges'], 1):
            source = edge.get('source', '')
            target = edge.get('target', '')
            relation = edge.get('relation', '')
            description = edge.get('description', '')
            print(f"  {i}. {source} → {target}")
            if relation:
                print(f"     关系: {relation}")
            if description:
                print(f"     描述: {description[:100]}{'...' if len(description) > 100 else ''}")
    
    return initial_graph


def test_extend_methods(generator, initial_graph):
    """测试三种扩展方法"""
    print("\n" + "="*60)
    print("测试 6: 扩展方法测试")
    print("="*60)
    
    nodes = initial_graph.get('nodes', [])
    if not nodes:
        print("⚠ 没有可用节点，跳过扩展测试")
        return
    
    daily_events = initial_graph.get('input_data', {}).get('daily_events', [])
    
    # 测试时序扩展
    print("\n[6.1] 时序扩展")
    temporal_ext = generator._extend_by_temporal(initial_graph, daily_events)
    print(f"  - 扩展结果数: {len(temporal_ext)}")
    if temporal_ext:
        desc = temporal_ext[0].get('description', '')
        print(f"  - 描述 (前200字): {desc[:200]}...")
    
    # 测试实体扩展
    print("\n[6.2] 实体扩展")
    entity_ext = generator._extend_by_entity(initial_graph, daily_events)
    print(f"  - 扩展结果数: {len(entity_ext)}")
    if entity_ext:
        desc = entity_ext[0].get('description', '')
        print(f"  - 描述 (前200字): {desc[:200]}...")
    
    # 测试编造扩展
    print("\n[6.3] 编造扩展")
    fabrication_ext = generator._extend_by_fabrication(initial_graph)
    print(f"  - 扩展结果数: {len(fabrication_ext)}")
    if fabrication_ext:
        desc = fabrication_ext[0].get('description', '')
        print(f"  - 描述 (前200字): {desc[:200]}...")


def test_generate_monthly_qa(generator, year, month):
    """测试生成单月问答"""
    print("\n" + "="*60)
    print("测试 7: 生成单月问答")
    print("="*60)
    
    print(f"\n生成 {year}-{month:02d} 的问答对...")
    qa_list = generator.generate_monthly_qa(year, month, num_questions=1)
    
    print(f"\n生成结果: {len(qa_list)} 个问答对")
    
    if qa_list:
        qa = qa_list[0]
        print(f"\n问题: {qa.get('question', '')}")
        print(f"答案: {qa.get('answer', '')}")
        print(f"提问时间: {qa.get('ask_time', '')}")
        print(f"问题类型: {qa.get('question_type', '')}")
        print(f"问题证据: {qa.get('evidence', '')}")

    
    return qa_list


def main():
    """主测试流程"""
    print("="*60)
    print("多跳问题生成器测试")
    print("="*60)
    
    # 加载测试数据
    print("\n[步骤 0] 加载测试数据")
    try:
        daily_event, event_tree, draft_event, phonedata, phone_data_dir = load_test_data()
    except Exception as e:
        print(f"✗ 加载数据失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 创建生成器
    print("\n[步骤 0.5] 创建生成器实例")
    generator = QAMultiHopGenerator(
        daily_event=daily_event,
        event_tree=event_tree,
        draft_event=draft_event,
        phonedata=phonedata,
        phone_data_dir=phone_data_dir,
        is_print=True  # 开启详细输出
    )
    print("✓ 生成器创建成功")
    
    # 选择测试年月
    test_year = 2025
    test_month = 1
    
    # # 测试 1: Select Agent
    # select_result = test_select_agent(generator, test_year, test_month)
    # if not select_result:
    #     print("\n✗ Select Agent 失败，终止测试")
    #     return
    #
    # # 测试 2 & 3: Search Agent (两种模式)
    # target_event = select_result.get('target_event', {})
    # dates = select_result.get('dates', [])
    #
    # # 先尝试模式 1
    # leaf_events = test_search_agent_mode1(generator, target_event)
    #
    # # 再测试模式 2
    # draft_events = test_search_agent_mode2(generator, dates, target_event)
    #
    #
    # # 测试 5: Inference Agent (使用 leaf_events 或 draft_events)
    # search_result = leaf_events if leaf_events else draft_events
    # if search_result:
    #     initial_graph = test_inference_agent(generator, select_result, search_result)
    #
    #     # 测试 6: 扩展方法
    #     if initial_graph and initial_graph.get('nodes'):
    #         test_extend_methods(generator, initial_graph)

    # # 测试 7: 生成单月问答（可选，因为需要多次 LLM 调用）
    # print("\n" + "="*60)
    # print("是否执行完整问答生成测试？(需要多次 LLM 调用)")
    # print("="*60)
    # print("提示: 此测试会调用 LLM 生成完整的问答对，可能需要较长时间")
    # print("如需测试，请取消下面代码的注释")
    #
    # 取消注释以启用完整测试
    test_generate_monthly_qa(generator, test_year, test_month)
    
    print("\n" + "="*60)
    print("测试完成！")
    print("="*60)


if __name__ == '__main__':
    main()
