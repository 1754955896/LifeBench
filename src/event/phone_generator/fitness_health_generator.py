"""
运动健康操作生成器模块
负责生成运动和健康数据
"""

import json
import random
from typing import List, Dict
from utils.llm_call import llm_call


class FitnessHealthOperationGenerator:
    """
    运动健康操作生成器
    根据事件信息生成运动和健康数据
    """
    
    def __init__(self, random_seed: int = 42):
        """初始化运动健康数据生成器"""
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
    
    def phone_gen_fitness_health(self, date, contact, file_path, c):
        """
        生成指定日期的运动健康数据
        
        Args:
            date: 日期
            contact: 联系人列表
            file_path: 文件路径
            c: 结果列表
            
        Returns:
            生成的运动健康数据列表
        """
        from event.phone_data_gen import extool
        
        c = []
        daily_events = extool.filter_by_date(date)
        status = extool.getstatus(date)
        status['event'] = {}
        
        template = '''
        请基于用户提供的{{当日事件}}和{{当日状态数据}}{{个人画像}}，生成完整的一天运动健康数据。生成需严格遵循以下格式和要求：
        
        ## 输出格式要求
        输出严格为以下 JSON 格式，包含所有字段，字段值符合数据类型和范围要求，逻辑自洽。
        
        {{
          "日期": "YYYY-MM-DD",
          "城市": "北京/上海/深圳",
          "日常活动": {{
            "步数": ">=0 步",
            "距离": ">=0 公里",
            "热量": ">=0 千卡",
            "锻炼时长": ">=0 分钟",
            "活动小时数": ">=0 小时"
          }},
          "跑步": {{
            "运动类型": "户外跑步/室内跑步/越野跑",
            "运动时间": "YYYY/MM/DD/HH:mm:ss-YYYY/MM/DD/HH:mm:ss",
            "天气": "晴/雨/阴/雪/多云/雾/霾",
            "距离统计": ">=0 公里",
            "平均心率": "30-220 次/分钟",
            "平均步频": "0-240 步/分钟",
            "累计爬升": ">=0 米",
            "累计下降": ">=0 米",
            "平均配速": "MM 分 SS 秒/公里",
            "最佳配速": "MM 分 SS 秒/公里",
            "总步数": ">=0 步",
            "消耗热量": ">=0 千卡"
          }},
          "骑行": {{
            "运动类型": "户外骑行/室内骑行",
            "运动时间": "YYYY/MM/DD/HH:mm:ss-YYYY/MM/DD/HH:mm:ss",
            "天气": "晴/雨/阴/雪/多云/雾/霾",
            "距离统计": ">=0 公里",
            "平均速度": "0-60 公里/小时",
            "平均心率": "30-220 次/分钟",
            "平均踏频": "0-200 转/分钟",
            "平均功率": ">=0 瓦",
            "最佳速度": "0-60 公里/小时",
            "最大踏频": "0-200 转/分钟",
            "消耗热量": ">=0 千卡"
          }},
          "步行": {{
            "运动类型": "户外步行/室内步行/徒步",
            "运动时间": "YYYY/MM/DD/HH:mm:ss-YYYY/MM/DD/HH:mm:ss",
            "天气": "晴/雨/阴/雪/多云/雾/霾",
            "距离统计": ">=0 公里",
            "平均心率": "30-220 次/分钟",
            "平均步频": "0-200 步/分钟",
            "步数统计": ">=0 步",
            "平均配速": "MM 分 SS 秒/公里",
            "最佳配速": "MM 分 SS 秒/公里",
            "消耗热量": ">=0 千卡"
          }},
          "睡眠": {{
            "入睡时间": "HH:mm:ss (昨日)/HH:mm:ss",
            "出睡时间": "HH:mm:ss",
            "全部睡眠时长": ">=0 分钟",
            "浅睡时长": ">=0 分钟",
            "深睡时长": ">=0 分钟",
            "快速眼动时长": ">=0 分钟",
            "清醒时长": ">=0 分钟",
            "清醒次数": ">=0 次",
            "深睡连续性得分": "0-100 分",
            "睡眠得分": "0-100 分",
            "零星小睡时长": ">=0 分钟"
          }},
          "心率统计": {{
            "平均心率": "30-220 次/分钟",
            "平均静息心率": "30-120 次/分钟",
            "心率变异性": "0-200 毫秒"
          }},
          "体温统计": {{
            "平均体温": "34.0-42.0 摄氏度"
          }},
          "血糖统计": {{
            "平均血糖水平": "1.0-33.0mmol/L"
          }},
          "体重": {{
            "体重": "10.0-250.0 千克",
          }},
          "压力": {{
            "压力得分": "1-99 分"
          }},
          "饮食记录": {{
            "摄入热量": "1-9999 千卡"
          }},
          "用户交互事件": [
            {{
              "时间": "YYYY/MM/DD HH:mm",
              "描述": "事件概述（尽量简洁，只关注主要事件）"
            }}
          ],
          "summarized_info":"对今日运动健康数据的描述，包括起床时间，睡觉时间，体重和当日运动量"
        }}
        
        ## 生成要求
        1. 所有字段必须填充符合范围要求的具体数值，不能保留模板中的">=0 步"等占位符
        2. 数据必须与当日事件和个人画像相符（例如，如果当日有跑步事件，跑步数据应反映该活动）
        3. 时间字段必须与指定日期一致
        4. 各指标之间需逻辑自洽（例如：步数与距离成正比，消耗热量与活动量成正比）
        5. 运动数据（跑步、骑行、步行）如果当天没有对应活动，可以设置为合理的基础值
        6. 城市字段应与个人画像中的常居地一致
        7. 用户交互事件应包含与运动健康相关的操作（如查看运动数据、设置目标等）
        
        ## 输入数据
        <当日状态数据>: {status}
        <当日事件>: {daily_events}
        <个人画像>: {persona}
        
        请直接输出符合要求的 JSON 数据，不要添加任何额外文本、注释或说明。
        '''
        
        prompt = template.format(daily_events=daily_events, persona=extool.persona, status=status)
        print("运动健康数据生成 prompt:", prompt)
        
        response = llm_call(prompt)
        print("LLM 响应:", response)
        
        response = self.remove_json_wrapper(response, 'object')
        try:
            fitness_data = json.loads(response)
            c.append(fitness_data)
        except json.JSONDecodeError as e:
            print(f"运动健康数据解析失败：{str(e)}")
        
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
