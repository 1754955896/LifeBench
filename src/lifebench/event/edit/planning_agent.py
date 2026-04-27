# -*- coding: utf-8 -*-
"""
规划 Agent (Planning Agent)
负责解析用户指令，进行意图理解与操作规划

新工作流：
1. 解析指令 → 2. 拆分目标 → 3. 查询数据 → 4. 思考修改方式 → 5. 输出操作
"""

import json
import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from src.lifebench.utils.llm_call import llm_call_j, llm_call
from src.lifebench.event.templates.template_edit import (
    template_think_modification,
    template_format_operation_to_json,
    template_plan_query,
    template_analyze_and_group_goals,
    template_evaluate_task_complexity,
    template_execute_simple_task,
    OPERATION_FORMAT_DESCRIPTION
)
from .data_query_tool import DataQueryTool


class DataType(Enum):
    """数据类型枚举"""
    DAILY_EVENT = "daily_event"
    DAILY_DRAFT = "daily_draft"
    PHONE_DATA = "phone_data"


class OperationType(Enum):
    """操作类型枚举"""
    ADD = "add"
    DELETE = "delete"
    UPDATE = "update"
    QUERY = "query"
    WHOLE_DAY_REWRITE = "whole_day_rewrite"


class IndexMethod(Enum):
    """索引方式枚举"""
    BY_ID = "by_id"
    BY_DATE = "by_date"
    BY_DATE_RANGE = "by_date_range"  # 按日期范围查询（精细数据，最多2天）
    BY_DATE_RANGE_DRAFT = "by_date_range_draft"  # 按日期范围查询draft（粗略数据，防数据爆炸）
    BY_CONDITION = "by_condition"
    BY_DATE_RANGE_AND_CONDITION = "by_date_range_and_condition"  # 日期范围+条件复合查询


@dataclass
class OperationPlan:
    """操作计划数据结构"""
    operation_type: OperationType
    data_type: DataType
    target_path: str
    index_method: IndexMethod = IndexMethod.BY_CONDITION
    index_value: Any = None
    modification: Dict[str, Any] = field(default_factory=dict)
    params: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    priority: int = 0
    cascade_effects: List[str] = field(default_factory=list)  # 级联影响的事件ID
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "operation_type": self.operation_type.value,
            "data_type": self.data_type.value,
            "target_path": self.target_path,
            "index_method": self.index_method.value,
            "index_value": self.index_value,
            "modification": self.modification,
            "params": self.params,
            "description": self.description,
            "priority": self.priority,
            "cascade_effects": self.cascade_effects
        }


@dataclass
class ExecutionPlan:
    """完整执行计划"""
    operations: List[OperationPlan]
    summary: str = ""
    estimated_steps: int = 0
    requires_confirmation: bool = False
    thinking_process: Optional[Dict] = None  # 思考过程记录
    
    def to_dict(self) -> Dict[str, Any]:

        return {
            "operations": [op.to_dict() for op in self.operations],
            "summary": self.summary,
            "estimated_steps": self.estimated_steps,
            "requires_confirmation": self.requires_confirmation
        }


@dataclass
class PlanningGoal:
    """规划目标"""
    goal_id: str
    description: str
    data_type: DataType
    index_method: IndexMethod
    index_value: Any
    known_params: Dict[str, Any] = field(default_factory=dict)


