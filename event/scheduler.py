# -*- coding: utf-8 -*-
#1）调整日程使其合理  2）消解冲突  3）事件插入+后续调整  4）事件插入  5）事件粒度对齐
import json
import multiprocessing
import os
from typing import Dict, List, Any
from concurrent.futures import ProcessPoolExecutor, as_completed, ThreadPoolExecutor
from utils.IO import *
from datetime import datetime, timedelta
from utils.llm_call import *
from event.templates import *
import re
from datetime import datetime, timedelta
import holidays  # 需安装：pip install holidays


class EventTree:
    def __init__(self, persona: str):
        self.persona = persona
        self.decompose_schedule = []  # 最终分解结果（完整树形结构）
        # 合并后的提示词模板（单步输出子事件JSON数组，含decompose标记）
        self.template_event_decomposer = '''
            基于以下待分解事件，完成推理、扩展、分解，并直接输出子事件JSON数组（无需额外分析文本）：
            
            1. 事件扩展：原事件可能不完整，需合理推理**前置（准备/规划/预定）、后续（收尾/影响）及相关事件**，补充后使其完整丰富。
            2. 粒度与阶段分解规则：
               - 阶段事件：针对跨度长（超过7天）、流程复杂、重要性高的原事件，可拆分为「阶段性子事件」（如项目立项→执行→验收、旅行准备→行程执行→收尾）。
                 - 阶段事件特征：date格式为跨天区间（如["2025-01-01至2025-01-15"]），覆盖一个完整阶段的时间范围，decompose=1，表示其后续将被递归分解。
                 - 阶段划分原则：按「时间顺序+流程逻辑」拆分，每个阶段聚焦一个核心目标，避免阶段重叠或遗漏。注意，如果原事件时间范围小于一天，则不用拆分为阶段事件，直接拆分为原子事件或不拆分，decompose=0。
               - 原子事件：粒度≤1天，具体可执行，发生时间可超出原事件起止时间；多次发生需拆分为多个日期（如["2025-01-01","2025-02-01"]而非["2025-01-01至2025-02-01"]），decompose=0（无需继续分解）。
               - 简单事件：不重要/日常频繁发生/流程简单的事件，直接作为原子事件输出（decompose=0），无需拆分阶段。
            3. 递归分解约束：
               - 每一层分解的子事件数量**严格控制在10个以内**（建议3-8个，避免过度拆分）。
               - 递归深度建议≤3层（如原事件→阶段事件→原子事件，或原事件→原子事件），防止层级过深导致逻辑混乱。**请你判断事件id，每有一个'-'代表多了一层事件，即已经被分解过一次。你在做递归分解。一旦被有'-'，则你一定分解为原子事件（即粒度为天，decompose=0的事件）
               - 阶段事件递归分解后，需输出原子事件（decompose=0），不可出现连续多个decompose=1的层级。
            4. 分解策略：
               - 分解需多样化：并非所有事件都需经过准备/规划流程，同一类事件在不同场景下流程可不同（如吃饭可选择不同菜系）。
               - 时间分布：无需均匀分布事件，按真实场景合理安排（持续时间长不代表每天都有相关动作）；阶段事件的时间区间需覆盖原事件核心流程，原子事件可穿插在阶段内。
            5. 合理性优化：可修改原事件不合理信息，避免事件间安排冲突，确保描述真实丰富；阶段事件的时间区间需衔接自然，无明显断层。
            
            --- 输出格式强制要求 ---
            1. **仅返回JSON数组（直接子事件列表），以[]开头结尾，无任何额外文本（包括分析、注释、代码块标记）。**
            2. 每个子事件必须包含以下字段（缺一不可，语法严格正确）：
               - event_id：格式为「父事件ID-序号」（如父ID=1，子事件ID=1-1、1-2），确保层级关联。
               - name：事件名称（简洁明了）。
               - date：时间数组（单个日期/多个日期，粒度≤1天；跨天事件用"至"连接，如["2025-01-01至2025-01-03"]）。
               - type：取值范围（必选其一）：Career & Education、Relationships、Living Situation、Social & Lifestyle、Finance、Self Satisfy/Care & Entertainment、Personal Growth、Health & Well-being、Unexpected Events、Other。
               - description：事件详细描述（包含执行动作、目的、场景）。
               - participant：参与者数组，格式：[{{"name":"姓名","relation":"关系"}}]，优先从用户画像选择；无合适关系可合理编造，自己参与则为[{{"name":"自己名字","relation":"自己"}}]。
               - location：城市+POI类别描述（如"上海市-家中书房"、"杭州市-灵隐寺"）。
               - decompose：0=无需继续分解（原子事件/简单事件），1=需要继续分解（复杂子事件）。
            3. JSON语法要求：
               - 字段名用双引号包裹，字段间用逗号分隔（无多余逗号）。
               - 字符串值用双引号包裹，无语法错误。
            
            --- 输出示例（仅参考格式，勿复制内容） ---
            示例：父事件ID=5（制定2025年家庭预算，复杂事件），输出子事件（需继续分解+原子事件混合）
            [
                {{
                    "event_id": "5-1",
                    "name": "收集往年账本记录",
                    "date": ["2025-01-09"],
                    "type": "Finance",
                    "description": "徐静与母亲李芳一起收集整理过去一年的家庭账本记录，包括日常生活费、服装店运营成本、父母医疗等各项支出明细，为制定新一年预算做准备",
                    "participant": [{{"name": "徐静", "relation": "自己"}}, {{"name": "李芳", "relation": "母亲"}}],
                    "location": "上海市-家中书房",
                    "decompose": 0
                }},
                {{
                    "event_id": "5-2",
                    "name": "讨论预算分配方案",
                    "date": ["2025-01-10"],
                    "type": "Finance",
                    "description": "徐静与父母徐明、李芳在客厅详细讨论各项开支预算分配，确定日常生活费、服装店运营成本、父母医疗费用的优先级和额度",
                    "participant": [{{"name": "徐静", "relation": "自己"}}, {{"name": "徐明", "relation": "父亲"}}, {{"name": "李芳", "relation": "母亲"}}],
                    "location": "上海市-家中客厅",
                    "decompose": 0
                }},
                {{
                    "event_id": "5-3",
                    "name": "制作年度预算表",
                    "date": ["2025-01-11"],
                    "type": "Finance",
                    "description": "根据讨论结果，徐静使用Excel制作详细的2025年度预算表，分解月度支出目标，设置资金预警线",
                    "participant": [{{"name": "徐静", "relation": "自己"}}],
                    "location": "上海市-家中书房",
                    "decompose": 0
                }}
            ]
            
            -- 用户画像 --
            {persona}
            
            -- 待分解事件 --
            {parent_event}
'''

    def llm_call_s(self, prompt: str) -> str:
        """大模型调用（直接输出子事件JSON数组）"""
        #print('call llm')
        response = llm_call(prompt)
        return response

    def _extract_json_from_llm_output(self, llm_output: str) -> List[Dict[str, Any]]:
        """简单处理LLM输出：提取[]包裹的JSON数组（防止无关内容）"""
        # 匹配第一个[到最后一个]之间的所有内容（贪婪匹配，忽略中间无关文本）
        json_pattern = r'\[(.*)\]'  # 关键修改：贪婪匹配，覆盖完整JSON数组
        matches = re.findall(json_pattern, llm_output, re.DOTALL)
        if not matches:
            raise ValueError("未找到JSON数组内容")
        print(matches[0])
        # 解析JSON
        try:
            raw_json = f"[{matches[0]}]"
            # 修复1：补全字段间缺少的逗号（核心修复）
            # 修复2：去除多余的逗号（如最后一个字段后有逗号）
            raw_json = re.sub(r',\s*]', ']', raw_json)
            raw_json = re.sub(r',\s*}', '}', raw_json)
            # 修复3：确保字段名用双引号（替换单引号为双引号）
            raw_json = re.sub(r"'([^']+)'", r'"\1"', raw_json)
            # 修复4：去除JSON中的注释（// 开头的内容）
            raw_json = re.sub(r'//.*?$', '', raw_json, flags=re.MULTILINE)
            # 修复5：去除多余空格和换行（可选，优化格式）
            raw_json = re.sub(r'\s+', ' ', raw_json).strip()
            sub_events = json.loads(raw_json)
            if not isinstance(sub_events, list):
                raise ValueError("提取内容不是数组")
            return sub_events
        except Exception as e:
            raise ValueError(f"JSON解析失败：{str(e)}")

    def _decompose_single_node(self, parent_event: Dict[str, Any]) -> List[Dict[str, Any]]:
        """并行处理单个父事件：生成分解后的子事件列表"""
        print(parent_event)
        parent_id = parent_event["event_id"]
        parent_name = parent_event["name"]
        print(f"正在分解事件：{parent_id} - {parent_name[:30]}...")

        # 1. 生成提示词（传入父事件完整信息）
        parent_event_str = parent_event
        print(parent_event_str)
        prompt = self.template_event_decomposer.format(
            persona=self.persona,
            parent_event=parent_event_str
        )
        #print(prompt)
        # 2. 调用大模型获取子事件JSON
        llm_output = self.llm_call_s(prompt)
        print('-----------------------------')
        print(llm_output)
        print('-----------------------------')
        # 3. 提取并解析JSON（简单处理，仅提取[]内内容）
        try:
            sub_events = self._extract_json_from_llm_output(llm_output)
            # 验证子事件字段完整性
            required_fields = ["event_id", "name", "date", "type", "description", "participant", "location",
                               "decompose"]
            valid_sub_events = []
            for idx, sub_event in enumerate(sub_events):
                missing_fields = [f for f in required_fields if f not in sub_event]
                if missing_fields:
                    print(f"子事件{idx + 1}缺少字段：{missing_fields}，跳过该事件")
                    continue
                # 验证decompose字段取值
                if sub_event["decompose"] not in [0, 1]:
                    sub_event["decompose"] = 0  # 默认为无需分解
                valid_sub_events.append(sub_event)

            print(f"事件分解完成：{parent_id} - 生成{len(valid_sub_events)}个有效子事件")
            return valid_sub_events
        except Exception as e:
            print(f"事件分解失败：{parent_id} - 错误：{str(e)}")
            return []  # 失败时返回空列表，避免中断流程

    def _dfs_parallel_decompose_tree(self, event_nodes: List[Dict[str, Any]], max_workers: int = 10) -> List[
        Dict[str, Any]]:
        """DFS递归分解+并行处理（基于decompose标记判断是否继续）"""
        if not event_nodes:
            return []

        # 步骤1：并行分解当前层级需要继续分解的事件（decompose=1）
        processed_nodes = []
        pending_nodes = []  # 下一层级待分解的事件

        # 筛选需要分解的节点
        nodes_to_decompose = []
        for node in event_nodes:
            if node.get("decompose", 0) == 1:
                nodes_to_decompose.append(node)
            else:
                # 无需分解的节点，直接保留（subevent设为空）
                node["subevent"] = []
                processed_nodes.append(node)

        # 并行处理需要分解的节点
        if nodes_to_decompose:
            print(f"\n当前层级需分解{len(nodes_to_decompose)}个节点，并行处理中...")
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_node = {
                    executor.submit(self._decompose_single_node, node): node
                    for node in nodes_to_decompose
                }

                for future in as_completed(future_to_node):
                    parent_node = future_to_node[future]
                    try:
                        sub_events = future.result()
                        # 为父节点添加子事件列表
                        parent_node["subevent"] = sub_events
                        processed_nodes.append(parent_node)
                        # 收集下一层级需要分解的子事件（decompose=1）
                        pending_nodes.extend([sub for sub in sub_events if sub["decompose"] == 1])
                    except Exception as e:
                        print(f"处理节点{parent_node['event_id']}时异常：{str(e)}")
                        parent_node["subevent"] = []
                        processed_nodes.append(parent_node)

        # 步骤2：递归分解下一层级的事件
        if pending_nodes:
            print(f"\n发现{len(pending_nodes)}个子节点需要继续分解，进入下一层递归...")
            decomposed_subtrees = self._dfs_parallel_decompose_tree(pending_nodes, max_workers)

            # 替换子节点为分解后的完整子树（通过event_id匹配）
            for processed_node in processed_nodes:
                original_sub_events = processed_node.get("subevent", [])
                updated_sub_events = []
                for sub_event in original_sub_events:
                    # 查找是否有分解后的子树
                    matched = False
                    for decomposed_subtree in decomposed_subtrees:
                        if decomposed_subtree["event_id"] == sub_event["event_id"]:
                            updated_sub_events.append(decomposed_subtree)
                            matched = True
                            break
                    if not matched:
                        updated_sub_events.append(sub_event)
                processed_node["subevent"] = updated_sub_events

        return processed_nodes

    def event_decomposer(self, events: List[Dict[str, Any]], file: str, max_workers: int = 10):
        """
        主函数：DFS并行分解事件为树形结构（基于decompose标记自动终止）
        Args:
            events: 原始事件列表（需包含 event_id、name、date 等基础字段）
            file: 结果保存路径前缀
            max_workers: 并行线程数（IO密集型可设10-20）
        """
        # 验证原始事件格式
        required_fields = ["event_id", "name"]
        for i, event in enumerate(events):
            missing_fields = [f for f in required_fields if f not in event]
            if missing_fields:
                raise ValueError(f"原始事件{i + 1}缺少必填字段：{','.join(missing_fields)}")
            # 为原始事件添加默认字段（若缺失）
            event.setdefault("type", "Other")
            event.setdefault("description", event["name"])
            event.setdefault("participant", [{"name": "自己", "relation": "自己"}])
            event.setdefault("location", "未知")
            event.setdefault("decompose", 1)  # 原始事件默认需要分解
            event.setdefault("subevent", [])

        print(f"开始分解事件树，共{len(events)}个原始事件，并行线程数：{max_workers}")

        # 核心：DFS+并行分解
        self.decompose_schedule = self._dfs_parallel_decompose_tree(events, max_workers)

        # 保存完整树形结果
        output_path = f"{file}event_decompose_dfs.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.decompose_schedule, f, ensure_ascii=False, indent=2)

        print(f"\n事件树分解完成！结果已保存到：{output_path}")

        # 统计原子事件总数（decompose=0且subevent为空）
        def count_atomic_events(nodes: List[Dict[str, Any]]) -> int:
            count = 0
            for node in nodes:
                if node["decompose"] == 0 and not node.get("subevent", []):
                    count += 1
                count += count_atomic_events(node.get("subevent", []))
            return count

        atomic_count = count_atomic_events(self.decompose_schedule)
        print(f"原子事件总数：{atomic_count}")

