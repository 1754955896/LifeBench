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
                 is_print: bool = True):
        """
        初始化冲突问题生成器
        
        Args:
            daily_event: daily_event 数据列表
            draft_event: draft_event 数据字典（按月份组织）
            phonedata: 手机操作数据字典
            phone_data_dir: 手机数据目录路径
            is_print: 是否打印调试信息
        """
        super().__init__()
        self.daily_event = daily_event
        self.draft_event = draft_event
        self.phonedata = phonedata
        self.phone_data_dir = phone_data_dir
        self.is_print = is_print
        
        # 线程锁
        self.phonedata_lock = threading.Lock()
        self.phone_id_counters = {}
        
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
        作为月度事件总结专家，请分析以下 {month_key} 的生活记录数据，输出用户本月主要做了什么。
        
        【月份数据】
        {json.dumps(month_events, ensure_ascii=False, indent=2)}
        
        **核心要求**
        - **叙述性总结**：以"用户这个月主要做了什么"的角度进行总结
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
                "event_description": "事件描述（简洁突出用户做了什么）",
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
        
        【原始事件】
        {json.dumps(event_info, ensure_ascii=False, indent=2)}
        
        【冲突类型及错误信息来源】
        {conflict_type}
        
        **重要提示：灵活选择冲突类型**
        - 上述冲突类型仅作为参考和启发
        - **如果当前类型难以设计出合理、自然的冲突情节，可以自由选择其他更适合的冲突类型**
        - 优先考虑冲突的合理性、真实性和可设计性，不必严格遵循指定的类型
        - 最终目标是生成一个逻辑清晰、符合生活场景的冲突故事
        
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
           - 示例：说“我打算5月去”，但实际4月就去了；或者说“我要去A地”，但实际去了B地
           - 关键：体现意图声明和实际行动的差异
                
        7. **记忆冲突（回忆冲突）**：在后续回忆该事件时给出了错误的信息
           - 错误信息来源：事后回忆、聊天回顾、笔记记录时的错误记忆
           - 示例：事件发生在4月15日，但在5月份回忆时说“我记得是4月20日”；或者在6月份和朋友聊天时说错地点
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
             * 先发信息说“计划5月15日去北京”
             * 过几天又说“我订了5月15日的机票”（印证前面的说法）
             * 再过几天说“酒店也订好了，5月15-17日”（继续印证）
             * （这些都是错误的，实际是4月15日）
           - **互相印证的示例**：
             * 第一条：“我查了下日历，你生日好像是5月15日”
             * 第二条：“我刚跟朋友确认了，他说也是5月15日”（用第三方印证）
             * 第三条：“我订了5月15日的餐厅，到时候见”（用行动印证）
           - 多条互相印证的错误信息会让冲突更真实、更有说服力
           - 这些错误信息要符合冲突类型的特征
                           
           **第二步：纠正错误信息（只生成一条）**
           - 在原事件发生前，必须有**且仅有一条**明确的情节显示所有错误被纠正
           - **纠正方式要自然含蓄**：不要直接说出正确答案，而是表达“我之前的信息有误”、“我需要重新确认/安排”
           - **关键要求**：纠正信息只声明自己纠正了，但**不需要告诉具体正确内容**
           - 例如：
             * “不好意思，我之前说的时间可能不对，我需要重新确认一下”（不说正确时间）
             * “我发现之前搞错了，让我重新安排一下时间”（不说新时间）
             * “等等，我刚才发现有些问题，我们重新商量一下”（不说具体问题）
             * “我之前说的都不算数了，有变动，稍后告诉你准确信息”（不说准确信息）
             * “之前的计划有变，我重新安排了”（不说新计划）
           - **禁止**：纠正信息中直接说出正确答案（如“应该是4月15日”）
           - 纠正情节要让原事件的发生变得合理、不突兀
           - **关键**：纠正信息应该体现“意识到错误 → 重新确认/安排”的过程，但**不透露最终结果**
                           
           **第三步：原事件正常发生**
           - 原事件按照最初的事实正常进行
           - 因为有纠正情节，所以原事件的发生是合理的
                
           ### 对于第7种冲突类型（记忆冲突/回忆冲突）
                   
           **只需一步：在原事件之后生成回忆错误的信息**
           - 错误情节必须发生在**原事件日期之后**
           - 生成**1-2条**回忆时的错误信息
           - 例如：
             * 原事件是4月15日参加聚会
             * 5月10日：发短信给朋友说“我记得上次聚会是4月20日吧？”（实际是4月15日）
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
             * 例如：问AI“我5月15日有什么安排？”（实际是4月15日）、让AI提醒错误的时间等
             * 特点：用户向AI透露错误信息，AI基于错误信息给出回应，后续可纠正
           - **calendar（日历）**：适合记录错误的时间安排，后续可以被纠正或更新
             * 例如：在日历中错误地标记了5月15日的活动，后来被告知后修改为4月15日
           - **note（笔记）**：适合记录从别人那得到的错误信息，或者自己记错的内容
             * 例如：记下“朋友生日是5月15日”，后来发现记错了
             * 例如：记录会议时间，但信息来源有误，后续收到纠正通知
           - 至少需要2条数据：一条错误信息 + 一条纠正信息
           - **content_hint 必须明确包含要生成的数据的具体内容**，不能只是模糊的提示
             * ✅ 正确示例："发送短信给张三，内容为'我可能5月15日才能参加你的生日聚会了，4月有事'"
             * ✅ 正确示例："在日历中创建日程，标题为'参加李四生日聚会'，时间为5月15日 19:00-21:00"
             * ✅ 正确示例："记录笔记，标题为'朋友生日'，内容为'张三生日：5月15日'"
             * ❌ 错误示例："发送一条关于时间的短信"（太模糊）
             * ❌ 错误示例："创建一个日程"（没有具体内容）
        
        **示例场景**
        
        假设原事件是“4月15日参加朋友的生日聚会”
        
        ✅ **正确设计（前6种类型，包含纠正）**：
        - 4月5日：发短信给朋友“我可能5月15日才能参加你的生日聚会了，4月有事”
        - 4月10日：再发短信“不好意思，我重新安排了时间，4月15日可以参加了！之前说的5月不对”
        - 4月15日：原事件正常发生（参加生日聚会）
        
        ❌ **错误设计（前6种类型，缺少纠正）**：
        - 4月5日：发短信说“我5月15日参加你的生日聚会”
        - 4月15日：原事件发生（参加生日聚会）
        - 问题：没有纠正情节，4月15日的发生显得突兀
        
        ✅ **正确设计（第7种类型，记忆冲突）**：
        - 4月15日：原事件正常发生（参加生日聚会）
        - 5月20日：发短信给朋友说“我记得上次聚会是4月20日吧？”（实际是4月15日）
        - 或者在6月份记录笔记时写错日期：“4月20日参加了张三的生日聚会”
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
        注意：只生成与冲突情节相关的操作，不生成原事件的手机数据
        
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
            
            # 只支持这四种类型
            if data_type not in ['sms', 'note', 'calendar', 'agent_chat']:
                print(f"[Generate Phone Data] 不支持的数据类型：{data_type}，跳过")
                continue
            
            try:
                # 获取人物画像信息
                persona_info = self.persona if hasattr(self, 'persona') else ''
                
                # 根据 data_type 动态拼接对应的数据格式要求
                format_requirements = {
                    'sms': """
            ### SMS (短信) 格式要求
            - type: 固定为 "sms"
            - message_content: 短信内容，体现冲突情节（如发错的信息或纠正信息）
            - contactName: 联系人姓名（对方）
            - phoneNumber: 电话号码
            - datetime: 发送时间，格式 YYYY-MM-DD HH:MM:SS，日期使用 {plot_date}
            - message_type: "发送" 或 "接收"
            - daily_event_id: 字符串类型的事件ID
            """,
                    'note': """
            ### Note (笔记) 格式要求
            - type: 固定为 "note"
            - title: 笔记标题，简洁明确
            - content: 笔记内容，结构化分点，体现冲突情节相关信息
            - datetime: 创建时间，格式 YYYY-MM-DD HH:MM:SS，日期使用 {plot_date}
            - summarized_info: 笔记内容的摘要总结
            """,
                    'calendar': """
            ### Calendar (日历) 格式要求
            - event_id: 固定为 0
            - type: 固定为 "calendar"
            - title: 日程标题，简洁明确
            - description: 日程描述，包含时间、地点、核心信息
            - start_time: 开始时间，格式 YYYY-MM-DD HH:MM:SS
            - end_time: 结束时间，格式 YYYY-MM-DD HH:MM:SS
            - datetime: 创建时间，格式 YYYY-MM-DD HH:MM:SS
            - summarized_info: 日历内容的摘要总结
            """,
                    'agent_chat': """
            ### Agent Chat (智能体对话) 格式要求
            - event_id: 固定为 0
            - type: 固定为 "agent_chat"
            - date: 日期，格式 YYYY-MM-DD，使用 {plot_date}
            - conversation: 对话内容对象，最多包含两轮对话（turn 1, turn 2）
              - 每轮对话包含 user 和 assistant 两个对象
              - user 包含 action 和 content 字段
              - assistant 包含 action 和 content 字段
              - action 可选值：topic query, need inference, need confirmation, solution discussion 等
                        
            **示例**
            {{
                "date": "{plot_date}",
                "type": "agent_chat",
                "conversation": {{
                    "turn 1": {{
                        "user": {{
                            "action": "topic query",
                            "content": "用户的问题或咨询内容"
                        }},
                        "assistant": {{
                            "action": "need inference",
                            "content": "AI 助手的回复内容"
                        }}
                    }},
                    "turn 2": {{
                        "user": {{
                            "action": "need confirmation",
                            "content": "用户的进一步询问"
                        }},
                        "assistant": {{
                            "action": "solution discussion",
                            "content": "AI 助手的建议或解答"
                        }}
                    }}
                }}
            }}
            """
                }
                
                # 获取当前类型的格式要求
                current_format = format_requirements.get(data_type, '')
                
                # 构建完整的 prompt，让 LLM 直接生成手机数据
                generation_prompt = f"""
                作为手机数据生成专家，请基于以下冲突情节和人物画像，直接生成手机数据。
                
                【情节描述】
                {plot.get('description', '')}
                
                【情节角色】
                {plot_role}
                
                【内容提示】
                {content_hint}
                
                【人物画像】
                {persona_info if persona_info else '无特定画像信息'}
                
                【数据类型】
                {data_type}
                
                【任务要求】
                1. 严格按照【内容提示】中的具体要求生成数据
                2. 结合人物画像，确定合适的表达方式和语气
                3. **只生成与冲突情节直接相关的内容**，不要生成原事件的常规提醒
                4. 生成的数据必须符合指定类型的格式要求
                5. **只生成一条数据**，精确反映情节的核心内容
                
                **数据格式要求**
                {current_format}
                
                **输出要求**
                请以 JSON 数组格式返回生成的数据（**必须且只能包含一条数据**）：
                [
                    {{
                        // 根据数据类型填入对应字段
                    }}
                ]
                
                **重要约束**
                - 所有数据的 event_id 必须为 0
                - 内容必须严格基于【内容提示】，不得编造与原事件无关的内容
                - 时间字段的日期部分必须使用 {plot_date}
                - 语气和表达方式要符合人物画像特征
                - **数组中必须且只能包含一个对象**
                """
                
                # 调用 LLM 直接生成手机数据
                llm_result = llm_call_j(generation_prompt)
                
                # 解析结果
                operations = []
                if isinstance(llm_result, str):
                    start_idx = llm_result.find('[')
                    end_idx = llm_result.rfind(']') + 1
                    if start_idx != -1 and end_idx != -1:
                        operations = json.loads(llm_result[start_idx:end_idx])
                    else:
                        print(f"[Generate Phone Data] LLM 返回格式错误")
                        continue
                elif isinstance(llm_result, list):
                    operations = llm_result
                else:
                    print(f"[Generate Phone Data] LLM 返回格式错误")
                    continue
                
                if not isinstance(operations, list):
                    print(f"[Generate Phone Data] LLM 返回不是数组")
                    continue
                
                # 后处理：确保所有必要字段存在
                for op in operations:
                    # 强制设置 event_id 为 0
                    op['event_id'] = 0
                    
                    # 确保 type 字段正确
                    if 'type' not in op:
                        op['type'] = data_type
                    
                    # 如果没有 datetime，设置默认值
                    if 'datetime' not in op and plot_date:
                        op['datetime'] = f"{plot_date} 10:00:00"
                
                all_operations.extend(operations)
                print(f"[Generate Phone Data] 成功生成 {len(operations)} 条 {data_type} 数据（{plot_role}）")
                    
            except Exception as e:
                print(f"[Generate Phone Data] 生成失败：{e}")
                import traceback
                traceback.print_exc()
                continue
        
        print(f"[Generate Phone Data] 总共生成 {len(all_operations)} 条手机数据")
        return all_operations
    
    def QAGen(self, year: int = 2025, num_samples: int = 30) -> List[Dict[str, Any]]:
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
            conflict_scenario = plot.get('conflict_scenario', '')
            correct_information = plot.get('correct_information', '')
            incorrect_information = plot.get('incorrect_information', '')
            
            question_prompt = f"""
            作为问答设计师，请基于以下原始事件和错误信息类型生成一个问题。
            
            【原始事件】
            {json.dumps(daily_event_data, ensure_ascii=False, indent=2)}
            
            【错误信息】
            {incorrect_information}
            
            **任务要求**
            1. **根据错误信息的类型确定提问焦点**：
               - 如果错误信息涉及**时间**（如日期、时刻），则提问时间
               - 如果错误信息涉及**地点**，则提问地点
               - 如果错误信息涉及**人物**，则提问参与者
               - 如果错误信息涉及**内容/事项**，则提问具体内容
            
            2. **在题面中加入月份信息**：
               - 从原始事件的 date 字段中提取月份（如 "2025-12-01" 提取为 "12月"）
               - 在问题中自然地融入月份信息，例如“我在12月份...”或“12月的时候...”
               - 如果目标事件常规来说可能在一个月内经常发生，请加上上旬，下旬，第x周等描述，如 "我在12月上旬..."
               - 如果目标事件可能每天都会发生，请加上具体的日期信息，如 "我在12月1号..."
               
            3. **根据提问类型添加相关上下文**：
               - **提问时间时**：加上地点和人物信息，例如“我在12月份在[地点]与[人物]见面是什么时候？”
               - **提问地点时**：加上时间信息，例如“我在12月份[时间描述]XX时是在哪里？”
               - **提问人物时**：加上时间信息
               - **提问内容时**：加上时间信息
            
            4. **只基于原始事件的正确信息**设计问题
            5. **完全忽视任何冲突情节或错误信息**，不要在问题中提及或暗示
            6. 问题应该自然、符合真实对话场景
            7. 不要直接在问题中透露答案
            8. 以回忆的口吻提问
            
            **重要约束**
            - 问题必须只关注事件的客观事实（时间、地点、人物、内容等）
            - 不要提及任何关于“记错”、“纠正”、“之前说错”等内容
            - 不要暗示存在矛盾或冲突
            - 让问题看起来像是一个普通的记忆查询
            - **必须在问题中包含月份信息**
            
            **输出要求**
            请以 JSON 格式返回：
            {{
                "question": "生成的问题文本",
                "answer": "简洁准确的答案（基于原始事件的正确信息）"
            }}
            """
            
            try:
                llm_result = llm_call_j(question_prompt)
                
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
            
            【问题】
            {question_text}
            
            【答案】
            {answer_text}
            
            【现有证据】（共{len(all_evidence)}条）
            {json.dumps([{'type': item.get('type', 'unknown'), 'summary': str(item)[:200]} for item in all_evidence[:5]], ensure_ascii=False, indent=2)}
            
            **任务要求**
            1. 分析现有证据是否足以回答问题
            2. 如果不足，说明缺少什么关键信息
            3. 如果需要生成新证据，说明需要生成什么类型的数据和内容
            
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
            qa['ask_time'] = '2025-12'
        print(f"✓ 已为 {len(qa_pairs)} 个问题设置 question_type")
        
        # 保存到文件
        if self.phone_data_dir:
            parent_dir = os.path.dirname(self.phone_data_dir)
            output_path = os.path.join(parent_dir, "conflict_qa.json")
            
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(qa_pairs, f, ensure_ascii=False, indent=2)
            
            print(f"\n问答对已成功写入文件：{output_path}")
        
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
                    op['phone_id'] = str(self.phone_id_counters[op_type])
                
                self.phone_id_counters[op_type] += 1
                
                self.phonedata[op_type].append(op)
        
        print(f"[Add Operations] 已将 {len(operations)} 条操作数据添加到 phonedata")
