"""
评判家代理模块
负责分析时间线质量，找出不足并给出修改建议
"""

import json
import re
from typing import Dict, List, Any
from datetime import datetime, timedelta
import holidays
from utils.llm_call import llm_call


def log(message: str, debug: bool = True) -> None:
    """
    日志函数，根据debug参数决定是否打印
    
    Args:
        message: 要打印的消息
        debug: 是否打印日志，默认为True
    """
    if debug:
        print(f"[DEBUG] {message}")


class CriticAgent:
    """
    评判家代理类
    分析时间线质量，找出不足并给出修改建议
    """
    
    def __init__(self, path: str, year: int = 2025):
        """
        初始化评判家代理
        
        Args:
            path: 基础路径，包含persona.json
            year: 目标年份，默认为2025
        """
        self.path = path
        self.year = year
        self.persona_path = f"{path}/persona.json"
        self.persona_data = self._load_persona()
        # 预设的评估标准
        self.evaluation_criteria = {
            "合理性": "时间线是否符合逻辑，是否符合人物的背景和目标，是否符合现实世界的常理",
            "丰富性": "时间线是否包含足够的事件和细节，每个月是否有充实的内容",
            "多样性": "时间线是否包含不同类型的事件，如工作、生活、学习、社交等",
            "连贯性": "事件之间是否有合理的因果关系和逻辑联系",
            "真实性": "事件是否符合人物的性格、职业、背景和目标",
            "发展性": "时间线是否体现了人物的成长和变化",
            "多线叙事": "是否存在多条叙事线索，且线索之间有交叉影响",
            "平衡性": "不同领域的事件是否分布合理，避免过于集中在某一方面",
            "创新性": "时间线是否有新颖的情节和创意，避免过于平淡",
            "完整性": "是否有些产生影响变化的事件在后续的时间线没有被体现，或某个事件链条没有完整体现到12月结束，如认识了某人，但后续没有再提及，或是培养了新爱好但没有后续发展",
            "充分性": "画像数据的每个细节点（爱好，关系，技能）是否被重复体现，有没有遗漏。"
        }
        # 评估次数计数器
        self.evaluation_count = 0
        # 上一次评估总结缓存
        self.previous_evaluation_summary = None
    
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
    
    def evaluate_timeline(self, current_plot: Dict) -> str:
        """
        评估时间线质量
        
        Args:
            current_plot: 当前时间线数据
            
        Returns:
            评估结果字符串
        """
        try:
            # 构建评估提示词
            prompt = f"""
            你是一位专业的人生故事评判家，请根据以下人物画像、评估标准和当前时间线，对时间线质量进行全面评估，并给出具体的修改建议。
            
            人物画像：
            {json.dumps(self.persona_data, ensure_ascii=False, indent=2)}
            
            评估标准：
            {json.dumps(self.evaluation_criteria, ensure_ascii=False, indent=2)}
            
            当前时间线：
            {json.dumps(current_plot, ensure_ascii=False, indent=2)}
            
            评估要求：
            1. 基于预设的评估标准，对时间线进行全面分析
            2. 为每个评估维度给出具体的评分（1-10分）
            3. 找出时间线中的不足和问题
            4. 给出具体、可操作的修改建议
            5. 分析如何使时间线更符合人物画像，更具吸引力
            
            输出格式：
            使用文本格式，包含以下部分：
            1. 整体评估：使用<overall>标签包裹
            2. 维度评分：使用<scores>标签包裹，列出每个维度的评分
            3. 问题分析：使用<problems>标签包裹，详细分析存在的问题
            4. 修改建议：使用<suggestions>标签包裹，给出具体的修改建议
            """
            
            response = llm_call(prompt).strip()
            log(f"评估结果：\n{response}")
            
            return response
            
        except Exception as e:
            error_msg = f"评估时间线失败：{str(e)}"
            log(error_msg)
            return f"<problem>{error_msg}</problem><suggestion>评估失败，请检查输入数据</suggestion>"
    
    def generate_improvement_advice(self, current_plot: Dict) -> str:
        """
        生成具体的改进建议
        
        Args:
            current_plot: 当前时间线数据
            
        Returns:
            改进建议字符串
        """
        evaluation_result = self.evaluate_timeline(current_plot)
        # 从评估结果字符串中提取suggestions部分
        import re
        suggestions_match = re.search(r'<suggestions>(.*?)</suggestions>', evaluation_result, re.DOTALL)
        suggestions = suggestions_match.group(1).strip() if suggestions_match else ""
        return suggestions
    
    def interact_with_writing_agent(self, writing_agent, current_plot: Dict) -> Dict:
        """
        与写作代理交互，提供改进建议
        
        Args:
            writing_agent: WritingAgent实例
            current_plot: 当前时间线数据
            
        Returns:
            改进后的时间线数据
        """
        print("\n=== 评判家开始分析时间线 ===")
        
        # 执行评估规划
        evaluation_result = self.plan(current_plot)
        
        # 打印评估结果
        print("\n=== 综合评估结果 ===")
        print(f"关键问题: {evaluation_result.get('problems', '')[:100]}...")
        print(f"改进建议: {evaluation_result.get('suggestions', '')[:100]}...")
        
        # 获取问题和改进建议
        problems = evaluation_result.get('problems', '')
        suggestions = evaluation_result.get('suggestions', '')
        # 拼接问题和建议
        suggestions = f"问题：{problems}\n\n建议：{suggestions}"
        
        if suggestions:
            print("\n=== 评判家给出的改进建议 ===")
            print(suggestions)
            
            # 使用写作代理应用改进建议
            improved_plot = writing_agent.modify_plot(current_plot, suggestions)
            
            # 保存改进后的情节到历史记录
            writing_agent.plot_history.append(improved_plot.copy())
            
            print("\n=== 时间线改进完成 ===")
            return improved_plot
        else:
            print("\n=== 未生成改进建议 ===")
            return current_plot
    
    def evaluate_dates(self, current_plot: Dict) -> str:
        """
        日期评估：分析时间线的节假日相关内容是否正确和体现
        
        Args:
            current_plot: 当前时间线数据
            
        Returns:
            日期评估结果字符串
        """
        try:
            # 使用初始化时设置的年份
            year = self.year
            
            # 获取中国节假日
            cn_holidays = holidays.China(years=year)
            
            # 构建节假日列表
            holiday_list = []
            for date, name in cn_holidays.items():
                holiday_list.append(f"{date.strftime('%Y-%m-%d')}: {name}")
            
            # 构建评估提示词
            prompt = f"""
            你是一位专业的时间线日期评估专家，请分析以下时间线数据中的节假日相关内容：
            
            人物画像信息：
            {json.dumps(self.persona_data, ensure_ascii=False, indent=2)}
            
            {year}年中国主要节假日：
            {chr(10).join(holiday_list)}
            
            时间线数据：
            {json.dumps(current_plot, ensure_ascii=False, indent=2)}
            
            评估要求：
            1. 首先给出详细的思考引导，具体步骤如下：
               - 提取时间线中已有的与节假日相关的事件（如春运、春节、国庆等）
               - 分析这些事件的时间安排是否正确，是否符合实际节假日日期
               - 评估节假日事件的内容是否丰富、合理，是否符合人物身份特点
               - 识别时间线中缺失的重要节假日事件
            2. 基于提供的{year}年中国主要节假日数据，系统分析时间线中是否充分体现了这些节假日
            3. 结合人物身份特点，分析相关的特殊日期（如教师/学生的寒暑假，特定工种的特殊日期）在时间线中的体现情况
            4. 评估时间线中节假日内容的丰富性、合理性和时间准确性
            5. 提供具体、可操作的改进建议，包括增加缺失的节假日事件、调整现有节假日事件的时间安排，删除或修改时间上错误的事件等，同时建议中给出重要节假日的具体时间。
            
            输出格式：
            1. 思考引导：使用<thinking>标签包裹
            2. 问题分析：使用<problem>标签包裹，列出时间线中与节假日相关的问题
            3. 改进建议：使用<suggestion>标签包裹，给出具体的改进建议
            """
            
            response = llm_call(prompt).strip()
            log(f"日期评估结果：\n{response}")
            return response
            
        except Exception as e:
            return f"日期评估失败：{str(e)}"
    
    def evaluate_dynamic_changes(self, current_plot: Dict) -> str:
        """
        动态变化评估：分析用户这一年的变化
        
        Args:
            current_plot: 当前时间线数据
            
        Returns:
            动态变化评估结果字符串
        """
        try:
            # 构建评估提示词
            prompt = f"""
            你是一位专业的时间线动态变化评估专家，请分析以下时间线数据中的动态变化：
            
            初始人物画像信息：
            {json.dumps(self.persona_data, ensure_ascii=False, indent=2)}
            
            时间线数据：
            {json.dumps(current_plot, ensure_ascii=False, indent=2)}
            
            评估要求：
            1. 首先给出思考引导，分析时间线中动态变化的体现情况
            2. 分析用户这一年认识了哪些新朋友
            3. 分析用户与他人的关系发生了哪些亲近/疏远的变化
            4. 分析用户培养了哪些新爱好
            5. 分析用户的物品偏好是否有改变
            6.分析其他变化发展的体现，如生活上，职业上，经济上等
            6. 评估动态变化的丰富性和合理性
            7. 提供具体的改进建议
            
            输出格式：
            1. 思考引导：使用<thinking>标签包裹
            2. 问题分析：使用<problem>标签包裹，列出时间线中与动态变化相关的问题
            3. 改进建议：使用<suggestion>标签包裹，给出具体的改进建议
            """
            
            response = llm_call(prompt).strip()
            log(f"动态变化评估结果：\n{response}")
            return response
            
        except Exception as e:
            return f"动态变化评估失败：{str(e)}"
    
    def evaluate_persona_implementation(self, current_plot: Dict) -> str:
        """
        画像信息体现评估：分析画像中有哪些信息每月体现
        
        Args:
            current_plot: 当前时间线数据
            
        Returns:
            画像信息体现评估结果字符串
        """
        try:
            # 构建评估提示词
            prompt = f"""
            你是一位专业的时间线画像信息体现评估专家，请分析以下时间线数据中画像信息的体现情况：
            
            人物画像信息：
            {json.dumps(self.persona_data, ensure_ascii=False, indent=2)}
            
            时间线数据：
            {json.dumps(current_plot, ensure_ascii=False, indent=2)}
            
            评估要求：
            1. 首先给出思考引导，分析时间线中画像信息的体现情况，如某个人物的社交关系，某个爱好，某个地域、职业特色
            2. 提取画像中的关键信息（社交关系、兴趣爱好、职业、目标等）
            3. 分析每月时间线中这些信息的体现情况
            4. 统计各信息类型的体现频率
            5. 评估画像信息在时间线中的体现充分性
            6. 提供具体的改进建议
            
            输出格式：
            1. 思考引导：使用<thinking>标签包裹
            2. 问题分析：使用<problem>标签包裹，列出时间线中与画像信息体现相关的问题
            3. 改进建议：使用<suggestion>标签包裹，给出具体的改进建议
            """
            
            response = llm_call(prompt).strip()
            log(f"画像信息体现评估结果：\n{response}")
            return response
            
        except Exception as e:
            return f"画像信息体现评估失败：{str(e)}"
    
    def _parse_evaluation_result(self, result: str) -> Dict[str, str]:
        """
        解析评估结果，提取problem和suggestion字段
        
        Args:
            result: LLM生成的评估结果字符串
            
        Returns:
            包含problem和suggestion字段的字典
        """
        import re
        
        # 提取think字段
        think_match = re.search(r'<thinking>(.*?)</thinking>', result, re.DOTALL)
        think = think_match.group(1).strip() if think_match else ""
        
        # 提取problem字段
        problem_match = re.search(r'<problem>(.*?)</problem>', result, re.DOTALL)
        problem = problem_match.group(1).strip() if problem_match else ""
        
        # 提取suggestion字段
        suggestion_match = re.search(r'<suggestion>(.*?)</suggestion>', result, re.DOTALL)
        suggestion = suggestion_match.group(1).strip() if suggestion_match else ""
        
        # 去掉think字段后的结果
        result_without_think = re.sub(r'<thinking>.*?</thinking>', '', result, flags=re.DOTALL).strip() if think else result
        
        # 如果problem提取失败
        if not problem:
            if suggestion:
                # 如果suggestion匹配到了，去除suggestion部分再赋值
                result_without_think_and_suggestion = re.sub(r'<suggestion>.*?</suggestion>', '', result_without_think, flags=re.DOTALL).strip()
                problem = result_without_think_and_suggestion
            else:
                problem = result_without_think
        
        # 如果suggestion提取失败
        if not suggestion:
            if problem:
                # 如果problem匹配到了，去除problem部分再赋值
                result_without_think_and_problem = re.sub(r'<problem>.*?</problem>', '', result_without_think, flags=re.DOTALL).strip()
                suggestion = result_without_think_and_problem
            else:
                suggestion = result_without_think
        
        return {
            "problem": problem,
            "suggestion": suggestion
        }
    
    def plan(self, current_plot: Dict) -> Dict[str, Any]:
        """
        规划评估流程：决定调用哪些评估方法，并行执行评估，然后整合输出
        
        Args:
            current_plot: 当前时间线数据
            
        Returns:
            整合后的评估结果
        """
        from concurrent.futures import ThreadPoolExecutor
        import json
        
        print("\n=== 开始执行评估规划 ===")
        
        # 定义评估方法
        evaluation_methods = {
            "comprehensive": self.evaluate_timeline,
            "dates": self.evaluate_dates,
            "dynamic_changes": self.evaluate_dynamic_changes,
            "persona_implementation": self.evaluate_persona_implementation
        }
        
        # 增加评估次数
        self.evaluation_count += 1
        print(f"当前是第 {self.evaluation_count} 次评估")
        
        # 决定调用哪些评估方法
        if self.evaluation_count == 1:
            # 初次评估：执行 dates, persona_implementation, dynamic_changes
            selected_methods = ["dates", "persona_implementation", "dynamic_changes"]
        else:
            # 后几次评估：使用 comprehensive
            selected_methods = ["comprehensive"]
        
        # 调用LLM来决定最终的评估方法
        from utils.llm_call import llm_call
        
        # 构建包含上一次评估总结的提示词
        previous_summary_info = """
        上一次的评估总结：
        {}
        """
        
        if self.previous_evaluation_summary:
            previous_summary_info = previous_summary_info.format(self.previous_evaluation_summary)
        else:
            previous_summary_info = "上一次评估总结：无"
        
        prompt = f"""
        你是一位专业的时间线评估专家，请根据以下信息决定应该使用哪些评估方法：
        
        评估方法列表：
        - comprehensive：全面评估时间线的各个维度
        - dates：分析时间线的节假日相关内容
        - dynamic_changes：分析用户一年中的变化
        - persona_implementation：分析画像信息在时间线中的体现
        
        当前是第 {self.evaluation_count} 次评估，默认选择的评估方法：{selected_methods}
        
        {previous_summary_info}
        
        请分析当前时间线数据，参考上一次的评估总结，决定是否需要调整评估方法：
        {json.dumps(current_plot, ensure_ascii=False, indent=2)}
        
        输出格式：
        仅返回JSON对象，格式如下：
        {{
            "selected_methods": ["方法1", "方法2", ...]
        }}
        """
        
        try:
            response = llm_call(prompt).strip()
            # 提取JSON部分
            import re
            start_idx = response.find('{')
            end_idx = response.rfind('}')
            if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                json_response = response[start_idx:end_idx + 1]
                llm_decision = json.loads(json_response)
                selected_methods = llm_decision.get('selected_methods', selected_methods)
                log(f"LLM决定的评估方法: {selected_methods}")
            else:
                log(f"无法提取LLM决策的JSON，使用默认评估方法: {selected_methods}")
        except Exception as e:
            log(f"LLM决策失败，使用默认评估方法: {e}")
            log(f"使用默认评估方法: {selected_methods}")
        
        # 确保选择的方法都是有效的
        selected_methods = [method for method in selected_methods if method in evaluation_methods]
        
        # 并行执行评估
        results = {}
        parsed_results = {}
        
        with ThreadPoolExecutor() as executor:
            # 提交所有评估任务
            future_to_method = {
                executor.submit(evaluation_methods[method], current_plot): method
                for method in selected_methods
            }
            
            # 收集评估结果
            for future in future_to_method:
                method = future_to_method[future]
                try:
                    result = future.result()
                    results[method] = result
                    # 解析评估结果
                    parsed_results[method] = self._parse_evaluation_result(result)
                    log(f"{method} 评估完成")
                except Exception as e:
                    log(f"{method} 评估失败: {e}")
                    error_msg = f"评估失败: {str(e)}"
                    results[method] = error_msg
                    parsed_results[method] = {"problem": error_msg, "suggestion": error_msg}
        
        # 整合评估结果
        from utils.llm_call import llm_call
        
        # 构建包含上一次评估总结的整合提示词
        integration_prompt = f"""
        你是一位专业的时间线评估整合专家，请根据以下解析后的评估结果和时间线数据，生成一个综合的评估报告。
        
        评估结果（包含问题和建议）：
        {json.dumps(parsed_results, ensure_ascii=False, indent=2)}
        
        时间线数据：
        {json.dumps(current_plot, ensure_ascii=False, indent=2)}
        
            
        
        整合要求：
        1. 综合所有评估结果，提取关键问题和建议
        2. 识别评估结果中的共同点和矛盾点
        3. 生成优先级排序的改进建议
        4. 参考上一次的评估总结，确保评估的连续性和一致性
        
        输出格式：
        使用文本格式，包含以下部分：
        1. 关键问题：使用<problems>标签包裹，列出所有评估中发现的关键问题
        2. 改进建议：使用<suggestions>标签包裹，按优先级排序的改进建议
        """
        
        response = llm_call(integration_prompt).strip()
        log(f"整合评估结果: {response}")
        # 提取整合结果
        import re
        problems_match = re.search(r'<problems>(.*?)</problems>', response, re.DOTALL)
        suggestions_match = re.search(r'<suggestions>(.*?)</suggestions>', response, re.DOTALL)
        
        problems = problems_match.group(1).strip() if problems_match else ""
        suggestions = suggestions_match.group(1).strip() if suggestions_match else ""
        
        # 构建整合结果
        integrated_result = {
            "problems": problems,
            "suggestions": suggestions,
            "detailed_results": results,
            "parsed_results": parsed_results
        }
        
        # 生成评估总结并更新缓存
        evaluation_summary = f"""
        评估总结：
        关键问题：{problems[:100]}...
        改进建议：{suggestions[:100]}...
        """
        
        self.previous_evaluation_summary = evaluation_summary
        log("\n=== 评估总结已更新到缓存 ===")
        
        log("\n=== 评估规划执行完成 ===")
        
        return integrated_result