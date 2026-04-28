#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
用户对话接口
实现与用户的交互，调用规划、执行和反思代理来实现循环修改
"""

import os
import sys
from typing import Optional, Dict, Any

# 添加项目根目录到路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from .planning_agent import PlanningAgent
from .execution_agent import ExecutionAgent
from .reflection_agent import ReflectionAgent


class UserInterface:
    """用户对话接口类"""
    
    def __init__(self, base_dir: Optional[str] = None):
        """
        初始化用户接口
        
        Args:
            base_dir: 基础目录路径
        """
        if base_dir is None:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        
        self.base_dir = base_dir
        self.planning_agent = PlanningAgent(base_dir=base_dir)
        self.execution_agent = ExecutionAgent(base_dir=base_dir)
        self.reflection_agent = ReflectionAgent(base_dir=base_dir)
        
        # 启用调试模式
        self.planning_agent.debug_mode = True
        
        # 加载数据
        self._load_data()
    
    def _load_data(self):
        """加载数据"""
        print("正在加载数据...")
        try:
            self.execution_agent._load_daily_events()
            self.execution_agent._load_daily_drafts()
            self.execution_agent._load_phone_data()
            print("数据加载完成")
        except Exception as e:
            print(f"加载数据时出错: {e}")
    
    def run_conversation(self):
        """运行对话"""
        print("=" * 60)
        print("欢迎使用事件编辑系统")
        print("输入您的指令，或输入 'exit' 退出")
        print("=" * 60)
        
        while True:
            # 获取用户输入
            command = input("\n请输入指令: ").strip()
            
            if command.lower() == 'exit':
                print("退出系统")
                break
            
            if not command:
                continue
            
            # 处理用户指令
            self._process_command(command)
    
    def _process_command(self, command: str, iteration: int = 1):
        """
        处理用户指令
        
        Args:
            command: 用户输入的指令
            iteration: 当前迭代次数
        """
        print(f"\n处理指令: {command}")
        print(f"当前迭代次数: {iteration}/3")
        print("-" * 60)
        
        # 检查迭代次数
        if iteration > 3:
            print("✗ 达到最大迭代次数，停止执行")
            return
        
        # 步骤 1: 规划
        print("[步骤 1] 正在生成执行计划...")
        try:
            plan = self.planning_agent.plan(command)
            print(f"✓ 规划完成")
            print(f"执行计划: {plan.summary}")
            print(f"估计步骤: {plan.estimated_steps}")
            print(f"是否需要确认: {'是' if plan.requires_confirmation else '否'}")
        except Exception as e:
            print(f"✗ 规划失败: {e}")
            return
        
        # 步骤 2: 执行
        print("\n[步骤 2] 正在执行操作...")
        try:
            results = self.execution_agent.execute_batch(plan.operations)
            print(f"✓ 执行完成")
            print(f"执行了 {len(results)} 个操作")
        except Exception as e:
            print(f"✗ 执行失败: {e}")
            return
        
        # 步骤 3: 反思
        print("\n[步骤 3] 正在反思评估...")
        try:
            reflection_result = self.reflection_agent.reflect(
                original_command=command,
                execution_plan=plan,
                execution_results=results
            )
            print(f"✓ 反思完成")
            print(f"反思结果: {'成功' if reflection_result.is_successful else '失败'}")
            print(f"反思建议: {reflection_result.suggestions[0] if reflection_result.suggestions else '无建议'}")
        except Exception as e:
            print(f"✗ 反思失败: {e}")
            return
        
        # 步骤 4: 根据反思结果决定是否需要重新执行
        if not reflection_result.is_successful:
            print("\n[步骤 4] 需要重新执行操作")
            print("反思建议: " + reflection_result.suggestions[0] if reflection_result.suggestions else "无建议")
            
            # 直接使用反思建议作为新指令重新执行
            new_command = reflection_result.suggestions[0] if reflection_result.suggestions else "重新执行操作"
            print(f"根据反思建议重新执行: {new_command}")
            self._process_command(new_command, iteration + 1)
        else:
            print("\n操作执行成功，无需重新执行")
            
        # 保存数据
        print("\n[步骤 5] 正在保存数据...")
        try:
            save_results = self.execution_agent.save_all()
            success = all(save_results.values())
            if success:
                print("✓ 数据保存完成")
            else:
                print(f"✗ 部分数据保存失败: {save_results}")
        except Exception as e:
            print(f"✗ 保存数据时出错: {e}")


if __name__ == "__main__":
    # 创建接口实例
    interface = UserInterface()
    
    # 运行对话
    interface.run_conversation()