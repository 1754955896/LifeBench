# -*- coding: utf-8 -*-
"""draft生成类，负责处理draft生成相关的操作"""
from event.draft.timeline_gen import TimelineGen
from event.edit.writing_agent import WritingAgent
from event.scheduler import Scheduler
import os
import json


class DraftGen:
    def __init__(self, persona, file_path):
        """初始化draft生成器"""
        self.persona = persona
        self.file_path = file_path
    
    def generate_draft(self, output_path="output/", meidan_path=None):
        """
        生成draft的主要方法
        
        参数:
            output_path: 输出路径
            meidan_path: 中间数据路径
            
        返回:
            生成的draft数据
        """
        print("开始生成draft...")
        
        # 步骤1: 调用timeline_gen.py生成情节库
        print("\n=== 步骤1: 生成情节库 ===")
        timeline_gen = TimelineGen(self.persona, self.file_path)
        
        # 调用generate_yearly_timeline_plot方法生成情节库
        timeline_gen.generate_yearly_timeline_plot(self.persona, output_path, meidan_path)
        print(f"✓ 成功生成情节库")
        
        # 步骤2: 调用Interface_1.py唤起writing agent的接口
        print("\n=== 步骤2: 唤起writing agent ===")
        
        # 获取基础路径
        base_path = self._get_base_path()
        print(f"使用基础路径: {base_path}")
        
        # 初始化WritingAgent
        try:
            writing_agent = WritingAgent(path=base_path)
            print("✓ WritingAgent 初始化成功")
        except Exception as e:
            print(f"✗ WritingAgent 初始化失败: {e}")
            return None
        
        # 获取初始情节
        current_plot = writing_agent.initial_plot.copy()
        print("✓ 获取初始情节成功")
        
        # 自动优化当前情节
        print("\n开始自动优化情节...")
        current_plot = writing_agent.interact_with_user("帮我自动优化", current_plot)
        print("✓ 情节优化完成")
        
        # 步骤3: 规范化事件格式
        print("\n=== 步骤3: 规范化事件格式 ===")
        from event.draft.normalizer import Normalizer
        
        # 确保输出路径存在
        if meidan_path is None:
            meidan_path = os.path.join(output_path, 'process')
        
        os.makedirs(output_path, exist_ok=True)
        os.makedirs(meidan_path, exist_ok=True)
        
        # 保存当前情节到文件
        plot_path = os.path.join(meidan_path, "current_plot.json")
        with open(plot_path, 'w', encoding='utf-8') as f:
            json.dump(current_plot, f, ensure_ascii=False, indent=2)
        print(f"✓ 情节已保存到: {plot_path}")
        
        # 初始化规范化器
        optimize_timeline_path = os.path.join(meidan_path, "optimize_timeline.json")
        
        # 将当前情节转换为时间线格式
        timeline_data = {
            "comprehensive_summary": current_plot.get('yearly_summary', ''),
            "monthly_details": current_plot.get('monthly_events', [])
        }
        
        # 保存为 optimize_timeline.json
        with open(optimize_timeline_path, 'w', encoding='utf-8') as f:
            json.dump(timeline_data, f, ensure_ascii=False, indent=2)
        print(f"✓ 时间线数据已保存到: {optimize_timeline_path}")
        
        # 调用规范化器
        normalizer = Normalizer(optimize_timeline_path=optimize_timeline_path, persona=self.persona, isprint=True)
        normalized_data = normalizer.load_and_normalize_data()
        print("✓ 事件格式规范化完成")
        
        # 提取规范化后的事件列表
        normalized_events = []
        for month_detail in normalized_data.get('monthly_details', []):
            normalized_events.extend(month_detail.get('events', []))
        
        print(f"✓ 共提取 {len(normalized_events)} 个规范化事件")
        
        # 步骤4: 生成事件图谱
        print("\n=== 步骤4: 生成事件图谱 ===")
        from event.draft.GraphGenerator import EventGraphGenerator
        
        # 初始化图谱生成器
        graph_generator = EventGraphGenerator(events_data=normalized_events)
        
        # 构建事件图谱
        event_graph = graph_generator.build_event_graph(normalized_events)
        
        # 保存图谱
        graph_path = os.path.join(meidan_path, "graph", "event_graph.json")
        os.makedirs(os.path.dirname(graph_path), exist_ok=True)
        with open(graph_path, 'w', encoding='utf-8') as f:
            json.dump(event_graph, f, ensure_ascii=False, indent=2)
        print(f"✓ 事件图谱已保存到: {graph_path}")
        
        # # 步骤5: 优化图谱
        # print("\n=== 步骤5: 优化图谱 ===")
        # from event.draft.GraphRefiner import GraphRefiner
        # 
        # # 初始化图谱优化器
        # graph_refiner = GraphRefiner(event_graph=event_graph, yearly_summary=current_plot.get('yearly_summary', ''), isprint=True)
        # 
        # # 执行图谱优化（插入建议可以从情节中获取）
        # insertion_suggestion = current_plot.get('insertion_suggestion', '根据人物画像和已有事件，补充完善生活细节')
        # optimized_graph = graph_refiner.insert_events(insertion_suggestion)
        # 
        # # 保存优化后的图谱
        # optimized_graph_path = os.path.join(meidan_path, "graph", "inserted_event_graph.json")
        # with open(optimized_graph_path, 'w', encoding='utf-8') as f:
        #     json.dump(optimized_graph, f, ensure_ascii=False, indent=2)
        # print(f"✓ 优化后的图谱已保存到: {optimized_graph_path}")
        
        # 使用未优化的图谱作为后续步骤的输入
        optimized_graph = event_graph
        
        # 步骤6: 优化每月事件
        print("\n=== 步骤6: 优化每月事件 ===")
        from event.draft.monthly_refine import MonthlyRefiner
        
        # 初始化月度优化器
        monthly_refiner = MonthlyRefiner(filepath=output_path, year=2025, isprint=True)
        
        # 执行完整流程
        monthly_refiner.run_full_pipeline()
        print("✓ 每月事件优化完成")
        
        # 步骤7: 生成每日大纲
        print("\n=== 步骤7: 生成每日大纲 ===")
        from event.draft.scheduler import Scheduler
        
        # 初始化调度器
        scheduler = Scheduler(persona=self.persona, file_path=output_path)
        
        # 处理每月详情
        print("\n[Step 7.1] 处理每月详情...")
        scheduler.process_monthly_details(self.persona, output_path)
        print("✓ 每月详情处理完成")
        
        # 生成年度时间线草稿
        print("\n[Step 7.2] 生成年度时间线草稿...")
        result = scheduler.generate_yearly_timeline_draft(self.persona, output_path, meidan_path)
        print("✓ 年度时间线草稿生成完成")
        
        # 步骤8: 优化每日大纲
        print("\n=== 步骤8: 优化每日大纲 ===")
        from event.draft.outline_optimizer import OutlineOptimizer
        
        # 初始化大纲优化器
        outline_optimizer = OutlineOptimizer(output_path, meidan_path)
        
        # 执行大纲优化
        optimized_outline = outline_optimizer.optimize_outline()
        print("✓ 每日大纲优化完成")
        
        print("\n🎉 Draft生成完成！")
        return optimized_outline
    
    def _get_base_path(self):
        """获取基础路径"""
        # 默认路径 - 使用绝对路径
        default_path = r"D:\pyCharmProjects\pythonProject4\test"
        
        # 检查默认路径是否存在
        if os.path.exists(default_path):
            return default_path
        
        # 如果不存在，使用项目根目录
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        test_path = os.path.join(project_root, 'test')
        
        # 确保test目录存在
        os.makedirs(test_path, exist_ok=True)
        return test_path