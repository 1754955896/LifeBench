import json
import os
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional
import threading
import concurrent.futures

from src.lifebench.utils.llm_call import llm_call, llm_call_j, llm_call_reason_j
from .base_generator import BaseQAGenerator
from .phone_operation_generator import PhoneOperationGenerator


class QAMultiHopGenerator(BaseQAGenerator):
    """多跳问题生成器"""

    def __init__(self, daily_event: List[Dict], event_tree: List[Dict],
                 draft_event: Dict[str, List], phonedata: Dict[str, List],
                 phone_data_dir: str = None, is_print: bool = True,
                 year: int = 2025, persona_data: Dict = None):
        """
        初始化多跳问题生成器

        Args:
            daily_event: daily_event 数据列表
            event_tree: event_tree 数据列表
            draft_event: draft_event 数据字典（按月份组织）
            phonedata: 手机操作数据字典
            phone_data_dir: 手机数据目录路径
            is_print: 是否打印调试信息
            year: 年份，默认 2025
            persona_data: 用户画像数据
        """
        super().__init__()
        self.daily_event = daily_event
        self.event_tree = event_tree
        self.draft_event = draft_event
        self.phonedata = phonedata
        self.phone_data_dir = phone_data_dir
        self.is_print = is_print
        self.persona_data = persona_data or {}
        self.phone_op_generator = PhoneOperationGenerator(persona_data=self.persona_data)
        # 线程锁
        self.phonedata_lock = threading.Lock()
        self.phone_id_counters = {}
        self.default_ask_time = f"{year}-12-31"

    def _add_operations_to_phonedata(self, operations: List[Dict[str, Any]]):
        """
        将手机操作数据添加到 phonedata

        Args:
            operations: 手机操作数据列表
        """
        with self.phonedata_lock:
            for op in operations:
                op_type = op.get('type', 'unknown')

                if op_type not in self.phonedata:
                    self.phonedata[op_type] = []

                # 分配 phone_id
                if op_type not in self.phone_id_counters:
                    self.phone_id_counters[op_type] = 1

                if 'phone_id' not in op:
                    op['phone_id'] = self.phone_id_counters[op_type]  # 使用 int 格式

                self.phone_id_counters[op_type] += 1

                self.phonedata[op_type].append(op)

        print(f"[Evidence Refine] 已将 {len(operations)} 条操作数据添加到 phonedata")

    def select_agent(self, year: int, target_month: int) -> List[Dict[str, Any]]:
        """
        Select Agent: 从目标月份随机抽样一天，往后扩展两天，基于事件选择目标事件

        Args:
            year: 年份
            target_month: 目标月份

        Returns:
            包含采样日期和目标事件信息的列表
        """
        print(f"\n[Select Agent] 处理月份：{year}-{target_month:02d}")

        # 1. 收集所有可用日期
        all_available_dates = []
        if target_month == 12:
            last_day = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = datetime(year, target_month + 1, 1) - timedelta(days=1)

        first_day = datetime(year, target_month, 1)
        month_dates = [first_day + timedelta(days=i) for i in range((last_day - first_day).days + 1)]
        all_available_dates.extend(month_dates)

        # 2. 随机选择 1 个起始日期
        selected_start = random.choice(all_available_dates)

        # 3. 往后扩展 2 天（共 3 天）
        consecutive_dates = [selected_start + timedelta(days=i) for i in range(3)]
        date_strs = [d.strftime("%Y-%m-%d") for d in consecutive_dates]

        # 4. 获取这 3 天的 daily event 数据
        daily_events_in_range = []
        if isinstance(self.daily_event, list):
            for event in self.daily_event:
                if isinstance(event, dict) and 'date' in event:
                    event_dates = event.get('date', [])
                    if isinstance(event_dates, list):
                        for time_range in event_dates:
                            if '至' in time_range:
                                start_time_str = time_range.split('至')[0].strip()
                                event_date = start_time_str[:10]
                            else:
                                event_date = time_range[:10]

                            if event_date in date_strs:
                                daily_events_in_range.append(event)
                                break

        print(f"[Select Agent] 获取 {date_strs[0]} 到 {date_strs[-1]} 的 daily event 数据：{len(daily_events_in_range)} 条")

        # 5. 基于事件数据来选择目标事件并分析
        design_prompt = f"""
        作为 Select Agent，请仔细分析以下 daily event 数据，选择一个适合构建多跳推理问题的目标事件。

        日期范围：{date_strs[0]} 到 {date_strs[-1]}

        该时间段内的 daily event 数据：
        {json.dumps(daily_events_in_range, ensure_ascii=False, indent=2)}

        请完成以下任务：

        **1. 选择目标事件**
           - 选择具有重要价值或复杂关联的事件
           - 优先选择涉及多个人物、地点、物品的事件
           - 优先选择有时间跨度或因果关系的事件

        **2. 结构化分析**
           a) **主要人物**：事件中涉及哪些关键人物？
           b) **地点信息**：事件发生在哪里？是否有多个相关地点？
           c) **过程描述**：事件的完整过程是怎样的？
           d) **相关实体**：涉及哪些重要的物品、文件、活动？
           e) **可推理点**：从时间、地点、人物、因果等角度可以设计哪些推理链条？

        请以 JSON 格式返回：
        {{
            "target_event": {{
                "event_id": "事件 ID（必须使用上面数据中的 event_id 字段值，直接复制，不要修改或重新生成）",
                "event_name": "事件名称",
                "event_type": "事件类型",
                "date": "事件日期"
            }},
            "analysis_text": "对该事件的详细分析文本"
        }}

        【重要提醒】
        - event_id 必须从上面的 daily event 数据中直接提取
        - 不要自行生成、修改或编造 event_id
        - 如果数据中没有合适的 event_id，请从数据中选择最匹配的事件并使用其原始 event_id
        """

        design_result = llm_call(design_prompt)

        if self.is_print:
            print("\n[Select Agent] LLM 输出:")
            print(design_result)

        # 6. 解析 LLM 返回，查找或随机选择目标事件
        target_event_full, analysis_text = self._find_or_sample_target_event(
            design_result, daily_events_in_range
        )

        sampling_results = [{
            'dates': date_strs,
            'target_event': target_event_full,
            'analysis_text': analysis_text,
            'daily_events_in_range': daily_events_in_range
        }]

        print(f"[Select Agent] 完成，选择了 {len(sampling_results)} 个时间段")
        return sampling_results

    def _find_or_sample_target_event(self, design_result: str, daily_events_in_range: List[Dict]) -> Tuple[Dict, str]:
        """
        根据 LLM 返回查找目标事件，如果找不到则随机选择一个

        Args:
            design_result: LLM 返回的原始字符串
            daily_events_in_range: 日期范围内的所有事件

        Returns:
            (target_event_full, analysis_text)
        """
        # 如果 LLM 返回无效，随机选择
        if not design_result:
            return self._sample_random_event(daily_events_in_range, "LLM 返回为空")

        try:
            start_idx = design_result.find('{')
            end_idx = design_result.rfind('}') + 1
            if start_idx == -1 or end_idx == 0:
                return self._sample_random_event(daily_events_in_range, "LLM 返回中找不到 JSON")

            design_json = json.loads(design_result[start_idx:end_idx])

            # 安全获取 target_event，处理 null 情况
            target_event = design_json.get('target_event')
            if target_event is None:
                target_event = {}

            # 优先从 target_event 获取 event_id，也支持从 design_json 顶层获取
            event_id = design_json.get('event_id') or target_event.get('event_id', '')

            # 根据 event_id 查找完整事件
            target_event_full = self._find_event_by_id(event_id, daily_events_in_range)

            # 找不到则随机选择
            if not target_event_full:
                return self._sample_random_event(daily_events_in_range, f"未找到 event_id={event_id}")

            analysis_text = design_json.get('analysis_text', '')
            return target_event_full, analysis_text

        except Exception as e:
            print(f"[Select Agent] 解析失败：{e}")
            return self._sample_random_event(daily_events_in_range, f"解析异常: {e}")

    def _find_event_by_id(self, event_id: str, events: List[Dict]) -> Optional[Dict]:
        """根据 event_id 在事件列表中查找匹配的事件"""
        if not event_id:
            return None

        for event in events:
            if isinstance(event, dict) and str(event.get('event_id', '')) == str(event_id):
                return event

        return None

    def _sample_random_event(self, events: List[Dict], reason: str) -> Tuple[Dict, str]:
        """随机选择一个事件，优先选择 event_id 不为空的事件"""
        if not events:
            print(f"[Select Agent] {reason}，但事件列表为空")
            return {}, ''

        # 优先选择 event_id 不为空的事件
        valid_events = [e for e in events if e.get('event_id')]
        sample_pool = valid_events if valid_events else events

        sampled = random.choice(sample_pool)
        print(f"[Select Agent] {reason}，随机选择：event_id={sampled.get('event_id')}")
        return sampled, ''

    def _validate_and_cleanup_nodes(self, nodes: List[Dict], edges: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """
        验证并清理 event_id 无效的节点，同时删除关联的边

        Args:
            nodes: 节点列表
            edges: 边列表

        Returns:
            (清理后的节点列表, 清理后的边列表)
        """
        if not self.daily_event:
            return nodes, edges

        # 构建有效的 event_id 集合
        valid_event_ids = set()
        for event in self.daily_event:
            eid = str(event.get('event_id', ''))
            if eid:
                valid_event_ids.add(eid)

        # 获取所有有效的 node_id（event_id 有效的节点）
        valid_node_ids = set()
        invalid_nodes_info = []
        for node in nodes:
            event_id = str(node.get('event_id', ''))
            # 检查：event_id 有效或者是空字符串（空字符串表示来自编造扩展，允许保留）
            if event_id and event_id not in valid_event_ids:
                invalid_nodes_info.append({
                    'node_id': node.get('id'),
                    'name': node.get('name'),
                    'event_id': event_id
                })
            elif event_id:
                valid_node_ids.add(node.get('id'))

        if invalid_nodes_info:
            print(f"[Inference Agent] 发现 {len(invalid_nodes_info)} 个节点 event_id 无效:")
            for info in invalid_nodes_info:
                print(f"  - {info['node_id']}: {info['name']}, event_id={info['event_id']}")

        # 过滤节点：只保留 event_id 有效或为空字符串的节点
        # 注意：空字符串的节点可能来自编造扩展，保留作为中间推理节点
        valid_nodes = []
        for node in nodes:
            event_id = str(node.get('event_id', ''))
            # 保留：event_id 有效 或 event_id 为空（来自编造扩展等）
            if not event_id or event_id in valid_event_ids:
                valid_nodes.append(node)

        # 过滤边：只保留两端节点都在有效节点列表中的边
        valid_node_ids = set(n.get('id') for n in valid_nodes)
        valid_edges = []
        for edge in edges:
            if edge.get('from') in valid_node_ids and edge.get('to') in valid_node_ids:
                valid_edges.append(edge)

        if len(invalid_nodes_info) > 0:
            print(f"[Inference Agent] 清理完成: {len(valid_nodes)} 个节点, {len(valid_edges)} 条边")

        return valid_nodes, valid_edges

    def search_agent(self, dates: List[str], target_event: Dict[str, Any]):
        """
        Search Agent: 搜索目标事件对应的 event_tree

        Args:
            dates: 日期范围列表
            target_event: 目标事件信息

        Returns:
            搜索到的事件树数据和总结
        """
        event_id = target_event.get('atomic_id')

        # 模式 1: 基于 atomic_id 搜索 event_tree
        if event_id and isinstance(self.event_tree, list):
            print(f"[Search Agent - 模式 1] 基于 atomic_id 搜索 event_tree")
            return self._search_by_atomic_id(event_id, target_event)

        # 模式 2: 基于月份的 draft_event 分析
        else:
            return []

    def _search_by_atomic_id(self, atomic_id: str, target_event: Dict[str, Any]) -> List[Dict]:
        """
        模式 1: 基于 atomic_id 提取最前面的父节点序号，然后从 daily_event 中筛选匹配的事件

        Args:
            atomic_id: 事件的 atomic_id（可能是字符串或列表）
            target_event: 目标事件信息

        Returns:
            daily_event 中匹配的事件列表
        """
        # 提取最前面的父节点序号
        parent_id = None
        if isinstance(atomic_id, list):
            # 如果是列表，取第一个元素的父节点
            if atomic_id:
                first_item = str(atomic_id[0])
                if '-' in first_item:
                    parent_id = first_item.split('-')[0]
                else:
                    parent_id = first_item
        elif atomic_id:
            # 如果是字符串，直接提取父节点
            atomic_id_str = str(atomic_id)
            if '-' in atomic_id_str:
                parent_id = atomic_id_str.split('-')[0]
            else:
                parent_id = atomic_id_str

        if not parent_id:
            print(f"[Search Agent] 无法提取父节点 ID")
            return []

        print(f"[Search Agent] 提取父节点 ID: {parent_id}")

        # 构建前缀匹配字符串：parent_id + "-"
        prefix = parent_id + "-"

        # 从 daily_event 中筛选 atomic_id 以 prefix 开头或等于 parent_id 的事件
        matched_daily_events = []
        for event in self.daily_event:
            event_atomic_id = event.get('atomic_id', '')

            # 检查 daily_event 的 atomic_id 是否匹配
            is_match = False
            if isinstance(event_atomic_id, str):
                # 如果 daily_event 的 atomic_id 是字符串
                # 匹配条件：等于 parent_id 或以 parent_id- 开头
                if event_atomic_id == parent_id or event_atomic_id.startswith(prefix):
                    is_match = True
            elif isinstance(event_atomic_id, list):
                # 如果 daily_event 的 atomic_id 是列表，检查列表中是否有匹配的
                for aid in event_atomic_id:
                    aid_str = str(aid)
                    if aid_str == parent_id or aid_str.startswith(prefix):
                        is_match = True
                        break

            if is_match:
                matched_daily_events.append(event)

        print(f"[Search Agent] 从 daily_event 中找到 {len(matched_daily_events)} 个匹配事件")

        return matched_daily_events
    
    def _extract_leaf_events(self, nodes: List[Dict]) -> List[Dict]:
        """
        递归提取所有叶子节点事件
        
        Args:
            nodes: 事件节点列表
            
        Returns:
            叶子节点事件列表
        """
        leaf_events = []
        for node in nodes:
            if isinstance(node, dict):
                children = node.get('subevent', [])
                if children and isinstance(children, list) and len(children) > 0:
                    # 有子节点，递归处理
                    leaf_events.extend(self._extract_leaf_events(children))
                else:
                    # 没有子节点，是叶子节点
                    leaf_events.append(node)
        return leaf_events
    
    def _search_by_draft_event(self, dates: List[str], target_event: Dict[str, Any]) -> List[Dict]:
        """
        模式 2: 基于 draft_event 搜索
        
        Args:
            dates: 日期范围列表
            target_event: 目标事件信息
            
        Returns:
            该月份的所有事件列表（只包含 name 和 holiday）
        """
        # 提取月份信息
        target_month = dates[0][:7]  # YYYY-MM
        
        print(f"[Search Agent - 模式 2] 提取月份：{target_month}")
        
        # 从 draft_event 中获取该月份的数据
        month_events_raw = self.draft_event.get(target_month, [])
        
        if not month_events_raw or not isinstance(month_events_raw, list):
            print(f"[Search Agent - 模式 2] 未找到 {target_month} 的 draft_event 数据")
            return []
        
        # 组织每天的事件，只保留 name 和 holiday
        all_events = []
        for day_data in month_events_raw:
            if not isinstance(day_data, dict):
                continue
            
            # 提取 holiday（如果有）
            date_attr = day_data.get('date_attribute', {})
            holiday = date_attr.get('holiday', '') if isinstance(date_attr, dict) else ''
            
            # 提取 events
            events = day_data.get('events', [])
            if not isinstance(events, list):
                continue
            
            # 只保留 name 和 holiday
            for event in events:
                if isinstance(event, dict):
                    simplified_event = {
                        'name': event.get('name', ''),
                    }
                    if holiday:
                        simplified_event['holiday'] = holiday
                    all_events.append(simplified_event)
        
        print(f"[Search Agent - 模式 2] 从 {target_month} 提取到 {len(all_events)} 个事件")
        
        return all_events
    
    def inference_agent(self, target_event: Dict[str, Any], search_result: Dict[str, Any], 
                       daily_events: List[Dict]) -> Dict[str, Any]:
        """
        Inference Agent: 构建多跳推理链条
        
        Args:
            target_event: 目标事件
            search_result: 搜索结果
            daily_events: daily_event 数据
            
        Returns:
            推理链条信息
        """
        print("[Inference Agent] 构建多跳推理链条")
        
        # Step 1: 基于 event_tree 生成初始推理图
        initial_graph = self._generate_initial_inference_graph(target_event, search_result ,daily_events)
        
        # Step 2: 三种扩展方法
        extended_nodes = []
        
        # 方法 1: 基于时序扩展
        temporal_extensions = self._extend_by_temporal(initial_graph, daily_events)
        extended_nodes.extend(temporal_extensions)

        # # 方法 1: 基于时序扩展
        # temporal_extensions = self._extend_by_temporal(initial_graph, daily_events)
        # extended_nodes.extend(temporal_extensions)

        # 方法 2: 基于实体扩展
        entity_extensions = self._extend_by_entity(initial_graph, daily_events)
        extended_nodes.extend(entity_extensions)

        # 方法 2: 基于实体扩展
        entity_extensions = self._extend_by_entity(initial_graph, daily_events)
        extended_nodes.extend(entity_extensions)

        # 方法 2: 基于实体扩展
        entity_extensions = self._extend_by_entity(initial_graph, daily_events)
        extended_nodes.extend(entity_extensions)

        # 方法 2: 基于实体扩展
        entity_extensions = self._extend_by_entity(initial_graph, daily_events)
        extended_nodes.extend(entity_extensions)


        # # 方法 3: 基于编造扩展
        # fabrication_extensions = self._extend_by_fabrication(initial_graph)
        # extended_nodes.extend(fabrication_extensions)
        
        # Step 3: 整合推理链条
        inference_chain = self._build_inference_chain(initial_graph, extended_nodes)
        
        return inference_chain
    
    def _generate_initial_inference_graph(self, target_event: Dict[str, Any], 
                                         search_result: List[Dict],
                                         daily_events: List[Dict]) -> Dict[str, Any]:
        """
        生成初始推理图（单链条结构）
        
        设计一条从起始节点到目标节点的推理链条，每个节点通过特定关系连接到下一个节点。
        最终节点是目标事件的某个信息，其他节点逐渐推理到最终节点。
        
        Args:
            target_event: 目标事件
            search_result: Search Agent 返回的事件列表（leaf_events 或 draft_events）
            daily_events: Select Agent 返回的 daily_event 数据
            
        Returns:
            初始推理图（包含 nodes, edges, reasoning_chain）
        """
        print(f"[Inference Agent] 生成初始推理图（单链条结构）")
        
        # 构建输入数据
        input_data = {
            'target_event': target_event,
            'related_events': search_result,
            'daily_events': daily_events
        }
        
        # 调用 LLM 生成推理链条
        inference_prompt = f"""
作为 Inference Agent，请基于以下事件数据设计一条多跳推理链条。

【目标事件】
{json.dumps(target_event, ensure_ascii=False, indent=2)}

【相关事件数据】（来自 event_tree 或 draft_event）
{json.dumps(search_result[:15], ensure_ascii=False, indent=2) if len(search_result) > 10 else json.dumps(search_result, ensure_ascii=False, indent=2)}

【目标日期范围内的 daily_event】
{json.dumps(daily_events[:30], ensure_ascii=False, indent=2) if daily_events and len(daily_events) > 10 else json.dumps(daily_events, ensure_ascii=False, indent=2) if daily_events else '暂无'}

**任务要求**

1. **设计推理链条**
   - 构建一条从起始节点到最终节点的线性推理链
   - 链条长度：3-10 个节点（包含起始和最终节点）
   - 最终节点必须是目标事件的某个具体信息（如时间、地点、人物、物品等）
   - 前面的节点应该是可以通过推理逐渐导向最终节点的中间步骤

2. **节点设计原则**
   - 每个节点代表一个具体的事件或事实
   - 节点之间应该有清晰的逻辑关系
   - 避免跳跃过大，确保推理的连贯性
   - 节点应包含：名称、时间、实体（人物/地点/物品）、来源、event_id（如果有）

3. **关系类型**（只能使用以下 5 种,可以尽量丰富的使用关系）
   - **同实体**：两个事件涉及相同的人物、地点或物品
   - **同位置**：两个事件发生在相同的地点
   - **因果**：前一个事件导致或影响了后一个事件
   - **时间差**：两个事件之间有明确的时间间隔（如"3天后"、"一周前"）
   - **同事件**：两个事件属于同一个大事件的子事件，或是发生在不同天的同样的事件，如跑步，理发

4. **链条示例**
   ```
   节点1 (起始) → [关系1] → 节点2 → [关系2] → 节点3 → [关系3] → 节点4 (最终)
   ```

请以 JSON 格式返回：
{{
    "chain": [
        {{
            "step": 1,
            "node": {{
                "name": "事件名称",
                "time": "时间信息",
                "entity": "主要涉及的实体（人物/地点/物品）",
                "source": "来源（target/daily_event/related_event）",
                "event_id": "事件 ID（对应的daily_event的event_id如果有的话，否则为空字符串）"
            }},
            "relation_to_next": "与下一个节点的关系类型（同实体/同位置/因果/时间差/同事件），最后一个节点为空字符串",
            "relation_description": "关系的具体描述，解释为什么这两个节点有这种关系"
        }}
    ],
    "final_answer_info": "最终节点代表的目标事件信息是什么",
    "reasoning_summary": "简要说明整个推理链条的逻辑"
}}

**【关键约束】event_id 填写规则（必须严格遵守）**：
- **必须**从上面的 daily_event 数据中获取真实的 event_id
- **禁止**填写 node_1、node_2 等内部节点 ID
- **禁止**填写自行编造的 event_id（如"出门事件"、"早晨事件"等描述性文字）
- **禁止**填写在 daily_event 中不存在的 event_id
- 如果该节点没有对应的真实 daily_event 事件，event_id 字段填写**空字符串 ""**
- 每个节点的 event_id 必须是数字或字符串，必须能在 daily_event 中找到对应记录

**注意**：
- 确保链条是线性的，每个节点只指向下一个节点
- 关系类型必须从上述 5 种中选择
- 最终节点应该直接回答关于目标事件的某个问题
"""
        print("[Inference Agent] 调用 LLM 生成推理链条")
        llm_result = llm_call(inference_prompt)
        print("[Inference Agent] LLM 输出:", llm_result[:300] + "..." if len(llm_result) > 300 else llm_result)

        if self.is_print:
            print("\n[Inference Agent - 推理链条] LLM 输出:")
            print(llm_result[:500] + "..." if len(llm_result) > 500 else llm_result)
        
        try:
            start_idx = llm_result.find('{')
            end_idx = llm_result.rfind('}') + 1
            if start_idx != -1 and end_idx != -1:
                chain_json = json.loads(llm_result[start_idx:end_idx])
                
                # 转换为标准的 nodes 和 edges 格式
                nodes = []
                edges = []
                chain = chain_json.get('chain', [])
                
                for i, step in enumerate(chain):
                    node_data = step.get('node', {})
                    node_id = f"node_{i+1}"
                    
                    # 构建节点
                    nodes.append({
                        'id': node_id,
                        'name': node_data.get('name', ''),
                        'time': node_data.get('time', ''),
                        'entity': node_data.get('entity', ''),
                        'source': node_data.get('source', ''),
                        'event_id': node_data.get('event_id', ''),
                        'step': step.get('step', i+1)
                    })
                    
                    # 构建边（除了最后一个节点）
                    if i < len(chain) - 1:
                        next_node_id = f"node_{i+2}"
                        relation = step.get('relation_to_next', '')
                        description = step.get('relation_description', '')
                        
                        edges.append({
                            'from': node_id,
                            'to': next_node_id,
                            'relation': relation,
                            'description': description
                        })

                # 验证并清理 event_id 无效的节点
                nodes, edges = self._validate_and_cleanup_nodes(nodes, edges)

                print(f"[Inference Agent] 推理链条生成完成，包含 {len(nodes)} 个节点和 {len(edges)} 条边")

                return {
                    'nodes': nodes,
                    'edges': edges,
                    'reasoning_chain': chain,
                    'final_answer_info': chain_json.get('final_answer_info', ''),
                    'reasoning_summary': chain_json.get('reasoning_summary', ''),
                    'input_data': input_data
                }
        except Exception as e:
            print(f"[Inference Agent] 推理链条生成失败：{e}")
            import traceback
            traceback.print_exc()
        
        # 失败时返回空图
        return {
            'nodes': [], 
            'edges': [], 
            'reasoning_chain': [],
            'final_answer_info': '',
            'reasoning_summary': '',
            'input_data': input_data
        }
    
    def _extend_by_temporal(self, graph: Dict[str, Any], daily_events: List[Dict]) -> List[Dict]:
        """
        基于时序扩展节点
        
        选取推理链条第一个节点的时间，在其前后七天内随机选择一个日期，
        然后让 LLM 挑选出该日期最重要的事件来生成一个新节点。
        
        Args:
            graph: 初始推理图（包含 reasoning_chain）
            daily_events: daily_event 数据
            
        Returns:
            扩展的节点和边列表
        """
        print("[Inference Agent] 基于时序扩展节点")
        
        # 获取推理链条
        chain = graph.get('reasoning_chain', [])
        if not chain:
            print("[Inference Agent] 时序扩展：没有推理链条，跳过")
            return []
        
        if not daily_events:
            print("[Inference Agent] 时序扩展：没有 daily_events 数据，跳过")
            return []
        
        # 选取第一个节点
        first_step = chain[0]
        first_node = first_step.get('node', {})
        node_time = first_node.get('time', '')
        
        if not node_time:
            print(f"[Inference Agent] 时序扩展：第一个节点没有时间信息，跳过")
            return []
        
        print(f"[Inference Agent] 时序扩展：使用第一个节点 '{first_node.get('name', '')}' 的时间 {node_time}")
        
        # 解析第一个节点的日期
        try:
            import re
            date_match = re.search(r'\d{4}-\d{2}-\d{2}', node_time)
            if not date_match:
                print(f"[Inference Agent] 时序扩展：无法从时间中提取日期，跳过")
                return []
            
            base_date = datetime.strptime(date_match.group(), '%Y-%m-%d')
            offset_days = random.randint(-7, 7)
            target_date = base_date + timedelta(days=offset_days)
            target_date_str = target_date.strftime('%Y-%m-%d')
            
            print(f"[Inference Agent] 时序扩展：目标日期 {target_date_str} (偏移 {offset_days} 天)")
        except Exception as e:
            print(f"[Inference Agent] 时序扩展：日期解析失败 ({e})，跳过")
            return []
        
        # 筛选目标日期的所有事件
        events_on_target_date = []
        for event in self.daily_event:
            event_date = event.get('date', '')
            if isinstance(event_date, list):
                for time_range in event_date:
                    if '至' in time_range:
                        start_time = time_range.split('至')[0].strip()[:10]
                        if start_time == target_date_str:
                            events_on_target_date.append(event)
                            break
                    elif time_range[:10] == target_date_str:
                        events_on_target_date.append(event)
                        break
        
        if not events_on_target_date:
            print(f"[Inference Agent] 时序扩展：{target_date_str} 没有事件，跳过")
            return []
        
        print(f"[Inference Agent] 时序扩展：找到 {len(events_on_target_date)} 个事件，让 LLM 选择最重要的")
        
        # 调用 LLM 选择最重要的事件并生成新节点
        selection_prompt = f"""
作为 Inference Agent，请从以下事件中选出最重要的一个，并基于它创建一个新的推理节点。

【起始节点】
{json.dumps(first_node, ensure_ascii=False, indent=2)}

【目标日期】
{target_date_str}

【候选事件】
{json.dumps(events_on_target_date, ensure_ascii=False, indent=2)}

**任务要求**

1. **选择最重要的事件**
   - 分析与起始节点的关系最紧密的事件
   - 考虑事件的关联性、重要性、对推理的贡献

2. **生成新节点**
   - 基于选中的事件创建一个新节点
   - 包含：名称、时间、实体、来源、event_id

3. **建立时序关系**
   - 描述新节点与起始节点的时间关系（如"X天后"、"X天前"）
   - 解释为什么这个事件对推理链条很重要

请以 JSON 格式返回：
{{
    "selected_event": {{
        "name": "事件名称",
        "time": "时间信息",
        "entity": "主要涉及的实体",
        "source": "来源",
        "event_id": "事件 ID（必须从候选事件中获取真实 ID，禁止自行编造或填写不存在于候选事件中的 ID）"
    }},
    "temporal_relation": "与起始节点的时间关系（如'3天后'、'5天前'）",
    "importance_reason": "为什么选择这个事件，它对推理的重要性"
}}
"""
        
        llm_result = llm_call(selection_prompt)
        
        if self.is_print:
            print("\n[Inference Agent - 时序扩展] LLM 输出:")
            print(llm_result[:500] + "..." if len(llm_result) > 500 else llm_result)
        
        try:
            start_idx = llm_result.find('{')
            end_idx = llm_result.rfind('}') + 1
            if start_idx != -1 and end_idx != -1:
                result_json = json.loads(llm_result[start_idx:end_idx])
                
                selected_event = result_json.get('selected_event', {})
                temporal_relation = result_json.get('temporal_relation', '')
                importance_reason = result_json.get('importance_reason', '')
                
                print(f"[Inference Agent] 时序扩展：选中事件 '{selected_event.get('name', '')}'")
                print(f"[Inference Agent] 时序扩展：时间关系 '{temporal_relation}'")
                
                # 返回扩展结果
                return [{
                    'type': 'temporal_extension',
                    'new_node': {
                        'name': selected_event.get('name', ''),
                        'time': selected_event.get('time', ''),
                        'entity': selected_event.get('entity', ''),
                        'source': selected_event.get('source', 'daily_event'),
                        'event_id': selected_event.get('event_id', '')
                    },
                    'temporal_relation': temporal_relation,
                    'importance_reason': importance_reason,
                    'start_node': first_node,
                    'target_date': target_date_str
                }]
        except Exception as e:
            print(f"[Inference Agent] 时序扩展：LLM 结果解析失败 ({e})")
            import traceback
            traceback.print_exc()
        
        return []
    
    def _extend_by_entity(self, graph: Dict[str, Any], daily_events: List[Dict]) -> List[Dict]:
        """
        基于实体扩展节点
        
        选择第一个节点，让 LLM 分析相关实体并确定日期，然后基于该日期及其前后各一天获取 daily_event，
        再调用 LLM 找到最相关的事件并输出为新节点。
        
        Args:
            graph: 初始推理图（包含 reasoning_chain）
            daily_events: daily_event 数据
            
        Returns:
            扩展的节点和边列表
        """
        print("[Inference Agent] 基于实体扩展节点")
        
        # 获取推理链条
        chain = graph.get('reasoning_chain', [])
        if not chain:
            print("[Inference Agent] 实体扩展：没有推理链条，跳过")
            return []
        
        if not self.draft_event:
            print("[Inference Agent] 实体扩展：没有 draft_event 数据，跳过")
            return []
        
        # 选取第一个节点
        first_step = chain[0]
        first_node = first_step.get('node', {})
        
        print(f"[Inference Agent] 实体扩展：使用第一个节点 '{first_node.get('name', '')}'")
        
        # 随机选择一个月份
        available_months = list(self.draft_event.keys())
        selected_month = random.choice(available_months)
        print(f"[Inference Agent] 实体扩展：随机选择月份 {selected_month}")
        
        # 获取该月份的 draft_event 数据
        month_events = self.draft_event.get(selected_month, [])
        if not month_events:
            print(f"[Inference Agent] 实体扩展：{selected_month} 没有事件数据")
            return []
        
        print(f"[Inference Agent] 实体扩展：让 LLM 分析实体并确定日期")
        
        # 第一步：LLM 分析实体并确定日期
        # 获取主角名字
        persona_name = self.persona.get('name', '') if hasattr(self, 'persona') and isinstance(self.persona, dict) else ''
        
        analysis_prompt = f"""
作为 Inference Agent，请分析起始节点和月份事件数据，找出相关的实体和目标事件，构建推理关系。

【主角姓名】
{persona_name}

【起始节点】
{json.dumps(first_node, ensure_ascii=False, indent=2)}

【月份事件数据】（{selected_month}）
{json.dumps(month_events[:15], ensure_ascii=False, indent=2) if len(month_events) > 15 else json.dumps(month_events, ensure_ascii=False, indent=2)}

**任务要求**

1. **分析起始节点的实体**
   - 从起始节点中提取关键实体，包括：
     * **人物**：除主角（{persona_name}）外的其他人物（如朋友、同事、家人等）
     * **地点**：事件发生的地点（如餐厅、公司、公园等）
     * **物品**：事件中涉及的物品（如礼物、文件、设备等）
   - **重要约束**：
     * **绝对不要将主角（{persona_name}）作为实体提取**
     * 重点找其他人物、地点、物品
     * 如果起始节点中只有主角，尝试提取地点或物品

2. **在月份事件中寻找能反映该实体的目标事件**
   - 基于提取的实体，在月份事件中寻找能体现该实体的其他事件
   - 思考方向：
     * **同一地点**：在该月，这个地点还发生了什么其他事情？
       - 例：起始节点是"在和平饭店过生日"，寻找"在和平饭店同事聚餐"
     * **同一人物**：在该月，这个人还做了什么其他重要的事情？
       - 例：起始节点是"和同事张三开会"，寻找"和张三一起健身"
     * **同一物品**：在该月，这个物品还出现在什么场景中？
       - 例：起始节点是"收到李四送的书籍"，寻找"和李四讨论这本书"

3. **设计推理关系**
   - 两个事件应该能通过实体形成一条推理链
   - 推理关系示例：
     * "我过生日" --(和平饭店)--> "同事聚餐"
     * "参加工作会议" --(张三)--> "和张三健身"
     * "收到礼物" --(书籍)--> "和朋友讨论书"

4. **确定目标日期**
   - 从选中的目标事件中确定一个具体的日期（YYYY-MM-DD 格式）
   - 这个日期应该是目标事件发生的日期

请以 JSON 格式返回：
{{
    "identified_entities": [
        {{
            "type": "人物/地点/物品",
            "value": "实体名称",
            "from_start_node": "该实体在起始节点中的描述"
        }}
    ],
    "target_event": {{
        "name": "目标事件名称",
        "date": "事件日期 (YYYY-MM-DD)",
        "entity_connection": "该事件如何反映上述实体"
    }},
    "target_date": "确定的目标日期 (YYYY-MM-DD)",
    "reasoning_relation": "推理关系描述，格式：'起始事件 --(实体)--> 目标事件'",
    "reason": "为什么选择这个实体和目标事件，它们如何形成推理关系"
}}

**示例**：
如果起始节点是"在和平饭店过十周岁生日"，识别的实体是"和平饭店（地点）"，
目标事件可能是"在和平饭店与同事聚餐"，推理关系是"我过生日 --(和平饭店)--> 同事聚餐"
"""
        
        llm_result = llm_call(analysis_prompt)
        
        if self.is_print:
            print("\n[Inference Agent - 实体分析] LLM 输出:")
            print(llm_result[:500] + "..." if len(llm_result) > 500 else llm_result)
        
        try:
            start_idx = llm_result.find('{')
            end_idx = llm_result.rfind('}') + 1
            if start_idx != -1 and end_idx != -1:
                analysis_json = json.loads(llm_result[start_idx:end_idx])
                target_date = analysis_json.get('target_date', '')
                identified_entities = analysis_json.get('identified_entities', [])
                
                print(f"[Inference Agent] 实体扩展：识别实体 {identified_entities}")
                print(f"[Inference Agent] 实体扩展：目标日期 {target_date}")
                
                if not target_date:
                    print("[Inference Agent] 实体扩展：未确定目标日期，跳过")
                    return []
                
                # 第二步：获取目标日期及其前后各一天的 daily_event
                from datetime import timedelta
                target_dt = datetime.strptime(target_date, '%Y-%m-%d')
                date_range = [
                    (target_dt + timedelta(days=-1)).strftime('%Y-%m-%d'),
                    target_date,
                    (target_dt + timedelta(days=1)).strftime('%Y-%m-%d')
                ]
                
                print(f"[Inference Agent] 实体扩展：搜索日期范围 {date_range}")
                
                # 筛选这三天的事件
                events_in_range = []
                for event in self.daily_event:
                    event_date = event.get('date', '')
                    if isinstance(event_date, list):
                        for time_range in event_date:
                            if '至' in time_range:
                                start_time = time_range.split('至')[0].strip()[:10]
                                if start_time in date_range:
                                    events_in_range.append(event)
                                    break
                            elif time_range[:10] in date_range:
                                events_in_range.append(event)
                                break
                
                if not events_in_range:
                    print(f"[Inference Agent] 实体扩展：日期范围内没有找到事件，跳过")
                    return []
                
                print(f"[Inference Agent] 实体扩展：找到 {len(events_in_range)} 个候选事件，让 LLM 选择最相关的")
                
                # 第三步：LLM 选择最相关的事件并生成新节点
                selection_prompt = f"""
作为 Inference Agent，请从以下事件中选出与起始节点最相关的一个，并生成新节点。

【起始节点】
{json.dumps(first_node, ensure_ascii=False, indent=2)}

【识别的实体】
{json.dumps(identified_entities, ensure_ascii=False)}

【候选事件】（{date_range[0]} 至 {date_range[2]}）
{json.dumps(events_in_range, ensure_ascii=False, indent=2)}

**任务要求**

1. **选择最相关的事件**
   - 基于识别的实体，选择与起始节点最相关的事件
   - 考虑实体匹配度、事件关联性

2. **生成新节点**
   - 基于选中的事件创建新节点
   - 包含：名称、时间、实体、来源、event_id

3. **建立实体关系**
   - 描述新节点与起始节点的实体关系
   - 解释为什么这两个事件通过实体关联

请以 JSON 格式返回：
{{
    "selected_event": {{
        "name": "事件名称",
        "time": "时间信息",
        "entity": "主要涉及的实体",
        "source": "来源",
        "event_id": "事件 ID（必须从候选事件中获取真实 ID，禁止自行编造或填写不存在于候选事件中的 ID）"
    }},
    "entity_relation": "实体关系描述（如'同一人物'、'相关地点'等）",
    "relation_description": "详细说明两个事件如何通过实体关联"
}}
"""
                
                selection_result = llm_call(selection_prompt)
                
                if self.is_print:
                    print("\n[Inference Agent - 事件选择] LLM 输出:")
                    print(selection_result[:500] + "..." if len(selection_result) > 500 else selection_result)
                
                sel_start_idx = selection_result.find('{')
                sel_end_idx = selection_result.rfind('}') + 1
                if sel_start_idx != -1 and sel_end_idx != -1:
                    selection_json = json.loads(selection_result[sel_start_idx:sel_end_idx])
                    
                    selected_event = selection_json.get('selected_event', {})
                    entity_relation = selection_json.get('entity_relation', '')
                    relation_description = selection_json.get('relation_description', '')
                    
                    print(f"[Inference Agent] 实体扩展：选中事件 '{selected_event.get('name', '')}'")
                    print(f"[Inference Agent] 实体扩展：实体关系 '{entity_relation}'")
                    
                    # 返回扩展结果
                    return [{
                        'type': 'entity_extension',
                        'new_node': {
                            'name': selected_event.get('name', ''),
                            'time': selected_event.get('time', ''),
                            'entity': selected_event.get('entity', ''),
                            'source': selected_event.get('source', 'daily_event'),
                            'event_id': selected_event.get('event_id', '')
                        },
                        'entity_relation': entity_relation,
                        'relation_description': relation_description,
                        'start_node': first_node,
                        'target_date': target_date,
                        'identified_entities': identified_entities
                    }]
        except Exception as e:
            print(f"[Inference Agent] 实体扩展：处理失败 ({e})")
            import traceback
            traceback.print_exc()
        
        return []
    
    def _extend_by_fabrication(self, graph: Dict[str, Any]) -> List[Dict]:
        """
        基于编造扩展节点
        
        选择第一个节点，编造该节点对应实体的短信数据作为新节点。
        
        Args:
            graph: 初始推理图（包含 reasoning_chain）
            
        Returns:
            扩展的节点和边列表
        """
        print("[Inference Agent] 基于编造扩展节点")
        
        # 获取推理链条
        chain = graph.get('reasoning_chain', [])
        if not chain:
            print("[Inference Agent] 编造扩展：没有推理链条，跳过")
            return []
        
        # 选取第一个节点
        first_step = chain[0]
        first_node = first_step.get('node', {})
        
        print(f"[Inference Agent] 编造扩展：使用第一个节点 '{first_node.get('name', '')}'")
        
        # 调用 LLM 编造短信数据
        fabrication_prompt = f"""
作为 Inference Agent，请基于起始节点编造一条相关的短信数据，并生成新的推理节点。

【起始节点】
{json.dumps(first_node, ensure_ascii=False, indent=2)}

**任务要求**

1. **选择实体类型**（二选一）
   - **地点实体**：选择起始节点中的某个地点（如餐厅、公司、公园等）
   - **人物实体**：选择起始节点中的某个人物（除主角外的其他人，如朋友、同事、家人等）
   - 注意：不要选择主角（冯浩然）作为实体

2. **编造与该实体相关但与主角生活无关的事件**
   
   **如果选择地点实体**：
   - 编造他人在该地点发生的事件，与主角无关
   - 示例：
     * 起始节点："在星巴克开会" → 编造："昨天看到李四和王五在星巴克讨论项目"
     * 起始节点："去健身房" → 编造："听说张三最近在健身房遇到了老同学"
   
   **如果选择人物实体**：
   - 编造该人物发生的其他事件，与主角无关
   - 示例：
     * 起始节点："和同事张三开会" → 编造："张三说他周末要去参加马拉松"
     * 起始节点："和朋友李四吃饭" → 编造："李四告诉我他下个月要搬家"

3. **时间和独立性要求**
   - **时间要求**：编造的事件必须发生在起始节点时间之前（至少提前1天）
   - **独立性要求**：编造的事件与起始节点的事件无任何关联
     * 不是起始事件的背景、原因或结果
     * 不是起始事件的准备或后续
     * 是完全独立的另一件事
   - 示例：
     * 起始节点："2025-01-15 在星巴克开会"
     * 编造事件："2025-01-10 李四在星巴克遇到老同学"（时间在前，独立事件）
     * 错误示例："2025-01-14 李四说要在星巴克开会"（有关联，错误）

4. **生成短信内容**
   - 短信应该是他人发送给主角的，或者主角收到的关于该事件的间接信息
   - 短信内容要自然，像是日常聊天中偶然得知的信息
   - 短信应该暗示这个事件的存在，但不直接说明全部细节
   - 示例：
     * "昨天路过星巴克，看到李四和王五在里面聊得很热烈"
     * "张三说他周末要去跑马拉松，让我给他加油"
     * "听王五说，李四下个月要搬到浦东去了"

5. **确定短信时间**
   - 短信时间应该在起始节点时间的合理范围内（前后几天内）
   - 格式：YYYY-MM-DD HH:MM:SS

6. **生成新节点**
   - 基于编造的短信创建新节点
   - 包含：短信内容摘要、时间、涉及的实体、来源（fabricated_sms）

请以 JSON 格式返回：
{{
    "selected_entity": {{
        "type": "地点/人物",
        "value": "实体名称",
        "from_start_node": "该实体在起始节点中的描述"
    }},
    "fabricated_event": "编造的事件描述（与主角生活无关）",
    "fabricated_sms": {{
        "content": "短信具体内容",
        "sender": "发送者（可以是起始节点中的人物或其他相关人物）",
        "receiver": "接收者（通常是主角）",
        "time": "短信时间 (YYYY-MM-DD HH:MM:SS)"
    }},
    "new_node": {{
        "name": "节点名称（短信内容摘要）",
        "time": "短信时间",
        "entity": "主要涉及的实体",
        "source": "fabricated_sms"
    }},
    "relation_to_start": "与起始节点的关系描述",
    "reasoning_value": "这条短信如何增加推理链条的深度和难度"
}}

**重要提醒**：
- 编造的事件必须与主角（冯浩然）的生活无关
- 事件应该是他人的独立活动或发生在某地点的其他事情
- 短信应该是间接得知这些信息的方式
- **编造事件的时间必须在起始节点时间之前**
- **编造事件与起始节点事件无任何关联（不是背景、原因、结果、准备或后续）**
"""
        
        llm_result = llm_call(fabrication_prompt)
        
        if self.is_print:
            print("\n[Inference Agent - 编造扩展] LLM 输出:")
            print(llm_result[:500] + "..." if len(llm_result) > 500 else llm_result)
        
        try:
            start_idx = llm_result.find('{')
            end_idx = llm_result.rfind('}') + 1
            if start_idx != -1 and end_idx != -1:
                result_json = json.loads(llm_result[start_idx:end_idx])
                
                fabricated_sms = result_json.get('fabricated_sms', {})
                new_node = result_json.get('new_node', {})
                relation_to_start = result_json.get('relation_to_start', '')
                reasoning_value = result_json.get('reasoning_value', '')
                
                print(f"[Inference Agent] 编造扩展：短信内容 '{fabricated_sms.get('content', '')[:50]}...'")
                print(f"[Inference Agent] 编造扩展：新节点 '{new_node.get('name', '')}'")
                
                # 返回扩展结果
                return [{
                    'type': 'fabrication_extension',
                    'new_node': new_node,
                    'fabricated_sms': fabricated_sms,
                    'relation_to_start': relation_to_start,
                    'reasoning_value': reasoning_value,
                    'start_node': first_node
                }]
        except Exception as e:
            print(f"[Inference Agent] 编造扩展：处理失败 ({e})")
            import traceback
            traceback.print_exc()
        
        return []
    
    def _build_inference_chain(self, initial_graph: Dict[str, Any], 
                              extended_nodes: List[Dict]) -> Dict[str, Any]:
        """
        构建完整的推理链条
        
        直接将新增节点和边并入 initial_graph
        
        Args:
            initial_graph: 初始推理图（包含 nodes, edges, reasoning_chain）
            extended_nodes: 扩展的节点列表
            
        Returns:
            完整的推理图
        """
        print("[Inference Agent] 构建完整推理链条")
        
        # 获取初始图的节点和边
        nodes = initial_graph.get('nodes', [])
        edges = initial_graph.get('edges', [])
        reasoning_chain = initial_graph.get('reasoning_chain', [])
        
        print(f"[Inference Agent] 初始图：{len(nodes)} 个节点，{len(edges)} 条边")
        print(f"[Inference Agent] 扩展节点数：{len(extended_nodes)}")
        
        # 将扩展节点并入图中
        for ext_node in extended_nodes:
            new_node = ext_node.get('new_node', {})
            extension_type = ext_node.get('type', '')
            
            # 生成新节点 ID
            node_id = f"node_{len(nodes) + 1}"
            
            # 添加新节点（包含 event_id）
            nodes.append({
                'id': node_id,
                'name': new_node.get('name', ''),
                'time': new_node.get('time', ''),
                'entity': new_node.get('entity', ''),
                'source': new_node.get('source', ''),
                'event_id': new_node.get('event_id', ''),
                'extension_type': extension_type
            })
            
            # 添加连接到起始节点的边
            if reasoning_chain:
                start_node_id = 'node_1'  # 第一个节点
                relation_desc = ext_node.get('relation_to_start', '') or \
                               ext_node.get('temporal_relation', '') or \
                               ext_node.get('entity_relation', '') or \
                               '扩展节点'
                
                edges.append({
                    'from': start_node_id,
                    'to': node_id,
                    'relation': extension_type,
                    'description': relation_desc
                })
        
        print(f"[Inference Agent] 完整推理图：{len(nodes)} 个节点，{len(edges)} 条边")
        
        # 打印最终的完整推理图
        print(f"\n[Inference Agent] === 最终推理图详情 ===")
        print(f"\n节点列表（共 {len(nodes)} 个）：")
        for idx, node in enumerate(nodes, 1):
            print(f"\n  节点 {idx} ({node.get('id', '')}):")
            print(f"    - 名称: {node.get('name', '')}")
            print(f"    - 时间: {node.get('time', '')}")
            print(f"    - 实体: {node.get('entity', '')}")
            print(f"    - 来源: {node.get('source', '')}")
            print(f"    - 事件 ID: {node.get('event_id', '')}")
            if node.get('extension_type'):
                print(f"    - 扩展类型: {node.get('extension_type')}")
        
        print(f"\n边列表（共 {len(edges)} 条）：")
        for idx, edge in enumerate(edges, 1):
            print(f"\n  边 {idx}:")
            print(f"    - 从: {edge.get('from', '')}")
            print(f"    - 到: {edge.get('to', '')}")
            print(f"    - 关系: {edge.get('relation', '')}")
            print(f"    - 描述: {edge.get('description', '')}")
        
        # 更新 initial_graph
        initial_graph['nodes'] = nodes
        initial_graph['edges'] = edges
        
        return initial_graph
    
    def generate_question_and_data(self, inference_chain: Dict[str, Any]) -> Dict[str, Any]:
        """
        基于推理链条生成问题和手机数据
        
        Args:
            inference_chain: 推理链条信息（包含 nodes, edges, reasoning_chain）
            
        Returns:
            生成的问题和手机数据
        """
        print("[Generate Question & Data] 生成问题和手机数据")
        
        # 提取 nodes 和 edges
        nodes = inference_chain.get('nodes', [])
        edges = inference_chain.get('edges', [])
        
        if not nodes or len(nodes) < 2:
            print("[Generate Question & Data] 推理链条太短，无法生成问题")
            return {}
        
        # 根据 nodes 中的 event_id 收集对应的 daily_event
        involved_daily_events = []
        for node in nodes:
            event_id = node.get('event_id', '')
            if event_id:
                # 在 daily_event 中查找对应事件
                for event in self.daily_event:
                    if str(event.get('event_id', '')) == str(event_id):
                        involved_daily_events.append(event)
                        break
        
        print(f"[Generate Question & Data] 涉及 {len(nodes)} 个节点，{len(edges)} 条边")
        print(f"[Generate Question & Data] 找到 {len(involved_daily_events)} 个对应的 daily_event")
        
        # Step 1: 基于推理链生成问题
        # 确定目标事件（推理链的起始节点）
        target_node = nodes[0] if nodes else {}
        target_event_name = target_node.get('name', '')
        target_event_time = target_node.get('time', '')
        
        # 获取目标事件前后各一天的 daily_event 作为背景素材
        background_events = self._get_background_events_for_target(target_event_time)
        background_events_desc = json.dumps(background_events, ensure_ascii=False, indent=2) if background_events else "无背景事件"
        
        question_prompt = f"""
作为 Question Generator，请基于推理链条为用户{self.persona_data.get('name', '用户')}的生活生成一个高质量的多跳推理问题。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【输入数据参考】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**推理节点**（可供选择的节点池）：
{json.dumps(nodes, ensure_ascii=False, indent=2)}

**推理边**（节点间的关系）：
{json.dumps(edges, ensure_ascii=False, indent=2)}

**目标事件**（推理链的起点）：
- 名称：{target_event_name}
- 时间：{target_event_time}

**背景事件**（目标事件前后各一天的 daily_event，可作为设计问题的参考素材）：
{background_events_desc}

⚠️ **核心约束**：最终问题中绝对不能直接提及目标事件的任何信息（名称、时间、地点、人物等），必须通过多步推理才能得出答案。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【思考过程】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Step 1: 设计初始多跳问题

**优先策略：设计涉及多个事件信息的询问**

- 从推理节点或背景事件中选择多个相关联的事件，设计一个需要整合这些事件信息才能回答的问题
- 示例：
  * 事件1："1月19号完成体检调研表"
  * 事件2："1月20号基于调研表和哥哥讨论"
  * ✅ 好问题："我1月和哥哥讨论的内容是什么时候制定的？"
    - 答案需要整合：讨论内容（来自事件2） + 制定时间（来自事件1）
  * ✅ 好问题："我1月下旬关于健康体检做了哪些事情？"
    - 答案需要整合：填写的项目（来自事件1） + 讨论对象（来自事件2）

- 针对同一时间段或同一主题的多个事件，设计一个需要汇总所有相关信息的问题
- 示例：
  * 事件1："1月15号和小红在公园跑步"
  * 事件2："1月18号和小红在湖边跑步"
  * 事件3："1月20号和小红在操场跑步"
  * ✅ 好问题："1月15号到20号这段时间我和小红去了哪些地方跑步？"
    - 答案需要整合：所有跑步地点（公园、湖边、操场）
  * 事件1："3月5号去北京出差"
  * 事件2："3月12号去上海开会"
  * 事件3："3月20号去广州参加展览"
  * ✅ 好问题："我3月份都去了哪些城市出差或参加活动？"
    - 答案需要整合：所有城市（北京、上海、广州）

💡 **关键原则**：
- 多信息整合类问题的特点是：**问题指向一个时间段或主题，答案需要汇总该范围内的所有相关事件信息**
- 这类问题天然需要多跳推理，因为需要从多个事件中抽取信息并整合
- 适合用于考察记忆系统对一段时间内同类事件的汇总能力

**备选策略：若难以设计多事件问题，可设计单跳查询问题**
- 针对目标事件设计一个直接的查询问题
- 示例："3月4号我在和平饭店庆祝生日的时候和小明交谈了什么？"

💡 **关键原则**：
- 初始问题可以包含目标事件的直接信息（后续会被替换掉）
- 记录已使用的节点，后续替换时不得再次使用
- 根据事件发生频率决定时间表述粒度（一年一次不用加月份，一月一次加月份，多次发生加具体日期）

### Step 2: 选择替换方案

使用以下两种替换方式，将初始问题中的目标事件信息逐步替换为需要通过推理才能得出的描述：

**① 实体替换**（同实体关系）
- 用具有相同实体（地点、人物、物品等）的其他事件来替换
- ⚠️ **重要约束**：**不得提取用户主体（主角/"我"）作为同实体来替换**
  * ❌ 错误："我" → "那天去跑步的人"（禁止，因为"我"是用户主体）
  * ✅ 正确："和平饭店" → "我2月同事聚餐的地方"（地点替换）
  * ✅ 正确："小明" → "那天散步时遇到的邻居"（其他人物替换）
  * ✅ 正确："笔记本电脑" → "上周刚买的那台设备"（物品替换）

**② 因果替换**（因果/目的关系）
- 用导致目标事件的原因或目标事件导致的结果来替换
- 示例：
  * "过生日" → "和小红在3月2号计划要做的事情"
  * "庆祝生日" → "完成那个需要三个材料准备的任务后举行的活动"

**③ 描述替换**（相关关系）
- 用与其他事件的描述来替换想询问的目标事件的描述，要求两个事件之间有明确的关联关系或相对关系。
- 示例：
    * "在和平饭店庆祝生日" → "在我2月同事聚餐的地方"
    * "和小明交谈" → "我们出门散步快回家时遇见的事情"


⚠️ **关键约束**：
- 每次替换都必须使用**未使用节点**（即初始问题中未涉及的节点）
- 分析问题的难度来选择是否进行替换，确保问题需要多步推理，可以不进行任何替换
- 替换后的描述应该自然流畅，不要生硬

### Step 3: 总体分析润色

**这是最关键的一步，可以选择性取消之前的替换策略，重新设计问题和答案**

**检查清单**：
1. **自然流畅性**：问题读起来是否自然？是否因为多次替换导致题面不自然、拗口？
2. **多跳推理要求**：是否需要至少 2-3 步推理或者需要整合多个事件的信息才能得出答案？
3. **信息隐藏**：问题中是否完全不包含目标事件的直接信息，是否包含了多余的没必要的信息导致问题难度下降？
4. **合理性**：问题是否有实际意义？答案是否能从提供的节点中推理出来？
5. **质量保障**：问题是否清晰、无歧义？
6. **月份信息包含**：题面是否明确包含月份信息？
7. **信息减少**：删除题面中包含的一些细节信息，尽可能多的减少信息量，但要保证问题可回答。例如我XX会上的主题为"植树节"的ppt是什么时候制作的？应该修改为我XX会上的ppt什么时候制作的？去除不必要的信息。

**如果发现问题不自然或不合理**：
- ✅ **可以完全重新设计问题和答案**，不必拘泥于之前的替换步骤
- ✅ **可以调整替换策略**，选择不同的节点或替换方式
- ✅ **可以简化或复杂化问题**，以确保质量和合理性
- ✅ **最终目标是**：一个自然流畅、需要多跳推理、信息隐藏得当的高质量问题

**润色示例**：
- ❌ 不自然："在我晋升主管的10天前，我在我2月同事聚餐的地方，做那件和小红在3月2号计划要做的事情时，和那天散步时遇到的邻居交谈了什么？"
- ✅ 润色后："我2月同事聚餐那天，我和散步时遇到的那位邻居聊起了之前和小红计划的事情，我们主要谈了什么？"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【任务要求】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. **选择关键节点**
   - 从提供的推理节点和背景事件中灵活选择必要的节点
   - 不需要使用所有节点，也可以完全不参考推理链的关系，自行设计推理，但必须确保能形成完整的推理链
   - 选择的节点应该能推导出目标事件的信息
   - 记录所选节点的 event_id

2. **生成问题**
   - ❌ 绝对禁止：问题中不能出现目标事件的任何直接信息
   - ✅ 明确月份：至少明确指出一个节点的月份，其他用相对时间或实体指代
   - ✅ 问题焦点：询问目标事件的某个具体信息（做了什么、在哪里、和谁、为什么等）

3. **生成标准答案**
   - 详细说明完整的推理过程（每一步都要清晰）
   - 明确指出最终推理出的目标事件信息

4. **生成评分要点**
   - 分解为 2-4 个评分要点，每个要点对应推理链中的一个关键步骤
   - 总分 10

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【输出格式】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
请以JSON格式输出：
{{
    "initial_question": "设计的初始直接问题（基于目标事件或多个相关事件设计多跳初始问题，尽量需要整合多个事件/节点才能得出答案）",
    "replacement_process": [
        {{
            "step": 1,
            "replacement_type": "实体替换/因果替换/描述替换",
            "original": "被替换的原始信息",
            "replaced_with": "替换后的描述",
            "reason": "为什么这样替换（推理关系说明）",
            "question_after_replacement": "替换后的问题"
        }}
    ],
    "polished_question": "替换策略执行后，经过润色优化的最终问题（确保自然流畅、符合多跳推理要求）",
    "question": "最终的多跳推理问题（与 polished_question 相同，或进一步调整后的版本，注意包含月份信息）",
    "answer": "标准答案（只需最终结论）",
    "score_points": [
        {{"description": "评分要点描述", "score": 分数}}
    ],
    "required_events_id": ["选中的节点对应的 event_id 列表（必须是 daily_event 中的真实 event_id，不能使用 node_1、node_2 等内部节点 ID）"]
}}

**【关键约束】required_events_id 格式要求：
- 必须填写 daily_event 中真实存在的 event_id 字符串
- 禁止使用 node_1、node_2、node_3 等推理图内部节点 ID
- 禁止使用空字符串或自行编造的 event_id
- 如果节点没有真实的 event_id，请从节点的 source 字段判断其来源，填写对应 daily_event 的 event_id

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【自检清单】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- [ ] 是否需要整合多个事件信息才能得出答案？
- [ ] **题面是否明确了至少一个节点的月份？**
- [ ] 推理路径是否清晰、合理？
- [ ] **题面是否清晰明确，没有模糊表述**？
- [ ] **答案是否可以被唯一推导出来，不存在歧义**？
- [ ] 题面是否有过于丰富的信息，尽可能减少信息和去除细节，来提高问题难度，但要保证足够回答问题的信息量。

**题面清晰度检查**：
- 问题中的每个指代（如"那个地方"、"那个人"、"那件事"）是否都有明确的推理路径可以定位？
- 是否存在多个可能的事件都符合描述，导致答案不唯一？
- 示例：
  - ❌ 模糊："我去过的那个地方" （可能指多个地方）
  - ✅ 清晰："我2月同事聚餐的那个地方" （唯一定位到2月的聚餐事件）

**答案可推导性检查**：
- 从问题出发，是否能通过推理链唯一确定答案？
- 是否存在多种可能的解释或答案？
- 示例：
  - ❌ 不可推导："我和某人见面时聊了什么？"（"某人"不确定，"聊了什么"无法推导）
  - ✅ 可推导："我和那天散步时遇到的邻居交谈了什么？"（"那天散步时遇到的邻居"可以唯一定位到具体人物，进而推导出交谈内容）

如果以上任何一项不满足，请重新设计问题。
"""
        print("[Generate Question & Data] LLM 输入:", question_prompt)
        llm_result = llm_call_reason_j(question_prompt)
        print("[Generate Question & Data] LLM 输出:", llm_result)
        if self.is_print:
            print("\n[Question Generator] LLM 输出:")
            print(llm_result[:500] + "..." if len(llm_result) > 500 else llm_result)
        
        try:
            start_idx = llm_result.find('{')
            end_idx = llm_result.rfind('}') + 1
            if start_idx != -1 and end_idx != -1:
                question_json = json.loads(llm_result[start_idx:end_idx])
                question = question_json.get('question', '')
                answer = question_json.get('answer', '')
                score_points = question_json.get('score_points', [])
                required_events_id = question_json.get('required_events_id', [])
                
                print(f"[Generate Question & Data] 生成问题: {question[:80]}...")
                print(f"[Generate Question & Data] 答案长度: {len(answer)} 字符")
                print(f"[Generate Question & Data] 所需事件 ID: {required_events_id}")

                # 获取 required_events_id 对应的 daily_event 数据
                required_events_data = {}
                for eid in required_events_id:
                    event_data = self._find_event_by_id(str(eid), self.daily_event)
                    if event_data:
                        required_events_data[str(eid)] = event_data

#                 # Step 1.5: 检查并优化问题
#                 check_prompt = f"""
# 作为 Question Reviewer，请检查并优化以下多跳推理问题的质量。尽量不对原问题做大的修改。

# 【当前问题】
# {question}

# 【当前答案】
# {answer}

# 【相关事件数据】
# {json.dumps(required_events_data, ensure_ascii=False, indent=2)}

# **检查标准**

# 1. **问题答案一致性**
#    - 问题是否清晰无歧义？
#    - 答案是否正确回答了问题？
#    - 答案是否包含问题要求回答的之外的信息？(若包含考虑增加问题的提问内容)

# 2. **多跳特性**
#    - 是否需要结合多个事件信息才能回答？
#    - 是否需要多步骤推理？

# 3. **复杂性**
#    - 是否有一定推理难度？
#    - 是否过于简单直接？
#    - 是否可以通过模糊/减少题面的信息来增加难度？（但要保证可回答性）

# 4. **信息冗余/完整**
#    - 是否有不影响答案的冗余描述？
#    - 是否可以简化而不影响回答？
#    - 注意分析有些事件可能会经常发生（如晨跑，吃饭，这类事件一般要明确时间约束才能定位，比如2月下旬的那次晨跑，3月5日的午饭时，如果直接题面说那次晨跑时，会导致回答者根本无法确定是哪次晨跑，这属于信息不充足，需要优化题面添加时间约束）

# 在完成上述检查并重新设计了问题后，对新的问题进行进一步优化:
# **优化步骤**
# 在答案不变、题面整体目标不变的前提下：
# 1. 找出题面中过于丰富、明确、冗余的信息
# 2. 用更模糊的表达替换（如具体日期→X月，但对于可能在一年内多次发生的事情请不要让题面一点时间信息都没有，请加上X月，X-2月后，年初，春季等类似描述约束）
# 3. 删除不影响推理的冗余描述
# 4. 确保优化后问题仍可回答

# **输出格式**
# 请以 JSON 格式返回：
# {{
#     "is_valid": true/false,
#     "issues": ["问题列表（如果没有则为空数组）"],
#     "improved_question": "优化后的问题（如果无需优化则与原问题相同）",
#     "improved_answer": "优化后的答案（如果无需优化则与原答案相同）",
#     "reason": "优化说明或保持原样的原因"
# }}
# """
#                 print("[Generate Question & Data] 开始检查问题质量...")
#                 check_result = llm_call_j(check_prompt)
#                 print("[Generate Question & Data] 检查结果:", check_result)
                
#                 try:
#                     start_idx = check_result.find('{')
#                     end_idx = check_result.rfind('}') + 1
#                     if start_idx != -1 and end_idx != -1:
#                         check_json = json.loads(check_result[start_idx:end_idx])
#                         is_valid = check_json.get('is_valid', True)
#                         issues = check_json.get('issues', [])
#                         improved_question = check_json.get('improved_question', question)
#                         improved_answer = check_json.get('improved_answer', answer)
#                         reason = check_json.get('reason', '')
                        
#                         if not is_valid or issues:
#                             print(f"[Generate Question & Data] 发现问题: {issues}")
#                             print(f"[Generate Question & Data] 改进原因: {reason}")
#                             question = improved_question
#                             answer = improved_answer
#                             print(f"[Generate Question & Data] 改进后问题: {question[:80]}...")
#                         else:
#                             print(f"[Generate Question & Data] 问题质量良好，无需改进")
#                 except Exception as e:
#                     print(f"[Generate Question & Data] 问题检查失败: {e}，使用原始问题")
#                     import traceback
#                     traceback.print_exc()
                
                # 构建 QA 结果
                qa_result = {
                    'question': question,
                    'answer': answer,
                    'score_points': score_points,
                    'required_events_id': required_events_id,
                    'evidence':[],
                    'question_type': 'Multi_hop'
                }

                # Step 3: 检查相似事件混淆问题
                print("\n[Generate Question & Data] Step 3: 检查相似事件混淆...")
                qa_result = self._check_similar_events_confusion(qa_result)

                # 验证 required_events_id，过滤无效的 event_id（如 node_1, node_2 等）
                validated_ids = []
                for rid in required_events_id:
                    rid_str = str(rid)
                    # 检查是否是有效的 event_id（必须是数字或匹配 daily_event 中存在的 event_id）
                    if rid_str.startswith('node_'):
                        print(f"[Generate Question & Data] 警告：required_events_id={rid_str} 是无效的节点ID，已跳过")
                        continue
                    # 检查是否在 daily_event 中存在
                    found = False
                    for event in self.daily_event:
                        if str(event.get('event_id', '')) == rid_str:
                            found = True
                            break
                    if found:
                        validated_ids.append(rid_str)
                    else:
                        print(f"[Generate Question & Data] 警告：required_events_id={rid_str} 在 daily_event 中未找到，已跳过")
                        validated_ids.append(rid_str)  # 保留以便追踪

                qa_result['required_events_id'] = validated_ids
                
                # Step 2: 调用 evidence_refine 进行证据优化
                month_key = f"{datetime.now().year}-{datetime.now().month:02d}"
                qa_result = self.evidence_refine(qa_result, month_key)
                
                return qa_result
            else:
                print("[Generate Question & Data] 无法解析 LLM 输出")
                return {
                    'question': '',
                    'answer': '',
                    'reasoning_chain': inference_chain,
                    'phone_data': []
                }
        except Exception as e:
            print(f"[Generate Question & Data] 问题生成失败: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def evidence_refine(self, question: Dict[str, Any], month_key: str) -> Dict[str, Any]:
        """
        Evidence Refine: 分析并优化问题的证据数据，确保手机数据能够充足反映事件并提供足够回答问题的数据

        Args:
            question: 优化后的问题
            month_key: 月份标识

        Returns:
            优化证据后的问题
        """
        print(f"\n[Evidence Refine] 开始优化 {month_key} 的证据数据...")

        # 获取 required_events_id 列表
        required_events_ids = question.get('required_events_id', [])
        if not required_events_ids:
            print("[Evidence Refine] 无需补充证据数据")
            return question

        # 初始化操作列表
        to_generate = []
        to_delete = []

        # 定义允许的操作类型
        ALLOWED_OP_TYPES = {'sms', 'phonecall', 'photo', 'push', 'note', 'calendar'}

        print(f"[Evidence Refine] 收集 {len(required_events_ids)} 个事件的证据数据...")

        # 收集所有事件及其现有证据
        all_events_evidence = []
        for event_id in required_events_ids:
            # 在 daily_event 中查找对应事件
            target_event = None
            if isinstance(self.daily_event, list):
                for event in self.daily_event:
                    event_id_in_event = event.get('event_id', '')
                    if str(event_id_in_event) == str(event_id):
                        target_event = event
                        break
                    # 也检查一下整数类型
                    try:
                        if int(event_id_in_event) == int(event_id):
                            target_event = event
                            break
                    except (ValueError, TypeError):
                        pass

            if not target_event:
                print(f"[Evidence Refine - {event_id}] 未找到事件，跳过")
                continue

            # 获取事件信息
            event_date = target_event.get('date', [])
            event_description = target_event.get('description', '')

            # 从手机数据中查找与该事件对应的数据（基于 event_id 匹配）
            existing_evidence = []
            if self.phonedata:
                with self.phonedata_lock:  # 加锁保护共享数据
                    for data_type, data_list in self.phonedata.items():
                        if isinstance(data_list, list):
                            for item in data_list:
                                if isinstance(item, dict):
                                    # 检查 daily_event_id 或 related_event 字段
                                    item_event_id = str(item.get('daily_event_id', ''))
                                    related_event = str(item.get('related_event', ''))

                                    # 如果匹配，添加完整的操作数据
                                    if item_event_id == str(event_id) or related_event == str(event_id):
                                        existing_evidence.append({
                                            'type': data_type,
                                            'data': item,
                                            'phone_id': item.get('phone_id', '')
                                        })

            print(f"[Evidence Refine - {event_id}] 找到 {len(existing_evidence)} 条现有相关数据")

            # 添加到所有事件列表
            all_events_evidence.append({
                'event_id': event_id,
                'event_description': event_description,
                'event_date': event_date,
                'existing_evidence': existing_evidence
            })

        print(f"\n[Evidence Refine] 共收集 {len(all_events_evidence)} 个事件的证据")

        # 构建所有事件的信息字符串
        events_info_str = ""
        for idx, evt_data in enumerate(all_events_evidence, 1):
            events_info_str += f"\n【事件 {idx}】\n"
            events_info_str += f"- 事件 ID: {evt_data['event_id']}\n"
            events_info_str += f"- 事件描述：{evt_data['event_description']}\n"
            events_info_str += f"- 事件日期：{json.dumps(evt_data['event_date'], ensure_ascii=False)}\n"
            events_info_str += f"- 现有手机数据证据（共{len(evt_data['existing_evidence'])}条）：\n"
            events_info_str += json.dumps([
                {
                    'type': ev['type'],
                    'phone_id': ev['phone_id'],
                    'data_summary': str(ev['data'])[:200]
                } for ev in evt_data['existing_evidence']
            ], ensure_ascii=False, indent=2)
            events_info_str += "\n"

        # 使用 LLM 一次性分析所有事件的证据是否充足，以及需要增删哪些数据
        analysis_prompt = f"""
作为数据分析师，请分析以下问题、答案和多个事件的证据数据。

【任务背景】
您正在为问题的回答设计证据。这些证据是手机操作数据（包括短信、通话、照片、推送通知、笔记、日历等），手机智能助手会基于这些手机操作推理并回答问题。

【问题与答案】
- 问题：{question.get('question', '')}
- 答案：{question.get('answer', '')[:500]}{'...' if len(question.get('answer', '')) > 500 else ''}

【所有事件及其证据】
{events_info_str}

【可生成的数据类型】
sms, phonecall, photo, push, note, calendar

**重要原则**
1. **多跳推理设计（核心原则，设计生成数据时参考，生成多个数据）**：
   - 生成的手机数据必须分散在多个操作中，使得信息碎片化，确保回答问题需要整合多个操作的信息
   - 不要在单个手机操作中包含完整答案信息
   - 每个操作只提供部分线索，需要通过多个操作的组合才能推理出完整答案
   - **示例**：
     - ❌ 错误：一个笔记包含"凌晨2点处理35床心衰的全过程"
     - ✅ 正确：分散为多条数据，每个类型的数据表示不同的碎片信息。
       * 短信："今晚加班，可能很晚回去"
       * 日历："凌晨2点，35床急诊"
       * 笔记："标注35床心衰病例重点"
2. **降低重复性**：只有当确定缺乏关键信息，或缺乏足以支持回答的信息时，才考虑新增数据表达缺失信息。但是，一旦当你决定新增数据，就尽量为这个事件和目标信息生成多个不同类型的手机操作，把要补充的信息分散在多个操作中，这些操作之间形成信息互补关系。生成的手机操作的信息不要和已有信息重合。
3. **重点优先**：不需要全面反映出事件的所有细节，只关注与问题相关的重点内容。
   - 例如：问题可能只问跑步频率，那只要手机数据能反映出用户跑步了就行，至于距离、时间可以不关心
   - 例如：如果问题问了跑量，则需要反映公里数
4. **互补性原则**：如果要生成新数据，必须与已有数据形成互补关系，不要和已有数据反映同样的信息。
   - **检查已有数据**：先看看已经有了什么信息
   - **补充缺失信息**：只生成能提供新信息的数据
   - **避免重复**：**严禁**生成与已有数据内容重复或高度相似的数据
   - **示例**：
     - ✅ 已有一条短信提到"今天跑了 5 公里"，但缺少具体时间 → 生成推送"您于 07:30 完成晨跑 5 公里"
     - ❌ 已有短信"今天跑了 5 公里"，又生成笔记"今天早上我跑了 5 公里"（信息重复）
5. **最小信息量**：当要新增手机数据时：
   - 先分析缺少的具体信息是什么
   - 只生成包含缺少信息的数据，不要在数据中反映所有信息
   - **禁止**生成一个包含了事件所有信息或可以直接反映答案的充足数据（如一个反映了所有信息的笔记/信息）
   - **示例**：
     - ✅ 缺少跑步公里数：生成短信"今天跑步的公里数记录在keep app里"和推送"[keep]你今日已运动 5 公里，十分健康"
     - ❌ 不要生成：一条详细的跑步笔记，包含时间、路线，配速，心率等完整信息
6. **谨慎删除**：**除非数据不合理且会干扰回答问题，否则不要删除手机数据**。仅在数据存在明显错误或矛盾情况下考虑删除，有些数据是合理的噪声。当选择删除操作时，考虑该手机数据是否有事件相关的信息需要反应，如有则生成对应的新增操作。

**分析任务**
请逐个分析每个事件的证据数据：
1. 现有手机数据是否充分反映了该事件的关键信息？
2. 该事件的重要信息是否都在手机数据中有所体现？
3. 如果不足，最需要补充哪些关键数据来完整展现该事件？（尽可能少地增加）
4. 如果有与该事件不相关或冗余的数据，应该删除哪些？
5. 手机数据是否满足多跳推理设计原则？

**输出格式**
请以 JSON 格式返回，针对每个事件分别给出分析结果：
{{
    "overall_analysis": "对所有事件证据的整体分析",
    "events_analysis": [
        {{
            "event_id": "事件 ID",
            "sufficiency_analysis": "对现有数据是否充分反映该事件的分析",
            "to_generate": [
                {{
                    "type": "sms/phonecall/photo/push/note/calendar",
                    "content_summary": "数据内容描述（用于生成具体数据，只包含缺少的关键信息，保持最小信息量）",
                    "reason": "为什么需要这个数据来反映该事件的哪个重要信息，以及为何现有数据不足"
                }}
            ],
            "to_delete": [
                {{
                    "type": "数据类型",
                    "phone_id": "数据 ID",
                    "reason": "为什么要删除（与该事件不相关/冗余/错误等）"
                }}
            ]
        }}
    ]
}}
"""

        try:
            llm_result = llm_call_j(analysis_prompt)

            # 解析 LLM 结果
            if isinstance(llm_result, str):
                start_idx = llm_result.find('{')
                end_idx = llm_result.rfind('}') + 1
                if start_idx != -1 and end_idx != -1:
                    llm_result = json.loads(llm_result[start_idx:end_idx])

            if isinstance(llm_result, dict):
                overall_analysis = llm_result.get('overall_analysis', '')
                events_analysis = llm_result.get('events_analysis', [])

                print(f"\n[Evidence Refine] LLM 整体分析：{overall_analysis[:200]}...")

                # 收集所有事件的生成和删除操作
                for event_analysis in events_analysis:
                    event_id = event_analysis.get('event_id', '')
                    sufficiency = event_analysis.get('sufficiency_analysis', '')

                    # 验证 event_id 是否有效（必须是 daily_event 中存在的 ID）
                    if not event_id or event_id.startswith('node_'):
                        print(f"[Evidence Refine] 警告：event_id={event_id} 无效，跳过生成")
                        continue

                    # 检查是否在 daily_event 中存在
                    event_exists = False
                    if isinstance(self.daily_event, list):
                        for evt in self.daily_event:
                            if str(evt.get('event_id', '')) == str(event_id):
                                event_exists = True
                                break
                    if not event_exists:
                        print(f"[Evidence Refine] 警告：event_id={event_id} 在 daily_event 中未找到，跳过生成")
                        continue

                    # 收集需要生成的数据
                    for gen_item in event_analysis.get('to_generate', []):
                        gen_item['target_event_id'] = event_id
                        to_generate.append(gen_item)

                    # 收集需要删除的数据
                    to_delete.extend(event_analysis.get('to_delete', []))

                    print(f"\n[Evidence Refine - {event_id}] 分析完成")
                    print(f"  - 充分性分析：{sufficiency[:100]}...")
                    print(f"  - 需要生成：{len(event_analysis.get('to_generate', []))} 条数据")
                    print(f"  - 需要删除：{len(event_analysis.get('to_delete', []))} 条数据")

                print(f"\n[Evidence Refine] 所有事件分析完成")
                print(f"  - 共待生成：{len(to_generate)} 条")
                print(f"  - 共待删除：{len(to_delete)} 条")
            else:
                print("[Evidence Refine] LLM 返回格式错误")
                return question

        except Exception as e:
            print(f"[Evidence Refine] 分析失败：{e}")
            import traceback
            traceback.print_exc()
            return question

        print(f"\n[Evidence Refine] 所有事件分析完成")
        print(f"  - 共待生成：{len(to_generate)} 条")
        print(f"  - 共待删除：{len(to_delete)} 条")

        # 执行数据操作
        print(f"\n[Evidence Refine] 开始执行数据操作...")
        print(f"  - 待生成：{len(to_generate)} 条")
        print(f"  - 待删除：{len(to_delete)} 条")

        # 1. 执行删除操作
        if to_delete:
            print(f"\n[Evidence Refine] === 开始执行删除操作 ===")
            with self.phonedata_lock:
                for del_item in to_delete:
                    op_type = del_item.get('type', 'unknown')
                    phone_id = del_item.get('phone_id', '')
                    reason = del_item.get('reason', '')

                    print(f"\n准备删除：{op_type}:{phone_id}")
                    print(f"  原因：{reason}")

                    if op_type in self.phonedata:
                        original_len = len(self.phonedata[op_type])

                        # 找到要删除的数据并打印详情
                        for op in self.phonedata[op_type]:
                            if str(op.get('phone_id', '')) == str(phone_id):
                                print(f"  删除数据详情:")
                                print(f"    {json.dumps(op, ensure_ascii=False, indent=2)}")
                                break

                        # 执行删除
                        self.phonedata[op_type] = [
                            op for op in self.phonedata[op_type]
                            if str(op.get('phone_id', '')) != str(phone_id)
                        ]

                        if len(self.phonedata[op_type]) < original_len:
                            print(f"  ✓ 已成功删除 {op_type}:{phone_id}\n")

        # 2. 执行生成操作（仅生成必需的数据）
        generated_operations = []
        if to_generate:
            print(f"\n[Evidence Refine] === 开始执行生成操作 ===")
            print(f"[Evidence Refine] 使用 20 线程并行处理 {len(to_generate)} 个生成任务...")

            # 定义允许的 operative types
            ALLOWED_OP_TYPES = {'sms', 'phonecall', 'photo', 'push', 'note', 'calendar'}

            # 准备所有需要生成的任务
            generation_tasks = []
            for gen_item in to_generate:
                op_type = gen_item.get('type', 'sms')

                # 验证类型是否在允许列表中
                if op_type not in ALLOWED_OP_TYPES:
                    print(f"[Evidence Refine] 警告：'{op_type}' 不是允许的操作类型，跳过")
                    continue

                content_summary = gen_item.get('content_summary', '')
                target_event_id = gen_item.get('target_event_id', '')
                reason = gen_item.get('reason', '')

                # 在 phonedata 中查找目标事件的上下文
                target_event = None
                if isinstance(self.daily_event, list):
                    for event in self.daily_event:
                        if event.get('event_id') == target_event_id:
                            target_event = event
                            break

                # 创建临时事件用于生成
                temp_event = {
                    'question': question.get('question', ''),
                    'target_event': target_event or {},
                    'event_id': target_event_id  # 添加 event_id 供 PhoneOperationGenerator 使用
                }

                # 使用 content_summary 作为 generation_hint
                generation_hint = f"""
                请生成{op_type}类型的数据，要求：{content_summary}

                注意：这是为了支持事件 {target_event_id} 的证据数据，请确保数据准确反映该事件。
                可生成的数据类型仅限于：sms, phonecall, photo, push, note, calendar
                """

                generation_tasks.append({
                    'gen_item': gen_item,
                    'op_type': op_type,
                    'temp_event': temp_event,
                    'generation_hint': generation_hint,
                    'target_event_id': target_event_id,
                    'reason': reason,
                    'content_summary': content_summary
                })

            # 并行生成函数
            def generate_single_task(task_data):
                """生成单个任务的手机操作数据"""
                op_type = task_data['op_type']
                temp_event = task_data['temp_event']
                generation_hint = task_data['generation_hint']
                target_event_id = task_data['target_event_id']
                reason = task_data['reason']
                content_summary = task_data['content_summary']

                try:
                    print(f"\n准备生成：{op_type}")
                    print(f"  目标事件 ID: {target_event_id}")
                    print(f"  生成原因：{reason}")
                    print(f"  内容要求：{content_summary[:100]}...")

                    # 使用 PhoneOperationGenerator 生成
                    operations = self.phone_op_generator.generate(
                        operation_type=op_type,
                        original_event=temp_event,
                        question=question.get('question', ''),
                        generation_hint=generation_hint
                    )

                    if operations:
                        print(f"  ✓ 已生成 {len(operations)} 条 {op_type} 数据")
                        return operations
                    else:
                        print(f"  ⚠ 未生成任何 {op_type} 数据")
                        return []
                except Exception as e:
                    print(f"  ✗ 生成失败：{e}")
                    return []

            # 使用 ThreadPoolExecutor 并行处理，最多 20 个线程
            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                # 提交所有任务
                futures = [executor.submit(generate_single_task, task) for task in generation_tasks]

                # 收集结果
                for future in concurrent.futures.as_completed(futures):
                    try:
                        operations = future.result()
                        generated_operations.extend(operations)
                    except Exception as e:
                        print(f"[Evidence Refine] 生成任务异常：{e}")

            # 打印生成的每条数据详情
            if generated_operations:
                print(f"\n[Evidence Refine] 生成完成，共 {len(generated_operations)} 条数据")
                for i, op in enumerate(generated_operations[:5], 1):  # 只显示前 5 条
                    op_type = op.get('type', '')
                    print(f"\n  生成的第 {i} 条数据 ({op_type}):")
                    print(f"    type: {op.get('type', '')}")
                    print(f"    daily_event_id: {op.get('daily_event_id', '')}")
                    print(f"    datetime: {op.get('datetime', '')}")
                    # 根据类型打印特定字段
                    if op_type == 'sms':
                        print(f"    contactName: {op.get('contactName', '')}")
                        print(f"    phoneNumber: {op.get('phoneNumber', '')}")
                        print(f"    message_content: {op.get('message_content', '')[:100]}...")
                    elif op_type == 'phonecall':
                        print(f"    contactName: {op.get('contactName', '')}")
                        print(f"    phoneNumber: {op.get('phoneNumber', '')}")
                        print(f"    call_result: {op.get('call_result', '')}")
                    elif op_type == 'photo':
                        print(f"    title: {op.get('title', '')}")
                        print(f"    caption: {op.get('caption', '')[:100]}...")
                        loc = op.get('location', {})
                        if isinstance(loc, dict):
                            print(f"    location: {loc.get('poi', '')} - {loc.get('city', '')}")
                    elif op_type == 'push':
                        print(f"    title: {op.get('title', '')}")
                        print(f"    content: {op.get('content', '')[:100]}...")
                        print(f"    source: {op.get('source', '')}")
                    elif op_type == 'note':
                        print(f"    title: {op.get('title', '')}")
                        print(f"    content: {op.get('content', '')[:100]}...")
                    elif op_type == 'calendar':
                        print(f"    title: {op.get('title', '')}")
                        print(f"    description: {op.get('description', '')[:100]}...")
                        print(f"    start_time: {op.get('start_time', '')}")
                        print(f"    end_time: {op.get('end_time', '')}")

                if len(generated_operations) > 5:
                    print(f"\n  ... 还有 {len(generated_operations) - 5} 条数据未显示")

            # 添加到 phonedata
            if generated_operations:
                print(f"\n[Evidence Refine] 将生成的 {len(generated_operations)} 条数据添加到 phonedata")
                self._add_operations_to_phonedata(generated_operations)

        # 更新问题的 evidence 字段
        # 重新收集所有事件的最新证据（因为 phonedata 已经被更新）
        updated_evidence = []

        print(f"\n[Evidence Refine] 重新收集所有事件的证据...")

        # 遍历所有必需的事件 ID，收集最新的证据
        for event_id in required_events_ids:
            # 在 daily_event 中查找对应事件
            target_event = None
            if isinstance(self.daily_event, list):
                for event in self.daily_event:
                    if str(event.get('event_id', '')) == str(event_id):
                        target_event = event
                        break

            if not target_event:
                print(f"[Evidence Refine] 警告：event_id={event_id} 在 daily_event 中未找到匹配，跳过证据收集")
                continue

            # 从手机数据中查找与该事件对应的数据（基于 event_id 匹配）
            found_count = 0
            if self.phonedata:
                for data_type, data_list in self.phonedata.items():
                    if isinstance(data_list, list):
                        for item in data_list:
                            if isinstance(item, dict):
                                # 检查 daily_event_id 或 related_event 字段
                                item_event_id = str(item.get('daily_event_id', ''))
                                related_event = str(item.get('related_event', ''))

                                # 如果匹配，添加到 updated_evidence
                                if item_event_id == str(event_id) or related_event == str(event_id):
                                    updated_evidence.append(item)
                                    found_count += 1

            print(f"[Evidence Refine - {event_id}] 收集到 {found_count} 条证据")

        # 更新问题的 evidence 字段
        question['evidence'] = updated_evidence

        print(f"\n[Evidence Refine] 证据优化完成")
        print(f"  - 最终证据：{len(updated_evidence)} 条")

        return question

    def generate_monthly_qa(self, year: int, month: int, num_questions: int = 5) -> List[Dict[str, Any]]:
        """
        生成单个月份的多跳问答
        
        Args:
            year: 年份
            month: 月份
            num_questions: 生成问题数量
            
        Returns:
            问答列表
        """
        print(f"\n========== 生成 {year}-{month:02d} 的多跳问答 ==========")
        
        monthly_qa = []
        
        for i in range(num_questions):
            print(f"\n--- 生成第 {i+1}/{num_questions} 个问题 ---")
            
            # Step 1: Select Agent 选择目标事件
            select_results = self.select_agent(year, month)
            if not select_results:
                continue
            
            select_result = select_results[0]
            dates = select_result['dates']
            target_event = select_result.get('target_event', {})
            daily_events = select_result.get('daily_events_in_range', [])
            
            # Step 2: Search Agent 搜索事件树
            search_result = self.search_agent(dates, target_event)
            
            # Step 3: Inference Agent 构建推理链条
            inference_chain = self.inference_agent(target_event, search_result, daily_events)

            print(f"\n[inference_agent] 推理链条：{inference_chain}")

            # Step 4: 生成问题和手机数据
            qa_result = self.generate_question_and_data(inference_chain)
            
            if qa_result.get('question'):
                # 添加 ask_time
                random_month = random.randint(month, 12)
                qa_result['ask_time'] = self.default_ask_time
                qa_result['question_type'] = 'Multi_hop'
                
                monthly_qa.append(qa_result)
        
        print(f"========== {year}-{month:02d} 完成，生成 {len(monthly_qa)} 个问题 ==========")
        return monthly_qa
    
    def _filter_multi_hop_questions(self, questions: List[Dict[str, Any]], max_workers: int = 20) -> List[Dict[str, Any]]:
        """
        并行过滤检查多跳推理问题质量（20线程）
        
        Args:
            questions: 待检查的问题列表
            max_workers: 最大线程数，默认20
            
        Returns:
            过滤后的问题列表（保留通过检查或被重新生成的问题）
        """
        print(f"\n[_filter_multi_hop_questions] 开始对 {len(questions)} 个多跳问题进行过滤检查（{max_workers}线程并行）...")
        
        filtered_results = [None] * len(questions)  # 预分配列表保持顺序
        
        def filter_single_question(idx: int, question: Dict[str, Any]) -> tuple:
            """处理单个问题的过滤检查"""
            try:
                print(f"\n[_filter_multi_hop_questions] 检查第 {idx + 1}/{len(questions)} 个问题...")
                
                # 调用 LLM 进行质量检查
                check_prompt = f"""
作为多跳推理问题质量检查专家，请检查以下多跳推理问题的质量。

【问题】
{question.get('question', '')}

【答案】
{question.get('answer', '')}

【证据数据】
{json.dumps(question.get('evidence', []), ensure_ascii=False, indent=2) if question.get('evidence') else '无'}

**检查标准**

1. **多跳推理难度要求**
   - 问题必须是真正的多跳推理问题，需要基于多个 evidence 进行推理才能得到答案
   - 不能是单步推理或直接查找就能回答的简单问题
   - 推理链条应该具有适当的复杂度，需要跨事件、跨时间或跨实体进行关联

2. **题面信息量控制**
   - **减少题面与目标信息的相似度**：题面不应直接暴露答案或目标 evidence 的关键特征
   - 主要基于推理来定位目标 evidence，而不是通过题面的直接描述
   - 题面应该提供线索和上下文，让回答者需要通过推理才能找到答案
   - 参考原题目设计的推理思路来润色新题目，保证推理需要2-4跳。
   - 题目应至少包含月份信息。

3. **问题和答案的合理性**
   - 问题是否清晰、无歧义？
   - 答案是否正确回答了问题？
   - 答案的内容是否合理、符合逻辑？

4. **可从 evidence 推理的可回答性**
   - 提供的 evidence 是否包含回答问题所需的足够信息？
   - 从 evidence 出发，是否能通过多步推导出答案？
   - 是否存在 evidence 不足导致无法回答的情况？

5. **答案与证据的一致性检查**（重要）
   - 答案中是否包含了证据（evidence）中没有的、无法体现的细节或信息？
   - 如果答案描述了具体日期、数字、人名、事件细节等，检查这些内容是否能在 evidence 中找到依据
   - 答案不应包含 evidence 中不存在的信息，尤其是具体数值、具体人名、具体地点等关键细节
   - 若发现此类问题，可通过微调答案（去除evidence中不存在的细节）来修正

6. **题面与证据的一致性检查**（重要）
   - 题面的描述是否与 evidence 中的信息一致？
   - 题面中提到的日期、时间、地点、人物等关键信息，是否能在 evidence 中找到对应？
   - 题面是否包含了无法从 evidence 推理出来的内容或描述？
   - 若发现不一致，可通过微调题面来修正

**输出要求**

请以 JSON 格式返回检查结果：
{{
    "is_valid": true/false,
    "issues": ["问题列表，如果没有问题则为空数组"],
    "action": "keep/regenerate/discard",
    "reason": "做出该决定的原因",
    "suggested_question": "如果需要重新生成或微调，建议的新问题（可选）",
    "suggested_answer": "如果需要重新生成或微调，建议的新答案（可选）"
}}

**决策规则**：
- keep: 问题是高质量的多跳推理问题，题面简洁且信息量适中，可以从多个 evidence 推理得出答案，且答案和题面均与 evidence 一致
- regenerate: 问题整体合理，但出现答案包含 evidence 无法体现的细节，或题面描述与 evidence 不一致，可通过微调答案和题面来修正。或者题面包含了过多提示和冗余信息，导致题面的推理难度/跳数减少或过于简单。可修改题面表述。
- discard: 问题难以改造成合理的高质量多跳复杂推理问题，或者 evidence 完全不足以支持多跳推理，或存在根本性不一致无法通过微调修正

**示例判断**：
- ✅ keep: "我参加完马拉松比赛后，和小李庆祝时提到的项目合作方案后来实施了吗？"（需要推理：马拉松→庆生→项目讨论→实施情况）
- ❌ regenerate: "我在5月15日参加完马拉松比赛后，5月20日在和平饭店和小李讨论的项目合作方案后来实施了吗？"（题面过长，直接给出了太多细节）
- ❌ discard: "我那天做了什么？"（单步推理，不是多跳问题）
- ❌ regenerate: 答案提到"7月15日在中心医院"，但 evidence 只显示"7月15日"，地点无法体现 → 微调答案为"7月15日"，去除医院信息
"""
                
                check_result = llm_call_reason_j(check_prompt)
                
                try:
                    start_idx = check_result.find('{')
                    end_idx = check_result.rfind('}') + 1
                    if start_idx != -1 and end_idx != -1:
                        check_json = json.loads(check_result[start_idx:end_idx])
                        is_valid = check_json.get('is_valid', True)
                        action = check_json.get('action', 'keep')
                        issues = check_json.get('issues', [])
                        reason = check_json.get('reason', '')
                        
                        if action == 'discard':
                            print(f"[_filter_multi_hop_questions] 第 {idx + 1} 个问题被抛弃：{reason}")
                            return idx, None
                        elif action == 'regenerate':
                            suggested_question = check_json.get('suggested_question', '')
                            suggested_answer = check_json.get('suggested_answer', '')
                            if suggested_question and suggested_answer:
                                print(f"[_filter_multi_hop_questions] 第 {idx + 1} 个问题需要重新生成：{reason}")
                                question['question'] = suggested_question
                                question['answer'] = suggested_answer
                                return idx, question
                            else:
                                print(f"[_filter_multi_hop_questions] 第 {idx + 1} 个问题需要重新生成但未提供建议，抛弃：{reason}")
                                return idx, None
                        else:  # keep
                            print(f"[_filter_multi_hop_questions] 第 {idx + 1} 个问题通过检查")
                            return idx, question
                    else:
                        print(f"[_filter_multi_hop_questions] 第 {idx + 1} 个问题检查结果解析失败，保留原问题")
                        return idx, question
                except Exception as e:
                    print(f"[_filter_multi_hop_questions] 第 {idx + 1} 个问题检查异常：{e}，保留原问题")
                    return idx, question
                    
            except Exception as e:
                print(f"[_filter_multi_hop_questions] 第 {idx + 1} 个问题检查失败：{e}")
                return idx, question
        
        # 使用 ThreadPoolExecutor 并行处理
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(filter_single_question, idx, question)
                for idx, question in enumerate(questions)
            ]
            
            # 收集结果
            completed_count = 0
            for future in concurrent.futures.as_completed(futures):
                try:
                    idx, result = future.result()
                    filtered_results[idx] = result
                    completed_count += 1
                    if completed_count % 5 == 0 or completed_count == len(questions):
                        print(f"\n[_filter_multi_hop_questions] 已完成 {completed_count}/{len(questions)} 个问题的过滤检查")
                except Exception as e:
                    print(f"[_filter_multi_hop_questions] 结果收集失败：{e}")
        
        # 过滤掉 None 值（被抛弃的问题）
        filtered_questions = [q for q in filtered_results if q is not None]
        
        discarded_count = len(questions) - len(filtered_questions)
        print(f"\n[_filter_multi_hop_questions] 过滤完成：保留 {len(filtered_questions)} 个问题，抛弃 {discarded_count} 个问题")

        return filtered_questions

    def _check_similar_events_confusion(self, qa_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        检查问题中的事件描述是否可能导致与相似事件混淆，并重写问题

        Args:
            qa_result: QA 结果

        Returns:
            可能已重写问题的 QA 结果
        """
        required_events_ids = qa_result.get('required_events_id', [])
        if not required_events_ids:
            return qa_result

        # 收集所有事件及其日期信息，按月份分组
        event_info_map = {}  # event_id -> event info
        events_by_month = {}  # month -> list of events

        for event_id in required_events_ids:
            # 在 daily_event 中查找事件
            target_event = None
            for event in self.daily_event:
                if str(event.get('event_id', '')) == str(event_id):
                    target_event = event
                    break

            if not target_event:
                continue

            # 获取目标事件的日期
            target_date = target_event.get('date', [])
            if isinstance(target_date, list) and target_date:
                target_date_str = target_date[0][:10] if target_date[0] else ''
            else:
                target_date_str = str(target_date)[:10] if target_date else ''

            target_year = target_date_str[:4] if target_date_str else '2025'
            target_month = int(target_date_str[5:7]) if len(target_date_str) >= 7 else 1

            event_info_map[event_id] = {
                'event_id': event_id,
                'event': target_event,
                'year': target_year,
                'month': target_month,
                'name': target_event.get('name', ''),
                'description': target_event.get('description', '')[:200]
            }

            # 按月份分组
            if target_month not in events_by_month:
                events_by_month[target_month] = []
            events_by_month[target_month].append({
                'event_id': event_id,
                'name': target_event.get('name', ''),
                'description': target_event.get('description', '')
            })

        if not event_info_map:
            return qa_result

        # 批量查找每个月的相似事件
        event_similar_events = []
        for month, events_in_month in events_by_month.items():
            # 使用批量查询（每月只调用一次 LLM）
            event_ids_in_month = [e['event_id'] for e in events_in_month]
            similar_map = self._find_similar_events_batch(events_in_month, '2025', month)

            for event_id in event_ids_in_month:
                similar_list = similar_map.get(event_id, [])
                if similar_list:
                    info = event_info_map[event_id]
                    event_similar_events.append({
                        'event_id': event_id,
                        'event_name': info['name'],
                        'event_description': info['description'],
                        'similar_events': similar_list
                    })

        if not event_similar_events:
            return qa_result

        print(f"[_check_similar_events_confusion] 检查 {len(event_similar_events)} 个事件的相似事件...")

        # ========== 收集事件相关的 daily_event 数据 ==========
        date_daily_events = {}
        all_dates = set()

        # 收集目标事件的日期
        for item in event_similar_events:
            for date_str in item.get('event_date', '').split(','):
                date_str = date_str.strip()[:10]
                if date_str:
                    all_dates.add(date_str)

        # 收集相似事件的日期
        for item in event_similar_events:
            for sim_event in item.get('similar_events', []):
                sim_date = str(sim_event.get('date', ''))[:10]
                if sim_date:
                    all_dates.add(sim_date)

        # 获取每个日期的 daily_event
        for date_str in all_dates:
            date_daily_events[date_str] = self._get_unique_daily_events_for_date(date_str)

        # ========== 第一轮 LLM：分析哪些事件可能会混淆 ==========
        analysis_prompt = f"""
作为问题质量审核专家，请分析以下多跳推理问题中的事件描述是否可能导致混淆。

【当前问题】
{qa_result.get('question', '')}

【当前答案】
{qa_result.get('answer', '')}

【涉及的事件及其相似事件】
{json.dumps(event_similar_events, ensure_ascii=False, indent=2)}

【事件相关的 daily_event 数据】
{json.dumps(date_daily_events, ensure_ascii=False, indent=2)}

**分析任务**
逐一检查每个目标事件与其相似事件，分析哪些会产生混淆：

1. 对于每个目标事件，检查其相似事件列表
2. 判断题面描述是否足够区分目标事件与相似事件
3. 如果存在混淆风险，输出该事件及其日期，以及会导致混淆的相似事件详情

**输出格式**
请以 JSON 格式返回：
{{
    "confusion_analysis": [
        {{
            "event_id": "目标事件ID",
            "event_name": "目标事件名称",
            "event_date": "YYYY-MM-DD",
            "confusing_similar_events": [
                {{
                    "date": "YYYY-MM-DD",
                    "description": "相似事件描述",
                    "similarity_reason": "相似原因"
                }}
            ]
        }}
    ],
    "has_confusion": true/false
}}
"""
        confusion_result = {}
        try:
            result = llm_call(analysis_prompt)
            if isinstance(result, str):
                start_idx = result.find('{')
                end_idx = result.rfind('}') + 1
                if start_idx != -1 and end_idx != -1:
                    result = json.loads(result[start_idx:end_idx])

            if isinstance(result, dict):
                confusion_result = result
                print(f"[_check_similar_events_confusion] 混淆分析结果: has_confusion={result.get('has_confusion', False)}")

        except Exception as e:
            print(f"[_check_similar_events_confusion] 第一轮分析失败: {e}")
            return qa_result

        if not confusion_result.get('has_confusion', False):
            return qa_result

        confusion_analysis = confusion_result.get('confusion_analysis', [])
        if not confusion_analysis:
            return qa_result

        # ========== 第二轮 LLM：基于分析结果和 daily_event 重写问题 ==========
        rewrite_prompt = f"""
基于以下混淆分析结果，判断是否需要重写问题。

【当前问题】
{qa_result.get('question', '')}

【当前答案】
{qa_result.get('answer', '')}

【混淆分析结果】
{json.dumps(confusion_analysis, ensure_ascii=False, indent=2)}

【各日期的 daily_event 数据】
{json.dumps(date_daily_events, ensure_ascii=False, indent=2)}

**第一步：判断是否需要重写**
逐一检查每个目标事件的相似事件：
1. 假设用户阅读问题描述后，能否明确区分目标事件和相似事件？
2. 即：使用当前问题描述，回答相似事件的内容也算正确吗？
   - 如果是 → 需要重写
   - 如果否 → 不需要重写，保持原样

**第二步：重写要求**（仅在需要重写时执行）
1. 选取一个目标日期中独特的事件作为区分锚点
2. 将该区分事件的描述加入问题题面
3. 必须从 daily_event 数据中返回对应的 event_id

**示例**
原问题："今年3月我和朋友聚会聊天，有的朋友给我鼓励打气，想问问具体说了什么？"
重写后："今年3月我和朋友聚会聊天（那天还给父亲买了按摩仪），有的朋友给我鼓励打气，想问问具体说了什么？"
新增事件ID：["123"]
（123指代给父亲买按摩仪的事件）

**输出格式**
{{
    "needs_rewrite": true/false,
    "rewritten_question": "添加区分性描述后的问题（仅当 needs_rewrite=true 时）",
    "additional_required_events": ["返回新增事件的 event_id（仅当 needs_rewrite=true 时）"]
}}
"""
        try:
            result = llm_call(rewrite_prompt)
            if isinstance(result, str):
                start_idx = result.find('{')
                end_idx = result.rfind('}') + 1
                if start_idx != -1 and end_idx != -1:
                    result = json.loads(result[start_idx:end_idx])

            if isinstance(result, dict):
                needs_rewrite = result.get('needs_rewrite', False)
                new_q = result.get('rewritten_question', '')
                additional_events = result.get('additional_required_events', [])

                print(f"\n[_check_similar_events_confusion] 第二轮 LLM 返回:")
                print(f"  needs_rewrite: {needs_rewrite}")
                print(f"  rewritten_question: {new_q[:100] if new_q else 'N/A'}...")
                print(f"  additional_required_events: {additional_events}")
                print(f"  原始 required_events_id: {qa_result.get('required_events_id', [])}")

                if needs_rewrite and new_q:
                    print(f"\n[_check_similar_events_confusion] 问题描述已重写:")
                    print(f"  原问题: {qa_result.get('question', '')[:80]}...")
                    print(f"  新问题: {new_q[:80]}...")

                    qa_result['question'] = new_q

                    if additional_events:
                        current_required = qa_result.get('required_events_id', [])
                        for evt_id in additional_events:
                            if evt_id not in current_required:
                                current_required.append(evt_id)
                        qa_result['required_events_id'] = current_required
                        print(f"  更新后 required_events_id: {current_required}")
                    else:
                        print(f"  未新增事件ID，保留原 required_events_id: {qa_result.get('required_events_id', [])}")

                    qa_result['rewritten_for_similarity'] = True
                elif not needs_rewrite:
                    print(f"[_check_similar_events_confusion] 不需要重写，保持原问题")

        except Exception as e:
            print(f"[_check_similar_events_confusion] 第二轮重写失败: {e}")

        return qa_result


    def _find_similar_events_batch(self, events: List[Dict], year: str, target_month: int) -> Dict[str, List[Dict]]:
        """
        批量查找多个事件的相似事件（每月只调用一次 LLM）

        Args:
            events: 目标事件列表，每个元素包含 event_id, name, description
            year: 年份
            target_month: 目标月份

        Returns:
            Dict[str, List[Dict]]: key 为 event_id，value 为该事件的相似事件列表
        """
        if not events:
            return {}

        # 收集该月及之前月份的所有 draft events
        draft_events_to_check = []
        for month in range(1, target_month + 1):
            month_key = f"{year}-{month:02d}"
            if month_key not in self.draft_event:
                continue

            month_data = self.draft_event[month_key]
            if not isinstance(month_data, list):
                continue

            for day_data in month_data:
                date_str = day_data.get('date', '')
                events_list = day_data.get('events', [])
                if not isinstance(events_list, list):
                    continue

                for evt in events_list:
                    evt_id = evt.get('event_id', [])
                    if isinstance(evt_id, list) and evt_id:
                        evt_id_str = evt_id[0]
                    else:
                        evt_id_str = str(evt_id) if evt_id else ''

                    draft_events_to_check.append({
                        'event_id': evt_id_str,
                        'date': date_str,
                        'name': evt.get('name', ''),
                        'description': evt.get('description', '')
                    })

        if not draft_events_to_check:
            return {}

        # 构建批量查询 prompt
        prompt = f"""
作为相似度分析专家，请为以下 {len(events)} 个目标事件各找出与它们极度相似的历史事件。

**极度相似的定义**：主要内容相似，但发生时间和一些细节不一样。
如果直接提问"今年XXX"，可能导致指代不明确、混淆。

【目标事件列表】
{json.dumps(events, ensure_ascii=False, indent=2)}

【候选事件列表】（共 {len(draft_events_to_check)} 个）
{json.dumps(draft_events_to_check, ensure_ascii=False, indent=2)}

**输出要求**
请以 JSON 格式返回每个目标事件的相似事件：
{{
    "results": [
        {{
            "target_event_id": "目标事件ID",
            "similar_events": [
                {{
                    "date": "YYYY-MM-DD",
                    "description": "事件描述",
                    "similarity_reason": "相似原因说明"
                }}
            ]
        }}
    ]
}}

注意：
1. 为每个目标事件分别找出与它极度相似的历史事件
2. 如果某个目标事件没有相似事件，similar_events 返回空数组
3. 每个目标事件最多返回 5 个最相似的事件
4. 重点关注事件类型、人物关系、活动内容相似的条目
5. 输出时 description 字段请使用完整描述，不要截断
"""
        try:
            result = llm_call_j(prompt)
            if isinstance(result, str):
                start_idx = result.find('{')
                end_idx = result.rfind('}') + 1
                if start_idx != -1 and end_idx != -1:
                    result = json.loads(result[start_idx:end_idx])

            if isinstance(result, dict):
                results = result.get('results', [])
                print(f"[_find_similar_events_batch] LLM 返回 {len(results)} 个结果")

                # 转换为 Dict[str, List[Dict]]
                event_similar_map = {}
                for item in results:
                    target_id = item.get('target_event_id', '')
                    similar_list = item.get('similar_events', [])[:5]
                    if target_id:
                        event_similar_map[target_id] = similar_list

                return event_similar_map

        except Exception as e:
            print(f"[_find_similar_events_batch] 分析失败: {e}")

        return {}

    def _get_unique_daily_events_for_date(self, date_str: str) -> List[Dict]:
        """
        获取指定日期的所有 daily_event，选取较为独特的事件作为区分参考

        Args:
            date_str: 日期字符串 (YYYY-MM-DD)

        Returns:
            该日期的 daily_event 列表
        """
        if not date_str or not self.daily_event:
            return []

        unique_events = []
        for event in self.daily_event:
            event_dates = event.get('date', [])
            if not event_dates:
                continue

            # 检查事件是否在目标日期
            event_date_str = ''
            for d in event_dates:
                if isinstance(d, str) and d.startswith(date_str):
                    event_date_str = date_str
                    break

            if event_date_str == date_str:
                unique_events.append({
                    'event_id': event.get('event_id', ''),
                    'name': event.get('name', ''),
                    'description': event.get('description', ''),
                    'date': event.get('date', []),
                    'type': event.get('type', ''),
                    'location': event.get('location', ''),
                    'participant': event.get('participant', [])
                })

        return unique_events

    def _find_similar_confusing_events(self, target_event: Dict, year: str, target_month: int) -> List[Dict]:
        """
        使用 LLM 查找与目标事件极度相似的历史事件

        Args:
            target_event: 目标事件
            year: 年份
            target_month: 目标月份

        Returns:
            相似事件列表
        """
        target_event_id = target_event.get('event_id', '')
        target_desc = target_event.get('description', '')
        target_name = target_event.get('name', target_event.get('event_name', ''))

        # 收集该月及之前月份的所有 draft events
        draft_events_to_check = []
        for month in range(1, target_month + 1):
            month_key = f"{year}-{month:02d}"
            if month_key not in self.draft_event:
                continue

            month_data = self.draft_event[month_key]
            if not isinstance(month_data, list):
                continue

            for day_data in month_data:
                date_str = day_data.get('date', '')
                events_list = day_data.get('events', [])
                if not isinstance(events_list, list):
                    continue

                for evt in events_list:
                    evt_id = evt.get('event_id', [])
                    if isinstance(evt_id, list) and evt_id:
                        evt_id_str = evt_id[0]
                    else:
                        evt_id_str = str(evt_id) if evt_id else ''

                    # 排除目标事件本身
                    if evt_id_str == target_event_id:
                        continue

                    draft_events_to_check.append({
                        'date': date_str,
                        'name': evt.get('name', ''),
                        'description': evt.get('description', '')
                    })

        if not draft_events_to_check:
            return []

        # 调用 LLM 查找相似事件
        prompt = f"""
作为相似度分析专家，请从以下候选事件中找出与目标事件极度相似的历史事件。

**极度相似的定义**：主要内容相似，但发生时间和一些细节不一样。
如果直接提问"今年XXX"，可能导致指代不明确、混淆。

【目标事件】
事件名称：{target_name}
事件描述：{target_desc[:500]}

【候选事件列表】（共 {len(draft_events_to_check)} 个）
{json.dumps(draft_events_to_check, ensure_ascii=False, indent=2)}

**输出要求**
请以 JSON 格式返回极度相似的事件列表：
{{
    "similar_events": [
        {{
            "date": "YYYY-MM-DD",
            "description": "事件描述（全量内容）",
            "similarity_reason": "相似原因说明"
        }}
    ]
}}

注意：
1. 只返回与目标事件极度相似的历史事件
2. 如果没有找到相似事件，返回空的 similar_events 数组
3. 最多返回 5 个最相似的事件
4. 重点关注事件类型、人物关系、活动内容相似的条目
5. 输出时 description 字段请使用完整描述，不要截断
"""
        try:
            result = llm_call_j(prompt)
            if isinstance(result, str):
                start_idx = result.find('{')
                end_idx = result.rfind('}') + 1
                if start_idx != -1 and end_idx != -1:
                    result = json.loads(result[start_idx:end_idx])

            if isinstance(result, dict):
                similar_events = result.get('similar_events', [])
                print(f"[_find_similar_confusing_events] LLM 返回 {len(similar_events)} 个相似事件")
                return similar_events[:5]

        except Exception as e:
            print(f"[_find_similar_confusing_events] 分析失败: {e}")

        return []

    def _get_background_events_for_target(self, target_time: str) -> List[Dict]:
        """
        获取目标事件前后各一天的 daily_event 作为背景素材
        
        Args:
            target_time: 目标事件的时间字符串（如 "2025-03-04"）
        
        Returns:
            前后各一天的 daily_event 列表
        """
        if not target_time or not self.daily_event:
            return []
        
        try:
            from datetime import datetime, timedelta
            
            # 解析目标时间
            target_date = datetime.strptime(target_time.split(' ')[0], '%Y-%m-%d')
            
            # 计算前后日期
            prev_date = target_date - timedelta(days=1)
            next_date = target_date + timedelta(days=1)
            
            prev_date_str = prev_date.strftime('%Y-%m-%d')
            next_date_str = next_date.strftime('%Y-%m-%d')
            target_date_str = target_date.strftime('%Y-%m-%d')
            
            print(f"[Background Events] 目标日期: {target_date_str}, 前一日: {prev_date_str}, 后一日: {next_date_str}")
            
            # 收集这三天的事件
            background_events = []
            for event in self.daily_event:
                event_dates = event.get('date', [])
                if not event_dates:
                    continue
                
                for date_range in event_dates:
                    if isinstance(date_range, str):
                        # 处理单个日期或日期范围
                        if '至' in date_range:
                            start_end = date_range.split('至')
                            start_date = start_end[0].strip().split(' ')[0]
                            end_date = start_end[1].strip().split(' ')[0]
                            # 检查事件是否在这三天范围内
                            if start_date <= next_date_str and end_date >= prev_date_str:
                                background_events.append(event)
                                break
                        else:
                            event_date = date_range.split(' ')[0]
                            if event_date in [prev_date_str, target_date_str, next_date_str]:
                                background_events.append(event)
                                break
            
            print(f"[Background Events] 找到 {len(background_events)} 个背景事件")
            return background_events
            
        except Exception as e:
            print(f"[Background Events] 获取背景事件失败: {e}")
            return []
    
    def QAGen(self, year: int = 2025, num_questions_per_month: int = 5) -> List[Dict[str, Any]]:
        """
        生成多跳 QA 对的主入口函数
        
        Args:
            year: 年份，默认 2025
            num_questions_per_month: 每月生成问题数量
            
        Returns:
            生成的 QA 对列表
        """
        print(f"\n开始生成 {year} 年的多跳问答对...")
        
        all_qa = []
        
        # 12线程并行为每个月生成问答
        print(f"\n开始12线程并行生成12个月的多跳问答对...")
        
        import concurrent.futures
        
        def generate_monthly_task(month: int) -> tuple:
            """生成单月问答的任务函数"""
            try:
                print(f"\n[QAGen] 开始生成 {year}-{month:02d} 的多跳问答...")
                monthly_qa = self.generate_monthly_qa(year, month, num_questions_per_month)
                print(f"[QAGen] {year}-{month:02d} 生成了 {len(monthly_qa)} 个问题")
                return month, monthly_qa
            except Exception as e:
                print(f"[QAGen] {year}-{month:02d} 生成失败：{e}")
                import traceback
                traceback.print_exc()
                return month, []
        
        # 使用 ThreadPoolExecutor 并行处理12个月
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
            # 提交所有月份任务
            futures = {
                executor.submit(generate_monthly_task, month): month
                for month in range(1, 13)
            }
            
            # 收集结果（按月份顺序）
            monthly_results = {}
            completed_count = 0
            for future in concurrent.futures.as_completed(futures):
                try:
                    month, monthly_qa = future.result()
                    monthly_results[month] = monthly_qa
                    completed_count += 1
                    if completed_count % 3 == 0 or completed_count == 12:
                        total_generated = sum(len(qa) for qa in monthly_results.values())
                        print(f"\n[QAGen] 已完成 {completed_count}/12 个月，累计生成 {total_generated} 个问题")
                except Exception as e:
                    print(f"[QAGen] 结果收集失败：{e}")
        
        # 按月份顺序合并结果
        for month in range(1, 13):
            if month in monthly_results:
                all_qa.extend(monthly_results[month])
        
        # 对所有生成的问题进行并行过滤检查
        if all_qa:
            print(f"\n开始对 {len(all_qa)} 个多跳问题进行质量过滤检查...")
            all_qa = self._filter_multi_hop_questions(all_qa, max_workers=20)
            print(f"过滤后剩余 {len(all_qa)} 个问题")
        
        # # 保存到文件（已移至 all_qa_generator 统一处理）
        # if self.phone_data_dir:
        #     parent_dir = os.path.dirname(self.phone_data_dir)
        #     output_path = os.path.join(parent_dir, "multi_hop_qa.json")
        #
        #     with open(output_path, "w", encoding="utf-8") as f:
        #         json.dump(all_qa, f, ensure_ascii=False, indent=2)
        #
        #     print(f"\n问答对已成功写入文件：{output_path}")
        print(f"共生成 {len(all_qa)} 个问答对\n")
        
        return all_qa