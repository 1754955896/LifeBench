"""
智能体对话操作生成器模块
负责生成与智能体的对话数据
"""

import json
import random
from typing import List, Dict
from src.lifebench.utils.llm_call import llm_call


class ChatOperationGenerator:
    """
    智能体对话操作生成器
    根据事件信息生成用户与智能体的对话数据
    """
    
    def __init__(self, random_seed: int = 42):
        """初始化智能体对话生成器"""
        random.seed(random_seed)
    
    def parse_llm_prob_json(self, llm_json_str: str) -> List[Dict]:
        """解析 LLM 返回的 JSON 数据"""
        try:
            start_idx = llm_json_str.find('[')
            end_idx = llm_json_str.rfind(']')
            if start_idx == -1 or end_idx == -1 or start_idx >= end_idx:
                print("错误：未找到有效的 JSON 数组（缺少 [] 包裹）")
                return []

            core_json_str = llm_json_str[start_idx:end_idx + 1].strip()
            return json.loads(core_json_str)
        except json.JSONDecodeError as e:
            print(f"JSON 解析失败：位置{e.pos}，原因{e.msg}")
            return []
        except Exception as e:
            print(f"解析异常：{str(e)}")
            return []
    
    def _validate_format_only(self, data: Dict) -> tuple:
        """
        仅校验智能体对话数据格式（不涉及合理性），并删除多余字段
        
        Args:
            data: 单条智能体对话数据
            
        Returns:
            (is_valid: bool, error_message: str)
        """
        try:
            required_fields = ["event_id", "date", "type", "conversation"]
            missing_fields = [f for f in required_fields if f not in data]
            if missing_fields:
                return False, f"智能体对话数据缺少必填字段: {missing_fields}"
            
            # 删除多余字段
            extra_fields = [k for k in data.keys() if k not in required_fields]
            for field in extra_fields:
                del data[field]
            
            # 校验 type 字段
            if data.get("type") != "agent_chat":
                return False, f"type 取值错误: {data.get('type')}，应为 'agent_chat'"
            
            # 校验 conversation 是否为字典
            if not isinstance(data.get("conversation"), dict):
                return False, "conversation 字段格式错误，应为字典"
            
            # 校验 conversation 中的 turn 结构
            conversation = data["conversation"]
            valid_turns = []
            for key in conversation.keys():
                if not key.startswith("turn "):
                    return False, f"conversation 中存在非 turn 键: {key}"
                turn_num = key.replace("turn ", "")
                if not turn_num.isdigit():
                    return False, f"turn 编号格式错误: {key}"
                valid_turns.append(int(turn_num))
            
            # 校验 turn 数量不超过 3
            if len(valid_turns) > 3:
                return False, f"对话轮数超过限制: {len(valid_turns)} 轮，最多 3 轮"
            
            # 校验每个 turn 的结构
            for turn_key, turn_data in conversation.items():
                if not isinstance(turn_data, dict):
                    return False, f"{turn_key} 格式错误，应为字典"
                
                # 校验 user 和 assistant 字段
                if "user" not in turn_data or "assistant" not in turn_data:
                    return False, f"{turn_key} 缺少 user 或 assistant 字段"
                
                # 校验 user 结构
                user_data = turn_data["user"]
                if not isinstance(user_data, dict):
                    return False, f"{turn_key}.user 格式错误，应为字典"
                if "action" not in user_data or "content" not in user_data:
                    return False, f"{turn_key}.user 缺少 action 或 content 字段"
                
                # 校验 assistant 结构
                assistant_data = turn_data["assistant"]
                if not isinstance(assistant_data, dict):
                    return False, f"{turn_key}.assistant 格式错误，应为字典"
                if "action" not in assistant_data or "content" not in assistant_data:
                    return False, f"{turn_key}.assistant 缺少 action 或 content 字段"
            
            return True, ""
            
        except Exception as e:
            return False, f"格式校验异常: {str(e)}"
    
    def phone_gen_agent_chat(self, date, contact, file_path, c):
        """
        生成指定日期的智能体对话数据
        
        Args:
            date: 日期
            contact: 联系人列表
            file_path: 文件路径
            c: 结果列表
            
        Returns:
            生成的智能体对话数据列表
        """
        from src.lifebench.event.phone_data_gen import extool
        
        c = []
        daily_events = extool.filter_by_date(date)
        
        prob_template = '''
        请基于用户提供的{{当日事件}}和{{个人画像}}，全面分析该用户在当天可能与智能体对话的所有潜在需求，并为每个需求单独分配概率。需特别关注两类核心需求：
        1. 目的性/功能性需求：如询问、求解、搜索、日程管理等具体任务需求
        2. 心理性需求：如交谈分享信息、情感支持、压力缓解等情绪和心理层面的需求
        
        ## 分析规则
        1. **需求提取全面性**：从当日事件中提取所有可能的对话场景，包括但不限于：
           - 与当日事件直接相关的任务需求（如活动准备、信息查询）
           - 与当日事件间接相关的延伸需求（如经验分享、后续规划）
           - 基于当日经历/或个人兴趣产生的其他需求（如压力倾诉、成就分享、爱好话题询问等）
           - **每天的需求不得超过 4 个，可以为空数组，合理选择生成。**
           
        2. **概率分配合理性**：
           - 基于用户画像的行为习惯和当日事件的紧急重要程度分配概率
           - 每个需求的概率独立分析，总和不必等于 100%
           - 概率范围为 0-100%，使用百分比字符串格式（如"60%"）
           
        3. **场景描述具体性**：
           - 每个需求应与用户当日具体活动紧密相关
           - 需体现用户可能的真实对话动机和情境
           - 避免泛泛而谈，要有明确的上下文背景
           
        4. **上下文信息丰富性**：
           - **context 字段必须包含以下信息**：
             1. 用户信息总结：基于个人画像的关键特征（如职业、兴趣爱好、性格特点等）
             2. 对话完整上下文：当日事件的详细背景、时间顺序和相关细节
             3. 用户对话需求点：用户的具体问题或诉求，为什么会产生这个需求
             4. 对话可能涉及的内容：围绕需求可能展开的话题、需要的信息或支持类型
             5. 通过对话应可以透露一些事件相关信息。供智能体分析。
           - context 应足够详细，后续将仅基于此信息生成对话，无需再参考原始事件和画像
           
        ## 输出格式
        请输出 JSON 数组，每个元素包含：
        - event_id: 需求基于的 event_id，若没有则填 0
        - requirement: 对话需求的详细描述
        - intention: 对话的核心意图和目标
        - probability: 发生概率（百分比字符串，如"60%"）
        - context: 对话的详细上下文背景，包含用户信息总结、完整上下文、需求点和可能涉及的内容
        
        ## 输出示例
        [
            {{
                "event_id": "1",
                "requirement": "询问如何准备明天的马拉松比赛",
                "intention": "获取马拉松比赛前的准备建议，确保比赛顺利进行",
                "probability": "75%",
                "context": "用户信息总结：张明，35 岁，IT 工程师，爱好跑步，有 2 年跑步经验，首次参加全程马拉松。\\n对话完整上下文：今天是 2025 年 1 月 1 日，用户刚完成了马拉松前的最后一次长距离训练（25 公里），感觉膝盖有些不适，同时担心明天比赛的天气和补给安排。\\n用户对话需求点：用户担心膝盖疼痛影响明天的比赛，需要了解如何缓解膝盖不适，同时希望获取比赛当天的饮食、装备和节奏控制建议。\\n对话可能涉及的内容：膝盖疼痛的临时缓解方法、比赛前一晚的准备工作、比赛当天的饮食安排、装备检查清单、跑步节奏控制策略、补给站使用建议。"
            }},
            {{
                "event_id": "0",
                "requirement": "分享今天完成项目的成就感",
                "intention": "表达完成重要项目的喜悦，获得情感上的肯定和共鸣",
                "probability": "45%",
                "context": "用户信息总结：李华，28 岁，市场营销专员，性格开朗，喜欢分享工作成就，重视他人的认可。\\n对话完整上下文：今天是 2025 年 1 月 1 日，用户耗时 3 个月的市场推广项目终于成功上线，获得了领导和同事的好评，项目初期遇到了很多困难，但最终都一一克服。\\n用户对话需求点：用户希望分享项目成功的喜悦，回顾项目过程中的挑战和收获，获得智能体的积极回应和肯定。\\n对话可能涉及的内容：项目的具体成果、遇到的主要困难、解决问题的方法、团队合作的体验、对未来工作的影响和期望。"
            }}
        ]
        
        ## 输入数据
        <当日事件>: {daily_events}
        <个人画像>: {persona}
        
        请直接输出符合要求的 JSON 数据，不要添加任何额外文本、注释或说明。
        '''
        
        prob_prompt = prob_template.format(daily_events=daily_events, persona=extool.persona)
        print("对话需求概率分析 prompt:", prob_prompt)
        
        prob_response = llm_call(prob_prompt)
        print("概率分析响应:", prob_response)
        
        prob_data = self.parse_llm_prob_json(prob_response)
        
        chat_template = '''
        请基于以下提供的完整上下文信息，生成一段个人与智能体助手的对话。
        
        ## 核心要求
        1. **对话轮数**：严格控制在 1-3 轮之间（即 turn 1 到 turn 3）
        2. **内容精准**：准确反映原事件的核心信息，避免无关细节
        3. **表达简洁**：每轮对话内容精炼直接，去除冗余叙述
        4. **自然流畅**：符合真实对话场景，体现用户特征和需求
        5. **事件信息展现**：可以展现部分事件的信息，如时间、地点、人物、动作等关键要素，帮助用户向智能体描述自己的情况或需求
        
        ## 对话角色
        - 用户：根据上下文中的用户信息确定身份和特征，可以向智能体描述自己当前的事件或情况
        - 智能体助手：理解用户需求并提供帮助的 AI 助手，能够基于用户提供的事件信息进行推理和建议
        
        ## 动作类型
        用户动作：topic query / information request / need confirmation / solution feedback / clarification
        智能体动作：need inference / solution proposal / solution discussion / information provision / confirmation / talk
        
        ## 上下文信息
        {context}
        
        ## 输出格式
        JSON 格式，包含 turn 1 到 turn n（n≤3），示例：
        {{
          "turn 1": {{
            "user": {{"action": "topic query", "content": "出差时如何高效工作？"}},
            "assistant": {{"action": "need inference", "content": "你需要适配频繁出差、操作简单的时间管理方法？"}}
          }},
          "turn 2": {{
            "user": {{"action": "need confirmation", "content": "对，客户电话经常打断工作。"}},
            "assistant": {{"action": "solution proposal", "content": "每天划分 1 个 3 小时'核心工作块'，关闭非紧急通知，专注关键任务。"}}
          }}
        }}
        
        直接输出 JSON 数据，不要添加任何额外文本。
        '''
        
        generated_count = 0
        for item in prob_data:
            if generated_count >= 4:
                break
            prob = int(item['probability'].strip('%'))
            if random.random() < prob / 100:
                selected_context = item
                print(f"{date}：生成智能体对话，场景：{selected_context['requirement']}")
                
                chat_prompt = chat_template.format(context=selected_context)
                print("对话生成 prompt:", chat_prompt)
                
                chat_response = llm_call(chat_prompt)
                print("对话生成响应:", chat_response)
                
                if "<END_OF_DIALOG>" in chat_response:
                    chat_response = chat_response.replace("<END_OF_DIALOG>", "")
                
                chat_response = self.remove_json_wrapper(chat_response, 'object')
                try:
                    chat_data = json.loads(chat_response)
                    generated_item = {
                        "event_id": selected_context['event_id'],
                        "date": date,
                        "type": "agent_chat",
                        "conversation": chat_data
                    }
                    
                    # 格式校验
                    format_valid, format_error = self._validate_format_only(generated_item)
                    if format_valid:
                        c.append(generated_item)
                        generated_count += 1
                    else:
                        print(f"  [格式错误] event_id={selected_context['event_id']}: {format_error}，抛弃该数据")
                except json.JSONDecodeError as e:
                    print(f"对话数据解析失败：{str(e)}")
        
        if generated_count == 0:
            print(f"{date}：未生成智能体对话")
        else:
            print(f"{date}：共生成 {generated_count} 次智能体对话")
        
        return c
    
    @staticmethod
    def remove_json_wrapper(s: str, json_type: str = 'array') -> str:
        """移除 JSON 字符串的包装"""
        import re
        pattern = r'^\s*```json\s*\n?|\s*```\s*$'
        result = re.sub(pattern, '', s, flags=re.MULTILINE)
        
        if json_type == 'array':
            first_bracket = result.find('[')
            last_bracket = result.rfind(']')
            if first_bracket != -1 and last_bracket != -1 and first_bracket < last_bracket:
                result = result[first_bracket:last_bracket + 1]
        else:
            first_brace = result.find('{')
            last_brace = result.rfind('}')
            if first_brace != -1 and last_brace != -1 and first_brace < last_brace:
                result = result[first_brace:last_brace + 1]
            
        return result
