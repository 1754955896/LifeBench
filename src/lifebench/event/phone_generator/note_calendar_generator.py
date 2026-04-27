"""
笔记日历操作生成器模块
负责生成日历和笔记数据
"""

import json
import random
from typing import List, Dict
from src.lifebench.utils.llm_call import llm_call, llm_call_j


class NoteCalendarOperationGenerator:
    """
    笔记日历操作生成器
    根据事件信息生成日历和笔记数据
    """
    
    def __init__(self, random_seed: int = 42):
        """初始化生成器（设置随机种子确保可复现）"""
        random.seed(random_seed)
        # 核心约束：日历 + 笔记总数≤4（不常用操作，仅重要事件生成）
        self.max_total_output = 4
        # 非事件相关笔记额外约束：每天最多 1 个
        self.max_unrelated_note = 1
        # 定义事件类型优先级（确保重要事件优先生成）
        self.event_priority = [
            "重要事件 - 出行预定", "重要事件 - 重要会议",
            "重要事件 - 医疗预约", "重要事件 - 旅行计划",
            "日常事件 - 购物", "日常事件 - 普通社交",
            "非事件相关 - 兴趣爱好"
        ]
        # 明确概率范围（贴合"不常用"设定，整体调低概率）
        self.default_prob_ranges = {
            "calendar": (60, 85),  # 极重要事件才生成，概率低于之前
            "note_related": (50, 70),  # 事件相关笔记概率降低
            "note_unrelated": (10, 20),  # 非事件相关笔记（诗词/知识点）概率 10%-20%
            "calendar_invalid": 0,  # 非重要事件日历概率 0%
            "note_related_daily": (0, 5)  # 日常事件笔记概率 0%-5%
        }
    
    def parse_llm_prob_json(self, llm_json_str: str) -> List[Dict]:
        """
        解析 LLM 返回的 JSON 数据
        
        Args:
            llm_json_str: LLM 返回的字符串
            
        Returns:
            解析后的事件列表
        """
        try:
            start_idx = llm_json_str.find('[')
            end_idx = llm_json_str.rfind(']')
            if start_idx == -1 or end_idx == -1 or start_idx >= end_idx:
                print("错误：未找到有效的 JSON 数组（缺少 [] 包裹）")
                return []

            core_json_str = llm_json_str[start_idx:end_idx + 1].strip()
            events = json.loads(core_json_str)
            return events
        except json.JSONDecodeError as e:
            print(f"JSON 解析失败：位置{e.pos}，原因{e.msg}")
            return []
        except Exception as e:
            print(f"解析异常：{str(e)}")
            return []
    
    def _build_prob_modeling_prompt(self, daily_events: List[Dict], persona) -> str:
        """
        第一步 Prompt：概率建模（仅输出事件 ID 和生成概率）
        
        Args:
            daily_events: 当日事件列表
            persona: 用户画像
            
        Returns:
            概率建模 prompt 字符串
        """
        return f'''
请基于用户提供的当日事件和个人画像，逐事件分析生成概率，仅输出事件 ID 和各类操作的生成概率，不涉及具体内容。
核心规则：日历和笔记是不常用操作，仅重要事件才生成，总数一天不超过 6 个。

### 一、概率定义与约束
#### 1. 事件分类（严格对应）
- 重要事件：出行预定、极度重要会议、医疗预约、旅行计划、极度重要聚会，重要节点（婚礼、考试）
- 独特事件：一次考试，一次会议，一次航班等
- 信息事件：涉及复杂信息/步骤的各类事件，涉及较多知识点的事件，会议/课程要点记录，攻略想法等
- 日常事件：普通社交、购物、休闲等非重要场景
- 非事件相关：与当日事件无关，基于个人兴趣的记录或个人事务的记录（如诗词、知识点）

#### 2. 各类生成概率规则（必须严格遵循）
- 日历（calendar）：
  - 重要事件：80%-90%（按重要度微调，出行预定/核心会议最高）
  - 独特事件：30%-60%
  - 日常事件/非事件相关：0%（强制不生成）
- 事件相关笔记（note_related）：
  - 重要事件：60%-80%（记录待办/要点/注意事项）
  - 信息事件：30%-60%
  - 独特事件：0%-10%
  - 日常事件：0%-5%（概率极低，几乎不生成）
- 非事件相关笔记（note_unrelated）：
  - 定义：与当日事件无关，基于用户兴趣的记录（如读到的诗词、咖啡知识点）
  - 概率：10%-15%（每天最多 1 个）其他事件都是 0%。
  - 无兴趣关联：0%

#### 3. 个人画像适配
- 非事件相关笔记需匹配用户兴趣（如诗词、咖啡、多肉）
- 整体概率需贴合"不常用"习惯，避免高概率生成

#### 4. 其他约束
大部分事件不生成笔记或日历，甚至可以所有事件都不生成。只关注重要事件。

### 二、输出字段要求（仅保留以下 6 个字段，无额外内容）
每个事件必须包含：
- event_id：沿用原事件 ID；非事件相关填"0"
- event_name：事件名称；非事件相关填兴趣主题（如"古典诗词记录"）
- event_type：分类格式「类型 - 子类型」（如"重要事件 - 出行预定"、"非事件相关 - 兴趣爱好"）
- calendar_prob：日历生成概率（百分比字符串，如"80%"）
- note_related_prob：事件相关笔记生成概率（百分比字符串）
- note_unrelated_prob：非事件相关笔记生成概率（百分比字符串）

### 三、输出格式要求
仅输出 JSON 数组，无任何注释、额外文本或代码块。示例：
[
  {{
    "event_id": "1",
    "event_name": "G1234 次列车北京→上海",
    "event_type": "重要事件 - 出行预定",
    "calendar_prob": "85%",
    "note_related_prob": "65%",
    "note_unrelated_prob": "0%"
  }},
  {{
    "event_id": "0",
    "event_name": "古典诗词记录",
    "event_type": "非事件相关 - 兴趣爱好",
    "calendar_prob": "0%",
    "note_related_prob": "0%",
    "note_unrelated_prob": "10%"
  }}
]

请基于<当日事件>：{daily_events}、<个人画像>：{persona}，严格按上述要求输出概率建模结果。
'''
    
    def _validate_format_only(self, data: Dict) -> tuple:
        """
        仅校验笔记日历数据格式（不涉及合理性），并删除多余字段
        
        Args:
            data: 单条笔记或日历数据
            
        Returns:
            (is_valid: bool, error_message: str)
        """
        try:
            # 1. 根据 type 校验必填字段并删除多余字段
            if data.get("type") == "calendar":
                required_fields = [
                    "event_id", "type", "title", "description", 
                    "start_time", "end_time", "datetime"
                ]
                missing_fields = [f for f in required_fields if f not in data]
                if missing_fields:
                    return False, f"日历数据缺少必填字段: {missing_fields}"
                
                # 删除多余字段
                extra_fields = [k for k in data.keys() if k not in required_fields]
                for field in extra_fields:
                    del data[field]
                
            elif data.get("type") == "note":
                required_fields = [
                    "event_id", "type", "title", "content", 
                    "datetime"
                ]
                missing_fields = [f for f in required_fields if f not in data]
                if missing_fields:
                    return False, f"笔记数据缺少必填字段: {missing_fields}"
                
                # 删除多余字段
                extra_fields = [k for k in data.keys() if k not in required_fields]
                for field in extra_fields:
                    del data[field]
            else:
                return False, f"type 取值错误: {data.get('type')}，应为'calendar'或'note'"
            
            # 2. 校验时间格式
            from datetime import datetime
            try:
                dt = datetime.strptime(data["datetime"], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return False, f"datetime 格式错误: {data['datetime']}，应为 'YYYY-MM-DD HH:MM:SS'"
            
            # 3. 校验年份是否为2025年
            if dt.year != 2025:
                return False, f"年份不是2025年: {data['datetime']}，实际年份为 {dt.year}"
            
            # 4. 如果是日历，校验 start_time 和 end_time
            if data.get("type") == "calendar":
                try:
                    start_dt = datetime.strptime(data["start_time"], "%Y-%m-%d %H:%M:%S")
                    end_dt = datetime.strptime(data["end_time"], "%Y-%m-%d %H:%M:%S")
                    
                    # 校验 end_time 不早于 start_time
                    if end_dt < start_dt:
                        return False, f"end_time 早于 start_time: {data['start_time']} -> {data['end_time']}"
                    
                    # 校验 start_time 年份
                    if start_dt.year != 2025:
                        return False, f"start_time 年份不是2025年: {data['start_time']}"
                    
                    # 校验 end_time 年份
                    if end_dt.year != 2025:
                        return False, f"end_time 年份不是2025年: {data['end_time']}"
                except ValueError as e:
                    return False, f"start_time 或 end_time 格式错误: {str(e)}"
            
            return True, ""
            
        except Exception as e:
            return False, f"格式校验异常: {str(e)}"
    
    def phone_gen_noteandcalendar(self, date, contact, file_path, c):
        """
        生成笔记和日历数据的主方法
        
        Args:
            date: 日期
            contact: 联系人列表
            file_path: 文件路径
            c: 结果列表
            
        Returns:
            生成的笔记和日历数据列表
        """
        from src.lifebench.event.phone_data_gen import extool
        
        c = []
        res1 = extool.filter_by_date(date)
        res = []
        for i in range(len(res1)):
            if "-" in res1[i]['event_id']:
                continue
            res.append(res1[i])
            print(res1[i]['event_id'])
        prompt = self._build_prob_modeling_prompt(res, extool.persona)
        a = llm_call_j(prompt)
        print(a)
        a = self.parse_llm_prob_json(a)
        
        def sample(p1):
            prob = int(p1.strip('%'))
            return random.random() < max(0, min(100, prob)) / 100
        
        instruction = ""
        f = True
        for item in a:
            event_id = item['event_id']
            event_name = item['event_name']
            event_type = item['event_type']

            p1 = item['calendar_prob']
            p2 = item['note_related_prob']
            p3 = item['note_unrelated_prob']

            if sample(p1):
                instruction += f'''\n--------------------------------------------------\n
                    'event_id':'{event_id}',
                    'event_name':'{event_name}',
                    'phone operation':'calendar',
                '''
            elif sample(p2):
                instruction += f'''\n--------------------------------------------------\n
                                    'event_id':'{event_id}',
                                    'event_name':'{event_name}',
                                    'phone operation':'note'
                                '''
            if sample(p3) and f:
                instruction += f'''\n--------------------------------------------------\n
                                                    'event_id':'{event_id}',,
                                                    'event_name':'{event_name}',
                                                    'phone operation':'note',
                                                    'special':"基于画像生成用户与事件无关的笔记内容，如兴趣、新闻、知识等。"
                                                '''
                f = False

        template = '''
请基于用户提供的{{生成项清单}}、{{当日事件}}和{{个人画像}}，生成具体的手机日历与笔记数据，数据总条目不超过 3 个，严格按照**{{生成项清单}}**提供的指令生成，若其为空则不生成，输出空数组。
核心约束：1. 仅生成清单中的项目，不额外新增，若清单中数目超过 4 则挑选最重要的 4 个生成；2. 若清单为空则直接输出空数组 []；3. 内容高保真、结构化；4. 无任何双引号。

### 零、日期约束（**最高优先级**）
- **当前关注的事件日期：{date}**
- **生成原则**：请严格基于此日期进行数据生成，所有时间字段（start_time、end_time、datetime）的日期部分应以此日期为基准
- **跨天处理**：对于某些需跨天的数据（如长途出行、跨夜会议等），可以在此日期的基础上往前或往后选择合理的相邻日期，但必须严格围绕此日期展开，不得偏离过远

### 零点五、事件来源约束（**强制要求**）
- **严格基于当日事件**：所有生成的日历和事件相关笔记（note_related）必须严格基于【五、今日事件背景参考】中提供的事件信息
- **禁止编造事件**：不得生成与当日事件无关的虚构事件，event_id 必须对应真实存在的当日事件
- **内容一致性**：生成的 title、description、content 等内容必须与当日事件的描述保持一致，准确反映事件的核心信息
- **非事件笔记例外**：只有 item_type=note_unrelated 的非事件相关笔记可以基于个人画像生成与事件无关的内容（如兴趣、知识、新闻等）

### 一、个人画像适配（确保内容贴合用户习惯）
用户信息：
- 非事件相关笔记（note_unrelated）：基于画像生成用户与事件无关的笔记内容，如兴趣、新闻、知识等，或是某事的总结，内容真实自然
- 事件相关笔记（note_related）：聚焦核心信息（待办/要点/注意事项），不冗余
- 日历（calendar）：仅保留关键凭证和时间信息，来源明确
- **内容质量原则**：description 和 content 字段应与事件描述保持一致，合理简洁，同时包含完整的核心信息，准确反映事件内容

### 二、字段规则（严格遵循，缺一不可）
#### （一）日历日程（item_type=calendar）
- event_id：**必须来自生成项清单中的 event_id**，不得自行生成
- type：固定"calendar"
- title：简洁明确（场景 + 核心信息），例："G1234 次列车（北京 - 上海）"
- description：简洁明确，完整反映事件核心信息，可包含一些细节，包含"时间 + 核心要素 + 来源"，例："G1234 次列车（北京南站→上海虹桥站），08:00 发车，预定码 E12345，凭身份证检票，来源 12306"
- start_time：事件时间（格式 YYYY-MM-DD HH:MM:SS）
- end_time：出行类=start_time；会议/预约类=合理时长后（如 1.5 小时）
- datetime：创建该日程数据的时间，格式 YYYY-MM-DD HH:MM:SS，合理确定

#### （二）事件相关笔记（item_type=note_related）
- event_id：**必须来自生成项清单中的 event_id**，不得自行生成
- type：固定"note"
- title：事件名称 + 记录类型，例："Q4 项目会议待办清单"
- content：简洁明确，完整反映事件核心信息，可包含一些细节，结构化分点，例："一、会议前准备：1. 预算报表；2. PPT 优化；二、核心议题：1. 资源调配；2. 节点确认"
- datetime：创建该笔记的时间，合理确定（格式 YYYY-MM-DD HH:MM:SS）

#### （三）非事件相关笔记（item_type=note_unrelated）
- event_id：固定为 0
- type：固定"note"
- title：兴趣主题 + 记录类型，例："喜爱诗词记录"、"手冲咖啡知识点"
- content：简洁明确，完整反映事件核心信息，结构化分点，例："一、诗句：人生若只如初见；二、作者：纳兰性德；三、赏析：情感细腻，适合文案灵感"
- datetime：当日合理时间（8:00-21:00，格式 YYYY-MM-DD HH:MM:SS）


### 三、生成项清单（**仅生成以下项目，不新增**）
{instruct}

### 四、输出格式要求
仅输出 JSON 数组，严格遵循下面的格式，不添加任何额外文本/注释/代码块。示例：
[
{{"type":"calendar","event_id":"1","title":"G1234 次列车（北京 - 上海）","description":"G1234 次列车（北京南站→上海虹桥站），08:00 发车，预定码 E12345，凭身份证检票，来源 12306","start_time":"2023-10-05 08:00:00","end_time":"2023-10-05 08:00:00","datetime":"2023-10-04 15:30:00"}},
{{"type":"note","event_id":"2","title":"Q4 项目会议待办清单","content":"一、会议前准备：1. 整理 Q4 预算明细；2. 优化项目进度 PPT；3. 预约会议室设备；二、核心议题：1. 预算审批；2. 资源调配；3. 里程碑节点确认","datetime":"2023-10-08 13:45:00"}}
]

### 五、今日事件背景参考
{event}

### 六、个人画像
{persona}
'''
        prompt = template.format(date=date, instruct=instruction, event=res, persona=extool.persona)
        res = llm_call_j(prompt)
        print(res)
        res = self.remove_json_wrapper(res, "array")
        data = json.loads(res)
        
        # ========== 新增：格式校验环节 ==========
        print(f"\n开始笔记日历数据格式校验，共 {len(data)} 条数据...")
        
        valid_data = []
        for idx, item in enumerate(data):
            format_valid, format_error = self._validate_format_only(item)
            if format_valid:
                valid_data.append(item)
            else:
                print(f"  [格式错误] 索引 {idx}, event_id={item.get('event_id')}: {format_error}，抛弃该数据")
        
        c += valid_data
        print(f"\n最终保留 {len(c)} 条笔记日历数据\n")
        # ================================================
        print(c)
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
