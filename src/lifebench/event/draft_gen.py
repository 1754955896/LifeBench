# -*- coding: utf-8 -*-
"""draft生成类，负责处理draft生成相关的操作"""
from src.lifebench.event.draft.timeline_gen import TimelineGen
from src.lifebench.event.edit.writing_agent import WritingAgent
from src.lifebench.event.scheduler import Scheduler
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
        base_path = meidan_path
        print(f"使用基础路径: {base_path}")
        
        # 初始化WritingAgent
        try:
            writing_agent = WritingAgent(path=base_path)
            print("✓ WritingAgent 初始化成功")
        except Exception as e:
            print(f"✗ WritingAgent 初始化失败: {e}")
            return None
        
        # 获取初始情节
        plot_path = os.path.join(meidan_path, "current_plot.json") if meidan_path else None
        if plot_path and os.path.exists(plot_path):
            print(f"⊙ current_plot.json 已存在，跳过自动优化步骤")
            try:
                with open(plot_path, 'r', encoding='utf-8') as f:
                    current_plot = json.load(f)
                print("✓ 已加载现有情节")
            except Exception as e:
                print(f"⚠️  加载现有情节失败：{e}，重新生成")
                current_plot = writing_agent.initial_plot.copy()
                print("\n开始自动优化情节...")
                current_plot = writing_agent.interact_with_user("帮我自动优化", current_plot)
                print("✓ 情节优化完成")
        else:
            current_plot = writing_agent.initial_plot.copy()
            print("✓ 获取初始情节成功")
            
            # 自动优化当前情节
            print("\n开始自动优化情节...")
            current_plot = writing_agent.interact_with_user("帮我自动优化", current_plot)
            print("✓ 情节优化完成")

            current_plot = writing_agent.iterative_optimization(current_plot)

        # 步骤3: 规范化事件格式
        print("\n=== 步骤3: 规范化事件格式 ===")
        from src.lifebench.event.draft.normalizer import Normalizer
        
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
        # 确保使用正确的键名映射，如果 current_plot 已经是标准格式则直接使用
        timeline_data = {
            "comprehensive_summary": current_plot.get('comprehensive_summary', current_plot.get('yearly_summary', '')),
            "monthly_details": current_plot.get('monthly_details', current_plot.get('monthly_events', []))
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
        
        # # 步骤4: 生成事件图谱
        # print("\n=== 步骤4: 生成事件图谱 ===")
        # from event.draft.GraphGenerator import EventGraphGenerator
        #
        # # 初始化图谱生成器
        # graph_generator = EventGraphGenerator(events_data=normalized_events)
        #
        # # 构建事件图谱
        # event_graph = graph_generator.build_event_graph(normalized_events)
        #
        # # 保存图谱
        # graph_path = os.path.join(meidan_path, "graph", "event_graph.json")
        # os.makedirs(os.path.dirname(graph_path), exist_ok=True)
        # with open(graph_path, 'w', encoding='utf-8') as f:
        #     json.dump(event_graph, f, ensure_ascii=False, indent=2)
        # print(f"✓ 事件图谱已保存到: {graph_path}")
        
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
        
        # # 使用未优化的图谱作为后续步骤的输入
        # optimized_graph = event_graph
        
        # 步骤6: 优化每月事件
        print("\n=== 步骤6: 优化每月事件 ===")
        from src.lifebench.event.draft.monthly_refine import MonthlyRefiner
        
        refined_months_path = os.path.join(meidan_path, "refined", "optimized_months.json") if meidan_path else None
        if refined_months_path and os.path.exists(refined_months_path):
            print(f"⊙ optimized_months.json 已存在，跳过月度事件优化步骤")
        else:
            # 初始化月度优化器
            monthly_refiner = MonthlyRefiner(filepath=output_path, year=2025, isprint=True)
            
            # 执行完整流程
            monthly_refiner.run_full_pipeline()
            print("✓ 每月事件优化完成")
        
        # 步骤7: 生成事件树与每日大纲
        print("\n=== 步骤7: 生成事件树与每日大纲 ===")
        
        # 1. 读取优化后的月度事件数据
        optimized_months_path = os.path.join(meidan_path, "refined", "optimized_months.json") if meidan_path else None
        optimized_monthly_status = None
        yearly_trends = {}
        if optimized_months_path and os.path.exists(optimized_months_path):
            try:
                with open(optimized_months_path, 'r', encoding='utf-8') as f:
                    optimized_monthly_status = json.load(f)
                print(f"✓ 已从 {optimized_months_path} 加载优化后的月度事件数据")
            except Exception as e:
                print(f"⚠️  加载优化后的月度数据失败: {e}")
        
        # 2. 读取年度趋势数据 (yearly_trends.json)
        trends_path = os.path.join(meidan_path, "refined", "yearly_trends.json") if meidan_path else None
        if trends_path and os.path.exists(trends_path):
            try:
                with open(trends_path, 'r', encoding='utf-8') as f:
                    yearly_trends = json.load(f)
                print(f"✓ 已加载年度趋势数据")
            except Exception as e:
                print(f"⚠️  加载年度趋势数据失败: {e}")
        
        if not optimized_monthly_status:
            print("⚠️  未找到优化后的月度数据，将尝试使用原始时间线数据")
            optimized_monthly_status = timeline_data

        # 2. 调用 event_tree.py 实现事件的分解（事件树生成）
        print("\n[Step 7.1] 开始进行事件树分解...")
        from src.lifebench.event.draft.event_tree import EventTree
        
        event_tree_path = os.path.join(meidan_path, "event_decompose_dfs.json") if meidan_path else None
        decomposed_events = []
        
        # 检查事件树文件是否已存在
        if event_tree_path and os.path.exists(event_tree_path):
            print(f"⊙ event_tree.json 已存在，跳过分解步骤，直接读取...")
            try:
                with open(event_tree_path, 'r', encoding='utf-8') as f:
                    decomposed_events = json.load(f)
                print(f"✓ 已加载事件树数据，包含 {len(decomposed_events)} 个节点")
            except Exception as e:
                print(f"⚠️  读取事件树文件失败: {e}，将重新执行分解")
                decomposed_events = []
        
        if not decomposed_events:
            # 初始化事件树分解器
            event_tree_decomposer = EventTree(persona=json.dumps(self.persona, ensure_ascii=False))
            
            # 合并所有月份的事件为一个列表，并重新分配 ID 和标准化字段
            all_events_flat = []
            current_id = 1
            
            # optimized_months.json 的结构是 {"2025-01": {"final_events": [...]}, ...}
            for month_str, month_data in optimized_monthly_status.items():
                if not isinstance(month_data, dict):
                    continue
                    
                # 尝试从 final_events 或 events 字段获取事件列表
                events = month_data.get("final_events") or month_data.get("events") or []
                
                # 如果 events 是字符串，尝试解析
                if isinstance(events, str):
                    try:
                        events = json.loads(events)
                    except:
                        events = []
                
                if not events:
                    continue
                    
                for event in events:
                    if not isinstance(event, dict):
                        continue
                        
                    # 深拷贝以避免修改原始数据
                    new_event = json.loads(json.dumps(event))
                    
                    # 重新分配 event_id
                    new_event['event_id'] = current_id
                    current_id += 1
                    
                    # 字段名转换: title -> name
                    if 'title' in new_event:
                        new_event['name'] = new_event.pop('title')
                    
                    # 字段名转换: time -> date
                    if 'time' in new_event:
                        new_event['date'] = new_event.pop('time')
                    
                    # 只保留核心字段：name, date, type, description, event_id
                    allowed_keys = {'name', 'date', 'type', 'description', 'event_id'}
                    keys_to_remove = [key for key in new_event.keys() if key not in allowed_keys]
                    for key in keys_to_remove:
                        del new_event[key]
                    
                    all_events_flat.append(new_event)
            
            print(f"✓ 已合并并标准化 {len(all_events_flat)} 个事件，准备进行分解...")
            
            # 调用 event_decomposer 进行整体分解（该方法直接保存文件，不返回结果）
            event_tree_decomposer.event_decomposer(all_events_flat, meidan_path)
        
        # 无论是否执行了分解，都从文件中读取最终的事件树数据
        decomposed_events = []
        if event_tree_path and os.path.exists(event_tree_path):
            try:
                with open(event_tree_path, 'r', encoding='utf-8') as f:
                    decomposed_events = json.load(f)
                print(f"✓ 已从 {event_tree_path} 加载事件树数据，包含 {len(decomposed_events)} 个节点")
            except Exception as e:
                print(f"⚠️  读取事件树文件失败: {e}")

        if not decomposed_events:
            print("⚠️  未能获取到事件树数据，跳过每日大纲生成步骤")
            return None

        # 3. 调用 daily_refine 生成每日大纲
        print("\n[Step 7.2] 开始生成每日详细大纲...")
        from src.lifebench.event.draft.daily_refine import DailyRefiner
        
        # 检查是否已存在最终的大纲文件，如果存在则跳过
        final_outline_path = os.path.join(meidan_path, "daily_draft.json") if meidan_path else None
        if final_outline_path and os.path.exists(final_outline_path):
            print(f"⊙ daily_draft.json 已存在，跳过大纲要素生成步骤")
        else:
            try:
                # 准备包含分解后事件的月度状态数据
                # 这里我们将分解后的事件重新组织回 monthly_details 结构，或者直接传递给 DailyRefiner
                # 为了简化，我们假设 DailyRefiner 能够处理分解后的事件列表
                refined_status_with_trees = {
                    "comprehensive_summary": optimized_monthly_status.get("comprehensive_summary", ""),
                    "monthly_details": []
                }
                
                # 将分解后的事件按月份重组（这里简化处理，实际可能需要更复杂的映射逻辑）
                # 由于 decompose_event_list 返回的是扁平列表，我们需要根据原事件的月份信息进行关联
                # 在实际应用中，EventTree 可能会返回带有月份信息的树形结构
                # 此处暂时直接使用 optimized_monthly_status，因为 DailyRefiner 内部会再次提取底层事件
                
                daily_refiner = DailyRefiner(
                    persona=self.persona,
                    events=decomposed_events, # 传入分解后的事件
                    monthly_status=optimized_monthly_status,
                    yearly_trends=yearly_trends,
                    record_folder=meidan_path
                )
                
                # 遍历每个月份调用 daily_event_refine
                all_month_outlines = []
                months_to_process = list(optimized_monthly_status.keys()) if isinstance(optimized_monthly_status, dict) else []
                
                # 使用12线程并行处理
                from concurrent.futures import ThreadPoolExecutor, as_completed
                print(f"\n开始并行精细化处理 {len(months_to_process)} 个月份...")
                
                with ThreadPoolExecutor(max_workers=12) as executor:
                    future_to_month = {
                        executor.submit(daily_refiner.daily_event_refine, month_str): month_str 
                        for month_str in months_to_process
                    }
                    
                    for future in as_completed(future_to_month):
                        month_str = future_to_month[future]
                        try:
                            outline_result = future.result()
                            if outline_result:
                                all_month_outlines.append(outline_result)
                                print(f"✓ 月份 {month_str} 精细化处理完成")
                        except Exception as e:
                            print(f"✗ 月份 {month_str} 处理失败: {e}")

                # 保存所有月份的大纲要素
                if meidan_path:
                    os.makedirs(meidan_path, exist_ok=True)
                    with open(final_outline_path, 'w', encoding='utf-8') as f:
                        json.dump(all_month_outlines, f, ensure_ascii=False, indent=2)
                    print(f"✓ 全年度每日大纲已保存到: {final_outline_path}")
                    
            except Exception as e:
                print(f"✗ 每日大纲生成失败: {e}")
                import traceback
                traceback.print_exc()
        
        # 步骤8: 优化每日大纲
        print("\n=== 步骤8: 优化每日大纲 ===")
        from src.lifebench.event.draft.outline_optimizer import OutlineOptimizer
        
        # 初始化大纲优化器
        outline_optimizer = OutlineOptimizer(output_path, meidan_path)
        
        # 执行大纲优化
        optimized_outline = outline_optimizer.optimize_outline()
        print("✓ 每日大纲优化完成")
        
        print("\n🎉 Draft生成完成！")
        return optimized_outline