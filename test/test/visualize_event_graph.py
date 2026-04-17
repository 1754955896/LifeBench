# -*- coding: utf-8 -*-
"""事件图谱可视化脚本"""
import os
import sys
import json

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from event.draft.GraphGenerator import EventGraphGenerator


def visualize_event_graph(graph_path: str, output_file: str = "event_graph_visualization.html"):
    """
    可视化事件图谱
    
    Args:
        graph_path: 事件图谱 JSON 文件路径
        output_file: 输出的 HTML 文件路径
    """
    # 检查文件是否存在
    if not os.path.exists(graph_path):
        print(f"✗ 图谱文件不存在：{graph_path}")
        return
    
    # 加载图谱数据
    try:
        with open(graph_path, 'r', encoding='utf-8') as f:
            event_graph = json.load(f)
        print(f"✓ 成功加载图谱文件：{graph_path}")
    except Exception as e:
        print(f"✗ 加载图谱失败：{e}")
        return
    
    # 使用 GraphGenerator 的可视化功能
    generator = EventGraphGenerator()
    
    # 输出文件路径
    output_path = os.path.join(os.path.dirname(graph_path), output_file)
    
    # 调用可视化方法
    generator.visualize_event_graph(event_graph, output_path)
    
    print(f"\n✓ 图谱已保存到：{output_path}")
    print("✓ 可以用浏览器打开查看交互式可视化效果")


def main():
    """主函数"""
    # 默认图谱路径
    default_graph_path = r"/test/process/graph/inserted_event_graph.json"
    
    print("="*60)
    print("事件图谱可视化工具")
    print("="*60)
    
    # 使用默认路径
    graph_path = default_graph_path
    print(f"\n使用默认图谱路径：{graph_path}")
    
    # 调用可视化函数
    visualize_event_graph(graph_path)
    
    print("\n" + "="*60)
    print("可视化完成！")
    print("="*60)


if __name__ == "__main__":
    main()
