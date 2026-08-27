"""
写作代理模块
负责与用户迭代交互，基于用户输入的情节，分析和画像的适配性，修改并生成情节数据
"""

import json
import re
from typing import Dict, List, Any
from src.lifebench.utils.llm_call import llm_call_j, llm_call, llm_call_reason_j
from src.lifebench.utils.date_utils import TimeSpec
from .critic_agent import CriticAgent


class WritingAgent:
    """
    写作代理类
    与用户迭代交互，分析情节与画像适配性，修改并生成情节数据
    """
    
    def __init__(self, path: str, spec: TimeSpec = None):
        """
        初始化写作代理

        Args:
            path: 基础路径，包含persona.json和process/merged_timelines.json
            spec: 时间范围规格（年份 + 模拟月数），默认 2025 全年
        """
        self.path = path
        self.spec = spec or TimeSpec()
        self.persona_path = f"{path}/persona.json"
        self.reference_timeline_path = f"{path}/process/merged_timelines.json"
        self.persona_data = self._load_persona()
        self.reference_timeline_data = self._load_reference_timeline()
        # 初始化空的plot结构（月份数量由 spec 决定，是整条链路月份数的源头）
        self.initial_plot = {
            "comprehensive_summary": "",
            "monthly_details": [
                {"month": month_key, "events": [], "main topics": [], "changes": ""}
                for month_key in self.spec.month_keys
            ]
        }
        self.plot_history = [self.initial_plot.copy()]  # 保存情节的历史版本，初始版本为空结构
    
    def remove_json_wrapper(self, input_str: str, json_type: str = 'object') -> str:
        """
        移除JSON字符串的前后包装（如```json ```标签、非法转义字符等）
        并根据json_type参数提取对应的JSON内容：
        - json_type='object'：提取第一个{到最后一个}之间的内容
        - json_type='array'：提取第一个[到最后一个]之间的内容

        参数:
            input_str: 输入字符串
            json_type: JSON类型，'object'对应{}，'array'对应[]，默认为'object'

        返回:
            str: 清理后的字符串
        """
        # 步骤1：去除开头的```json（含空格/换行）和结尾的```（含空格）
        pattern = r'^\s*```json\s*\n?|\s*```\s*$'
        result = re.sub(pattern, '', input_str, flags=re.MULTILINE)

        # 步骤2：根据json_type提取对应的括号内容
        if json_type == 'array':
            first_bracket = result.find('[')
            last_bracket = result.rfind(']')
            if first_bracket != -1 and last_bracket != -1 and first_bracket < last_bracket:
                result = result[first_bracket:last_bracket + 1]
        else:  # 默认处理JSON对象
            first_brace = result.find('{')
            last_brace = result.rfind('}')
            if first_brace != -1 and last_brace != -1 and first_brace < last_brace:
                result = result[first_brace:last_brace + 1]

        # 步骤3：清理 JSON 非法控制字符
        # 保留：JSON 允许的控制字符（\n换行、\r回车、\t制表符、\b退格、\f换页）+ 可见ASCII字符（0x20-0x7E）+ 中文/全角字符
        valid_pattern = r'[^\x20-\x7E\n\r\t\b\f\u4E00-\u9FFF\u3000-\u303F\uFF00-\uFFEF\u2000-\u206F\u2E80-\u2EFF]'
        result = re.sub(valid_pattern, '', result)

        # 步骤4：规范空格和换行
        result = result.strip()  # 去除首尾多余空格/换行
        result = result.replace('\u3000', ' ')  # 全角空格转半角空格
        result = re.sub(r'\r\n?', '\n', result)  # 统一换行符为 \n
        return result
    
    def _load_persona(self) -> Dict:
        """
        加载画像数据
        
        Returns:
            画像数据字典
        """
        try:
            with open(self.persona_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载画像数据失败：{str(e)}")
            return {}
    
    def _load_reference_timeline(self) -> Dict:
        """
        加载参考时间线数据
        
        Returns:
            参考时间线数据字典
        """
        try:
            with open(self.reference_timeline_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载参考时间线数据失败：{str(e)}")
            return {}
    
    def analyze_adaptability(self, plot: Dict, user_input: str) -> str:
        """
        分析用户指令，生成情节修改指导
        
        Args:
            plot: 当前时间线数据
            user_input: 用户输入的修改指令
            
        Returns:
            建议字符串
        """
        prompt = f"""
        你是一位专业的作家，请根据以下人物画像、当前时间线和用户输入的修改指令，分析用户想要如何修改情节，并生成修改指导。
        
        人物画像：
        {json.dumps(self.persona_data, ensure_ascii=False, indent=2)}
        
        当前时间线：
        {json.dumps(plot, ensure_ascii=False, indent=2)}
        
        用户输入：
        {user_input}
        
        分析要求：
        1. 分析用户指令想怎么添加事件，是否需要扩展现有情节
        2. 对比当前时间线，找出需要修改的部分
        3. 以作家的视角，思考如何修改情节，可以删除现有情节或修改调整
        4. 思考如何将新事件融入到现有情节中，确保情节的合理性和连贯性
        5. 提出具体的修改指导，包括需要添加、删除或修改的内容
        
        输出格式：
        使用文本格式，包含以下两部分：
        1. 思考过程：使用<thinking>标签包裹
        2. 修改建议：使用<advice>标签包裹
        
        示例输出：
        <thinking>
        用户想要添加一个北京出差的事件，需要在{self.spec.month_keys[0]}月份添加相关内容。
        目前时间线中{self.spec.month_keys[0]}月份的events为空，需要添加出差相关事件。
        同时需要更新comprehensive_summary，包含这次出差的内容。
        </thinking>
        <advice>
        1. 在monthly_details中{self.spec.month_keys[0]}月份的events列表中添加："前往北京参加医学会议"
        2. 在monthly_details中{self.spec.month_keys[0]}月份的main topics列表中添加："专业发展"
        3. 在monthly_details中{self.spec.month_keys[0]}月份的changes字段中添加："拓展了专业人脉，了解了最新医学研究成果"
        4. 在comprehensive_summary中添加关于这次出差的内容
        </advice>
        """
        
        try:
            # 使用llm_call而不是llm_call_j，因为不要求返回JSON
            response = llm_call(prompt).strip()
            
            # 提取思考过程和建议
            import re
            thinking_match = re.search(r'<thinking>(.*?)</thinking>', response, re.DOTALL)
            advice_match = re.search(r'<advice>(.*?)</advice>', response, re.DOTALL)
            
            thinking = thinking_match.group(1).strip() if thinking_match else ""
            advice = advice_match.group(1).strip() if advice_match else ""
            
            # 如果没有advice但有thinking，则把response去除thinking当作advice
            if not advice and thinking:
                advice = response.replace(f'<thinking>{thinking}</thinking>', '').strip()
            # 如果既没有advice也没有thinking，则把所有输出当作advice
            elif not advice and not thinking:
                advice = response
            
            # 打印思考过程和建议
            print(f"思考过程：\n{thinking}")
            print(f"修改建议：\n{advice}")
            
            return advice
        except Exception as e:
            print(f"分析用户指令失败：{str(e)}")
            print(f"思考过程：分析用户指令失败")
            print(f"修改建议：{user_input}")
            return user_input
    
    def modify_plot(self, plot: Dict, advice: str) -> Dict:
        """
        根据分析结果修改情节

        Args:
            plot: 原始情节数据
            advice: 修改建议字符串

        Returns:
            修改后的情节数据
        """
        # 按 spec 时间范围动态生成示例，避免 12 个月示例诱导 LLM 发散到范围外
        example_details = [
            {
                "month": month_key,
                "events": ["制定年度计划", "参加行业会议"] if idx == 0 else [],
                "main topics": ["规划", "专业发展"] if idx == 0 else [],
                "changes": "开始注重时间管理和目标设定" if idx == 0 else "",
            }
            for idx, month_key in enumerate(self.spec.month_keys)
        ]
        example_plot = {
            "comprehensive_summary": (
                f"{self.spec.year}年是充满挑战与成长的一年。在专业领域，通过项目管理的突破，"
                "提升了团队协作效率；在财务方面，通过合理规划实现了资产增值；在健康意识上，"
                "经历了从忽视到重视的转变；在家庭责任上，深刻理解了家庭的重要性。这一年，"
                "在压力中成长，在挑战中突破，实现了个人的系统性跃迁。"
            ),
            "monthly_details": example_details,
        }
        example_json = json.dumps(example_plot, ensure_ascii=False, indent=4)

        prompt = f"""
        你是一位专业的人生规划师，请根据以下人物画像、原始时间线和修改建议，修改时间线数据。

        人物画像：
        {json.dumps(self.persona_data, ensure_ascii=False, indent=2)}

        原始时间线：
        {json.dumps(plot, ensure_ascii=False, indent=2)}

        修改建议：
        {advice}

        修改要求：
        1. 根据修改建议修改时间线
        2. 修改时间线，使其更多样、丰富、合理
        3. 确保修改后的时间线符合人物的性格、职业、背景和目标
        4. 提高时间线的合理性和连贯性
        5. 保持与原始时间线相同的格式
        6. 时间范围严格限定为 {self.spec.describe()}，monthly_details 只能包含 {', '.join(self.spec.month_keys)} 这些月份，不得新增或遗漏其他月份

        输出格式：
        仅输出修改后的完整时间线数据，使用JSON格式，与输入格式一致

        输出JSON示例：
        {example_json}
        """

        try:
            response = llm_call_reason_j(prompt).strip()
            # 移除JSON包装
            response = self.remove_json_wrapper(response, 'object')
            # 解析响应
            modified_plot = json.loads(response)
            # 月份护栏：杜绝优化过程把时间线发散到 spec 之外的月份
            modified_plot = self._guard_monthly_details(modified_plot)
            print(f"修改后的时间线：\n{json.dumps(modified_plot, ensure_ascii=False, indent=2)}")
            return modified_plot
        except Exception as e:
            print(f"修改情节失败：{str(e)}")
            return plot

    def _guard_monthly_details(self, plot: Dict) -> Dict:
        """
        月份护栏：强制 monthly_details 与 spec.month_keys 严格一致。

        丢弃 spec 范围之外的月份（防止 12 月泄漏），并补齐缺失的目标月份，
        最终按 spec 顺序排序。这是所有情节修改（modify_plot）的唯一收口点。
        """
        if not isinstance(plot, dict):
            return plot
        details = plot.get("monthly_details")
        if not isinstance(details, list):
            details = []
        allowed = set(self.spec.month_keys)
        kept = [d for d in details if isinstance(d, dict) and d.get("month") in allowed]
        dropped = [d.get("month") for d in details
                   if not (isinstance(d, dict) and d.get("month") in allowed)]
        if dropped:
            print(f"⚠️ 月份护栏：丢弃超出 {self.spec.describe()} 的月份 {dropped}")
        present = {d.get("month") for d in kept}
        for month_key in self.spec.month_keys:
            if month_key not in present:
                kept.append({"month": month_key, "events": [], "main topics": [], "changes": ""})
        order = {k: i for i, k in enumerate(self.spec.month_keys)}
        kept.sort(key=lambda d: order.get(d.get("month"), 0))
        plot["monthly_details"] = kept
        return plot
    
    def parse_command(self, user_input: str) -> Dict:
        """
        解析用户指令，确定调用什么流程
        
        Args:
            user_input: 用户输入
            
        Returns:
            指令解析结果，包含command和content字段
        """
        prompt = f"""
        你是一位指令解析专家，请分析用户的输入，确定用户想要执行什么操作：
        1. 修改情节：用户希望修改现有的情节
        2. 撤销：用户希望撤销上一次的修改，恢复到之前的版本
        3. 自动优化：用户希望使用参考时间线数据自动优化当前情节
        4. 结束：用户希望结束当前会话，保存情节数据
        5. 无关内容：用户询问与情节生成无关的内容
        
        用户输入：
        {user_input}
        
        输出JSON格式：
        {{{{
            "command": "修改情节" 或 "撤销" 或 "自动优化" 或 "结束" 或 "无关内容",
            "content": 用户输入的具体内容
        }}}}
        """
        
        try:
            response = llm_call_j(prompt).strip()
            # 移除JSON包装
            response = self.remove_json_wrapper(response, 'object')
            result = json.loads(response)
            return result
        except Exception as e:
            print(f"解析指令失败：{str(e)}")
            return {
                "command": "修改情节",
                "content": user_input
            }
    
    def interact_with_user(self, user_input: str, current_plot: Dict = None) -> Dict:
        """
        与用户迭代交互，生成最终的情节数据
        
        Args:
            user_input: 用户的输入
            current_plot: 当前情节数据
            
        Returns:
            最终的情节数据
        """
        # 解析用户指令
        command_result = self.parse_command(user_input)
        command = command_result.get("command", "修改情节")
        content = command_result.get("content", user_input)
        
        if command == "无关内容":
            print("抱歉，我只能回答与情节生成相关的问题。")
            return current_plot if current_plot else self.initial_plot.copy()
        
        if command == "结束":
            # 获取当前情节数据
            current_plot = self.plot_history[-1].copy()
            # 保存情节数据到指定文件
            save_path = f"{self.path}/process/optimize_timeline.json"
            try:
                # 确保目录存在
                import os
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                # 保存数据
                with open(save_path, 'w', encoding='utf-8') as f:
                    json.dump(current_plot, f, ensure_ascii=False, indent=2)
                print(f"情节数据已保存到 {save_path}")
            except Exception as e:
                print(f"保存情节数据失败：{str(e)}")
            # 返回None表示结束会话
            return None
        
        if command == "撤销":
            # 初始空版本就是最原始版本，撤销到初始版本后就不可以撤销了
            # 历史记录中至少需要有2个版本才可以撤销（初始版本+至少一个修改版本）
            if len(self.plot_history) > 1:
                # 移除最后一次修改的版本，返回之前的版本
                self.plot_history.pop()
                previous_plot = self.plot_history[-1]
                print("已撤销到上一个版本")
                return previous_plot
            else:
                print("已经是初始版本，无法再撤销")
                return self.plot_history[-1].copy()
        
        if command == "自动优化":
            # 确定当前情节，始终使用栈顶的数据作为当前情节
            current_plot = self.plot_history[-1].copy()
            # 调用自动优化方法
            optimized_plot = self.optimize_plot_with_reference_timeline(current_plot)
            return optimized_plot
        
        # 确定当前情节，始终使用栈顶的数据作为当前情节
        # 这样可以确保当前数据和栈顶数据一致
        current_plot = self.plot_history[-1].copy()
        
        # 分析用户指令，生成修改指导
        advice = self.analyze_adaptability(current_plot, content)
        
        # 调用modify_plot方法进行修改
        updated_plot = self.modify_plot(current_plot, advice)
        
        # 保存修改后的情节到历史记录
        # 添加修改后的版本
        self.plot_history.append(updated_plot.copy())

        return updated_plot
    
    def optimize_plot_with_reference_timeline(self, current_plot: Dict) -> Dict:
        """
        利用参考时间线数据优化当前情节时间线
        
        Args:
            current_plot: 当前情节数据
            
        Returns:
            优化后的情节数据
        """
        try:
            # 使用已加载的参考时间线数据作为参考情节
            reference_plots = self.reference_timeline_data
            
            print("开始分析参考时间线数据...")
            
            # 随机采样6个参考数据
            import random
            if len(reference_plots) > 6:
                sampled_plots = random.sample(reference_plots, 6)
                print(f"随机采样了6个参考情节")
            else:
                sampled_plots = reference_plots
                print(f"参考情节数量不足6个，使用全部{len(reference_plots)}个")
            
            # 遍历参考情节，每次处理两个参考情节后更新当前情节
            optimized_plot = current_plot.copy()
            for i in range(0, len(sampled_plots), 2):
                # 获取当前两个参考情节
                ref_plots = sampled_plots[i:i+2]
                print(f"分析参考情节 {i+1}-{min(i+2, len(sampled_plots))}/{len(sampled_plots)}...")
                
                # 分析参考情节中的好元素，使用最新的情节数据
                prompt = f"""
                你是一位专业的作家，请分析以下参考情节，提取其中的优秀元素，丰富当前时间线，融入多线叙事，优化当前的时间线。
                
                人物画像：
                {json.dumps(self.persona_data, ensure_ascii=False, indent=2)}
                
                参考情节：
                {json.dumps(ref_plots, ensure_ascii=False, indent=2)}
                
                当前时间线：
                {json.dumps(optimized_plot, ensure_ascii=False, indent=2)}
                
                分析要求：
                1. 分析当前时间线是否存在以下问题：
                   - 过于稀疏，事件比较少
                   - 过于平淡，事件比较日常平淡，不能反映现实人物的复杂性、独特性、变化性、动态性、多样性
                   - 过于单调、静态：缺乏人物变化，多线叙事，事件情节间影响的体现
                2. 从参考情节中选取与人物画像相符的优秀元素，可以借鉴加入到当前时间线
                3. 合理修改借鉴的情节，使其融入当前时间线，确保符合人物的性格、职业、背景和目标
                4. 优化原有时间线，确保新情节加入后产生的因果关联和后续影响被体现，甚至可能影响已有事件的发生情况
                5. 提供具体的优化建议，包括需要添加、修改或调整的内容
                6. 我们期望最终的时间线更丰富、更立体、更有趣味性，能更好地反映人物的性格、职业、背景和目标。同时多线叙事，且环节仅仅相扣，不断发展变化。{self.spec.year}年1月至{self.spec.months}月期间有许多不同主题的多线叙述，每个线还会交叉影响。每个月也有充实的足够多的事件。
                7. 你不需要在一次修改就满足所有的最终目标，提出一定的修改建议，选取适量的情节和构思适量的创作想法，并为情节的选取增添一些随机性。对于参考情节的数据也是选择性的使用。
                8. 你也可以选择性删除已有情节，创作新的情节，优化当前时间线，但尽量不要删除太多内容。
        
                输出格式：
                使用文本格式，包含以下两部分：
                1. 思考过程：使用<thinking>标签包裹
                2. 优化建议：使用<advice>标签包裹
                """
                from src.lifebench.utils.llm_call import llm_call_reason
                response = llm_call_reason(prompt).strip()
                print(f"参考情节 {i+1}-{min(i+2, len(sampled_plots))} 的分析结果：\n{response}")
                # 提取思考过程和建议
                import re
                thinking_match = re.search(r'<thinking>(.*?)</thinking>', response, re.DOTALL)
                advice_match = re.search(r'<advice>(.*?)</advice>', response, re.DOTALL)
                
                thinking = thinking_match.group(1).strip() if thinking_match else ""
                advice = advice_match.group(1).strip() if advice_match else ""
                
                # 如果没有匹配到advice但匹配到了thinking，则从response中去除thinking部分作为advice
                if not advice and thinking:
                    # 去除thinking部分
                    advice = response.replace(f'<thinking>{thinking}</thinking>', '').strip()
                    print("使用去除thinking后的内容作为advice")
                # 如果都没匹配到，直接把llm的输出作为advice
                elif not advice and not thinking:
                    advice = response.strip()
                    print("使用LLM原始输出作为advice")
                
                if advice:
                    print(f"发现优秀情节元素：{advice[:100]}...")
                    # 应用当前参考情节的优化建议
                    optimized_plot = self.modify_plot(optimized_plot, advice)
                    print(f"参考情节 {i+1}-{min(i+2, len(sampled_plots))} 优化完成！")
            
            # 保存优化后的情节到历史记录
            self.plot_history.append(optimized_plot.copy())
            print("情节优化完成！")
            return optimized_plot
                
        except Exception as e:
            print(f"优化情节失败：{str(e)}")
            return current_plot
    
    def iterative_optimization(self, current_plot: Dict, max_rounds: int = 3) -> Dict:
        """
        循环调用评判家代理进行迭代优化
        
        Args:
            current_plot: 当前情节数据
            max_rounds: 最大迭代轮次，默认3
            
        Returns:
            优化后的情节数据
        """
        try:
            print("\n=== 开始迭代优化过程 ===")
            
            # 创建评判家代理
            critic_agent = CriticAgent(self.path, spec=self.spec)
            
            # 初始化优化结果
            optimized_plot = current_plot.copy()
            
            # 进行多轮优化
            for round_num in range(1, max_rounds + 1):
                print(f"\n=== 第 {round_num} 轮优化 ===")
                
                # 调用评判家代理进行评估和优化
                optimized_plot = critic_agent.interact_with_writing_agent(self, optimized_plot)
                
                print(f"第 {round_num} 轮优化完成！")
            
            print("\n=== 迭代优化过程完成 ===")
            return optimized_plot
            
        except Exception as e:
            print(f"迭代优化失败：{str(e)}")
            return current_plot