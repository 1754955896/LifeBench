# -*- coding: utf-8 -*-
"""
数据编辑代理系统 - 三 Agent 工作流版本
用于管理和修改日常事件、草稿和手机数据

工作流：PlanningAgent -> ExecutionAgent -> ReflectionAgent
"""

import json
import os
import copy
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

from src.lifebench.event.edit import PlanningAgent, ExecutionAgent, ReflectionAgent
from src.lifebench.event.edit.planning_agent import ExecutionPlan, OperationPlan
from src.lifebench.event.edit.execution_agent import ExecutionResult
from src.lifebench.event.edit.reflection_agent import ReflectionResult, CompletionStatus


@dataclass
class WorkflowResult:
    """完整工作流结果"""
    success: bool
    original_command: str
    execution_plan: Optional[ExecutionPlan]
    execution_results: List[ExecutionResult]
    reflection: Optional[ReflectionResult]
    final_message: str
    data_modified: bool = False


class DataEditorAgent:
    """
    数据编辑代理类（三 Agent 工作流）
    
    工作流程：
    1. PlanningAgent: 解析指令，生成执行计划
    2. ExecutionAgent: 执行具体操作，修改文件
    3. ReflectionAgent: 评估执行效果，判断是否完成
    """
    
    def __init__(self, base_dir: str, auto_save: bool = True, max_retries: int = 2):
        """
        初始化代理
        
        Args:
            base_dir: 基础数据目录路径
            auto_save: 是否自动保存修改到文件
            max_retries: 最大重试次数
        """
        if not base_dir:
            raise ValueError("base_dir 参数不能为空")
        
        self.base_dir = base_dir
        self.auto_save = auto_save
        self.max_retries = max_retries
        
        # 初始化三个核心 Agent
        self.planning_agent = PlanningAgent()
        self.execution_agent = ExecutionAgent(base_dir)
        self.reflection_agent = ReflectionAgent()
        
        # 工作流状态
        self._workflow_history: List[WorkflowResult] = []
        self._current_data_snapshot: Optional[Dict] = None
    
    def process_command(self, command_text: str, context: Optional[Dict] = None) -> WorkflowResult:
        """
        处理用户指令的完整工作流
        
        Args:
            command_text: 用户自然语言指令
            context: 可选的上下文信息
            
        Returns:
            WorkflowResult: 完整工作流结果
        """
        print(f"\n{'='*60}")
        print(f"[WORKFLOW] 开始处理指令：{command_text}")
        print(f"{'='*60}\n")
        
        # 步骤 0: 捕获数据快照（用于反思对比）
        self._capture_data_snapshot()
        
        # 步骤 1: Planning - 解析指令，生成执行计划
        execution_plan = self.planning_agent.plan(command_text, context)
        
        # 如果需要用户确认（删除或批量操作）
        if execution_plan.requires_confirmation:
            print(f"\n[WORKFLOW] 该操作需要确认：{execution_plan.summary}")
            print(f"[WORKFLOW] 预计执行 {execution_plan.estimated_steps} 个操作")
            # 实际应用中这里应该询问用户，现在自动继续
        
        # 步骤 2: Execution - 执行操作
        execution_results = self.execution_agent.execute_batch(execution_plan.operations)
        
        # 步骤 3: Reflection - 反思评估
        # 构建执行结果摘要
        results_summary = [
            {
                "success": r.success,
                "operation": r.operation_type,
                "message": r.message,
                "affected": r.affected_count
            }
            for r in execution_results
        ]
        
        # 获取当前数据状态
        current_data = self._get_current_data_state()
        
        reflection = self.reflection_agent.reflect(
            original_command=command_text,
            execution_plan={
                "summary": execution_plan.summary,
                "operations": [
                    {
                        "type": op.operation_type.value,
                        "data": op.data_type.value,
                        "target": op.target_path,
                        "desc": op.description
                    }
                    for op in execution_plan.operations
                ]
            },
            execution_results=results_summary,
            data_before=self._current_data_snapshot,
            data_after=current_data
        )
        
        # 步骤 4: 处理反思结果
        workflow_result = self._handle_reflection(
            command_text, execution_plan, execution_results, reflection
        )
        
        # 步骤 5: 保存修改（如果启用）
        if workflow_result.data_modified and self.auto_save:
            save_results = self.execution_agent.save_all()
            workflow_result.final_message += f"\n[SAVE] 保存结果：{save_results}"
        
        # 记录历史
        self._workflow_history.append(workflow_result)
        
        # 输出最终结果
        print(f"\n{'='*60}")
        print(f"[WORKFLOW] 执行完成")
        print(f"[WORKFLOW] 状态：{'成功' if workflow_result.success else '失败'}")
        print(f"[WORKFLOW] {workflow_result.final_message}")
        print(f"{'='*60}\n")
        
        return workflow_result
    
    def _handle_reflection(
        self,
        command_text: str,
        execution_plan: ExecutionPlan,
        execution_results: List[ExecutionResult],
        reflection: ReflectionResult
    ) -> WorkflowResult:
        """处理反思结果，决定下一步操作"""
        
        # 快速检查执行结果
        quick_check = self.reflection_agent.quick_check(execution_results)
        
        # 判断是否成功
        is_successful = reflection.is_successful and quick_check["success_rate"] >= 0.8
        data_modified = any(
            r.operation_type in ["add", "delete", "update"] 
            for r in execution_results
        )
        
        # 构建结果消息
        messages = [
            f"计划：{execution_plan.summary}",
            f"执行：{quick_check['successful']}/{quick_check['total_operations']} 个操作成功",
            f"影响：{quick_check['affected_count']} 条数据",
            f"反思：{reflection.analysis}"
        ]
        
        if reflection.issues:
            messages.append(f"问题：{'; '.join(reflection.issues)}")
        
        if reflection.suggestions:
            messages.append(f"建议：{'; '.join(reflection.suggestions)}")
        
        final_message = "\n".join(messages)
        
        return WorkflowResult(
            success=is_successful,
            original_command=command_text,
            execution_plan=execution_plan,
            execution_results=execution_results,
            reflection=reflection,
            final_message=final_message,
            data_modified=data_modified
        )
    
    def retry_last(self, feedback: Optional[str] = None) -> WorkflowResult:
        """
        重试上一次指令
        
        Args:
            feedback: 用户反馈，用于优化重试计划
            
        Returns:
            新的工作流结果
        """
        if not self._workflow_history:
            raise ValueError("没有可重试的历史记录")
        
        last_result = self._workflow_history[-1]
        command_text = last_result.original_command
        
        print(f"\n[WORKFLOW] 重试指令：{command_text}")
        
        # 如果有反馈，先优化计划
        if feedback and last_result.execution_plan:
            refined_plan = self.planning_agent.refine_plan(last_result.execution_plan, feedback)
            print(f"[WORKFLOW] 根据反馈优化计划")
        
        # 重新执行
        return self.process_command(command_text)
    
    def undo_last(self) -> Dict[str, Any]:
        """
        撤销上一次操作
        
        Returns:
            撤销结果
        """
        result = self.execution_agent.undo_last()
        
        if result.success and self.auto_save:
            self.execution_agent.save_all()
        
        return {
            "success": result.success,
            "message": result.message,
            "operation": result.operation_type
        }
    
    def get_workflow_history(self) -> List[WorkflowResult]:
        """获取工作流历史"""
        return self._workflow_history.copy()
    
    def _capture_data_snapshot(self):
        """捕获当前数据快照"""
        self._current_data_snapshot = self._get_current_data_state()
    
    def _get_current_data_state(self) -> Dict:
        """获取当前数据状态"""
        state = {}
        
        # 从 ExecutionAgent 的缓存获取数据
        cache = self.execution_agent._cache
        
        if 'daily_event' in cache:
            state['daily_event'] = copy.deepcopy(cache['daily_event'])
        
        if 'daily_draft' in cache:
            state['daily_draft'] = copy.deepcopy(cache['daily_draft'])
        
        if 'phone_data' in cache:
            state['phone_data'] = copy.deepcopy(cache['phone_data'])
        
        return state
    
    # ========== 便捷方法 ==========
    
    def load_all_data(self) -> None:
        """加载所有数据"""
        print("[AGENT] 正在加载所有数据...")
        
        # 触发 ExecutionAgent 加载数据
        self.execution_agent._load_daily_events()
        self.execution_agent._load_daily_drafts()
        self.execution_agent._load_phone_data()
        
        print("[AGENT] 数据加载完成")
    
    def save_all(self) -> Dict[str, bool]:
        """手动保存所有修改"""
        return self.execution_agent.save_all()
    
    def get_data_summary(self) -> Dict[str, Any]:
        """获取数据摘要"""
        cache = self.execution_agent._cache
        
        summary = {}
        
        if 'daily_event' in cache:
            summary['daily_event'] = len(cache['daily_event'])
        
        if 'daily_draft' in cache:
            summary['daily_draft'] = len(cache['daily_draft'])
        
        if 'phone_data' in cache:
            phone_summary = {}
            for dtype, data in cache['phone_data'].items():
                phone_summary[dtype] = len(data)
            summary['phone_data'] = phone_summary
        
        return summary


# 使用示例
if __name__ == "__main__":
    # 创建代理实例
    agent = DataEditorAgent(base_dir="./data", auto_save=False)
    
    # 加载数据
    agent.load_all_data()
    
    # 示例 1: 简单查询
    print("\n" + "="*60)
    print("示例 1: 查询数据")
    print("="*60)
    result = agent.process_command("查询所有日常事件")
    print(f"结果：{result.final_message}")
    
    # 示例 2: 添加数据
    print("\n" + "="*60)
    print("示例 2: 添加数据")
    print("="*60)
    result = agent.process_command(
        '添加一个日常事件，名称为"团队会议"，日期为2025-03-15，描述为"讨论项目进度"'
    )
    print(f"结果：{result.final_message}")
    
    # 示例 3: 复杂指令（多操作）
    print("\n" + "="*60)
    print("示例 3: 复杂指令")
    print("="*60)
    result = agent.process_command(
        "把2025-03-01的通话记录都删掉，然后添加一条张三的呼入记录"
    )
    print(f"结果：{result.final_message}")
    
    # 查看数据摘要
    print("\n" + "="*60)
    print("当前数据摘要：")
    print(agent.get_data_summary())