class PlanningAgent:
    """
    规划 Agent（增强版）
    
    新工作流：
    1. 解析指令：理解用户意图
    2. 拆分目标：将复杂指令拆分为独立目标
    3. 查询数据：使用 DataQueryTool 获取相关数据
    4. 思考修改：分析影响，确定修改策略
    5. 输出操作：生成具体的 OperationPlan
    """
    
    def __init__(self, base_dir: Optional[str] = None):
        """
        初始化规划 Agent
        
        Args:
            base_dir: 基础数据目录路径（用于查询工具）
        """
        # 操作类型映射
        self._op_map = {
            "add": OperationType.ADD,
            "delete": OperationType.DELETE,
            "update": OperationType.UPDATE,
            "query": OperationType.QUERY,
            "whole_day_rewrite": OperationType.WHOLE_DAY_REWRITE,
        }
        # 数据类型映射
        self._dt_map = {
            "daily_event": DataType.DAILY_EVENT,
            "daily_draft": DataType.DAILY_DRAFT,
            "phone_data": DataType.PHONE_DATA,
        }
        # 索引方式映射
        self._index_map = {
            "by_id": IndexMethod.BY_ID,
            "by_date": IndexMethod.BY_DATE,
            "by_date_range": IndexMethod.BY_DATE_RANGE,
            "by_date_range_draft": IndexMethod.BY_DATE_RANGE_DRAFT,
            "by_condition": IndexMethod.BY_CONDITION,
            "by_date_range_and_condition": IndexMethod.BY_DATE_RANGE_AND_CONDITION,
        }
        
        # 初始化查询工具
        self.query_tool = DataQueryTool(base_dir) if base_dir else None
        
        # 是否启用深度思考模式
        self.enable_thinking = True
        
        # 调试模式：只有打开时才打印日志
        self.debug_mode = False
    
    def _log(self, message: str):
        """打印调试日志（仅在调试模式下）"""
        if self.debug_mode:
            print(message)
    
    def _log_sep(self, title: str = "", width: int = 50):
        """打印调试分隔线"""
        if not self.debug_mode:
            return
        if title:
            pad = max(1, (width - len(title) - 2) // 2)
            print(f"[PlanningAgent] {'─' * pad} {title} {'─' * pad}")
        else:
            print(f"[PlanningAgent] {'─' * width}")
    
    def plan(self, command_text: str, context: Optional[Dict] = None, use_thinking: bool = True) -> ExecutionPlan:
        """解析指令并生成执行计划（使用深度思考模式）"""
        # 统一使用深度思考模式
        return self._plan_with_thinking(command_text, context)
    

    def _plan_with_thinking(
        self,
        command_text: str,
        context: Optional[Dict]
    ) -> ExecutionPlan:
        """
        深度思考规划模式（新工作流）
        
        步骤：
        1. 目标拆分：将指令拆分为独立目标
        2. 思考获取数据：确定需要查询什么数据，调用 data_query_tool 获取
        3. 思考执行修改：根据影响程度决定修改范围
           - 影响不大、轻微、易实现 → 修改单个事件
           - 影响较大、复杂 → 修改一整天数据，保障事件连贯性
        4. 输出操作：生成具体操作计划
        """
        self._log_sep("深度思考规划")
        
        # ========== 步骤 1: 目标拆分 ==========
        self._log_sep("Step 1 · 目标拆分")
        goals = self._step1_split_goals(command_text)
        self._log(f"[PlanningAgent] 拆分结果  : 共 {len(goals)} 个目标")
        for g in goals:
            self._log(f"[PlanningAgent]   [{g.goal_id}] {g.description}  ({g.data_type.value})")
        
        # ========== 步骤 2: 思考获取数据并查询 ==========
        self._log_sep("Step 2 · 思考获取数据")
        goals_with_data = self._step2_query_data(goals)
        
        # ========== 步骤 3: 思考执行修改 ==========
        self._log_sep("Step 3 · 思考修改策略")
        modification_decisions = self._step3_think_modification(goals_with_data, command_text)
        
        # ========== 步骤 4: 输出操作 ==========
        self._log_sep("Step 4 · 生成操作列表")
        operations = self._step4_generate_operations(modification_decisions)
        
        if not operations:
            operations.append(self._create_query_plan(command_text))
        
        # 排序：删除优先，然后按优先级
        operations.sort(key=lambda x: (x.operation_type != OperationType.DELETE, x.priority))
        
        # 构建执行计划
        summary = self._generate_summary(command_text, goals, modification_decisions)
        
        execution_plan = ExecutionPlan(
            operations=operations,
            summary=summary,
            estimated_steps=len(operations),
            requires_confirmation=self._check_requires_confirmation(operations),
            thinking_process={
                "goals": [g.__dict__ for g in goals],
                "modification_decisions": modification_decisions
            }
        )
        
        self._log_sep("规划结果")
        self._log(f"[PlanningAgent] 摘要      : {execution_plan.summary}")
        self._log(f"[PlanningAgent] 需要确认  : {execution_plan.requires_confirmation}")
        self._log(f"[PlanningAgent] 操作列表  : 共 {len(operations)} 个")
        for i, op in enumerate(operations, 1):
            self._log(f"[PlanningAgent]   [{i}] {op.operation_type.value:8s} | {op.data_type.value:15s} | {op.description}")
        
        # 无论调试模式是否开启，始终打印最终摘要
        print(f"[PlanningAgent] ✓ 规划完成  : {execution_plan.summary}  ({len(operations)} 个操作)")
        
        return execution_plan
    
    def _step1_split_goals(self, command_text: str) -> List[PlanningGoal]:
        """
        步骤 1: 指令分析与目标分组（增强版）

        使用 LLM 分析指令，思考可能暗示/不完整之处，给出具体步骤，然后按时间范围分组：
        - 如果涉及修改时间只在两周之内，或者只修改某几天的数据，一轮上下文可以处理 → 不分组
        - 否则按时间范围/逻辑关联进行合理分组
        """
        prompt = template_analyze_and_group_goals.format(command_text=command_text)
        
        try:
            llm_output = llm_call_j(prompt)
            result = json.loads(llm_output)
            
            # 解析分析结果
            analysis = result.get("analysis", {})
            steps = result.get("steps", [])
            groups = result.get("groups", [])
            
            self._log(f"[PlanningAgent] 指令分析完成:")
            
            # 打印明确需求
            explicit_reqs = analysis.get('explicit_requirements', [])
            if explicit_reqs:
                self._log(f"  - 明确需求 ({len(explicit_reqs)}个):")
                for req in explicit_reqs[:5]:  # 最多显示 5 个
                    self._log(f"    • {req}")
                if len(explicit_reqs) > 5:
                    self._log(f"    ... 还有{len(explicit_reqs) - 5}个")
            
            # 打印暗示线索
            implicit_hints = analysis.get('implicit_hints', [])
            if implicit_hints:
                self._log(f"  - 暗示线索 ({len(implicit_hints)}个):")
                for hint in implicit_hints[:5]:
                    self._log(f"    • {hint}")
                if len(implicit_hints) > 5:
                    self._log(f"    ... 还有{len(implicit_hints) - 5}个")
            
            # 打印缺失信息
            missing_info = analysis.get('missing_info', [])
            if missing_info:
                self._log(f"  - 缺失信息 ({len(missing_info)}个):")
                for info in missing_info[:5]:
                    self._log(f"    • {info}")
                if len(missing_info) > 5:
                    self._log(f"    ... 还有{len(missing_info) - 5}个")
            
            # 打印常识推理
            common_sense = analysis.get('common_sense_inferences', [])
            if common_sense:
                self._log(f"  - 常识推理 ({len(common_sense)}个):")
                for inference in common_sense[:5]:
                    self._log(f"    • {inference}")
                if len(common_sense) > 5:
                    self._log(f"    ... 还有{len(common_sense) - 5}个")
            
            # 打印步骤详情
            if steps:
                self._log(f"  - 步骤数量：{len(steps)}个")
                for step in steps[:5]:  # 最多显示 5 个步骤
                    step_id = step.get('step_id', '')
                    op_type = step.get('operation_type', '')
                    date_involved = step.get('date_involved', '')
                    desc = step.get('description', '')[:50]
                    self._log(f"    [{step_id}] {op_type} | {date_involved} | {desc}...")
                if len(steps) > 5:
                    self._log(f"    ... 还有{len(steps) - 5}个步骤")
            
            # 打印分组详情
            if groups:
                self._log(f"  - 分组数量：{len(groups)}个")
                for group in groups:
                    group_id = group.get('group_id', '')
                    group_name = group.get('group_name', '')
                    date_range = group.get('date_range', {})
                    start_date = date_range.get('start_date', '')
                    end_date = date_range.get('end_date', '')
                    span_days = date_range.get('span_days', 0)
                    actual_days = date_range.get('actual_modified_days', 0)
                    step_count = len(group.get('steps', []))
                    context_load = group.get('estimated_context_load', 'medium')
                    self._log(f"    [{group_id}] {group_name}")
                    self._log(f"         时间范围：{start_date} ~ {end_date} (跨度{span_days}天，实际修改{actual_days}天)")
                    self._log(f"         包含{step_count}个步骤 | 上下文负载：{context_load}")
            
            # 根据分组创建目标
            goals = []
            for group in groups:
                group_step_ids = group.get("steps", [])  # 这是 step_id 列表，如 ["s1", "s2"]
                if not group_step_ids:
                    continue
                
                # 从总 steps 中找到对应的完整步骤对象
                group_steps = [step for step in steps if step.get("step_id") in group_step_ids]
                
                # 为每个组创建一个综合目标
                goal = PlanningGoal(
                    goal_id=group.get("group_id", f"g{len(goals)+1}"),
                    description=f"{group.get('group_name', '未命名组')} - 包含{len(group_steps)}个步骤",
                    data_type=DataType.DAILY_EVENT,  # 默认类型，后续可调整
                    index_method=IndexMethod.BY_DATE_RANGE,  # 使用日期范围查询
                    index_value={
                        "start_date": group.get("date_range", {}).get("start_date"),
                        "end_date": group.get("date_range", {}).get("end_date"),
                        "group_info": {
                            "steps": group_steps,
                            "context_load": group.get("estimated_context_load", "medium")
                        }
                    },
                    known_params={
                        "group_rationale": group.get("rationale", ""),
                        "execution_order": group.get("group_id"),
                        "detailed_steps": group_steps  # 新增：保存完整步骤对象
                    }
                )
                goals.append(goal)
            
            # 如果没有分组或分组失败，使用单一步骤
            if not goals and steps:
                self._log(f"[PlanningAgent] 无分组信息，使用默认单步处理")
                # 从步骤中提取日期范围
                all_dates = []
                for step in steps:
                    date_involved = step.get("date_involved", "")
                    if "~" in date_involved:
                        dates = date_involved.split("~")
                        all_dates.extend(dates)
                    elif date_involved:
                        all_dates.append(date_involved)
                
                start_date = min(all_dates) if all_dates else None
                end_date = max(all_dates) if all_dates else None
                
                goal = PlanningGoal(
                    goal_id="g1",
                    description=command_text,
                    data_type=DataType.DAILY_EVENT,
                    index_method=IndexMethod.BY_DATE_RANGE if (start_date and end_date) else IndexMethod.BY_CONDITION,
                    index_value={
                        "start_date": start_date,
                        "end_date": end_date,
                        "steps": steps
                    } if (start_date and end_date) else {"steps": steps},
                    known_params={
                        "detailed_steps": steps  # 新增：保存详细步骤
                    }
                )
                goals.append(goal)
            
            # 如果连步骤都没有，使用最简目标
            if not goals:
                self._log(f"[PlanningAgent] 无步骤信息，使用最简目标")
                goal = PlanningGoal(
                    goal_id="g1",
                    description=command_text,
                    data_type=DataType.DAILY_EVENT,
                    index_method=IndexMethod.BY_CONDITION,
                    index_value={},
                    known_params={
                        "detailed_steps": []  # 空步骤列表
                    }
                )
                goals.append(goal)
            
            return goals
            
        except Exception as e:
            self._log(f"[PlanningAgent] ✗ 目标拆分失败：{e}，使用默认目标")
            return [PlanningGoal(
                goal_id="g1",
                description=command_text,
                data_type=DataType.DAILY_EVENT,
                index_method=IndexMethod.BY_CONDITION,
                index_value={},
                known_params={}
            )]
    
    def _step2_query_data(self, goals: List[PlanningGoal]) -> List[Dict]:
        """
        步骤 2: 思考获取数据并查询
        
        对每个目标：
        1. 思考需要获取什么数据
        2. 确定索引方式（by_id/by_date/by_condition）
        3. 调用 data_query_tool 获取数据
        """
        if not self.query_tool:
            self._log("[PlanningAgent] 未配置查询工具，跳过数据查询")
            return [{"goal": g, "queried_data": None, "index_decision": "by_condition"} for g in goals]
        
        results = []
        
        for goal in goals:
            # 构建增强的目标描述（包含详细步骤）
            enhanced_goal_description = self._build_enhanced_goal_description(goal)
            
            self._log(f"[PlanningAgent] ┌ 目标 [{goal.goal_id}] {enhanced_goal_description}")
            
            # 使用 LLM 思考应该用什么方式查询
            prompt = template_plan_query.format(
                goal_description=enhanced_goal_description,
                data_type=goal.data_type.value,
                index_value=json.dumps(goal.index_value, ensure_ascii=False)
            )
            
            try:
                llm_output = llm_call_j(prompt)
                decision = json.loads(llm_output)
                
                index_method = self._index_map.get(
                    decision.get("index_method", "by_condition"),
                    IndexMethod.BY_CONDITION
                )
                index_value = decision.get("index_value", goal.index_value)
                
                self._log(f"[PlanningAgent] │ 索引方式  : {index_method.value}  →  {index_value}")
                self._log(f"[PlanningAgent] │ 理由      : {decision.get('rationale', '')}")
                
                # 更新目标的索引方式
                goal.index_method = index_method
                goal.index_value = index_value
                
                # 执行查询
                queried_data = self._execute_query(goal)
                
                # 查询相关事件（用于后续影响分析）
                related_data = None
                if goal.data_type == DataType.DAILY_EVENT and queried_data:
                    related_data = self._query_related_for_analysis(queried_data)
                
                data_count = len(queried_data) if isinstance(queried_data, list) else (1 if queried_data else 0)
                related_count = len(related_data) if related_data else 0
                self._log(f"[PlanningAgent] │ 查询结果  : {data_count} 条目标数据，{related_count} 条同日关联数据")
                self._log(f"[PlanningAgent] └─────────────────────────────────")
                
                results.append({
                    "goal": goal,
                    "queried_data": queried_data,
                    "related_data": related_data,
                    "index_decision": decision
                })
                
            except Exception as e:
                self._log(f"[PlanningAgent] │ ✗ 查询决策失败：{e}")
                self._log(f"[PlanningAgent] └─────────────────────────────────")
                results.append({
                    "goal": goal,
                    "queried_data": None,
                    "error": str(e)
                })
        
        return results
    
    def _execute_query(self, goal: PlanningGoal) -> Any:
        """执行具体查询（复用_execute_query_by_type）"""
        # 将 PlanningGoal 转换为 query dict 格式
        query = {
            "query_type": goal.index_method.value,
            "target": goal.index_value
        }
        return self._execute_query_by_type(query, goal.data_type.value)

    def _query_related_for_analysis(self, queried_data: Any) -> List[Dict]:
        """查询相关数据用于影响分析"""
        if not isinstance(queried_data, dict):
            return []
        
        event_id = queried_data.get("event_id")
        if not event_id:
            return []
        
        try:
            return self.query_tool.query_related_events(event_id, "same_date")
        except:
            return []
    
    def _build_enhanced_goal_description(self, goal: PlanningGoal) -> str:
        """
        构建增强的目标描述，包含详细步骤信息
        
        Args:
            goal: PlanningGoal 对象
            
        Returns:
            包含详细步骤的增强描述字符串
        """
        base_description = goal.description
        detailed_steps = goal.known_params.get("detailed_steps", [])
        
        # 如果没有详细步骤，直接返回原始描述
        if not detailed_steps:
            return base_description
        
        # 构建步骤详情（不限制数量，全部显示）
        steps_detail = []
        for step in detailed_steps:
            step_id = step.get("step_id", "N/A")
            date_info = step.get("date_involved", "")
            desc = step.get("description", "")
            content_outline = step.get("content_outline", "")
            
            # 构建简洁的步骤描述：只显示日期和描述
            step_parts = [f"  [{step_id}]"]
            
            if date_info:
                step_parts.append(f"@ {date_info}")
            
            # 添加详细描述
            detail_parts = []
            if desc:
                detail_parts.append(desc)
            if content_outline:
                detail_parts.append(content_outline)
            
            if detail_parts:
                step_parts.append(f"| {' '.join(detail_parts)}")
            
            steps_detail.append(' '.join(step_parts))
        
        # 组合完整描述
        enhanced = f"{base_description}\n\n具体步骤:\n" + "\n".join(steps_detail)
        
        return enhanced
    
    def _step3_think_modification(
        self,
        goals_with_data: List[Dict],
        original_command: str,
        max_iterations: int = 5
    ) -> List[Dict]:
        """
        步骤 3: 思考执行修改（智能分流版）
            
        根据任务复杂度进行分流处理：
        - **简单任务**：直接调用简单任务执行模板，一次性生成操作方案
        - **复杂任务**：采用迭代式分析，多轮交互制定策略
        
        Args:
            goals_with_data: 已查询数据的目标列表
            original_command: 原始用户指令
            max_iterations: 复杂任务的最大迭代轮次
            
        Returns:
            决策列表，每个决策包含策略和执行方案
        """
        decisions = []
            
        for item in goals_with_data:
            goal = item["goal"]
            data = item.get("queried_data")
            related = item.get("related_data", [])
            
            # 构建增强的目标描述（包含详细步骤）
            enhanced_goal_description = self._build_enhanced_goal_description(goal)
            print(enhanced_goal_description)
            self._log(f"[PlanningAgent] ┌ 目标 [{goal.goal_id}] {enhanced_goal_description}")
                
            # 初始化数据字符串（只保留主要字段，防止数据过大）
            if not data:
                data_str = "未查询到匹配数据"
            else:
                # 对 daily_event 类型，只保留主要字段
                if goal.data_type == DataType.DAILY_EVENT:
                    data_str = self._extract_main_fields(data)
                else:
                    data_str = json.dumps(data, ensure_ascii=False, indent=2) if isinstance(data, dict) else str(data)
            
            # ========== 第一步：评估任务复杂度 ==========
            self._log(f"[PlanningAgent] │ 评估任务复杂度...")
            
            complexity_prompt = template_evaluate_task_complexity.format(
                original_command=original_command,
                goal_description=enhanced_goal_description,
                data_str=data_str
            )
            
            try:
                complexity_output = llm_call_j(complexity_prompt)
                complexity_result = json.loads(complexity_output)
                
                task_type = complexity_result.get("task_type", "complex")
                confidence = complexity_result.get("confidence", "medium")
                rationale = complexity_result.get("rationale", "")
                
                self._log(f"[PlanningAgent] │ 任务类型  : {task_type} (置信度：{confidence})")
                self._log(f"[PlanningAgent] │ 分类理由  : {rationale}")
                
                # 根据任务类型选择不同的处理路径
                if task_type == "simple":
                    self._log(f"[PlanningAgent] │ → 进入【简单任务】直接执行流程")
                    operations_list = self._execute_simple_task(
                        original_command, goal, data_str, complexity_result
                    )
                else:
                    self._log(f"[PlanningAgent] │ → 进入【复杂任务】迭代分析流程")
                    operations_list = self._analyze_complex_task_iteratively(
                        original_command, goal, data_str, related, max_iterations
                    )
                
                # 记录决策结果（现在 operations_list 是操作数组）
                self._log(f"[PlanningAgent] │ └─────────────────────────────────")
                
                decisions.append({
                    "goal": goal,
                    "data": data,
                    "related": related,
                    "task_type": task_type,
                    "confidence": confidence,
                    "operations": operations_list  # 保存操作列表
                })
                
            except Exception as e:
                self._log(f"[PlanningAgent] │ ✗ 任务评估失败：{e}，降级为复杂任务处理")
                # 降级处理：使用迭代分析方法
                operations_list = self._analyze_complex_task_iteratively(
                    original_command, goal, data_str, related, max_iterations
                )
                
                decisions.append({
                    "goal": goal,
                    "data": data,
                    "related": related,
                    "task_type": "complex",
                    "confidence": "fallback",
                    "operations": operations_list  # 保存操作列表
                })
        
        return decisions
    
    def _execute_simple_task(
        self,
        original_command: str,
        goal: PlanningGoal,
        data_str: str,
        complexity_result: Dict
    ) -> List[Dict]:
        """
        简单任务直接执行
        
        Args:
            original_command: 原始指令
            goal: 规划目标
            data_str: 数据字符串
            complexity_result: 复杂度评估结果
            
        Returns:
            操作列表（JSON 数组）
        """
        try:
            prompt = template_execute_simple_task.format(
                goal_description=self._build_enhanced_goal_description(goal),
                data_str=data_str
            )
            
            llm_output = llm_call(prompt)
            
            # 打印 LLM 原始输出
            self._log(f"[PlanningAgent] │ ✓ LLM 原始输出:\n{llm_output}...")
            
            # 提取 <operation> 标签中的内容
            operation_text = self._extract_operation_from_llm_output(llm_output)
            
            if not operation_text:
                self._log(f"[PlanningAgent] │ ✗ 未找到 <operation> 标签，使用原始文本作为操作列表")
                operation_text = llm_output
            
            # 使用操作生成 prompt 来格式化操作列表
            json_prompt = template_format_operation_to_json.format(
                goal_description=goal.description,
                operation_text=operation_text,
                operation_format=OPERATION_FORMAT_DESCRIPTION
            )
            json_output = llm_call_j(json_prompt)
            operations_list = json.loads(json_output)
            
            self._log(f"[PlanningAgent] │ ✓ 简单任务执行完成，共 {len(operations_list)} 个操作")
            
            # 打印操作列表
            for i, op in enumerate(operations_list, 1):
                op_type = op.get("operation_type", "unknown")
                target_id = op.get("target_id", "N/A")
                target_date = op.get("target_date", "N/A")
                self._log(f"[PlanningAgent] │   操作{i}: {op_type} - {target_id if target_id != 'N/A' else target_date};{op.get('fields', 'N/A')}")
            
            return operations_list
            
        except Exception as e:
            self._log(f"[PlanningAgent] │ ✗ 简单任务执行失败：{e}")
            return []
    
    def _extract_operation_from_llm_output(self, llm_output: str) -> Optional[str]:
        """
        从 LLM 输出中提取 <operation> 标签内的内容
        
        Args:
            llm_output: LLM 的完整输出
            
        Returns:
            <operation>标签内的内容，如果未找到则返回 None
        """
        # 使用正则表达式提取 <operation>...</operation>
        pattern = r'<operation>(.*?)</operation>'
        match = re.search(pattern, llm_output, re.DOTALL)
        
        if match:
            operation_text = match.group(1).strip()
            self._log(f"[PlanningAgent] │ ✓ 提取到 <operation> 标签内容")
            return operation_text
        
        return None
    
    def _convert_queries_to_operations(self, queries: List[Dict]) -> List[Dict]:
        """
        将解析后的 queries 转换为标准操作列表格式
        
        Args:
            queries: 解析后的查询列表
            
        Returns:
            操作列表（JSON 数组）
        """
        operations = []
        
        for query in queries:
            op_dict = {
                "operation_type": "update",  # 默认
                "fields": {}
            }
            
            # 优先使用已解析的 operation_type
            if "operation_type" in query:
                op_dict["operation_type"] = query["operation_type"]
            else:
                # 根据 query 的内容推断 operation_type
                op_text = query.get("reason", "").lower()
                
                if "delete" in op_text or "删除" in op_text:
                    op_dict["operation_type"] = "delete"
                elif "add" in op_text or "新增" in op_text:
                    op_dict["operation_type"] = "add"
                elif "rewrite" in op_text or "重写" in op_text:
                    op_dict["operation_type"] = "whole_day_rewrite"
                else:
                    op_dict["operation_type"] = "update"
            
            # 提取 target_id 或 target_date
            target = query.get("target", "")
            if target.startswith("evt_") or len(target) > 10:
                op_dict["target_id"] = target
            else:
                # 可能是日期
                op_dict["target_date"] = target
            
            # 使用已解析的 fields
            if "fields" in query and isinstance(query["fields"], dict):
                op_dict["fields"] = query["fields"]
            
            operations.append(op_dict)
        
        return operations
    
    def _analyze_complex_task_iteratively(
        self,
        original_command: str,
        goal: PlanningGoal,
        data_str: str,
        related_data: List,
        max_iterations: int = 5
    ) -> List[Dict]:
        """
        复杂任务迭代分析（原有逻辑）
            
        Args:
            original_command: 原始指令
            goal: 规划目标
            data_str: 数据字符串
            related_data: 相关数据
            max_iterations: 最大迭代轮次
                
        Returns:
            操作列表（JSON 数组）
        """
        previous_output = "无"
        final_operation_text = ""
                        
        for iteration in range(1, max_iterations + 1):
            self._log(f"[PlanningAgent] │ 迭代轮次：{iteration}/{max_iterations}")
                            
            # 构建分析提示
            prompt = template_think_modification.format(
                original_command=original_command,
                goal_description=self._build_enhanced_goal_description(goal),
                data_str=data_str,
                previous_output=previous_output
            )
                
            try:
                llm_output = llm_call(prompt)
                    
                # 解析输出标签
                thinking_text = self._extract_tag(llm_output, "thinking")
                operation_text = self._extract_tag(llm_output, "operation")
                task_text = self._extract_tag(llm_output, "task")
                data_text = self._extract_tag(llm_output, "data")
                finish_text = self._extract_tag(llm_output, "finish")
                    
                # 检查是否完成
                is_complete = "true" in finish_text.lower() or "是否完成：true" in finish_text.lower()
                    
                # 保存当前 operation
                if operation_text and operation_text != "待定":
                    final_operation_text = operation_text
                    
                # 详细打印本轮输出
                self._log(f"[PlanningAgent] │ ┌─ 思考过程 ─")
                self._log(f"[PlanningAgent] │ │ <thinking>:" )
                for line in thinking_text.split('\n'):
                    self._log(f"[PlanningAgent] │ │   {line}")
                self._log(f"[PlanningAgent] │ │ </thinking>")
                self._log(f"[PlanningAgent] │ └─")
                self._log(f"[PlanningAgent] │")
                self._log(f"[PlanningAgent] │ ┌─ 解析结果 ─")
                self._log(f"[PlanningAgent] │ │ <operation>:" )
                for line in operation_text.split('\n'):
                    self._log(f"[PlanningAgent] │ │   {line}")
                self._log(f"[PlanningAgent] │ │ <task>:" )
                for line in task_text.split('\n'):
                    self._log(f"[PlanningAgent] │ │   {line}")
                self._log(f"[PlanningAgent] │ │ <data>:" )
                for line in data_text.split('\n'):
                    self._log(f"[PlanningAgent] │ │   {line}")
                self._log(f"[PlanningAgent] │ │ <finish>:" )
                for line in finish_text.split('\n'):
                    self._log(f"[PlanningAgent] │ │   {line}")
                self._log(f"[PlanningAgent] │ └─")
                self._log(f"[PlanningAgent] │")
                self._log(f"[PlanningAgent] │ 是否完成：{is_complete}")
                    
                # 如果完成或达到最大轮次，退出迭代
                if is_complete or iteration >= max_iterations:
                    if iteration >= max_iterations and not is_complete:
                        self._log(f"[PlanningAgent] │ ⚠ 达到最大轮次 ({max_iterations})，采用当前策略")
                    break
                    
                # 解析需要查询的数据
                queries = self._parse_data_queries(data_text)
                    
                # 执行数据查询
                if queries and self.query_tool:
                    new_data_results = []
                    for query in queries:
                        self._log(f"[PlanningAgent] │ 执行查询：{query.get('query_type')} -> {query.get('target')}")
                        result = self._execute_query_by_type(query, goal.data_type.value)
                        if result:
                            if goal.data_type == DataType.DAILY_EVENT:
                                result_str = self._extract_main_fields(result)
                            else:
                                result_str = json.dumps(result, ensure_ascii=False, indent=2) if isinstance(result, (dict, list)) else str(result)
                            new_data_results.append(result_str)
                        else:
                            self._log(f"[PlanningAgent] │ 查询结果：无数据")
                        
                    # 更新数据字符串
                    if new_data_results:
                        data_str += "\n\n## 新查询数据\n" + "\n".join(new_data_results)
                        self._log(f"[PlanningAgent] │ 已更新数据上下文，新增 {len(new_data_results)} 条数据")
                    
                # 更新上一轮输出
                previous_output = llm_output
                self._log(f"[PlanningAgent] │ ─────────────────────────────")
                    
            except Exception as e:
                self._log(f"[PlanningAgent] │ ✗ 迭代失败：{e}")
                break
            
        # 最后一轮：将 operation 格式化为 JSON
        try:
            if final_operation_text:
                json_prompt = template_format_operation_to_json.format(
                    goal_description=goal.description,
                    operation_text=final_operation_text,
                    operation_format=OPERATION_FORMAT_DESCRIPTION
                )
                json_output = llm_call_j(json_prompt)
                operations_list = json.loads(json_output)  # 返回的是数组格式
                    
                self._log(f"[PlanningAgent] │ ✓ 复杂任务分析完成，共 {len(operations_list)} 个操作")
                    
                # 打印操作列表
                for i, op in enumerate(operations_list, 1):
                    op_type = op.get("operation_type", "unknown")
                    target_id = op.get("target_id", "N/A")
                    target_date = op.get("target_date", "N/A")
                    self._log(f"[PlanningAgent] │   操作{i}: {op_type} - {target_id if target_id != 'N/A' else target_date} - {op.get('fields', 'N/A')}")
                    
                return operations_list
            else:
                # 没有制定任何策略，返回空列表
                self._log(f"[PlanningAgent] │ ⚠ 未能制定有效策略")
                return []
                
        except Exception as e:
            self._log(f"[PlanningAgent] │ ✗ JSON 格式化失败：{e}")
            return []

    def _extract_tag(self, text: str, tag_name: str) -> str:
        """从文本中提取指定标签的内容"""
        import re
        pattern = f"<{tag_name}>(.*?)</{tag_name}>"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return ""
    
    def _extract_main_fields(self, data: Any) -> str:
        """
        提取 daily_event 的主要字段，避免数据过大
        
        Args:
            data: 原始数据（dict 或 list）
            
        Returns:
            只包含主要字段的 JSON 字符串
        """
        allowed_fields = {'event_id', 'name', 'date', 'description','location'}
        
        def extract_single_event(event: Dict) -> Dict:
            """提取单个事件的主要字段"""
            if not isinstance(event, dict):
                return event
            return {k: v for k, v in event.items() if k in allowed_fields}
        
        if isinstance(data, list):
            # 如果是列表，对每个事件提取主要字段
            filtered_data = [extract_single_event(event) for event in data]
        elif isinstance(data, dict):
            # 如果是单个字典，直接提取主要字段
            filtered_data = extract_single_event(data)
        else:
            # 其他类型保持原样
            filtered_data = data
        
        return json.dumps(filtered_data, ensure_ascii=False, indent=2)
    
    def _parse_data_queries(self, data_text: str) -> List[Dict]:
        """
        解析数据查询需求或操作列表
            
        支持两种格式：
        1. 旧格式：查询 1: by_date | 2025-10-01 | 原因
        2. 新格式：- 操作 1: update evt_123 - start_time=15:00
        """
        queries = []
        lines = data_text.strip().split('\n')
            
        for line in lines:
            line = line.strip()
                
            # 尝试新格式：- 操作 1: update evt_123 - start_time=15:00
            if line.startswith('- 操作') or line.startswith('操作'):
                # 提取操作信息
                # 格式：- 操作 N: [operation_type] [target] - [fields]
                match = re.match(r'-?\s*操作\s*\d*:\s*(\w+)\s+(\S+)(?:\s*-\s*(.+))?', line)
                if match:
                    op_type = match.group(1).strip()
                    target = match.group(2).strip()
                    fields_str = match.group(3).strip() if match.group(3) else ""
                        
                    # 解析 fields (key=value 格式)
                    fields = {}
                    if fields_str:
                        for kv_pair in fields_str.split(','):
                            if '=' in kv_pair:
                                key, value = kv_pair.split('=', 1)
                                fields[key.strip()] = value.strip()
                        
                    queries.append({
                        "operation_type": op_type,
                        "target": target,
                        "reason": fields_str,  # 用于推断 operation_type
                        "fields": fields
                    })
                
            # 兼容旧格式：查询 1: by_date | 2025-10-01 | 原因
            elif line.startswith('- 查询') or line.startswith('查询'):
                parts = line.split('|')
                if len(parts) >= 3:
                    query_type = parts[0].split(':')[-1].strip()
                    target = parts[1].strip()
                    reason = parts[2].strip()
                    queries.append({
                        "query_type": query_type,
                        "target": target,
                        "reason": reason
                    })
            
        return queries
    
    def _execute_query_by_type(self, query: Dict, data_type: str) -> Any:
        """根据查询类型执行查询
            
        支持的查询类型：
        - by_id: 按 ID 查询（调用 DataQueryTool.query_by_id）
        - by_date: 按日期查询（调用 DataQueryTool.query_by_date）
        - by_date_range: 按日期范围查询（调用 DataQueryTool.query_by_date_range）
        - by_date_range_draft: 按日期范围查询 daily_draft（调用 DataQueryTool.query_by_date_range_draft）
        """
        try:
            query_type = query.get("query_type", "")
            target = query.get("target", "")
                
            if "by_id" in query_type:
                return self.query_tool.query_by_id(data_type, target)
                
            elif "by_date_range_draft" in query_type:
                # Draft 日期范围查询（粗略数据，数据量小）- 固定查询 daily_draft.json
                try:
                    range_obj = json.loads(target) if isinstance(target, str) else target
                    if isinstance(range_obj, dict):
                        start_date = range_obj.get("start_date")
                        end_date = range_obj.get("end_date")
                        if start_date and end_date:
                            return self.query_tool.query_by_date_range_draft(start_date, end_date)
                except:
                    return None
                    
            elif "by_date_range" in query_type:
                # 日期范围查询
                try:
                    range_obj = json.loads(target) if isinstance(target, str) else target
                    if isinstance(range_obj, dict):
                        start_date = range_obj.get("start_date")
                        end_date = range_obj.get("end_date")
                        if start_date and end_date:
                            return self.query_tool.query_by_date_range(data_type, start_date, end_date)
                except Exception as e:
                    self._log(f"[PlanningAgent] │ ✗ by_date_range 解析失败：{e}")
                    return None
                    
            elif "by_date" in query_type:
                return self.query_tool.query_by_date(data_type, target)
                
            else:
                self._log(f"[PlanningAgent] │ ✗ 不支持的查询类型：{query_type}")
                return None
                
        except Exception as e:
            self._log(f"[PlanningAgent] │ ✗ 查询执行失败：{e}")
            return None
    
    def _step4_generate_operations(
        self,
        modification_decisions: List[Dict]
    ) -> List[OperationPlan]:
        """
        步骤 4: 输出操作
        
        根据修改决策生成具体操作计划（仅支持 operations 新格式）
        完全根据输入的操作序列来解析，不依赖 goal 对象
        """
        operations = []
        
        for decision in modification_decisions:
            # 直接从 decision 中获取 operations 列表
            if "operations" in decision and isinstance(decision["operations"], list):
                ops_list = decision["operations"]
                self._log(f"[PlanningAgent] │ 处理 {len(ops_list)} 个操作...")
                
                # 将每个操作字典转换为 OperationPlan
                for op_dict in ops_list:
                    print(f"[PlanningAgent] │ 操作：： - {op_dict}")
                    op_type = op_dict.get("operation_type", "update")
                    
                    # 根据操作类型直接从 op_dict 中提取信息并创建 OperationPlan
                    if op_type == "whole_day_rewrite":
                        target_date = op_dict.get("target_date")
                        fields = op_dict.get("fields", {})
                        guidance = fields.get("guidance", "") if isinstance(fields, dict) else ""
                        
                        # 直接创建 OperationPlan
                        main_op = OperationPlan(
                            operation_type=OperationType.WHOLE_DAY_REWRITE,
                            data_type=DataType.DAILY_EVENT,  # 默认数据类型
                            target_path="daily_event",
                            index_method=IndexMethod.BY_DATE,
                            index_value=target_date,
                            modification={"guidance": guidance},
                            params={"date": target_date, "guidance": guidance},
                            description=f"重写 {target_date} 全天事件",
                            priority=0
                        )
                        operations.append(main_op)
                    elif op_type == "add":
                        fields = op_dict.get("fields", {})
                        target_date = op_dict.get("target_date")
                        
                        # 确定索引方式和值
                        if target_date:
                            index_method = IndexMethod.BY_DATE
                            index_value = target_date
                        else:
                            index_method = IndexMethod.BY_CONDITION
                            index_value = None
                        
                        # 直接创建 OperationPlan
                        op = OperationPlan(
                            operation_type=OperationType.ADD,
                            data_type=DataType.DAILY_EVENT,  # 默认数据类型
                            target_path="daily_event",
                            index_method=index_method,
                            index_value=index_value,
                            modification={"fields": fields} if fields else {},
                            params={"fields": fields},
                            description="新增数据",
                            priority=0
                        )
                        operations.append(op)
                    elif op_type == "delete":
                        target_id = op_dict.get("target_id")
                        target_date = op_dict.get("target_date")
                        condition = op_dict.get("condition")
                        
                        # 确定索引方式和值
                        if target_id:
                            index_method = IndexMethod.BY_ID
                            index_value = target_id
                        elif target_date:
                            index_method = IndexMethod.BY_DATE
                            index_value = target_date
                        elif condition:
                            index_method = IndexMethod.BY_CONDITION
                            index_value = condition
                        else:
                            index_method = IndexMethod.BY_CONDITION
                            index_value = None
                        
                        # 直接创建 OperationPlan
                        op = OperationPlan(
                            operation_type=OperationType.DELETE,
                            data_type=DataType.DAILY_EVENT,  # 默认数据类型
                            target_path="daily_event",
                            index_method=index_method,
                            index_value=index_value,
                            params={"condition": index_value} if isinstance(index_value, dict) else {},
                            description="删除数据",
                            priority=-10  # 删除优先级最高
                        )
                        operations.append(op)
                    elif op_type == "update":
                        target_id = op_dict.get("target_id")
                        target_date = op_dict.get("target_date")
                        fields = op_dict.get("fields", {})
                        
                        # 确定索引方式和值
                        if target_id:
                            index_method = IndexMethod.BY_ID
                            index_value = target_id
                        elif target_date:
                            index_method = IndexMethod.BY_DATE
                            index_value = target_date
                        else:
                            index_method = IndexMethod.BY_CONDITION
                            index_value = None
                        
                        # 直接创建 OperationPlan
                        op = OperationPlan(
                            operation_type=OperationType.UPDATE,
                            data_type=DataType.DAILY_EVENT,  # 默认数据类型
                            target_path="daily_event",
                            index_method=index_method,
                            index_value=index_value,
                            modification={"fields": fields} if fields else {},
                            params={"updates": fields, "event_id": target_id, "date": target_date},
                            description="更新数据",
                            priority=0
                        )
                        operations.append(op)
                    else:
                        # 操作类型识别错误，打印错误信息并跳过
                        self._log(f"[PlanningAgent] │ ✗ 操作类型识别错误：{op_type}")
                        print(f"[PlanningAgent] ✗ 操作类型识别错误：{op_type}")
        
        # 打印最终生成的完整操作数据（便于调试）
        self._log(f"\n[PlanningAgent] ╔{'═' * 76}╗")
        self._log(f"[PlanningAgent] ║ {'【最终操作列表】共 {len(operations)} 个操作':^72} ║")
        self._log(f"[PlanningAgent] ╠{'═' * 76}╣")
        
        for i, op in enumerate(operations, 1):
            self._log(f"[PlanningAgent] ║ [操作 {i}/{len(operations)}]")
            self._log(f"[PlanningAgent] │   ├─ 类型：{op.operation_type.value}")
            self._log(f"[PlanningAgent] │   ├─ 数据类型：{op.data_type.value}")
            self._log(f"[PlanningAgent] │   ├─ 索引方式：{op.index_method.value}")
            self._log(f"[PlanningAgent] │   ├─ 索引值：{op.index_value}")
            self._log(f"[PlanningAgent] │   ├─ 修改内容：{op.modification}")
            self._log(f"[PlanningAgent] │   ├─ 参数：{op.params}")
            self._log(f"[PlanningAgent] │   ├─ 描述：{op.description}")
            self._log(f"[PlanningAgent] │   └─ 优先级：{op.priority}")
            if op.cascade_effects:
                self._log(f"[PlanningAgent] │       └─ 级联影响：{op.cascade_effects}")
            self._log(f"[PlanningAgent] ║")
        
        self._log(f"[PlanningAgent] ╚{'═' * 76}╝\n")
        
        return operations
    
    def _convert_dict_to_operation_plan(self, op_dict: Dict, goal: PlanningGoal) -> Optional[OperationPlan]:
        """
        将操作字典转换为 OperationPlan 对象
        
        Args:
            op_dict: 操作字典，格式如 {"operation_type": "update", "target_id": "...", "fields": {...}}
            goal: 规划目标
            
        Returns:
            OperationPlan 对象，如果转换失败返回 None
        """
        try:
            op_type_str = op_dict.get("operation_type", "update")
            
            # 映射 operation_type 字符串到枚举
            op_type_map = {
                "update": OperationType.UPDATE,
                "add": OperationType.ADD,
                "delete": OperationType.DELETE,
                "whole_day_rewrite": OperationType.WHOLE_DAY_REWRITE
            }
            op_type = op_type_map.get(op_type_str, OperationType.UPDATE)
            
            # 提取关键字段
            target_id = op_dict.get("target_id")
            target_date = op_dict.get("target_date")
            fields = op_dict.get("fields", {})
            
            # 确定索引方式和值
            if target_id:
                index_method = IndexMethod.BY_ID
                index_value = target_id
            elif target_date:
                index_method = IndexMethod.BY_DATE
                index_value = target_date
            else:
                index_method = IndexMethod.BY_CONDITION
                index_value = None
            
            # 创建 OperationPlan
            return OperationPlan(
                operation_type=op_type,
                data_type=goal.data_type,
                target_path=goal.data_type.value,
                index_method=index_method,
                index_value=index_value,
                modification={"fields": fields} if fields else {},
                params={
                    "event_id": target_id,
                    "date": target_date,
                    "updates": fields
                },
                description=f"{op_type_str}: {goal.description}",
                priority=0
            )
        except Exception as e:
            self._log(f"[PlanningAgent] │ ✗ 操作转换失败：{e}")
            return None
    
    def _create_single_event_operation(self, decision: Dict) -> Optional[OperationPlan]:
        """创建单个事件修改操作"""
        goal = decision["goal"]
        event_id = decision.get("target_event_id")
        
        if not event_id and isinstance(decision.get("data"), dict):
            event_id = decision["data"].get("event_id")
        
        # 从 fields 中获取更新内容（新格式）
        fields = decision.get("fields", {})
        if not fields:
            # 降级处理：旧格式
            fields = decision.get("modification_fields", {})
        
        return OperationPlan(
            operation_type=OperationType.UPDATE,
            data_type=goal.data_type,
            target_path=goal.data_type.value,
            index_method=IndexMethod.BY_ID,
            index_value=event_id,
            modification={
                "fields": fields,
                "strategy": "single"
            },
            params={
                "event_id": event_id,
                "updates": fields
            },
            description=f"修改单个事件：{goal.description}",
            priority=0,
            cascade_effects=[u.get("event_id") for u in decision.get("cascade_updates", [])]
        )
    
    def _create_whole_day_operations(self, decision: Dict) -> List[OperationPlan]:
        """创庖一整天数据重写操作（基于 LLM 重新生成当日所有事件）"""
        goal = decision["goal"]
        target_date = decision.get("target_date")
            
        # 从 fields 中获取重写指导
        fields = decision.get("fields", {})
        guidance = fields.get("guidance", "") if isinstance(fields, dict) else ""
            
        # 创建 WHOLE_DAY_REWRITE 操作
        main_op = OperationPlan(
            operation_type=OperationType.WHOLE_DAY_REWRITE,
            data_type=goal.data_type,
            target_path=goal.data_type.value,
            index_method=IndexMethod.BY_DATE,
            index_value=target_date,
            modification={
                "guidance": guidance
            },
            params={
                "date": target_date,
                "guidance": guidance
            },
            description=f"重写 {target_date} 全天事件：{goal.description}",
            priority=0
        )
            
        return [main_op]
    
    def _create_add_operation(self, decision: Dict) -> Optional[OperationPlan]:
        """创建新增操作"""
        goal = decision["goal"]
        
        return OperationPlan(
            operation_type=OperationType.ADD,
            data_type=goal.data_type,
            target_path=goal.data_type.value,
            index_method=goal.index_method,
            index_value=goal.index_value,
            params=goal.known_params,
            description=f"新增数据：{goal.description}",
            priority=0
        )
    
    def _create_delete_operation(self, decision: Dict) -> Optional[OperationPlan]:
        """创建删除操作"""
        goal = decision["goal"]
        
        return OperationPlan(
            operation_type=OperationType.DELETE,
            data_type=goal.data_type,
            target_path=goal.data_type.value,
            index_method=goal.index_method,
            index_value=goal.index_value,
            params={"condition": goal.index_value} if isinstance(goal.index_value, dict) else {},
            description=f"删除数据：{goal.description}",
            priority=-10  # 删除优先级最高
        )
    
    def _create_update_operation(self, decision: Dict) -> Optional[OperationPlan]:
        """创建更新操作"""
        goal = decision["goal"]
        fields = decision.get("fields", {})
        
        return OperationPlan(
            operation_type=OperationType.UPDATE,
            data_type=goal.data_type,
            target_path=goal.data_type.value,
            index_method=goal.index_method,
            index_value=goal.index_value,
            modification={"fields": fields} if fields else {},
            params={
                "updates": fields,
                "condition": goal.index_value
            } if isinstance(goal.index_value, dict) else {"updates": fields},
            description=f"更新数据：{goal.description}",
            priority=0
        )
    
    def _create_cascade_operation(
        self,
        goal: PlanningGoal,
        update: Dict
    ) -> Optional[OperationPlan]:
        """创建级联更新操作"""
        return OperationPlan(
            operation_type=OperationType.UPDATE,
            data_type=goal.data_type,
            target_path=goal.data_type.value,
            index_method=IndexMethod.BY_ID,
            index_value=update.get("event_id"),
            modification={
                "field": update.get("field"),
                "reason": update.get("reason")
            },
            params={
                "event_id": update.get("event_id"),
                "field": update.get("field"),
                "cascade": True
            },
            description=f"级联更新：{update.get('reason', '')}",
            priority=5
        )
    
    def _generate_summary(
        self,
        command_text: str,
        goals: List[PlanningGoal],
        decisions: List[Dict]
    ) -> str:
        """生成执行计划摘要"""
        strategies = [d.get("strategy", "single") for d in decisions]
        
        single_count = strategies.count("single")
        whole_day_count = strategies.count("whole_day")
        add_count = strategies.count("add_new")
        delete_count = strategies.count("delete")
        
        parts = []
        if single_count > 0:
            parts.append(f"{single_count}个单事件修改")
        if whole_day_count > 0:
            parts.append(f"{whole_day_count}个全天调整")
        if add_count > 0:
            parts.append(f"{add_count}个新增")
        if delete_count > 0:
            parts.append(f"{delete_count}个删除")
        
        return f"执行{' + '.join(parts)}，共{len(goals)}个目标"
    
    def _check_requires_confirmation(self, operations: List[OperationPlan]) -> bool:
        """检查是否需要用户确认"""
        delete_count = sum(1 for op in operations if op.operation_type == OperationType.DELETE)
        total_count = len(operations)
        return delete_count > 0 or total_count > 3
    
    def _create_query_plan(self, command_text: str) -> OperationPlan:
        """创建查询操作"""
        return OperationPlan(
            operation_type=OperationType.QUERY,
            data_type=DataType.DAILY_EVENT,
            target_path="",
            description=command_text,
            priority=100
        )