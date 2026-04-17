# -*- coding: utf-8 -*-
"""Scheduler 模块的测试文件"""
import os
import sys
import json
from event.scheduler import Scheduler


def test_scheduler_main():
    """
    测试 Scheduler的 main 函数
    """
    print("\n" + "="*60)
    print("Scheduler Main 函数测试")
    print("="*60)
    
    # 使用测试数据
    test_path = os.path.join(os.path.dirname(__file__), "test")
    persona_path = os.path.join(test_path, "persona.json")
    timeline_path = os.path.join(test_path, "process", "normalized_timeline.json")
    
    # 检查测试数据是否存在
    if not os.path.exists(persona_path):
        print(f"✗ 测试数据不存在：{persona_path}")
        return
    
    if not os.path.exists(timeline_path):
        print(f"✗ 时间线数据不存在：{timeline_path}")
        return
    
    try:
        # 加载测试数据
        with open(persona_path, 'r', encoding='utf-8') as f:
            persona = json.load(f)
        
        with open(timeline_path, 'r', encoding='utf-8') as f:
            timeline_data = json.load(f)
        
        print(f"✓ 成功加载测试数据")
        print(f"  - 人物画像：{persona.get('name', 'Unknown')}")
        print(f"  - 时间线包含 {len(timeline_data.get('monthly_details', []))} 个月的数据")
        
        # 创建 Scheduler 实例
        scheduler = Scheduler(
            filepath=test_path
        )
        
        print(f"\n✓ Scheduler 初始化成功")
        print(f"  - 文件路径：{scheduler.filepath}")
        
        # 调用 main 函数
        print(f"\n开始执行 main 函数...")
        result = scheduler.main()
        
        # 检查结果
        if result and isinstance(result, dict):
            nodes_count = len(result.get('nodes', []))
            edges_count = len(result.get('edges', []))
            
            print(f"\n" + "="*60)
            print("测试结果")
            print("="*60)
            print(f"✓ main 函数执行成功")
            print(f"  - 最终图谱包含 {nodes_count} 个节点")
            print(f"  - 最终图谱包含 {edges_count} 条边")
            
            # 检查是否生成了 inserted_event_graph.json
            graph_dir = os.path.join(test_path, "process", "graph")
            inserted_graph_path = os.path.join(graph_dir, "inserted_event_graph.json")
            
            if os.path.exists(inserted_graph_path):
                print(f"✓ 插入后的图谱已保存：{inserted_graph_path}")
                
                # 验证保存的文件
                with open(inserted_graph_path, 'r', encoding='utf-8') as f:
                    saved_graph = json.load(f)
                
                saved_nodes = len(saved_graph.get('nodes', []))
                saved_edges = len(saved_graph.get('edges', []))
                print(f"  - 保存的图谱包含 {saved_nodes} 个节点，{saved_edges} 条边")
                
                if saved_nodes == nodes_count and saved_edges == edges_count:
                    print(f"✓ 保存的图谱与内存中的数据一致")
                else:
                    print(f"⚠️  保存的图谱与内存中的数据不一致")
            else:
                print(f"⚠️  未找到保存的图谱文件：{inserted_graph_path}")
        else:
            print(f"⚠️  main 函数返回结果异常：{result}")
        
    except Exception as e:
        print(f"\n✗ 测试失败：{e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n🎉 Scheduler Main 函数测试完成！")


def test_scheduler_with_real_data():
    """
    使用真实数据测试 Scheduler（如果存在）
    """
    print("\n" + "="*60)
    print("Scheduler 真实数据测试")
    print("="*60)
    
    # 尝试使用真实的人物数据
    real_personas = [
        os.path.join(os.path.dirname(__file__), "fenghaoran", "persona.json"),
        os.path.join(os.path.dirname(__file__), "yuxiaowen", "persona.json")
    ]
    
    for persona_path in real_personas:
        if os.path.exists(persona_path):
            print(f"\n尝试使用真实数据：{persona_path}")
            try:
                with open(persona_path, 'r', encoding='utf-8') as f:
                    persona = json.load(f)
                
                # 查找对应的时间线数据
                name = os.path.basename(os.path.dirname(persona_path))
                timeline_path = os.path.join(os.path.dirname(__file__), name, "process", "normalized_timeline.json")
                
                if os.path.exists(timeline_path):
                    with open(timeline_path, 'r', encoding='utf-8') as f:
                        timeline_data = json.load(f)
                    
                    print(f"✓ 成功加载 {name} 的数据")
                    
                    # 创建 Scheduler 并测试
                    scheduler = Scheduler(
                        persona=persona,
                        timeline_data=timeline_data,
                        filepath=os.path.join(os.path.dirname(__file__), name)
                    )
                    
                    result = scheduler.main()
                    
                    if result:
                        print(f"✓ {name} 测试成功，生成 {len(result.get('nodes', []))} 个节点")
                    else:
                        print(f"⚠️  {name} 测试结果异常")
                    
                    return  # 成功测试一个即可
                else:
                    print(f"⚠️  未找到 {name} 的时间线数据")
                    
            except Exception as e:
                print(f"✗ 测试失败：{e}")
                continue
    
    print("\n⚠️  未找到可用的真实数据")


if __name__ == "__main__":
    # 运行测试
    print("="*60)
    print("开始执行 Scheduler 测试")
    print("="*60)
    
    # 测试 main 函数（使用测试数据）
    test_scheduler_main()
    
    # 可选：测试真实数据
    # test_scheduler_with_real_data()
    
    print("\n" + "="*60)
    print("所有测试执行完毕！")
    print("="*60)