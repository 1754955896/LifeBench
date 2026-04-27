# -*- coding: utf-8 -*-
"""
知识更新问题生成器：基于月度大纲中的状态变化生成问答对
"""
import os
import json
import random
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
from .base_generator import BaseQAGenerator
from .phone_operation_generator import PhoneOperationGenerator
from src.lifebench.utils.llm_call import llm_call_j

class QAKnowledgeUpdatingGenerator(BaseQAGenerator):
    def __init__(self, daily_event: List[Dict], event_tree: List[Dict],
                 draft_event: Dict[str, List], phonedata: Dict[str, List],
                 phone_data_dir: str = None, is_print: bool = True):
        """
        初始化知识更新 QA 生成器
            
        Args:
            daily_event: daily_event 数据列表
            event_tree: event_tree 数据列表
            draft_event: draft_event 数据字典（按月份组织）
            phonedata: 手机操作数据字典
            phone_data_dir: 手机数据目录路径
            is_print: 是否打印调试信息
        """
        # 调用父类的 __init__
        super().__init__()
        self.daily_event = daily_event
        self.event_tree = event_tree
        self.draft_event = draft_event
        self.phonedata = phonedata
        self.phone_data_dir = phone_data_dir
        self.is_print = is_print
        
        # 初始化线程锁
        self.phonedata_lock = threading.Lock()
        self.phone_id_lock = threading.Lock()
        
        # 初始化手机操作生成器
        self.phone_op_generator = PhoneOperationGenerator()
        
        self.outlines = []
        self.state_changes = []  # 记录所有检测到的状态变化
        self.global_state_record = {}  # 全局状态记录：{state_name: {"initial_state": ..., "current_state": ..., "change_nodes": [...]}}
        
        # 尝试从文件加载全局状态记录
        if phone_data_dir:
            process_dir = os.path.join(os.path.dirname(phone_data_dir), "process")
            state_file = os.path.join(process_dir, "global_state_record.json")
            if os.path.exists(state_file):
                try:
                    with open(state_file, 'r', encoding='utf-8') as f:
                        self.global_state_record = json.load(f)
                    if self.is_print:
                        print(f"✓ 从文件加载全局状态记录: {state_file}")
                        print(f"  - 状态数: {len(self.global_state_record)}")
                except Exception as e:
                    if self.is_print:
                        print(f"⚠️ 加载全局状态记录失败: {e}，将重新生成")
                    self._build_global_state_record()
            else:
                if self.is_print:
                    print(f"⚠️ 未找到全局状态记录文件，开始生成...")
                self._build_global_state_record()
        else:
            if self.is_print:
                print(f"⚠️ 未提供 phone_data_dir，开始生成全局状态记录...")
            self._build_global_state_record()
        
        # 初始化时执行证据定位（带文件缓存）
        located_file = None
        if self.phone_data_dir:
            process_dir = os.path.join(os.path.dirname(self.phone_data_dir), "process")
            located_file = os.path.join(process_dir, "global_state_record_located.json")
        
        if located_file and os.path.exists(located_file):
            try:
                with open(located_file, 'r', encoding='utf-8') as f:
                    self.global_state_record_located = json.load(f)
                if self.is_print:
                    print(f"✓ 从文件加载已定位的状态记录: {located_file}")
            except Exception as e:
                if self.is_print:
                    print(f"⚠️ 加载已定位状态记录失败: {e}，将重新生成")
                self._locate_evidence_for_all_states()
        else:
            if self.is_print:
                print(f"⚠️ 未找到已定位状态记录文件，开始生成...")
            self._locate_evidence_for_all_states()
        
        # 初始化时执行主题细分（带文件缓存）
        refined_file = None
        if self.phone_data_dir:
            process_dir = os.path.join(os.path.dirname(self.phone_data_dir), "process")
            refined_file = os.path.join(process_dir, "global_state_record_located_refined.json")
        
        if refined_file and os.path.exists(refined_file):
            try:
                with open(refined_file, 'r', encoding='utf-8') as f:
                    self.global_state_record_located_refined = json.load(f)
                if self.is_print:
                    print(f"✓ 从文件加载已细分的状态记录: {refined_file}")
                # 生成 topic_group 数据结构
                self._build_topic_group()
            except Exception as e:
                if self.is_print:
                    print(f"⚠️ 加载已细分状态记录失败: {e}，将重新生成")
                self._refine_state_topics()
        else:
            if self.is_print:
                print(f"⚠️ 未找到已细分状态记录文件，开始生成...")
            self._refine_state_topics()


    def _build_global_state_record(self):
        """构建全局状态记录，遍历所有月份并保存"""
        self.detect_state_changes()
        
        # 保存到文件
        if self.phone_data_dir:
            process_dir = os.path.join(os.path.dirname(self.phone_data_dir), "process")
            os.makedirs(process_dir, exist_ok=True)
            state_file = os.path.join(process_dir, "global_state_record.json")
            try:
                with open(state_file, 'w', encoding='utf-8') as f:
                    json.dump(self.global_state_record, f, ensure_ascii=False, indent=2)
                if self.is_print:
                    print(f"✓ 全局状态记录已保存至: {state_file}")
            except Exception as e:
                if self.is_print:
                    print(f"⚠️ 保存全局状态记录失败: {e}")
    
    def detect_state_changes(self):
        """遍历 draft_event，使用 LLM 分析月内状态变化，维护全局状态记录"""
        print("[KnowledgeGen] 正在分析状态变化...")
        changes = []
        
        # 遍历每个月的 draft_event
        for month, daily_list in self.draft_event.items():
            if not isinstance(daily_list, list) or len(daily_list) < 2:
                continue
            
            if self.is_print:
                print(f"  - 分析月份: {month}")
            
            # 构建该月的所有事件摘要
            month_events_summary = []
            for day_data in daily_list:
                date = day_data.get('date', '')
                events = day_data.get('events', [])
                month_events_summary.append({
                    'date': date,
                    'events': events
                })
            
            # 准备当前全局状态快照
            current_global_state = {}
            for state_name, state_info in self.global_state_record.items():
                current_global_state[state_name] = {
                    "current_state": state_info["current_state"],
                    "change_nodes_count": len(state_info["change_nodes"])
                }
            
            # 使用 LLM 分析月内状态变化
            analysis_prompt = f"""
            你是一位生活观察专家。请分析以下{month}的人物活动数据，找出该月内发生的**个人状态变化**。
            
            【重要说明】
            - **只关注人物自身的状态变化**，不考虑人际关系变化和他人的状态变动
            - 只记录有明显证据支持的变化，不要编造
            - 记录的事件节点要明显体现出个人的变化或者对进度有推动作用，不要记录影响不大，不体现个人的明显改变的节点。
            
            【月度活动数据】
            {json.dumps(month_events_summary, ensure_ascii=False, indent=2)}
            
            【当前全局状态快照】（截至上月末的状态）
            {json.dumps(current_global_state, ensure_ascii=False, indent=2) if current_global_state else "无历史状态记录"}
            
            【必须检测的状态类型】（共8个固定状态）
            **重要**：以下8个类型对应8个固定状态，同类型的不同事件都归到同一个状态下记录变化。
            
            1. **所在城市**：常住城市或居住地的变化
               - 示例：从北京搬到上海、从租房改为购房等
            
            2. **工作变动**：换工作、离职、入职、职位变化等（**只有确实出现变动才记录**）
               - 示例：从A公司跳槽到B公司、从工程师晋升为经理、失业后重新就业等
            
            3. **生活环境变化**：搬家、租房/购房、居住环境明显改善或恶化等（**出现明显变化才记录**）
               - 示例：从合租改为独居、搬到更好的小区、装修房屋等
            
            4. **身体健康变化**：生病、康复、健康状况显著改善或恶化等（**出现明显变化才记录**）
               - 示例：患上糖尿病、手术后康复、体检发现高血压等
            
            5. **运动里程碑事件**：所有运动相关的突破性进展都归到此状态
               - 示例：完成首次马拉松、游泳突破1000米、开始规律健身、跑步配速提升等
               - **注意**：跑步、游泳、健身等不同类型的运动都记录在"运动"这一个状态下
            
            6. **爱好/偏好变化**：新增爱好、培养新兴趣、偏好明显改变等
               - 示例：开始学习摄影、喜欢上喝咖啡、不再喜欢看电影等
            
            7. **年龄变化**：过生日导致的年龄增长
               - 示例：从27岁变为28岁
            
            8. **工资变化**：薪资调整、奖金、收入变化等
               - 示例：月薪从15k涨到18k、获得年终奖、副业收入增加等
            
            【排除项】
            - **不要记录人际关系变化**：与他人的关系变化不在本次检测范围内
            - **不要记录他人的状态变动**：只关注人物自身
            - **不要记录体重、生活习惯等日常细碎变化**
            
            【输出要求】
            - **只输出本月发生变化的状态**，本月没有变化的状态不要输出
            - 对于【当前全局状态快照】中已有的状态字段，如果本月发生了变化，则生成新的变化节点
            - 对于新的状态变化，可以添加新的状态字段
            - 对于每个状态变化，必须包含：
              * `name`: 状态名称（**必须严格使用以下8个标准名称之一**："所在城市"、"工作变动"、"生活环境变化"、"身体健康变化"、"运动"、"爱好/偏好变化"、"年龄"、"工资收入变化"）
              * `initial_state`: 初始状态（月初或变化前的状态，如果是已有状态则从全局状态快照中获取）
              * `change_nodes`: 变化节点数组，每个节点包含：
                - `date`: 变化发生的日期（YYYY-MM-DD）
                - `new_state`: 变化后的状态
            - 如果某个月没有明显状态变化，返回空数组
            
            **输出格式**
            请以 JSON 数组格式返回：
            [
                {{
                    "name": "状态名称",
                    "initial_state": "初始状态描述",
                    "change_nodes": [
                        {{
                            "date": "2025-01-15",
                            "new_state": "变化后的状态描述"
                        }}
                    ]
                }}
            ]
            
            **示例**
            [
                {{
                    "name": "所在城市",
                    "initial_state": "北京",
                    "change_nodes": [
                        {{
                            "date": "2025-01-10",
                            "new_state": "上海"
                        }}
                    ]
                }},
                {{
                    "name": "工作变动",
                    "initial_state": "A公司前端工程师",
                    "change_nodes": [
                        {{
                            "date": "2025-01-15",
                            "new_state": "B公司高级前端工程师"
                        }}
                    ]
                }},
                {{
                    "name": "运动",
                    "initial_state": "偶尔跑步，无系统训练",
                    "change_nodes": [
                        {{
                            "date": "2025-01-20",
                            "new_state": "完成首次半程马拉松，用时2小时15分"
                        }},
                        {{
                            "date": "2025-01-28",
                            "new_state": "开始规律游泳训练，每周3次"
                        }}
                    ]
                }},
                {{
                    "name": "年龄",
                    "initial_state": "27岁",
                    "change_nodes": [
                        {{
                            "date": "2025-01-25",
                            "new_state": "28岁"
                        }}
                    ]
                }}
            ]
            """
            
            try:
                from src.lifebench.utils.llm_call import llm_call_j
                llm_result = llm_call_j(analysis_prompt)
                # if self.is_print:
                #     print(f"    LLM 分析提示: {analysis_prompt}")
                #     print(f"    LLM 分析结果: {llm_result}")
                
                # 解析 LLM 结果
                if isinstance(llm_result, str):
                    start_idx = llm_result.find('[')
                    end_idx = llm_result.rfind(']') + 1
                    if start_idx != -1 and end_idx != -1:
                        llm_result = json.loads(llm_result[start_idx:end_idx])
                
                if isinstance(llm_result, list):
                    for change in llm_result:
                        change['month'] = month
                        changes.append(change)
                        
                        # 更新全局状态记录
                        state_name = change.get('name', '')
                        if state_name:
                            change_nodes = change.get('change_nodes', [])
                            if not change_nodes:
                                if self.is_print:
                                    print(f"    ⚠️ 状态 '{state_name}' 的 change_nodes 为空，跳过")
                                continue
                            
                            new_state = change_nodes[-1].get('new_state', '')
                            
                            if state_name not in self.global_state_record:
                                # 新状态
                                self.global_state_record[state_name] = {
                                    "initial_state": change.get('initial_state', ''),
                                    "current_state": new_state,
                                    "change_nodes": change_nodes
                                }
                            else:
                                # 已有状态，追加变化节点
                                existing = self.global_state_record[state_name]
                                existing["change_nodes"].extend(change_nodes)
                                existing["current_state"] = new_state
                    
                    if self.is_print:
                        print(f"    ✓ 检测到 {len(llm_result)} 处状态变化")
                        print(f"    ✓ 全局状态记录数: {len(self.global_state_record)}")
                else:
                    if self.is_print:
                        print(f"    ⚠️ LLM 返回格式异常")
            except Exception as e:
                if self.is_print:
                    print(f"    ✗ 分析失败: {e}")
        
        self.state_changes = changes
        print(f"[KnowledgeGen] ✓ 共检测到 {len(changes)} 处状态变化")
        print(f"[KnowledgeGen] ✓ 全局状态记录数: {len(self.global_state_record)}")
        return changes
    
    def _locate_evidence_for_all_states(self):
        """
        为全局状态记录中的所有变化节点搜索证据，并保存为 global_state_record_located
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        if self.is_print:
            print("\n[KnowledgeGen] 开始为所有状态变化节点搜索证据...")
        
        self.global_state_record_located = {}
        
        # 遍历所有状态
        for state_name, state_info in self.global_state_record.items():
            change_nodes = state_info.get("change_nodes", [])
            if not change_nodes:
                continue
            
            if self.is_print:
                print(f"  - 处理状态: {state_name} ({len(change_nodes)} 个变化节点)")
            
            # 并行搜索每个变化节点的证据
            located_nodes = []
            
            with ThreadPoolExecutor(max_workers=20) as executor:
                future_to_node = {}
                for node in change_nodes:
                    date = node.get("date", "")
                    if not date:
                        continue
                    
                    target_dates = [date]
                    if not target_dates:
                        continue
                    
                    # 并行搜索该日期范围内的证据
                    evidence_futures = []
                    for target_date in target_dates:
                        future = executor.submit(
                            self._search_evidence_in_daily_event,
                            target_date,
                            state_name,
                            node.get("new_state", "")
                        )
                        evidence_futures.append((future, target_date))
                    
                    # 收集证据
                    evidence_states = []
                    for future, target_date in evidence_futures:
                        try:
                            result = future.result()
                            if result:
                                evidence_states.append(result)
                        except Exception as e:
                            pass
                    
                    # 判断是否有证据
                    has_evidence = len(evidence_states) > 0
                    located_nodes.append({
                        "date": date,
                        "new_state": node.get("new_state", ""),
                        "has_evidence": has_evidence,
                        "evidence": evidence_states if has_evidence else []
                    })
            
            # 保存该状态的已定位信息
            self.global_state_record_located[state_name] = {
                "initial_state": state_info.get("initial_state", ""),
                "current_state": state_info.get("current_state", ""),
                "change_nodes": located_nodes
            }
        
        # 保存到文件
        if self.phone_data_dir:
            process_dir = os.path.join(os.path.dirname(self.phone_data_dir), "process")
            os.makedirs(process_dir, exist_ok=True)
            located_file = os.path.join(process_dir, "global_state_record_located.json")
            try:
                with open(located_file, 'w', encoding='utf-8') as f:
                    json.dump(self.global_state_record_located, f, ensure_ascii=False, indent=2)
                if self.is_print:
                    print(f"✓ 已定位状态记录已保存至: {located_file}")
            except Exception as e:
                if self.is_print:
                    print(f"⚠️ 保存已定位状态记录失败: {e}")
        
        if self.is_print:
            total_nodes = sum(len(info.get("change_nodes", [])) for info in self.global_state_record_located.values())
            evidenced_nodes = sum(
                sum(1 for node in info.get("change_nodes", []) if node.get("has_evidence", False))
                for info in self.global_state_record_located.values()
            )
            print(f"[KnowledgeGen] ✓ 证据搜索完成，共 {total_nodes} 个节点，{evidenced_nodes} 个有证据")

    
    def _get_date_range(self, date: str) -> List[str]:
        """
        获取指定日期及其前后两天的日期列表
        
        Args:
            date: 日期字符串，格式为 YYYY-MM-DD
        
        Returns:
            日期列表，最多5个日期（前2天、当天、后2天）
        """
        from datetime import datetime, timedelta
        
        try:
            current_date = datetime.strptime(date, "%Y-%m-%d")
            dates = []
            
            # 前2天到后2天
            for i in range(-1, 2):
                target_date = current_date + timedelta(days=i)
                dates.append(target_date.strftime("%Y-%m-%d"))
            
            return dates
        except Exception as e:
            print(f"  ⚠️ 解析日期 {date} 失败: {e}")
            return []
    
    def _search_evidence_in_daily_event(self, date: str, change_type: str, change_detail: str) -> Dict:
        """
        在指定日期的 daily_event 中搜索能体现变化的事件（使用 LLM 分析）
        
        Args:
            date: 日期字符串，格式为 YYYY-MM-DD
            change_type: 变化类型
            change_detail: 变化详情
        
        Returns:
            如果找到相关事件，返回包含日期和相关事件的字典；否则返回 None
        """
        #print(f"[KnowledgeGen] 正在搜索 {date} 的证据...","输入为", change_type, change_detail)

        # 获取该日期及其前后两天的日期范围
        target_dates = self._get_date_range(date)
        if not target_dates:
            return None
        #print(target_dates)
        # 收集这些日期的所有事件
        all_events = []
        for event in self.daily_event:
            # 检查事件的日期是否在目标日期范围内
            event_dates = event.get("date", [])
            if not event_dates:
                continue
            
            # 提取事件的日期部分（从 "2025-01-01 06:30:00至2025-01-01 07:00:00" 中提取 "2025-01-01"）
            for date_range in event_dates:
                if isinstance(date_range, str):
                    # 提取开始日期
                    start_date = date_range.split("至")[0].split(" ")[0] if "至" in date_range else date_range.split(" ")[0]
                    
                    # 检查是否在目标日期范围内
                    if start_date in target_dates:
                        evt_with_date = event.copy()
                        evt_with_date["event_date"] = start_date
                        all_events.append(evt_with_date)
                        break  # 每个事件只添加一次
        
        if not all_events:
            return None
        
        # 使用 LLM 分析哪些事件能体现变化
        prompt = f"""
        你是一位生活观察专家。人物在 {date} 发生了一项状态变化：
        【变化类型】: {change_type}
        【变化详情】: {change_detail}
        
        【候选事件列表】（来自 {date} 及其前后两天的 daily_event）
        {json.dumps(all_events, ensure_ascii=False, indent=2)}
        
        【任务要求】
        请从候选事件中找出能够体现或支持这一状态变化的事件。要求找最主要直接的事件。
        
        **筛选标准**：
        - 事件应该直接或间接反映了状态的变化
        - 事件可能是导致变化的原因，也可能是变化的结果或表现
        - 选择最相关的个事件，不要超过4个。选择尽可能少的能体现变化的事件。只有一个事件体现不了时才选多个事件。
        
        **输出格式**：
        请以 JSON 数组格式返回相关事件的 ID 列表：
        ["event_id_1", "event_id_2", ...]
        
        如果没有找到相关事件，返回空数组 []。
        """
        
        try:
            res = llm_call_j(prompt)
            if isinstance(res, str):
                res = json.loads(res)
            
            # 提取相关事件
            related_event_ids = res if isinstance(res, list) else []
            
            if not related_event_ids:
                return None
            
            # 根据 ID 过滤出相关事件
            related_events = []
            for evt in all_events:
                if evt.get("id") in related_event_ids or evt.get("event_id") in related_event_ids:
                    related_events.append(evt)
            
            if not related_events:
                return None
            
            return {
                "events": related_events,
                "event_ids": related_event_ids
            }
        
        except Exception as e:
            if self.is_print:
                print(f"  ⚠️ LLM 分析失败: {e}")
            return None

    def _refine_state_topics(self):
        """
        对 global_state_record_located 中的每个状态进行主题细分，生成 global_state_record_located_refined
        """
        if self.is_print:
            print("\n[KnowledgeGen] 开始对状态进行主题细分...")
        
        self.global_state_record_located_refined = {}
        
        # 遍历所有状态
        for state_name, state_info in self.global_state_record_located.items():
            change_nodes = state_info.get("change_nodes", [])
            if not change_nodes:
                continue
            
            if self.is_print:
                print(f"  - 处理状态: {state_name} ({len(change_nodes)} 个变化节点)")
            
            # 为每个节点分配 ID
            nodes_with_ids = []
            for idx, node in enumerate(change_nodes):
                node_with_id = node.copy()
                node_with_id["node_id"] = idx
                nodes_with_ids.append(node_with_id)
            
            # 使用 LLM 对该状态的所有节点进行分组
            grouped_result = self._group_state_nodes(state_name, nodes_with_ids)
            
            # 根据分组结果构建细化后的节点
            refined_nodes = []
            if grouped_result:
                # 为每个组内的节点添加组信息
                for group in grouped_result.get("groups", []):
                    group_name = group.get("group_name", "")
                    group_description = group.get("group_description", "")
                    node_ids = group.get("node_ids", [])
                    
                    # 找到对应的节点并添加组信息
                    for node_id in node_ids:
                        if 0 <= node_id < len(nodes_with_ids):
                            refined_node = nodes_with_ids[node_id].copy()
                            refined_node["refined_topic"] = group_name
                            refined_node["topic_description"] = group_description
                            refined_nodes.append(refined_node)
            else:
                # 如果分组失败，保留原始节点
                refined_nodes = nodes_with_ids
            
            # 保存该状态的已细分信息
            self.global_state_record_located_refined[state_name] = {
                "initial_state": state_info.get("initial_state", ""),
                "current_state": state_info.get("current_state", ""),
                "change_nodes": refined_nodes
            }
        
        # 保存到文件
        if self.phone_data_dir:
            process_dir = os.path.join(os.path.dirname(self.phone_data_dir), "process")
            os.makedirs(process_dir, exist_ok=True)
            refined_file = os.path.join(process_dir, "global_state_record_located_refined.json")
            try:
                with open(refined_file, 'w', encoding='utf-8') as f:
                    json.dump(self.global_state_record_located_refined, f, ensure_ascii=False, indent=2)
                if self.is_print:
                    print(f"✓ 已细分状态记录已保存至: {refined_file}")
            except Exception as e:
                if self.is_print:
                    print(f"⚠️ 保存已细分状态记录失败: {e}")
        
        if self.is_print:
            total_nodes = sum(len(info.get("change_nodes", [])) for info in self.global_state_record_located_refined.values())
            print(f"[KnowledgeGen] ✓ 主题细分完成，共 {total_nodes} 个节点")
        
        # 生成 topic_group 数据结构
        self._build_topic_group()
    
    def _build_topic_group(self):
        """
        根据 global_state_record_located_refined 构建 topic_group 数据结构
        topic_group 是一个字典，key 为 topic_group_id，value 为该组的所有节点
        """
        self.topic_group = {}
        
        if not hasattr(self, 'global_state_record_located_refined'):
            return
        
        for state_name, state_info in self.global_state_record_located_refined.items():
            change_nodes = state_info.get("change_nodes", [])
            if not change_nodes:
                continue
            
            # 按 refined_topic 分组
            topic_to_nodes = {}
            for node in change_nodes:
                refined_topic = node.get("refined_topic", "未分类")
                if refined_topic not in topic_to_nodes:
                    topic_to_nodes[refined_topic] = []
                topic_to_nodes[refined_topic].append(node)
            
            # 为每个主题组生成唯一的 topic_group ID 并存储
            for refined_topic, nodes in topic_to_nodes.items():
                topic_group_id = f"{state_name}_{refined_topic}"
                self.topic_group[topic_group_id] = {
                    "state_name": state_name,
                    "refined_topic": refined_topic,
                    "nodes": nodes,
                    "node_count": len(nodes)
                }
    
    def _group_state_nodes(self, state_name: str, nodes_with_ids: List[Dict]) -> Dict:
        """
        使用 LLM 对某个状态的所有节点进行分组
        
        Args:
            state_name: 状态名称
            nodes_with_ids: 包含 node_id 的节点列表
        
        Returns:
            分组结果，包含 groups 数组，每个 group 包含 group_name, group_description, node_ids
        """
        # 构建节点摘要
        nodes_summary = []
        for node in nodes_with_ids:
            nodes_summary.append({
                "node_id": node.get("node_id"),
                "date": node.get("date", ""),
                "new_state": node.get("new_state", "")
            })
        
        prompt = f"""
        你是一位生活分析专家。请对以下状态的所有变化节点进行主题分组。
        
        【状态类型】: {state_name}
        
        【所有变化节点】
        {json.dumps(nodes_summary, ensure_ascii=False, indent=2)}
        
        【任务要求】
        请根据节点的变化内容，将这些节点分成若干个主题组。每个组应该包含具有相似主题或性质的节点。
        
        **分组原则**：
        - 同一组内的节点应该有共同的主题特征
        - 例如："工作变动" 状态下，可以分为 "跳槽组"、"晋升组"、"离职组" 等
        - 例如："运动" 状态下，可以分为 "马拉松相关"、"游泳训练"、"健身习惯" 等
        - 例如："爱好/偏好变化" 状态下，可以分为 "新增爱好"、"兴趣深化"、"偏好转变" 等
        - 组的数量应该合理，通常 2-5 个组
        - 每个节点必须属于且仅属于一个组
        
        **输出格式**：
        请以 JSON 格式返回分组结果：
        {{
            "groups": [
                {{
                    "group_name": "组名（简洁明确的主题标签）",
                    "group_description": "对该组主题的简要描述（20-50字）",
                    "node_ids": [0, 2, 5]  // 该组包含的节点 ID 列表
                }},
                {{
                    "group_name": "另一个组名",
                    "group_description": "描述",
                    "node_ids": [1, 3, 4]
                }}
            ]
        }}
        
        **注意**：
        - node_ids 必须是输入中存在的节点 ID
        - 所有节点都必须被分配到某个组
        - 不能有重复的节点 ID
        """
        
        try:
            res = llm_call_j(prompt)
            if isinstance(res, str):
                res = json.loads(res)
            
            return res
        
        except Exception as e:
            if self.is_print:
                print(f"  ⚠️ LLM 分组失败: {e}")
            return None

    def generate_questions_by_topic(self, max_questions_per_topic: int = 10):
        """
        基于 topic_group 生成问题，遍历每个主题组，LLM 设计不超过 max_questions_per_topic 个问题
        
        Args:
            max_questions_per_topic: 每个主题组最多生成的问题数量
        
        Returns:
            生成的 QA 列表
        """
        if not hasattr(self, 'topic_group') or not self.topic_group:
            if self.is_print:
                print("⚠️ topic_group 为空，无法生成问题")
            return []
        
        all_questions = []
        
        if self.is_print:
            print(f"\n[KnowledgeGen] 开始基于主题生成问题，共 {len(self.topic_group)} 个主题组...")



        # 遍历每个主题组
        for topic_group_id, group_info in self.topic_group.items():
            state_name = group_info.get("state_name", "")
            refined_topic = group_info.get("refined_topic", "")
            nodes = group_info.get("nodes", [])
            node_count = group_info.get("node_count", 0)
            
            if not nodes:
                continue
            
            if self.is_print:
                print(f"  - 处理主题: {topic_group_id} ({node_count} 个节点)")
            
            # 构建节点摘要
            nodes_summary = []
            for node in nodes:
                nodes_summary.append({
                    "node_id": node.get("node_id", ""),
                    "date": node.get("date", ""),
                    "new_state": node.get("new_state", "")
                })
            
            # 使用 LLM 生成问题
            questions = self._generate_questions_for_topic(
                topic_group_id,
                state_name,
                refined_topic,
                nodes_summary,
                max_questions_per_topic
            )
            
            if questions:
                # 验证并补充该主题组涉及的节点的手机数据
                questions = self.validate_and_generate_phone_data_for_nodes(questions)
                
                # 为每个问题添加 required_events_id 和 evidence 字段
                for qa in questions:
                    node_ids = qa.get("node_ids", [])
                    if isinstance(node_ids, list) and node_ids:
                        # 收集所有相关节点的证据事件ID
                        all_event_ids = []
                        for nid in node_ids:
                            node_info = self._get_node_by_id(nid)
                            if node_info:
                                evidence = node_info.get("evidence", [])
                                if evidence and isinstance(evidence, list):
                                    for evt_group in evidence:
                                        if isinstance(evt_group, dict):
                                            events = evt_group.get("events", [])
                                            if isinstance(events, list):
                                                for event in events:
                                                    if isinstance(event, dict):
                                                        event_id = event.get("event_id") or event.get("id")
                                                        if event_id:
                                                            all_event_ids.append(str(event_id))
                        
                        # 去重
                        all_event_ids = list(set(all_event_ids))
                        qa["required_events_id"] = all_event_ids

                        # 校验并调整 ask_time：若 ask_time 在所有引用事件最晚日期之前，则调整为最晚日期 + 1 天
                        if all_event_ids and qa.get('ask_time'):
                            qa['ask_time'] = self._adjust_ask_time_for_knowledge(all_event_ids, qa['ask_time'])
                        
                        # 基于 required_events_id 获取对应的手机数据作为 evidence
                        if all_event_ids:
                            phone_evidence = self._get_phone_data_by_event_ids(all_event_ids)
                            qa["evidence"] = phone_evidence
                        else:
                            qa["evidence"] = []
                    else:
                        qa["required_events_id"] = []
                        qa["evidence"] = []
                    qa['question_type'] = 'Knowledge_Update'
                    qa['score_points'] = [{
        "description": f"正确回答出答案:{qa['answer']}",
        "score": 10
      }]
                all_questions.extend(questions)
                if self.is_print:
                    print(f"    ✓ 生成 {len(questions)} 个问题（已补充手机数据）")
                    for qa in questions:
                        print(qa)

        if self.is_print:
            print(f"[KnowledgeGen] ✓ 完成，共生成 {len(all_questions)} 个问题")
        
        return all_questions

    def _adjust_ask_time_for_knowledge(self, required_events_id: List[str], ask_time: str) -> str:
        """
        校验 ask_time 是否在 required_events_id 所有事件最晚日期之后，
        若不是，则调整为最晚日期的下一天（YYYY-MM-DD 格式）。

        Args:
            required_events_id: 问题引用的必需事件 ID 列表
            ask_time: 当前提问时间（格式 YYYY-MM-DD 或 YYYY-MM）

        Returns:
            调整后的提问时间（YYYY-MM-DD）
        """
        if not required_events_id or not ask_time:
            return ask_time

        # 构建 event_id -> date 的映射
        event_id_to_date = {}
        for event in self.daily_event:
            if isinstance(event, dict):
                eid = str(event.get('event_id', ''))
                event_id_to_date[eid] = event.get('date', [])

        # 找到所有引用的最晚事件日期
        latest_dt = None
        for eid in required_events_id:
            dates = event_id_to_date.get(str(eid), [])
            for date_range in dates:
                if isinstance(date_range, str) and '至' in date_range:
                    start_part = date_range.split('至')[0].strip()
                    try:
                        dt = datetime.strptime(start_part, "%Y-%m-%d %H:%M:%S")
                        if latest_dt is None or dt > latest_dt:
                            latest_dt = dt
                    except ValueError:
                        pass

        if latest_dt is None:
            return ask_time

        # 解析 ask_time（兼容 YYYY-MM 和 YYYY-MM-DD 格式）
        try:
            if ask_time.count('-') == 2:
                ask_dt = datetime.strptime(ask_time, "%Y-%m-%d")
            else:
                ask_dt = datetime.strptime(ask_time, "%Y-%m")
        except ValueError:
            return ask_time

        # 若 ask_time 在最晚事件日期之前或当天，调整为最晚日期 + 1 天
        if ask_dt <= latest_dt:
            adjusted_dt = latest_dt + timedelta(days=1)
            # 若超过 2025-12-31，则用 2025-12-31
            max_dt = datetime(2025, 12, 31)
            if adjusted_dt > max_dt:
                adjusted_dt = max_dt
            print(f"[ask_time 调整] 原 ask_time {ask_time} 早于最晚事件日期 {latest_dt.strftime('%Y-%m-%d')}, 已调整为 {adjusted_dt.strftime('%Y-%m-%d')}")
            return adjusted_dt.strftime("%Y-%m-%d")

        return ask_time

    def _generate_questions_for_topic(self, topic_group_id: str, state_name: str, 
                                      refined_topic: str, nodes_summary: List[Dict],
                                      max_questions: int) -> List[Dict]:
        """
        为单个主题组生成问题
        
        Args:
            topic_group_id: 主题组 ID
            state_name: 状态名称
            refined_topic: 细分主题
            nodes_summary: 节点摘要列表
            max_questions: 最大问题数量
        
        Returns:
            生成的 QA 列表
        """
        prompt = f"""
        你是一位生活观察专家和问题设计师。请基于以下人物状态变化信息，设计**知识和信息更新类问题对**。
        
        **核心概念**：知识和信息更新问题是指，在不同时间点询问同一个问题时，由于人物状态发生了变化，得到的答案会不一样。
        
        【状态类型】: {state_name}
        【细分主题】: {refined_topic}
        
        【状态变化节点】
        {json.dumps(nodes_summary, ensure_ascii=False, indent=2)}
        
        【任务要求】
        请设计**成对的问题**（至少2个问题，必须是偶数个），每对问题应该是：
        - **相同的核心问题**，但在**不同的时间点**提问
        - 由于状态发生了变化，两个问题的**答案不同**
        
        例如：
        - 问题1："冯浩然在哪里工作？" (ask_time: "2025-01-10") → 答案："A公司"
        - 问题2："冯浩然在哪里工作？" (ask_time: "2025-01-20") → 答案："B公司"
        
        **具体要求**：
        
        1. **问题本质**：
           - 问题应该是询问人物的某个状态或信息
           - 在状态变化前后，这个问题的答案应该不同
           - **重要**：设计问题时，对于目标节点外的所有之前节点都要考虑是否会影响答案
           - 例如：如果人物去过徐州、南京、苏州三个城市旅游，那么在第三个节点之后提问"我去过哪些城市旅游？"时，答案应该是"徐州、南京、苏州"，而不是只有"苏州"
           - 累积性的状态（如去过的地方、学过的技能、完成的事项等）需要包含所有历史节点的信息
        
        2. **ask_time 设计与事件参考范围**：
           - 每个问题必须包含 `ask_time` 字段，表示提问的时间点
           - **重要约束**：`ask_time` 必须是 "YYYY-MM-DD" 格式（如 "2025-01-10"、"2025-03-31"），具体到天
           - **时间顺序强制要求**：`ask_time` 必须在所引用节点的所有事件日期之后（包含当天），否则会导致时间逻辑矛盾
             * 如果节点的最新事件发生在 2025-03-15，则 `ask_time` 必须 >= 2025-03-15
             * 例如：`ask_time: "2025-03-16"` 表示在 2025年3月16日 提问
             * 例如：`ask_time: "2025-04-01"` 表示在 2025年4月1日 提问
           - **上限约束**：`ask_time` 最晚不得超过 2025-12-31
           - **时间偏移原则**：`ask_time` 应该与状态变化节点的时间有合理的间隔
             * 如果节点发生在某月中旬，`ask_time` 可以是该月或下个月
             * 避免 `ask_time` 与节点日期过于接近，应该有足够的时间让状态稳定
           
           **根据问题类型确定参考的事件范围**：
           - **问"上一次"、"前两次"等特定次序**：需要准确定位到特定的时间节点，考察记忆系统能否识别事件的先后顺序
             * 例如："我上一次去哪里旅游了？" → 需要找到最近一次旅行事件
             * 例如："我前两次参加的比赛是什么？" → 需要找到倒数第二次的比赛
           
           - **问"累计"、"总共"、"一共"等累积性问题**：需要参考从开始到 ask_time 的所有相关事件
             * 例如："我一共去过哪些城市旅游？" → 需要汇总所有旅行事件
             * 例如："我总共完成了多少个项目？" → 需要统计所有完成的项目
           
           - **问"近期"、"最近"、"这段时间"等模糊时间**：主要参考最近的事件，但也要考虑上下文
             * 例如："我最近在忙什么？" → 参考最近的几个事件
             * 例如："这段时间我的工作状态如何？" → 参考近期的工作相关事件
           
           - **问当前状态**：参考 ask_time 之前最后一个影响该状态的事件
             * 例如："我现在在哪里工作？" → 参考最后一次工作变动
        
        3. **问题质量与意义**：
           - 问题应该具体、明确，避免模糊
           - 答案必须能够从提供的节点信息中推导出来
           - 不要编造不存在的信息
           - **问题必须有实际意义**：应该是真实用户可能会问的问题，有明确的查询目的
           - **体现变化的难度**：问题的设计应该考察记忆系统是否捕捉到了状态变化
             * 如果两个时间点的答案相同，说明这个问题没有体现出变化的价值
             * 好的问题应该让答题者需要仔细回忆和推理才能给出正确答案
             * 问题应该有一定的挑战性，不能太显而易见
           - **题目描述要自然流畅**，像真实用户会问的问题
           - **使用第一人称视角**，例如"我现在..."、"我最近..."、"我的..."
        
        4. **node_ids 标注**：
           - 每个问题必须包含 `node_ids` 字段，指明是基于哪些变化节点设计的
           - `node_ids` 是一个数组，包含相关的节点 ID
           - 例如：如果问题涉及从节点0到节点1的变化，则 `node_ids: [0, 1]`
        
        5. **成对输出**：
           - 必须输出偶数个问题（2个、4个、6个等）
           - 每对问题应该是相同的核心问题，但 ask_time 不同
           - 每对问题的答案应该不同，体现状态变化
        
        **输出格式**：
        请以 JSON 数组格式返回问题和答案：
        [
            {{
                "question": "问题内容",
                "answer": "答案内容",
                "ask_time": "提问时间点（YYYY-MM-DD 格式，如 2025-03-16）",
                "node_ids": [0, 1]
            }},
            {{
                "question": "问题内容（与上一个问题相同或类似）",
                "answer": "答案内容（与上一个答案不同）",
                "ask_time": "提问时间点（YYYY-MM-DD 格式，与上一个时间不同，且在节点事件日期之后）",
                "node_ids": [0, 1]
            }}
        ]
        
        **示例**：
        [
            {{
                "question": "冯浩然在哪里工作？",
                "answer": "冯浩然在A公司担任前端工程师。",
                "ask_time": "2025-01-10",
                "node_ids": [0]
            }},
            {{
                "question": "冯浩然在哪里工作？",
                "answer": "冯浩然在B公司担任高级前端工程师。",
                "ask_time": "2025-01-20",
                "node_ids": [0]
            }},
            {{
                "question": "冯浩然的月收入是多少？",
                "answer": "冯浩然的月收入是15000元。",
                "ask_time": "2025-02-01",
                "node_ids": [1]
            }},
            {{
                "question": "冯浩然的月收入是多少？",
                "answer": "冯浩然的月收入是18000元。",
                "ask_time": "2025-03-01",
                "node_ids": [1]
            }}
        ]
        
        **注意**：
        - 必须输出偶数个问题（至少2个）
        - `ask_time` 格式必须为 "YYYY-MM-DD"，且必须在所引用节点的所有事件日期之后，最晚不得超过 2025-12-31
        - `node_ids` 必须引用输入中存在的节点 ID
        - 问题的答案应该反映在 `ask_time` 这个时间点的状态
        - 每对问题的核心问题应该相同或非常相似，但答案不同
        """
        
        try:
            res = llm_call_j(prompt)
            print(f"[KnowledgeGen] LLM 输入: {prompt}")
            print(f"[KnowledgeGen] LLM 生成问题结果: {res}")
            if isinstance(res, str):
                res = json.loads(res)
            
            if isinstance(res, list):
                # 限制问题数量
                return res[:max_questions]
            else:
                return []
        
        except Exception as e:
            if self.is_print:
                print(f"  ⚠️ LLM 生成问题失败: {e}")
            return []
    
    def validate_and_generate_phone_data_for_nodes(self, questions: List[Dict]) -> List[Dict]:
        """
        验证问题涉及的节点是否有对应的手机数据，若没有则生成
        
        Args:
            questions: generate_questions_by_topic 输出的问题列表
        
        Returns:
            补充了手机数据的问题列表
        """
        if not questions:
            return questions
        
        print(f"\n[KnowledgeGen] 开始验证和补充 {len(questions)} 个问题的手机数据...")
        
        # 收集所有涉及的 node_id
        all_node_ids = set()
        for qa in questions:
            node_ids = qa.get("node_ids", [])
            if isinstance(node_ids, list):
                all_node_ids.update(node_ids)
        
        if not all_node_ids:
            print("[KnowledgeGen] 没有涉及任何节点，跳过验证")
            return questions
        
        print(f"[KnowledgeGen] 共涉及 {len(all_node_ids)} 个节点")
        
        # 遍历每个节点，检查并补充手机数据
        for node_id in all_node_ids:
            self._validate_and_generate_phone_data_for_single_node(node_id)
        
        print(f"[KnowledgeGen] ✓ 手机数据验证和补充完成")
        
        return questions
    
    def _validate_and_generate_phone_data_for_single_node(self, node_id: int):
        """
        验证单个节点是否有对应的手机数据，若没有则生成
        
        Args:
            node_id: 节点 ID
        """
        # 1. 获取节点信息
        node_info = self._get_node_by_id(node_id)
        if not node_info:
            print(f"  ⚠️ 节点 {node_id} 不存在")
            return
        
        date = node_info.get("date", "")
        new_state = node_info.get("new_state", "")
        evidence = node_info.get("evidence", [])
        
        if not date or not new_state:
            print(f"  ⚠️ 节点 {node_id} 缺少必要信息")
            return
        
        print(f"\n  - 验证节点 {node_id}: {date} - {new_state[:50]}...")
        
        # 2. 从节点的 evidence 字段获取 daily_event ID
        event_ids = []
        if evidence and isinstance(evidence, list):
            for evt_group in evidence:
                if isinstance(evt_group, dict):
                    # evidence 结构: {"events": [{"event_id": "12", ...}, ...]}
                    events = evt_group.get("events", [])
                    if isinstance(events, list):
                        for event in events:
                            if isinstance(event, dict):
                                event_id = event.get("event_id") or event.get("id")
                                if event_id:
                                    event_ids.append(str(event_id))
        
        if not event_ids:
            print(f"    ⚠️ 节点 {node_id} 的 evidence 字段为空或缺少事件ID")
            return
        
        print(f"    - 从 evidence 中找到 {len(event_ids)} 个事件: {event_ids}")
        
        # 3. 获取这些事件对应的手机数据
        phone_data = self._get_phone_data_by_event_ids(event_ids)
        
        print(f"    - 找到 {len(phone_data)} 条手机数据")
        
        # 4. 使用 LLM 分析手机数据是否体现了该节点的状态变化
        is_reflected = self._check_if_phone_data_reflects_node(phone_data, new_state, date)
        
        if is_reflected:
            print(f"    ✓ 手机数据已体现该节点状态")
        else:
            print(f"    ⚠️ 手机数据未体现该节点状态，开始生成...")
            # 5. 生成手机数据
            generated_phone_data = self._generate_phone_data_for_node(node_info, event_ids)
            
            if generated_phone_data:
                print(f"    ✓ 成功生成 {len(generated_phone_data)} 条手机数据")
                # 6. 将生成的数据添加到 phonedata 中
                self._add_generated_phone_data(generated_phone_data)
            else:
                print(f"    ✗ 生成手机数据失败")
    
    def _get_node_by_id(self, node_id: int) -> Dict:
        """
        根据 node_id 获取节点信息
        
        Args:
            node_id: 节点 ID
        
        Returns:
            节点信息字典
        """
        if not hasattr(self, 'topic_group') or not self.topic_group:
            return {}
        
        for topic_group_id, group_info in self.topic_group.items():
            nodes = group_info.get("nodes", [])
            for node in nodes:
                if node.get("node_id") == node_id:
                    return node
        
        return {}
    
    def _get_event_ids_by_date(self, date: str) -> List[str]:
        """
        根据日期获取对应的 daily_event ID 列表
        
        Args:
            date: 日期字符串
        
        Returns:
            事件 ID 列表
        """
        event_ids = []
        
        if not self.daily_event:
            return event_ids
        
        for event in self.daily_event:
            event_dates = event.get("date", [])
            if not event_dates:
                continue
            
            for date_range in event_dates:
                if isinstance(date_range, str):
                    # 处理单个日期或日期范围
                    if "至" in date_range:
                        start_end = date_range.split("至")
                        start_date = start_end[0].strip().split(" ")[0]
                        end_date = start_end[1].strip().split(" ")[0]
                        if start_date <= date <= end_date:
                            event_id = event.get("id") or event.get("event_id")
                            if event_id:
                                event_ids.append(str(event_id))
                            break
                    else:
                        event_date = date_range.split(" ")[0]
                        if event_date == date:
                            event_id = event.get("id") or event.get("event_id")
                            if event_id:
                                event_ids.append(str(event_id))
                            break
        
        return event_ids
    
    def _get_phone_data_by_event_ids(self, event_ids: List[str]) -> List[Dict]:
        """
        根据事件 ID 列表获取对应的手机数据
        
        Args:
            event_ids: 事件 ID 列表
        
        Returns:
            手机数据列表
        """
        phone_data_list = []
        
        if not self.phonedata or not event_ids:
            return phone_data_list
        
        event_id_set = set(str(eid) for eid in event_ids)
        
        for data_type, data_items in self.phonedata.items():
            if not isinstance(data_items, list):
                continue
            
            for item in data_items:
                if not isinstance(item, dict):
                    continue
                
                # 检查 daily_event_id 或 related_event 字段
                item_event_id = str(item.get('daily_event_id', ''))
                related_event = str(item.get('related_event', ''))
                
                if item_event_id in event_id_set or related_event in event_id_set:
                    phone_data_list.append({
                        'type': data_type,
                        'data': item
                    })
        
        return phone_data_list
    
    def _check_if_phone_data_reflects_node(self, phone_data: List[Dict], new_state: str, date: str) -> bool:
        """
        使用 LLM 分析手机数据是否体现了节点的状态变化
        
        Args:
            phone_data: 手机数据列表
            new_state: 新的状态描述
            date: 日期
        
        Returns:
            如果手机数据体现了状态变化返回 True，否则返回 False
        """
        if not phone_data:
            return False
        
        # 构建手机数据摘要
        phone_data_summary = json.dumps(phone_data[:5], ensure_ascii=False, indent=2)  # 只取前5条
        
        prompt = f"""
        你是一位用户行为分析师。请分析以下手机数据是否体现了用户在 {date} 的状态变化。
        
        【状态变化】
        {new_state}
        
        【{date} 的手机数据】
        {phone_data_summary}
        
        【任务要求】
        请判断这些手机数据是否能够反映或支持上述状态变化。
        
        **判断标准**：
        - 手机数据应该直接或间接反映了状态的变化
        - 例如：如果状态是“换了新工作”，手机数据中应该有与新工作相关的通讯、日程等
        - 如果状态是“去了某地旅游”，手机数据中应该有与旅行相关的照片、导航、预订等
        
        **输出格式**：
        请以 JSON 格式返回：
        {{
            "is_reflected": true/false,
            "reason": "简要说明判断理由（20字以内）"
        }}
        """
        
        try:
            res = llm_call_j(prompt)
            if isinstance(res, str):
                res = json.loads(res)
            
            return res.get("is_reflected", False)
        
        except Exception as e:
            if self.is_print:
                print(f"      ⚠️ LLM 分析失败: {e}")
            return False
    
    def _generate_phone_data_for_node(self, node_info: Dict, event_ids: List[str]) -> List[Dict]:
        """
        为节点生成手机数据
        
        Args:
            node_info: 节点信息
            event_ids: 相关事件 ID 列表
        
        Returns:
            生成的手机数据列表
        """
        date = node_info.get("date", "")
        new_state = node_info.get("new_state", "")
        state_name = node_info.get("state_name", "")
        
        prompt = f"""
        你是一位手机数据生成专家。请基于用户的状态变化，生成合理的手机操作数据。
        
        【状态变化】
        - 日期: {date}
        - 状态类型: {state_name}
        - 新状态: {new_state}
        
        【相关事件 ID】
        {json.dumps(event_ids, ensure_ascii=False)}
        
        【任务要求】
        请生成 2-5 条能够反映该状态变化的手机数据。
        
        **生成原则**：
        1. **相关性**：手机数据必须与状态变化直接相关
        2. **真实性**：数据应该符合真实用户的手机使用习惯
        3. **多样性**：可以包含不同类型的手机数据（短信、通话、笔记、日历、照片等）
        4. **时间合理**：数据的时间应该在 {date} 当天或前后
        
        **可选的数据类型**：
        - sms: 短信
        - call: 通话记录
        - note: 笔记
        - calendar: 日历事件
        - photo: 照片元数据
        - app_usage: APP 使用记录
        
        **输出格式**：
        请以 JSON 数组格式返回：
        [
            {{
                "type": "sms",
                "data": {{
                    "content": "短信内容",
                    "timestamp": "{date} 10:30:00",
                    "direction": "received",
                    "contact": "联系人姓名"
                }},
                "related_event_id": "事件ID"
            }},
            ...
        ]
        
        **示例**（假设状态是“换了新工作”）：
        [
            {{
                "type": "sms",
                "data": {{
                    "content": "欢迎加入我们的团队！明天上午9点到公司报到。",
                    "timestamp": "{date} 18:00:00",
                    "direction": "received",
                    "contact": "HR李经理"
                }},
                "related_event_id": "{event_ids[0] if event_ids else ''}" 
            }},
            {{
                "type": "calendar",
                "data": {{
                    "title": "新员工入职培训",
                    "start_time": "{date} 09:00:00",
                    "end_time": "{date} 17:00:00",
                    "location": "公司会议室A"
                }},
                "related_event_id": "{event_ids[0] if event_ids else ''}" 
            }}
        ]
        """
        
        try:
            res = llm_call_j(prompt)
            if isinstance(res, str):
                res = json.loads(res)
            
            if isinstance(res, list):
                return res
            else:
                return []
        
        except Exception as e:
            if self.is_print:
                print(f"      ⚠️ LLM 生成手机数据失败: {e}")
            return []
    
    def _add_generated_phone_data(self, generated_data: List[Dict]):
        """
        将生成的手机数据添加到 phonedata 中
        
        Args:
            generated_data: 生成的手机数据列表
        """
        if not self.phonedata:
            self.phonedata = {}
        
        for item in generated_data:
            data_type = item.get("type", "unknown")
            data_content = item.get("data", {})
            related_event_id = item.get("related_event_id", "")
            
            # 添加 related_event 字段
            if isinstance(data_content, dict):
                data_content["related_event"] = related_event_id
            
            # 添加到对应的数据类型列表中
            if data_type not in self.phonedata:
                self.phonedata[data_type] = []
            
            self.phonedata[data_type].append(data_content)
        
        if self.is_print:
            print(f"      - 已添加 {len(generated_data)} 条手机数据到 phonedata")

    def QAGen(self, **kwargs):
        """
        实现基类抽象方法，作为外部调用的统一入口
        """
        max_questions_per_topic = kwargs.get('max_questions_per_topic', 6)
        
        # 3. 基于主题生成问题（会自动验证和补充手机数据）
        if self.is_print:
            print(f"\n[QAGen] 开始基于主题生成知识更新问题（每个主题最多 {max_questions_per_topic} 个问题）...")
        questions = self.generate_questions_by_topic(max_questions_per_topic=max_questions_per_topic)
        
        # 4. 过滤和优化问题
        if questions:
            if self.is_print:
                print(f"\n[QAGen] 开始过滤和优化 {len(questions)} 个问题...")
            questions = self._filter_and_refine_questions(questions)
        
        if self.is_print:
            print(f"[QAGen] ✓ 完成，共生成 {len(questions)} 个问题")
        
        return questions

    def _filter_and_refine_questions(self, questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        使用 20 线程并行过滤和优化问题

        工作流程：
        1. 检查问题和答案是否可以根据 evidence 推断回答
        2. 如果可以，则通过
        3. 否则重新设计问题和答案
        4. 若难以设计则抛弃

        Args:
            questions: 待过滤的问题列表

        Returns:
            过滤和优化后的问题列表
        """
        import concurrent.futures

        print(f"\n{'=' * 80}")
        print(f"[Filter & Refine] 开始并行过滤和优化 {len(questions)} 个问题...")
        print(f"{'=' * 80}")

        # 用于存储结果的字典（保持顺序）
        results_dict = {}

        def process_single_question(idx: int, question: Dict[str, Any]) -> Tuple[int, Dict[str, Any], bool]:
            """
            处理单个问题的过滤和优化

            Args:
                idx: 问题索引
                question: 问题对象

            Returns:
                (索引, 优化后的问题或 None, 是否保留)
            """
            try:
                print(f"\n[Filter Thread {idx + 1}/{len(questions)}] 开始处理问题...")

                # 过滤 evidence 中时间晚于 ask_time 的数据项
                filtered_evidence = self._filter_evidence_by_ask_time(question)
                question['evidence'] = filtered_evidence

                # 构建评估 prompt
                eval_prompt = f"""
                作为 QA 质量评估专家，请仔细分析以下问答对的质量。

                **重要说明**：
                - 提供的 evidence 并非全量数据，只是部分相关事件
                - 只要 evidence 中有能够体现答案的事件即可，不需要考虑时序、潜在幻觉、不充分等问题
                - 不要因为 evidence 看起来不完整就判断为不合理

                【问题】
                {question.get('question', '')}

                【答案】
                {question.get('answer', '')}

                【ask_time】
                {question.get('ask_time', 'N/A')}

                【证据数据】
                {json.dumps(question.get('evidence', []), ensure_ascii=False, indent=2)}

                **评估任务**

                1. **答案合理性检查（核心）**
                   - 答案是否存在严重的不合理或明显错误？
                   - 答案是否与 evidence 中的信息有严重冲突？
                   - 注意：只要 evidence 中有能够支持答案的事件即可，不需要 evidence 完全覆盖答案的所有细节

                2. **问题合理性检查**
                   - 问题表述是否清晰、无歧义？
                   - 问题是否有实际意义？

                **决策规则**

                ### 情况 A：问题和答案基本合理
                - **判断标准**：
                  * 答案没有严重的不合理或明显错误
                  * evidence 中有能够体现答案的事件（即使不是全部）
                  * 问题表述清晰
                - **处理方式**：**通过**

                ### 情况 B：答案存在严重不合理
                - **判断标准**：
                  * 答案与 evidence 中的信息有严重冲突
                  * 答案包含明显的错误或荒谬的内容
                  * 但问题是合理的，只需要修正答案
                - **处理方式**：**重新设计答案**
                - **设计要求**：
                  * 新答案必须基于 evidence 中的信息
                  * 新答案应该合理、准确
                  * 保持原问题不变

                ### 情况 C：问题本身存在严重问题
                - **判断标准**：
                  * 问题表述不清、有歧义或无意义
                  * 问题与知识更新的主题完全无关
                - **处理方式**：**抛弃该问题**

                **输出格式**
                请以 JSON 格式返回评估结果：
                {{
                    "decision": "pass/redesign_answer/discard",
                    "analysis": "详细分析（包括答案合理性、问题合理性）",
                    "modified_answer": null,
                    "reason": "决策理由"
                }}

                **字段说明**：
                - `decision`: 决策类型
                  * `pass`: 问题和答案合理，可以通过
                  * `redesign_answer`: 需要重新设计答案（问题保持不变）
                  * `discard`: 问题本身有严重问题，直接抛弃
                - `modified_answer`: 在 `redesign_answer` 时必须填写新答案
                - **不允许重新设计问题**，只能重新设计答案或直接抛弃
                """

                # 调用 LLM 进行评估
                llm_result = llm_call_j(eval_prompt)
                print(f"[Filter Thread {idx + 1}] LLM 评估结果: {llm_result}")
                if self.is_print:
                    print(f"[Filter Thread {idx + 1}] LLM 评估输出:")
                    print(str(llm_result)[:300] + "..." if len(str(llm_result)) > 300 else str(llm_result))

                # 解析 LLM 结果
                if isinstance(llm_result, str):
                    start_idx = llm_result.find('{')
                    end_idx = llm_result.rfind('}') + 1
                    if start_idx != -1 and end_idx != -1:
                        llm_result = json.loads(llm_result[start_idx:end_idx])

                if not isinstance(llm_result, dict):
                    print(f"[Filter Thread {idx + 1}] LLM 返回格式错误，保留原问题")
                    return idx, question, True

                decision = llm_result.get('decision', 'pass')
                analysis = llm_result.get('analysis', '')
                reason = llm_result.get('reason', '')

                print(f"[Filter Thread {idx + 1}] 决策：{decision}")
                print(f"  理由：{reason[:100]}..." if len(reason) > 100 else f"  理由：{reason}")

                # 根据决策执行相应操作
                if decision == 'pass':
                    # 情况 A：通过
                    print(f"[Filter Thread {idx + 1}] ✓ 问题质量良好，通过")
                    return idx, question, True

                elif decision == 'redesign':
                    # 情况 B：重新设计
                    modified_question = llm_result.get('modified_question', '')
                    modified_answer = llm_result.get('modified_answer', '')

                    if modified_question and modified_answer:
                        # 验证新问题是否真的可以从 evidence 中推理出来
                        verification_prompt = f"""
                        请验证以下新问题是否可以从提供的 evidence 中推理出来。

                        【新问题】
                        {modified_question}

                        【新答案】
                        {modified_answer}

                        【证据数据】
                        {json.dumps(question.get('evidence', []), ensure_ascii=False, indent=2)}

                        **验证要求**
                        1. 新问题是否能从 evidence 中推理出来？
                        2. 新答案是否能完全从 evidence 中推理出来？
                        3. 是否存在幻觉或编造的信息？

                        请以 JSON 格式返回：
                        {{
                            "is_valid": true/false,
                            "reason": "验证理由"
                        }}
                        """

                        verify_result = llm_call_j(verification_prompt)

                        if isinstance(verify_result, str):
                            start_idx = verify_result.find('{')
                            end_idx = verify_result.rfind('}') + 1
                            if start_idx != -1 and end_idx != -1:
                                verify_result = json.loads(verify_result[start_idx:end_idx])

                        if isinstance(verify_result, dict) and verify_result.get('is_valid', False):
                            question['question'] = modified_question
                            question['answer'] = modified_answer
                            print(f"[Filter Thread {idx + 1}] ✓ 问题已重新设计并通过验证")
                            return idx, question, True
                        else:
                            print(f"[Filter Thread {idx + 1}] ✗ 重新设计的问题未通过验证，抛弃")
                            return idx, None, False
                    else:
                        print(f"[Filter Thread {idx + 1}] ✗ 需要重新设计但未提供新问题或答案，抛弃")
                        return idx, None, False

                elif decision == 'discard':
                    # 情况 C：直接抛弃
                    print(f"[Filter Thread {idx + 1}] ✗ 问题无法修复，抛弃")
                    return idx, None, False

                else:
                    print(f"[Filter Thread {idx + 1}] ⚠ 未知决策类型：{decision}，保留原问题")
                    return idx, question, True

            except Exception as e:
                print(f"[Filter Thread {idx + 1}] 处理异常：{e}，保留原问题")
                return idx, question, True

        # 使用 ThreadPoolExecutor 并行处理，最多 20 个线程
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [
                executor.submit(process_single_question, idx, question)
                for idx, question in enumerate(questions)
            ]

            # 收集结果
            completed = 0
            for future in concurrent.futures.as_completed(futures):
                try:
                    idx, result, should_keep = future.result()
                    if should_keep and result is not None:
                        results_dict[idx] = result
                    completed += 1
                    if completed % 10 == 0 or completed == len(futures):
                        print(f"\n[Filter & Refine] 已完成 {completed}/{len(futures)} 个问题")
                except Exception as e:
                    print(f"[Filter & Refine] 结果收集异常：{e}")

        # 按索引顺序构建结果列表
        filtered_questions = [results_dict[i] for i in range(len(questions)) if i in results_dict]

        print(f"\n{'=' * 80}")
        print(f"[Filter & Refine] 过滤完成")
        print(f"  - 原始问题数：{len(questions)}")
        print(f"  - 保留问题数：{len(filtered_questions)}")
        print(f"  - 抛弃问题数：{len(questions) - len(filtered_questions)}")
        print(f"{'=' * 80}")

        return filtered_questions

    def _filter_evidence_by_ask_time(self, question: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        过滤 question 中 evidence 里时间晚于 ask_time 的数据项

        Args:
            question: 问题对象，包含 evidence 和 ask_time

        Returns:
            过滤后的证据列表
        """
        ask_time_str = question.get('ask_time', '')
        if not ask_time_str:
            return question.get('evidence', [])

        # 解析 ask_time（兼容 YYYY-MM-DD 和 YYYY-MM 格式）
        try:
            if ask_time_str.count('-') == 2:
                ask_dt = datetime.strptime(ask_time_str, "%Y-%m-%d")
            else:
                ask_dt = datetime.strptime(ask_time_str, "%Y-%m-%d")  # 视为该月最后一天
        except ValueError:
            return question.get('evidence', [])

        evidence = question.get('evidence', [])
        filtered = []
        for item in evidence:
            if not isinstance(item, dict):
                continue
            data = item.get('data', {})
            if not isinstance(data, dict):
                filtered.append(item)
                continue
            # 取 datetime 字段判断时间
            dt_str = data.get('datetime', '')
            if not dt_str:
                filtered.append(item)
                continue
            try:
                # datetime 格式：YYYY-MM-DD HH:MM:SS 或 YYYY-MM-DD
                dt_parts = dt_str.split(' ')
                if len(dt_parts) >= 2:
                    dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                else:
                    dt = datetime.strptime(dt_str, "%Y-%m-%d")
                if dt <= ask_dt:
                    filtered.append(item)
            except ValueError:
                # 无法解析时间则保留
                filtered.append(item)

        return filtered