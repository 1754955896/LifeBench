# -*- coding: utf-8 -*-
"""draft生成类，负责处理draft生成相关的操作"""
from src.lifebench.event.draft.timeline_gen import TimelineGen
from src.lifebench.event.edit.writing_agent import WritingAgent
from src.lifebench.event.draft.scheduler import Scheduler
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

        # 确保输出路径存在
        if meidan_path is None:
            meidan_path = os.path.join(output_path, 'process')
        os.makedirs(output_path, exist_ok=True)
        os.makedirs(meidan_path, exist_ok=True)

        # 检查 optimize_timeline.json 是否存在，存在则跳过步骤1-6
        optimize_timeline_path = os.path.join(meidan_path, "optimized_timelines.json")
        if optimize_timeline_path and os.path.exists(optimize_timeline_path):
            print(f"✓ optimize_timeline.json 已存在，跳过步骤1-6，直接调用 Scheduler")
        else:
            # 步骤1: 调用timeline_gen.py生成情节库
            print("\n=== 步骤1: 生成情节库 ===")
            timeline_gen = TimelineGen(self.persona, self.file_path)

            # 调用generate_yearly_timeline_plot方法生成情节库
            timeline_gen.generate_yearly_timeline_plot(self.persona, output_path, meidan_path)
            print(f"✓ 成功生成情节库")

            # 步骤2: 调用Interface_1.py唤起writing agent的接口
            print("\n=== 步骤2: 唤起writing agent ===")

            # 获取基础路径
            base_path = output_path
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

            # 保存当前情节到文件
            plot_path = os.path.join(meidan_path, "current_plot.json")
            with open(plot_path, 'w', encoding='utf-8') as f:
                json.dump(current_plot, f, ensure_ascii=False, indent=2)
            print(f"✓ 情节已保存到: {plot_path}")

            # 将当前情节转换为时间线格式
            timeline_data = {
                "comprehensive_summary": current_plot.get('comprehensive_summary', current_plot.get('yearly_summary', '')),
                "monthly_details": current_plot.get('monthly_details', current_plot.get('monthly_events', []))
            }

            # 保存为 optimize_timeline.json
            with open(optimize_timeline_path, 'w', encoding='utf-8') as f:
                json.dump(timeline_data, f, ensure_ascii=False, indent=2)
            print(f"✓ 时间线数据已保存到: {optimize_timeline_path}")

        # 步骤7: 调用 scheduler.py 的 generate_yearly_timeline_draft
        print("\n=== 步骤7: 调用 Scheduler 生成每日状态 ===")

        daily_draft_file = os.path.join(output_path, 'daily_draft.json')
        if os.path.exists(daily_draft_file):
            print(f"✓ daily_draft.json 已存在，跳过 Scheduler 调用")
        else:
            scheduler = Scheduler(persona=self.persona, file_path=output_path)
            scheduler.generate_yearly_timeline_draft(
                self.persona,
                output_path=output_path,
                meidan_path=meidan_path
            )

        # 步骤8: 调用 outline_optimizer.py 优化每日大纲
        print("\n=== 步骤8: 调用 OutlineOptimizer 优化每日大纲 ===")
        if os.path.exists(daily_draft_file):
            from src.lifebench.event.draft.outline_optimizer import OutlineOptimizer

            outline_optimizer = OutlineOptimizer(output_path, meidan_path)
            optimized_outline = outline_optimizer.optimize_outline()
            print("✓ 每日大纲优化完成")
        else:
            print("⚠️  daily_draft.json 不存在，跳过优化步骤")

        print("\n🎉 Draft生成完成！")
        return None