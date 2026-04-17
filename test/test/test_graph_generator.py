# -*- coding: utf-8 -*-
"""测试 GraphGenerator.py"""
import os
import json
import sys

# 添加项目根目录到路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from event.draft.GraphGenerator import EventGraphGenerator


def load_yearly_summary():
    """
    从测试数据文件中加载全年总结
    
    Returns:
        yearly_summary: 全年总结文本
    """
    # 测试数据路径
    test_data_path = os.path.join(os.path.dirname(__file__), "test", "process", "normalized_timeline.json")
    
    if not os.path.exists(test_data_path):
        print(f"✗ 测试数据不存在：{test_data_path}")
        return None
    
    # 加载测试数据
    try:
        with open(test_data_path, 'r', encoding='utf-8') as f:
            timeline_data = json.load(f)
        print("✓ 加载测试数据成功")
    except Exception as e:
        print(f"✗ 加载测试数据失败：{e}")
        return None
    
    # 提取全年总结
    yearly_summary = timeline_data.get("comprehensive_summary", "")
    if yearly_summary:
        print(f"✓ 提取全年总结成功：{len(yearly_summary)} 字符")
    else:
        print("⚠️  全年总结为空")
    
    return yearly_summary


def load_event_graph():
    """
    加载或构建事件图谱
    
    Returns:
        事件图谱数据
    """
    # 创建 graph 文件夹
    graph_folder = os.path.join(os.path.dirname(__file__), "graph")
    if not os.path.exists(graph_folder):
        os.makedirs(graph_folder)
        print(f"✓ 创建 graph 文件夹成功：{graph_folder}")
    
    # 事件图谱数据文件路径
    output_json = os.path.join(graph_folder, "event_graph.json")
    
    # 检查是否已存在事件图谱数据
    if os.path.exists(output_json):
        print("✓ 事件图谱数据已存在，直接加载")
        try:
            with open(output_json, 'r', encoding='utf-8') as f:
                event_graph = json.load(f)
            print("✓ 加载事件图谱数据成功")
            print(f"  - 节点数量：{len(event_graph.get('nodes', []))}")
            print(f"  - 边数量：{len(event_graph.get('edges', []))}")
            return event_graph
        except Exception as e:
            print(f"✗ 加载事件图谱数据失败：{e}")
            return None
    else:
        # 测试数据路径
        test_data_path = os.path.join(os.path.dirname(__file__), "test", "process", "normalized_timeline.json")
        
        if not os.path.exists(test_data_path):
            print(f"✗ 测试数据不存在：{test_data_path}")
            return None
        
        # 加载测试数据
        try:
            with open(test_data_path, 'r', encoding='utf-8') as f:
                timeline_data = json.load(f)
            print("✓ 加载测试数据成功")
        except Exception as e:
            print(f"✗ 加载测试数据失败：{e}")
            return None
        
        # 提取所有事件数据
        events_data = []
        monthly_details = timeline_data.get("monthly_details", [])
        print(f"✓ 提取到{len(monthly_details)}个月的数据")
        
        for month_data in monthly_details:
            month = month_data.get("month")
            events = month_data.get("events", [])
            print(f"  - {month}: {len(events)}个事件")
            events_data.extend(events)
        
        print(f"✓ 总计提取{len(events_data)}个事件")
        
        # 创建 GraphGenerator 实例
        try:
            generator = EventGraphGenerator(events_data)
            print("✓ 创建 GraphGenerator 实例成功")
        except Exception as e:
            print(f"✗ 创建 GraphGenerator 实例失败：{e}")
            return None
        
        # 构建事件图谱
        try:
            event_graph = generator.build_event_graph()
            print("✓ 构建事件图谱成功")
            print(f"  - 节点数量：{len(event_graph.get('nodes', []))}")
            print(f"  - 边数量：{len(event_graph.get('edges', []))}")
        except Exception as e:
            print(f"✗ 构建事件图谱失败：{e}")
            return None
        
        # 保存事件图谱
        try:
            generator.save_event_graph(event_graph, output_json)
            print(f"✓ 保存事件图谱成功：{output_json}")
        except Exception as e:
            print(f"✗ 保存事件图谱失败：{e}")
        
        return event_graph