class Scheduler:
    def __init__(self,persona,file_path):
        """初始化日程调度器，创建空的日程存储结构"""
        self.schedule = {}  # 存储日程数据，格式如{"2025-01-01":["event1","event2"],...}
        # 保存原始事件信息，包括所有可能的时间范围
        self.raw_events = []
        self.persona = persona
        self.relation = ""
        self.final_schedule = {}
        self.decompose_schedule = {}
        d = persona
        if type(persona)==str:
            d = json.loads(persona)
        self.relation = d['relation']
        self.name = d['name']
        self.summary=""
        self.file_path = file_path
        self.percentage = {}
    def load_from_json(self, json_data,persona,percentage):
        """
        从JSON数据加载日程，支持起止时间为数组的格式

        参数:
            json_data: 符合指定格式的JSON数据列表
                       每个元素包含"主题事件"和"起止时间"，其中"起止时间"是数组
        """
        self.raw_events = json_data
        self.persona = persona
        self.relation = persona['relation']
        self.percentage = percentage

    def load_finalevent(self,json):
        self.final_schedule = json
        return True

    def save_to_json(self):
        """
        将日程转换为JSON格式

        返回:
            符合指定格式的JSON数据列表，其中起止时间为数组
        """
        return self.raw_events

    def llm_call_sr(self,prompt,record=0):
        """调用大模型的函数"""
        res = llm_call_reason(prompt,context2,record=record)
        return res

    def llm_call_s(self,prompt,record=0):
        """调用大模型的函数"""
        res = llm_call(prompt,context2,record=record)
        return res

    def handle_profie(self,persona):
        prompt = template_analyse.format(persona=persona)
        res = llm_call(prompt, context,1)
        #print(res)
        pattern = r'<percent>(.*?)<\/percent>'
        match = re.search(pattern, res, re.IGNORECASE | re.DOTALL)
        json_str = match.group(1).strip()
        #print(json_str)
        if json_str:
            percent_dict = json.loads(json_str)
            self.percentage = percent_dict
        print(self.percentage)
        pattern = r'<analyse>(.*?)<\/analyse>'
        match = re.search(pattern, res, re.IGNORECASE | re.DOTALL)
        persona_summary = match.group(1).strip()
        self.summary = persona_summary
        print(self.summary)
        with open(self.file_path + "process/percent.json", "w", encoding="utf-8") as f:
            json.dump(self.percentage, f, ensure_ascii=False, indent=2)
        return persona_summary

    def genevent_yearterm(self,persona):
        #基于persona提取重点+分配不同类型事件概率
        summary = self.handle_profie(persona)
        prompt = template_yearterm_eventgen.format(summary=summary)
        #第一轮生成，基于不同类别和概率。100件
        res1 = llm_call(prompt, context, 1)
        print(res1)
        prompt = template_yearterm_complete.format(persona=persona)
        #第二轮，基于画像，挖掘没在重点中的细节。100件
        res2 = llm_call(prompt, context, 1)
        print(res2)
        prompt = template_yearterm_complete_2.format()
        #第三轮，聚焦类别百分比平衡和人类共性事件。100件
        res3 = llm_call(prompt, context, 1)
        print(res3)
        prompt = template_yearterm_complete_3.format(summary=summary)
        #第四轮，聚焦波折、困难、负面事件。20件
        res4 = llm_call(prompt, context)
        print(res4)
        return [res1, res2, res3, res4]

    def extract_events_by_categories(self, file_path, prob):
        CATEGORIES = [
            "Career & Education",
            "Relationships",
            "Living Situation",
            "Social & Lifestyle",
            "Finance",
            "Self Satisfy/Care & Entertainment",
            "Personal Growth",
            "Health & Well-being",
            "Unexpected Events",
            "Other"
        ]

        # 读取文件内容
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 初始化类别字典，存储事件列表和数量
        event_data = {
            category: {
                'events': [],  # 存储事件列表
                'count': 0  # 事件数量统计
            } for category in CATEGORIES
        }
        current_category = None

        # 按行处理内容
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 检查是否为类别标题行（宽松匹配）
            cleaned_line = line.strip('*').strip('#').strip('+').strip()  # 去除常见标记符号
            core_category = cleaned_line.split('（')[0].split('(')[0].strip()  # 去除括号及内部内容

            # 宽松匹配类别（忽略大小写）
            matched_category = None
            for cat in CATEGORIES:
                if core_category.lower() == cat.lower():
                    matched_category = cat
                    break

            if matched_category:
                current_category = matched_category
                continue
            # 检查是否是其他可能的标题格式（包含"件"字的标题）
            elif '件' in cleaned_line and any(cat.lower() in cleaned_line.lower() for cat in CATEGORIES):
                for cat in CATEGORIES:
                    if cat.lower() in cleaned_line.lower():
                        current_category = cat
                        break
                else:
                    current_category = "Other"
                continue

            # 处理事件行（非标题行且当前有活跃类别）
            if current_category:
                event = line
                # 去除可能的序号（如数字+.开头）
                if event and event[0].isdigit() and ('.' in event[:5] or '、' in event[:5]):
                    event = event.split('. ', 1)[1] if '. ' in event else event.split('、', 1)[
                        1] if '、' in event else event

                event_data[current_category]['events'].append(event)
                event_data[current_category]['count'] += 1

        # -------------------------- 新增：基于prob调整事件百分比（仅删除，不新增） --------------------------
        def parse_percentage(s):
            """辅助函数：解析百分比字符串为小数（0-1），无效返回None"""
            if not isinstance(s, str) or '%' not in s:
                return None
            try:
                num = float(s.strip().strip('%'))
                return num / 100.0 if 0 <= num <= 100 else None  # 仅允许0-100%
            except (ValueError, TypeError):
                return None

        # 第一步：验证prob参数有效性（严格校验，避免无效调整）
        prob_valid = False
        percentage_dict = {}  # 解析后的有效百分比（小数）
        valid_cats = [cat for cat in CATEGORIES if event_data[cat]['count'] > 0]  # 有事件的类别

        if isinstance(prob, dict) and prob:
            # 1. prob的key必须与CATEGORIES完全一致（无多余/缺失）
            if set(prob.keys()) == set(CATEGORIES):
                total_p = 0.0
                all_valid = True
                # 2. 解析并验证每个百分比
                for cat, p_str in prob.items():
                    p = parse_percentage(p_str)
                    if p is None:
                        all_valid = False
                        break
                    percentage_dict[cat] = p
                    total_p += p
                # 3. 总百分比需在95%-105%（允许微小误差）
                # 4. 有事件的类别，目标占比不能为0（否则无法匹配）
                has_valid_target = all(
                    percentage_dict[cat] > 0 for cat in valid_cats
                ) if valid_cats else True

                if all_valid and 0.95 <= total_p <= 1.05 and has_valid_target:
                    prob_valid = True

        # 第二步：仅当prob有效时，执行调整（仅删除事件）
        if prob_valid:
            print(prob)
            # 核心逻辑：计算每个类别的「理论总事件数上限」= 该类别现有数量 ÷ 目标占比
            # 总上限取最小值（确保所有类别按此上限计算的目标数量 ≤ 现有数量，仅需删除）
            total_upper_bounds = []
            for cat in CATEGORIES:
                cat_count = event_data[cat]['count']
                cat_p = percentage_dict[cat]

                if cat_p == 0:
                    # 目标占比为0的类别，理论上限为0（需删除所有事件）
                    total_upper_bounds.append(10000)
                else:
                    # 有事件的类别：按现有数量反推总上限；无事件的类别：上限设为无穷大（不影响最小值）
                    upper_bound = cat_count / cat_p if cat_count > 0 else float('inf')
                    total_upper_bounds.append(upper_bound)

            # 最终总事件数上限（取所有理论上限的最小值，确保所有类别都能满足“仅删除”）
            final_total_upper = min(total_upper_bounds) if total_upper_bounds else 300
            final_total_upper = max(final_total_upper, 0)  # 避免负数

            if final_total_upper > 0:
                # 按总上限计算每个类别的目标数量（四舍五入，且不超过现有数量）
                for cat in CATEGORIES:
                    cat_p = percentage_dict[cat]
                    cat_count = event_data[cat]['count']
                    # 目标数量 = 总上限 × 目标占比（四舍五入）
                    target_count = round(final_total_upper * cat_p)
                    # 实际保留数量：不超过现有数量，且不小于0
                    actual_count = min(target_count, cat_count)
                    actual_count = max(actual_count, 0)

                    # 保留前N个事件，删除后面的（符合“先去除后面”要求）
                    event_data[cat]['events'] = event_data[cat]['events'][:actual_count]
                    event_data[cat]['count'] = actual_count

        # -------------------------- 新增功能结束 --------------------------


        return event_data

    def standard_data(self,data,type):
        # 相似性检查合并+标准化
        # name
        # date
        # id
        # type
        print(data)
        #合理性校检：画像匹配度、现实合理性、日期、频率与间隔、相似事件
        prompt = template_check.format(persona=self.persona, content=data)
        res1 = llm_call(prompt, context, 1)
        print(res1)
        #基于合理性校检结果作修改、删除
        prompt = template_process.format(content=data)
        res1 = llm_call(prompt, context)
        print(res1)
        data1 = json.loads(res1)
        instruction = {
            "Career & Education": "工作内容是否都涉及到，工作可能会有什么长期项目或任务或成果",
            "Relationships": "思考已有人物关系是否有没有涉及的",
            "Living Situation": "思考生活，家庭相关事件",
            "Social & Lifestyle": "思考社交，爱好，出行等相关事件",
            "Finance": "思考资产、财务、买卖、消费等相关事件",
            "Self Satisfy/Care & Entertainment": "思考娱乐，自我满足，自我追求等相关事件",
            "Personal Growth": "更多样化的事件",
            "Health & Well-being": "更多样化的事件",
            "Unexpected Events": "更多样化的事件",
            "Other": "更多样化的事件"
        }
        #多样性新增事件，补充删除事件
        prompt = template_process_2.format(type=type, content=res1, persona=self.persona, instruction=instruction[type])
        res2 = llm_call(prompt, context)
        print(res2)
        data2 = json.loads(res2)
        data = data1 + data2
        print(data)

        def split_array(arr, chunk_size=20):
            # 列表推导式：从0开始，每30个元素取一次
            return [arr[i:i + chunk_size] for i in range(0, len(arr), chunk_size)]

        res = []
        for i in split_array(data):
            #标准化事件schema，填充participant和location。
            prompt = template_process_1.format(content=i, relation=self.relation)
            res1 = llm_call(prompt, context)
            print(res1)
            res1 = json.loads(res1)
            res = res + res1
        print(res)
        return res

    def print_category_stats(self,event_data, title="事件数量统计"):
        """
        打印每个类别的事件数量和占比

        参数:
            event_data: 事件数据字典（格式同函数返回值）
            title: 统计标题（区分调整前/后）
        """
        CATEGORIES = [
            "Career & Education",
            "Relationships",
            "Living Situation",
            "Social & Lifestyle",
            "Finance",
            "Self Satisfy/Care & Entertainment",
            "Personal Growth",
            "Health & Well-being",
            "Unexpected Events",
            "Other"
        ]
        print("\n" + "=" * 50)
        print(f"【{title}】")
        print("=" * 50)

        total = sum(item['count'] for item in event_data.values())
        print(f"总事件数：{total}\n")

        # 按类别打印（保持CATEGORIES顺序）
        for category in CATEGORIES:
            count = event_data[category]['count']
            ratio = (count / total * 100) if total > 0 else 0.0
            # 格式化输出：类别名称（对齐）、数量、占比（保留2位小数）
            print(f"{category:<30} | 数量：{count:<3} | 占比：{ratio:.2f}%")

        print("=" * 50 + "\n")

    def process_single_category(self,args: tuple) -> List:
        """单个类别的处理函数（供并行调用）"""
        category, data = args  # 解包参数（因为executor提交只能传单个参数）
        print(f"【{category}】（共{data['count']}件）")
        try:
            res = self.standard_data(data['events'], category)
            print(f"【{category}】（生成{len(res)}件）")
            return res
        except Exception as e:
            print(f"【{category}】处理失败：{str(e)}")
            return []

    def parallel_process_event_stats(self,event_stats: Dict[str, Dict], file_path: str):
        """
        并行处理事件统计数据的主函数

        Args:
            event_stats: 输入数据，格式为 {category: {'count': int, 'events': List}}
            file_path: 输出文件的基础路径（对应原代码的 self.file_path）
        """
        result = []
        # 限制最大进程数（避免资源耗尽，可根据实际调整）
        max_workers = min(10, multiprocessing.cpu_count() * 2)

        # 准备并行任务参数（将category和data打包成元组）
        task_args = [(category, data) for category, data in event_stats.items()]

        # 进程池并行执行
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务并收集结果
            futures = executor.map(self.process_single_category, task_args)

            # 合并所有结果（map会按提交顺序返回，as_completed按完成顺序，按需选择）
            for res in futures:
                result.extend(res)  # 高效合并结果

        # 统一写入文件（避免并行写入冲突）
        output_path = f"{file_path}event_1.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    def main_gen_event(self):
        txt_file_path = self.file_path+"process/output.txt"
        if not os.path.exists(txt_file_path):
            res = self.genevent_yearterm(self.persona)#persona处理+三轮事件生成
            with open(txt_file_path, "w", encoding="utf-8") as file: #记录，防止丢失
                for s in res:
                    file.write(s + "\n")  # 每个字符串后加换行符，实现分行存储
        if os.path.exists(self.file_path + "process/percent.json"):
            self.percentage = read_json_file(self.file_path + "process/percent.json")
        # 提取事件并生成字符串数组
        event_stats = self.extract_events_by_categories(txt_file_path,self.percentage)#从记录文件中提取事件
        self.print_category_stats(event_stats)
        # result = []
        # for category, data in event_stats.items():#逐类别做json格式标准化+合理性校检
        #     print(f"【{category}】（共{data['count']}件）")
        #     res = self.standard_data(data['events'],category)
        #     print(f"【{category}】（生成{len(res)}件）")
        #     result = result + res
        #     with open(self.file_path+"process/event_1.json", "w", encoding="utf-8") as f:
        #         json.dump(result, f, ensure_ascii=False, indent=2)
        self.parallel_process_event_stats(
            event_stats=event_stats,
            file_path=self.file_path+"process/"  # 替换为你的实际文件路径
        )


    def extract_events_by_month(self,target_month):
        """
        提取目标月份（如2）及之前的事件
        :param target_month: 目标月份（整数，1-12）
        :return: (x月事件字典, x月之前事件字典)
        """
        month_events = {}  # x月事件
        before_events = {}  # x月之前事件

        for date_str, events in self.schedule.items():
            # 解析年份和月份
            year = int(date_str.split("-")[0])
            month = int(date_str.split("-")[1])

            # 仅处理2025年数据（与您的日程年份一致）
            if year != 2025:
                continue

            if month == target_month:
                month_events[date_str] = events
            elif month < target_month or month > target_month:
                before_events[date_str] = events

        return month_events, before_events
    def extract_events_by_month2(self,target_month):
        """
        提取目标月份（如2）的事件
        :param target_month: 目标月份（整数，1-12）
        :return: (x月事件字典)
        """
        month_events = {}  # x月事件
        before_events = {}  # x月之前事件
        after_events = {}
        for date_str, events in self.final_schedule.items():
            # 解析年份和月份
            year = int(date_str.split("-")[0])
            month = int(date_str.split("-")[1])

            # 仅处理2025年数据（与您的日程年份一致）
            if year != 2025:
                continue

            elif month == target_month-1:
                before_events[date_str] = events


        for date_str, events in self.schedule.items():
            # 解析年份和月份
            year = int(date_str.split("-")[0])
            month = int(date_str.split("-")[1])

            # 仅处理2025年数据（与您的日程年份一致）
            if year != 2025:
                continue

            elif month == target_month:
                month_events[date_str] = events
            elif month == target_month+1:
                after_events[date_str] = events
        return month_events, before_events,after_events\

    def add_event(self, event_name, time_ranges):
        """
        添加单个事件

        参数:
            event_name: 事件名称
            time_ranges: 时间范围数组，每个元素为"YYYY-MM-DD至YYYY-MM-DD"格式的字符串
        """
        # 保存原始事件信息
        self.raw_events.append({
            "主题事件": event_name,
            "起止时间": time_ranges.copy()
        })

        # 解析每个时间范围
        for time_range in time_ranges:
            start_str, end_str = time_range.split("至")
            start_date = datetime.strptime(start_str.strip(), "%Y-%m-%d").date()
            end_date = datetime.strptime(end_str.strip(), "%Y-%m-%d").date()

            current_date = start_date
            while current_date <= end_date:
                date_str = current_date.strftime("%Y-%m-%d")
                if date_str not in self.schedule:
                    self.schedule[date_str] = []
                self.schedule[date_str].append(event_name)
                current_date += timedelta(days=1)

        self.schedule = dict(sorted(self.schedule.items()))

    def split_and_convert_events(self,events):
        """
        将包含多日期的事件拆分为独立事件，并转换date字段为start_time和end_time
        处理逻辑：
        - 若date是数组（如["2025-01-01", "2025-01-05至2025-01-06"]），每个元素对应一个独立事件
        - 单个日期（无"至"）：start_time = end_time
        - 日期范围（有"至"）：分割为start_time和end_time
        :param events: 原始事件列表（date为数组，元素为单日期或日期范围）
        :return: 拆分并转换后的事件列表（每个事件对应一次发生）
        """
        processed_events = []
        for event in events:
            # 遍历date数组中的每个发生日期/范围
            for date_item in event["date"]:
                # 复制原事件基础信息（避免修改原始数据）
                new_event = event.copy()
                # 移除原date字段（后续替换为start/end）
                del new_event["date"]
                # 处理当前日期项
                date_str = date_item.strip()
                # 单日期（无"至"）
                if "至" not in date_str:
                    new_event["start_time"] = date_str
                    new_event["end_time"] = date_str
                # 日期范围（有"至"）
                else:
                    parts = date_str.split("至")
                    new_event["start_time"] = parts[0].strip()
                    new_event["end_time"] = parts[1].strip() if len(parts) > 1 else parts[0].strip()
                # 添加到结果列表
                processed_events.append(new_event)
        return processed_events

    def sort_and_add_event_id(self,events):
        import re

        def get_start_time(text):
            """
            从文本中提取XX-XX-XX格式的日期（支持年-月-日，年可2位或4位）
            匹配规则：
            - 月：01-12，日：01-31
            - 年：2位（如25-01-08）或4位（如2025-01-08）
            示例：从"时间：2025-01-08 会议"中提取"2025-01-08"
            :param text: 可能包含日期的文本字符串
            :return: 提取到的XX-XX-XX格式日期字符串；若无则返回空字符串
            """
            # 正则匹配XX-XX-XX：年（2或4位数字）-月（2位）-日（2位）
            date_pattern = r"\b(\d{2}|\d{4})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])\b"
            match = re.search(date_pattern, text)
            return match.group(0) if match else ""
        """
        按start_time（"YYYY-MM-DD"格式）升序排序，为每个事件添加event_id
        :param events: 经split_and_extract_events处理后的事件列表
        :return: 带event_id的排序后事件列表
        """
        # "YYYY-MM-DD"格式可直接按字符串排序（无需转datetime），效率高且结果准确
        sorted_events = sorted(events, key=lambda x: get_start_time(x["start_time"]))

        # 分配event_id（从1开始递增）
        for idx, event in enumerate(sorted_events, start=1):
            event["event_id"] = idx

        return sorted_events
    def filter_events_by_date(self,processed_events, target_date):
        """
        从拆分后的事件列表中，抽取时间范围包含目标日期的事件
        :param processed_events: 经split_and_convert_events处理后的事件列表
        :param target_date: 目标日期，格式为"YYYY-MM-DD"
        :return: 符合条件的事件列表
        """
        try:
            target = datetime.strptime(target_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError("目标日期格式错误，请使用'YYYY-MM-DD'")

        filtered = []
        for event in processed_events:
            start = datetime.strptime(event["start_time"], "%Y-%m-%d")
            end = datetime.strptime(event["end_time"], "%Y-%m-%d")
            if start <= target <= end:
                filtered.append(event)
        return filtered

    def get_events_by_month(self,events, target_year, target_month):
        def extract_date(date_str):
            """从start_time/end_time中提取YYYY-MM-DD格式日期（兼容含文本描述的情况）"""
            # 正则匹配YYYY-MM-DD格式（优先提取完整日期）
            pattern = r"\b20\d{2}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])\b"
            match = re.search(pattern, date_str)
            if match:
                return match.group(0)
            # 若未找到完整日期，返回空（后续视为单日期事件处理）
            return ""
        """
        提取与目标月份（target_year年target_month月）有时间重叠的所有事件
        :param events: 事件列表（含start_time和end_time字段）
        :param target_year: 目标年份（如2025）
        :param target_month: 目标月份（如1表示1月，6表示6月）
        :return: 符合条件的事件列表
        """
        # 计算目标月份的第一天和最后一天（用于判断时间重叠）
        # 月份最后一天：若为12月则次年1月1日减1天，否则当月+1月的1日减1天
        if target_month == 12:
            next_month_first_day = datetime(target_year + 1, 1, 1)
        else:
            next_month_first_day = datetime(target_year, target_month + 1, 1)
        target_month_start = datetime(target_year, target_month, 1)
        target_month_end = next_month_first_day - timedelta(days=1)

        result = []
        for event in events:
            # 提取事件的起止日期（处理含文本的情况）
            start_str = extract_date(event["start_time"])
            end_str = extract_date(event["end_time"])

            # 处理无法提取日期的情况（默认视为单日期事件，取文本中的年份和月份）
            if not start_str:
                start_str = event["start_time"]  # 保留原始文本用于提取年份
            if not end_str:
                end_str = start_str  # 无结束日期则默认与开始日期相同

            # 尝试解析事件的起止日期（兼容纯文本，提取年份和月份）
            try:
                # 优先按YYYY-MM-DD解析
                event_start = datetime.strptime(start_str, "%Y-%m-%d")
                event_end = datetime.strptime(end_str, "%Y-%m-%d")
            except:
                # 若解析失败，提取年份和月份（默认当月1日至当月最后一天）
                # 从文本中提取年份（优先20xx）
                year_match = re.search(r"20\d{2}", start_str)
                event_year = int(year_match.group()) if year_match else target_year
                # 从文本中提取月份（若未找到则默认事件在目标月份）
                month_match = re.search(r"(0?[1-9]|1[0-2])", start_str)
                event_month = int(month_match.group()) if month_match else target_month
                # 构造事件的起止日期（当月1日至当月最后一天）
                event_start = datetime(event_year, event_month, 1)
                if event_month == 12:
                    event_end = datetime(event_year, 12, 31)
                else:
                    event_end = datetime(event_year, event_month + 1, 1) - timedelta(days=1)

            # 判断事件时间范围与目标月份是否有重叠
            # 重叠条件：事件开始时间 <= 目标月份结束 且 事件结束时间 >= 目标月份开始
            if event_start <= target_month_end and event_start >= target_month_start:
                result.append(event)

        return result

    def get_month_calendar(self,year, month):
        """
        生成指定年月的每日星期几和节日对照表
        :param year: 年份（如2025）
        :param month: 月份（如1-12）
        :return: 列表，每个元素为{"date": "YYYY-MM-DD", "weekday": "星期X", "holiday": "节日名称或空"}
        """
        # 初始化中国节假日数据集
        cn_holidays = holidays.China(years=year)

        # 获取当月第一天和最后一天
        first_day = datetime(year, month, 1)
        # 计算当月最后一天（下个月第一天减1天）
        if month == 12:
            next_month_first = datetime(year + 1, 1, 1)
        else:
            next_month_first = datetime(year, month + 1, 1)
        last_day = (next_month_first - timedelta(days=1)).day

        calendar = []
        for day in range(1, last_day + 1):
            current_date = datetime(year, month, day)
            date_str = current_date.strftime("%Y-%m-%d")

            # 转换星期几（0=周一，6=周日 → 调整为"星期一"至"星期日"）
            weekday_map = {0: "星期一", 1: "星期二", 2: "星期三", 3: "星期四",
                           4: "星期五", 5: "星期六", 6: "星期日"}
            weekday = weekday_map[current_date.weekday()]

            # 获取节日（优先法定节假日，再传统节日）
            holiday = cn_holidays.get(current_date, "")

            calendar.append({
                "date": date_str,
                "weekday": weekday,
                "holiday": holiday
            })

        return calendar

    def event_decomposer(self,events,file):
        # def split_array(arr, chunk_size=30):
        #     # 列表推导式：从0开始，每30个元素取一次
        #     return [arr[i:i + chunk_size] for i in range(0, len(arr), chunk_size)]
        # t = 0
        # ans = []
        # for i in split_array(events,5):
        #     #对其中的事件进行推理、扩展、分解，形成原子事件序列
        #     prompt = template_event_decomposer.format(content=i, persona=self.persona)
        #     res = self.llm_call_s(prompt,1)
        #     print(res)
        #     #结构化生成，形成树形结构。
        #     prompt = template_process_3.format()
        #     res = self.llm_call_sr(prompt)
        #     print(res)
        #     data = json.loads(res)
        #     ans += data
        #     #保存
        #     with open(file+"event_decompose.json", "w", encoding="utf-8") as f:
        #         json.dump(ans, f, ensure_ascii=False, indent=2)
        # self.decompose_schedule = ans
        obj = EventTree(persona=self.persona)
        # 调用并行分解函数
        obj.event_decomposer(
            events=events,
            file=file,
            max_workers=10  # 并行线程数（根据网络带宽和大模型QPS调整）
        )


    def event_schedule(self,data,month):
        prompt = template_process_4.format(content=data, persona=self.persona,calendar=self.get_month_calendar(2025,month))
        res = self.llm_call_sr(prompt)
        print(res)
        data = json.loads(res)
        return data

    def merge_events_events(self,events_data):
        """
        处理事件数据，保留event_id小于500且首次出现的事件

        参数:
            events_data (list): 原始事件列表，每个元素为包含event_id的字典

        返回:
            list: 处理后的事件列表（去重且event_id < 500）
        """
        seen_ids = set()  # 记录已出现的event_id
        processed_events = []

        for event in events_data:
            # 提取event_id，若不存在则跳过（容错处理）
            event_id = event.get("event_id")
            if event_id is None:
                continue

            # 筛选条件：event_id < 500 且 未出现过
            if event_id < 500 and event_id not in seen_ids:
                seen_ids.add(event_id)
                processed_events.append(event)

        return processed_events

    @staticmethod
    def _process_single_month_static(args: tuple) -> List[Any]:
        """静态方法：供多进程调用（避免依赖类实例）"""
        # 解包参数：(self实例, 原始数据, 月份)
        self_obj, data, month = args
        print(f"【2025年{month}月】开始处理")
        try:
            month_events = self_obj.get_events_by_month(data, 2025, month)
            scheduled_events = self_obj.event_schedule(month_events, month)
            print(f"【2025年{month}月】完成，生成{len(scheduled_events)}件")
            return scheduled_events
        except Exception as e:
            print(f"【2025年{month}月】处理失败：{str(e)}")
            return []

    def parallel_process_monthly_events(self, data: Dict[str, Any]):
        """并行处理1-12月主题事件（类方法入口）"""
        final_schedule = []
        max_workers = min(12, multiprocessing.cpu_count() * 2)

        # 准备任务参数：(self实例, 原始数据, 月份)
        task_args = [(self, data, month) for month in range(1, 13)]

        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            future_to_month = {
                executor.submit(self._process_single_month_static, args): args[2]
                for args in task_args
            }

            for future in as_completed(future_to_month):
                month = future_to_month[future]
                try:
                    final_schedule.extend(future.result())
                except Exception as e:
                    print(f"【2025年{month}月】收集失败：{str(e)}")

        # 保存结果到文件和实例属性
        output_path = f"{self.file_path}process/event_2.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(final_schedule, f, ensure_ascii=False, indent=2)

        self.final_schedule = final_schedule
        print(f"所有月份处理完成，共生成{len(final_schedule)}件主题事件")

    def main_schedule_event(self,data,file):
        data = self.split_and_convert_events(data)#将重复事件分解为单个事件
        data = self.sort_and_add_event_id(data)#按起始时间顺序为事件分配id
        self.parallel_process_monthly_events(data=data)
        # res = []
        # for i in range(1,13):
        #     rest = self.event_schedule(self.get_events_by_month(data,2025,i),i) #逐月规划主题事件
        #     res+=rest
        #     with open(file+"process/event_2.json", "w", encoding="utf-8") as f: #保存主题事件
        #         json.dump(res, f, ensure_ascii=False, indent=2)
        # self.final_schedule = res

    def main_decompose_event(self,data,file):
        # res = read_json_file(file+"event.json")
        res = self.merge_events_events(data) #做预处理，防止主题事件文件出错
        res = self.split_and_convert_events(res)
        res = self.sort_and_add_event_id(res)
        #分解事件
        self.event_decomposer(res,file)


# 使用示例
if __name__ == "__main__":
    # 创建调度器实例
    persona = read_json_file('../data/persona.json')
    file_path = '../data/'
    scheduler = Scheduler(file_path=file_path,persona=persona)
    # scheduler.handle_profie(scheduler.persona)
    scheduler.main_gen_event()












