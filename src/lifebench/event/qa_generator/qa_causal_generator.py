# -*- coding: utf-8 -*-
"""
因果问题生成器：基于事件树提取因果关系并生成问答对
"""
import os
import json
import random
import threading
from typing import List, Dict, Tuple, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from .base_generator import BaseQAGenerator
from .phone_operation_generator import PhoneOperationGenerator
from src.lifebench.utils.llm_call import llm_call, llm_call_j

class QACausalGenerator(BaseQAGenerator):
    def __init__(self, daily_event: List[Dict], event_tree: List[Dict],
                 draft_event: Dict[str, List], phonedata: Dict[str, List],
                 phone_data_dir: str = None, is_print: bool = True,
                 year: int = 2025):
        """
        初始化因果问题生成器

        Args:
            daily_event: daily_event 数据列表
            event_tree: event_tree 数据列表
            draft_event: draft_event 数据字典（按月份组织）
            phonedata: 手机操作数据字典
            phone_data_dir: 手机数据目录路径
            is_print: 是否打印调试信息
        """
        super().__init__()
        self.daily_event = daily_event
        self.event_tree = event_tree
        self.draft_event = draft_event
        self.phonedata = phonedata
        self.phone_data_dir = phone_data_dir
        self.is_print = is_print
        self.phone_op_generator = PhoneOperationGenerator()
        # 线程锁
        self.phonedata_lock = threading.Lock()
        self.phone_id_counters = {}
        self.default_ask_time = f"{year}-12-31"

        self.causal_pairs = []
        self.daily_events_map = {}  # {atomic_id: daily_event}
        self.atomic_to_event_id_map = {}  # {atomic_id: event_id}
        
        # 建立 ID 映射
        for event in self.daily_event:
            eid = event.get("event_id")
            if eid:
                self.daily_events_map[str(eid)] = event
            
            # 构建 atomic_id 到 event_id 的映射
            atomic_ids = event.get("atomic_id", [])
            if isinstance(atomic_ids, list):
                for aid in atomic_ids:
                    if aid:
                        self.atomic_to_event_id_map[str(aid)] = str(eid)


    def extract_causal_pairs(self) -> List[Dict]:
        """遍历事件树森林，提取每棵树的底层节点并调用 LLM 识别因果关系对"""
        if self.is_print:
            print("[CausalGen] 正在从事件树森林中提取各树的底层节点...")
            
        all_pairs = []
            
        # event_tree 是一个列表，代表一个森林
        # 使用 20 线程并行处理多棵树
        def process_single_tree(tree_idx: int, root: Dict) -> List[Dict]:
            """处理单棵树，返回该树的因果对列表"""
            bottom_events = []
                
            def traverse(node):
                if not isinstance(node, dict):
                    return
                subevents = node.get("subevent", [])
                if not subevents or not isinstance(subevents, list) or len(subevents) == 0:
                    # 这是一个底层节点
                    bottom_events.append({
                        "event_id": str(node.get("event_id")),
                        "description": node.get("description", ""),
                        "date": node.get("date", "")
                    })
                else:
                    for child in subevents:
                        traverse(child)
    
            traverse(root)
                
            if not bottom_events:
                return []
                    
            if self.is_print:
                print(f"  - 树 {tree_idx + 1} 包含 {len(bottom_events)} 个底层节点，正在分析因果...")
                
            # 将当前树的底层事件分批输入给 LLM 进行因果对提取
            batch_size = 20
            tree_pairs = []
                
            def process_batch(batch):
                prompt = f"""
                你是一位逻辑分析专家。请分析以下一组生活事件，找出其中存在**明确且强因果关系**的事件组。
                    
                【事件列表】
                {json.dumps(batch, ensure_ascii=False, indent=2)}
                    
                【筛选标准 - 宁缺毋滥】
                1. **强因果关联（必须满足）**：原因必须对结果有**直接的、决定性的**推动作用，而非仅仅是时间先后或可能的相关性。
                   - ✅ 正确示例：“连续熬夜一周” → “第二天身体不适请假”
                   - ❌ 错误示例：“吃了早餐” → “去上班”（仅为时间顺序，无因果）
                   - ❌ 错误示例：“下雨” → “心情不好”（可能相关，但非必然因果，除非明确提到下雨天）
                2. **重要性判断**：忽略琐碎、日常重复或对生活轨迹无显著影响的事件。
                3. **多对一关联**：支持多个原因事件共同导致一个结果事件（cause_id 为数组），但每个原因都必须是结果的必要条件或重要贡献因素。
                4. **时间跨度优先**：优先提取间隔时间较长但逻辑紧密的因果关联。
                5. **严格数量限制**：最多生成 2 个因果对/组。**如果没有符合条件的强因果关系，必须返回空数组 []，绝不凑数。**
                    
                【输出要求】
                输出格式为 JSON 数组，每个元素包含：
                   - "cause_id": 原因事件的 ID 数组 (例如: ["id1", "id2"])
                   - "effect_id": 结果事件的 ID (字符串)
                   - "reason": 简要说明为什么它们构成**明确的强因果关系**（必须解释因果机制，而非仅描述时间顺序）
                    
                示例：
                [
                  {{
                    "cause_id": ["101", "102"],
                    "effect_id": "105",
                    "reason": "长期的压力积累（101）和一次突发的争吵（102）共同直接导致了情绪崩溃（105），两者缺一不可。"
                  }}
                ]
                    
                **重要提醒**：如果事件之间只有时间先后关系、相关性或弱关联，请不要提取。宁可返回空数组，也不要输出不确定的因果对。
                """
                try:
                    res = llm_call_j(prompt)
                    if self.is_print:
                        print(f"    LLM 输出：{res}")
                    if isinstance(res, str):
                        res = json.loads(res)
                    if isinstance(res, list):
                        return res
                except Exception as e:
                    if self.is_print:
                        print(f"    ⚠️ 批次处理失败: {e}")
                return []
    
            # 使用 20 线程并行处理批次
            batches = [bottom_events[i:i + batch_size] for i in range(0, len(bottom_events), batch_size)]
            with ThreadPoolExecutor(max_workers=20) as executor:
                futures = [executor.submit(process_batch, batch) for batch in batches]
                for future in as_completed(futures):
                    tree_pairs.extend(future.result())
                
            return tree_pairs
            
        # 并行处理所有树（随机采样100棵）
        import random
        total_trees = len(self.event_tree)
        if total_trees > 100:
            # 随机采样100个索引
            sampled_indices = random.sample(range(total_trees), 100)
            sampled_trees = [(idx, self.event_tree[idx]) for idx in sampled_indices]
            if self.is_print:
                print(f"[CausalGen] 事件树总数: {total_trees}，随机采样 100 棵进行处理")
        else:
            # 如果不足100棵，全部处理
            sampled_trees = list(enumerate(self.event_tree))
            if self.is_print:
                print(f"[CausalGen] 事件树总数: {total_trees}，全部处理")
        
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [
                executor.submit(process_single_tree, tree_idx, root)
                for tree_idx, root in sampled_trees
            ]
                
            completed_count = 0
            total_trees = len(self.event_tree)
            for future in as_completed(futures):
                try:
                    tree_pairs = future.result()
                    all_pairs.extend(tree_pairs)
                    completed_count += 1
                    if self.is_print and completed_count % 5 == 0:
                        print(f"[CausalGen] 已完成 {completed_count}/{total_trees} 棵树的处理")
                except Exception as e:
                    if self.is_print:
                        print(f"[CausalGen] ⚠️ 树处理失败: {e}")
            
        self.causal_pairs = all_pairs
        if self.is_print:
            print(f"[CausalGen] ✓ 经 LLM 识别，全森林共确认 {len(all_pairs)} 个因果对")
        return all_pairs

    def generate_questions(self, num_samples: int = 120):
        """采样并生成因果问题"""
        if not self.causal_pairs:
            self.extract_causal_pairs()
        
        if len(self.causal_pairs) > num_samples:
            sampled_pairs = random.sample(self.causal_pairs, num_samples)
        else:
            sampled_pairs = self.causal_pairs
            
        results = []
        if self.is_print:
            print(f"[CausalGen] 开始并行生成 {len(sampled_pairs)} 个因果问题...")
        
        def process_pair(pair):
            cause_atomic_ids = pair.get("cause_id", [])
            effect_atomic_id = pair.get("effect_id")
            
            # 兼容旧格式（单 ID）和新格式（ID 数组）
            if isinstance(cause_atomic_ids, str):
                cause_atomic_ids = [cause_atomic_ids]
            
            # 检查因果对的 event_id 是否完全一样，如果是则直接抛弃
            cause_eids = set()
            for aid in cause_atomic_ids:
                eid = self.atomic_to_event_id_map.get(str(aid))
                if eid:
                    cause_eids.add(str(eid))
            
            effect_eid = self.atomic_to_event_id_map.get(str(effect_atomic_id)) if effect_atomic_id else None
            
            if effect_eid and str(effect_eid) in cause_eids:
                if self.is_print:
                    print(f"  ⚠️ 跳过因果对 - 原因和结果的 event_id 相同: {effect_eid}")
                return None
            
            if self.is_print:
                print(f"  [DEBUG] 处理因果对 - cause_ids: {cause_atomic_ids}, effect_id: {effect_atomic_id}")
                print(f"    atomic_to_event_id_map 大小: {len(self.atomic_to_event_id_map)}")
                print(f"    daily_events_map 大小: {len(self.daily_events_map)}")
            
            # 基于 atomic_id 获取 event_id，再获取对应的 daily_event
            cause_events = []
            for aid in cause_atomic_ids:
                eid = self.atomic_to_event_id_map.get(str(aid))
                if self.is_print:
                    print(f"    - atomic_id {aid} -> event_id {eid} (found: {eid is not None})")
                if eid and eid in self.daily_events_map:
                    cause_events.append(self.daily_events_map[eid])
            
            effect_eid = self.atomic_to_event_id_map.get(str(effect_atomic_id)) if effect_atomic_id else None
            if self.is_print:
                print(f"    - effect atomic_id {effect_atomic_id} -> event_id {effect_eid} (found: {effect_eid is not None})")
            effect_event = self.daily_events_map.get(effect_eid) if effect_eid else None
            
            if not cause_events or not effect_event:
                if self.is_print:
                    print(f"  ⚠️ 未找到目标事件 - cause_found: {len(cause_events)}/{len(cause_atomic_ids)}, effect_found: {effect_event is not None}")
                return None
                
            qa_data = self._generate_single_causal_qa(pair, cause_events, effect_event)
            if qa_data:
                # 包装为 evidence_refine 期望的格式
                return {'data': qa_data}
            return None

        # 使用 20 线程并行处理
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = {executor.submit(process_pair, pair): idx for idx, pair in enumerate(sampled_pairs)}
            completed_count = 0
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                    completed_count += 1
                    if self.is_print and completed_count % 10 == 0:
                        print(f"  - 已生成 {completed_count}/{len(sampled_pairs)} 个问题")
                except Exception as e:
                    if self.is_print:
                        print(f"  ⚠️ 任务执行出错: {e}")
        
        # 保持原有顺序（可选，如果需要严格对应 sampled_pairs 的顺序）
        # results.sort(key=lambda x: x.get('index', 0)) 
                
        return results

    def _generate_single_causal_qa(self, pair: Dict, cause_evs: List[Dict], effect_ev: Dict) -> Dict:
        """基于因果对（支持多对一）生成单个 QA"""
        # 提取月份信息
        effect_date = effect_ev.get('date', '')
        month_info = effect_date[:7] if len(effect_date) >= 7 else "未知月份"
        
        # 格式化原因事件组
        cause_details = "\n".join([f"- {e.get('date')}: {e.get('description')}" for e in cause_evs])
        effect_desc = effect_ev.get('description', '')
        
        prompt = f"""
        你是一位擅长挖掘生活逻辑的提问专家。请根据以下存在**明确关联（因果关系或逻辑先后关系）**的事件组，设计一个需要**多跳推理**才能回答的问题。
                
        【背景信息】
        月份：{month_info}
        
        **事件关联说明（输入依据）**：
        {pair.get('reason', '未提供具体原因说明')}
        
        原因事件组：
        {cause_details}
                
        结果事件：
        - {effect_date}: {effect_desc}
                
        【核心设计理念 - 多跳推理】
        **设计目标**：找出有关联的事件，题目只叙述一些事件的信息，查询另一些事件的信息，迫使用户进行多跳推理。
        
        1. **问题必须只包含部分事件的信息**，用户需要通过推理才能得出其他事件的信息：
           - ✅ 正确示例（给出结果，查原因）："2025年3月我为什么突然请假了？" → 需要从原因事件推理出请假原因
           - ✅ 正确示例（给出原因，查结果）："2025年3月连续熬夜一周后，我的身体发生了什么变化？" → 需要从结果事件推理出身体状况
           - ✅ 正确示例（逻辑先后，查细节）："我1月3号去看电影时，电影票是何时/如何预定的？" → 需要从买票事件推理出预定事件的信息
           - ❌ 错误示例："因为我连续熬夜，所以我请假了，这是为什么？" → 同时包含了原因和结果，无需推理
                
        2. **提问方式灵活多变**，根据事件关联类型选择不同策略：
           - **强因果关系**（如"熬夜→生病"）：可以问"XX是因为什么？"、"我为什么XX？"、"是什么导致了XX？"
           - **逻辑先后关系**（如"买票→看电影"）：当难以设计"为什么"问题时，针对其中一个事件的细节提问，但答案需要从另一个事件推理得出
             - 例如：两个事件为"去看电影"和"买票"，可以提问"我1月3号去看电影时，电影票何时/如何预定的？"
             - 例如：两个事件为"预订餐厅"和"去吃饭"，可以提问"我去那家新开的日料店时，是怎么预订位置的？"
           - 可以结合情境："还记得那次XX吗？后来怎么样了？"、"当时XX的背后有什么故事？"
           - **示例仅供参考，请根据具体事件特点创造性地设计问题**
                
        3. **最小信息原则（题目）**：
           - **题目只保留定位事件所需的最少信息**，避免过多的生活细节描述
           - 例如：用"那次重要的会议"而非"周三下午三点在会议室A举行的季度总结会议"
           - 目的是让问题简洁明了，但足以让回答者知道指的是哪个事件
           - 必须在题目开头或描述中带上月份信息（例如："在2025年3月，我..."）
           
        4. **多跳推理要求（答案）**：
           - **答案必须结合两个及以上的事件信息才能完整得出**，防止设计为单跳信息检索问题
           - 答案需要解释完整的因果链条或逻辑关系：原因事件如何导致结果事件，或者两个事件之间的关联是什么
           - 如果只有单个原因事件，需要说明该事件的哪些特征/细节导致了结果
           - 如果有多个原因事件，需要说明它们如何共同作用导致结果
           - 答案应该体现推理过程，而非简单的事实陈述
                
        5. **输出结构**：
           - `question`: 生成的问题（自然、流畅、符合日常对话风格）
           - `answer`: 准确、逻辑严密的答案，完整解释因果链条或逻辑关系
           - `score_points`: 评分点列表，包含 description 和 score，用于评估答案质量
           - `required_events_id`: 涉及的所有事件 ID 数组（包括原因和结果）
           - `question_type`: 固定为 "Causal"
                
        请输出 JSON 格式：
        {{
            "question": "...",
            "answer": "...",
            "score_points": [
                {{"description": "...", "score": 2}},
                {{"description": "...", "score": 3}}
            ],
            "required_events_id": ["{effect_ev.get('event_id')}", "{cause_evs[0].get('event_id') if cause_evs else ''}"],
            "question_type": "Causal"
        }}
        """
        
        try:
            res = llm_call_j(prompt)
            if isinstance(res, str):
                res = json.loads(res)
            
            # 补充完整的事件 ID 列表
            all_ids = [effect_ev.get('event_id')] + [e.get('event_id') for e in cause_evs]
            res['required_events_id'] = [str(eid) for eid in all_ids if eid]
            res['question_type'] = 'Causal'
            res['ask_time'] = self.default_ask_time

            # 确保有 score_points
            if 'score_points' not in res or not res['score_points']:
                res['score_points'] = [{
                    "description": "准确回答出答案",
                    "score": 10
                }]

            return res
        except Exception as e:
            if self.is_print:
                print(f"  ⚠️ 生成失败: {e}")
            return None

    def run(self, output_path: str = "output/causal_qa.json"):
        """执行完整的因果问题生成流程"""
        questions = self.generate_questions()
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(questions, f, ensure_ascii=False, indent=2)
        if self.is_print:
            print(f"[CausalGen] ✓ 完成！结果已保存至: {output_path}")
        return questions

    def QAGen(self, **kwargs):
        """
        实现基类抽象方法，作为外部调用的统一入口
        """
        num_samples = kwargs.get('num_samples', 60)
        
        # 1. 提取因果对
        if not self.causal_pairs:
            if self.is_print:
                print("\n[QAGen] 开始提取因果对...")
            self.extract_causal_pairs()
        
        # 2. 生成问题
        if self.is_print:
            print(f"\n[QAGen] 开始生成 {num_samples} 个因果问题...")
        questions = self.generate_questions(num_samples=num_samples)
        
        # 3. 使用 20 线程并行调用 evidence_refine
        if self.is_print:
            print(f"\n[QAGen] 开始并行优化 {len(questions)} 个问题的证据...")
        
        refined_questions = []
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(self.evidence_refine, q) for q in questions]
            for future in as_completed(futures):
                try:
                    refined_question = future.result()
                    refined_questions.append(refined_question)
                except Exception as e:
                    if self.is_print:
                        print(f"[QAGen] 证据优化任务异常: {e}")
        
        if self.is_print:
            print(f"[QAGen] ✓ 证据优化完成，共 {len(refined_questions)} 个问题")
        
        # 4. 问题分析与过滤
        if self.is_print:
            print(f"\n[QAGen] 开始问题分析与过滤...")
        
        filtered_questions = []
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(self._analyze_and_filter_question, q) for q in refined_questions]
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result is not None:
                        filtered_questions.append(result)
                except Exception as e:
                    if self.is_print:
                        print(f"[QAGen] 问题分析任务异常: {e}")
        
        if self.is_print:
            print(f"[QAGen] ✓ 问题过滤完成，保留 {len(filtered_questions)}/{len(refined_questions)} 个问题")
        
        return filtered_questions

    def _analyze_and_filter_question(self, question: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析问题的合理性、流畅性、难度，并判断是否可以从 evidence 回答
        
        Args:
            question: 包含 evidence 的问题
            
        Returns:
            优化后的问题或 None（如果应该抛弃）
        """
        question_data = question.get('data', {})
        question_text = question_data.get('question', '')
        answer_text = question_data.get('answer', '')
        evidence = question_data.get('evidence', [])
        score_points = question_data.get('score_points', [])
        
        if self.is_print:
            print(f"\n[QA Filter] 分析问题: {question_text[:50]}...")
        
        analysis_prompt = f"""
        你是一位专业的问答质量评估专家。请分析以下因果问题及其证据的质量。
        
        【问题信息】
        - 问题：{question_text}
        - 答案：{answer_text}
        - 评分点：{json.dumps(score_points, ensure_ascii=False, indent=2)}
        
        【证据数据】（共{len(evidence)}条）
        {json.dumps([{'type': ev.get('type', ''), 'summary': str(ev)[:300]} for ev in evidence[:10]], ensure_ascii=False, indent=2)}
        {'...' if len(evidence) > 10 else ''}
        
        【评估维度】
        1. **合理性**：问题和答案是否符合逻辑，因果关系是否成立
        2. **流畅性**：问题表述是否自然流畅，符合日常对话习惯
        3. **难度**：问题是否具有适当的推理难度，不是简单的信息检索
        4. **可回答性**：基于提供的证据，是否能够推理出答案
        5. **证据充分性**：证据是否过于简单，没有设计问题的必要
        
        【处理策略】
        - 如果问题质量良好且可以从证据回答：返回 "pass"
        - 如果问题需要重新设计但证据有价值：返回 "redesign" 并提供新的问题、答案和评分点
        - 如果证据过于简单，没有设计问题的必要：返回 "discard"
        
        **Redesign 指导原则**（仅在 decision 为 redesign 时应用）：
        1. **多跳推理要求**：重新设计的问题必须具有足够的难度，需要从多个 evidence 中推理才能得出答案
           - 题目只包含部分事件的信息，迫使用户从其他 evidence 中推理出缺失信息
           - 答案必须结合至少 2-3 条不同的 evidence 才能完整回答
           - 避免单跳检索问题（如直接从某条短信中找到答案）
        2. **推理链条设计**：
           - 明确哪些 evidence 提供线索，哪些 evidence 提供关键信息
           - 设计合理的推理路径：evidence A → 推断中间结论 → 结合 evidence B → 得出最终答案
           - 例如：从短信知道“买了票”，从日历知道“看电影时间”，从推送知道“票价”，综合推理出“何时以什么价格预定了电影票”
        3. **难度控制**：
           - 问题不应过于简单（直接检索即可回答）
           - 问题不应过于困难（需要外部知识或过度推测）
           - 理想难度：需要整合 2-3 条 evidence，进行 1-2 步推理
        
        **输出格式**
        请以 JSON 格式返回：
        {{
            "decision": "pass/redesign/discard",
            "analysis": {{
                "reasonableness_score": 1-5,
                "fluency_score": 1-5,
                "difficulty_score": 1-5,
                "answerability": true/false,
                "evidence_sufficiency": "充足/不足/过于简单"
            }},
            "reason": "决策理由",
            "redesigned_question": {{
                "question": "重新设计的问题（仅在 decision 为 redesign 时提供）",
                "answer": "重新设计的答案",
                "score_points": [
                    {{"description": "...", "score": 2}}
                ]
            }}
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
                decision = llm_result.get('decision', 'discard')
                reason = llm_result.get('reason', '')
                
                if self.is_print:
                    print(f"  - 决策: {decision}")
                    print(f"  - 理由: {reason[:100]}")
                
                if decision == 'pass':
                    return question
                elif decision == 'redesign':
                    redesigned = llm_result.get('redesigned_question', {})
                    if redesigned:
                        question['data']['question'] = redesigned.get('question', question_text)
                        question['data']['answer'] = redesigned.get('answer', answer_text)
                        question['data']['score_points'] = redesigned.get('score_points', score_points)
                        if self.is_print:
                            print(f"  - 已重新设计问题")
                        return question
                    else:
                        if self.is_print:
                            print(f"  - 重新设计失败，抛弃问题")
                        return None
                else:  # discard
                    if self.is_print:
                        print(f"  - 抛弃问题")
                    return None
            else:
                if self.is_print:
                    print(f"  - LLM 返回格式异常，抛弃问题")
                return None
        except Exception as e:
            if self.is_print:
                print(f"  - 分析失败: {e}，抛弃问题")
            return None

    def evidence_refine(self, question: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evidence Refine: 分析并优化问题的证据数据，确保手机数据能够充足反映事件并提供足够回答问题的数据

        Args:
            question: 生成的因果问题

        Returns:
            优化证据后的问题
        """
        if self.is_print:
            print(f"\n[Evidence Refine] 开始优化因果问题的证据数据...")

        # 获取 required_events_id 列表
        required_events_ids = question.get('data', {}).get('required_events_id', [])
        if not required_events_ids:
            if self.is_print:
                print("[Evidence Refine] 无需补充证据数据")
            return question

        # 收集所有事件的现有证据
        all_existing_evidence = []
        event_details = []
        
        for event_id in required_events_ids:
            # 在 daily_event 中查找对应事件
            target_event = None
            if isinstance(self.daily_event, list):
                for event in self.daily_event:
                    event_id_in_event = event.get('event_id', '')
                    if str(event_id_in_event) == str(event_id):
                        target_event = event
                        break
                    try:
                        if int(event_id_in_event) == int(event_id):
                            target_event = event
                            break
                    except (ValueError, TypeError):
                        pass
            
            if not target_event:
                continue
            
            # 获取事件信息
            event_date = target_event.get('date', '')
            event_description = target_event.get('description', '')
            event_details.append({
                'event_id': event_id,
                'date': event_date,
                'description': event_description
            })
            
            # 从手机数据中查找与该事件对应的数据
            if self.phonedata:
                with self.phonedata_lock:
                    for data_type, data_list in self.phonedata.items():
                        if isinstance(data_list, list):
                            for item in data_list:
                                if isinstance(item, dict):
                                    item_event_id = str(item.get('daily_event_id', ''))
                                    related_event = str(item.get('related_event', ''))
                                    
                                    if item_event_id == str(event_id) or related_event == str(event_id):
                                        all_existing_evidence.append({
                                            'event_id': event_id,
                                            'type': data_type,
                                            'data': item,
                                            'phone_id': item.get('phone_id', '')
                                        })
        
        if self.is_print:
            print(f"[Evidence Refine] 找到 {len(all_existing_evidence)} 条现有相关数据")
            print(f"[Evidence Refine] 涉及 {len(event_details)} 个事件")
        
        # 使用 LLM 整体分析问题是否需要补充证据
        analysis_prompt = f"""
        作为数据分析师，请分析以下因果问题、答案和现有证据。
                    
        【任务背景】
        您正在为因果问题的回答设计证据。这些证据是手机操作数据（包括短信、通话、照片、推送通知、笔记、日历等），手机智能助手会基于这些手机操作推理并回答问题。
        
        **重要**：这是一个因果问题，需要结合多个事件的信息才能回答。请评估现有证据是否足以支持用户通过手机数据推理出完整的因果关系。
                    
        【问题与答案】
        - 问题：{question.get('data', {}).get('question', '')}
        - 答案：{question.get('data', {}).get('answer', '')[:500]}{'...' if len(question.get('data', {}).get('answer', '')) > 500 else ''}
                    
        【涉及的事件】（共{len(event_details)}个）
        {json.dumps(event_details, ensure_ascii=False, indent=2)}
                    
        【现有手机数据证据】（共{len(all_existing_evidence)}条）
        {json.dumps([{'event_id': ev['event_id'], 'type': ev['type'], 'phone_id': ev['phone_id'], 'data_summary': str(ev['data'])[:200]} for ev in all_existing_evidence], ensure_ascii=False, indent=2)}
                    
        【可生成的数据类型】
        sms, phonecall, photo, push, note, calendar
                    
        **重要原则**
        1. **因果推理完整性**：评估现有证据是否能支持用户通过手机数据推理出完整的因果关系链。
           - 原因事件的关键信息是否在证据中有所体现？
           - 结果事件的关键信息是否在证据中有所体现？
           - 是否存在关键信息的缺失导致无法完成因果推理？
        2. **非必要不生成**：只有当十分确定缺乏关键信息，或缺乏足以支持因果推理的信息时，才考虑新增。
        3. **重点优先**：不需要全面反映出所有事件的所有细节，只关注与问题和答案相关的重点内容。
        4. **互补性原则**：如果要生成新数据，必须与已有数据形成互补关系，不要和已有数据反映同样的信息。
           - **检查已有数据**：先看看已经有了什么信息
           - **补充缺失信息**：只生成能提供新信息的数据
           - **避免重复**：**严禁**生成与已有数据内容重复或高度相似的数据
        5. **最小信息量**：当要新增手机数据时：
           - 先分析缺少的具体信息是什么
           - 只生成包含缺少信息的数据，不要在数据中反映所有信息
           - **禁止**生成一个包含了事件所有信息或可以直接反映答案的充足数据
        
        **分析任务**
        1. 现有手机数据是否充分反映了所有相关事件的关键信息？
        2. 现有证据是否足以支持用户通过手机数据推理出完整的因果关系？
        3. 如果不足，最需要补充哪些关键数据来完整展现因果关系？
                    
        **输出格式**
        请以 JSON 格式返回：
        {{
            "sufficiency_analysis": "对现有数据是否充分反映所有事件及支持因果推理的分析",
            "can_answer_with_current_evidence": true/false,
            "to_generate": [
                {{
                    "target_event_id": "目标事件ID",
                    "type": "sms/phonecall/photo/push/note/calendar",
                    "content_summary": "只描述要生成的手机操作数据应该包含哪些具体信息（例如：'短信内容应提到跑步5公里'、'推送通知应包含时间07:30'），不要包含推理过程或解释",
                    "reason": "为什么需要这个数据来反映该事件的哪个重要信息，以及为何现有数据不足"
                }}
            ],
            "rationale": "数据分析理由"
        }}
        """
        
        try:
            llm_result = llm_call_j(analysis_prompt)
            print(f"[Evidence Refine] LLM 分析提示：{analysis_prompt}")
            print(f"[Evidence Refine] LLM 分析结果：{llm_result}")
            # 解析 LLM 结果
            if isinstance(llm_result, str):
                start_idx = llm_result.find('{')
                end_idx = llm_result.rfind('}') + 1
                if start_idx != -1 and end_idx != -1:
                    llm_result = json.loads(llm_result[start_idx:end_idx])
            
            if isinstance(llm_result, dict):
                to_generate = llm_result.get('to_generate', [])
                can_answer = llm_result.get('can_answer_with_current_evidence', False)
                
                if self.is_print:
                    print(f"[Evidence Refine] 分析完成")
                    print(f"  - 现有数据：{len(all_existing_evidence)} 条")
                    print(f"  - 能否基于现有证据回答：{can_answer}")
                    print(f"  - 需要生成：{len(to_generate)} 条数据")
                    print(f"  - 分析说明：{llm_result.get('sufficiency_analysis', '')[:200]}")
            else:
                to_generate = []
                can_answer = False
                if self.is_print:
                    print(f"[Evidence Refine] LLM 返回格式异常")
        except Exception as e:
            if self.is_print:
                print(f"[Evidence Refine] 分析失败：{e}")
            to_generate = []
            can_answer = False
        
        # 如果能基于现有证据回答，直接返回
        if can_answer and not to_generate:
            if self.is_print:
                print(f"[Evidence Refine] 现有证据已足够，无需补充")
            
            # 更新问题的 evidence 字段
            question['data']['evidence'] = all_existing_evidence
            if self.is_print:
                print(f"\n[Evidence Refine] 证据优化完成")
                print(f"  - 最终证据：{len(all_existing_evidence)} 条")
            return question
        
        # 执行生成操作
        generated_operations = []
        if to_generate:
            if self.is_print:
                print(f"\n[Evidence Refine] === 开始执行生成操作 ===")
                print(f"[Evidence Refine] 使用 20 线程并行处理 {len(to_generate)} 个生成任务...")
            
            # 定义允许的操作类型
            ALLOWED_OP_TYPES = {'sms', 'phonecall', 'photo', 'push', 'note', 'calendar'}
            
            # 准备所有需要生成的任务
            generation_tasks = []
            for gen_item in to_generate:
                op_type = gen_item.get('type', 'sms')
                
                # 验证类型是否在允许列表中
                if op_type not in ALLOWED_OP_TYPES:
                    if self.is_print:
                        print(f"[Evidence Refine] 警告：'{op_type}' 不是允许的操作类型，跳过")
                    continue
                
                content_summary = gen_item.get('content_summary', '')
                target_event_id = gen_item.get('target_event_id', '')
                reason = gen_item.get('reason', '')
                
                # 在 daily_event 中查找目标事件
                target_event = None
                if isinstance(self.daily_event, list):
                    for event in self.daily_event:
                        if str(event.get('event_id', '')) == str(target_event_id):
                            target_event = event
                            break
                
                # 创建临时事件用于生成
                temp_event = {
                    'question': question.get('data', {}).get('question', ''),
                    'target_event': target_event or {}
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
                    if self.is_print:
                        print(f"\n准备生成：{op_type}")
                        print(f"  目标事件 ID: {target_event_id}")
                        print(f"  生成原因：{reason}")
                        print(f"  内容要求：{content_summary[:100]}...")
                    
                    # 使用 PhoneOperationGenerator 生成
                    operations = self.phone_op_generator.generate(
                        operation_type=op_type,
                        original_event=temp_event,
                        question=question.get('data', {}).get('question', ''),
                        generation_hint=generation_hint
                    )
                    
                    if operations:
                        if self.is_print:
                            print(f"  ✓ 已生成 {len(operations)} 条 {op_type} 数据")
                        return operations
                    else:
                        if self.is_print:
                            print(f"  ⚠ 未生成任何 {op_type} 数据")
                        return []
                except Exception as e:
                    if self.is_print:
                        print(f"  ✗ 生成失败：{e}")
                    return []
            
            # 使用 ThreadPoolExecutor 并行处理，最多 20 个线程
            with ThreadPoolExecutor(max_workers=20) as executor:
                # 提交所有任务
                futures = [executor.submit(generate_single_task, task) for task in generation_tasks]
                
                # 收集结果
                for future in as_completed(futures):
                    try:
                        operations = future.result()
                        generated_operations.extend(operations)
                    except Exception as e:
                        if self.is_print:
                            print(f"[Evidence Refine] 生成任务异常：{e}")
            
            # 添加到 phonedata
            if generated_operations:
                if self.is_print:
                    print(f"\n[Evidence Refine] 将生成的 {len(generated_operations)} 条数据添加到 phonedata")
                self._add_operations_to_phonedata(generated_operations)

        # 重新收集所有事件的最新证据
        updated_evidence = []
        
        if self.is_print:
            print(f"\n[Evidence Refine] 重新收集所有事件的证据...")
        
        for event_id in required_events_ids:
            # 在 daily_event 中查找对应事件
            target_event = None
            if isinstance(self.daily_event, list):
                for event in self.daily_event:
                    if str(event.get('event_id', '')) == str(event_id):
                        target_event = event
                        break
            
            if not target_event:
                continue
            
            # 从手机数据中查找与该事件对应的数据
            if self.phonedata:
                for data_type, data_list in self.phonedata.items():
                    if isinstance(data_list, list):
                        for item in data_list:
                            if isinstance(item, dict):
                                item_event_id = str(item.get('daily_event_id', ''))
                                related_event = str(item.get('related_event', ''))
                                
                                if item_event_id == str(event_id) or related_event == str(event_id):
                                    updated_evidence.append(item)
        
        # 更新问题的 evidence 字段
        question['data']['evidence'] = updated_evidence
        
        if self.is_print:
            print(f"\n[Evidence Refine] 证据优化完成")
            print(f"  - 最终证据：{len(updated_evidence)} 条")

        return question

    def _add_operations_to_phonedata(self, operations: List[Dict]):
        """
        将生成的手机操作数据添加到 phonedata 中
        
        Args:
            operations: 生成的操作数据列表
        """
        with self.phonedata_lock:
            for op in operations:
                op_type = op.get('type', '')
                if op_type and op_type in self.phonedata:
                    self.phonedata[op_type].append(op)
