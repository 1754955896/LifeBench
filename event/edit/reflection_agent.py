# -*- coding: utf-8 -*-
"""
反思 Agent (Reflection Agent)
负责分析执行效果，判断是否完成目标，并提供优化建议
"""

import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from utils.llm_call import llm_call_j


class CompletionStatus(Enum):
    """完成状态枚举"""
    COMPLETED = "completed"      # 已完成
    PARTIAL = "partial"          # 部分完成
    FAILED = "failed"            # 失败
    NEEDS_RETRY = "needs_retry"  # 需要重试
    NEEDS_CLARIFICATION = "needs_clarification"  # 需要澄清


@dataclass
class ReflectionResult:
    """反思结果数据结构"""
    status: CompletionStatus
    is_successful: bool          # 整体是否成功
    completion_rate: float       # 完成率 0.0-1.0
    analysis: str                # 详细分析
    issues: List[str]            # 发现的问题
    suggestions: List[str]       # 改进建议
    next_action: str             # 建议的下一步操作
    should_retry: bool = False   # 是否应该重试
    retry_plan: Optional[Dict] = None  # 重试计划


class ReflectionAgent:
    """
    反思 Agent
    负责评估执行结果，分析是否达到预期目标
    """
    
    def __init__(self, base_dir=None):
        self.base_dir = base_dir
        # 反思提示词模板
        self._reflection_template = """
你是一个数据编辑任务的反思评估 Agent，负责分析执行结果是否达到预期目标。

## 评估维度
1. 目标达成度：用户的原始指令是否被完全执行
2. 数据准确性：修改后的数据是否正确、完整
3. 副作用检查：是否有意外的数据变更
4. 逻辑一致性：操作是否符合业务逻辑
5. 执行质量评估：执行过程是否准确、高效

## 输出格式
严格输出 JSON 对象：
{{
  "status": "<completed|partial|failed|needs_retry|needs_clarification>",
  "is_successful": <true|false>,
  "completion_rate": <0.0-1.0>,
  "analysis": "<详细分析>",
  "issues": ["<问题1>", "<问题2>"],
  "suggestions": ["<建议1>", "<建议2>"],
  "next_action": "<建议的下一步操作：完成/重试/澄清/修复>",
  "should_retry": <true|false>,
  "retry_plan": {{
    "reason": "<重试原因>",
    "adjusted_params": {{}}
  }}
}}

## 原始指令
{original_command}

## 执行计划
{execution_plan}

## 执行结果
{execution_results}

请分析执行效果并输出评估结果。
"""
    
    def reflect(
        self,
        original_command: str,
        execution_plan: Any,
        execution_results: List[Any]
    ) -> ReflectionResult:
        """
        对执行结果进行反思评估
        
        Args:
            original_command: 原始用户指令
            execution_plan: 执行计划（可以是 ExecutionPlan 对象或字典）
            execution_results: 执行结果列表（可以是 ExecutionResult 对象或字典）
            
        Returns:
            ReflectionResult: 反思结果
        """
        print(f"[ReflectionAgent] 开始反思评估...")
        
        # 构建数据摘要
        data_summary = "无数据状态信息"
        
        # 处理执行计划
        plan_dict = execution_plan
        if hasattr(execution_plan, "to_dict"):
            # 调用 to_dict 方法获取字典表示
            plan_dict = execution_plan.to_dict()
        
        # 简化执行结果，只提取重要信息
        simplified_results = []
        for result in execution_results:
            if hasattr(result, "to_dict"):
                # 调用 to_dict 方法获取字典表示
                result_dict = result.to_dict()
            else:
                # 假设是字典
                result_dict = result
            
            simplified = {
                "operation_type": result_dict.get("operation_type"),
                "data_type": result_dict.get("data_type"),
                "data_after": result_dict.get("data_after")
            }
            simplified_results.append(simplified)
        
        # 构建提示词
        prompt = self._reflection_template.format(
            original_command=original_command,
            execution_plan=json.dumps(plan_dict, ensure_ascii=False, indent=2),
            execution_results=json.dumps(simplified_results, ensure_ascii=False, indent=2)
        )
        
        # 调用 LLM 进行反思
        try:
            llm_output = llm_call_j(prompt)
            reflection_data = json.loads(llm_output)
            
            return self._parse_reflection_result(reflection_data)
            
        except Exception as e:
            print(f"[ReflectionAgent] LLM 反思失败：{e}，使用本地评估")
            return self._local_reflect(original_command, execution_results)
    
    def quick_check(
        self,
        execution_results: List[Any],
        expected_count: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        快速检查执行结果
        
        Args:
            execution_results: 执行结果列表
            expected_count: 预期执行的操作数量
            
        Returns:
            快速检查结果
        """
        total = len(execution_results)
        successful = sum(1 for r in execution_results if getattr(r, 'success', False))
        failed = total - successful
        
        # 计算影响的数据条数
        affected = sum(getattr(r, 'affected_count', 0) for r in execution_results)
        
        status = CompletionStatus.COMPLETED
        if failed == total and total > 0:
            status = CompletionStatus.FAILED
        elif failed > 0:
            status = CompletionStatus.PARTIAL
        elif expected_count and total < expected_count:
            status = CompletionStatus.PARTIAL
        
        return {
            "status": status,
            "total_operations": total,
            "successful": successful,
            "failed": failed,
            "affected_count": affected,
            "success_rate": successful / total if total > 0 else 0.0
        }
    
    def compare_data(
        self,
        data_before: Dict,
        data_after: Dict,
        focus_keys: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        对比操作前后的数据变化
        
        Args:
            data_before: 操作前的数据
            data_after: 操作后的数据
            focus_keys: 关注的关键字段
            
        Returns:
            数据变化对比结果
        """
        changes = {
            "added": [],
            "removed": [],
            "modified": [],
            "unchanged": []
        }
        
        # 对比 daily_events
        if 'daily_event' in data_before or 'daily_event' in data_after:
            before_events = {e.get('event_id'): e for e in data_before.get('daily_event', [])}
            after_events = {e.get('event_id'): e for e in data_after.get('daily_event', [])}
            
            # 检查新增
            for event_id, event in after_events.items():
                if event_id not in before_events:
                    changes["added"].append({"type": "daily_event", "id": event_id, "data": event})
            
            # 检查删除
            for event_id, event in before_events.items():
                if event_id not in after_events:
                    changes["removed"].append({"type": "daily_event", "id": event_id, "data": event})
            
            # 检查修改
            for event_id in set(before_events.keys()) & set(after_events.keys()):
                before = before_events[event_id]
                after = after_events[event_id]
                if before != after:
                    diff = self._compute_diff(before, after, focus_keys)
                    if diff:
                        changes["modified"].append({
                            "type": "daily_event",
                            "id": event_id,
                            "diff": diff
                        })
        
        # 对比 daily_drafts
        if 'daily_draft' in data_before or 'daily_draft' in data_after:
            before_drafts = data_before.get('daily_draft', {})
            after_drafts = data_after.get('daily_draft', {})
            
            for draft_id in set(before_drafts.keys()) | set(after_drafts.keys()):
                if draft_id in after_drafts and draft_id not in before_drafts:
                    changes["added"].append({"type": "daily_draft", "id": draft_id})
                elif draft_id in before_drafts and draft_id not in after_drafts:
                    changes["removed"].append({"type": "daily_draft", "id": draft_id})
                elif before_drafts.get(draft_id) != after_drafts.get(draft_id):
                    changes["modified"].append({"type": "daily_draft", "id": draft_id})
        
        return changes
    
    def _build_data_summary(
        self,
        data_before: Optional[Dict],
        data_after: Optional[Dict]
    ) -> str:
        """构建数据状态摘要"""
        summary = []
        
        if data_before:
            summary.append("操作前：")
            if 'daily_event' in data_before:
                summary.append(f"  - daily_event: {len(data_before['daily_event'])} 条")
            if 'daily_draft' in data_before:
                summary.append(f"  - daily_draft: {len(data_before['daily_draft'])} 条")
            if 'phone_data' in data_before:
                phone = data_before['phone_data']
                total = sum(len(v) for v in phone.values())
                summary.append(f"  - phone_data: {total} 条（{len(phone)} 种类型）")
        
        if data_after:
            summary.append("操作后：")
            if 'daily_event' in data_after:
                summary.append(f"  - daily_event: {len(data_after['daily_event'])} 条")
            if 'daily_draft' in data_after:
                summary.append(f"  - daily_draft: {len(data_after['daily_draft'])} 条")
            if 'phone_data' in data_after:
                phone = data_after['phone_data']
                total = sum(len(v) for v in phone.values())
                summary.append(f"  - phone_data: {total} 条（{len(phone)} 种类型）")
        
        return "\n".join(summary) if summary else "无数据状态信息"
    
    def _parse_reflection_result(self, data: Dict) -> ReflectionResult:
        """解析 LLM 返回的反思结果"""
        status_str = data.get("status", "failed")
        try:
            status = CompletionStatus(status_str)
        except ValueError:
            status = CompletionStatus.FAILED
        
        retry_plan = data.get("retry_plan")
        
        # 处理 is_successful 字段，确保它是布尔值
        is_successful_value = data.get("is_successful", False)
        if isinstance(is_successful_value, str):
            # 更宽松的匹配，只要字符串中包含 "true" 就认为是 True
            is_successful_value = "true" in is_successful_value.lower()
        
        # 处理 should_retry 字段，确保它是布尔值
        should_retry_value = data.get("should_retry", False)
        if isinstance(should_retry_value, str):
            # 更宽松的匹配，只要字符串中包含 "true" 就认为是 True
            should_retry_value = "true" in should_retry_value.lower()
        
        return ReflectionResult(
            status=status,
            is_successful=is_successful_value,
            completion_rate=data.get("completion_rate", 0.0),
            analysis=data.get("analysis", ""),
            issues=data.get("issues", []),
            suggestions=data.get("suggestions", []),
            next_action=data.get("next_action", "未知"),
            should_retry=should_retry_value,
            retry_plan=retry_plan
        )
    
    def _local_reflect(
        self,
        original_command: str,
        execution_results: List[Any]
    ) -> ReflectionResult:
        """本地快速反思（LLM 失败时使用）"""
        quick = self.quick_check(execution_results)
        
        status = quick["status"]
        is_successful = quick["success_rate"] >= 0.8
        
        issues = []
        suggestions = []
        
        if quick["failed"] > 0:
            issues.append(f"有 {quick['failed']} 个操作执行失败")
            suggestions.append("检查失败原因并重试失败的操作")
        
        if quick["success_rate"] < 1.0:
            issues.append("部分操作未完全成功")
            suggestions.append("查看详细错误信息并修复")
        
        next_action = "完成" if is_successful else "修复问题"
        should_retry = status in [CompletionStatus.PARTIAL, CompletionStatus.FAILED]
        
        return ReflectionResult(
            status=status,
            is_successful=is_successful,
            completion_rate=quick["success_rate"],
            analysis=f"执行了 {quick['total_operations']} 个操作，成功 {quick['successful']} 个，成功率 {quick['success_rate']:.1%}",
            issues=issues,
            suggestions=suggestions,
            next_action=next_action,
            should_retry=should_retry,
            retry_plan=None
        )
    
    def _compute_diff(
        self,
        before: Dict,
        after: Dict,
        focus_keys: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """计算两个字典的差异"""
        diff = {}
        keys = focus_keys or set(before.keys()) | set(after.keys())
        
        for key in keys:
            before_val = before.get(key)
            after_val = after.get(key)
            if before_val != after_val:
                diff[key] = {"before": before_val, "after": after_val}
        
        return diff