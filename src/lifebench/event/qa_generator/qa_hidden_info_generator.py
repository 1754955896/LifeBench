# -*- coding: utf-8 -*-
"""
隐藏信息问题生成器：基于用户行为挖掘隐藏需求
工作流程：
1. 并行对每个月生成问题
2. 分析每月 daily_draft 数据，识别某日可能的隐藏需求
3. 调用 LLM 基于该日期及前后3天的 daily_event，润色需求并找到体现需求的事件
4. 设计隐藏信息问题（发掘用户未被明确提及但可推理出的需求）
"""
import os
import json
import random
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from .base_generator import BaseQAGenerator
from .phone_operation_generator import PhoneOperationGenerator
from src.lifebench.utils.llm_call import llm_call_j


class QAHiddenInfoGenerator(BaseQAGenerator):
    def __init__(self, daily_event: List[Dict], event_tree: List[Dict],
                 draft_event: Dict[str, List], phonedata: Dict[str, List],
                 phone_data_dir: str = None, is_print: bool = True,
                 persona_data: Dict = None, year: int = 2025):
        """
        初始化隐藏信息 QA 生成器

        Args:
            daily_event: daily_event 数据列表
            event_tree: event_tree 数据列表
            draft_event: draft_event 数据字典（按月份组织）
            phonedata: 手机操作数据字典
            phone_data_dir: 手机数据目录路径
            is_print: 是否打印调试信息
            persona_data: 用户画像数据
            year: 年份，默认 2025
        """
        super().__init__()
        self.daily_event = daily_event
        self.event_tree = event_tree
        self.draft_event = draft_event
        self.phonedata = phonedata
        self.phone_data_dir = phone_data_dir
        self.is_print = is_print
        self.year = year
        self.persona_data = persona_data
        self.phone_op_generator = PhoneOperationGenerator(persona_data=persona_data or {})
    
    def QAGen(self, **kwargs) -> List[Dict]:
        """
        实现基类抽象方法，作为外部调用的统一入口
        """
        return self.generate_questions()
    
    def generate_questions(self) -> List[Dict]:
        """
        生成隐藏信息问题，并行处理每个月
        
        Returns:
            生成的 QA 列表
        """
        if self.is_print:
            print("\n[HiddenInfoGen] 开始生成隐藏信息问题...")
        
        all_questions = []
        months = list(self.draft_event.keys())
      
        if self.is_print:
            print(f"  - 共 {len(months)} 个月份需要处理")
        
        # 并行处理每个月
        with ThreadPoolExecutor(max_workers=20) as executor:
            future_to_month = {}
            for month in months:
                future = executor.submit(
                    self._generate_questions_for_month,
                    month
                )
                future_to_month[future] = month
            
            # 收集结果
            for future in as_completed(future_to_month):
                month = future_to_month[future]
                try:
                    questions = future.result()
                    if questions:
                        all_questions.extend(questions)
                        if self.is_print:
                            print(f"  ✓ {month}: 生成 {len(questions)} 个问题")
                except Exception as e:
                    if self.is_print:
                        print(f"  ✗ {month}: 处理失败 - {e}")
        
        if self.is_print:
            print(f"[HiddenInfoGen] ✓ 完成，共生成 {len(all_questions)} 个隐藏信息问题")

        # Step 6: 验证问题的可回答性和答案合理性（20线程并行）
        if self.is_print:
            print("\n[HiddenInfoGen] 开始验证问题的可回答性和答案合理性...")

        from src.lifebench.utils.llm_call import llm_call_j

        def validate_single_qa(idx: int, qa: Dict) -> tuple:
            """验证单个 QA 对的可回答性和答案合理性"""
            try:
                question_text = qa.get('question', '')
                answer_text = qa.get('answer', '')
                evidence_list = qa.get('evidence', [])
                score_points = qa.get('score_points', [])

                validate_prompt = f"""
作为问答质量审核员，请严格按以下步骤验证问题。

【问题】
{question_text}

【答案】
{answer_text}

【评分点】
{json.dumps(score_points, ensure_ascii=False, indent=2)}

【证据列表】（共 {len(evidence_list)} 条）
{json.dumps(evidence_list, ensure_ascii=False, indent=2)}

【验证步骤】

**第一步：问题可回答性分析**

分析基于现有证据能否回答该问题：
- 问题询问的信息是否在证据覆盖的时间范围内？
- 证据是否提供了足够的关键信息来推断答案？
- 问题是否超出了证据所能回答的范围？

如果问题完全不可回答（如证据时间范围与问题不符、缺少关键信息），直接输出：
{{"result": "discard", "pass": false, "reason": "问题不可回答的具体原因"}}

**第二步：答案合理性分析**

在确认问题可回答后，逐条检查答案中的每个关键信息：
- 答案中的每个细节（时间、地点、人物、状态、事件等）是否在证据中有对应？
- 答案是否有证据中不存在的细节？

**第三步：综合判断**

根据以下规则输出最终结果：

【情况1 - 通过】问题和答案均合理，答案与证据完全对应
- 输出：{{"result": "pass", "pass": true, "reason": "通过理由"}}

【情况2 - 修改】答案有少量细节需要修正，但核心正确
- 输出：{{"result": "modify", "pass": true, "modified_answer": "修正后的答案", "reason": "需要修改的细节及原因"}}

【情况3 - 放弃】答案与证据矛盾，或关键信息缺失无法修复
- 输出：{{"result": "discard", "pass": false, "reason": "放弃原因"}}

**输出格式**
请以 JSON 格式返回：
{{
    "result": "pass/modify/discard",
    "pass": true/false,
    "modified_answer": "修正后的答案（仅情况2填写）",
    "reason": "判断理由",
    "answer_check": {{
        "supported": ["证据支持的细节"],
        "unsupported_or_contradict": ["证据不支持或矛盾的内容"]
    }}
}}
"""
                llm_result = llm_call_j(validate_prompt)

                if isinstance(llm_result, str):
                    start_idx = llm_result.find('{')
                    end_idx = llm_result.rfind('}') + 1
                    if start_idx != -1 and end_idx != -1:
                        llm_result = json.loads(llm_result[start_idx:end_idx])

                if isinstance(llm_result, dict):
                    result_type = llm_result.get('result', 'pass')
                    reason = llm_result.get('reason', '')
                    answer_check = llm_result.get('answer_check', {})

                    if result_type == 'pass':
                        is_pass = True
                        qa['_validation'] = {
                            'result': 'pass',
                            'pass': True,
                            'reason': reason,
                            'answer_check': answer_check
                        }
                        status = "✓ 通过"
                    elif result_type == 'modify':
                        is_pass = True
                        modified_answer = llm_result.get('modified_answer', '')
                        if modified_answer:
                            qa['answer'] = modified_answer
                        qa['_validation'] = {
                            'result': 'modify',
                            'pass': True,
                            'modified_answer': modified_answer,
                            'reason': reason,
                            'answer_check': answer_check
                        }
                        status = "✓ 修改后通过"
                    else:  # discard
                        is_pass = False
                        qa['_validation'] = {
                            'result': 'discard',
                            'pass': False,
                            'reason': reason,
                            'answer_check': answer_check
                        }
                        status = "✗ 抛弃"

                    print(f"[HiddenInfoGen] 问题 {idx + 1}: {status}")
                    print(f"    理由: {reason}")
                    unsupported = answer_check.get('unsupported_or_contradict', [])
                    if unsupported:
                        print(f"    证据不支持的内容: {unsupported}")

                    return idx, qa, is_pass
                else:
                    return idx, qa, True

            except Exception as e:
                print(f"[HiddenInfoGen] 问题 {idx + 1} 验证失败：{e}")
                qa['_validation'] = {'pass': True, 'reason': f'验证异常: {e}'}
                return idx, qa, True

        # 20线程并行验证
        validation_results = [None] * len(all_questions)
        pass_count = 0
        abandon_count = 0

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [
                executor.submit(validate_single_qa, idx, qa)
                for idx, qa in enumerate(all_questions)
            ]

            for future in as_completed(futures):
                try:
                    idx, qa, is_pass = future.result()
                    validation_results[idx] = qa
                    if is_pass:
                        pass_count += 1
                    else:
                        abandon_count += 1
                except Exception as e:
                    print(f"[HiddenInfoGen] 结果收集失败：{e}")

        # 过滤掉未通过验证的问题
        filtered_questions = [r for r in validation_results if r is not None and r.get('_validation', {}).get('pass', True)]

        if self.is_print:
            print(f"\n[HiddenInfoGen] ✓ 验证完成")
            print(f"    通过: {pass_count} 个")
            print(f"    抛弃: {abandon_count} 个")
            print(f"    最终有效问题: {len(filtered_questions)} 个")

        all_questions = filtered_questions

        return all_questions

    def _convert_to_qa_format(self, questions: List[Dict]) -> List[Dict]:
        """
        将选择题格式转换为问答题格式（使用 LLM 并行重写）

        将 options 和 correct_answer 转换为：
        - question: 改写为问答题格式
        - answer: correct_answer（字母如 "C"）
        - score_points: 评分点
        """
        # 找出需要转换的问题
        questions_to_convert = []
        questions_to_keep = []
        for qa in questions:
            if 'options' in qa and 'correct_answer' in qa:
                questions_to_convert.append(qa)
            else:
                questions_to_keep.append(qa)

        if not questions_to_convert:
            print(f"[HiddenInfoGen] 无需转换的问题")
            return questions

        print(f"[HiddenInfoGen] 需要使用 LLM 重写 {len(questions_to_convert)} 个选择题为问答题")

        # 使用 ThreadPoolExecutor 并行重写
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def rewrite_single_qa(qa: Dict) -> Dict:
            """使用 LLM 将选择题重写为问答题"""
            options = qa.get('options', [])
            correct_answer = qa.get('correct_answer', '')

            prompt = f"""请将以下选择题改写为问答题格式。

【原始选择题】
问题：{qa.get('question', '')}
选项：
{json.dumps(options, ensure_ascii=False, indent=2)}
正确答案：{correct_answer}

【要求】
1. 将选择题改写为自然流畅的问答题
2. 将选项内容融入到问题中（不要只保留字母）
3. 保持问题的意图和意义不变
4. 问题应该像用户在询问一个真实的问题

请以 JSON 格式返回：
{{
    "question": "改写后的问题（选项内容融入问题中）",
    "answer": "对应的选项内容",
    "score_points": [{{"description": "准确回答出答案", "score": 10}}]
}}
"""
            try:
                result = llm_call_j(prompt)
                if isinstance(result, str):
                    start_idx = result.find('{')
                    end_idx = result.rfind('}') + 1
                    if start_idx != -1 and end_idx != -1:
                        result = json.loads(result[start_idx:end_idx])

                if isinstance(result, dict) and 'question' in result:
                    # 复制其他字段
                    new_qa = dict(qa)
                    new_qa.pop('options', None)
                    new_qa.pop('correct_answer', None)
                    new_qa['question'] = result['question']
                    new_qa['answer'] = result.get('answer', correct_answer)
                    new_qa['score_points'] = result.get('score_points', [{"description": "准确回答出答案", "score": 10}])
                    print(f"[HiddenInfoGen] ✓ 成功重写问题")
                    return new_qa
            except Exception as e:
                print(f"[HiddenInfoGen] 重写失败: {e}")

            # 失败时使用规则重写方式
            options_text = '\n' + '\n'.join(options) if isinstance(options, list) else str(options)
            new_qa = dict(qa)
            new_qa.pop('options', None)
            new_qa.pop('correct_answer', None)
            new_qa['question'] = new_qa.get('question', '') + options_text
            new_qa['answer'] = correct_answer
            new_qa['score_points'] = [{"description": "准确回答出答案", "score": 10}]
            return new_qa

        # 并行重写
        rewritten_questions = [None] * len(questions_to_convert)
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = {
                executor.submit(rewrite_single_qa, qa): i
                for i, qa in enumerate(questions_to_convert)
            }
            for future in as_completed(futures):
                i = futures[future]
                try:
                    rewritten_questions[i] = future.result()
                except Exception as e:
                    print(f"[HiddenInfoGen] 重写任务异常: {e}")
                    rewritten_questions[i] = questions_to_convert[i]

        print(f"[HiddenInfoGen] ✓ 格式转换完成: {len(rewritten_questions)} 个问题已使用 LLM 重写")

        return questions_to_keep + rewritten_questions
    
    def _generate_questions_for_month(self, month: str, k: int = 7) -> List[Dict]:
        """
        为单月生成隐藏信息问题

        Args:
            month: 月份字符串，格式 YYYY-MM
            k: 最终选取的节点数量上限，默认为5

        Returns:
            该月生成的 QA 列表
        """
        print(f"[HiddenInfoGen] 开始处理月份 {month}")
        month_data = self.draft_event.get(month, [])
        print(f"  - 月份 {month}: 共 {len(month_data)} 条数据")
        if not month_data or not isinstance(month_data, list):
            return []

        # Step 1: 分析整月的异常状态/节点
        print(f"  - 开始分析异常状态节点...")
        unusual_states = self._analyze_unusual_states_for_month(month, month_data)

        if not unusual_states:
            print(f"  ⚠️ 未发现异常状态节点，返回空列表")
            return []

        print(f"  - 共 {len(unusual_states)} 个异常状态节点")

        # Step 2: 对每个节点进行影响分析
        for state in unusual_states:
            self._analyze_node_impact(state, month_data)

        # Step 2.5: 对节点进行质量排序，选取最佳节点
        print(f"  - 开始对节点进行质量排序...")
        ranked_states = self._rank_and_select_nodes(unusual_states, k=k)
        print(f"  - 选取了 {len(ranked_states)} 个高质量节点")

        # Step 2.6: 为每个节点收集对应的 daily_event
        for node in ranked_states:
            self._collect_evidence_for_node(node)

        print(ranked_states)

        # Step 3: 基于异常状态节点直接生成问题
        questions = self._design_questions_for_all_nodes(ranked_states, month)

        # Step 4: 为每个问题补充 evidence 字段（手机数据）
        for qa in questions:
            required_events_id = qa.get("required_events_id", [])
            if required_events_id:
                evidence_data = self._get_phone_evidence_by_event_ids(required_events_id)
                qa["evidence"] = evidence_data
            else:
                qa["evidence"] = []
            qa['ask_time'] = f'{self.year}-12-31'
        return questions
    
    def _analyze_unusual_states_for_month(self, month: str, month_data: List[Dict]) -> List[Dict]:
        """
        分析整月的异常状态区间和状态变化节点

        Args:
            month: 月份字符串
            month_data: 该月的所有数据

        Returns:
            异常状态列表，每项包含：state（状态描述）、state_analysis（状态分析）、start_date、end_date
        """
        # 准备用户画像数据（去掉relation字段）
        persona_info = {}
        if self.persona_data:
            persona_info = {k: v for k, v in self.persona_data.items() if k != 'relation'}
        persona_text = json.dumps(persona_info, ensure_ascii=False, indent=2) if persona_info else "无用户画像数据"

        prompt = f"""
        你是一位用户行为分析师。请分析以下用户在 {month} 的整体活动数据，找出与用户正常状态不同的**异常状态区间**或**状态变化节点**。

        【用户画像】（用于判断什么是"异常"状态）
        {persona_text}

        【重要概念】
        异常状态是指：
        - 用户在特定时间段内表现出的、与平时不同的行为模式或状态
        - 用户对自己施加的临时性规则、约束或限制（如"这周不吃辣"、"每天必须走10000步"）
        - 物理位置发生变化的时间段（如出差、返乡、旅游等不在常居地的时期）
        - 生活节奏或习惯的显著改变（如某段时间突然开始运动、某段时间情绪低落）
        - 用户主动制定的计划或承诺（如"每周三去陶艺"、"素食日打卡"）

        【月度活动数据】
        {json.dumps(month_data, ensure_ascii=False, indent=2)}

        【任务要求】
        请分析用户的行为模式，识别所有符合"异常状态"定义的时间段或节点，不要限制数量。

        **节点类型**（必须标注，每项都要有 node_type 字段）：
        - "rule_constraint"：规则约束（用户对自己施加的临时性规则、限制、承诺）
        - "position_change"：位置变化（出差、旅游、返乡等离开常居地）
        - "special_event"：特殊事件（导致生活习惯、状态在一定时间内发生改变的事件）
        - "profile_change"：画像变化（个人信息变化，如薪资、住址、职业、工作地、信仰、人物关系等）

        **分析维度**：
        1. **规则约束**：用户是否在某段时间给自己制定了规则、限制、承诺？
        2. **位置变化**：用户是否在某段时间离开常居地（出差、旅游、返乡等）？
        3. **特殊事件**：是否有特殊事件导致生活习惯或状态在一定时间内发生改变？
        4. **画像变化**：用户的个人信息是否有显著变化，如：
           - 薪资/收入变化（获得奖金、加薪、投资收益/亏损等）
           - 住址变化（搬家、装修、租房/退租等）
           - 职业/工作变化（晋升、调岗、离职、开始新项目等）
           - 工作地变化（办公室搬迁、远程办公、出差常驻等）
           - 信仰/价值观变化（开始/停止某种信仰、观念转变等）
           - 人物关系变化（新认识重要朋友、朋友离职/搬家/去世、恋人关系进展、社交圈变化等）

        **筛选标准**：
        - 状态必须是可观测的、有行为证据支持的
        - 状态应该有一定的持续时间（至少1天以上）
        - 优先识别持续多天或反复出现的状态
        - 状态应该是"异常"的，即与用户的一般模式不同

        **输出格式**：
        请以 JSON 数组格式返回：
        [
            {{
                "node_type": "rule_constraint/position_change/special_event/profile_change",
                "state": "状态描述（如：这周开始严格执行素食日/出差去北京期间/这段时间每天晨跑5公里）",
                "state_analysis": "状态分析（说明这个状态的特点、原因或影响）",
                "start_date": "YYYY-MM-DD",
                "end_date": "YYYY-MM-DD"
            }}
        ]

        **示例**：
        [
            {{
                "node_type": "special_event",
                "state": "出差去北京期间，生活节奏被打乱，运动中断",
                "state_analysis": "因工作出差前往北京，期间无暇晨跑和打球，日常运动量大幅减少",
                "start_date": "2025-01-15",
                "end_date": "2025-01-20"
            }},
            {{
                "node_type": "rule_constraint",
                "state": "严格执行素食日计划，并记录身体变化",
                "state_analysis": "用户主动开始素食实验，每天在日记中记录体重和身体感受，持续执行了一周",
                "start_date": "2025-01-10",
                "end_date": "2025-01-17"
            }}
        ]

        如果没有发现明显的异常状态，返回空数组 []。
        """

        try:
            res = llm_call_j(prompt)
            print(f"  - LLM 分析异常状态: {res}")
            if isinstance(res, str):
                res = json.loads(res)

            # 兼容不同的返回格式
            if isinstance(res, list):
                return res
            elif isinstance(res, dict):
                states = res.get("states") or res.get("data") or res.get("abnormal_states") or []
                if isinstance(states, list):
                    return states

            return []

        except Exception as e:
            if self.is_print:
                print(f"  ⚠️ 分析异常状态失败 ({month}): {e}")
            return []

    def _analyze_node_impact(self, node: Dict, month_data: List[Dict]):
        """
        对单个异常状态节点进行影响分析：
        - 输入当月的 daily_draft 和一个不寻常节点
        - 推理分析这个不寻常节点的时间具体有什么不寻常
        - 有哪些事情会因为这个不寻常的改变在哪段时间不能做
        - 或者有哪些事件在没发生不寻常事件之前不能做
        - 或哪些事件在发生不寻常事件之后不能做了

        Args:
            node: 异常状态节点（包含 start_date, end_date, state, state_analysis, node_type）
            month_data: 该月的所有数据
        """
        start_date = node.get("start_date", "")
        end_date = node.get("end_date", "")
        state = node.get("state", "")
        state_analysis = node.get("state_analysis", "")

        prompt = f"""
        你是一位用户行为分析师。请分析以下异常状态节点对用户生活的影响。

        【异常状态节点信息】
        - 节点类型: {node.get('node_type', 'N/A')}
        - 状态描述: {state}
        - 状态分析: {state_analysis}
        - 开始日期: {start_date}
        - 结束日期: {end_date}

        【该月活动数据】
        {json.dumps(month_data, ensure_ascii=False, indent=2)}

        【任务要求】
        请从以下角度分析该异常状态节点的影响：

        1. **该时间段的不寻常之处**：这个节点期间，用户的行为/状态有哪些与平时不同？

        2. **因该节点而不能做的事**：由于这个事件的发生，在 {start_date} 到 {end_date} 这段时间内，用户有哪些原本可以做的事情不能做了？

        3. **在该节点之前不能做的事**：在没有发生这个事件之前，用户有哪些事情是不能做/没条件做的？

        4. **在该节点之后不能做的事**：发生这个事件之后，用户有哪些事情就不能做了？

        **输出格式**：
        请以 JSON 格式返回：
        {{
            "unusual_points": ["该时间段的不寻常之处1", "该时间段的不寻常之处2", ...],
            "cannot_do_during": ["因该节点而不能做的事1", "因该节点而不能做的事2", ...],
            "cannot_do_before": ["在该节点之前不能做的事1", "在该节点之前不能做的事2", ...],
            "cannot_do_after": ["在该节点之后不能做的事1", "在该节点之后不能做的事2", ...]
        }}

        如果某个类别没有相关内容，返回空数组 []。
        """

        try:
            res = llm_call_j(prompt)
            print(f"  - LLM 分析节点影响: {res}")
            if isinstance(res, str):
                res = json.loads(res)

            if isinstance(res, dict):
                node["impact_analysis"] = {
                    "unusual_points": res.get("unusual_points", []),
                    "cannot_do_during": res.get("cannot_do_during", []),
                    "cannot_do_before": res.get("cannot_do_before", []),
                    "cannot_do_after": res.get("cannot_do_after", [])
                }
            else:
                node["impact_analysis"] = {
                    "unusual_points": [],
                    "cannot_do_during": [],
                    "cannot_do_before": [],
                    "cannot_do_after": []
                }

        except Exception as e:
            if self.is_print:
                print(f"  ⚠️ 分析节点影响失败: {e}")
            node["impact_analysis"] = {
                "unusual_points": [],
                "cannot_do_during": [],
                "cannot_do_before": [],
                "cannot_do_after": []
            }

        # Step 2: 再次调用 LLM，对影响分析结果进行提炼
        self._refine_node_impact(node, month_data)

    def _refine_node_impact(self, node: Dict, month_data: List[Dict]):
        """
        对节点影响分析结果进行二次提炼

        从第一次分析的结果中，选取最明确、最有关联性、最能基于节点状态
        推断出的"不能做的事情"，关注最能确定、最容易观察到的内容。

        Args:
            node: 异常状态节点（已包含 impact_analysis）
            month_data: 该月的所有数据
        """
        impact = node.get("impact_analysis", {})
        state = node.get("state", "")
        state_analysis = node.get("state_analysis", "")
        node_type = node.get("node_type", "")
        start_date = node.get("start_date", "")
        end_date = node.get("end_date", "")

        # 准备第一次分析的结果
        initial_analysis = {
            "unusual_points": impact.get("unusual_points", []),
            "cannot_do_during": impact.get("cannot_do_during", []),
            "cannot_do_before": impact.get("cannot_do_before", []),
            "cannot_do_after": impact.get("cannot_do_after", [])
        }

        prompt = f"""
        请以 JSON 格式输出分析结果。你是一位用户行为分析专家。请分析以下异常状态节点，推理其背后的隐藏信息，并基于这些隐藏信息设计用户"不能做"的事情。

        【节点基本信息】
        - 节点类型: {node_type}
        - 状态描述: {state}
        - 状态分析: {state_analysis}
        - 时间范围: {start_date} ~ {end_date}

        【第一次 LLM 分析的初步结果】（仅供参考，不要直接采用）
        {json.dumps(initial_analysis, ensure_ascii=False, indent=2)}

        【分析流程】（三步法）
        1. **提取隐藏信息**：从节点事件中提取导致用户变化的隐含信息（分为两种，变化后产生的约束，和变化前不满足的条件）
           - 地点变化：如"不在武汉（约束，之后一段时间不在武汉，不能处理武汉事务）"、"在省人民医院培训（约束，培训期间不能在市中心医院接诊）"
           - 数值变化：如"薪资提升50%（条件，之前不满足月收入足够的条件）"、"月供能力变化"
           - 事实变化：如"之前不认识林婉清（条件，之前不满足认识她的条件）"、"开始独立带组（约束，之后一段时间内要负责独立带组）（同时也有条件，之前不能独立带组）"

        2. **确定不能做的事情**：基于隐藏信息，确定用户不能实现的某类事情
           - 例如：培训期间不能正常接诊、薪资提升前不能买更贵的房子

        3. **设计具体情景**：用具体的情景/事件来体现这个"不能做"
           - 情景可以是合理设计的，不必拘泥于原数据
           - 情景应该是用户自己能明显感知到的限制

        **情景设计示例**：

        | 节点类型 | 隐藏信息 | 不能做的事 | 情景设计 |
        |---------|---------|-----------|---------|
        | 位置变化 | 不在武汉 | 处理家中事务 | 在长沙旅游时，不能及时回家处理漏水事故 |
        | 数值变化 | 薪资1万→1.5万 | 购买高月供房子 | 假设最多用50%收入还贷，则不能买月供7000的房子 |
        | 事实变化 | 之前不认识林婉清 | 和她交流 | 在认识她之前，不能和她一起听歌、交流心事 |

        **阶段标注要求**：
        - 每个 cannot_do 必须标注"之前"、"过程中"或"之后"
        - 之前：该节点发生前，由于缺少某个条件而不能做
        - 过程中：该节点持续期间，因隐含状态而不能做
        - 之后：该节点发生后，因状态改变而不能做

        **好的情景 vs 不好的情景**：

        ✓ 好的情景（直接、具体、有因果关系）：
        - "去省人民医院全天候上课则不能在市中心医院接诊老患者"
        - "假设最多支持收入50%还房贷则不能购买月供7000的房屋"
        - "在洛阳老家则不能在郑州常去的健身房锻炼"

        ✗ 不好的情景（模糊、泛泛、缺少因果）：
        - "用户可能感到孤独，想念家人"（情绪推断，不具体）
        - "培训期间用户可能有压力"（泛泛而谈，无关推断）
        - "结识新朋友后需要维护关系"（表面总结，非不能做）

        **输出格式**：
        {{
            "hidden_info": "该状态的隐藏信息描述",
            "reason": "推理过程说明，解释隐藏信息和 cannot_do 的逻辑关联",
            "cannot_do": [
                {{
                    "constraint": "基于隐藏信息，不能做的事情（简洁描述）",
                    "phase": "之前/过程中/之后",
                    "scenario": "具体的情景/事件（如：假设最多支持收入50%还房贷则不能购买月供7000的房屋）"
                }}
            ]
        }}

        **重要约束**：
        - hidden_info：深层解读，而非表面描述
        - cannot_do：最多返回2个，必须有 phase 和 scenario
        - scenario：具体可落地，体现直接因果关系
        - **第一次分析结果仅供参考**，不直接采用
        - 优先选择直接、直观、因果明确的推断
        """

        try:
            res = llm_call_j(prompt)
            print(f"  - LLM 提炼节点影响: {res}")
            if isinstance(res, str):
                res = json.loads(res)

            if isinstance(res, dict):
                node["impact_analysis"] = {
                    "hidden_info": res.get("hidden_info", ""),
                    "reason": res.get("reason", ""),
                    "cannot_do": res.get("cannot_do", [])
                }
            else:
                node["impact_analysis"] = {
                    "hidden_info": "",
                    "reason": "",
                    "cannot_do": []
                }

        except Exception as e:
            if self.is_print:
                print(f"  ⚠️ 提炼节点影响失败: {e}")
            node["impact_analysis"] = {
                "hidden_info": "",
                "reason": "",
                "cannot_do": []
            }

        # Step 3: 为每个 cannot_do 约束分配具体的时间范围
        self._assign_constraint_time_ranges(node, month_data)

    def _assign_constraint_time_ranges(self, node: Dict, month_data: List[Dict]):
        """
        为每个 cannot_do 约束分配具体的时间范围

        输入当月的 daily_draft 数据，为每个约束分配限制的时间段，
        包含起始时间、结束时间、跨度（1天到1个月）

        Args:
            node: 异常状态节点（已包含 impact_analysis）
            month_data: 该月的所有数据
        """
        impact = node.get("impact_analysis", {})
        cannot_do = impact.get("cannot_do", [])
        state = node.get("state", "")
        node_type = node.get("node_type", "")
        start_date = node.get("start_date", "")
        end_date = node.get("end_date", "")

        if not cannot_do:
            return

        prompt = f"""
        你是一位用户行为分析专家。请根据当月的活动数据，为以下约束分配具体的时间范围。

        【节点基本信息】
        - 节点类型: {node_type}
        - 状态描述: {state}
        - 节点时间范围: {start_date} ~ {end_date}
        - 隐藏信息: {impact.get("hidden_info", "")}

        【约束项】
        {json.dumps(cannot_do, ensure_ascii=False, indent=2)}

        【当月活动数据】
        {json.dumps(month_data, ensure_ascii=False, indent=2)}

        【任务要求】
        请分析当月活动数据，为每个约束选取**不与约束冲突**、**符合约束**、**受约束影响**的日期。

        **分析步骤**：
        1. **确定节点基础起止时间**：根据节点信息确认时间范围
        2. **确定约束阶段**：确认约束是"之前"、"过程中"还是"之后"
        3. **选取合适日期**：从当月活动中选取符合以下条件的日期：
           - 不与约束冲突（如约束说"不能晨跑"，则不选有晨跑数据的日期）
           - 符合约束的背景（如约束是培训期间，则选培训相关的日期）
           - 受约束影响（该日期的行为与约束有关联）

        **日期选取原则**：
        - 跨度可以任意选取：1天、2-3天、一周、多周均可
        - 可以从月中任意位置选取，不必完全匹配节点时间范围
        - 优先选取与约束情景最吻合的时间段

        **输出格式**：
        请以 JSON 格式返回：
        {{
            "constraint_time_ranges": [
                {{
                    "constraint": "约束描述（与输入一致）",
                    "phase": "之前/过程中/之后",
                    "start_date": "YYYY-MM-DD",
                    "end_date": "YYYY-MM-DD",
                    "duration_days": 天数
                }},
                ...
            ]
        }}

        **重要约束**：
        - start_date 和 end_date 必须精确到 YYYY-MM-DD 格式
        - duration_days 为自然数
        - 选取的日期必须与约束情景相符，不冲突
        """

        try:
            res = llm_call_j(prompt)
            print(f"  - LLM 分配约束时间范围: {res}")
            if isinstance(res, str):
                res = json.loads(res)

            if isinstance(res, dict):
                constraint_time_ranges = res.get("constraint_time_ranges", [])
                # 将时间范围信息合并到 cannot_do 中
                for i, item in enumerate(cannot_do):
                    if isinstance(item, dict) and i < len(constraint_time_ranges):
                        time_range = constraint_time_ranges[i]
                        item["start_date"] = time_range.get("start_date", "")
                        item["end_date"] = time_range.get("end_date", "")
                        item["duration_days"] = time_range.get("duration_days", 0)
                node["impact_analysis"]["cannot_do"] = cannot_do

        except Exception as e:
            if self.is_print:
                print(f"  ⚠️ 分配约束时间范围失败: {e}")

    def _rank_and_select_nodes(self, unusual_states: List[Dict], k: int = 5) -> List[Dict]:
        """
        对节点进行质量排序，选取最佳节点

        根据节点的隐藏信息质量、约束的明确性、情景的直观性等维度
        进行综合评估，选取前 k 个最优质的节点。

        Args:
            unusual_states: 异常状态节点列表
            k: 选取数量上限

        Returns:
            排序后的节点列表（按质量从高到低）
        """
        if not unusual_states:
            return []

        if len(unusual_states) <= k:
            print(f"  - 节点数量 {len(unusual_states)} <= {k}，全部保留")
            return unusual_states

        prompt = f"""
        请对以下节点进行质量评估和排序，选取最优质的前 {k} 个节点。

        【节点列表】
        {json.dumps(unusual_states, ensure_ascii=False, indent=2)}

        【评估维度】（每个维度 1-10 分）：
        1. **明确性**：隐藏信息是否清晰、具体、不模糊
        2. **直观性**：约束和情景是否直观、可理解
        3. **因果强度**：约束与隐藏信息是否有直接、强烈的因果关系
        4. **事实贴合度**：情景是否符合逻辑，与用户实际情况贴切
        5. **可落地性**：情景是否可以具体执行，还是泛泛的总结

        【排序原则】
        - 综合评分最高的排在前面
        - 优先选取：明确、直观、因果强、贴合事实的节点
        - 排除：模糊、泛泛、因果弱的节点

        【输出格式】
        请以 JSON 格式返回排序后的节点索引列表：
        {{
            "ranked_indices": [索引3, 索引1, 索引5, ...],
            "scores": [
                {{"index": 3, "total_score": 42, "明确性": 8, "直观性": 9, "因果强度": 8, "事实贴合度": 9, "可落地性": 8}},
                ...
            ]
        }}
        """

        try:
            res = llm_call_j(prompt)
            print(f"  - LLM 节点排序结果: {res}")
            if isinstance(res, str):
                res = json.loads(res)

            if isinstance(res, dict):
                ranked_indices = res.get("ranked_indices", [])
                if ranked_indices and len(ranked_indices) > 0:
                    # 根据索引排序
                    ranked_states = []
                    for idx in ranked_indices:
                        if 0 <= idx < len(unusual_states):
                            ranked_states.append(unusual_states[idx])
                    print(f"  - 选取了 {len(ranked_states)} 个高质量节点")
                    return ranked_states[:k]

            # 如果解析失败，使用默认排序
            print(f"  - LLM 排序解析失败，使用默认顺序")
            return unusual_states[:k]

        except Exception as e:
            if self.is_print:
                print(f"  ⚠️ 节点排序失败: {e}")
            return unusual_states[:k]

    def _collect_evidence_for_node(self, node: Dict):
        """
        为单个异常状态节点收集证据（调用LLM分析每日daily_event）

        遍历这段时间的每日的daily_event，调用LLM分析记录下所有能反映
        状态变化和隐藏信息和情景的daily_event的event id

        Args:
            node: 异常状态节点（包含 start_date, end_date, state, impact_analysis 等）
        """
        start_date = node.get("start_date", "")
        end_date = node.get("end_date", "")

        if not start_date or not end_date:
            node["evidence"] = []
            return

        # 生成该时间段内的所有日期
        from datetime import datetime, timedelta
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            node["evidence"] = []
            return

        date_range = []
        current = start
        while current <= end:
            date_range.append(current.strftime("%Y-%m-%d"))
            current += timedelta(days=1)

        # 收集这些日期对应的 daily_event
        daily_events_by_date = []
        for date in date_range:
            daily_events = self._get_events_for_single_date(date)
            if daily_events:
                daily_events_by_date.append({
                    "date": date,
                    "events": daily_events
                })

        if not daily_events_by_date:
            node["evidence"] = []
            print(f"  - 节点 {start_date} ~ {end_date}: 未收集到每日事件证据")
            return

        # 提取节点关键信息用于 LLM 分析
        node_state = node.get("state", "")
        state_analysis = node.get("state_analysis", "")
        hidden_info = node.get("impact_analysis", {}).get("hidden_info", "")
        cannot_do = node.get("impact_analysis", {}).get("cannot_do", [])

        # 构建 cannot_do 描述用于提示 LLM
        cannot_do_text = ""
        if cannot_do:
            for i, constraint in enumerate(cannot_do, 1):
                constraint_text = constraint.get("constraint", "")
                scenario = constraint.get("scenario", "")
                phase = constraint.get("phase", "")
                cannot_do_text += f"\n{i}. [{phase}] {constraint_text}\n   情景: {scenario}"

        # 调用 LLM 分析每天的 events，识别与该节点严格相关的 event_id
        prompt = f"""
请以 JSON 格式输出。你需要分析以下每日事件列表，只提取与该节点**严格相关**的事件。

【筛选标准，满足一项即可】
1. 体现出该节点关键的变化事件的事件（如体现晋升，地址变化，人物关系变化的具体事件）
2. 事件能体现该节点的隐藏信息（如晋升后的工资上调，出差后的地址变化，认识新人物的具体事件）
3. 事件能对应"不能做"情景的具体原因体现

【节点状态】
{node_state}

【状态分析】
{state_analysis}

【隐藏信息】
{hidden_info}

【日期范围】
{start_date} 至 {end_date}

【每日事件列表】
{json.dumps(daily_events_by_date, ensure_ascii=False, indent=2)}

【输出格式】
请以 JSON 对象格式返回：
{{
    "related_events": [
        {{
            "date": "事件日期",
            "event_id": "事件ID",
            "event_name": "事件名称",
            "reason": "为什么这个事件与该节点严格相关（必须具体说明）"
        }},
        ...
    ]
}}

【重要约束】
- 只返回 JSON 对象
- 不要使用 Markdown 代码块
- **只输出严格相关的事件**，如果某天所有事件都无关，则该天的 related_events 输出空数组（不要省略该字段）
- event_id 必须是字符串格式
- 宁缺毋滥：不相关的事件不要输出
"""

        try:
            res = llm_call_j(prompt)

            if isinstance(res, str):
                res = json.loads(res)

            if not isinstance(res, dict):
                node["evidence"] = daily_events_by_date
                print(f"  - 节点 {start_date} ~ {end_date}: LLM 返回格式错误，使用原始事件数据")
                return

            related_events = res.get("related_events", [])

            if not related_events:
                node["evidence"] = {
                    "date_range": {"start": start_date, "end": end_date},
                    "node_state": node_state,
                    "related_event_ids": [],
                    "related_events_detail": [],
                    "total_days": len(date_range),
                    "days_with_events": len(daily_events_by_date),
                    "abandon": True,
                    "abandon_reason": "未识别到任何相关事件"
                }
                print(f"  - 节点 {start_date} ~ {end_date}: 未识别到相关事件，标记为抛弃")
                return

            # Step 2: 第二次 LLM 过滤分析，只保留最相关的不超过10个事件
            print(f"  - 节点 {start_date} ~ {end_date}: 初步识别 {len(related_events)} 个相关事件，进行过滤分析...")

            # 获取相关事件的完整详情（包含 event 对象）
            related_events_with_detail = []
            for rel_event in related_events:
                rel_date = rel_event.get("date")
                rel_event_id = rel_event.get("event_id")
                # 从 daily_events_by_date 中找到完整的 event 对象
                for day_data in daily_events_by_date:
                    if day_data.get("date") == rel_date:
                        for evt in day_data.get("events", []):
                            if str(evt.get("event_id", "")) == str(rel_event_id):
                                rel_event["event_obj"] = evt
                                related_events_with_detail.append(rel_event)
                                break

            filter_prompt = f"""
请以 JSON 格式输出。你需要对以下初步识别的事件进行深度过滤分析，提取最相关的最多10个事件，并判断这些事件是否能有效反映节点的状态变化和约束。

【节点状态】
{node_state}

【状态分析】
{state_analysis}

【隐藏信息】
{hidden_info}

【初步识别的事件列表】
{json.dumps(related_events_with_detail, ensure_ascii=False, indent=2)}

【过滤分析任务】
1. **精选最相关事件**：从列表中选择最多10个最能反映以下内容的事件：
   - 核心状态变化的主要事件的关键节点
   - 直接体现隐藏信息的事件
   - 明确对应"不能做"的原因情景的事件

2. **评估事件能否反映状态和约束**：
   - 分析选中事件是否能够清晰反映出主要事件节点（如晋升，地址变化，人物关系变化的具体事件）
   - 分析选中事件是否能够体现隐藏信息（如晋升后的工资上调，出差后的地址变化，认识新人物的具体事件）
   - 分析选中事件是否能够对应"不能做"情景的具体原因

3. **判断标准**：
   - 如果有 >= 3 个事件能清晰关联状态变化/约束，则保留
   - 如果 < 3 个事件能清晰关联，则输出抛弃标志

【输出格式】
请以 JSON 对象格式返回：
{{
    "filtered_events": [
        {{
            "date": "事件日期",
            "event_id": "事件ID",
            "event_name": "事件名称",
            "reason": "为什么这个事件与该节点最相关",
            "reflects_state": true/false,
            "reflects_constraint": true/false
        }},
        ...
    ],
    "abandon": true/false,
    "abandon_reason": "如果 abandon 为 true，说明原因",
    "summary": "对这些事件的整体评估，说明为什么保留或抛弃"
}}

【重要约束】
- 只返回 JSON 对象
- 不要使用 Markdown 代码块
- filtered_events 最多 10 个
- 必须明确给出 abandon 字段（true 或 false）
"""

            try:
                filter_res = llm_call_j(filter_prompt)

                if isinstance(filter_res, str):
                    filter_res = json.loads(filter_res)

                if not isinstance(filter_res, dict):
                    # LLM 返回格式错误，使用初步分析结果
                    evidence = {
                        "date_range": {"start": start_date, "end": end_date},
                        "node_state": node_state,
                        "related_event_ids": [e.get("event_id") for e in related_events if e.get("event_id")],
                        "related_events_detail": related_events,
                        "total_days": len(date_range),
                        "days_with_events": len(daily_events_by_date),
                        "abandon": False
                    }
                    node["evidence"] = evidence
                    print(f"  - 节点 {start_date} ~ {end_date}: 过滤分析返回格式错误，使用初步结果")
                    return

                filtered_events = filter_res.get("filtered_events", [])
                abandon = filter_res.get("abandon", False)
                abandon_reason = filter_res.get("abandon_reason", "")
                summary = filter_res.get("summary", "")

                # 构建最终证据数据结构
                evidence = {
                    "date_range": {"start": start_date, "end": end_date},
                    "node_state": node_state,
                    "related_event_ids": [e.get("event_id") for e in filtered_events if e.get("event_id")],
                    "related_events_detail": filtered_events,
                    "total_days": len(date_range),
                    "days_with_events": len(daily_events_by_date),
                    "abandon": abandon,
                    "abandon_reason": abandon_reason if abandon else "",
                    "summary": summary,
                    "original_count": len(related_events),
                    "filtered_count": len(filtered_events)
                }

                node["evidence"] = evidence

                if abandon:
                    print(f"  - 节点 {start_date} ~ {end_date}: 标记为抛弃 - {abandon_reason}")
                else:
                    print(f"  - 节点 {start_date} ~ {end_date}: 过滤后保留 {len(filtered_events)} 个相关事件（原始 {len(related_events)} 个）")
                    if summary:
                        print(f"    评估: {summary}")

                    # Step 3: 检查并生成手机数据证据
                    print(f"  - 节点 {start_date} ~ {end_date}: 检查手机数据证据...")
                    phone_evidence = self._check_and_generate_phone_evidence(node, filtered_events)
                    evidence["phone_evidence"] = phone_evidence
                    node["evidence"] = evidence

            except Exception as e:
                if self.is_print:
                    print(f"  - 节点 {start_date} ~ {end_date}: 过滤分析失败: {e}")
                # 失败时使用初步结果，不抛弃
                evidence = {
                    "date_range": {"start": start_date, "end": end_date},
                    "node_state": node_state,
                    "related_event_ids": [e.get("event_id") for e in related_events if e.get("event_id")],
                    "related_events_detail": related_events,
                    "total_days": len(date_range),
                    "days_with_events": len(daily_events_by_date),
                    "abandon": False,
                    "error": str(e)
                }
                node["evidence"] = evidence

        except Exception as e:
            if self.is_print:
                print(f"  - 节点 {start_date} ~ {end_date}: LLM 分析失败: {e}")
            node["evidence"] = {"date_range": {"start": start_date, "end": end_date}, "error": str(e)}

    def _design_questions_for_all_nodes(self, unusual_states: List[Dict], month: str) -> List[Dict]:
        """
        基于异常状态节点生成问答题（每个节点单独调用LLM）

        问题需要挖掘隐藏信息才能回答，设计为询问在某段时间做某安排是否合适。
        如果不知道隐藏信息，问题看起来会是正常甚至有吸引力的安排。

        Args:
            unusual_states: 异常状态节点列表（已排序）
            month: 月份字符串

        Returns:
            生成的 QA 列表
        """
        if not unusual_states:
            return []

        print(f"\n  - 开始为 {len(unusual_states)} 个异常状态节点生成问题...")

        # 准备 persona 数据
        persona_info = {}
        if self.persona_data:
            persona_info = {k: v for k, v in self.persona_data.items() if k != 'relation'}
        persona_text = json.dumps(persona_info, ensure_ascii=False, indent=2) if persona_info else "无用户画像数据"

        questions = []

        for idx, node in enumerate(unusual_states, 1):
            # 跳过已被标记为抛弃的节点
            evidence = node.get("evidence", {})
            if evidence.get("abandon", False):
                abandon_reason = evidence.get("abandon_reason", "未说明原因")
                print(f"  - 节点 {idx}: 已标记为抛弃，跳过问题生成 - {abandon_reason}")
                continue

            print(f"  - 处理节点 {idx}/{len(unusual_states)}: {node.get('state', 'N/A')}")

            prompt = f"""
请以 JSON 格式输出。你是一位问答设计专家。请基于以下异常状态节点，为用户设计问答题。

【用户画像】
{persona_text}

【月份】
{month}

【异常状态节点】
{json.dumps(node, ensure_ascii=False, indent=2)}

**【问题设计指导——核心流程】**

**第一步：分析异常状态节点**
1. 仔细阅读节点的 hidden_info（隐藏信息）和 impact_analysis（影响分析）
2. 识别节点代表的**重要事件**以及该事件会引发的**变化和影响**
3. 分析这种变化带来的影响，然后设计两种约束1）因为这个变化所形成的约束，在变化之后不能做什么；2）因为这个变化所形成的条件，在变化发生之前，没法满足所以不能做什么；把条件/约束作为隐藏信息，设计针对变化前/后的不能做的事情的假设提问。

**第二步：基于隐藏信息设计问题**
1. 找到因为隐藏信息后，选择合适的时间段，分析**看似合理但实则不可行的事件安排**
2. 这个安排必须满足：
   - **表面合理性**：对不知道隐藏信息的人来说，这个安排看起来完全正常、甚至有吸引力
   - **隐藏约束性**：由于隐藏信息的约束/或条件未满足，实际上这个安排行不通

**第三步：设计问题题面（关键）**
1. **题面只描述"表面合理安排"，不要暴露任何隐藏信息的提示**
2. 避免在题面中出现：
   - 直接说明"因为xxx所以不行"的结构性提示
   - 过多的限定词暗示了答案（如明确的时间重叠暗示）
   - "是否合适"、"能不能"等直接揭示意图的问法
3. 题面应该是**自然的、随意的提议/询问语气**，让回答者自己去推理是否可行
4. 题面描述的安排应该让普通人觉得"这听起来没问题啊"
5. 题面应包含尽量少的信息，只保持可回答性的最小信息量，增加难度。

**第四步：设计答案**
1. 答案基于 hidden_info 揭示为什么不合适
2. 答案需要说明隐藏信息造成的具体约束
3. 答案应该让答题者理解：了解这些隐藏信息后，这个安排确实不可行

【问题设计原则】
1. **问题要体现安排/提议性质**：询问用户在某段时间做某个安排是否合适、怎么样
   - 示例："我在今年7月2日到7月14日去省人民医院参观学习怎么样？"
   - 示例："安排我去长沙玩几天怎么样？"
   - 示例："我计划在那段时间每天早起晨跑，这个安排怎么样？"

2. **答案要揭示隐藏信息**：说明为什么不合适/不可行
   - 答案应该基于节点的 hidden_info 和 constraint
   - 如果知道隐藏信息，就会理解为什么这个安排不合适

3. **问题要具有迷惑性**：对于不知道隐藏信息的人来说
   - 问题看起来应该是正常的、甚至是有吸引力的安排
   - 不应该直接暴露"不能做"的事实
   - 例如：询问培训期间去接诊老患者看起来是正常提议

4. **情景可以自己设计**：
   - 不必完全照搬【异常状态节点】中约束中的提供的情景示例，你可以自行推理选择更合适的受状态变化/人物变化影响而不能做的事情
   - 可以设计更迷惑性的、看似正常的安排
   - 让不知道隐藏信息的人觉得这是个好提议

5. **问题格式灵活**：
   - 不必严格遵循"我在xxx这段时间去XX怎么样"的格式
   - 可以是"xxx安排怎么样"、"计划在xxx做xx合适吗"等
   - 保持自然流畅的第一人称表达

6. **题面不能包含对隐藏信息的提示和冗余过多提示**（重要）：
   - 题面应该像普通用户随口提的一个建议/询问，不暴露任何推理线索
   - 避免在题面中出现"这段时间我在培训"、"我在吃药"等信息，因为这就是隐藏信息本身
   - 题面只说表面安排（如"我计划去接诊老患者"），不说背后原因（如"因为我在市中心医院工作"）

**好的问题示例**：（产生了去培训地点的约束）
- 节点：参加省级骨干医师培训（7月2日-14日）
  问题："我计划在7月2日到14日每天去市中心医院出门诊接诊老患者，这个安排怎么样？"
  答案："不合适，因为这段时间要去省人民医院参加全天候培训，无法在市中心医院接诊。"

- 节点：薪资1万→1.5万（之前不满足月收入条件）
  问题："我打算在看中的地段买个月供8000的房子，月收入1.5万能负担得起吗？"
  答案："不能，假设最多用50%收入还贷，则1.5万的月收入只能负担7500以下的月供。"

- 节点：结识新朋友林婉清（7月7日认识）（之前不满足认识她的条件）
  问题："7月初我想约林婉清一起去听古典音乐会，可惜还不认识她，有机会吗？"
  答案："不行，因为7月7日才认识她，7月初还不存在'约她'这个选项。"

【输出格式】
请以 JSON 对象格式返回：
{{
    "question": "问答题描述（包含时间段和安排）",
    "answer": "基于隐藏信息的回答（揭示为什么不合适）",
    "score_points": [
        {{"description": "能说出隐藏信息的核心要点", "score": 10}},
        {{"description": "能基于隐藏信息进行合理推断", "score": 5}}
    ]
}}

【重要约束】
- 只返回 JSON 对象
- 不要使用 Markdown 代码块
- question 包含具体时间段和安排
- answer 基于 hidden_info 说明为什么不合适
- **题面不能包含对隐藏信息的提示**，只描述表面合理安排
"""

            try:
                res = llm_call_j(prompt)

                if isinstance(res, str):
                    res = json.loads(res)

                if not isinstance(res, dict):
                    print(f"  ⚠️ 节点 {idx}: LLM 返回格式错误，期望对象")
                    continue

                # 从节点证据中提取 related_event_ids 作为 required_events_id
                node_evidence = node.get("evidence", {})
                required_event_ids = node_evidence.get("related_event_ids", []) if isinstance(node_evidence, dict) else []

                qa = {
                    "question": res.get("question", ""),
                    "answer": res.get("answer", ""),
                    "score_points": res.get("score_points", [{"description": "能基于隐藏信息回答", "score": 10}]),
                    "node_type": node.get("node_type", ""),
                    "state": node.get("state", ""),
                    "impact_analysis": node.get("impact_analysis", {}),
                    "required_events_id": required_event_ids,
                    "question_type": "Hidden_info"
                }

                if not qa["question"] or not qa["answer"]:
                    print(f"  ⚠️ 节点 {idx}: 问题或答案为空，跳过")
                    continue

                questions.append(qa)
                print(f"  ✓ 节点 {idx}: 成功生成问题")

            except Exception as e:
                if self.is_print:
                    print(f"  ⚠️ 节点 {idx}: 设计问题失败: {e}")
                continue

        print(f"  - 共生成 {len(questions)} 个问题")
        return questions

    def _check_and_generate_phone_evidence(self, node: Dict, filtered_events: List[Dict]) -> Dict:
        """
        检查并生成手机数据证据

        遍历最终选取的所有 daily_event，获取其对应的手机数据，
        分析关于该状态，主要事件的信息是否被手机数据体现。
        若没有，则生成该事件的相关手机数据。

        Args:
            node: 异常状态节点
            filtered_events: 过滤后保留的相关事件列表

        Returns:
            手机数据证据字典
        """
        node_state = node.get("state", "")
        hidden_info = node.get("impact_analysis", {}).get("hidden_info", "")
        cannot_do = node.get("impact_analysis", {}).get("cannot_do", [])

        # 获取所有相关事件ID和完整事件对象
        related_events_info = []
        for event in filtered_events:
            event_id = event.get("event_id")
            if not event_id:
                continue

            # 获取原始事件对象
            original_event = None
            for daily_event in self.daily_event:
                if str(daily_event.get("event_id", "")) == str(event_id):
                    original_event = daily_event
                    break

            if original_event:
                related_events_info.append({
                    "event_id": event_id,
                    "event_name": event.get("event_name", ""),
                    "date": event.get("date", ""),
                    "original_event": original_event
                })

        if not related_events_info:
            return {"has_phone_data": False, "generated_phone_data": [], "reason": "无相关事件ID"}

        # 收集已存在的手机数据
        existing_phone_data = []
        for event_info in related_events_info:
            event_id = event_info["event_id"]
            phone_ops = self.get_phone_operations_by_event_id(event_id)
            if phone_ops:
                existing_phone_data.append({
                    "event_id": event_id,
                    "event_name": event_info["event_name"],
                    "phone_operations": phone_ops
                })

        # 准备事件列表用于 LLM 分析
        events_for_analysis = []
        for event_info in related_events_info:
            event_id = event_info["event_id"]
            # 查找该事件的现有手机数据
            event_phone_data = [p for p in existing_phone_data if p["event_id"] == event_id]
            events_for_analysis.append({
                "event_id": event_id,
                "event_name": event_info["event_name"],
                "date": event_info["date"],
                "original_event": event_info["original_event"],
                "existing_phone_data": event_phone_data[0]["phone_operations"] if event_phone_data else []
            })

        # 调用 LLM 分析并生成 to_generate 格式
        analysis_prompt = f"""
请分析以下事件及其现有手机数据，判断是否充分体现节点的状态和约束，并为不充分的事件生成需要补充的数据。

【节点状态】
{node_state}

【隐藏信息】
{hidden_info}

【不能做的情景】
{json.dumps(cannot_do, ensure_ascii=False, indent=2) if cannot_do else "无"}

【允许的数据类型】
sms, phonecall, photo, push, note, calendar

【事件列表及现有手机数据】
{json.dumps(events_for_analysis, ensure_ascii=False, indent=2)}

【分析任务】
1. 对每个事件，分析其现有手机数据是否充分反映了该事件的核心信息
2. 如果不充分，使用 to_generate 格式指定需要生成的数据
3. to_generate 中的 content_summary 应该详细描述需要生成什么数据来补充现有数据的不足

【输出格式】
请以 JSON 格式返回：
{{
    "overall_analysis": "对所有事件证据的整体分析",
    "events_analysis": [
        {{
            "event_id": "事件 ID",
            "event_name": "事件名称",
            "sufficiency_analysis": "对现有数据是否充分反映该事件的分析",
            "to_generate": [
                {{
                    "type": "sms/phonecall/photo/push/note/calendar",
                    "content_summary": "数据内容描述（用于生成具体数据，只包含缺少的关键信息，保持最小信息量）",
                    "reason": "为什么需要这个数据来反映该事件的哪个重要信息，以及为何现有数据不足"
                }}
            ]
        }}
    ]
}}

【重要约束】
- 只返回 JSON 对象
- 不要使用 Markdown 代码块
- 只为确实需要补充数据的事件生成 to_generate
- content_summary 应该详细且具体，描述需要生成什么内容
"""
        try:
            analysis_res = llm_call_j(analysis_prompt)
            if isinstance(analysis_res, str):
                analysis_res = json.loads(analysis_res)

            if not isinstance(analysis_res, dict):
                return {
                    "has_phone_data": len(existing_phone_data) > 0,
                    "existing_data": existing_phone_data,
                    "generated_phone_data": [],
                    "error": "LLM 返回格式错误"
                }

            events_analysis = analysis_res.get("events_analysis", [])

            # 收集所有需要生成的数据项
            all_to_generate = []
            for event_analysis in events_analysis:
                event_id = event_analysis.get("event_id", "")
                to_generate = event_analysis.get("to_generate", [])
                for gen_item in to_generate:
                    gen_item["target_event_id"] = event_id
                    all_to_generate.append(gen_item)

            print(f"    整体分析: {analysis_res.get('overall_analysis', '')[:100]}...")
            print(f"    需要生成 {len(all_to_generate)} 条手机数据")

            # 生成手机数据
            generated_data = []
            if all_to_generate:
                generated_data = self._generate_phone_data_from_to_generate(
                    node, all_to_generate, related_events_info
                )

            return {
                "has_phone_data": len(existing_phone_data) > 0,
                "existing_data": existing_phone_data,
                "generated_phone_data": generated_data,
                "events_analysis": events_analysis,
                "total_to_generate": len(all_to_generate)
            }

        except Exception as e:
            if self.is_print:
                print(f"    手机数据分析失败: {e}")
            return {
                "has_phone_data": len(existing_phone_data) > 0,
                "existing_data": existing_phone_data,
                "generated_phone_data": [],
                "error": str(e)
            }

    def _generate_phone_data_from_to_generate(self, node: Dict, to_generate: List[Dict], related_events_info: List[Dict]) -> List[Dict]:
        """
        根据 to_generate 格式生成手机数据

        Args:
            node: 异常状态节点
            to_generate: 需要生成的数据项列表 (type, content_summary, reason, target_event_id)
            related_events_info: 相关事件的详细信息

        Returns:
            生成的手机数据列表
        """
        node_state = node.get("state", "")

        # 建立 event_id 到事件信息的映射
        event_info_map = {e["event_id"]: e for e in related_events_info}

        # 允许的操作类型
        ALLOWED_OP_TYPES = {'sms', 'phonecall', 'photo', 'push', 'note', 'calendar'}

        generated_data = []
        all_generated_operations = []

        for gen_item in to_generate:
            op_type = gen_item.get('type', 'sms')
            content_summary = gen_item.get('content_summary', '')
            target_event_id = gen_item.get('target_event_id', '')
            reason = gen_item.get('reason', '')

            if op_type not in ALLOWED_OP_TYPES:
                print(f"    跳过不支持的类型: {op_type}")
                continue

            event_info = event_info_map.get(target_event_id, {})
            original_event = event_info.get("original_event", {})

            if not original_event:
                continue

            # 构建详细的 generation_hint
            generation_hint = f"""
请生成 {op_type} 类型的数据，要求：{content_summary}

背景信息：
- 目标事件: {event_info.get('event_name', '')}
- 事件日期: {event_info.get('date', '')}
- 节点状态: {node_state}
- 生成原因: {reason}

注意：这是为了支持事件 {target_event_id} 的证据数据，请确保数据准确反映该事件。
可生成的数据类型仅限于：sms, phonecall, photo, push, note, calendar
"""

            try:
                print(f"    生成 {op_type} 数据 for 事件 {target_event_id}: {content_summary[:50]}...")

                # 使用 PhoneOperationGenerator 生成
                operations = self.phone_op_generator.generate(
                    operation_type=op_type,
                    original_event=original_event,
                    question=f"关于 {node_state} 的问题",
                    generation_hint=generation_hint
                )

                if operations:
                    # 为生成的数据设置 daily_event_id 和 event_id
                    for op in operations:
                        op["daily_event_id"] = target_event_id
                        op["event_id"] = target_event_id

                    all_generated_operations.extend(operations)

                    generated_data.append({
                        "event_id": target_event_id,
                        "event_name": event_info.get("event_name", ""),
                        "op_type": op_type,
                        "generated_operations": operations,
                        "reason": reason
                    })
                    print(f"      生成了 {len(operations)} 条 {op_type} 数据")

            except Exception as e:
                if self.is_print:
                    print(f"      生成失败: {e}")
                continue

        # 将生成的操作数据添加到 phonedata
        if all_generated_operations:
            self._add_operations_to_phonedata(all_generated_operations)

        return generated_data

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
                    op['phone_id'] = self.phone_id_counters[op_type]

                self.phone_id_counters[op_type] += 1

                self.phonedata[op_type].append(op)

        print(f"    已将 {len(operations)} 条操作数据添加到 phonedata")

    def _get_events_for_single_date(self, date: str) -> List[Dict]:
        """
        获取指定日期的所有事件
        
        Args:
            date: 日期字符串，格式 YYYY-MM-DD
        
        Returns:
            该日期的事件列表
        """
        events = []
        for event in self.daily_event:
            event_dates = event.get("date", [])
            if not event_dates:
                continue
            
            # 检查事件是否在该日期
            for date_range in event_dates:
                if isinstance(date_range, str):
                    # 处理日期范围或单个日期
                    if "至" in date_range:
                        # 日期范围：检查目标日期是否在范围内
                        start_end = date_range.split("至")
                        start_date = start_end[0].strip().split(" ")[0]
                        end_date = start_end[1].strip().split(" ")[0]
                        if start_date <= date <= end_date:
                            events.append(event)
                            break
                    else:
                        # 单个日期
                        event_date = date_range.split(" ")[0]
                        if event_date == date:
                            events.append(event)
                            break
        
        return events
    
    def _get_phone_evidence_by_event_ids(self, event_ids: List[str]) -> List[Dict]:
        """
        根据事件ID列表，从手机数据中提取对应的证据

        Args:
            event_ids: 事件ID列表

        Returns:
            对应的手机数据证据列表（直接返回数据，不嵌套type/data结构）
        """
        if not event_ids or not self.phonedata:
            return []

        evidence_list = []
        event_id_set = set(str(eid) for eid in event_ids)

        # 遍历所有类型的手机数据
        for data_type, data_items in self.phonedata.items():
            if not isinstance(data_items, list):
                continue

            for item in data_items:
                if not isinstance(item, dict):
                    continue

                # 检查 daily_event_id 或 related_event 字段
                item_event_id = str(item.get('daily_event_id', ''))
                related_event = str(item.get('related_event', ''))

                # 如果匹配，添加完整操作数据（不嵌套type/data）
                if item_event_id in event_id_set or related_event in event_id_set:
                    evidence_list.append(item)

        return evidence_list