def test_visualization():
    """
    测试可视化功能
    """
    print("=== 测试可视化功能 ===")
    
    # 加载事件图谱
    event_graph = load_event_graph()
    if not event_graph:
        print("✗ 无法加载事件图谱，测试终止")
        return
    
    # 可视化事件图谱
    try:
        generator = EventGraphGenerator()  # 创建一个新的实例用于可视化
        graph_folder = os.path.join(os.path.dirname(__file__), "graph")
        output_html = os.path.join(graph_folder, "event_graph.html")
        generator.visualize_event_graph(event_graph, output_html)
        print(f"✓ 可视化事件图谱成功：{output_html}")
    except Exception as e:
        print(f"✗ 可视化事件图谱失败：{e}")
    
    print("\n🎉 可视化功能测试完成！")


def test_insert_events():
    """
    测试 insert_events 方法，新增事件插入功能
    """
    print("=== 测试 insert_events 方法 ===")
    
    # 加载全年总结
    yearly_summary = load_yearly_summary()
    
    # 加载事件图谱
    event_graph = load_event_graph()  # 不需要第二个返回值
    
    try:
        # 创建 EventGraphGenerator 实例，传入全年总结
        insert_generator = EventGraphGenerator(
            event_graph=event_graph,
            yearly_summary=yearly_summary
        )
        
        # 定义插入建议
        insertion_suggestion = "决定开始学习 AI 使用课程，并计划参加相关培训和项目实践，来融入工作中"
        print(f"\n插入建议：{insertion_suggestion}")
        
        # 执行事件插入
        updated_graph = insert_generator.insert_events(insertion_suggestion)
        print("\n✓ 插入事件成功")
        print(f"  - 更新后节点数量：{len(updated_graph.get('nodes', []))}")
        print(f"  - 更新后边数量：{len(updated_graph.get('edges', []))}")
        
        # 保存更新后的事件图谱
        graph_folder = os.path.join(os.path.dirname(__file__), "graph")
        inserted_output_json = os.path.join(graph_folder, "inserted_event_graph.json")
        insert_generator.save_event_graph(updated_graph, inserted_output_json)
        print(f"✓ 保存插入后的事件图谱成功：{inserted_output_json}")
        
        # 可视化插入后的事件图谱
        inserted_output_html = os.path.join(graph_folder, "inserted_event_graph.html")
        insert_generator.visualize_event_graph(updated_graph, inserted_output_html)
        print(f"✓ 可视化插入后的事件图谱成功：{inserted_output_html}")
        
        # 打印新增的事件信息
        original_node_count = len(event_graph.get('nodes', []))
        new_node_count = len(updated_graph.get('nodes', [])) - original_node_count
        print(f"\n✓ 新增事件数量：{new_node_count}")
        
        # 显示新增事件的详细信息
        original_ids = set(str(node['id']) for node in event_graph.get('nodes', []))
        new_nodes = [node for node in updated_graph.get('nodes', []) if str(node['id']) not in original_ids]
        
        if new_nodes:
            print("\n新增事件详情:")
            for i, node in enumerate(new_nodes[:10], 1):  # 只显示前 10 个
                time_info = ', '.join(node['time']) if isinstance(node['time'], list) else node.get('time', '未知')
                print(f"  {i}. ID: {node['id']}, 名称：{node['name']}, 时间：{time_info}")
                print(f"     类型：{node['type']}")
                desc = node['description'][:80] + "..." if len(node['description']) > 80 else node['description']
                print(f"     描述：{desc}")
        
        # 打印新增的边信息
        original_edges_set = set((str(e['source']), str(e['target'])) for e in event_graph.get('edges', []))
        new_edges = [e for e in updated_graph.get('edges', []) if (str(e['source']), str(e['target'])) not in original_edges_set]
        
        if new_edges:
            print(f"\n✓ 新增边数量：{len(new_edges)}")
            print("前 5 条新增边示例:")
            for i, edge in enumerate(new_edges[:5], 1):
                print(f"  {i}. {edge['source']} → {edge['target']} ({edge['type']})")
                desc = edge['description'][:60] + "..." if len(edge['description']) > 60 else edge['description']
                print(f"     {desc}")
    except Exception as e:
        print(f"✗ 测试 insert_events 方法失败：{e}")
        import traceback
        traceback.print_exc()
    
    print("\n🎉 insert_events 方法测试完成！")


if __name__ == "__main__":
    import time
    
    start_time = time.time()
    
    # 运行可视化测试
    # test_visualization()
    
    # 运行新绌事件插入测试
    test_insert_events()
    
    end_time = time.time()
    elapsed_time = end_time - start_time
    
    print(f"\n🎉 所有测试完成！总执行时间：{elapsed_time:.2f}秒")
