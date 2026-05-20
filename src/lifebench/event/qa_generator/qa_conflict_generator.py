import json
import os
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
import threading
import concurrent.futures

from src.lifebench.utils.llm_call import llm_call, llm_call_j
from .base_generator import BaseQAGenerator
from .phone_operation_generator import PhoneOperationGenerator


class QAConflictGenerator(BaseQAGenerator):
    """冲突问题生成器 - 基于记忆错误、计划突变等场景生成包含矛盾证据的问题"""

    def __init__(self, daily_event: List[Dict], draft_event: Dict[str, List],
                 phonedata: Dict[str, List], phone_data_dir: str = None,
                 is_print: bool = True, year: int = 2025,
                 persona_data: Dict[str, Any] = None):
        """
        初始化冲突问题生成器

        Args:
            daily_event: daily_event 数据列表
            draft_event: draft_event 数据字典（按月份组织）
            phonedata: 手机操作数据字典
            phone_data_dir: 手机数据目录路径
            is_print: 是否打印调试信息
            year: 年份，默认 2025
            persona_data: 用户画像数据，包含 name 字段
        """
        super().__init__()
        self.daily_event = daily_event
        self.draft_event = draft_event
        self.phonedata = phonedata
        self.phone_data_dir = phone_data_dir
        self.is_print = is_print
        self.persona_data = persona_data or {}
        self.persona_name = self.persona_data.get('name', '用户')

        # 线程锁
        self.phonedata_lock = threading.Lock()
        self.phone_id_counters = {}
        self.default_ask_time = f"{year}-12-31"

        # 手机操作生成器
        self.phone_op_generator = PhoneOperationGenerator()
    
    def _generate_monthly_summary(self, year: int, month: int) -> Dict[str, Any]:
        """
        基于 draft_event 生成单个月份的主要事件总结
        
        Args:
            year: 年份
            month: 月份
            
        Returns:
            月份总结数据
        """
        month_key = f"{year}-{month:02d}"
        print(f"\n[Monthly Summary] 生成 {month_key} 的月份总结...")
        
        # 获取该月份的 draft_event 数据
        month_events = self.draft_event.get(month_key, [])
        
        if not month_events or not isinstance(month_events, list):
            print(f"[Monthly Summary] {month_key} 没有事件数据")
            return None
        
        prompt = f"""
        作为月度事件总结专家，请分析以下 {month_key} 的生活记录数据，输出{self.persona_name}本月主要做了什么。

        **重要**：请使用 {self.persona_name} 而不是"我/自己"来指代用户。

        【月份数据】
        {json.dumps(month_events, ensure_ascii=False, indent=2)}

        **核心要求**
        - **叙述性总结**：以"{self.persona_name}这个月主要做了什么"的角度进行总结
        - **包含重要事件**：出行、娱乐、工作成就、社交活动等重要活动都要包含
        - **数量限制**：只输出 10-15 个最主要的事件
        - **独立性保证**：输出的事件之间不应存在可合并的步骤关系

        **提取标准**
        1. **出行旅游事件**：短途旅行、长途旅游、出差等
        2. **娱乐休闲事件**：看电影、演唱会、聚会、运动比赛等
        3. **工作学习事件**：完成项目、考试、培训、技能提升等
        4. **健康医疗事件**：体检、治疗、健身突破等
        5. **社交人际事件**：重要聚会、拜访亲友、参加活动等
        6. **其他重要事件**：购物大件、搬家整理、特殊体验等

        **排除标准**
        ❌ 不要提取日常琐事（普通用餐、通勤、日常购物等）
        ❌ 不要提取规划性事件（计划但未执行的活动）

        **输出要求**
        请以 JSON 格式返回数组：
        [
            {{
                "date": "YYYY-MM-DD 或 YYYY-MM-DD 至 YYYY-MM-DD",
                "event_description": "事件描述（简洁突出{self.persona_name}做了什么）",
                "event_type": "事件类型（出行/娱乐/工作/健康/社交/其他）"
            }}
        ]
        """
        
        try:
            llm_result = llm_call_j(prompt)
            
            if self.is_print:
                print(f"\n[Monthly Summary - {month_key}] LLM 输出:")
                print(llm_result[:300] + "..." if len(llm_result) > 300 else llm_result)
            
            # 解析结果
            if isinstance(llm_result, str):
                start_idx = llm_result.find('[')
                end_idx = llm_result.rfind(']') + 1
                if start_idx != -1 and end_idx != -1:
                    json_str = llm_result[start_idx:end_idx]
                    important_events = json.loads(json_str)
                else:
                    return None
            elif isinstance(llm_result, list):
                important_events = llm_result
            else:
                return None
            
            if not isinstance(important_events, list):
                return None
            
            summary = {
                'month': month_key,
                'important_events': important_events,
                'event_count': len(important_events)
            }
            
            print(f"[Monthly Summary] {month_key} 提取了 {len(important_events)} 个重要事件")
            return summary
                
        except Exception as e:
            print(f"[Monthly Summary - {month_key}] 提取失败：{e}")
            return None
    
    def _locate_daily_events(self, summary_events: List[Dict[str, Any]], 
                             date_offset: int = 1) -> List[Dict[str, Any]]:
        """
        基于summary事件的日期，在目标日期及其前后offset天的范围内搜索daily_event（20线程并行）
        
        Args:
            summary_events: summary中的事件列表
            date_offset: 日期偏移量（前后各offset天），默认1
            
        Returns:
            找到的daily_event事件列表（已去重）
        """
        from datetime import datetime, timedelta
        import concurrent.futures
        
        print(f"[_locate_daily_events] 开始定位 {len(summary_events)} 个事件的daily_event（20线程并行）...")
        
        # 定义单个事件的搜索函数
        def search_single_event(event):
            date_str = event.get('date', '')
            description = event.get('description', '') or event.get('event_description', '')
            
            print(f"[_locate_daily_events.search_single_event] 开始处理事件: date={date_str}, desc={description[:50]}...")
            
            if not date_str:
                print(f"[_locate_daily_events.search_single_event] 跳过：缺少日期")
                return []
            
            try:
                # 解析日期
                start_date_str = date_str.split('至')[0].strip()[:10]
                target_date = datetime.strptime(start_date_str, '%Y-%m-%d')
                
                # 计算日期范围
                prev_date = target_date - timedelta(days=date_offset)
                next_date = target_date + timedelta(days=date_offset)
                
                date_range = [
                    prev_date.strftime('%Y-%m-%d'),
                    target_date.strftime('%Y-%m-%d'),
                    next_date.strftime('%Y-%m-%d')
                ]
                
                print(f"[_locate_daily_events.search_single_event] 日期范围: {date_range}")
                
                # 调用LLM搜索
                found_events = self._search_daily_events_by_llm(
                    date_range=date_range,
                    event_description=description,
                    target_date=start_date_str
                )
                
                print(f"[_locate_daily_events.search_single_event] 找到 {len(found_events)} 个匹配事件")
                return found_events
                    
            except Exception as e:
                print(f"[_locate_daily_events.search_single_event] 处理事件失败：{e}")
                import traceback
                traceback.print_exc()
                return []
        
        # 使用 ThreadPoolExecutor 并行处理，最多20线程
        all_found_daily_events = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            # 提交所有任务
            future_to_event = {
                executor.submit(search_single_event, event): event
                for event in summary_events
            }
            
            # 收集结果
            completed_count = 0
            for future in concurrent.futures.as_completed(future_to_event):
                try:
                    result = future.result()
                    if result:
                        all_found_daily_events.extend(result)
                    completed_count += 1
                    if completed_count % 5 == 0 or completed_count == len(summary_events):
                        print(f"[_locate_daily_events] 已完成 {completed_count}/{len(summary_events)} 个事件的搜索")
                except Exception as e:
                    print(f"[_locate_daily_events] 任务执行失败：{e}")
        
        if not all_found_daily_events:
            print("[_locate_daily_events] 未找到任何daily_event事件")
            return []
        
        print(f"[_locate_daily_events] 总共找到{len(all_found_daily_events)}个daily_event事件")
        
        # 去重（基于event_id）
        unique_events = {}
        for event in all_found_daily_events:
            event_id = event.get('event_id', '') or event.get('atomic_id', '')
            if event_id and event_id not in unique_events:
                unique_events[event_id] = event
        
        deduped_events = list(unique_events.values())
        print(f"[_locate_daily_events] 去重后剩余{len(deduped_events)}个事件")
        
        return deduped_events
    
    def _search_daily_events_by_llm(self, date_range: List[str], 
                                     event_description: str, 
                                     target_date: str) -> List[Dict[str, Any]]:
        """
        通过LLM在指定日期范围内搜索与描述匹配的daily_event
        
        Args:
            date_range: 日期范围列表 [prev_date, target_date, next_date]
            event_description: 事件描述
            target_date: 目标日期
            
        Returns:
            匹配的daily_event列表
        """
        print(f"[_search_daily_events_by_llm] 开始搜索: target_date={target_date}, date_range={date_range}")
        print(f"[_search_daily_events_by_llm] 事件描述: {event_description[:100]}...")
        
        # 从 daily_event 中筛选出在日期范围内的事件
        candidate_events = []
        for event in self.daily_event:
            if isinstance(event, dict):
                event_date = event.get('date', '')
                
                # 处理 date 字段可能是列表的情况
                if isinstance(event_date, list):
                    # 如果是列表，取第一个元素
                    if event_date:
                        event_date = event_date[0]
                    else:
                        continue
                
                # 处理日期范围格式 "YYYY-MM-DD HH:MM:SS至YYYY-MM-DD HH:MM:SS"
                if '至' in str(event_date):
                    start_date = str(event_date).split('至')[0].strip()[:10]
                    end_date = str(event_date).split('至')[1].strip()[:10]
                    if start_date <= target_date <= end_date:
                        candidate_events.append(event)
                else:
                    # 单一日期
                    single_date = str(event_date)[:10]
                    if single_date in date_range:
                        candidate_events.append(event)
        
        print(f"[_search_daily_events_by_llm] 筛选出 {len(candidate_events)} 个候选事件")
        
        if not candidate_events:
            print(f"[_search_daily_events_by_llm] 警告：在日期范围 {date_range} 内没有找到任何候选事件")
            print(f"[_search_daily_events_by_llm] self.daily_event 总共有 {len(self.daily_event)} 个事件")
            # 打印前3个事件的日期用于调试
            for i, evt in enumerate(self.daily_event[:3]):
                print(f"  事件{i+1}: date={evt.get('date', 'N/A')}, desc={evt.get('event_description', 'N/A')[:50]}")
            return []
        
        # 构建 prompt
        prompt = f"""
        作为事件匹配专家，请从以下候选事件中找出与目标事件**最独特、最重要、最匹配的一个事件**。
        
        【目标事件】
        日期：{target_date}
        描述：{event_description}
        
        【候选事件】（共{len(candidate_events)}个）
        {json.dumps(candidate_events, ensure_ascii=False, indent=2)}
        
        **任务要求**
        1. 分析目标事件与每个候选事件的相似度
        2. **只选择最匹配的1个事件**（必须且只能选择一个）
        3. 选择标准（按优先级排序）：
           - **独特性**：该事件是否有独特的特征（如特殊的时间、地点、人物组合），与其他事件区分度高
           - **重要性**：该事件是否是关键事件（如涉及重要人物、重要决策、重要活动）
           - **匹配度**：日期相近、描述内容相似、事件类型一致
        4. 如果多个事件都很相似，选择**最具代表性、最核心**的那一个
        
        **输出要求**
        请以 JSON 数组格式返回**唯一匹配的事件ID**：
        ["event_id"]
        
        **重要约束**
        - **必须且只能返回一个事件ID**
        - 如果没有匹配的事件，返回空数组 []
        - 不要返回多个事件，即使它们都很相似
        """
        
        print(f"[_search_daily_events_by_llm] 调用 LLM 进行匹配...")
        
        try:
            llm_result = llm_call_j(prompt)
            print(f"[_search_daily_events_by_llm] LLM 返回结果: {str(llm_result)[:200]}...")
            
            if isinstance(llm_result, str):
                start_idx = llm_result.find('[')
                end_idx = llm_result.rfind(']') + 1
                if start_idx != -1 and end_idx != -1:
                    matched_ids = json.loads(llm_result[start_idx:end_idx])
                else:
                    return []
            elif isinstance(llm_result, list):
                matched_ids = llm_result
            else:
                return []
            
            # 根据ID提取完整事件
            matched_events = []
            for event_id in matched_ids:
                for event in candidate_events:
                    if event.get('event_id') == event_id or event.get('atomic_id') == event_id:
                        matched_events.append(event)
                        break
            
            print(f"[_search_daily_events_by_llm] 匹配到 {len(matched_events)} 个事件")
            return matched_events
                
        except Exception as e:
            print(f"[_search_daily_events_by_llm] LLM搜索失败：{e}")
            return []
    
    def _sample_conflict_events(self, monthly_summaries: List[Dict], num_samples: int = 20) -> List[Dict]:
        """
        从全年月份总结中随机采样指定数量的事件用于生成冲突情节
        
        Args:
            monthly_summaries: 月份总结列表
            num_samples: 采样数量
            
        Returns:
            采样的事件列表
        """
        print(f"\n[Sample Conflict Events] 开始采样 {num_samples} 个事件...")
        
        # 收集所有事件
        all_events = []
        for summary in monthly_summaries:
            if summary and summary.get('important_events'):
                for event in summary['important_events']:
                    event['month'] = summary['month']
                    all_events.append(event)
        
        if not all_events:
            print("[Sample Conflict Events] 没有可用的事件")
            return []
        
        # 随机采样
        sampled_events = random.sample(all_events, min(num_samples, len(all_events)))
        
        print(f"[Sample Conflict Events] 从 {len(all_events)} 个事件中采样了 {len(sampled_events)} 个")
        return sampled_events
    
    def _generate_conflict_plot(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        为单个事件生成冲突情节（模拟记忆错误、计划突变、信息传递错误等场景）
        
        Args:
            event: 事件数据（必须包含 daily_event_data）
            
        Returns:
            冲突情节数据，如果没有 daily_event_data 则返回 None
        """
        # 只使用 daily_event_data，如果没有则不生成
        daily_event_data = event.get('daily_event_data')
        
        if not daily_event_data or not isinstance(daily_event_data, dict):
            print(f"[_generate_conflict_plot] 跳过：事件缺少 daily_event_data")
            return None
        
        # 使用完整的 daily_event 数据
        event_info = daily_event_data
        
        conflict_types = [
            "记忆错误：用户记错了事件的某个关键细节（时间/地点/人物/内容）",
            "计划突变：用户临时改变了计划但没有更新所有相关记录",
            "信息传递错误：在不同渠道（短信、邮件、对话）中传达了不一致的信息",
            "多方协调不一致：多个参与方对同一事件的理解或安排有差异",
            "遗忘与混淆：用户忘记了某些细节，与其他类似事件混淆",
            "意图与行动不符：用户原本打算做某事，但实际做了另一件事",
            "记忆冲突（回忆冲突）：在后续回忆该事件时给出了错误的信息"
        ]
        
        conflict_type = random.choice(conflict_types)
        
        prompt = f"""
        作为冲突情节设计师，请基于以下事件，设计一个合理的冲突场景。

        **重要**：请使用 {self.persona_name} 而不是"我/自己"来指代用户。在生成的手机数据内容中，也必须使用 {self.persona_name}。

        【原始事件】
        {json.dumps(event_info, ensure_ascii=False, indent=2)}
        
        【冲突类型及错误信息来源】
        {conflict_type}
        
        **重要提示：灵活选择冲突类型**
        - 上述冲突类型仅作为参考和启发
        - **如果当前类型难以设计出合理、自然的冲突情节，可以自由选择其他更适合的冲突类型**
        - 优先考虑冲突的合理性、真实性和可设计性，不必严格遵循指定的类型
        - 最终目标是生成一个逻辑清晰、符合生活场景的冲突故事

        **选择记错内容的指导原则**
        在设计冲突情节之前，先分析事件的特点，选择最容易被误导且有意义的方面：

        1. **分析事件的独特性**：
           - **一次性/罕见事件**（如：手术抢救、车祸、参加特定聚会、获得奖项等）：日期、地点、参与人物、具体内容都可以作为提问焦点
           - **日常重复性事件**（如：晨跑、上班通勤、常规健身、吃饭睡觉等）：不建议记错日期（因为每天都在做，日期没有特殊性），更适合记错具体内容（如跑了多远、吃的什么）、参与人物（和谁一起）、地点细微差别等

        2. **地点的稳定性**：
           - **固定常用地点**（如：上班公司、常去的健身房、家、固定的咖啡店）：不建议设计记错地点，因为这类地点不会混淆
           - **一次性/不常去的地点**（如：出差城市、旅游景点、参加活动的场所、探访的朋友家）：可以设计记错地点

        3. **人物的可混淆性**：
           - **重要人物/唯一参与者**（如：手术中的主刀医生、独自完成的事件）：可以设计记错人物
           - **普通社交场合**（如：和很多人一起参加的活动）：可以设计记错具体和谁一起

        4. **选择记错内容的判断标准**：
           - 如果事件是**重要的、罕见的、有明确日期的**，优先考虑记错日期
           - 如果事件是**日常重复的**，优先考虑记错具体内容/参与人物/感受细节
           - 如果地点是**不熟悉的**，可以记错地点
           - 避免选择那些"不太可能记错"的内容（稳定的工作地点、每天都见的家人等）
        
        **冲突类型详解（指导错误信息的设计）**
        
        根据上述冲突类型，设计相应的错误信息来源：
        
        1. **记忆错误**：用户记错了事件的某个关键细节（时间/地点/人物/内容）
           - 错误信息来源：发消息时说错了、口头表达错误、笔记记录错误
           - 示例：实际是4月15日，但发短信说"我记得是5月15日"；或者说去A地，但实际去B地
        
        2. **计划突变**：用户临时改变了计划但没有更新所有相关记录
           - 错误信息来源：早期的计划信息、已发送但未更新的通知
           - 示例：一开始约定5月10日，后来因为事情改变到4月15日，但之前发的信息还是5月10日
           - 关键：要体现计划的变更过程，从原计划 → 突发情况 → 新计划（即原事件）
        
        3. **信息传递错误**：在不同渠道（短信、邮件、对话）中传达了不一致的信息
           - 错误信息来源：发给不同人的信息不一致、不同渠道的信息矛盾
           - 示例：给朋友A发"4月15日参加"，给朋友B发"5月15日参加"；或者短信说一个时间，agent_chat说另一个时间
           - 关键：要生成多个类型的信息（sms + agent_chat），或发给不同人的有错误的信息
        
        4. **多方协调不一致**：多个参与方对同一事件的理解或安排有差异
           - 错误信息来源：不同参与方的确认信息、协调过程中的误解
           - 示例：朋友说"我们约好4月15日"，但自己回复"我以为是你生日那天（5月15日）"
           - 关键：体现多方沟通中的误解和最终统一
        
        5. **遗忘与混淆**：用户忘记了某些细节，与其他类似事件混淆
           - 错误信息来源：基于记忆的模糊信息、与类似事件的混淆
           - 示例：把这次聚会和上次的搞混了，说成上次的时间；或者忘记具体日期，说了个大概
           - 关键：体现记忆的模糊性和混淆过程
        
        6. **意图与行动不符**：用户原本打算做某事，但实际做了另一件事
           - 错误信息来源：表达意图的信息 vs 实际行动的记录
           - 示例：说"我打算5月去"，但实际4月就去了；或者说"我要去A地"，但实际去了B地
           - 关键：体现意图声明和实际行动的差异
                
        7. **记忆冲突（回忆冲突）**：在后续回忆该事件时给出了错误的信息
           - 错误信息来源：事后回忆、聊天回顾、笔记记录时的错误记忆
           - 示例：事件发生在4月15日，但在5月份回忆时说"我记得是4月20日"；或者在6月份和朋友聊天时说错地点
           - 关键：**错误情节必须发生在原事件之后**，体现记忆的偏差或遗忘
           - 特点：不需要纠正情节，因为这是纯粹的回忆错误，原事件已经正常发生
        
        **核心设计原则**
        
        ⚠️ **关键要求：保证原事件的合理性**
        - **绝对不能改变原事件的发生**：原事件必须按照原定时间、地点、内容正常发生
        - **对于前6种冲突类型**：冲突必须是可纠正的，设计的错误/矛盾信息必须在原事件发生前被纠正
        - **对于第7种（记忆冲突）**：错误发生在原事件之后，不需要纠正情节，因为原事件已经正常发生
        - **完整的冲突-纠正链条（仅适用于前6种类型）**：错误信息产生 → 发现并纠正 → 原事件合理发生
        
        **任务要求**
                
        1. **设计冲突情节（根据冲突类型选择不同策略）**
                
           ### 对于前6种冲突类型（错误发生在原事件之前）
                   
           **第一步：引入错误/矛盾信息（可以有多条）**
           - 在原事件之前，生成**1-3条**与最终事实不符的信息
           - **多条错误情节可以互相印证**，形成一个看似合理但实际错误的链条
           - 例如：
             * 先发信息说"计划5月15日去北京"
             * 过几天又说"我订了5月15日的机票"（印证前面的说法）
             * 再过几天说"酒店也订好了，5月15-17日"（继续印证）
             * （这些都是错误的，实际是4月15日）
           - **互相印证的示例**：
             * 第一条："我查了下日历，你生日好像是5月15日"
             * 第二条："我刚跟朋友确认了，他说也是5月15日"（用第三方印证）
             * 第三条："我订了5月15日的餐厅，到时候见"（用行动印证）
           - 多条互相印证的错误信息会让冲突更真实、更有说服力
           - 这些错误信息要符合冲突类型的特征
                           
           **第二步：纠正错误信息（只生成一条）**
           - 在原事件发生前，必须有**且仅有一条**明确的情节显示所有错误被纠正
           - **纠正方式要自然含蓄**：不要直接说出正确答案，而是表达"我之前的信息有误"、"我需要重新确认/安排"
           - **关键要求**：纠正信息只声明自己纠正了，但**不需要告诉具体正确内容**
           - 例如：
             * "不好意思，我之前说的时间可能不对，我需要重新确认一下"（不说正确时间）
             * "我发现之前搞错了，让我重新安排一下时间"（不说新时间）
             * "等等，我刚才发现有些问题，我们重新商量一下"（不说具体问题）
             * "我之前说的都不算数了，有变动，稍后告诉你准确信息"（不说准确信息）
             * "之前的计划有变，我重新安排了"（不说新计划）
           - **禁止**：纠正信息中直接说出正确答案（如"应该是4月15日"）
           - 纠正情节要让原事件的发生变得合理、不突兀
           - **关键**：纠正信息应该体现"意识到错误 → 重新确认/安排"的过程，但**不透露最终结果**
                           
           **第三步：原事件正常发生**
           - 原事件按照最初的事实正常进行
           - 因为有纠正情节，所以原事件的发生是合理的
                
           ### 对于第7种冲突类型（记忆冲突/回忆冲突）
                   
           **只需一步：在原事件之后生成回忆错误的信息**
           - 错误情节必须发生在**原事件日期之后**
           - 生成**1-2条**回忆时的错误信息
           - 例如：
             * 原事件是4月15日参加聚会
             * 5月10日：发短信给朋友说"我记得上次聚会是4月20日吧？"（实际是4月15日）
             * 或者在6月份记录笔记时写错日期
           - **不需要纠正情节**，因为这是纯粹的回忆错误
           - 错误信息要体现记忆的偏差、遗忘或混淆
        
        2. **确定新增情节的日期**
           - **对于前6种冲突类型**：
             * **错误信息情节**：应该在原事件日期之前的较早时间
             * **纠正情节**：应该在错误信息之后、原事件之前
             * 所有新增情节都应该在原事件日期前后合理的时间范围内
           - **对于第7种冲突类型（记忆冲突）**：
             * **回忆错误情节**：必须在**原事件日期之后**，可以是几天后、几周后甚至几个月后
             * 例如：原事件是4月15日，回忆错误可以发生在5月、6月或更晚
        
        3. **定义需要生成的手机数据类型**
           - 可以生成 sms、agent_chat、calendar、note 类型的数据
           - **sms（短信）**：适合和别人传递消息的场景
             * 例如：给朋友发信息说错时间、收到朋友的纠正信息、和朋友确认日程等
             * 特点：双向沟通，可以体现信息传递错误或协调不一致
           - **agent_chat（AI智能体对话）**：适合询问AI智能体的场景，可向AI智能体透露信息
             * 例如：问AI"我5月15日有什么安排？"（实际是4月15日）、让AI提醒错误的时间等
             * 特点：用户向AI透露错误信息，AI基于错误信息给出回应，后续可纠正
           - **calendar（日历）**：适合记录错误的时间安排，后续可以被纠正或更新
             * 例如：在日历中错误地标记了5月15日的活动，后来被告知后修改为4月15日
           - **note（笔记）**：适合记录从别人那得到的错误信息，或者自己记错的内容
             * 例如：记下"朋友生日是5月15日"，后来发现记错了
             * 例如：记录会议时间，但信息来源有误，后续收到纠正通知
           - 至少需要2条数据：一条错误信息 + 一条纠正信息
           - **content_hint 必须明确包含要生成的数据的具体内容**，不能只是模糊的提示
             * ✅ 正确示例："发送短信给张三，内容为'我可能5月15日才能参加你的生日聚会了，4月有事'"
             * ✅ 正确示例："在日历中创建日程，标题为'参加李四生日聚会'，时间为5月15日 19:00-21:00"
             * ✅ 正确示例："记录笔记，标题为'朋友生日'，内容为'张三生日：5月15日'"
             * ❌ 错误示例："发送一条关于时间的短信"（太模糊）
             * ❌ 错误示例："创建一个日程"（没有具体内容）
        
        **示例场景**
        
        假设原事件是"4月15日参加朋友的生日聚会"
        
        ✅ **正确设计（前6种类型，包含纠正）**：
        - 4月5日：发短信给朋友"我可能5月15日才能参加你的生日聚会了，4月有事"
        - 4月10日：再发短信"不好意思，我重新安排了时间，4月15日可以参加了！之前说的5月不对"
        - 4月15日：原事件正常发生（参加生日聚会）
        
        ❌ **错误设计（前6种类型，缺少纠正）**：
        - 4月5日：发短信说"我5月15日参加你的生日聚会"
        - 4月15日：原事件发生（参加生日聚会）
        - 问题：没有纠正情节，4月15日的发生显得突兀
        
        ✅ **正确设计（第7种类型，记忆冲突）**：
        - 4月15日：原事件正常发生（参加生日聚会）
        - 5月20日：发短信给朋友说"我记得上次聚会是4月20日吧？"（实际是4月15日）
        - 或者在6月份记录笔记时写错日期："4月20日参加了张三的生日聚会"
        - 特点：错误发生在事后，不需要纠正，体现记忆的偏差
        
        **输出要求**
        请以 JSON 格式返回：
        {{
            "conflict_scenario": "详细的冲突场景描述，包括错误信息的产生和纠正过程",
            "correct_information": "正确的信息是什么（即原事件的实际内容）",
            "incorrect_information": "错误的/过时的信息是什么",
            "correction_process": "错误是如何被纠正的，详细说明纠正的过程和时机",
            "new_plots": [
                {{
                    "date": "新增情节的日期（YYYY-MM-DD）",
                    "description": "新增情节的描述",
                    "data_type": "sms 或 agent_chat 或 note 或 calendar",
                    "content_hint": "数据内容的提示",
                    "plot_role": "错误信息 / 纠正信息 / 其他"
                }}
            ],
            "reasoning": "为什么这样设计冲突是合理的，以及如何保证原事件的发生不突兀"
        }}
        
        **注意事项**
        - **对于前6种冲突类型**：new_plots 中必须至少包含2个情节：一个引入错误，一个纠正错误
        - **对于第7种冲突类型（记忆冲突）**：new_plots 中包含1-2个回忆错误的情节即可，不需要纠正
        - **纠正情节必须在原事件日期之前**（仅适用于前6种类型）
        - **回忆错误情节必须在原事件日期之后**（仅适用于第7种类型）
        - 确保整个冲突链条逻辑清晰、符合真实生活场景
        """
        
        try:
            print(f"\n[Generate Conflict Plot] LLM 输入:", prompt)
            llm_result = llm_call_j(prompt)
            print(f"[Generate Conflict Plot] LLM 输出:", llm_result)
            
            if isinstance(llm_result, str):
                start_idx = llm_result.find('{')
                end_idx = llm_result.rfind('}') + 1
                if start_idx != -1 and end_idx != -1:
                    return json.loads(llm_result[start_idx:end_idx])
            elif isinstance(llm_result, dict):
                return llm_result
            
            return None
        except Exception as e:
            print(f"[Generate Conflict Plot] 生成失败：{e}")
            return None
    
    def _generate_phone_data_for_plot(self, conflict_plot: Dict, target_event: Dict) -> List[Dict]:
        """
        为冲突情节生成对应的手机数据（支持 sms、note、calendar、agent_chat）
        使用 PhoneOperationGenerator 进行实际生成，LLM 只生成规划指令

        Args:
            conflict_plot: 完整的冲突情节数据（包含 new_plots 数组）
            target_event: 目标事件（仅用于获取人物画像）

        Returns:
            生成的手机数据列表
        """
        new_plots = conflict_plot.get('new_plots', [])

        if not new_plots:
            print(f"[Generate Phone Data] 警告：new_plots 为空")
            return []

        all_operations = []

        # 遍历每个情节，生成对应的手机数据
        for i, plot in enumerate(new_plots, 1):
            print(f"[Generate Phone Data] 处理第 {i}/{len(new_plots)} 个情节...")

            data_type = plot.get('data_type', 'sms')
            plot_date = plot.get('date', '')
            content_hint = plot.get('content_hint', '')
            plot_role = plot.get('plot_role', '')

            # 支持多种类型：sms, note, calendar, agent_chat, phonecall, photo, push
            supported_types = ['sms', 'note', 'calendar', 'agent_chat', 'phonecall', 'photo', 'push']
            if data_type not in supported_types:
                print(f"[Generate Phone Data] 不支持的数据类型：{data_type}，跳过")
                continue

            try:
                # 构建原始事件信息
                target_event = plot.get('target_event', {})
                original_event = {
                    'name': plot.get('description', ''),
                    'type': data_type,
                    'date': plot_date,
                    'description': content_hint,
                    'event_id': target_event.get('event_id', '')  # 添加 event_id 供 PhoneOperationGenerator 设置 daily_event_id
                }

                # LLM 只生成操作类型和生成要求
                plan_prompt = f"""你是一位手机数据生成规划专家。请为以下冲突情节规划手机操作数据的生成方案。

【冲突情节】
- 情节描述: {plot.get('description', '')}
- 情节角色: {plot_role}
- 内容提示: {content_hint}
- 日期: {plot_date}

【支持的类型（必须使用以下类型之一）】
- **sms（短信）**：用户与他人的文字消息交流，包含消息内容、联系人、时间戳
  * 生成要点：联系人姓名、消息具体内容（如时间、地点、确认或询问的信息）、发送/接收时间
- **note（笔记）**：用户的文字记录，包含标题、内容、创建时间
  * 生成要点：笔记标题、内容摘要（可包含错误信息或待确认事项）、创建时间
- **calendar（日历）**：日程安排记录，包含标题、时间、地点、描述
  * 生成要点：日程标题、开始/结束时间、地点（如适用）、描述内容
- **photo（照片）**：拍摄的照片，包含标题、拍摄时间、地点、人物识别
  * 生成要点：照片标题（如IMG_年月日_时分秒格式）、拍摄时间、地点信息、人物（如有）、内容描述
- **push（推送通知）**：手机应用推送的通知，包含标题、内容、来源、时间
  * 生成要点：推送来源应用、通知标题、内容摘要、推送时间
- **agent_chat（智能体对话）**：用户与AI智能体的对话记录，包含对话轮次、用户动作、AI回复内容
  * 生成要点：用户的问题/陈述内容、对话轮次、用户action类型（如topic query、need confirmation等）

【任务要求】
请为这个冲突情节生成手机操作规划。

【规划要求】
1. 选择合适的手机数据类型（当前情节指定了 {data_type}）
2. 说明具体的生成要求（内容、要点等），包含足够的细节供实际数据生成
3. generation_hint 必须包含：联系人/人物、时间信息、具体内容描述
4. 生成要求应能精确反映冲突情节的核心内容

【输出格式】
请以 JSON 数组格式返回：
[
    {{
        "operation_type": "sms/note/calendar/photo/push/agent_chat 之一",
        "generation_hint": "具体的生成要求，必须包含：联系人/人物、时间（如具体钟点或时间段）、具体内容描述"
    }}
]
"""

                # 调用 LLM 生成规划
                plan_result = llm_call_j(plan_prompt)

                plan_list = []
                if isinstance(plan_result, str):
                    start_idx = plan_result.find('[')
                    end_idx = plan_result.rfind(']') + 1
                    if start_idx != -1 and end_idx != -1:
                        plan_list = json.loads(plan_result[start_idx:end_idx])
                elif isinstance(plan_result, list):
                    plan_list = plan_result

                if not plan_list:
                    print(f"[Generate Phone Data] LLM 生成规划为空，跳过")
                    continue

                # 使用 PhoneOperationGenerator 生成实际的手机数据
                for plan in plan_list:
                    operation_type = plan.get("operation_type", data_type)
                    generation_hint = plan.get("generation_hint", content_hint)

                    # 构建 question
                    question = f"冲突情节: {plot_role} - {content_hint}"

                    # 调用 PhoneOperationGenerator 生成
                    generated = self.phone_op_generator.generate(
                        operation_type=operation_type,
                        original_event=original_event,
                        question=question,
                        generation_hint=generation_hint
                    )

                    if generated:
                        all_operations.extend(generated)
                        print(f"[Generate Phone Data] 成功生成 {len(generated)} 条 {operation_type} 数据")
                    else:
                        print(f"[Generate Phone Data] {operation_type} 类型生成失败")

            except Exception as e:
                print(f"[Generate Phone Data] 生成失败：{e}")
                import traceback
                traceback.print_exc()
                continue

        print(f"[Generate Phone Data] 总共生成 {len(all_operations)} 条手机数据")
        return all_operations
    
    def QAGen(self, year: int = 2025, num_samples: int = 60) -> List[Dict[str, Any]]:
        """
        生成冲突 QA 对的主入口函数
        
        Args:
            year: 年份，默认 2025
            num_samples: 采样事件数量，默认 20
            
        Returns:
            生成的 QA 对列表
        """
        print(f"\n========== 开始生成 {year} 年的冲突问答对 ==========")
        
        # Step 1: 遍历每个月，生成主要事件总结
        print("\n[Step 1] 生成各月份的主要事件总结...")
        monthly_summaries = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(self._generate_monthly_summary, year, month) 
                      for month in range(1, 13)]
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    summary = future.result()
                    if summary:
                        monthly_summaries.append(summary)
                except Exception as e:
                    print(f"[Monthly Summary] 生成失败：{e}")
        
        print(f"[Step 1] 完成，共生成 {len(monthly_summaries)} 个月的总结")
        
        # Step 2: 采样 20 个事件
        print("\n[Step 2] 采样事件用于生成冲突情节...")
        sampled_events = self._sample_conflict_events(monthly_summaries, num_samples)
        
        if not sampled_events:
            print("[Step 2] 没有采样到事件")
            return []
        
        # Step 2.5: 基于日期定位到对应的 daily_event，获取完整的 event_id
        print("\n[Step 2.5] 基于日期定位 daily_event，获取完整的事件信息...")
        located_daily_events = self._locate_daily_events(sampled_events, date_offset=1)
        
        if not located_daily_events:
            print("[Step 2.5] 警告：未找到任何匹配的 daily_event，使用原始采样事件")
            # 如果没找到，保留原始事件但标记警告
            for event in sampled_events:
                event['event_id'] = event.get('event_id', '')
                event['daily_event_data'] = None
        else:
            # 用找到的 daily_event 替换或增强 sampled_events
            print(f"[Step 2.5] 成功定位到 {len(located_daily_events)} 个 daily_event")
            # 将 located_daily_events 包装为带有 daily_event_data 字段的事件
            enriched_sampled_events = []
            for daily_event in located_daily_events:
                # 创建新的事件对象，将 daily_event 作为 daily_event_data
                enriched_event = {
                    'daily_event_data': daily_event,
                    'event_id': daily_event.get('event_id', '') or daily_event.get('atomic_id', ''),
                    # 保留其他可能需要的字段
                    'date': daily_event.get('date', ''),
                    'event_description': daily_event.get('event_description', '') or daily_event.get('description', ''),
                }
                enriched_sampled_events.append(enriched_event)
            
            sampled_events = enriched_sampled_events
        
        # Step 3: 为每个采样事件生成冲突情节（20线程并行）
        print("\n[Step 3] 生成冲突情节（20线程并行）...")
        
        conflict_plots = [None] * len(sampled_events)  # 预分配列表保持顺序
        
        def generate_single_plot(idx: int, event: Dict[str, Any]) -> tuple:
            """处理单个事件的冲突情节生成"""
            try:
                print(f"\n--- 处理第 {idx + 1}/{len(sampled_events)} 个事件 ---")
                plot = self._generate_conflict_plot(event)
                if plot:
                    plot['target_event'] = event
                    return idx, plot
                else:
                    print(f"[Step 3] 第 {idx + 1} 个事件生成冲突情节失败")
                    return idx, None
            except Exception as e:
                print(f"[Step 3] 第 {idx + 1} 个事件生成冲突情节异常：{e}")
                return idx, None
        
        # 使用 ThreadPoolExecutor 并行处理，最多20线程
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [
                executor.submit(generate_single_plot, idx, event)
                for idx, event in enumerate(sampled_events)
            ]
            
            # 收集结果
            completed_count = 0
            for future in concurrent.futures.as_completed(futures):
                try:
                    idx, plot = future.result()
                    conflict_plots[idx] = plot
                    completed_count += 1
                    if completed_count % 5 == 0 or completed_count == len(sampled_events):
                        print(f"\n[Step 3] 已完成 {completed_count}/{len(sampled_events)} 个事件的冲突情节生成")
                except Exception as e:
                    print(f"[Step 3] 结果收集失败：{e}")
        
        # 过滤掉 None 值
        conflict_plots = [plot for plot in conflict_plots if plot is not None]
        
        print(f"[Step 3] 完成，共生成 {len(conflict_plots)} 个冲突情节")
        print("情节具体内容：", conflict_plots)
        # Step 5: 基于情节生成手机数据、问题并补充证据
        print("\n[Step 5] 基于情节生成手机数据、问题并补充证据...")
        qa_pairs = []
        
        for i, plot in enumerate(conflict_plots, 1):
            print(f"\n--- 处理第 {i}/{len(conflict_plots)} 个冲突情节 ---")
            
            target_event = plot['target_event']
            new_plots = plot.get('new_plots', [])
            
            # 只使用 daily_event_data
            daily_event_data = target_event.get('daily_event_data')
            if not daily_event_data or not isinstance(daily_event_data, dict):
                print(f"[Step 5] 跳过：事件缺少 daily_event_data")
                continue
            
            event_id = daily_event_data.get('event_id', '') or daily_event_data.get('atomic_id', '')
            event_description = daily_event_data.get('event_description', '') or daily_event_data.get('description', '')
            
            # === 子步骤 5.1: 基于情节生成对应的手机数据 ===
            print(f"[Step 5.1] 基于情节生成手机数据...")
            
            # 将整个冲突情节对象传入，函数内部会遍历 new_plots
            plot_evidence = self._generate_phone_data_for_plot(plot, target_event)
            
            # 添加到 phonedata
            if plot_evidence:
                self._add_operations_to_phonedata(plot_evidence)
            
            print(f"[Step 5.1] 为情节生成了 {len(plot_evidence)} 条手机数据")
            
            # === 子步骤 5.2: 基于原事件和情节生成问题 ===
            print(f"[Step 5.2] 基于原事件和情节生成问题...")

            correct_information = plot.get('correct_information', '')
            correct_information = plot.get('correct_information', '')


            question_prompt = f"""
            作为问答设计师，请根据以下信息设计一个会被干扰项误导的问题。

            **核心思路**
            1. 先分析：错误信息会干扰对原事件的哪个具体方面的记忆（时间/地点/人物/内容）
            2. 再设计：基于原始事件（正确信息）设计问题，即题面不知道冲突信息，只是描述对原始事件内容的询问。
            3. 问题本身不能提及或暗示任何错误信息或冲突

            **重要**：请使用 {self.persona_name} 而不是"我/自己/你"来指代用户。

            【原始事件（正确信息）】
            {json.dumps(daily_event_data, ensure_ascii=False, indent=2)}

            【完整冲突情节信息】
            # conflict_scenario: 冲突场景的详细描述，说明如何产生矛盾
            # correct_information: 正确信息，原始事件的真实情况
            # incorrect_information: 错误/干扰信息，与正确信息不符的内容
            {json.dumps({
                'conflict_scenario': plot.get('conflict_scenario', ''),
                'correct_information': plot.get('correct_information', ''),
                'incorrect_information': plot.get('incorrect_information', ''),
            }, ensure_ascii=False, indent=2)}

            **任务要求**
            1. **分析干扰项如何误导**：
               - 对比原始事件和错误信息，找出矛盾点
               - 确定用户记错的是哪个具体方面：时间、地点、人物还是内容
               - 例如：如果错误信息说"10月15日"，但原事件是"10月10日"，则时间被干扰

            2. **针对被干扰的方面设计问题**：
               - 如果被干扰的是**时间**：问"具体是哪天？""那天是几号来着？"
               - 如果被干扰的是**地点**：问"是在哪里来着？""具体地点是？"
               - 如果被干扰的是**人物**：问"当时有谁在一起？""和谁一起？"
               - 如果被干扰的是**内容**：问"当时做了什么来着？""具体是什么事？"

            3. **问题必须满足**：
               - 只基于原事件（正确信息）设计问题
               - 不提及任何错误信息、冲突情节或矛盾
               - 看起来像普通的生活记忆查询
               - 在问题中融入月份信息（如"{self.persona_name}在12月份..."）

            4. **问题示例**：
               - 干扰项说10月15日，原事件是10月10日：
                 - ✅ "10月上旬我被医生告知的成绩评估日期具体是在哪天？","10月10日"
               - 干扰项说是玩偶，原事件是准备的手表：
                 - ✅ "8月我给小明准备的礼物具体是什么？","手表"

            注意问题和答案要基于正确信息提问。

            **输出要求**
            请以 JSON 格式返回：
            {{
                "inferred_aspect": "根据错误信息推断出需要针对原事件提问的方面（如：时间、地点、人物、内容等）",
                "correct_answer": "基于原始事件的正确信息，推断出的方面对应的答案",
                "question": "生成的问题文本（基于原事件信息，针对推断出的方面设计，只针对原事件信息提问）",
                "answer": "简洁准确的答案（与question对应）"
            }}
            """
            
            try:
                print(f"[Generate Question] LLM 输入:", question_prompt)
                llm_result = llm_call_j(question_prompt)
                print(f"[Generate Question] LLM 输出:", llm_result)
                if isinstance(llm_result, str):
                    start_idx = llm_result.find('{')
                    end_idx = llm_result.rfind('}') + 1
                    if start_idx != -1 and end_idx != -1:
                        llm_result = json.loads(llm_result[start_idx:end_idx])
                
                if isinstance(llm_result, dict):
                    question_text = llm_result.get('question', '')
                    answer_text = llm_result.get('answer', '')
                else:
                    question_text = f"关于'{event_description}'的具体情况是什么？"
                    answer_text = correct_information or event_description
                    
            except Exception as e:
                print(f"[Generate Question] 生成失败：{e}，使用默认问题")
                question_text = f"关于'{event_description}'的具体情况是什么？"
                answer_text = correct_information or event_description
            
            print(f"[Step 5.2] 问题生成成功: {question_text[:50]}...")
            
            # 构建标准格式的 QA 对
            qa_pair = {
                'question': question_text,
                'answer': answer_text,
                'score_points': [
                    {
                        'description': f"准确回答问题",
                        'score': 10
                    }
                ],
                'required_events_id': [str(event_id)] if event_id else [],
                'evidence': list(plot_evidence)  # 先加入情节生成的证据
            }
            
            # === 子步骤 5.3: 分析原事件的手机数据是否充足，不充足则补充 ===
            print(f"[Step 5.3] 分析原事件的手机数据是否充足...")
            
            # 收集原事件的所有手机数据
            existing_evidence = []
            if self.phonedata:
                with self.phonedata_lock:
                    for data_type, data_list in self.phonedata.items():
                        if isinstance(data_list, list):
                            for item in data_list:
                                if isinstance(item, dict):
                                    item_event_id = str(item.get('daily_event_id', ''))
                                    related_event = str(item.get('related_event', ''))
                                    
                                    if item_event_id == str(event_id) or related_event == str(event_id):
                                        existing_evidence.append(item)
            
            print(f"[Step 5.3] 找到 {len(existing_evidence)} 条原事件的手机数据")
            
            # 将现有证据也加入 evidence 列表
            qa_pair['evidence'].extend(existing_evidence)
            
            # 分析证据是否充足
            all_evidence = qa_pair['evidence']
            analysis_prompt = f"""
            作为证据分析师，请分析以下问题和现有证据。

            【原事件数据】
            {json.dumps(daily_event_data, ensure_ascii=False, indent=2)}

            【问题】
            {question_text}

            【答案】
            {answer_text}

            【现有证据】（共{len(all_evidence)}条）
            {json.dumps([{'type': item.get('type', 'unknown'), 'summary': str(item)[:200]} for item in all_evidence[:10]], ensure_ascii=False, indent=2)}

            **任务要求**
            1. 分析现有证据是否足以回答问题
            2. 如果不足，说明缺少什么关键信息
            3. 如果需要生成新证据，说明需要生成什么类型的数据和内容
            4. 生成的证据要基于原事件来生成，生成的证据具有真实性，即不只包含简洁明确的面对答案的内容，内容可能同时含有复杂多样的信息，噪声等。使其符合真实手机数据的复杂性。
            5. 当你需要表达多个信息并生成多个手机操作数据时，尽量生成不同类型的手机操作，同时每个手机操作表达不同的信息而非重复的信息，操作间信息互补，体现真实数据的信息碎片化特性。多个手机操作只有有一两个左右反映答案信息即可，其他手机数据可以描述相关事件帮助定位作证到具体的时间，内容但不包含答案。
            
            **重要约束**
            - **只允许生成以下类型的证据**：sms、phonecall、photo、push、note、calendar
            - **严禁生成其他类型**（如 agent_chat 等）
            - 根据缺少的信息选择最合适的数据类型

            **输出要求**
            请以 JSON 格式返回：
            {{
                "sufficient": true/false,
                "missing_info": "缺少的关键信息描述",
                "to_generate": [
                    {{
                        "type": "sms/phonecall/photo/push/note/calendar（必须是这六种之一）",
                        "content_hint": "需要生成的数据内容提示"
                    }}
                ]
            }}
            """
            
            try:
                llm_result = llm_call_j(analysis_prompt)
                
                if isinstance(llm_result, str):
                    start_idx = llm_result.find('{')
                    end_idx = llm_result.rfind('}') + 1
                    if start_idx != -1 and end_idx != -1:
                        llm_result = json.loads(llm_result[start_idx:end_idx])
                
                if isinstance(llm_result, dict):
                    is_sufficient = llm_result.get('sufficient', False)
                    to_generate = llm_result.get('to_generate', [])
                    
                    if not is_sufficient and to_generate:
                        print(f"[Step 5.3] 证据不足，需要生成 {len(to_generate)} 条新数据")
                        
                        # 生成缺失的证据
                        for gen_item in to_generate:
                            op_type = gen_item.get('type', 'sms')
                            content_hint = gen_item.get('content_hint', '')
                            
                            # 使用 PhoneOperationGenerator 生成
                            operations = self.phone_op_generator.generate(
                                operation_type=op_type,
                                original_event=target_event,
                                question=question_text,
                                generation_hint=f"为回答问题生成{op_type}数据。内容要求：{content_hint}"
                            )
                            
                            if operations:
                                qa_pair['evidence'].extend(operations)
                                # 添加到 phonedata
                                self._add_operations_to_phonedata(operations)
                                print(f"[Step 5.3] 生成了 {len(operations)} 条 {op_type} 数据")
                    else:
                        print(f"[Step 5.3] 现有证据充足")
                else:
                    print(f"[Step 5.3] LLM 返回格式错误，使用现有证据")
                    
            except Exception as e:
                print(f"[Step 5.3] 分析失败：{e}，使用现有证据")
            
            qa_pairs.append(qa_pair)
            print(f"[Step 5] 完成，最终证据数量：{len(qa_pair['evidence'])}")
        
        print(f"\n[Step 5] 完成，共生成 {len(qa_pairs)} 个冲突问答对")
        
        # 为每个问题添加 question_type 字段
        print("\n[Step 6] 为所有问题设置 question_type 为 'Conflict'...")
        for qa in qa_pairs:
            qa['question_type'] = 'Conflict'
            qa['ask_time'] = self.default_ask_time
        print(f"✓ 已为 {len(qa_pairs)} 个问题设置 question_type")

        # Step 7: 过滤不可回答的问题（20线程并行）
        print("\n[Step 7] 过滤不可回答的问题，不通过的需要重新设计...")

        def validate_single_qa(idx: int, qa: Dict) -> tuple:
            """验证单个 QA 对"""
            try:
                filter_prompt = f"""
作为问答质量审核员，请验证以下问题是否可以通过现有证据回答，并检查其冲突性。

【问题】
{qa.get('question', '')}

【答案】
{qa.get('answer', '')}

【证据列表】（共 {len(qa.get('evidence', []))} 条）
{json.dumps([{'type': e.get('type', 'unknown'), 'summary': str(e)[:300]} for e in qa.get('evidence', [])], ensure_ascii=False, indent=2)}

**审查维度**

1. **可回答性检查**
   - 问题是否能从现有证据推理出答案？
   - 证据中是否包含回答问题所需的完整信息（时间、地点、人物、内容等）？
   - 如果证据不足以回答问题，标记为"不可回答"

2. **冲突性检查**
   - 证据中是否存在冲突/矛盾的信息（如不同来源提到不同时间/日期）？
   - 问题是否需要分析多个冲突证据才能得出正确答案？
   - 如果证据过于简单直接（无冲突），则缺乏区分度

**分类标准**

根据审查结果，将问题分为三类：

1. **pass（通过）**：题面有难度，需要综合分析矛盾证据和正确证据
   - 证据中存在冲突信息
   - 问题需要多步推理或对比分析才能得出正确答案
   - 题面描述清晰但不直接指向答案

2. **revise（微调）**：题面或答案需要小幅修改
   - 题面过于简单/直接，矛盾证据没有体现出来。
   - 答案不够精确，但可以微调
   - 适用于：问题框架合理，只需小幅修改即可

3. **discard（抛弃）**：质量不合格，需完全重新设计
   - 问题完全不可回答（证据缺失关键信息）
   - 证据完全没有冲突（过于简单，缺乏Conflict特点）
   - 题面与证据严重不匹配
   - 答案本身错误或不合理

**输出要求**
请以 JSON 格式返回：
{{
    "category": "pass/revise/discard",
    "reason": "判断原因详细说明",
    "revised_question": "如果 category=revise，给出微调后的问题",
    "revised_answer": "如果 category=revise，给出微调后的答案",
    "revised_score_points": "如果 category=revise，给出重新设计的评分点，格式为 [{{"description": "...", "score": N}}]"
}}
"""
                llm_result = llm_call_j(filter_prompt)

                if isinstance(llm_result, str):
                    start_idx = llm_result.find('{')
                    end_idx = llm_result.rfind('}') + 1
                    if start_idx != -1 and end_idx != -1:
                        llm_result = json.loads(llm_result[start_idx:end_idx])

                if isinstance(llm_result, dict):
                    category = llm_result.get('category', 'pass')
                    reason = llm_result.get('reason', '')

                    if category == 'pass':
                        print(f"[Step 7] ✓ 第 {idx + 1} 个问题通过验证（pass）")
                        return idx, qa, True, reason, None, None, None
                    elif category == 'revise':
                        print(f"[Step 7] ~ 第 {idx + 1} 个问题需要微调（revise）：{reason}")
                        revised_question = llm_result.get('revised_question', '')
                        revised_answer = llm_result.get('revised_answer', '')
                        revised_score_points = llm_result.get('revised_score_points', [])
                        return idx, qa, False, reason, revised_question, revised_answer, revised_score_points
                    else:  # discard
                        print(f"[Step 7] ✗ 第 {idx + 1} 个问题被抛弃（discard）：{reason}")
                        return idx, qa, False, reason, None, None, None
                else:
                    print(f"[Step 7] LLM 返回格式错误")
                    return idx, qa, True, "LLM 返回格式错误", None, None, None

            except Exception as e:
                print(f"[Step 7] 验证失败：{e}")
                return idx, qa, True, str(e), None, None, None

        # 20线程并行验证
        filtered_results = [None] * len(qa_pairs)
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [
                executor.submit(validate_single_qa, idx, qa)
                for idx, qa in enumerate(qa_pairs)
            ]

            for future in concurrent.futures.as_completed(futures):
                try:
                    idx, qa, is_pass, reason, revised_question, revised_answer, revised_score_points = future.result()
                    if is_pass:
                        # pass: 直接保留
                        filtered_results[idx] = qa
                    else:
                        # revise: 使用修订后的值
                        if revised_question and revised_answer:
                            qa['question'] = revised_question
                            qa['answer'] = revised_answer
                            if revised_score_points:
                                qa['score_points'] = revised_score_points
                            filtered_results[idx] = qa
                        else:
                            # discard: 抛弃（filtered_results[idx] 保持 None）
                            print(f"[Step 7] 抛弃问题 {idx + 1}")
                except Exception as e:
                    print(f"[Step 7] 结果收集失败：{e}")

        # 过滤掉 None 值
        filtered_qa_pairs = [r for r in filtered_results if r is not None]
        print(f"\n[Step 7] 完成，通过验证的问题数量：{len(filtered_qa_pairs)}/{len(qa_pairs)}")

        # 保存到文件 - 已移除，统一由调用方处理
        # if self.phone_data_dir:
        #     parent_dir = os.path.dirname(self.phone_data_dir)
        #     output_path = os.path.join(parent_dir, "conflict_qa.json")
        #
        #     with open(output_path, "w", encoding="utf-8") as f:
        #         json.dump(filtered_qa_pairs, f, ensure_ascii=False, indent=2)
        #
        #     print(f"\n问答对已成功写入文件：{output_path}")

        print(f"\n========== 完成，共生成 {len(qa_pairs)} 个冲突问答对 ==========")
        return qa_pairs
    
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
        
        print(f"[Add Operations] 已将 {len(operations)} 条操作数据添加到 phonedata")
