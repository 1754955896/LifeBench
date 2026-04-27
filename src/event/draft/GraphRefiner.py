# -*- coding: utf-8 -*-
"""事件图谱优化器，负责事件的插入和优化"""
import json
from typing import Dict, List, Any
import concurrent.futures
from utils.llm_call import llm_call_j, llm_call


class GraphRefiner:
    """事件图谱优化器，负责基于插入建议生成详细计划并执行事件插入"""
    
    def __init__(self, event_graph: Dict, yearly_summary: str = None, isprint: bool = True):
        """
        初始化图谱优化器
        
        Args:
            event_graph: 事件图谱数据，包含 nodes 和 edges
            yearly_summary: 全年总结文本，用于事件插入计划生成
            isprint: 是否打印输出日志
        """
        self.event_graph = event_graph or {"nodes": [], "edges": []}
        self.yearly_summary = yearly_summary or ""
        self.isprint = isprint
    
    def _print(self, message: str):
        """
        根据 isprint 判断是否打印输出
        
        Args:
            message: 要打印的消息
        """
        if self.isprint:
            print(message)
    
    def insert_events(self, insertion_suggestion: str, start_date: str = None) -> Dict:
        """
        基于输入的插入建议，通过 LLM 分析并插入新事件到现有事件图中
        
        Args:
            insertion_suggestion: 插入建议文本，描述需要添加的事件
            start_date: 起始日期（YYYY-MM-DD 或 YYYY-MM 格式），只分析此日期之后的月份
        
        Returns:
            更新后的事件图谱
        """
        print(f"\n{'='*60}")
        print("开始执行事件插入流程")
        print(f"{'='*60}")
        print(f"插入建议：{insertion_suggestion}")
        if start_date:
            print(f"起始日期：{start_date}")
        
        # Step 1: 按月份组织现有事件
        print(f"\n[Step 1] 按月份组织现有事件...")
        monthly_events = self._organize_events_by_month()
        
        # 如果指定了起始日期，只保留起始月份之后的月份
        if start_date:
            if len(start_date) >= 7:
                start_month = start_date[:7]
                monthly_events = {month: events for month, events in monthly_events.items() 
                                 if month >= start_month}
                print(f"只分析{start_month}及之后的月份，共{len(monthly_events)}个月")
        
        # Step 2: 生成扩展润色后的事件插入计划
        print(f"\n[Step 2] 生成详细的事件插入计划...")
        insertion_plan = self._generate_insertion_plan(insertion_suggestion)
        print(f"✓ 已生成事件插入计划")
        
        # Step 3: 并行分析每个月的事件与插入计划的关联
        print(f"\n[Step 3] 并行分析各月事件与插入计划的关联...")
        monthly_analyses = self._parallel_analyze_monthly_impact(monthly_events, insertion_plan)
        print(f"✓ 已完成{len(monthly_analyses)}个月的分析")
        
        # Step 4: 整合分析结果，生成最终插入事件
        print(f"\n[Step 4] 整合分析结果，生成最终插入事件...")
        new_events_data = self._synthesize_new_events(monthly_analyses, insertion_plan)
        
        # 检查是否有拒绝插入的情况
        if new_events_data.get("reject_insertion", False):
            print(f"⚠️  {new_events_data.get('reject_reason', '')}")
            print(f"事件插入被拒绝，保持原图不变")
            return self.event_graph
        
        # Step 5: 将新事件合并到现有事件图中
        print(f"\n[Step 5] 合并新事件到现有图谱...")
        updated_graph = self._merge_new_events(new_events_data)
        
        # 更新实例属性
        self.event_graph = updated_graph
        
        # Step 6: 重写全年总结，融入新事件
        print(f"\n[Step 6] 重写全年总结，融入新事件...")
        new_events = new_events_data.get('events', [])
        updated_summary = self._rewrite_yearly_summary(new_events)
        self.yearly_summary = updated_summary
        print(f"✓ 全年总结已更新")
        
        event_count = len(new_events_data.get('events', []))
        print(f"\n{'='*60}")
        print(f"事件插入完成！成功插入{event_count}个新事件")
        print(f"{'='*60}")
        return updated_graph
    
    def _organize_events_by_month(self) -> Dict[str, List[Dict]]:
        """
        将现有事件按月份组织
        
        Returns:
            月份到事件列表的映射
        """
        monthly_events = {}
        
        for node in self.event_graph.get("nodes", []):
            time_data = node.get("time", [])
            if isinstance(time_data, list) and time_data:
                first_time = time_data[0]
                # 去除"至"，获取开始日期
                if "至" in first_time:
                    start_date = first_time.split("至")[0]
                else:
                    start_date = first_time
                
                # 提取月份（YYYY-MM）
                if len(start_date) >= 7:
                    month = start_date[:7]
                    if month not in monthly_events:
                        monthly_events[month] = []
                    monthly_events[month].append(node)
        
        return monthly_events
    
    def _generate_insertion_plan(self, insertion_suggestion: str) -> str:
        """
        生成详细的事件插入计划，包括每个月的事件安排和总体描述
        
        Args:
            insertion_suggestion: 原始的插入提示
        
        Returns:
            扩展润色后的事件插入计划（JSON 格式）
        """
        prompt = f"""你是一位专业的事件规划专家，请基于已有的一年生活数据总结和以下插入提示，制定一份详细的事件新增计划。

**全年总结（已有生活数据）：**
{self.yearly_summary if self.yearly_summary else '暂无全年总结'}

**插入提示：**
{insertion_suggestion}

**任务要求：**

**第一步：冲突检测与可行性分析**

请仔细分析插入提示与已有全年总结的关系：
1. **时间冲突**：提示中的事件是否与已有事件在时间上重叠或矛盾？
2. **逻辑冲突**：提示中的事件是否否定或与已有事件的逻辑相悖？
3. **重复检测**：提示中的事件是否与已有事件高度相似或重复？
4. **人物一致性**：提示中的事件是否符合人物画像和行为逻辑？
5. **叙事必要性**：这些新事件是否真的必要？是否能丰富原有叙事？
6. **真实性评估**：提示中的事件是否真实可信？是否符合常理和社会现实？
7. **合理性判断**：提示中的事件是否在给定条件下可能发生？是否存在明显的逻辑漏洞？
8. **违和感检测**：将提示中的事件加入已有数据后，是否会产生违和感或不协调？
9. **完美性考量**：现有提示是否足够丰富、生动、有血有肉？是否需要进一步充实？

**第二步：决策 - 拒绝或润色**

基于第一步的分析，做出以下两种决策之一：

### **决策 A：拒绝插入**

**仅在以下情况下选择拒绝：**
- 存在**严重的、无法调和的**时间冲突或逻辑矛盾
- 与人物画像**完全不符**且无法通过合理方式转化
- 事件**极度不真实**且没有合理的替代方案
- 加入已有数据会**彻底破坏**原有叙事结构


### **决策 B：润色并生成事件方案**

**默认选择此项**，因为任何插入提示都可以通过创作修改重写转化为合理的事件。

**当事件不合理时的修改重写原则：**
1. **理解核心意图**：深入分析插入提示背后的真实需求
   - 表面需求：“买别墅” → 核心需求：“改善居住条件”或“提升生活质量”
   - 表面需求：“考清华” → 核心需求：“追求更好的教育”或“证明自己能力”

2. **创造性转化**（当原提示不合理时）：
   - **降级转化**：将过于夸张的事件降为合理版本
     - 穷人买别墅 → 努力工作 + 贷款买小公寓/搬到更好的小区
     - 学渣考清华 → 制定学习计划 + 成绩逐步提升 + 考上理想大学
     - 普通人认识市长 → 参加社区活动 + 认识政府工作人员
   
   - **拆分重组**：将一个不可能的事件拆分为多个合理步骤
     - 突然暴富 → 获得奖金 + 投资收益 + 兼职收入
     - 一天学会外语 → 报名课程 + 每日练习 + 水平逐步提升
   
   - **转移焦点**：保持主题但改变实现方式
     - 没钱环球旅行 → 周边城市游 + 深度本地探索 + 云旅游学习
     - 直接创业成功 → 积累经验 + 小规模试错 + 逐步发展

3. **推理扩展事件**（当原提示过于简单或需要丰富时）：
   - **因果链推理**：从一个起点事件逐步推理出合理的后续发展
     - 示例：哥哥出差 → 帮哥哥照顾宠物 → 宠物生病去医院 → 在医院遇到领导 → 和领导因为宠物话题成为好友
     - 示例：决定学习 AI → 筛选在线课程 → 开始系统学习 → 完成第一个项目 → 应用到工作中 → 获得领导认可
     - 示例：认识新跑友 → 一起晨跑锻炼 → 讨论健康饮食 → 参加马拉松比赛 → 建立跑步社群
   
   - **多因推理**：分析一个事件可能引发的多个并行结果
     - 哥哥出差 → 
       - 分支 1：帮哥哥照顾宠物 → 宠物生病去医院 → 遇到兽医
       - 分支 2：独自在家 → 研究美食 → 成为厨艺达人
       - 分支 3：帮忙浇花 → 学习园艺 → 爱上植物
   
   - **递进发展**：展现事件的逐步升级和深化
     - 初步尝试 → 遇到困难 → 寻找方法 → 持续练习 → 取得进步 → 获得成果
   
   - **自然延伸**：基于事件本身的逻辑自然发展到下一步
     - 不要强行跳跃，每一步都要有合理的因果关系
     - 考虑时间、资源、能力等现实约束
     - 允许曲折和反复，更符合真实生活

4. **自然衔接**：
   - 与已有事件建立因果或时间关联
   - 填补已有数据的空白时间段
   - 呼应已有事件中埋下的伏笔
   - 为后续事件发展留下空间

5. **符合人物画像和现实逻辑**：

**如果原提示已经足够合理且丰富：**
- 可以直接按原提示生成，只需稍作润色使其更加生动
- 或者在原有基础上进一步丰富细节和情感

**第三步：撰写事件发展链条**

如果分析结果为可行（包括修改后的版本），请撰写一份完整的事件情节发展链条。

**创作原则：**
1. **连贯性**：新事件应与已有事件形成有机整体，符合全年总结中体现的生活轨迹
2. **互补性**：填补已有数据的空白或薄弱环节，而非简单重复
3. **合理性**：符合人物画像和生活逻辑，与全年总结保持一致
4. **戏剧变化性**：适当加入转折和波动和变化，但要自然流畅
5. **成长性**：展现人物的变化、进步或认知升级，现实世界是复杂且发展的。
6. **时间充实性**：如果事件可以继续产生后续因果事件，那么就继续充实下去，直到 12 月结束。但如果事件在中间某月份确定结束并没有后续影响，则可以提前结束。
7. **因果推理增强**：在每个事件之间，要考虑事件之间的因果关系。每个事件可考虑会引起什么样可能的事情，如哥哥出差->帮哥哥照顾宠物->宠物生病去医院->在医院遇到领导—>和领导因为宠物话题成为好友。这样一步一步生成事件可以生成更丰富的叙事。
8. **与已有事件尽量不同**：可以体现新插入数据受已有事件的影响，但尽量避免与已有事件相似或有关联（如已有一个投资医疗领域的事件，若新增投资事件则选择完全不同的领域如能源领域投资），尽量和已有事件不同或无明显相似，呈现互补关系。
注意，只需要撰写发生在 2025 年的事情，不需要考虑之前年份的事情和之后年份的发展，我们只关注当年发生的生活内容。

**输出格式（严格遵循 JSON 格式）：**
仅返回 JSON 对象，包含以下字段：
{{
    "feasibility": {{
        "is_feasible": true/false,
        "reason": "详细说明可行性判断的理由，200-300 字"
    }},
    "event_chain_summary": "一段完整的文本描述，包括：\n1. 总结部分：计划新增多少个事件（建议 3-8 个），这些事件形成一个怎样的故事线，事件之间如何发展演进，新事件如何与已有事件形成有机整体，这些新事件将如何丰富和补充原有的一年生活数据（共 300-500 字）\n2. 每月具体新增事件：按月份详细说明每个月新增哪些事件，每个事件包含名称、类型、具体时间、详细描述（包含起因经过结果）、与已有事件的呼应关系。不必每个月都有新增，根据实际需要安排。"
}}

**注意事项：**
- 如果 is_feasible 为 false，则 event_chain_summary 可为空字符串
- event_chain_summary 是一段完整的文本，不是结构化数据
- 请在 event_chain_summary 中清晰地先给出总结，再列出每月的具体事件
- 如果需要修改原始插入提示，请直接在 event_chain_summary 中呈现修改后的内容，不需要额外说明
- 即使发现可以优化，也可以选择直接拒绝插入（当存在严重冲突时）

请严格按照以上 JSON 格式输出，不要添加任何额外说明文字。
        """
        
        try:
            plan = llm_call_j(prompt).strip()
            self._print(f"  生成的插入计划：{plan}")
            print(f"  生成的插入计划长度：{len(plan)} 字符")
            return plan
        except Exception as e:
            print(f"⚠️  生成插入计划失败：{e}，使用原始提示")
            return insertion_suggestion
    
    def _parallel_analyze_monthly_impact(self, monthly_events: Dict[str, List[Dict]], 
                                        insertion_plan: str) -> Dict[str, Any]:
        """
        并行分析每个月的事件与插入计划的关联，并给出合理性优化建议
        
        Args:
            monthly_events: 月份到事件列表的映射
            insertion_plan: 扩展后的事件插入计划
        
        Returns:
            每月分析结果的字典
        """
        monthly_analyses = {}
        
        def analyze_month(month: str, events: List[Dict]):
            """分析单个月份的事件影响和优化建议"""
            prompt = f"""
你是一位专业的事件分析专家，现在想在今年的个人生活数据中加入新的事件。请分析以下月份的事件与插入计划之间的关联，判断插入计划是否合理，是否与本月现有事件重复或冲突，或者是否会产生影响。

**当前月份**：{month}

**该月现有事件**（共{len(events)}个）：
{json.dumps(events, ensure_ascii=False, indent=2)}

**事件插入计划**：
{insertion_plan}

**分析要求：**

**第一步：关联性分析**
- 插入计划中的哪些事件与本月现有事件可能有关联或影响？
- 具体是哪些事件之间可能存在关联（因果、并列、对比等）？

**第二步：合理性评估**
- 插入计划中针对本月的安排是否合理？
- **时间冲突**：是否有时间上的重叠或矛盾？
- **逻辑冲突**：是否存在逻辑矛盾或与已有事件的因果关系相悖？
- **重复检测**：是否有与本月现有事件高度相似或重复的内容？
- **人物一致性**：是否符合人物画像和行为逻辑？

**第三步：给出建议**

根据以上分析，按以下两种情况给出建议：

**情况 1：存在不合理冲突**
如果插入计划与本月数据存在严重冲突、矛盾或不合理的影响：
- 明确指出问题所在（具体的冲突点）
- 要求对插入计划进行修改和重新制定
- 给出具体的重新制定建议（如调整时间、修改内容、改变事件类型等）

**情况 2：无冲突但可优化关联**
如果插入计划与本月数据无关或无明显冲突，但本月现有事件可以影响插入的数据：
- 简要给出润色插入计划的建议
- 指出如何利用本月现有事件来丰富或加强插入事件的关联性
- 建议要简洁，不要过多展开，点到为止

**输出格式：**
仅输出【优化建议】、【原因】和【本月小结】，不需要其他分析内容。

【优化建议】
根据分析结果，给出具体的建议：
- 如有严重冲突：要求修改计划并给出重新制定的方向
- 如无冲突但可优化：简要给出润色建议，体现事件关联（控制在 100 字以内）

【原因】
简要说明提出上述建议的原因（基于关联性分析和合理性评估的结果）

【本月小结】
简要说明本月的主要事件和对插入计划有关联的事件

            """
            
            try:
                response = llm_call(prompt).strip()
                return month, response
            except Exception as e:
                print(f"分析月份 {month} 失败：{str(e)}")
                return month, f"分析失败：{str(e)}"
        
        # 并行处理所有月份
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            future_to_month = {executor.submit(analyze_month, month, events): month 
                             for month, events in monthly_events.items()}
            
            for future in concurrent.futures.as_completed(future_to_month):
                month, analysis = future.result()
                monthly_analyses[month] = analysis
        self._print(f"  所有月份分析完成{monthly_analyses}")
        return monthly_analyses
    
    def _synthesize_new_events(self, monthly_analyses: Dict[str, Any], 
                              insertion_plan: str) -> Dict:
        """
        整合月份分析结果，生成完整的新事件方案（包含节点和边），支持拒绝插入
        
        Args:
            monthly_analyses: 每月分析结果
            insertion_plan: 扩展后的事件插入计划
        
        Returns:
            包含 events、internal_edges 的字典，或包含 reject_insertion 标志的字典
        """
        # 提取起始月份
        start_month = None
        if monthly_analyses:
            months = list(monthly_analyses.keys())
            if months:
                start_month = min(months)
        
        # 第一次 LLM 调用：整合分析结果，检测冲突，决定是否拒绝插入
        print(f"  正在整合分析结果...")
        integration_result = self._integrate_analyses_and_check_conflicts(
            monthly_analyses, insertion_plan, start_month
        )
        
        # 检查是否需要拒绝插入
        if integration_result.get("reject_insertion", False):
            return {
                "reject_insertion": True,
                "reject_reason": integration_result.get("reject_reason", "")
            }
        
        # 第二次 LLM 调用：格式化事件并分配边
        events_raw = integration_result.get("events_text", "")
        result = self._format_events_and_assign_edges(events_raw, start_month)
        
        return result
    
    def _integrate_analyses_and_check_conflicts(self, monthly_analyses: Dict[str, Any], 
                                                 insertion_plan: str, 
                                                 start_month: str = None) -> Dict:
        """
        整合各月分析结果，检测冲突，生成事件文本描述
        
        Args:
            monthly_analyses: 每月分析结果
            insertion_plan: 扩展后的事件插入计划
            start_month: 起始月份
        
        Returns:
            包含 events_text 文本，或 reject_insertion 标志的字典
        """
        # 第一轮：独立判断是否应该拒绝插入
        self._print(f"  [拒绝检查] 第一轮 LLM 调用：判断是否应该拒绝插入...")
        rejection_check = self._check_rejection(monthly_analyses, insertion_plan)
        
        if rejection_check.get("reject", False):
            self._print(f"⚠️  [拒绝检查] 判断结果：拒绝插入 - {rejection_check.get('reason', '')}")
            return {
                "reject_insertion": True,
                "reject_reason": rejection_check.get("reason", "")
            }
        
        self._print(f"✓ [拒绝检查] 判断结果：可以继续生成事件方案")
        
        # 第二轮：生成事件方案
        self._print(f"  [事件生成] 第二轮 LLM 调用：整合分析结果，生成事件方案...")
        response = self._generate_event_plan(insertion_plan, monthly_analyses, start_month)
        
        return {
            "events_text": response
        }
    
    def _check_rejection(self, monthly_analyses: Dict[str, Any], 
                         insertion_plan: str) -> Dict:
        """
        独立的 LLM 调用：判断是否应该拒绝插入
        
        Args:
            monthly_analyses: 每月分析结果
            insertion_plan: 扩展后的事件插入计划
        
        Returns:
            包含 reject 标志和 reason 的字典
        """
        prompt = f"""
你是一位专业的事件整合风险评估专家。请基于以下月份分析结果和插入计划，严格判断是否应该拒绝此次事件插入。

**事件插入计划：**
{insertion_plan}

**各月分析结果：**
{json.dumps(monthly_analyses, ensure_ascii=False, indent=2)}

**评估维度：**

1. **时间冲突**：是否有新事件与现有事件在时间上严重重叠？
2. **逻辑矛盾**：新事件是否否定或与已有事件的因果关系相悖？
3. **重复事件**：新事件是否与已有事件高度相似或完全重复？
4. **人物一致性**：新事件是否严重不符合人物画像和行为逻辑？
5. **叙事破坏**：新事件是否会严重破坏原有的叙事结构和生活轨迹？

**决策标准：**

【必须拒绝的情况】（同时满足以下条件）：
- 存在**严重的、无法调和的**冲突
- 冲突涉及核心事件或关键时间节点
- 无法通过调整来解决

【可以接受的情况】（满足任一条件即可继续）：
- 没有发现严重冲突
- 冲突是局部的、可以通过微调解决的
- 整体可行，只是某些细节需要优化

**输出格式（JSON）：**
{{
    "reject": true/false,
    "reason": "如果 reject 为 true，详细说明拒绝原因；如果为 false，说明可以继续的理由"
}}

**重要提示：**
- 请谨慎使用"拒绝"决定，只有在确实存在严重且无法解决的问题时才拒绝
- 对于可以通过调整优化的情况，应该选择继续
- 理由要具体明确，指出问题所在

请以 JSON 格式返回判断结果。
        """
        
        try:
            response = llm_call_j(prompt).strip()
            # 提取 JSON 部分
            start_idx = response.find('{')
            end_idx = response.rfind('}')
            if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                json_response = response[start_idx:end_idx + 1]
                result = json.loads(json_response)
                
                return {
                    "reject": result.get("reject", False),
                    "reason": result.get("reason", "")
                }
            else:
                self._print("✗ 无法提取 JSON，默认不拒绝")
                return {"reject": False, "reason": "解析失败，默认允许继续"}
                
        except Exception as e:
            self._print(f"✗ 拒绝检查失败：{e}，默认不拒绝")
            return {"reject": False, "reason": f"检查过程出错：{str(e)}"}
    
    def _generate_event_plan(self, insertion_plan: str, 
                             monthly_analyses: Dict[str, Any],
                             start_month: str = None) -> str:
        """
        生成事件方案的独立 LLM 调用
        
        Args:
            insertion_plan: 扩展后的事件插入计划
            monthly_analyses: 每月分析结果
            start_month: 起始月份
        
        Returns:
            事件方案文本
        """
        prompt = f"""
你是一位专业的事件整合专家，请整合以下月份的分析结果，制定最终的事件插入方案。

**事件插入计划：**
{insertion_plan}

**各月分析结果：**
{json.dumps(monthly_analyses, ensure_ascii=False, indent=2)}

**时间范围：** {start_month if start_month else '2025-01'} 到 2025-12

**任务要求：**

**创作原则：**
1. **自由发挥**：不必每个月都有事件，根据叙事需要自由安排密度和节奏
2. **数量灵活**：设计 3-12 个事件，关键是要讲好完整的故事
3. **体现发展**：展现人物的成长轨迹、关系变化、技能提升等动态过程
4. **连贯合理**：事件之间要有清晰的逻辑联系
5. **呼应优化**：充分考虑各月分析中的优化建议
6. **避免同质与重复事件**：新事件不能与已有事件相似或重复或同质，要展现处不同，和现有时间互补，丰富现有数据。
事件设计提示：
1. **丰富细节**：合理创作，增强事件，体现事件发展，起因、经过、结果
2. **分支发展**：可以设计可以引发多条分支故事线：例如哥哥出差->帮哥哥照顾宠物->宠物生病去医院->在医院遇到领导—>和领导因为宠物话题成为好友、和哥哥出差->帮哥哥照顾宠物->帮宠物拍照->分析给男友->男友提议养狗 这是两条可并行发生的分支
3. **多因合并**：可以设计"多因一果"的复合事件或整合事件：例如：我介绍哥哥认识我的舍友->两人恋爱并同居->两人决定养狗 和 哥哥出差 共同导致 我要帮哥哥照顾宠物。
4. **后续补充**：确保重要事件有完整的起承转合，应当有后续的事件突然中断或提前结束（如 6 月份认识新跑友，后续与跑友一起跑步的相关事件）
5. **冲突避免**：严格确保不与已有事件冲突
6. **事件网络**：构建复杂的事件关系网络
7. **与已有事件尽量不同**：可以提体现新插入数据受已有事件的影响，但尽量避免与已有事件相似或有关联（如已有一个投资医疗领域的事件，若新增投资事件则选择完全不同的领域如能源领域投资），尽量和已有事件不同，呈现互补关系。
8. **每月分析结果的意见并不一定要采纳，事实上有很多月份与本事件插入计划无关，不用关心**，请根据实际情况判断是否采纳。
请按以下格式输出每个事件：

=== 事件 1 ===
名称：[事件名称]
时间：[YYYY-MM-DD，必须在时间范围内]
类型：[Career/Health/Relationships/Education/Finance/Personal Life/Family&Living Situation - 只能选择一个]
描述：[详细的事件描述，包含起因、经过、结果，体现人物变化]

=== 事件 2 ===
...

=== 事件间关系 ===
[描述事件之间的关系，包括因果、分支、合并等]

=== 优化说明 ===
[说明如何采纳了各月分析中的优化建议]
        """
        
        try:
            response = llm_call(prompt).strip()
            return response
        except Exception as e:
            self._print(f"✗ 生成事件方案失败：{e}")
            raise
    
    def _format_events_and_assign_edges(self, events_raw: str, 
                                       start_month: str = None) -> Dict:
        """
        分两轮 LLM 调用：第一轮格式化事件，第二轮为事件分配边
        
        Args:
            events_raw: 事件文本描述
            start_month: 起始月份
        
        Returns:
            包含 events 和 internal_edges 的字典
        """
        # 第一轮：格式化事件
        print(f"  第一轮 LLM 调用：格式化事件...")
        events_result = self._format_events(events_raw, start_month)
        
        if not events_result.get("events"):
            print("✗ 事件格式化失败")
            return {"events": [], "internal_edges": []}
        
        # 第二轮：为事件分配边
        print(f"  第二轮 LLM 调用：为事件分配边...")
        edges_result = self._assign_edges(events_result["events"])
        
        return {
            "events": events_result["events"],
            "internal_edges": edges_result.get("edges", [])
        }
    
    def _format_events(self, events_raw: str, start_month: str = None) -> Dict:
        """
        第一轮 LLM 调用：将事件描述转换为标准 JSON 格式
        
        Args:
            events_raw: 事件文本描述
            start_month: 起始月份
        
        Returns:
            包含 events 的字典
        """
        prompt = f"""
请将以下事件描述转换为标准的 JSON 格式。

**事件描述：**
{events_raw}

**输出格式：**
仅返回 JSON 格式，包含以下字段：
{{
    "events": [
        {{
            "id": "整数，从 10000 开始递增（后续会重新分配）",
            "name": "事件名称",
            "description": "详细描述（包含起因、经过、结果）",
            "type": "事件类型（只能选择一个：Career/Health/Relationships/Education/Finance/Personal Life/Family&Living Situation）",
            "time": ["YYYY-MM-DD 至 YYYY-MM-DD"]
        }}
    ]
}}

**严格要求：**
1. **类型单一性**：每个事件的 type 字段只能选择一个最匹配的类型，不要使用多个类型组合
2. **时间格式**：必须提供具体的起止日期，格式为 "YYYY-MM-DD 至 YYYY-MM-DD"
3. **ID 占位符**：ID 只需从 10000 开始递增即可，系统会自动重新分配
4. **完整性**：确保每个事件都有清晰的起因背景、详细经过、结果
5. **详细性**：事件描述要具体、有血有肉，包含场景、行为和感受

请严格按照以上格式输出 JSON。
        """
        
        try:
            response = llm_call_j(prompt).strip()
            # 提取 JSON 部分
            start_idx = response.find('{')
            end_idx = response.rfind('}')
            if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                json_response = response[start_idx:end_idx + 1]
                result = json.loads(json_response)
                
                events = result.get("events", [])
                
                # 重新分配 ID：基于现有数据的最大 ID
                events = self._reassign_event_ids(events)
                
                # 更新 result 中的 events
                result["events"] = events
                
                print(f"✓ 第一轮完成：生成了{len(events)}个事件")
                return result
            else:
                print("✗ 无法提取 JSON")
                return {"events": []}
        except Exception as e:
            print(f"✗ 格式化事件失败：{str(e)}")
            return {"events": []}
    
    def _reassign_event_ids(self, events: List[Dict]) -> List[Dict]:
        """
        重新分配事件 ID，基于现有数据的最大 ID 递增
        
        Args:
            events: 事件列表
        
        Returns:
            重新分配 ID 后的事件列表
        """
        # 获取现有图谱中的最大 ID
        max_id = 0
        for node in self.event_graph.get("nodes", []):
            node_id = node.get("id")
            if isinstance(node_id, int) and node_id > max_id:
                max_id = node_id
        
        # 为新事件分配 ID（从 max_id + 1 开始）
        new_events = []
        for i, event in enumerate(events):
            new_event = event.copy()
            new_event["id"] = max_id + 1 + i
            new_events.append(new_event)
        
        print(f"  事件 ID 重分配：从 {max_id + 1} 到 {max_id + len(events)}")
        return new_events
    
    def _assign_edges(self, events: List[Dict]) -> Dict:
        """
        第二轮 LLM 调用：为事件之间分配边
        
        Args:
            events: 事件列表
        
        Returns:
            包含 edges 的字典
        """
        events_str = json.dumps(events, ensure_ascii=False, indent=2)
        
        prompt = f"""
请为以下事件之间分配边，描述事件之间的关系。

**事件列表：**
{events_str}

**边的类型包括：**
- causality: 因果关系（事件 A 导致事件 B）
- development: 发展关系（事件 B 是事件 A 的下一个发展阶段或下一个步骤，如 A->B->C 的流程）

**输出格式：**
仅返回 JSON 格式，包含以下字段：
{{
    "edges": [
        {{
            "source": 源事件 ID,
            "target": 目标事件 ID,
            "type": "边类型（causality/development）",
            "description": "边的描述，说明两个事件之间的具体关系"
        }}
    ]
}}

**要求：**
1. 仔细分析事件之间的因果关系和发展流程
2. 为有明显关系的事件分配边
3. 边的描述要清晰准确，体现关系的本质
4. 可以为一对多、多对一的关系分配边
5. 注意识别复杂的关系网络（如 A->B->C 同时 A->D->C）
        """
        
        try:
            response = llm_call_j(prompt).strip()
            # 提取 JSON 部分
            start_idx = response.find('{')
            end_idx = response.rfind('}')
            if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                json_response = response[start_idx:end_idx + 1]
                result = json.loads(json_response)
                
                edges = result.get("edges", [])
                print(f"✓ 第二轮完成：生成了{len(edges)}条边")
                return result
            else:
                print("✗ 无法提取 JSON")
                return {"edges": []}
        except Exception as e:
            print(f"✗ 分配边失败：{str(e)}")
            return {"edges": []}
    
    def _merge_new_events(self, new_events_data: Dict) -> Dict:
        """
        将新事件合并到现有事件图中
        
        Args:
            new_events_data: 包含 events 和 internal_edges 的字典
        
        Returns:
            更新后的事件图谱
        """
        # 复制现有事件图
        updated_graph = {
            "nodes": self.event_graph.get("nodes", []).copy(),
            "edges": self.event_graph.get("edges", []).copy()
        }
        
        # 获取新事件和内部边
        new_events = new_events_data.get("events", [])
        internal_edges = new_events_data.get("internal_edges", [])
        
        # 添加新事件节点
        for event in new_events:
            node = {
                "id": event.get("id", ""),
                "name": event.get("name", ""),
                "description": event.get("description", ""),
                "time": event.get("time", []),  # 使用 time 字段而不是 date
                "type": event.get("type", "")
            }
            updated_graph["nodes"].append(node)
        
        # 添加新事件之间的内部边
        updated_graph["edges"].extend(internal_edges)
        
        return updated_graph
    
    def _rewrite_yearly_summary(self, new_events: List[Dict]) -> str:
        """
        重写全年总结，融入新加入的事件序列（增量式重写）
        
        Args:
            new_events: 新插入的事件列表
        
        Returns:
            更新后的全年总结
        """
        self._print(f"  正在重写全年总结...")
        
        # 构建新事件的文本描述
        new_events_text = "\n\n新增事件序列：\n"
        for i, event in enumerate(new_events, 1):
            name = event.get('name', '未知事件')
            date = event.get('time', event.get('date', '未知日期'))
            desc = event.get('description', '')
            event_type = event.get('type', '未知类型')
            
            new_events_text += f"\n{i}. {name} - {date}\n"
            new_events_text += f"   类型：{event_type}\n"
            new_events_text += f"   描述：{desc}\n"
        
        prompt = f"""
你是一位专业的年度生活记录整理专家。请将新发生的事件自然地融入到已有的一年生活总结中。

**原有全年总结：**
{self.yearly_summary if self.yearly_summary else '暂无全年总结'}

{new_events_text}

**重写要求：**

1. **增量式整合**：
   - 保留原有总结的大部分内容和结构
   - 不要删除已有的重要内容和关键事件
   - 在合适的位置自然地加入新事件

2. **自然融合**：
   - 新事件要与原有叙事流畅衔接
   - 体现新事件与已有事件的关联和呼应
   - 展现生活的连续性和发展性

3. **突出重点**：
   - 如果新事件很重要，可以适当增加篇幅
   - 保持原有总结的核心主题和基调
   - 确保整体叙事的连贯一致

4. **细节丰富**：
   - 保留原有的生动细节
   - 为新事件补充合理的场景、感受和反思
   - 让整篇总结更加充实和立体

5. **时间线索**：
   - 按照时间顺序或主题组织内容
   - 清晰标注新事件的发生时间
   - 体现全年的生活节奏和变化轨迹

请直接输出重写后的完整全年总结，不需要任何额外说明。
        """
        
        try:
            updated_summary = llm_call(prompt).strip()
            self._print(f"✓ 全年总结重写完成：{len(updated_summary)} 字符")
            return updated_summary
        except Exception as e:
            self._print(f"⚠️  全年总结重写失败：{e}，保持原总结不变")
            return self.yearly_summary
