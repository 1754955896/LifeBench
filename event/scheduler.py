# -*- coding: utf-8 -*-
#1）调整日程使其合理  2）消解冲突  3）事件插入+后续调整  4）事件插入  5）事件粒度对齐
import json
import multiprocessing
import os
import threading
from typing import Dict, List, Any
from concurrent.futures import ProcessPoolExecutor, as_completed, ThreadPoolExecutor
from utils.IO import *
from datetime import datetime, timedelta
from utils.llm_call import *
from event.templates import *
import re
import holidays  # 需安装：pip install holidays


class EventTree:
    def __init__(self, persona: str):
        self.persona = persona
        self.decompose_schedule = []  # 最终分解结果（完整树形结构）

        # 第一层分解模板：原事件→阶段事件/原子事件
        self.template_level1 = '''
            基于以下待分解事件，完成推理、扩展、分解，并直接输出子事件JSON数组（无需额外分析文本），目标是将事件分解为粒度小于一天的原子事件：
            
            1. 事件扩展：可参考事件描述进行分解，但原事件可能不完整，不具体，甚至不合理，需合理推理**前置（准备/规划/预定）、后续（收尾/影响）及相关事件**，补充后使其完整丰富。
            2. 粒度与阶段分解规则：
               - 阶段事件：针对跨度长（超过7天）、流程复杂、重要性高的原事件，可拆分为「阶段性子事件」（如项目立项→执行→验收、旅行准备→行程执行→收尾），等后续再分解为粒度为一天的原子事件。
                 - 阶段事件特征：date格式为跨天区间（如["2025-01-01至2025-01-15"]），覆盖一个完整阶段的时间范围，decompose=1，表示其后续将被递归分解。
                 - 阶段划分原则：按「时间顺序+流程逻辑」拆分，每个阶段聚焦一个核心目标，避免阶段重叠或遗漏。注意，如果原事件时间范围小于一天，则不用拆分为阶段事件，直接拆分为原子事件。
               - 原子事件：粒度≤1天，date格式为当天日期（如["2025-01-01"]）。具体可执行，发生时间可超出原事件起止时间；多次发生需拆分为多个日期（如["2025-01-01","2025-02-01"]而非["2025-01-01至2025-02-01"]），decompose=0（无需继续分解）。
               - **注意，不可以输出空数组，如果原事件很简单，你也要分解为不同的原子事件，或推理相关后续/前置事件，只不过都为粒度小于1天的原子事件，decompose=0即可。**
            3. 递归分解约束：
               - 分解的子事件数量**严格控制在10个以内**（建议3-8个，避免过度拆分）。
               - 事件ID中的'-'代表层级，每多一个'-'表示多一层分解。
               - **如果你分解出的子事件为阶段事件，date格式为跨天区间（如["2025-01-01至2025-01-15"]），则其decompose一定为1。**
               - **如果分解出的子事件为原子事件，date格式为当天日期（如["2025-01-01"]），则其decompose一定为0。**
            4. 时间范围规则：
               - 第一层分解的子事件时间范围**可以超出**父事件规定的时间范围（允许前置准备和后续收尾事件）。
               - 同一父事件的子事件时间范围应避免重叠（除非有明确的并行执行逻辑）。
            5. 分解策略：
               - 分解需多样化：并非所有事件都需经过准备/规划流程，同一类事件在不同场景下流程可不同。
               - 时间分布：无需均匀分布事件，按真实场景合理安排（持续时间长不代表每天都有相关动作）；阶段事件的时间区间需覆盖原事件核心流程，原子事件可穿插在阶段内。
            6. 合理性优化：可修改原事件不合理信息，避免事件间安排冲突，确保描述真实丰富；阶段事件的时间区间需衔接自然，无明显断层。
            
            --- 输出格式强制要求 ---
            1. **仅返回JSON数组（直接子事件列表），以[]开头结尾，无任何额外文本（包括分析、注释、代码块标记）。**
            2. 每个子事件必须包含以下字段（缺一不可，语法严格正确）：
               - event_id：格式为「父事件ID-序号」（如父ID=1，子事件ID=1-1、1-2），确保层级关联。
               - name：事件名称（简洁明了）。
               - date：时间数组（单个日期/多个日期，粒度≤1天；跨天事件用"至"连接，如["2025-01-01至2025-01-03"]）。
               - type：取值范围（必选其一）：Career、Education、Relationships、Family&Living Situation、Personal Life、Finance、Health、Unexpected Events、Other。
               - description：事件详细描述（包含执行动作、目的、场景）。
               - participant：参与者数组，格式：[{{"name":"姓名","relation":"关系"}}]，优先从用户画像选择；无合适关系可合理编造，自己参与则为[{{"name":"自己名字","relation":"自己"}}]。
               - location：城市+POI类别描述（如"上海市-家中书房"、"杭州市-灵隐寺"）。
               - **decompose：0（原子事件，时间跨度小于一天），1=需要继续分解（时间跨度大于一天）。一定要检查，若子事件date中含至，即跨度大于1天，一定要decompose=1**
            3. JSON语法要求：
               - 字段名用双引号包裹，字段间用逗号分隔（无多余逗号）。
               - 字符串值用双引号包裹，无语法错误。
            
            -- 输出示例 --
            假设待分解事件为：{{"event_id":"1","name":"2025年1月1日至2025年1月15日的欧洲旅行","date":["2025-01-01至2025-01-15"],"type":"Personal Life","description":"为期15天的欧洲旅行","participant":[{{"name":"张三","relation":"自己"}}],"location":"欧洲","decompose":1}}
            输出：
            [{{"event_id":"1-1","name":"旅行前准备","date":["2024-12-15至2024-12-30"],"type":"Personal Life","description":"准备欧洲旅行所需的签证、机票、酒店预订等","participant":[{{"name":"张三","relation":"自己"}}],"location":"北京市-家中","decompose":1}},{{"event_id":"1-2","name":"欧洲旅行行程执行","date":["2025-01-01至2025-01-15"],"type":"Personal Life","description":"按照计划在欧洲各国旅行","participant":[{{"name":"张三","relation":"自己"}}],"location":"欧洲各国","decompose":1}},{{"event_id":"1-3","name":"旅行后整理","date":["2025-01-16"],"type":"Personal Life","description":"整理旅行照片和购买的纪念品","participant":[{{"name":"张三","relation":"自己"}}],"location":"北京市-家中","decompose":0}}]
            
            -- 用户画像 --
            {persona}
            
            -- 待分解事件 --
            {parent_event}
        '''

        # 第二层分解模板：阶段事件→原子事件
        self.template_level2 = '''
            基于以下待分解阶段事件和背景信息，完成推理、分解，并直接输出原子事件JSON数组（无需额外分析文本）：
            
            1. 原子事件要求：粒度≤1天，具体可执行，decompose=0（无需继续分解）。
            2. 粒度与阶段分解规则：
               - 当前为第二层分解（current_depth≥1），必须分解为原子事件（粒度为天）。
               - **原子事件时间跨度不超过1天，多次发生需拆分为多个日期（如["2025-01-01","2025-02-01"]而非["2025-01-01至2025-02-01"]）。**
            3. 递归分解约束：
               - 每一层分解的子事件数量**严格控制在10个以内**（建议3-8个，避免过度拆分）。
               - 事件ID中的'-'代表层级，每多一个'-'表示多一层分解。
            4. 时间范围规则：
               - 第二层分解的子事件时间范围**必须严格包含**在父事件规定的时间范围内（不允许超出）。
               - 同一父事件的子事件时间范围应避免重叠，确保时间安排合理。
               - 原子事件时间跨度不超过1天。
            5. 分解策略：
               - 基于背景信息，确保分解的原子事件与整体事件流程协调一致。
               - 按真实场景合理安排时间分布，确保事件流程连贯。
               - 时间分布：无需均匀分布事件，按真实场景合理安排（持续时间长不代表每天都有相关动作）；原子事件需在父事件时间范围内合理分布。
            6. 合理性优化：确保事件描述真实丰富，与用户画像匹配，避免事件间安排冲突。
            
            --- 输出格式强制要求 ---
            1. **仅返回JSON数组（直接子事件列表），以[]开头结尾，无任何额外文本（包括分析、注释、代码块标记）。**
            2. 每个子事件必须包含以下字段（缺一不可，语法严格正确）：
               - event_id：格式为「父事件ID-序号」（如父ID=1-1，子事件ID=1-1-1、1-1-2），确保层级关联。
               - name：事件名称（简洁明了）。
               - **date：时间数组（单个日期/多个日期，粒度≤1天，日期格式为XXXX-XX-XX,如["2025-01-01"]，不允许使用跨天区间格式（如["2025-01-01至2025-02-01"]）。**
               - type：取值范围（必选其一）：Career、Education、Relationships、Family&Living Situation、Personal Life、Finance、Health、Unexpected Events、Other。
               - description：事件详细描述（包含执行动作、目的、场景）。
               - participant：参与者数组，格式：[{{"name":"姓名","relation":"关系"}}]，优先从用户画像选择；无合适关系可合理编造，自己参与则为[{{"name":"自己名字","relation":"自己"}}]。
               - location：城市+POI类别描述（如"上海市-家中书房"、"杭州市-灵隐寺"）。
               - decompose：0=无需继续分解（原子事件）。
            3. JSON语法要求：
               - 字段名用双引号包裹，字段间用逗号分隔（无多余逗号）。
               - 字符串值用双引号包裹，无语法错误。
            
            -- 输出示例 --
            假设待分解阶段事件为：{{"event_id":"1-1","name":"旅行前准备","date":["2024-12-15至2024-12-30"],"type":"Personal Life","description":"准备欧洲旅行所需的签证、机票、酒店预订等","participant":[{{"name":"张三","relation":"自己"}}],"location":"北京市-家中","decompose":1}}
            输出：
            [{{"event_id":"1-1-1","name":"办理欧洲签证","date":["2024-12-15"],"type":"Personal Life","description":"前往大使馆办理欧洲申根签证","participant":[{{"name":"张三","relation":"自己"}}],"location":"北京市-大使馆","decompose":0}},{{"event_id":"1-1-2","name":"预订机票","date":["2024-12-20"],"type":"Personal Life","description":"预订北京往返欧洲的机票","participant":[{{"name":"张三","relation":"自己"}}],"location":"北京市-家中","decompose":0}},{{"event_id":"1-1-3","name":"预订酒店","date":["2024-12-25"],"type":"Personal Life","description":"预订欧洲旅行期间的酒店","participant":[{{"name":"张三","relation":"自己"}}],"location":"北京市-家中","decompose":0}},{{"event_id":"1-1-4","name":"准备旅行物品","date":["2024-12-30"],"type":"Personal Life","description":"收拾行李，准备旅行所需物品","participant":[{{"name":"张三","relation":"自己"}}],"location":"北京市-家中","decompose":0}}]
            
            -- 用户画像 --
            {persona}
            
            -- 背景信息 --
            {background_info}
            
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

    def _decompose_single_node(self, parent_event: Dict[str, Any], current_depth: int = 0, background_info="") -> List[Dict[str, Any]]:
        """并行处理单个父事件：生成分解后的子事件列表"""
        import copy
        import json
        # 深拷贝父事件，避免并行处理时的引用共享问题
        parent_event_copy = copy.deepcopy(parent_event)
        parent_id = parent_event_copy["event_id"]
        parent_name = parent_event_copy["name"]
        print(f"正在分解事件：{parent_id} - {parent_name[:30]}... 当前深度: {current_depth}")

        # 根据当前深度选择模板
        if current_depth == 0:
            template = self.template_level1
            # 第一层分解不需要背景信息
            prompt = template.format(
                persona=self.persona,
                parent_event=json.dumps(parent_event_copy, ensure_ascii=False),
                current_depth=current_depth
            )
        else:
            template = self.template_level2
            # 第二层分解需要背景信息
            prompt = template.format(
                persona=self.persona,
                parent_event=json.dumps(parent_event_copy, ensure_ascii=False),
                current_depth=current_depth,
                background_info=background_info
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
                if not isinstance(sub_event, dict):
                    continue
                missing_fields = [f for f in required_fields if f not in sub_event]
                if missing_fields:
                    print(f"子事件{idx + 1}缺少字段：{missing_fields}，跳过该事件")
                    continue
                # 验证decompose字段取值
                if "decompose" not in sub_event:
                    sub_event["decompose"] = 0
                else:
                    sub_event["decompose"] = int(sub_event["decompose"])
                    if sub_event["decompose"] not in [0, 1]:
                        sub_event["decompose"] = 0  # 默认为无需分解
                valid_sub_events.append(sub_event)

            print(f"事件分解完成：{parent_id} - 生成{len(valid_sub_events)}个有效子事件")
            return valid_sub_events
        except Exception as e:
            print(f"事件分解失败：{parent_id} - 错误：{str(e)}")
            return []  # 失败时返回空列表，避免中断流程

    def _dfs_parallel_decompose_tree(self, event_nodes: List[Dict[str, Any]], max_workers: int = None, current_depth: int = 0) -> List[
        Dict[str, Any]]:
        """DFS递归分解+并行处理（基于decompose标记判断是否继续）"""
        # 如果未指定max_workers，则使用类配置的线程数
        if max_workers is None:
            max_workers = self.decompose_workers
        if not event_nodes:
            return []

        # 步骤1：并行分解当前层级需要继续分解的事件（decompose=1）
        processed_nodes = []
        pending_nodes = []  # 下一层级待分解的事件

        # 深度检查：如果当前深度>=2（已分解3层），强制所有事件不再继续分解
        if current_depth >= 2:
            for node in event_nodes:
                node["decompose"] = 0
                node["subevent"] = []
                processed_nodes.append(node)
            return processed_nodes

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
                    executor.submit(self._decompose_single_node, node, current_depth): node
                    for node in nodes_to_decompose
                }

                # 保存每个父节点的分解结果，用于传递背景信息
                node_decomposition_results = {}

                for future in as_completed(future_to_node):
                    parent_node = future_to_node[future]
                    try:
                        sub_events = future.result()
                        # 为父节点添加子事件列表
                        parent_node["subevent"] = sub_events
                        processed_nodes.append(parent_node)
                        # 收集下一层级需要分解的子事件（decompose=1）
                        pending_nodes.extend([sub for sub in sub_events if sub["decompose"] == 1])
                        # 保存分解结果
                        node_decomposition_results[parent_node["event_id"]] = sub_events
                    except Exception as e:
                        print(f"处理节点{parent_node['event_id']}时异常：{str(e)}")
                        parent_node["subevent"] = []
                        processed_nodes.append(parent_node)
                        # 保存空结果
                        node_decomposition_results[parent_node["event_id"]] = []

        # 步骤2：递归分解下一层级的事件
        if pending_nodes:
            print(f"\n发现{len(pending_nodes)}个子节点需要继续分解，进入下一层递归...")

            # 为每个待分解的子节点构建背景信息
            nodes_with_background = []
            for node in pending_nodes:
                # 找到父节点的分解结果作为背景信息
                parent_id = "-".join(node["event_id"].split("-")[:-1])
                background_info = node_decomposition_results.get(parent_id, [])

                # 转换背景信息为JSON字符串
                import json
                background_str = json.dumps(background_info, ensure_ascii=False)

                # 将背景信息添加到节点中
                node_with_background = {
                    "node": node,
                    "background_info": background_str
                }
                nodes_with_background.append(node_with_background)

            # 使用线程池并行分解下一层级的事件
            decomposed_subtrees = []
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_node = {
                    executor.submit(self._decompose_single_node, node_info["node"], current_depth + 1, node_info["background_info"]): node_info["node"]
                    for node_info in nodes_with_background
                }

                for future in as_completed(future_to_node):
                    parent_node = future_to_node[future]
                    try:
                        sub_events = future.result()
                        # 为父节点添加子事件列表
                        parent_node["subevent"] = sub_events
                        decomposed_subtrees.append(parent_node)
                        # 递归分解更深层级的事件（如果有）
                        deeper_nodes = [sub for sub in sub_events if sub.get("decompose", 0) == 1]
                        if deeper_nodes:
                            deeper_subtrees = self._dfs_parallel_decompose_tree(deeper_nodes, max_workers, current_depth + 2)
                            # 更新子事件
                            updated_sub_events = []
                            for sub_event in sub_events:
                                matched = False
                                for deeper_subtree in deeper_subtrees:
                                    if deeper_subtree["event_id"] == sub_event["event_id"]:
                                        updated_sub_events.append(deeper_subtree)
                                        matched = True
                                        break
                                if not matched:
                                    updated_sub_events.append(sub_event)
                            parent_node["subevent"] = updated_sub_events
                    except Exception as e:
                        print(f"处理子节点{parent_node['event_id']}时异常：{str(e)}")
                        parent_node["subevent"] = []
                        decomposed_subtrees.append(parent_node)

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
        import copy
        # 验证原始事件格式并创建副本，避免修改原始数据
        required_fields = ["event_id", "name"]
        processed_events = []
        for i, event in enumerate(events):
            missing_fields = [f for f in required_fields if f not in event]
            if missing_fields:
                raise ValueError(f"原始事件{i + 1}缺少必填字段：{','.join(missing_fields)}")
            # 创建事件副本，避免修改原始数据
            event_copy = copy.deepcopy(event)
            # 为副本添加默认字段（若缺失）
            event_copy.setdefault("type", "Other")
            event_copy.setdefault("description", event_copy["name"])
            event_copy.setdefault("participant", [{"name": "自己", "relation": "自己"}])
            event_copy.setdefault("location", "未知")
            event_copy.setdefault("decompose", 1)  # 原始事件默认需要分解
            event_copy.setdefault("subevent", [])
            processed_events.append(event_copy)

        print(f"开始分解事件树，共{len(processed_events)}个原始事件，并行线程数：{max_workers}")

        # 核心：DFS+并行分解
        self.decompose_schedule = self._dfs_parallel_decompose_tree(processed_events, max_workers, current_depth=0)

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
    def __init__(self, persona, file_path):
        """初始化日程调度器，创建空的日程存储结构"""
        # 基础配置
        self.schedule = {}  # 存储日程数据，格式如{"2025-01-01":["event1","event2"],...}
        self.raw_events = []  # 保存原始事件信息
        self.persona = persona
        self.relation = ""
        self.final_schedule = {}
        self.decompose_schedule = {}
        self.file_path = file_path
        self.percentage = {}
        self.summary = ""

        # 线程数配置
        import multiprocessing
        self.cpu_count = multiprocessing.cpu_count()
        self.max_workers = self.cpu_count * 2  # 默认最大工作线程数
        self.decompose_workers = self.max_workers  # 事件分解线程数
        self.schedule_workers = self.max_workers  # 事件规划线程数

        # 解析人物画像
        d = persona
        if isinstance(persona, str):
            d = json.loads(persona)
        self.relation = d.get('relation', '')
        self.name = d.get('name', '')
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
        prompt = template_yearterm_complete_2.format(persona= persona)
        #第三轮，聚焦类别百分比平衡和人类共性事件。100件
        res3 = llm_call(prompt, context, 1)
        print(res3)
        prompt = template_yearterm_complete_3.format(summary=summary)
        #第四轮，聚焦波折、困难、负面事件。20件
        res4 = llm_call(prompt, context)
        print(res4)
        return [res1, res2, res3, res4]
    
    def process_events_with_impacts(self, initial_events, batch_size=20, max_workers=None):
        """
        接收maineventgen生成的初步事件，使用LLM多轮分析提取对生活/画像有影响的事件及其影响和时间跨度，
        然后将事件按impact_category分类，并行对每个类别进行总结，得到这个人一年各类型的重要事件和变化。
        
        优化：支持分批次处理大量事件，并进行并行处理以提高效率。
        
        Args:
            initial_events: maineventgen生成的初步事件列表
            batch_size: 每批次处理的事件数量，默认20
            max_workers: 并行处理的最大线程数，默认使用类配置的线程数
            
        Returns:
            category_summaries: 包含各类型总结结果的字典
        """
        try:
            import os
            import json
            import datetime
            # 如果未指定max_workers，则使用类配置的线程数
            if max_workers is None:
                max_workers = self.max_workers
            if not os.path.exists(self.file_path + "process/impact_events.json") and not os.path.exists(self.file_path + "process/events_analysis.json"):
                # 步骤1: 分批次并行提取对生活/画像有影响的事件及其影响和时间跨度
                print(f"开始提取影响事件，共{len(initial_events)}个事件，每批次{batch_size}个，并行线程数{max_workers}")

                # 将事件列表分成多个批次
                batches = [initial_events[i:i+batch_size] for i in range(0, len(initial_events), batch_size)]
                print(f"共分成{len(batches)}个批次")

                # 并行处理每个批次
                all_impact_events = []
                all_think_contents = []
                all_remaining_events = []
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    # 提交所有批次的处理任务
                    future_to_batch = {
                        executor.submit(self._extract_impact_events, batch): batch
                        for batch in batches
                    }

                    # 收集每个批次的处理结果
                    for future in as_completed(future_to_batch):
                        batch = future_to_batch[future]
                        try:
                            batch_result = future.result()
                            batch_think = batch_result.get("think", "")
                            batch_impact_events = batch_result.get("impact_events", [])
                            batch_remaining_events = batch_result.get("remaining_events", [])

                            # 收集think内容、impact_events和remaining_events
                            if batch_think:
                                all_think_contents.append(batch_think)
                            if batch_impact_events:
                                all_impact_events.extend(batch_impact_events)
                            if batch_remaining_events:
                                all_remaining_events.extend(batch_remaining_events)

                            print(f"完成一个批次的影响事件提取，该批次包含{len(batch)}个事件，提取到{len(batch_impact_events)}个影响事件，剩余{len(batch_remaining_events)}个事件")
                        except Exception as e:
                            print(f"处理批次时出错: {str(e)}")
                            # 如果处理出错，将整个批次的事件作为剩余事件添加
                            all_remaining_events.extend(batch)

                print(f"所有批次处理完成，共提取到{len(all_impact_events)}个影响事件，剩余{len(all_remaining_events)}个事件")

                # 保存步骤1的结果：影响事件

                # 确保process目录存在
                process_dir = os.path.join(self.file_path, "process")
                os.makedirs(process_dir, exist_ok=True)

                # 生成步骤1的文件名
                current_time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                impact_events_file = os.path.join(process_dir, f"impact_events.json")

                # 对影响事件按时间排序
                all_impact_events.sort(key=lambda x: x.get('time_point', ''))
                print(f"影响事件已按时间排序，共{len(all_impact_events)}个事件")

                # 保存影响事件
                with open(impact_events_file, 'w', encoding='utf-8') as f:
                    json.dump(all_impact_events, f, ensure_ascii=False, indent=2)
                print(f"影响事件已保存到: {impact_events_file}")

                # 保存think内容
                if all_think_contents:
                    think_file = os.path.join(process_dir, f"events_analysis.json")
                    with open(think_file, 'w', encoding='utf-8') as f:
                        json.dump(all_think_contents, f, ensure_ascii=False, indent=2)
                    print(f"事件分析内容已保存到: {think_file}")
                
                # 保存剩余事件到新文件
                remaining_events_file = os.path.join(process_dir, f"remaining_events.json")
                with open(remaining_events_file, 'w', encoding='utf-8') as f:
                    json.dump(all_remaining_events, f, ensure_ascii=False, indent=2)
                print(f"剩余事件已保存到: {remaining_events_file}")
            else:
                print("跳过步骤1 - 输出文件已存在")
                all_impact_events = read_json_file(self.file_path + "process/impact_events.json")
                all_think_contents = read_json_file(self.file_path + "process/events_analysis.json")
                
                # 处理剩余事件
                remaining_events_file = os.path.join(self.file_path, "remaining_events.json")
                if os.path.exists(remaining_events_file):
                    # 如果存在剩余事件文件，直接读取
                    all_remaining_events = read_json_file(remaining_events_file)
                    print(f"从文件读取剩余事件: {remaining_events_file}")
                else:
                    # 如果不存在剩余事件文件，根据原始事件和已提取的影响事件重新计算
                    print("重新计算剩余事件...")
                    # 获取所有已提取事件的original_event_id
                    extracted_event_ids = set()
                    for event in all_impact_events:
                        original_id = event.get('original_event_id')
                        if original_id:
                            extracted_event_ids.add(str(original_id))  # 转换为字符串以确保匹配
                    
                    # 过滤出未被提取的事件
                    all_remaining_events = []
                    for event in initial_events:
                        event_id = str(event.get('event_id', ''))  # 转换为字符串以确保匹配
                        if event_id not in extracted_event_ids:
                            all_remaining_events.append(event)
                    
                    # 保存重新计算的剩余事件
                    with open(remaining_events_file, 'w', encoding='utf-8') as f:
                        json.dump(all_remaining_events, f, ensure_ascii=False, indent=2)
                    print(f"重新计算的剩余事件已保存到: {remaining_events_file}")

            if not os.path.exists(self.file_path + "process/events_summary_optimized_by_category.json"):

                # 步骤2: 按impact_category对事件进行分类
                print("开始按类别分类影响事件...")
                category_events = {}
                for event in all_impact_events:
                    category = event.get('impact_category', 'Other')
                    if category not in category_events:
                        category_events[category] = []
                    category_events[category].append(event)

                print(f"影响事件分类完成，共{len(category_events)}个类别")
                for category, events in category_events.items():
                    print(f"{category}: {len(events)}个事件")

                # 步骤3: 并行对每个类别进行总结和创作优化
                print("开始并行总结和优化各类型影响事件...")
                category_summaries_optimized = {}
                updated_category_events = {}

                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    # 提交所有类别的总结和优化任务
                    future_to_category = {
                        executor.submit(self._summarize_and_optimize_events, events, category): category
                        for category, events in category_events.items()
                    }

                    # 收集每个类别的结果
                    for future in as_completed(future_to_category):
                        category = future_to_category[future]
                        try:
                            updated_events, optimized_summary = future.result()
                            updated_category_events[category] = updated_events
                            category_summaries_optimized[category] = optimized_summary
                            print(f"完成{category}类别的总结和优化")
                        except Exception as e:
                            print(f"总结和优化{category}类别时出错: {str(e)}")
                            category_summaries_optimized[category] = f"总结和优化{category}类别时发生错误: {str(e)}"
                            updated_category_events[category] = category_events.get(category, [])
                
                # 保存更新后的事件列表
                updated_events_file = os.path.join(self.file_path, "process", "updated_events_by_category.json")
                with open(updated_events_file, 'w', encoding='utf-8') as f:
                    json.dump(updated_category_events, f, ensure_ascii=False, indent=2)
                print(f"更新后的分类事件列表已保存到: {updated_events_file}")
                
                # 合并所有更新后的事件到一个列表
                all_updated_events = []
                for category, events in updated_category_events.items():
                    all_updated_events.extend(events)
                
                # 保存合并后的更新事件列表
                merged_updated_events_file = os.path.join(self.file_path, "process", "all_updated_events.json")
                with open(merged_updated_events_file, 'w', encoding='utf-8') as f:
                    json.dump(all_updated_events, f, ensure_ascii=False, indent=2)
                print(f"合并后的更新事件列表已保存到: {merged_updated_events_file}")

                print(f"所有类别总结和优化完成，共{len(category_summaries_optimized)}个类别")

                # 保存优化后的结果
                optimized_summary_file = os.path.join(self.file_path, "process", "events_summary_optimized_by_category.json")
                with open(optimized_summary_file, 'w', encoding='utf-8') as f:
                    json.dump(category_summaries_optimized, f, ensure_ascii=False, indent=2)
                print(f"优化后的分类总结结果已保存到: {optimized_summary_file}")
            else:
                print("跳过步骤2 - 输出文件已存在")
                category_summaries_optimized = read_json_file(self.file_path + "process/events_summary_optimized_by_category.json")
                # 从文件读取更新后的事件列表
                updated_events_file = os.path.join(self.file_path, "process", "updated_events_by_category.json")
                if os.path.exists(updated_events_file):
                    updated_category_events = read_json_file(updated_events_file)
                    print(f"从文件读取更新后的事件列表: {updated_events_file}")
            return
            # 新增步骤：按月分析重要事件和变化记录
            print("开始按月分析重要事件和变化记录...")
            try:
                # 获取所有更新后的事件
                all_updated_events = []
                for category, events in updated_category_events.items():
                    all_updated_events.extend(events)
                
                # 按月份分组事件
                events_by_month = {}
                for event in all_updated_events:
                    time_point = event.get('time_point', '')
                    if len(time_point) >= 7:  # 确保有足够的日期格式
                        month_key = time_point[:7]  # YYYY-MM
                        if month_key not in events_by_month:
                            events_by_month[month_key] = []
                        events_by_month[month_key].append(event)
                
                # 按月份顺序排序
                sorted_months = sorted(events_by_month.keys())
                
                # 并行对每个月进行分析
                monthly_analyses = {}
                
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    # 提交所有月份的分析任务
                    future_to_month = {
                        executor.submit(self._analyze_monthly_events, month, events_by_month[month], category_summaries_optimized, self.persona): month
                        for month in sorted_months
                    }
                    
                    # 收集每个月的分析结果
                    for future in as_completed(future_to_month):
                        month = future_to_month[future]
                        try:
                            result_month, monthly_json = future.result()
                            if monthly_json:
                                monthly_analyses[result_month] = monthly_json
                        except Exception as e:
                            print(f"处理{month}月份分析结果时出错: {str(e)}")
                
                # 确保结果按月份顺序排列
                monthly_analyses_sorted = {}
                for month in sorted_months:
                    if month in monthly_analyses:
                        monthly_analyses_sorted[month] = monthly_analyses[month]
                
                # 保存所有月度分析结果
                monthly_analyses_file = os.path.join(self.file_path, "process", "monthly_events_analyses.json")
                with open(monthly_analyses_file, 'w', encoding='utf-8') as f:
                    json.dump(monthly_analyses_sorted, f, ensure_ascii=False, indent=2)
                print(f"月度事件分析结果已保存到: {monthly_analyses_file}")
                
                print("事件影响分析、总结、优化及月度分析完成")
                
                # 返回包含月度分析结果的完整数据
                return {
                    "category_summaries_optimized": category_summaries_optimized,
                    "monthly_events_analyses": monthly_analyses_sorted,
                    "updated_category_events": updated_category_events
                }
            except Exception as e:
                print(f"按月分析事件时出错: {str(e)}")
            
            print("事件影响分析、总结和优化完成")
            return {"category_summaries_optimized": category_summaries_optimized, "updated_category_events": updated_category_events}
        except Exception as e:
            print(f"处理事件影响时出错: {str(e)}")
            return {}

    
    def _extract_impact_events(self, events):
        """
        使用LLM提取对生活/画像有影响的事件及其影响和时间跨度
        
        Args:
            events: 事件列表
            
        Returns:
            dict: 包含think分析、impact_events时间线和未被提取的事件列表的字典
        """
        try:
            # 格式化prompt
            import json
            events_str = json.dumps(events, ensure_ascii=False, indent=2)
            persona_str = json.dumps(self.persona, ensure_ascii=False, indent=2)
            
            prompt = template_extract_impact_events.format(
                events=events_str,
                persona=persona_str
            )

            # 调用LLM
            res = self.llm_call_s(prompt)

            # 提取think部分
            import re
            think_pattern = r'<think>(.*?)</think>'
            think_match = re.search(think_pattern, res, re.DOTALL)
            think_content = think_match.group(1).strip() if think_match else ""
            
            # 提取json部分
            json_pattern = r'<json>(.*?)</json>'
            json_match = re.search(json_pattern, res, re.DOTALL)
            if not json_match:
                print("未找到有效的JSON输出")
                print(f"LLM响应内容: {res}")
                return {"think": think_content, "impact_events": [], "remaining_events": events}

            json_str = json_match.group(1).strip()  # 获取完整匹配的JSON数组字符串
            try:
                impact_events = json.loads(json_str)
            except json.JSONDecodeError as e:
                print(f"JSON解析错误: {str(e)}")
                print(f"待解析的JSON字符串: {json_str}")
                return {"think": think_content, "impact_events": [], "remaining_events": events}
            
            # 从原始事件中删除已提取的影响事件
            if impact_events:
                # 获取所有已提取事件的original_event_id
                extracted_event_ids = set()
                for event in impact_events:
                    original_id = event.get('original_event_id')
                    if original_id:
                        extracted_event_ids.add(str(original_id))  # 转换为字符串以确保匹配
                
                # 过滤出未被提取的事件
                remaining_events = []
                for event in events:
                    event_id = str(event.get('event_id', ''))  # 转换为字符串以确保匹配
                    if event_id not in extracted_event_ids:
                        remaining_events.append(event)
            else:
                remaining_events = events
            
            return {"think": think_content, "impact_events": impact_events, "remaining_events": remaining_events}
        except Exception as e:
            print(f"提取影响事件时出错: {str(e)}")
            return {"think": "", "impact_events": [], "remaining_events": events}

    
    def _analyze_monthly_events(self, month, monthly_events, category_summaries_optimized, persona):
        """
        分析单个月份的事件和变化记录
        
        Args:
            month: 月份（格式：YYYY-MM）
            monthly_events: 该月份的事件列表
            category_summaries_optimized: 各类别年度事件总结
            persona: 人物画像
            
        Returns:
            tuple: (month, monthly_json) 或 (month, None)（如果分析失败）
        """
        try:
            print(f"开始分析{month}月份的事件...")
            
            # 格式化prompt
            category_summaries_str = json.dumps(category_summaries_optimized, ensure_ascii=False, indent=2)
            persona_str = json.dumps(persona, ensure_ascii=False, indent=2)
            monthly_events_str = json.dumps(monthly_events, ensure_ascii=False, indent=2)
            
            prompt = template_monthly_events_analysis.format(
                character_profile=persona_str,
                target_month=month,
                monthly_events=monthly_events_str,
                category_summaries=category_summaries_str
            )
            
            # 调用LLM
            monthly_result = self.llm_call_sr(prompt)
            
            # 提取JSON部分
            import re
            
            # 使用贪婪匹配提取完整的JSON结构
            json_pattern = r'(\{.*\})'  # 匹配从第一个{到最后一个}的完整JSON结构
            json_match = re.search(json_pattern, monthly_result, re.DOTALL)
            
            if json_match:
                monthly_json = json.loads(json_match.group(1))
                print(f"完成{month}月份的事件分析")
                return (month, monthly_json)
            else:
                print(f"未能从{month}月份的分析结果中提取有效的JSON数据")
                return (month, None)
        except Exception as e:
            print(f"分析{month}月份事件时出错: {str(e)}")
            return (month, None)
    
    def _summarize_and_optimize_events(self, impact_events, category=""):
        """
        使用LLM对影响事件进行总结并对每个类别输出进行创作优化，同时更新原始影响事件列表
        
        Args:
            impact_events: 影响事件列表
            category: 当前总结的类别名称
            
        Returns:
            tuple: (updated_events, optimized_text)
                updated_events: 更新后的影响事件列表（JSON数组）
                optimized_text: 按类别总结并优化后的文本结果
        """
        try:
            import json
            
            # 步骤1: 对事件进行总结
            impact_events_str = json.dumps(impact_events, ensure_ascii=False, indent=2)
            persona_str = json.dumps(self.persona, ensure_ascii=False, indent=2)
            
            summarize_prompt = template_summarize_impact_events.format(
                type=category,
                impact_events="",
                persona=persona_str
            )
            
            # 调用LLM进行总结
            summary_response = self.llm_call_sr(summarize_prompt)
            print(f"{category}类别的总结结果: {summary_response}")
            
            # 步骤2: 对总结结果进行创作优化
            optimize_prompt = template_optimize_year_events.format(
                type=category,
                character_profile=json.dumps(self.persona, ensure_ascii=False, default=str),
                category_summary=summary_response
            )
            
            # 调用LLM进行优化
            optimized_response = self.llm_call_sr(optimize_prompt)
            print(f"{category}类别的优化结果: {optimized_response}")
            
            # 步骤3: 根据优化后的总结更新原始影响事件列表
            update_prompt = template_update_impact_events.format(
                character_profile=json.dumps(self.persona, ensure_ascii=False, default=str),
                original_events=json.dumps(impact_events, ensure_ascii=False, indent=2),
                optimized_summary=optimized_response,
                t = category
            )
            
            # 调用LLM更新事件
            update_response = self.llm_call_sr(update_prompt)
            print(f"{category}类别的事件更新结果: {update_response}")
            
            # 提取更新后的JSON事件列表
            import re
            # 修改为使用贪婪匹配(.*)，匹配从第一个[到最后一个]的完整内容
            json_pattern = r'(\[.*\])'  # 匹配完整的JSON数组（贪婪匹配，匹配第一个[到最后一个]）
            json_match = re.search(json_pattern, update_response, re.DOTALL)
            
            if json_match:
                updated_events = json.loads(json_match.group(1))
                print(f"{category}类别的更新后的事件数量: {len(updated_events)}")
            else:
                # 如果没有找到JSON数组，尝试匹配JSON对象数组的另一种格式
                json_pattern = r'(\{.*\})'  # 匹配JSON对象
                json_matches = re.findall(json_pattern, update_response, re.DOTALL)
                if json_matches:
                    try:
                        updated_events = [json.loads(match) for match in json_matches]
                        print(f"{category}类别的更新后的事件数量: {len(updated_events)}")
                    except:
                        # 如果解析失败，返回原始事件列表
                        updated_events = impact_events
                        print(f"{category}类别事件更新解析失败，使用原始事件列表")
                else:
                    # 如果仍然没有找到，返回原始事件列表
                    updated_events = impact_events
                    print(f"{category}类别事件更新未找到JSON，使用原始事件列表")
            
            # 返回更新后的事件列表和优化后的文本
            return updated_events, optimized_response
        except Exception as e:
            print(f"总结和优化{category}事件时出错: {str(e)}")
            # 发生错误时返回原始事件列表和错误信息
            return impact_events, f"{category}事件总结和优化过程中发生错误: {str(e)}"


    def extract_events_by_categories(self, file_path, prob, filter = False):#filter:是否执行概率过滤
        # 定义所有类别
        CATEGORIES = [
            "Career",
            "Education",
            "Relationships",
            "Family&Living Situation",
            "Personal Life",
            "Finance",
            "Health",
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

            # 检查是否为带有<type>标记的标题行
            import re
            type_match = re.match(r'<type>(.*?)</type>', line)
            if type_match:
                # 提取<type>标签内的内容
                title_content = type_match.group(1).strip()
                # 根据标题内容匹配类别
                line_lower = title_content.lower()
                if 'career' in line_lower:
                    current_category = "Career"
                elif 'education' in line_lower:
                    current_category = "Education"
                elif 'relationships' in line_lower:
                    current_category = "Relationships"
                elif 'family' in line_lower:
                    current_category = "Family&Living Situation"
                elif 'personal' in line_lower:
                    current_category = "Personal Life"
                elif 'finance' in line_lower:
                    current_category = "Finance"
                elif 'health' in line_lower:
                    current_category = "Health"
                elif 'unexpected' in line_lower:
                    current_category = "Unexpected Events"
                elif 'other' in line_lower:
                    current_category = "Other"
                else:
                    # 处理可能的其他格式
                    continue
                continue

            # 处理事件行（非标题行且当前有活跃类别）
            if current_category:
                event = line
                # 去除可能的序号（如数字+.开头）
                if event and event[0].isdigit() and ('.' in event[:5] or '、' in event[:5]):
                    if '. ' in event:
                        event = event.split('. ', 1)[1]
                    elif '、' in event:
                        event = event.split('、', 1)[1]
                # 去除可能的前缀符号（如"- "、"* "等）
                if event.startswith(('- ', '* ', '+ ', '· ')):
                    event = event[2:]
                # 去除可能的空格和制表符
                event = event.strip()
                # 只添加非空事件
                if event:
                    # 只要包含冒号或括号中的信息都视为有效事件（非常宽松的判断）
                    if ':' in event or '（' in event or '）' in event or '(' in event or ')' in event:
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
        if prob_valid and filter:
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

    def standard_data(self, data, type):
        """
        对生成的事件进行合理性、一致性优化，修改，增加和格式化

        参数:
            data: 事件列表，每个事件包含基本信息
            type: 事件类别

        返回:
            优化后的标准化事件列表
        """
        # 参数验证
        if not isinstance(data, list):
            print(f"【{type}】参数错误：data 必须是列表类型")
            return []

        if not data:
            print(f"【{type}】输入事件列表为空")
            return []

        # 定义事件类别对应的指令
        category_instructions = {
            "Career": "涵盖工作相关的多个维度：项目推进、团队协作、业绩目标、工作挑战、行业交流、晋升机会、工作成果展示、职业规划等",
            "Education": "教育与学习相关事件：技能学习、职业认证、学术研究、课程学习、考试备考、知识更新、教育培训等",
            "Relationships": "丰富各类人际关系互动：家庭聚会、朋友约会、同事协作、导师交流、邻里互动、亲情陪伴、友情维护、爱情纪念日等不同场景",
            "Family&Living Situation": "覆盖家庭生活与居住环境：家居布置、物品采购、家务管理、社区活动、居住环境改善、搬家、装修、宠物照顾、家庭仪式等",
            "Personal Life": "自我关怀、娱乐与生活方式：个人兴趣发展、艺术欣赏、放松休闲、自我奖励、美容养生、心灵疗愈、爱好实践、社交聚会、旅行计划、美食探索等",
            "Finance": "全面的财务相关事件：收入变化、投资决策、理财规划、大额消费、预算管理、债务处理、保险购买、财务目标达成等",
            "Health": "身心健康的全面关注：定期体检、运动锻炼、饮食调整、睡眠改善、压力管理、疾病预防、康复调理、心理健康维护等",
            "Unexpected Events": "各类突发与意外事件：惊喜礼物、突发疾病、临时出差、朋友到访、设备故障、天气影响、意外收获、紧急情况处理等",
            "Other": "未被其他类别覆盖的独特事件：特殊节日习俗、公益活动参与、偶然机会把握、突发灵感实现、跨领域尝试等"
        }

        try:
            print(f"【{type}】开始处理，共 {len(data)} 个事件")

            # 从 event_schema.csv 提取当前类型的阶段事件
            def get_stage_events(category):
                """从 event_schema.csv 提取指定类别的阶段事件"""
                schema_path = "event/event_schema.csv"
                stage_events = []
                current_theme = ""

                try:
                    import csv
                    with open(schema_path, 'r', encoding='utf-8') as csvfile:
                        # 跳过前两行表头
                        next(csvfile)  # 跳过 "Table 1,Unnamed: 1,Unnamed: 2,Unnamed: 3"
                        next(csvfile)  # 跳过 "主题,阶段事件 (Stage),原子事件 (Atomic / 可观测),现实动作示例"

                        reader = csv.reader(csvfile)
                        for row in reader:
                            # 处理行数据，确保有足够的列
                            if len(row) >= 2:
                                row_theme = row[0].strip()  # 主题在第一列
                                row_stage_event = row[1].strip()  # 阶段事件在第二列

                                # 如果当前行有主题，则更新current_theme
                                if row_theme:
                                    current_theme = row_theme

                                # 如果当前主题与目标类别匹配，且有阶段事件，则添加
                                if current_theme == category and row_stage_event and row_stage_event not in stage_events:
                                    stage_events.append(row_stage_event)
                except Exception as e:
                    print(f"读取事件 schema 失败：{str(e)}")

                return stage_events

            def robust_json_parse(json_str, description=""):
                """
                鲁棒的JSON解析函数，处理常见的格式问题

                参数:
                    json_str: JSON字符串
                    description: 解析内容的描述，用于日志

                返回:
                    解析后的JSON对象，如果解析失败则返回空对象{}
                """
                try:
                    # 1. 清理Markdown格式
                    json_str = re.sub(r'^```json\s*|\s*```$', '', json_str.strip(), flags=re.MULTILINE)
                    json_str = re.sub(r'^```\s*|\s*```$', '', json_str.strip(), flags=re.MULTILINE)

                    # 2. 修复常见的格式错误
                    # 替换单引号为双引号（注意：如果字符串中包含单引号，需要先处理）
                    json_str = re.sub(r"(?<!\\)'", '"', json_str)
                    # 修复末尾多余的逗号
                    json_str = re.sub(r",\s*([}\]])", r" \1", json_str)
                    # 清理前后空格和换行符
                    json_str = json_str.strip()

                    # 3. 尝试解析
                    return json.loads(json_str)
                except json.JSONDecodeError as e:
                    print(f"【{type}】{description} JSON解析失败: {e}")
                    print(f"原始输出前200字符: {json_str[:200]}...")
                    # 尝试更激进的修复
                    try:
                        # 使用正则表达式提取最外层的JSON结构
                        json_match = re.search(r'\[.*\]|\{.*\}', json_str, re.DOTALL)
                        if json_match:
                            json_str = json_match.group(0)
                            # 再次尝试修复和解析
                            json_str = re.sub(r"(?<!\\)'", '"', json_str)
                            json_str = re.sub(r",\s*([}\]])", r" \1", json_str)
                            return json.loads(json_str)
                    except Exception as e2:
                        print(f"【{type}】{description} JSON修复失败: {e2}")
                    # 解析失败时返回空对象，不影响后续流程
                    print(f"【{type}】{description} JSON解析完全失败，返回空对象")
                    return {}
                except Exception as e:
                    print(f"【{type}】{description} JSON处理发生未知错误: {e}")
                    return {}

            category_stage_events = get_stage_events(type)
            stage_events_str = ", ".join(category_stage_events) if category_stage_events else ""

            # 1. 合理性校验：画像匹配度、现实合理性、日期、频率与间隔、相似事件
            prompt = template_check.format(persona=self.persona, content=data)
            validation_result = llm_call_reason(prompt, context, 1)
            print(f"【{type}】合理性校验完成")

            # 2. 基于合理性校验结果进行修改、删除
            prompt = template_process.format(content=data,t=type)
            processed_result = llm_call_reason(prompt, context,1)
            data1 = robust_json_parse(processed_result, "事件处理结果")
            # 确保data1是数组类型
            if not isinstance(data1, list):
                data1 = []
            print(f"【{type}】事件处理完成，剩余 {len(data1)} 个事件")

            # 3. 多样性新增事件，补充删除事件
            base_instruction = category_instructions.get(type, "更多样化的事件")
            if stage_events_str:
                instruction = f"{base_instruction}。可参考的阶段事件包括：{stage_events_str}"
            else:
                instruction = base_instruction

            prompt = template_process_2.format(type=type, content=processed_result, persona=self.persona, instruction=instruction)
            new_events_result = llm_call(prompt, context)
            data2 = robust_json_parse(new_events_result, "新增事件结果")
            # 确保data2是数组类型
            if not isinstance(data2, list):
                data2 = []
            print(f"【{type}】新增 {len(data2)} 个事件")

            # 4. 合并事件并去重
            combined_data = data1 + data2

            # 事件去重（基于名称和日期）
            unique_events = []
            seen_events = set()
            for event in combined_data:
                if isinstance(event, dict) and 'name' in event and 'date' in event:
                    # 创建唯一键：事件名称 + 日期
                    event_key = f"{event['name']}{event['date']}"
                    if event_key not in seen_events:
                        seen_events.add(event_key)
                        unique_events.append(event)

            print(f"【{type}】合并后共 {len(combined_data)} 个事件，去重后剩余 {len(unique_events)} 个事件")

            # 5. 分块处理，进行最终标准化（并行实现）
            def split_array(arr, chunk_size=15):
                """将列表分块处理"""
                return [arr[i:i + chunk_size] for i in range(0, len(arr), chunk_size)]

            def process_chunk(chunk_info):
                """处理单个块的函数（供并行使用）"""
                i, chunk = chunk_info
                try:
                    # 本地处理，不共享可变数据
                    local_prompt = template_process_1.format(content=chunk, relation=self.relation, stage_events=stage_events_str, t=type)
                    local_result = llm_call(local_prompt, context)
                    local_data = robust_json_parse(local_result, f"第 {i} 块标准化结果")
                    # 确保local_data是数组类型
                    if not isinstance(local_data, list):
                        local_data = []
                    # 使用线程安全的方式输出日志
                    with threading.Lock():
                        print(f"【{type}】第 {i}/{len(chunks)} 块处理完成，新增 {len(local_data)} 个标准化事件")
                    return local_data
                except Exception as e:
                    # 使用线程安全的方式输出错误日志
                    with threading.Lock():
                        print(f"【{type}】第 {i} 块处理失败：{str(e)}")
                    return []
            
            final_result = []
            chunks = split_array(unique_events)
            print(f"【{type}】分块处理：共 {len(chunks)} 块，每块最多 {15} 个事件")
            
            # 使用线程池并行处理所有块
            max_workers = min(10, len(chunks))  # 根据块数和系统资源设置线程数
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 提交所有任务，包含块索引和块数据
                chunk_infos = list(enumerate(chunks, 1))
                # 获取所有结果
                chunk_results = list(executor.map(process_chunk, chunk_infos))
                
                # 合并所有结果
                for chunk_data in chunk_results:
                    final_result.extend(chunk_data)
            
            print(f"【{type}】全部处理完成，最终生成 {len(final_result)} 个标准化事件")
            return final_result
            
        except json.JSONDecodeError as e:
            print(f"【{type}】JSON解析错误：{str(e)}")
            return []
        except Exception as e:
            print(f"【{type}】处理错误：{str(e)}")
            import traceback
            traceback.print_exc()
            return []

    def print_category_stats(self,event_data, title="事件数量统计"):
        """
        打印每个类别的事件数量和占比

        参数:
            event_data: 事件数据字典（格式同函数返回值）
            title: 统计标题（区分调整前/后）
        """
        CATEGORIES = [
            "Career",
            "Education",
            "Relationships",
            "Family&Living Situation",
            "Personal Life",
            "Finance",
            "Health",
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

        if not os.path.exists(self.file_path + "process/event_1.json"):
            # 提取事件并生成字符串数组
            event_stats = self.extract_events_by_categories(txt_file_path,self.percentage,filter=False)#从记录文件中提取事件，执行概率过滤
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
        
        # # 读取event_1.json作为输入并调用process_events_with_impacts
        # event_1_path = os.path.join(self.file_path, "process", "event_1.json")
        #
        # if os.path.exists(event_1_path):
        #     print(f"开始读取event_1.json文件: {event_1_path}")
        #     with open(event_1_path, 'r', encoding='utf-8') as f:
        #         initial_events = json.load(f)
        #
        #     print(f"成功读取event_1.json，共包含{len(initial_events)}个事件")
        #     data = self.split_and_convert_events(initial_events,False)  # 将重复事件分解为单个事件
        #     data = self.sort_and_add_event_id(data)  # 按起始时间顺序为事件分配id
        #     # 调用process_events_with_impacts处理事件
        #     modified_events = self.process_events_with_impacts(data)
        #     print(f"process_events_with_impacts处理完成，共生成{len(modified_events)}个事件")
        # else:
        #     print(f"event_1.json文件不存在: {event_1_path}")


    def extract_events_by_month(self, target_month, event_dict=None, target_year=2025, include_surrounding=False):
        """
        提取目标月份的事件，支持灵活配置
        :param target_month: 目标月份（整数，1-12）
        :param event_dict: 要提取的事件字典，默认使用self.schedule
        :param target_year: 目标年份，默认为2025
        :param include_surrounding: 是否包含前后一个月的事件
        :return: 根据参数返回相应的事件字典
        """
        if event_dict is None:
            event_dict = self.schedule
            
        month_events = {}  # 目标月事件
        before_events = {}  # 前一个月事件
        after_events = {}   # 后一个月事件

        for date_str, events in event_dict.items():
            try:
                # 解析年份和月份
                year = int(date_str.split("-")[0])
                month = int(date_str.split("-")[1])

                # 仅处理目标年份数据
                if year != target_year:
                    continue

                if month == target_month:
                    month_events[date_str] = events
                elif include_surrounding:
                    if month == target_month - 1:
                        before_events[date_str] = events
                    elif month == target_month + 1:
                        after_events[date_str] = events
            except (ValueError, IndexError) as e:
                print(f"解析日期 {date_str} 时出错: {e}")
                continue

        if include_surrounding:
            return month_events, before_events, after_events
        else:
            return month_events\

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

    def split_and_convert_events(self,events,delete_date=True):
        """
        将包含多日期的事件拆分为独立事件，并转换date字段为start_time和end_time
        处理逻辑：
        - 若事件无date字段（已处理过），直接添加到结果
        - 若date是数组（如["2025-01-01", "2025-01-05至2025-01-06"]），每个元素对应一个独立事件
        - 单个日期（无"至"）：start_time = end_time
        - 日期范围（有"至"）：分割为start_time和end_time
        :param events: 原始事件列表（date为数组，元素为单日期或日期范围）
        :return: 拆分并转换后的事件列表（每个事件对应一次发生）
        """
        processed_events = []
        for event in events:
            # 如果事件没有date字段，说明已经处理过（有start_time和end_time），直接添加
            if "date" not in event:
                processed_events.append(event)
                continue
            # 遍历date数组中的每个发生日期/范围
            for date_item in event["date"]:
                # 复制原事件基础信息（避免修改原始数据）
                new_event = event.copy()
                # 移除原date字段（后续替换为start/end）
                if delete_date:
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

    def extract_date_from_text(self, text):
        """
        从文本中提取XX-XX-XX格式的日期（支持年-月-日，年可2位或4位）
        匹配规则：
        - 月：01-12，日：01-31
        - 年：2位（如25-01-08）或4位（如2025-01-08）
        示例：从"时间：2025-01-08 会议"中提取"2025-01-08"
        :param text: 可能包含日期的文本字符串
        :return: 提取到的XX-XX-XX格式日期字符串；若无则返回空字符串
        """
        import re
        # 正则匹配XX-XX-XX：年（2或4位数字）-月（2位）-日（2位）
        date_pattern = r"\b(\d{2}|\d{4})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])\b"
        match = re.search(date_pattern, text)
        return match.group(0) if match else ""

    def sort_and_add_event_id(self, events):
        """
        按start_time（"YYYY-MM-DD"格式）升序排序，为每个事件添加event_id
        :param events: 经split_and_convert_events处理后的事件列表
        :return: 带event_id的排序后事件列表
        """
        # "YYYY-MM-DD"格式可直接按字符串排序（无需转datetime），效率高且结果准确
        sorted_events = sorted(events, key=lambda x: self.extract_date_from_text(x["start_time"]))

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

    def get_events_by_month(self, events, target_year, target_month):
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
            start_str = self.extract_date_from_text(event["start_time"])
            end_str = self.extract_date_from_text(event["end_time"])

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
            except ValueError:
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
            if event_end <= target_month_end and event_end >= target_month_start:
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

    def decompose_events_with_event_tree(self, events, file):
        """
        使用EventTree类进行事件分解
        :param events: 待分解的事件列表
        :param file: 结果保存路径前缀
        """
        obj = EventTree(persona=self.persona)
        # 调用并行分解函数，使用配置的线程数
        obj.event_decomposer(
            events=events,
            file=file,
            max_workers=self.decompose_workers  # 并行线程数（根据网络带宽和大模型QPS调整）
        )


    def event_schedule(self,data,month):
        prompt = template_process_4.format(content=data, persona=self.persona,calendar=self.get_month_calendar(2025,month))
        print(prompt)
        res = self.llm_call_sr(prompt)
        print(res)
        # 匹配字符串中的第一个[和最后一个]，确保只解析有效的JSON数组
        import re
        json_pattern = r'\[.*\]'  # 贪婪匹配从第一个[到最后一个]的内容
        json_match = re.search(json_pattern, res, re.DOTALL)
        if json_match:
            clean_res = json_match.group(0)
            data = json.loads(clean_res)
        else:
            # 如果没有找到[和]，尝试直接解析
            data = json.loads(res)
        return data
    
    def event_schedule_transition(self, data, month, transition_days=10):
        """
        处理月交界处的事件（前一个月的16号到最后一天和当前月的1号到15号）
        :param data: 所有事件数据
        :param month: 当前月份（需要处理month-1月的16号到最后一天和month月的1号到15号）
        :param transition_days: 交界天数参数（当前版本不再使用）
        :return: 调整后的月交界处事件
        """
        from datetime import datetime, timedelta
        
        # 计算前一个月的后10天和当前月的前10天的时间范围
        target_year = 2025
        
        # 计算前一个月的起始日期（从16号开始）
        # 确保所有日期都在target_year内
        if month == 1:
            # 1月份的交界处，只处理2025年1月1日到15日的事件，不处理2024年的事件
            prev_month_mid = None  # 不处理前一个月
            prev_month_last_day = None
        else:
            # 其他月份，处理target_year内的前一个月16号到最后一天
            prev_month = month - 1
            prev_year = target_year  # 确保前一个月也在target_year内
            
            # 计算前一个月的16号和最后一天
            prev_month_mid = datetime(prev_year, prev_month, 16)  # 前一个月的16号
            
            if prev_month == 12:
                next_month_first = datetime(prev_year + 1, 1, 1)
            else:
                next_month_first = datetime(prev_year, prev_month + 1, 1)
                
            prev_month_last_day = next_month_first - timedelta(days=1)
        
        # 计算当前月的1号到15号
        current_month_start = datetime(target_year, month, 1)
        current_month_mid = datetime(target_year, month, 15)  # 当前月的15号
        
        # 获取前一个月16号到最后一天的事件和当前月1号到15号的事件
        prev_month_events = []
        current_month_events = []
        
        for event in data:
            # 提取事件的起止日期
            start_str = self.extract_date_from_text(event["start_time"])
            end_str = self.extract_date_from_text(event["end_time"])
            
            if not start_str:
                start_str = event["start_time"]
            if not end_str:
                end_str = start_str
            
            # 尝试解析日期
            try:
                event_start = datetime.strptime(start_str, "%Y-%m-%d")
                event_end = datetime.strptime(end_str, "%Y-%m-%d")
            except ValueError:
                # 无法解析的日期跳过
                continue
            
            # 确保事件日期在target_year内
            if event_start.year != target_year and event_end.year != target_year:
                continue  # 跳过不在target_year内的事件
            
            # 判断事件是否在前一个月的16号到最后一天（仅当prev_month_mid不为None时）
            if prev_month_mid is not None and event_start <= prev_month_last_day and event_end >= prev_month_mid:
                prev_month_events.append(event)
            
            # 判断事件是否在当前月的1号到15号
            if event_start <= current_month_mid and event_end >= current_month_start:
                current_month_events.append(event)
        
        # 合并两个时间段的事件
        transition_events = prev_month_events + current_month_events
        
        if not transition_events:
            return []
        
        # 生成月交界处的日历信息
        # 计算时间范围的开始和结束日期
        if prev_month_mid is not None:
            transition_start = prev_month_mid
        else:
            # 1月份的情况，从当月1号开始
            transition_start = current_month_start
        transition_end = current_month_mid
        
        # 生成日历信息
        calendar_data = []
        current_date = transition_start
        while current_date <= transition_end:
            # 获取星期几
            weekday = "星期" + "日一二三四五六"[current_date.weekday()]
            
            # 获取节日信息
            holiday = ""
            try:
                from holidays import China
                cn_holidays = China(years=current_date.year)
                if current_date in cn_holidays:
                    holiday = cn_holidays[current_date]
            except:
                pass
            
            calendar_data.append({
                "date": current_date.strftime("%Y-%m-%d"),
                "weekday": weekday,
                "holiday": holiday
            })
            current_date += timedelta(days=1)
        
        # 调用LLM进行月交界处的事件调整
        prompt = template_process_4.format(content=transition_events, persona=self.persona, calendar=calendar_data)
        print(f"处理月交界处 {transition_start.strftime('%Y-%m-%d')} 至 {transition_end.strftime('%Y-%m-%d')}")
        print(prompt)
        res = self.llm_call_sr(prompt)
        print(res)
        
        try:
            # 匹配字符串中的第一个[和最后一个]，确保只解析有效的JSON数组
            import re
            json_pattern = r'\[.*\]'  # 贪婪匹配从第一个[到最后一个]的内容
            json_match = re.search(json_pattern, res, re.DOTALL)
            if json_match:
                clean_res = json_match.group(0)
                adjusted_events = json.loads(clean_res)
            else:
                # 如果没有找到[和]，尝试直接解析
                adjusted_events = json.loads(res)
            return adjusted_events
        except json.JSONDecodeError:
            print(f"月交界处 {month} 月的事件调整失败，返回空列表")
            return []

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

    def _process_single_month(self, data, month):
        """实例方法：处理单个月份的事件"""
        print(f"【2025年{month}月】开始处理")
        try:
            month_events = self.get_events_by_month(data, 2025, month)
            scheduled_events = self.event_schedule(month_events, month)
            print(f"【2025年{month}月】完成，生成{len(scheduled_events)}件")
            return scheduled_events
        except Exception as e:
            print(f"【2025年{month}月】处理失败：{str(e)}")
            import traceback
            traceback.print_exc()
            return []

    def parallel_process_monthly_events(self, data: List[Dict[str, Any]]):
        """并行处理1-12月主题事件（类方法入口）"""
        final_schedule = []
        max_workers = min(12, self.schedule_workers)

        # 使用ThreadPoolExecutor实现并行处理（避免pickling问题）
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        # 定义每个线程要执行的函数
        def process_month(month):
            print(f"【2025年{month}月】开始处理")
            try:
                month_events = self.get_events_by_month(data, 2025, month)
                scheduled_events = self.event_schedule(month_events, month)
                print(f"【2025年{month}月】完成，生成{len(scheduled_events)}件")
                return scheduled_events
            except Exception as e:
                print(f"【2025年{month}月】处理失败：{str(e)}")
                import traceback
                traceback.print_exc()
                return []

        # 提交所有任务到线程池
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交任务并获取Future对象
            future_to_month = {executor.submit(process_month, month): month for month in range(1, 13)}
            
            # 处理完成的任务结果
            for future in as_completed(future_to_month):
                month = future_to_month[future]
                try:
                    scheduled_events = future.result()
                    final_schedule.extend(scheduled_events)
                    self.final_schedule = final_schedule
                    # 实时保存结果
                    output_path = f"{self.file_path}process/event_2.json"
                    with open(output_path, "w", encoding="utf-8") as f:
                        json.dump(final_schedule, f, ensure_ascii=False, indent=2)
                except Exception as e:
                    print(f"【2025年{month}月】结果处理失败：{str(e)}")

        # 保存最终结果到实例属性
        self.final_schedule = final_schedule
        print(f"所有月份处理完成，共生成{len(final_schedule)}件主题事件")

    def parallel_process_transition_events(self, data, transition_days=10):
        """
        并行处理月交界处的事件
        :param data: 所有事件数据
        :param transition_days: 交界天数
        :return: 所有月交界处的事件
        """
        transition_events = []
        max_workers = min(12, self.schedule_workers)  # 最多12个线程

        # 使用ThreadPoolExecutor实现并行处理
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        # 定义每个线程要执行的函数
        def process_transition(month):
            print(f"【{month-1}-{month}月交界处】开始处理")
            try:
                trans_events = self.event_schedule_transition(data, month, transition_days)
                print(f"【{month-1}-{month}月交界处】完成，处理了{len(trans_events)}个事件")
                return trans_events
            except Exception as e:
                print(f"【{month-1}-{month}月交界处】处理失败：{str(e)}")
                import traceback
                traceback.print_exc()
                return []

        # 提交所有任务到线程池
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交任务并获取Future对象
            # 处理1-2月，2-3月，...，11-12月交界处
            future_to_month = {executor.submit(process_transition, month): month for month in range(2, 13)}
            
            # 处理完成的任务结果
            for future in as_completed(future_to_month):
                month = future_to_month[future]
                try:
                    trans_events = future.result()
                    transition_events.extend(trans_events)
                except Exception as e:
                    print(f"【{month-1}-{month}月交界处】结果处理失败：{str(e)}")

        return transition_events

    def main_schedule_event(self,data,file,transition_days=10):
        data = self.split_and_convert_events(data)#将重复事件分解为单个事件
        data = self.sort_and_add_event_id(data)#按起始时间顺序为事件分配id
        
        # 1. 先调用每月并行规划
        self.parallel_process_monthly_events(data=data)
        # monthly_events = self.final_schedule.copy()
        # monthly_events = self.split_and_convert_events(monthly_events)
        # monthly_events = self.sort_and_add_event_id(monthly_events)
        # # 2. 然后调用月交界处并行规划，使用每月规划后的事件作为输入
        # transition_events = self.parallel_process_transition_events(monthly_events, transition_days)
        #
        # # 3. 整合所有事件（包括每月规划和月交界处规划的结果）
        # # 筛选出12月16号到31号的事件（这些事件在月交界处规划中未被处理）
        # december_late_events = []
        # for event in monthly_events:
        #     end_date_str = self.extract_date_from_text(event["end_time"])
        #     if end_date_str:
        #         event_end = datetime.strptime(end_date_str, "%Y-%m-%d")
        #         # 筛选截止日期在2025-12-16到2025-12-31之间的事件
        #         if datetime(2025, 12, 16) <= event_end <= datetime(2025, 12, 31):
        #             december_late_events.append(event)
        #
        # # 合并月交界处事件和12月下旬事件
        # all_events = transition_events + december_late_events
        #
        # # 更新最终结果
        # self.final_schedule = all_events
        #
        # # 4. 保存最终结果
        # with open(file + "process/event_2.json", "w", encoding="utf-8") as f:
        #     json.dump(self.final_schedule, f, ensure_ascii=False, indent=2)
        #
        # print(f"所有月份和月交界处处理完成，共生成{len(self.final_schedule)}件主题事件")

    def main_decompose_event(self,data,file):
        #res = read_json_file(file+"process/event_2.json")
        #res = self.merge_events_events(data) #做预处理，防止主题事件文件出错
        res = self.split_and_convert_events(data)
        res = self.sort_and_add_event_id(res)
        #分解事件
        self.decompose_events_with_event_tree(res,file)


# 使用示例
if __name__ == "__main__":
    # 测试event_schedule方法
    import os
    
    # 加载persona文件
    persona_path = "output/persona.json"
    if os.path.exists(persona_path):
        with open(persona_path, "r", encoding="utf-8") as f:
            persona_data = json.load(f)
        print("成功加载persona文件")
    else:
        print("persona文件不存在")
        persona_data = {}
    
    # 创建调度器实例
    file_path = "output/"
    scheduler = Scheduler(persona=persona_data, file_path=file_path)
    
    # 从output\process\event_1.json读取测试数据
    event_file_path = "output/process/event_1.json"
    if os.path.exists(event_file_path):
        with open(event_file_path, "r", encoding="utf-8") as f:
            test_data = json.load(f)
        print("成功加载event_1.json文件，共{}个事件".format(len(test_data)))

        data = scheduler.split_and_convert_events(test_data)  # 将重复事件分解为单个事件
        data = scheduler.sort_and_add_event_id(data)  # 按起始时间顺序为事件分配id
        # 将测试数据添加到Scheduler的事件中
        scheduler.raw_events = data
        # 或者使用load_from_json方法
        # scheduler.load_from_json(json_data=test_data, persona=persona_data, percentage={})
        
        # 调用event_schedule方法测试
        # print("开始测试event_schedule方法...")
        # try:
        #     # 测试10月份的事件
        #     result = scheduler.event_schedule(scheduler.get_events_by_month(data,2025,10), 10)
        #     print("测试成功！结果：")
        #     print(json.dumps(result, ensure_ascii=False, indent=2))
        # except Exception as e:
        #     print(f"测试失败：{str(e)}")
        #     import traceback
        #     traceback.print_exc()
        
        # 调用event_schedule_transition方法测试月交界处的事件
        print("\n开始测试event_schedule_transition方法...")
        try:
            # 测试10-11月交界处的事件（以15号为分界线）
            transition_result = scheduler.event_schedule_transition(data, 11)
            if transition_result:
                print(f"测试成功！月交界处（15号分界）处理了{len(transition_result)}个事件")
                print("结果：")
                print(json.dumps(transition_result, ensure_ascii=False, indent=2))
            else:
                print("测试成功，但月交界处没有需要处理的事件")
        except Exception as e:
            print(f"测试失败：{str(e)}")
            import traceback
            traceback.print_exc()
        
        # 测试另一个月交界处（如11-12月）
        try:
            print("\n开始测试event_schedule_transition方法（11-12月）...")
            # 测试11-12月交界处的事件（以15号为分界线）
            transition_result_11_12 = scheduler.event_schedule_transition(data, 12)
            if transition_result_11_12:
                print(f"测试成功！月交界处（15号分界）处理了{len(transition_result_11_12)}个事件")
                print("结果：")
                print(json.dumps(transition_result_11_12, ensure_ascii=False, indent=2))
            else:
                print("测试成功，但月交界处没有需要处理的事件")
        except Exception as e:
            print(f"测试失败：{str(e)}")
            import traceback
            traceback.print_exc()
    else:
        print("event_1.json文件不存在，无法进行测试")
        test_data = []