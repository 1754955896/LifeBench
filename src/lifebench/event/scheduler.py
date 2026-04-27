# -*- coding: utf-8 -*-
"""规划器类，负责基于画像信息和时间线数据进行事件规划和分析"""
import os
import json
import datetime
from typing import Dict, List, Any, Optional
from src.lifebench.utils.llm_call import llm_call_j, llm_call_reason_j


class Scheduler:
    """规划器类，负责基于画像信息和时间线数据进行事件规划和分析"""
    
    def __init__(self, filepath: str, year: int = 2025):
        """
        初始化规划器
            
        Args:
            filepath: 基础路径，包含 persona.json 和 process/optimize_timeline.json 文件
            year: 目标年份，默认为 2025
        """
        self.filepath = filepath
        self.year = year
        self.persona_path = os.path.join(filepath, "persona.json")
        self.optimize_timeline_path = os.path.join(filepath, "process", "optimize_timeline.json")
        self.isprint = True  # 先初始化 isprint
        self.persona = self._load_persona()
        self.timeline_data = self._load_timeline_data()

    def _load_persona(self) -> Dict:
        """
        加载画像信息
        
        Returns:
            画像信息字典
        """
        if os.path.exists(self.persona_path):
            try:
                with open(self.persona_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"加载persona.json失败: {e}")
                return {}
        else:
            print(f"persona.json文件不存在: {self.persona_path}")
            return {}
    
    def _load_timeline_data(self) -> Dict:
        """
        加载时间线数据
        
        Returns:
            时间线数据字典
        """
        from src.lifebench.event.draft.normalizer import Normalizer
        
        # 创建规范化器实例，传递画像数据和isprint参数
        normalizer = Normalizer(self.optimize_timeline_path, self.persona, self.isprint)
        
        # 使用规范化器加载并规范化数据
        return normalizer.load_and_normalize_data()

    
    def main(self):
        """
        主函数：执行完整的事件图谱构建和插入流程
        
        流程：
        1. 创建 EventGraphGenerator 实例并构建事件图谱
        2. 使用 LLM 生成随机事件
        3. 采样事件
        4. 调用 insert_events 插入事件到图谱
        """
        from src.lifebench.event.draft.GraphGenerator import EventGraphGenerator
        import random
        
        print("="*60)
        print("开始执行事件图谱构建与插入流程")
        print("="*60)
        
        # Step 1: 创建 EventGraphGenerator 并构建事件图谱
        print("\n[Step 1] 构建事件图谱...")
        
        # 检查图谱文件是否已存在
        import os
        graph_dir = os.path.join(self.filepath, "process", "graph")
        graph_path = os.path.join(graph_dir, "event_graph.json")
        
        # 从 timeline_data 中提取全年总结和事件数据
        yearly_summary = self.timeline_data.get("comprehensive_summary", "")
        events_data = []
        monthly_details = self.timeline_data.get("monthly_details", [])
        print(f"✓ 提取到 {len(monthly_details)} 个月的数据")
        
        for month_data in monthly_details:
            month = month_data.get("month")
            events = month_data.get("events", [])
            print(f"  - {month}: {len(events)} 个事件")
            # 确保事件是字典格式，如果是字符串则转换为字典
            for event in events:
                if isinstance(event, dict):
                    events_data.append(event)
                elif isinstance(event, str):
                    # 如果是字符串，转换为字典格式
                    events_data.append({
                        "name": event,
                        "description": event,
                        "type": "unknown",
                        "date": [month]
                    })
        
        print(f"✓ 总计提取 {len(events_data)} 个事件")
        if yearly_summary:
            print(f"✓ 提取全年总结：{len(yearly_summary)} 字符")
        
        # 始终实例化 EventGraphGenerator，传入全年总结和事件数据
        generator = EventGraphGenerator(events_data=events_data, yearly_summary=yearly_summary)
        
        # 检查是否已有图谱文件
        if os.path.exists(graph_path):
            print(f"✓ 检测到已有图谱文件：{graph_path}")
            print("  正在加载现有图谱...")
            try:
                with open(graph_path, 'r', encoding='utf-8') as f:
                    event_graph = json.load(f)
                print(f"✓ 成功加载现有图谱，包含 {len(event_graph.get('nodes', []))} 个节点，{len(event_graph.get('edges', []))} 条边")
                # 将加载的图谱设置到 generator 中
                generator.event_graph = event_graph
            except Exception as e:
                print(f"⚠️  加载图谱失败：{e}，将重新构建...")
                event_graph = generator.build_event_graph()
                print(f"✓ 事件图谱构建完成，包含 {len(event_graph.get('nodes', []))} 个节点，{len(event_graph.get('edges', []))} 条边")
        else:
            # 图谱文件不存在，需要构建
            os.makedirs(graph_dir, exist_ok=True)
            
            # 构建事件图谱
            event_graph = generator.build_event_graph()
            print(f"✓ 事件图谱构建完成，包含 {len(event_graph.get('nodes', []))} 个节点，{len(event_graph.get('edges', []))} 条边")
            
            # 保存图谱到 filepath/process/graph 文件夹
            try:
                with open(graph_path, 'w', encoding='utf-8') as f:
                    json.dump(event_graph, f, ensure_ascii=False, indent=2)
                print(f"✓ 事件图谱已保存到：{graph_path}")
            except Exception as e:
                print(f"⚠️  保存图谱失败：{e}")
        
        # Step 2-4: 生成随机事件并插入到图谱
        updated_graph = self._generate_and_insert_events(generator, graph_path)
        
        print("\n" + "="*60)
        print("事件图谱构建与插入流程完成！")
        print("="*60)
        
        return updated_graph
    
    def _generate_and_insert_events(self, generator, graph_path: str):
        """
        生成随机事件并插入到图谱（步骤 2、3、4）
        
        Args:
            generator: EventGraphGenerator 实例
            graph_path: 图谱文件路径
        """
        import os
        import random
        # 检查是否已有插入后的图谱文件
        inserted_graph_path = os.path.join(os.path.dirname(graph_path), "inserted_event_graph.json")
        
        if os.path.exists(inserted_graph_path):
            print(f"\n✓ 检测到已有插入后的图谱文件：{inserted_graph_path}")
            print("  跳过事件生成和插入步骤...")
            try:
                with open(inserted_graph_path, 'r', encoding='utf-8') as f:
                    updated_graph = json.load(f)
                print(f"✓ 成功加载现有图谱，包含 {len(updated_graph.get('nodes', []))} 个节点")
                return updated_graph
            except Exception as e:
                print(f"⚠️  加载图谱失败：{e}，将重新执行...")
        
        # Step 2: 使用 EventGenerator.main() 生成事件
        print("\n[Step 2] 使用 EventGenerator 生成事件...")
        from src.lifebench.event.draft.event_gen import EventGenerator
        
        # 准备总结文本（从 timeline_data 的 comprehensive_summary 字段获取）
        summary_text = self.timeline_data.get("comprehensive_summary", "")
        
        # 调用 EventGenerator 的 main 函数
        event_generator = EventGenerator(self.persona)
        sampled_events = event_generator.main(
            target_count=5,
            sample_ratio=0.5,
            summary_text=summary_text
        )
        print(f"✓ 生成了 {len(sampled_events)} 个事件")
        
        # Step 3: 采样事件（由于 EventGenerator.main 已经采样到目标数量的 2 倍，这里不再需要额外采样）
        print("\n[Step 3] 事件已筛选完成...")
        
        # Step 4: 遍历每个事件，逐个插入到图谱
        print("\n[Step 4] 逐个插入事件到图谱...")
        updated_graph = generator.event_graph
        for i, event in enumerate(sampled_events, 1):
            print(f"\n  正在插入第 {i}/{len(sampled_events)} 个事件...")
            updated_graph = generator.insert_events([event])
            print(f"  ✓ 第 {i} 个事件插入完成")
        
        print(f"\n✓ 所有事件插入完成，更新后的图谱包含 {len(updated_graph.get('nodes', []))} 个节点")
        
        # 保存优化后的图谱
        try:
            with open(inserted_graph_path, 'w', encoding='utf-8') as f:
                json.dump(updated_graph, f, ensure_ascii=False, indent=2)
            print(f"✓ 优化后的图谱已保存到：{inserted_graph_path}")
        except Exception as e:
            print(f"⚠️  保存图谱失败：{e}")
        
        return updated_graph
    
