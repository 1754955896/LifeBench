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
from event.template_s import *
import re
import holidays  # 需安装：pip install holidays


class EventTree:
    def __init__(self, persona: str):
        self.persona = persona
        self.decompose_schedule = []  # 最终分解结果（完整树形结构）
        self.schema = {
"运动":["游泳",
        "健身锻炼",
        "跑步",
        "骑行",
        "户外步行",
        "武术",
        "舞蹈",
        "羽毛球",
        "棒球",
        "滑雪",
        "足球",
        "篮球",
        "轮滑",
        "户外探险",
        "健美操",
        "漫步机",
        "射箭",
        "羽毛球",
        "芭蕾舞",
        "沙滩足球",
        "沙滩排球",
        "肚皮舞",
        "冬季两项",
        "BMX自行车",
        "搏击操",
        "保龄球",
        "拳击",
        "闭气测试",
        "闭气训练",
        "蹦极",
        "皮划艇",
        "核心训练",
        "板球",
        "越野滑雪",
        "Crossfit",
        "冰壶",
        "飞镖",
        "自由潜水",
        "躲避球",
        "龙舟",
        "漂流",
        "椭圆机",
        "电子竞技",
        "击剑",
        "钓鱼","跳伞",
        "双杠",
        "跑酷",
        "体能训练",
        "普拉提",
        "操场赛跑",
        "广场舞",
        "台球",
        "泳池游泳",
        "赛车",
        "攀岩",
        "轮滑",
        "划船机",
        "赛艇",
        "橄榄球",
        "帆船",
        "水肺潜水",
        "体感运动",
        "藤球",
        "毽球",
        "单杠",
        "滑板",
        "滑冰",
        "滑雪",
        "滑雪橇",
        "单板滑雪",
        "雪地摩托",
        "垒球",
        "动感单车",
        "壁球",
        "爬楼",
        "踏步机",
        "街舞",
        "力量训练",
        "桨板冲浪",
        "冲浪",
        "秋千",
        "乒乓球",
        "跆拳道",
        "太极拳",
        "网球",
        "越野跑",
        "铁人三项",
        "拔河",
        "排球",
        "瑜伽"],
"工作": [
"出差",
"上班通勤",
"下班通勤",
"办公",
"会议研讨",
"出差 - 那年今日",
"请假",
"加班",
"工作总结",
"工作交流",
"培训",
"报销"
],
"社交动作": [
"与某人通话",
"与某人视频通话",
"向某人发送即时消息",
"接收某人发送的即时消息",
"向某人发送邮件",
"接收某人发送的工作邮件",
"邀请某人参加日历事件",
"接受某人发起的日历邀请",
"与某人同处一地（短时）",
"与某人参加同一会议",
"与某人参加同一培训 / 讲座",
"在通讯录中新增联系人",
"更新某人联系信息",
"删除 / 屏蔽某人"
],
"人际交往": [
"参加聚餐",
"参加婚礼",
"参加生日派对",
"参加公司团建",
"参加社区活动",
"拜访他人住所",
"探望住院人员",
"参加节日庆典",
"参加宗教仪式",
"参加慈善活动",
"参加政治集会",
"参加亲子活动",
"陪同前往学校 / 培训机构",
"组织活动",
"预订餐厅 / 场地",
"宠物照料"
],
"教育": [
"作业",
"会议研讨",
"课程",
"请假",
"上班通勤",
"下班通勤",
"背单词",
"预约考试",
"参加考试",
"成绩查询"
],
"便捷生活": [
"家政",
"政务和公共服务",
"生活缴费",
"跑腿代办",
"3C 数码维修",
"行李寄存"
],
"财务管理": [
"银行入账",
"银行出账",
"金融 app 入账",
"金融 app 出账",
"记账",
"理财",
"保险",
"支付订单",
"房产装修",
"房产交易",
"汽车交易"
],
"健康管理": [
"运动记录",
"体检",
"挂号",
"查看电子病历或检查报告",
"服药",
"心理咨询",
"睡眠管理",
"饮食管理",
"精神健康管理"
],
"出行旅游": [
"旅游",
"行走",
"跑",
"骑车",
"乘飞机",
"乘火车",
"乘地铁",
"开车",
"乘车",
"乘交通工具",
"行程规划",
"购票",
"检票",
"退票",
"改签",
"景点浏览",
"购物",
"逛街",
"城市漫游",
"出海游船",
"露营",
"度假村放松",
"酒店休息",
"就餐",
"出发",
"城市切换",
"达到",
"城市旅游",
"旅程",
"游玩主题乐园",
"参观动物园",
"参观博物馆",
"参观美术馆",
"参观海洋馆",
"节假日回乡",
"居家拜访",
"扫墓",
"探亲"
],
"休闲娱乐": [
"看演唱会",
"看话剧",
"看音乐剧",
"看展览",
"看脱口秀",
"看相声",
"看演唱会",
"看音乐会",
"看音乐节",
"看戏曲",
"看电竞赛事",
"看舞蹈",
"看体育赛事",
"看魔术",
"看电影",
"看亲子演出",
"划船",
"射击射箭",
"溜冰",
"马术",
"钓鱼",
"按摩足疗",
"洗浴汗蒸",
"密室逃脱",
"游戏厅",
"网吧",
"采摘农家乐",
"撸宠",
"K 歌",
"酒吧",
"轰趴",
"剧本杀",
"逛街",
"电子游戏",
"做 SPA",
"桌游",
"茶馆棋牌",
"DIY 手工"
]
}
        # 定义外部事件类别schema
        self.event_type_schema = {
            "Career": self.schema["工作"]+self.schema["社交动作"]+self.schema["人际交往"]+self.schema["教育"]+self.schema["财务管理"],
            "Education": self.schema["工作"]+self.schema["社交动作"]+self.schema["人际交往"]+self.schema["教育"],
            "Relationships": self.schema["工作"]+self.schema["社交动作"]+self.schema["人际交往"]+self.schema["休闲娱乐"],
            "Family&Living Situation": self.schema["工作"]+self.schema["社交动作"]+self.schema["人际交往"]+self.schema["教育"]+self.schema["便捷生活"]+self.schema["财务管理"],
            "Personal Life": self.schema["出行旅游"]+self.schema["休闲娱乐"]+self.schema["运动"],
            "Finance": self.schema["工作"]+self.schema["财务管理"]+self.schema["社交动作"]+self.schema["人际交往"],
            "Health": self.schema["社交动作"]+self.schema["人际交往"]+self.schema["健康管理"]+self.schema["运动"],
            "Unexpected Events": self.schema["工作"]+self.schema["社交动作"]+self.schema["人际交往"]+self.schema["便捷生活"]+self.schema["财务管理"]+self.schema["健康管理"],
            "Other": self.schema["工作"]+self.schema["社交动作"]+self.schema["人际交往"]+self.schema["教育"]+self.schema["便捷生活"]+self.schema["财务管理"],
        }
        
        # 第一层分解模板：原事件→阶段事件/原子事件
        self.template_level1_1 = '''
            基于以下待分解事件，完成推理、扩展、分解，并直接输出子事件JSON数组（无需额外分析文本），目标是将事件分解为粒度小于一天的原子事件：
            
            1. 事件扩展：可参考事件描述进行分解，但原事件可能不完整，不具体，甚至不合理，需合理推理**前置（准备/规划/预定）、后续（收尾/影响）及相关事件**，补充后使其完整丰富。
            2. 粒度与阶段分解规则：
               - 阶段事件：针对跨度长（超过7天）、流程复杂、重要性高的原事件，可拆分为「阶段性子事件」（如项目立项→执行→验收、旅行准备→行程执行→收尾），等后续再分解为粒度为一天的原子事件。
                 - 阶段事件特征：date格式为跨天区间（如["2025-01-01至2025-01-15"]），覆盖一个完整阶段的时间范围，decompose=1，表示其后续将被递归分解。
                 - 阶段划分原则：按「时间顺序+流程逻辑」拆分，每个阶段聚焦一个核心目标，避免阶段重叠或遗漏。注意，如果原事件时间范围小于一天，则不用拆分为阶段事件，直接拆分为原子事件。
               - 原子事件：粒度≤1天，date格式为当天日期（如["2025-01-01"]）。具体可执行，发生时间可超出原事件起止时间；多次发生需拆分为多个日期（如["2025-01-01","2025-02-01"]而非["2025-01-01至2025-02-01"]），decompose=0（无需继续分解）。
               - **重要规则：对于发生在同一日的事件，尽量不要拆分为不同的原子事件。同一日的所有动作应在一个原子事件中描述，避免过度拆分。**
               - **如果输入的父事件时间跨度为一天，则考虑是否有相关的不在这一天发生的事件（如提前预定），若全在这一天发生，则返回一个原子事件即可，内容为原事件更详细的描述。注意不要为了分解而分解，除了预定买票类需提前做的事件，否则不需要为跨度为一日的事件合成额外的事件，直接输出一个原子事件即可。**
               - **注意，不可以输出空数组，如果原事件很简单，你也要分解为不同的原子事件，或推理相关后续/前置事件，只不过都为粒度小于1天的原子事件，decompose=0即可。**
            3. 递归分解约束：
               - 分解的子事件数量**严格控制在10个以内**（建议2-7个，避免过度拆分）。
               - 事件ID中的'-'代表层级，每多一个'-'表示多一层分解。
               - **如果你分解出的子事件为阶段事件，date格式为跨天区间（如["2025-01-01至2025-01-15"]），则其decompose一定为1。**
               - **如果分解出的子事件为原子事件，date格式为当天日期（如["2025-01-01"]），则其decompose一定为0。**
            4. 时间范围规则：
               - 第一层分解的子事件时间范围**可以超出**父事件规定的时间范围（允许前置准备(如买票、预定)和后续收尾事件）。
               - 同一父事件的子事件时间范围应避免重叠（除非有明确的并行执行逻辑）。
            5. 分解策略：
               - 分解需多样化：并非所有事件都需经过准备/规划流程，同一类事件在不同场景下流程可不同。事件的发展可能并非线性，可能存在波动等情况。
               - 时间分布：无需均匀分布事件，按真实场景合理安排（持续时间长不代表每天都有相关动作）；阶段事件的时间区间需覆盖原事件核心流程，原子事件可穿插在阶段内。
               - **所有子事件应尽量为不同日期，同一日的所有动作在一个原子事件中描述，不要拆分。**
            6. 合理性优化：可修改原事件不合理信息，避免事件间安排冲突，确保描述真实丰富；阶段事件的时间区间需衔接自然，无明显断层。
            
            --- 输出格式强制要求 ---
            1. **仅返回JSON数组（直接子事件列表），以[]开头结尾，无任何额外文本（包括分析、注释、代码块标记）。**
            2. 每个子事件必须包含以下字段（缺一不可，语法严格正确）：
               - event_id：格式为「父事件ID-序号」（如父ID=1，子事件ID=1-1、1-2），确保层级关联。
               - name：事件名称（简洁明了）。
               - date：时间数组（单个日期/多个日期，粒度≤1天；跨天事件用"至"连接，如["2025-01-01至2025-01-03"]）。
               - type：
                 * 对于需要继续分解的事件（decompose=1）：取值范围（必选其一）：Career、Education、Relationships、Family&Living Situation、Personal Life、Finance、Health、Unexpected Events、Other。
                 * 对于原子事件（decompose=0）：请从以下预定义的底层事件类别中选择，若没有合适的预定义类别，可自行生成合理的详细类别描述，不同于decompose=1的事件。预定义的底层事件类别：【
                   {atomic_categories}】
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
            [{{"event_id":"1-1","name":"旅行前准备","date":["2024-12-15至2024-12-30"],"type":"Personal Life","description":"准备欧洲旅行所需的签证、机票、酒店预订等","participant":[{{"name":"张三","relation":"自己"}}],"location":"北京市-家中","decompose":1}},{{"event_id":"1-2","name":"欧洲旅行行程执行","date":["2025-01-01至2025-01-15"],"type":"Personal Life","description":"按照计划在欧洲各国旅行","participant":[{{"name":"张三","relation":"自己"}}],"location":"欧洲各国","decompose":1}},{{"event_id":"1-3","name":"旅行后整理","date":["2025-01-16"],"type":"物品购买","description":"整理旅行照片和购买的纪念品","participant":[{{"name":"张三","relation":"自己"}}],"location":"北京市-家中","decompose":0}}]
            
            -- 用户画像 --
            {persona}
            
            -- 待分解事件 --
            {parent_event}
        '''
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
        self.template_level2_1 = '''
            基于以下待分解阶段事件和背景信息，完成推理、分解，并直接输出原子事件JSON数组（无需额外分析文本）：
            
            1. 原子事件要求：粒度≤1天，具体可执行，decompose=0（无需继续分解）。
            2. 粒度与阶段分解规则：
               - 当前为第二层分解（current_depth≥1），必须分解为原子事件（粒度为天）。
               - **原子事件时间跨度不超过1天，多次发生需拆分为多个日期（如["2025-01-01","2025-02-01"]而非["2025-01-01至2025-02-01"]）。**
               - **重要规则：对于发生在同一日的事件，尽量不要拆分为不同的原子事件。同一日的所有动作应在一个原子事件中描述，避免过度拆分。**
               - **如果输入的父事件时间跨度为一天，则拆解并返回一个原子事件即可，内容为原事件更详细的描述。**
            3. 递归分解约束：
               - 每一层分解的子事件数量**严格控制在10个以内**（建议2-6个，避免过度拆分）。
               - 事件ID中的'-'代表层级，每多一个'-'表示多一层分解。
            4. 时间范围规则：
               - 第二层分解的子事件时间范围**必须严格包含**在父事件规定的时间范围内（不允许超出）。
               - 同一父事件的子事件时间范围应避免重叠，确保时间安排合理。
               - 原子事件时间跨度不超过1天。
            5. 分解策略：
               - 基于背景信息，确保分解的原子事件与整体事件流程协调一致。
               - 按真实场景合理安排时间分布，确保事件流程连贯。
               - 时间分布：无需均匀分布事件，按真实场景合理安排（持续时间长不代表每天都有相关动作）；原子事件需在父事件时间范围内合理分布。
               - **确保同一日的所有相关动作整合到一个原子事件中，避免将同一日的连续动作拆分为多个原子事件。**
            6. 合理性优化：确保事件描述真实丰富，与用户画像匹配，避免事件间安排冲突。
            
            --- 输出格式强制要求 ---
            1. **仅返回JSON数组（直接子事件列表），以[]开头结尾，无任何额外文本（包括分析、注释、代码块标记）。**
            2. 每个子事件必须包含以下字段（缺一不可，语法严格正确）：
               - event_id：格式为「父事件ID-序号」（如父ID=1-1，子事件ID=1-1-1、1-1-2），确保层级关联。
               - name：事件名称（简洁明了）。
               - **date：时间数组（单个日期/多个日期，粒度≤1天，日期格式为XXXX-XX-XX,如["2025-01-01"]，不允许使用跨天区间格式（如["2025-01-01至2025-02-01"]）。**
               - type：请使用以下预定义的底层事件类别，若没有合适的预定义类别，可自行生成合理的类别：
                   {atomic_categories}
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
            [{{"event_id":"1-1-1","name":"办理欧洲签证","date":["2024-12-15"],"type":"个人事务处理","description":"前往大使馆办理欧洲申根签证","participant":[{{"name":"张三","relation":"自己"}}],"location":"北京市-大使馆","decompose":0}},{{"event_id":"1-1-2","name":"预订机票","date":["2024-12-20"],"type":"票务预定","description":"预订北京往返欧洲的机票","participant":[{{"name":"张三","relation":"自己"}}],"location":"北京市-家中","decompose":0}},{{"event_id":"1-1-3","name":"预订酒店","date":["2024-12-25"],"type":"p","description":"预订欧洲旅行期间的酒店","participant":[{{"name":"张三","relation":"自己"}}],"location":"北京市-家中","decompose":0}},{{"event_id":"1-1-4","name":"准备旅行物品","date":["2024-12-30"],"type":"个人事务处理","description":"收拾行李，准备旅行所需物品","participant":[{{"name":"张三","relation":"自己"}}],"location":"北京市-家中","decompose":0}}]
            
            -- 用户画像 --
            {persona}
            
            -- 背景信息 --
            {background_info}
            
            -- 待分解事件 --
            {parent_event}
        '''
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

    def _get_atomic_categories(self, parent_type: str) -> str:
        """
        根据父节点的type获取对应的原子事件类别列表，格式化为字符串
        :param parent_type: 父节点的事件类型
        :return: 格式化后的原子事件类别字符串
        """
        # 构建原子事件类别字符串
        categories_str = ""
        
        # 如果父节点的type在预定义的schema中，优先显示该类型下的具体类别
        if parent_type in self.event_type_schema:
            categories_str += f"- {parent_type}: {', '.join(self.event_type_schema[parent_type])}\n"
            
        # 显示所有其他类型的类别
        for event_type, categories in self.event_type_schema.items():
            if event_type != parent_type:
                categories_str += f"- {event_type}: {', '.join(categories)}\n"
        
        return categories_str
    
    def _decompose_single_node(self, parent_event: Dict[str, Any], current_depth: int = 0, background_info="") -> List[Dict[str, Any]]:
        """并行处理单个父事件：生成分解后的子事件列表"""
        import copy
        import json
        # 深拷贝父事件，避免并行处理时的引用共享问题
        parent_event_copy = copy.deepcopy(parent_event)
        parent_id = parent_event_copy["event_id"]
        parent_name = parent_event_copy["name"]
        print(f"正在分解事件：{parent_id} - {parent_name[:30]}... 当前深度: {current_depth}")
        
        # 获取父事件的type
        parent_type = parent_event_copy.get("type", "Other")
        # 根据父事件的type获取对应的原子事件类别
        atomic_categories = self._get_atomic_categories(parent_type)

        # 根据当前深度选择模板
        if current_depth == 0:
            template = self.template_level1
            # 第一层分解不需要背景信息
            prompt = template.format(
                persona=self.persona,
                parent_event=json.dumps(parent_event_copy, ensure_ascii=False),
                current_depth=current_depth,
                atomic_categories=atomic_categories
            )
        else:
            template = self.template_level2
            # 第二层分解需要背景信息
            prompt = template.format(
                persona=self.persona,
                parent_event=json.dumps(parent_event_copy, ensure_ascii=False),
                current_depth=current_depth,
                background_info=background_info,
                atomic_categories=atomic_categories
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
        output_path = f"{file}/event_decompose_dfs.json"
        # 确保输出目录存在
        import os
        output_dir = os.path.dirname(output_path)
        os.makedirs(output_dir, exist_ok=True)
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

    def extract_important_nodes(self, persona):
        """
        基于人物画像提取今年（2025年）的重要节点
        
        参数:
            persona: 人物画像数据
            
        返回:
            dict: 包含个人重要节点和社交关系相关人士重要节点的字典
        """
        result = {"personal_nodes": [], "social_nodes": []}
        
        # 1. 单独提取个人重要节点
        print("开始提取个人重要节点...")
        personal_prompt = template_important_nodes.format(persona=persona)
        personal_res = self.llm_call_s(personal_prompt)
        #print("个人重要节点提取结果:")
        #print(personal_res)

        try:
            # 解析个人重要节点
            json_pattern = r'\{.*\}'
            matches = re.search(json_pattern, personal_res, re.DOTALL)
            if matches:
                json_str = matches.group(0)
                # 修复可能的JSON格式问题
                json_str = re.sub(r'\s+', ' ', json_str)
                json_str = re.sub(r',\s*\}', '}', json_str)
                json_str = re.sub(r',\s*\]', ']', json_str)

                personal_result = json.loads(json_str)
                if "personal_nodes" in personal_result:
                    result["personal_nodes"] = personal_result["personal_nodes"]
                    print(f"成功提取{len(result['personal_nodes'])}个个人重要节点")
        except Exception as e:
            print(f"解析个人重要节点失败: {str(e)}")

        # 2. 单独提取社交关系相关人士的重要节点（每10个社交关系为一组进行生成）
        print("\n开始提取社交关系重要节点...")

        # 检查persona中是否包含社交关系信息
        if "relation" not in persona or not persona["relation"]:
            print("persona中没有社交关系信息")
            return result

        try:
            # 创建main_persona：原个人信息去除relation之后的信息
            main_persona = persona.copy()
            if "relation" in main_persona:
                del main_persona["relation"]

            # 从persona中提取所有社交关系
            all_relations = []
            for relation_group in persona["relation"]:
                if isinstance(relation_group, list):
                    all_relations.extend(relation_group)
                else:
                    all_relations.append(relation_group)

            print(f"共提取到{len(all_relations)}个社交关系")

            # 将社交关系按每10个一组进行分组
            for i in range(0, len(all_relations), 10):
                batch_relations = all_relations[i:i+10]
                print(f"\n处理第{int(i/10)+1}组社交关系，共{len(batch_relations)}个")

                # 调用LLM生成当前批次社交关系的重要节点
                batch_prompt = template_social_nodes.format(main_persona=main_persona, social_group=batch_relations)
                batch_res = self.llm_call_s(batch_prompt)
                #print(f"第{int(i/10)+1}组社交关系重要节点提取结果:")
                #print(batch_res)

                # 解析当前批次的结果
                json_pattern = r'\{.*\}'
                matches = re.search(json_pattern, batch_res, re.DOTALL)
                if matches:
                    json_str = matches.group(0)
                    # 修复可能的JSON格式问题
                    json_str = re.sub(r'\s+', ' ', json_str)
                    json_str = re.sub(r',\s*\}', '}', json_str)
                    json_str = re.sub(r',\s*\]', ']', json_str)

                    batch_result = json.loads(json_str)
                    if "social_nodes" in batch_result:
                        result["social_nodes"].extend(batch_result["social_nodes"])
                        print(f"成功提取第{int(i/10)+1}组{len(batch_result['social_nodes'])}个社交关系重要节点")
        except Exception as e:
            print(f"提取社交关系重要节点失败: {str(e)}")
            import traceback
            traceback.print_exc()

        print(f"\n社交关系重要节点提取完成，共提取{len(result['social_nodes'])}个")
        
        return result
        
    def extract_personal_change_timelines(self, persona):
        """
        提取个人变化节点，为四个指定主题各生成一个时间线
        
        参数:
            persona: 人物画像数据
            
        返回:
            list: 包含个人变化时间线的列表
        """
        print("\n开始提取个人变化事件时间线...")
        personal_change_timelines = []
        
        try:
            # 初始化历史记录
            history_records = []
            
            # 定义四个主题字典
            event_types = [
                {"type": "工作变动", "description": "包括升职、降薪、转行、职业发展等相关事件"},
                {"type": "家庭变动", "description": "包括搬家、家庭成员变动（指成员的里程碑事件，如升职，结婚等）、家庭资产变动（如大物件购置，环境改造）相关事件"},
                {"type": "爱好变动", "description": "包括新增爱好相关事件"},
                {"type": "偏好变动", "description": "包括新增偏好、偏好转变等相关事件"}
            ]
            
            # 为每个主题生成一个事件时间线
            for idx, event_type in enumerate(event_types):
                print(f"\n为主题 '{event_type['type']}' 生成个人变化事件...")
                
                # 准备历史记录字符串
                if history_records:
                    history_str = "\n".join([f"{j+1}. 主题：{record['name']}，描述：{record['description']}" for j, record in enumerate(history_records)])
                else:
                    history_str = "暂无历史记录"
                
                # 构建prompt，传入指定主题
                changes_prompt = template_personal_changes.format(
                    persona=persona,
                    history=history_str,
                    event_type=event_type['type']
                )
                
                # 调用LLM生成个人变化事件时间线
                changes_res = self.llm_call_s(changes_prompt)
                #print(f"主题 '{event_type['type']}' 生成结果:")
                #print(changes_res)
                
                # 解析个人变化事件时间线
                json_pattern = r'\[.*\]'
                matches = re.search(json_pattern, changes_res, re.DOTALL)
                if matches:
                    json_str = matches.group(0)
                    # 修复可能的JSON格式问题
                    json_str = re.sub(r'\s+', ' ', json_str)
                    json_str = re.sub(r',\s*\}', '}', json_str)
                    json_str = re.sub(r',\s*\]', ']', json_str)
                    
                    changes_result = json.loads(json_str)
                    if changes_result and isinstance(changes_result, list):
                        # 获取事件（数组中的第一个元素）
                        event_timeline = changes_result[0]
                        # 添加主题类型字段
                        event_timeline["theme"] = event_type['type']
                        personal_change_timelines.append(event_timeline)
                        
                        # 记录历史，避免主题重复
                        history_records.append({
                            "name": event_timeline["topic"],
                            "description": event_timeline["detailed_description"]
                        })
                        
                        print(f"成功提取 '{event_type['type']}' 主题事件：{event_timeline['topic']}")
        except Exception as e:
            print(f"提取个人变化事件时间线失败: {str(e)}")
            import traceback
            traceback.print_exc()
        
        print(f"\n个人变化事件时间线提取完成，共提取{len(personal_change_timelines)}个事件时间线")
        
        return personal_change_timelines
    
    def generate_event_timeline(self, important_nodes, max_workers=None):
        """
        基于提取的重要节点生成主题时间线
        
        参数:
            important_nodes: 包含个人节点和社交节点的字典
            max_workers: 最大并发线程数，当前禁用多线程
            
        返回:
            dict: 按类别分类的主题时间线，每个主题包含结构化的主题、详细描述和月度描述
        """
        # 1. 按类别分类所有事件
        categorized_events = {}
        
        # 首先初始化所有在event_type_descriptions中定义的事件类别
        event_type_descriptions = {
            "Career": "职业工作相关（如“参加行业高峰论坛”“参与新产品研发项目”）",
            "Education": "教育学习相关（如“上课”“考取专业资格证”，学生角色该类事件较多，其他角色相关事件会较少）",
            "Relationships": "人际关系（如“为父母筹备生日宴”“组织闺蜜旅行”）",
            "Family&Living Situation": "家庭生活与居住环境（如“智能家居安装”“组织家庭活动”）",
            "Personal Life": "自我关怀、娱乐与生活方式（SelfCare & Entertainment & Lifesyle）（如“定期SPA护理”“短途旅行”“组织同学聚会”“KTV娱乐”）",
            "Finance": "个人资产财务（如“购买理财产品”“汽车保养与维修”）",
            "Health": "健康管理（如“中医调理”“瑜伽静修营”）",
        }
        
        # 初始化所有事件类别为[]
        for event_type in event_type_descriptions:
            categorized_events[event_type] = []
        
        # 处理个人重要节点
        for event in important_nodes.get("personal_nodes", []):
            event_type = event.get("type", "Other")
            if event_type not in categorized_events:
                categorized_events[event_type] = []
            categorized_events[event_type].append(event)
        
        # 处理社交重要节点（按事件自身的type分类）
        for event in important_nodes.get("social_nodes", []):
            # 使用事件自身的type字段进行分类
            event_type = event.get("type", "Relationships")
            if event_type not in categorized_events:
                categorized_events[event_type] = []
            categorized_events[event_type].append(event)
        
        # 3. 为每个类别生成额外的重要事件（测试阶段只生成Family&Living Situation类别）
        from event.template_s import template_important_events_generation
        import json
        
        # 为所有类别生成额外重要事件（多线程版本）
        from concurrent.futures import ThreadPoolExecutor
        
        def generate_important_events_for_category(event_type, existing_events):
            """为单个事件类别生成额外重要事件"""
            print(f"\n开始为{event_type}类别生成额外重要事件...")
            
            # 定义不同事件类别的描述
            event_type_descriptions = {
                "Career": "职业工作相关（如“参加行业高峰论坛”“参与新产品研发项目”）",
                "Education": "教育学习相关（如“上课”“考取专业资格证”，学生角色该类事件较多，其他角色相关事件会较少）",
                "Relationships": "人际关系（如“为父母筹备生日宴”“组织闺蜜旅行”）",
                "Family&Living Situation": "家庭生活与居住环境（如“智能家居安装”“组织家庭活动”）",
                "Personal Life": "自我关怀、娱乐与生活方式（SelfCare & Entertainment & Lifesyle）（如“定期SPA护理”“短途旅行”“组织同学聚会”“KTV娱乐”）",
                "Finance": "个人资产财务（如“购买理财产品”“汽车保养与维修”）",
                "Health": "健康管理（如“中医调理”“瑜伽静修营”）",
            }
            
            # 获取当前事件类别的描述，如果没有则使用默认描述
            event_type_with_description = event_type
            if event_type in event_type_descriptions:
                event_type_with_description = f"{event_type}：{event_type_descriptions[event_type]}"
            
            # 准备prompt，将已有重要节点作为参考输入
            prompt = template_important_events_generation.format(
                persona=self.persona,
                event_type=event_type_with_description,
                existing_events=json.dumps(existing_events, ensure_ascii=False) if existing_events else "[]"
            )
            
            generated_events = []
            
            # 调用LLM生成重要事件
            try:
                response = self.llm_call_sr(prompt)
                
                # 提取JSON部分
                start_idx = response.find('[')
                end_idx = response.rfind(']')
                if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                    json_response = response[start_idx:end_idx + 1]
                    raw_events = json.loads(json_response)
                    
                    # 转换为与原有事件格式一致的结构
                    generated_events = [{
                        "name": event["name"],
                        "type": event_type,
                        "description": event["description"],
                        "impact": event["potential_impact"],
                        "reason": event["reason"]
                    } for event in raw_events]
                    
                    print(f"成功为{event_type}类别生成{len(generated_events)}个额外重要事件")
                else:
                    print(f"无法提取{event_type}类别生成的重要事件JSON")
            except json.JSONDecodeError as e:
                print(f"解析{event_type}类别重要事件JSON时出错: {e}")
                #print(f"LLM响应内容: {response}")
            except Exception as e:
                print(f"为{event_type}类别生成重要事件时发生错误: {e}")
                import traceback
                traceback.print_exc()
            
            return (event_type, generated_events)
        
        # 使用线程池并行处理所有事件类别
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有事件类别的处理任务
            future_to_category = {
                executor.submit(generate_important_events_for_category, event_type, events): event_type
                for event_type, events in categorized_events.items()
            }
            
            # 收集处理结果
            for future in future_to_category:
                try:
                    event_type, result = future.result()
                    if result:
                        categorized_events[event_type].extend(result)
                except Exception as e:
                    event_type = future_to_category[future]
                    print(f"处理{event_type}类别额外重要事件时发生错误: {e}")
                    import traceback
                    traceback.print_exc()

        # 2. 为每个类别生成事件变动时间线
        event_timelines = {}
        
        # 如果没有事件类型，直接返回空字典
        if not categorized_events:
            return event_timelines
            
        def generate_topic_timelines(event_type, events):
            """生成单个类别的主题时间线JSON数组，每十个事件调用一次LLM生成"""
            import json
            print(f"\n开始生成{event_type}类别的主题时间线...")
            
            # 定义不同事件类别的描述
            event_type_descriptions = {
                "Career": "职业工作相关（如“参加行业高峰论坛”“参与新产品研发项目”）",
                "Education": "教育学习相关（如“上课”“考取专业资格证”，学生角色该类事件较多，其他角色相关事件会较少）",
                "Relationships": "人际关系（如“为父母筹备生日宴”“组织闺蜜旅行”）",
                "Family&Living Situation": "家庭生活与居住环境（如“家居装修”“智能家居安装”）",
                "Personal Life": "自我关怀、娱乐与生活方式（SelfCare & Entertainment & Lifesyle）（如“定期SPA护理”“短途旅行”“组织同学聚会”）",
                "Finance": "个人资产财务（如“购买理财产品”“汽车保养与维修”）",
                "Health": "健康管理（如“中医调理”“瑜伽静修营”）",
                "Unexpected Events": "突发应对（如“车辆小事故处理”“临时加班替班”）",
                "Other": "其他未涉及类别"
            }
            
            # 获取当前事件类别的描述，如果没有则使用默认描述
            event_type_with_description = event_type
            if event_type in event_type_descriptions:
                event_type_with_description = f"{event_type}：{event_type_descriptions[event_type]}"
            
            # 将事件按每10个一组进行分组
            events_per_group = 10
            event_groups = [events[i:i+events_per_group] for i in range(0, len(events), events_per_group)]
            
            all_timeline_data = []
            
            # 处理每组事件
            for group_idx, event_group in enumerate(event_groups):
                print(f"\n处理{event_type}类别第{group_idx+1}/{len(event_groups)}组事件，共{len(event_group)}个事件")
                
                # 准备prompt
                prompt = template_event_timeline.format(
                    event_type=event_type_with_description,
                    persona=self.persona,
                    important_nodes=json.dumps(event_group, ensure_ascii=False)
                )
                
                # 调用LLM生成时间线JSON
                try:
                    response = self.llm_call_sr(prompt)
                    #print(f"{event_type}类别第{group_idx+1}组主题时间线生成结果:")
                    #print(response)
                    
                    # 提取JSON部分：匹配第一个[和最后一个]之间的内容
                    start_idx = response.find('[')
                    end_idx = response.rfind(']')
                    if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                        json_response = response[start_idx:end_idx + 1]
                        timeline_data = json.loads(json_response)
                        all_timeline_data.extend(timeline_data)
                    else:
                        print(f"第{group_idx+1}组无法提取JSON内容")
                        print(f"LLM响应内容: {response}")
                except json.JSONDecodeError as e:
                    print(f"解析{event_type}第{group_idx+1}组时间线JSON时出错: {e}")
                    print(f"LLM响应内容: {response}")
                except Exception as e:
                    print(f"生成{event_type}第{group_idx+1}组时间线时出错: {str(e)}")
                    import traceback
                    traceback.print_exc()
            
            print(f"\n{event_type}类别所有组时间线生成完成，共生成{len(all_timeline_data)}个主题时间线")
            return all_timeline_data
        
        # 处理所有类别的事件，使用多线程并行处理
        from concurrent.futures import ThreadPoolExecutor
        
        def process_event_category(event_type, events):
            """处理单个事件类别的时间线生成"""
            print(f"\n开始处理{event_type}类别...")
            
            # 生成主题时间线数据（直接返回，不再进行冲突消解和时间线统一）
            topic_timelines_data = generate_topic_timelines(event_type, events)
            
            if topic_timelines_data:
                print(f"{event_type}类别主题时间线生成完成")
                return (event_type, topic_timelines_data)
            else:
                print(f"{event_type}类别没有生成主题时间线数据")
                return (event_type, [])
        
        # 使用线程池并行处理所有事件类别
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有事件类别的处理任务
            future_to_category = {
                executor.submit(process_event_category, event_type, events): event_type
                for event_type, events in categorized_events.items()
            }
            
            # 收集处理结果
            for future in future_to_category:
                try:
                    event_type, result = future.result()
                    if result:
                        event_timelines[event_type] = result
                except Exception as e:
                    event_type = future_to_category[future]
                    print(f"处理{event_type}类别时发生错误: {e}")
                    import traceback
                    traceback.print_exc()
        
        # 调用个人变化时间线提取函数，将结果作为"persona change"类别的时间线
        persona_change_timelines = self.extract_personal_change_timelines(self.persona)
        if persona_change_timelines:
            event_timelines["persona change"] = persona_change_timelines
        
        return event_timelines

    def save_event_timelines(self, event_timelines, output_path):
        """
        保存事件时间线到文件
        
        参数:
            event_timelines: 事件时间线字典
            output_path: 输出文件路径
        """
        import json
        import os
        
        # 确保输出目录存在
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # 保存时间线到文件
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(event_timelines, f, ensure_ascii=False, indent=2)
        
        print(f"事件时间线已保存到 {output_path}")
    
    def merge_similar_timelines(self, event_timelines, max_workers=None):
        """
        筛选所有类别的相似主题时间线（不分类别）
        
        参数:
            event_timelines: 事件时间线字典，键为事件类型，值为主题时间线列表
            max_workers: 最大并发线程数，默认使用CPU核心数
            
        返回:
            tuple: (筛选后的时间线列表, 筛选后的时间线id列表)
        """
        import json
        import concurrent.futures
        
        print("\n开始处理所有类别的相似主题合并...")
        
        # 1. 收集所有事件类型的时间线到一个列表
        all_timelines = []
        timeline_metadata = []  # 保存时间线的原始事件类型信息
        
        for event_type, timelines in event_timelines.items():
            for timeline in timelines:
                all_timelines.append(timeline)
                timeline_metadata.append({
                    'original_event_type': event_type
                })
        
        print(f"共收集到{len(all_timelines)}个主题时间线")
        
        # 如果时间线数量小于2，无需筛选
        if len(all_timelines) < 2:
            print(f"只有{len(all_timelines)}个主题时间线，无需筛选")
            # 为时间线生成id
            selected_ids = []
            for i, (timeline, metadata) in enumerate(zip(all_timelines, timeline_metadata), 1):
                event_type = metadata['original_event_type']
                timeline_id = f"{event_type}_{i}"
                selected_ids.append(timeline_id)
            return all_timelines, selected_ids
        
        # 2. 按主题长度排序（可选，有助于后续处理）
        sorted_timelines = sorted(all_timelines, key=lambda x: len(x.get('topic', '')), reverse=True)
        
        # 3. 准备LLM提示，判断主题相似性
        timeline_info = []
        for i, timeline in enumerate(sorted_timelines, 1):
            topic = timeline.get('topic', '')
            description = timeline.get('detailed_description', '')[:150]  # 截取部分描述以控制prompt长度
            timeline_info.append(f"序号{i}: 主题: {topic}\n描述: {description}...")
        
        # 构建相似性判断和选择prompt
        similarity_prompt = f"""
        以下是一系列主题时间线的信息：
        {chr(10).join(timeline_info)}
        
        请仔细分析这些主题时间线，并执行以下任务：
        
        1. 相似簇判断：找出所有主题相似的簇。相似的标准是主题内容大部分重复或高度相关，没有必要单独作为一个主题时间线。
        2. 相似簇选择：从每个相似簇中选择一个最具代表性、最全面、事件时间分布最真实丰富的时间线，返回其序号。
        3. 主题多样性优先：确保最终剩余的时间线主题间尽量差异明显，避免内容重复，优先保留不同类别的主题（如工作、学习、健康、生活、社交、爱好等）。
        4. 真实丰富时间优先：在选择时间线时，优先选择事件时间分布真实、丰富、符合生活逻辑的时间线，避免选择时间过于集中或事件安排不真实的时间线。避免变化过于曲折而违和的时间线。
        5. 冲突处理：
           - 对于存在冲突（事件时间、地点、影响等不一致）的时间线，选择冲突较少、更合理的时间线
           - 确保时间线的连贯性和合理性
        6. 事件真实性检查：
           - 对于主题相同的事件（如都是患病类事件），需考虑整合后是否会导致一年中该类事件过多而不真实
           - 确保最终的时间线组合符合实际生活逻辑，避免出现不真实的事件密集情况
           
        7. 数量控制：最终选择9-10个时间线，确保主题多样且时间真实丰富。
        
        输出格式要求：
        1. 仅返回JSON对象，格式如下：
        {{"selected_timelines": [序号1, 序号2, 序号3, ...],  # 保留的时间线序号列表（9-10个）
            "similar_clusters": [[序号1, 序号2], [序号3, 序号4], ...]  # 相似簇列表（用于冲突分析）
        }}
        2. 确保selected_timelines中的序号没有重复，且数量为8-10个
        3. 每个相似簇至少包含2个序号
        4. 请确保输出的JSON格式正确，不包含任何无关解释、注释或代码，直接以{{}}开头。
        """
        #print("相似主题判断和选择prompt: ", similarity_prompt)
        # 调用LLM判断相似性并选择时间线
        llm_result = {}
        try:
            response = self.llm_call_sr(similarity_prompt)
            #print(f"LLM响应内容: {response}")
            # 提取JSON部分
            start_idx = response.find('{')
            end_idx = response.rfind('}')
            if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                json_response = response[start_idx:end_idx + 1]
                llm_result = json.loads(json_response)
                print(f"成功获取LLM选择结果：共选择{len(llm_result.get('selected_timelines', []))}个时间线，识别{len(llm_result.get('similar_clusters', []))}个相似主题簇")
            else:
                print("无法提取相似主题和选择结果的JSON")
        except json.JSONDecodeError as e:
            print(f"解析相似主题和选择结果JSON时出错: {e}")
            #print(f"LLM响应内容: {response}")
        except Exception as e:
            print(f"判断主题相似性时发生错误: {e}")
            import traceback
            traceback.print_exc()
        
        # 4. 处理LLM返回的选择结果
        selected_timelines = []
        selected_ids = []
        
        # 获取LLM选择的时间线序号
        selected_indices = llm_result.get('selected_timelines', [])
        similar_clusters = llm_result.get('similar_clusters', [])
        
        if selected_indices:
            print(f"开始处理LLM选择的{len(selected_indices)}个时间线...")
            
            # 添加LLM选择的时间线
            for idx in selected_indices:
                if 1 <= idx <= len(sorted_timelines):
                    timeline = sorted_timelines[idx - 1]
                    selected_timelines.append(timeline)
                    # 为时间线生成id
                    event_type = timeline_metadata[idx - 1]['original_event_type']
                    timeline_id = f"{event_type}_{idx}"
                    selected_ids.append(timeline_id)
        else:
            print("LLM未返回选择结果，使用默认策略：选择前8个时间线")
            # 默认策略：选择前8个时间线
            selected_timelines = sorted_timelines[:8]  # 选择前8个时间线
            for i, timeline in enumerate(selected_timelines, 1):
                event_type = timeline_metadata[i - 1]['original_event_type']
                timeline_id = f"{event_type}_{i}"
                selected_ids.append(timeline_id)
        
        print(f"主题选择完成，保留{len(selected_timelines)}个时间线")
        return selected_timelines
    
    def optimize_merged_timelines(self, merged_timelines, max_workers=None):
        """
        优化合并后的时间线，主要功能：
        1. 每5个时间线进行一次合并，得到一组合并后时间线
        2. 最后对合并后时间线进行一次统一合并（单独的prompt）
        3. 生成一个多样的、丰富的、连贯的、无冲突的时间线
        
        参数:
            merged_timelines: 合并后的时间线列表
            max_workers: （已废弃，不再使用）
            
        返回:
            list: 包含一个统一优化后的时间线的列表
        """
        import json

        # 导入templates模块
        from event.templates import template_timeline_conflict_resolution

        print("\n开始优化合并后的时间线...")
        print(f"共收到{len(merged_timelines)}个合并后的时间线")

        # 如果时间线数量为0，直接返回
        if len(merged_timelines) == 0:
            print("没有时间线需要优化")
            return merged_timelines

        # 内部函数：合并一组时间线
        def merge_timeline_group(group_timelines, group_index):
            """合并一组时间线"""
            print(f"\n开始合并第{group_index+1}组时间线，共{len(group_timelines)}个时间线")

            # 1. 收集这组时间线信息，准备LLM分析
            group_analysis_data = []
            for i, timeline in enumerate(group_timelines, 1):
                topic = timeline.get('topic', '')
                description = timeline.get('detailed_description', '')
                # 将时间线信息添加到分析数据列表
                group_analysis_data.append({
                    'id': i,
                    'topic': topic,
                    'description': description,
                    'events': timeline.get('events', [])
                })
            print(f"成功收集第{group_index+1}组时间线的分析数据")

            # 2. 使用template_timeline_conflict_resolution模板进行冲突分析
            print(f"\n正在调用LLM分析第{group_index+1}组时间线冲突...")

            # 准备模板所需参数
            persona = json.dumps(self.persona, ensure_ascii=False, indent=2)
            group_timelines_json = json.dumps(group_timelines, ensure_ascii=False, indent=2)

            # 构建冲突分析提示
            analysis_prompt = template_timeline_conflict_resolution.format(
                persona=persona,
                timelines_list=group_timelines_json
            )


            response = self.llm_call_sr(analysis_prompt)
            print(f"成功获取第{group_index+1}组时间线冲突分析结果")

            # 4. 整合这组时间线，生成统一的优化时间线
            print(f"\n正在整合第{group_index+1}组时间线，生成统一的优化时间线...")

            try:
                # 准备整合时间线的参数
                original_timeline = json.dumps(group_timelines, ensure_ascii=False, indent=2)  # 将所有时间线作为一个整体

                # 构建整合时间线的提示
                integration_prompt = template_timeline_final_generation.format(
                    persona=persona,
                    original_timelines=original_timeline,
                    conflict_analysis_result=response
                )

                # 调用LLM生成整合后的时间线
                response = self.llm_call_sr(integration_prompt)
                #print(response)
                # 提取JSON部分（匹配第一个{和最后一个}）
                start_idx = response.find('{')
                end_idx = response.rfind('}')
                if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                    json_response = response[start_idx:end_idx + 1]
                    try:
                        group_merged_timeline = json.loads(json_response)
                        print(f"\n第{group_index+1}组时间线整合完成")

                        # 确保返回的是一个有效的时间线列表
                        if isinstance(group_merged_timeline, list):
                            result_to_return = group_merged_timeline
                        elif isinstance(group_merged_timeline, dict):
                            result_to_return = [group_merged_timeline]
                        else:
                            print(f"第{group_index+1}组整合后时间线格式不符合预期，返回原始时间线组")
                            result_to_return = group_timelines

                        # # 将每组输出保存到output/new/med.json文件
                        # import os
                        # output_dir = "output/new"
                        # output_file = os.path.join(output_dir, "med.json")
                        #
                        # # 确保输出目录存在
                        # os.makedirs(output_dir, exist_ok=True)
                        #
                        # try:
                        #     # 读取已有的数据（如果文件存在）
                        #     existing_data = []
                        #     if os.path.exists(output_file):
                        #         with open(output_file, 'r', encoding='utf-8') as f:
                        #             existing_data = json.load(f)

                            # # 添加当前组的结果
                            # existing_data.extend(result_to_return)

                            # # 保存到文件
                            # with open(output_file, 'w', encoding='utf-8') as f:
                            #     json.dump(existing_data, f, ensure_ascii=False, indent=2)
                            #
                            # print(f"第{group_index+1}组时间线已成功保存到{output_file}")
                        # except Exception as e:
                        #     print(f"保存第{group_index+1}组时间线到文件时出错: {e}")
                        #     import traceback
                        #     traceback.print_exc()

                        return result_to_return
                    except json.JSONDecodeError as e:
                        print(f"解析第{group_index+1}组整合时间线JSON时出错: {e}")
                        #print(f"LLM响应内容: {response}")
                        return group_timelines
                else:
                    print(f"无法提取第{group_index+1}组整合时间线的JSON")
                    #print(f"LLM响应内容: {response}")
                    return group_timelines
            except Exception as e:
                print(f"整合第{group_index+1}组时间线时发生错误: {e}")
                import traceback
                traceback.print_exc()
                return group_timelines

        # 步骤1: 将时间线按每5个一组进行分组
        grouped_timelines = [merged_timelines[i:i+5] for i in range(0, len(merged_timelines), 5)]
        print(f"将时间线分成{len(grouped_timelines)}组，每组最多5个时间线")

        # 步骤2: 合并每组时间线（多线程并行）
        import threading

        # 定义线程安全的结果列表
        group_merged_results = []
        results_lock = threading.Lock()

        # 线程工作函数
        def merge_group_thread(group, group_index):
            nonlocal group_merged_results
            result = merge_timeline_group(group, group_index)
            with results_lock:
                group_merged_results.extend(result)

        # 创建并启动线程
        threads = []
        for i, group in enumerate(grouped_timelines):
            thread = threading.Thread(target=merge_group_thread, args=(group, i))
            threads.append(thread)
            thread.start()

        # 等待所有线程完成
        for thread in threads:
            thread.join()

        print(f"\n所有分组合并完成，共得到{len(group_merged_results)}个中间合并结果")

        # 如果只有一个分组，直接返回该分组的结果
        if len(grouped_timelines) == 1:
            return group_merged_results

        # 步骤3: 对所有分组合并结果进行一次统一合并
        print("\n开始对所有分组合并结果进行统一合并...")
        # with open("output/new/med.json", 'w', encoding='utf-8') as f:
        #     json.dump(group_merged_results, f, ensure_ascii=False, indent=2)
        try:
            # 准备整合时间线的参数
            persona = json.dumps(self.persona, ensure_ascii=False, indent=2)
            original_timeline = json.dumps(group_merged_results, ensure_ascii=False, indent=2)  # 将所有分组合并结果作为原始时间线

            # 由于没有新的冲突分析结果，使用包含空结构的JSON对象
            conflict_analysis_result = {
                "conflict_resolution_result": [],
                "annual_overview": {}
            }
            conflict_analysis_result_str = json.dumps(conflict_analysis_result, ensure_ascii=False, indent=2)

            # 构建整合时间线的提示
            integration_prompt = template_timeline_final_generation.format(
                persona=persona,
                original_timelines=original_timeline,
                conflict_analysis_result=conflict_analysis_result_str
            )

            # 调用LLM生成整合后的时间线
            response = self.llm_call_sr(integration_prompt)
            #print(f"统一合并时间线LLM响应内容: {response}")

            # 提取JSON部分（匹配第一个{和最后一个}）
            start_idx = response.find('{')
            end_idx = response.rfind('}')
            if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                json_response = response[start_idx:end_idx + 1]
                try:
                    final_result = json.loads(json_response)
                    print("\n所有分组合并结果统一合并完成")

                    # 确保返回的是一个有效的时间线列表
                    if isinstance(final_result, list):
                        pass  # 已经是列表，直接使用
                    elif isinstance(final_result, dict):
                        final_result = [final_result]  # 转换为列表
                    else:
                        print("统一合并后时间线格式不符合预期，返回分组合并结果")
                        final_result = group_merged_results
                except json.JSONDecodeError as e:
                    print(f"解析统一合并时间线JSON时出错: {e}")
                    #print(f"LLM响应内容: {response}")
                    final_result = group_merged_results
            else:
                print("无法提取统一合并时间线的JSON")
                #print(f"LLM响应内容: {response}")
                final_result = group_merged_results
        except Exception as e:
            print(f"统一合并时间线时发生错误: {e}")
            import traceback
            traceback.print_exc()
            final_result = group_merged_results


        # 步骤4: 时间线校验优化
        try:
            # 将final_result转换为JSON字符串用于校验
            merged_timeline_str = json.dumps(final_result, ensure_ascii=False, indent=2)
            
            # 构建时间线校验的提示
            validation_prompt = template_timeline_validation.format(
                persona=self.persona,
                merged_timeline=merged_timeline_str
            )
            
            # 调用LLM进行时间线校验
            validation_response = self.llm_call_sr(validation_prompt)
            #print(f"时间线校验LLM响应内容: {validation_response}")
            
            # 提取JSON部分（匹配第一个{和最后一个}）
            start_idx_val = validation_response.find('{')
            end_idx_val = validation_response.rfind('}')
            if start_idx_val != -1 and end_idx_val != -1 and start_idx_val < end_idx_val:
                json_validation_response = validation_response[start_idx_val:end_idx_val + 1]
                try:
                    # 解析校验后的时间线
                    validated_result = json.loads(json_validation_response)
                    print("\n时间线校验优化完成")
                    
                    # 确保返回的是一个有效的时间线列表
                    if isinstance(validated_result, list):
                        print("\n统一合并完成，返回校验后的最终结果")
                        return validated_result
                    elif isinstance(validated_result, dict):
                        print("\n统一合并完成，返回校验后的最终结果")
                        return [validated_result]
                    else:
                        print("校验后时间线格式不符合预期，返回原始合并结果")
                except json.JSONDecodeError as e:
                    print(f"解析校验后时间线JSON时出错: {e}")
                    #print(f"LLM响应内容: {validation_response}")
            else:
                print("无法提取校验后时间线的JSON")
                #print(f"LLM响应内容: {validation_response}")
        except Exception as e:
            print(f"时间线校验时发生错误: {e}")
            import traceback
            traceback.print_exc()
        
        # 校验失败时返回原始合并结果
        print("\n统一合并完成，时间线校验失败，返回原始合并结果")
        return final_result


    def generate_and_insert_events(self, timeline_data, events_by_theme=None):
        """
        根据时间线数据生成可插入事件并进行分析和插入
        第一轮：生成25-40个基于时间线的可插入事件，参考event_schema.csv的第二列
        新增轮次：生成10个左右2025年的个人生活变化转折点事件，参考event_schema.csv的第二列
        第三轮：生成20个左右不基于个人画像的事件和人类共性事件，增加随机性以开启人物画像的新属性
        第四轮：对每个事件进行影响分析，并插入时间线
        """
        import csv
        import copy
        from event.template_s import template_generate_insertable_events, template_generate_creative_events, template_third_round_events, template_analyze_group_events
        
        try:
            # 读取event_schema.csv的所有内容作为参考事件
            reference_events_str = ""
            schema_path = "event/event_schema.csv"
            if os.path.exists(schema_path):
                with open(schema_path, 'r', encoding='utf-8') as f:
                    content = f.read()  # 读取整个文件内容
                    # 将内容按行分割，并在每行末尾添加分号
                    lines = content.strip().split('\n')
                    # 跳过标题行（假设第一行为标题）
                    for line in lines[1:]:
                        if line.strip():  # 确保不是空行
                            reference_events_str += line.strip() + ";"
            else:
                print("警告：event_schema.csv 文件不存在，将不使用参考事件")
            # 将字符串按分号分割成列表（去除最后的空元素）
            reference_events = reference_events_str.rstrip(';').split(';') if reference_events_str else []
            
            # 将参考事件转换为字符串格式
            reference_events_str = json.dumps(reference_events, ensure_ascii=False)
            
            # 初始化事件ID计数器和相关数据结构
            event_id_counter = 1
            same_theme_arr = []
            frequency_id_groups = []
            
            # 第一轮：生成基于时间线的可插入事件
            print("开始第一轮：生成基于时间线的可插入事件...")
            
            # 获取人物画像信息
            persona_info = getattr(self, 'persona', {})
            
            # 构建生成事件的提示
            prompt_gen_events = template_generate_insertable_events.format(
                persona=json.dumps(persona_info, ensure_ascii=False),
                timeline=json.dumps(timeline_data, ensure_ascii=False),
                reference_events=reference_events_str
            )
            
            # 调用LLM生成事件
            response_gen = self.llm_call_sr(prompt_gen_events,0)
            #print("LLM生成事件结果：",response_gen)
            # 提取JSON部分 - 预处理可能的引号问题
            processed_response = response_gen.replace('\\"', '"').replace('""', '\"')
            start_idx = processed_response.find('[')
            end_idx = processed_response.rfind(']')
            if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                json_response = processed_response[start_idx:end_idx + 1]
                try:
                    generated_events_round1 = json.loads(json_response)
                    print(f"成功生成{len(generated_events_round1)}个基于时间线的可插入事件")
                except json.JSONDecodeError as e:
                    print(f"解析第一轮生成的事件JSON失败: {str(e)}")
                    print(f"尝试解析的响应内容: {json_response}")
                    generated_events_round1 = []
            else:
                print("无法从第一轮生成事件的响应中提取JSON")
                #print(f"响应内容: {response_gen}")
                generated_events_round1 = []
            
            # 直接将第一轮生成的事件根据开始时间插入到对应月份
            print("开始第一轮：直接插入基于时间线的事件...")
            updated_timeline = copy.deepcopy(timeline_data)
            
            # 为输入数据中的原始事件分配ID
            for month_detail in updated_timeline.get('monthly_details', []):
                for event in month_detail.get('events', []):
                    event['id'] = event_id_counter
                    
                    # 检查是否与events_by_theme中的事件匹配
                    if events_by_theme:
                        event_name = event.get('name', '').strip()
                        for theme_data in events_by_theme:
                            for theme_event in theme_data.get('events', []):
                                theme_event_name = theme_event.get('name', '').strip()
                                if event_name == theme_event_name:
                                    # 如果匹配，记录主题和事件ID
                                    theme_name = theme_data.get('theme_name', '未知主题')
                                    # 检查是否已有该主题的记录
                                    existing_theme = next((item for item in same_theme_arr if item.get('theme_summary') == theme_name), None)
                                    if existing_theme:
                                        existing_theme['event_ids'].append(event_id_counter)
                                    else:
                                        same_theme_arr.append({
                                            'theme_summary': theme_name,
                                            'event_ids': [event_id_counter]
                                        })
                    
                    event_id_counter += 1
            
            # 统计事件发生频率
            event_name_count = {}
            for event in generated_events_round1:
                event_name = event.get('name', '未知事件')
                if event_name in event_name_count:
                    event_name_count[event_name] += 1
                else:
                    event_name_count[event_name] = 1
            
            for event in generated_events_round1:
                # 获取开始时间和结束时间，可能是数组
                start_times = event.get('start_time', [])
                end_times = event.get('end_time', [])
                
                # 确保start_times和end_times是列表
                if not isinstance(start_times, list):
                    start_times = [start_times] if start_times else []
                if not isinstance(end_times, list):
                    end_times = [end_times] if end_times else []
                
                # 记录同一事件的所有ID
                same_event_ids = []
                
                # 遍历所有发生时间，依次插入事件
                for idx, (start_time_str, end_time_str) in enumerate(zip(start_times, end_times)):
                    if start_time_str:
                        try:
                            event_date = datetime.strptime(start_time_str.split(' ')[0], '%Y-%m-%d')
                            month_key = f"2025-{event_date.month:02d}"
                            
                            # 查找对应的月份索引
                            month_found = False
                            for i, month_detail in enumerate(updated_timeline.get('monthly_details', [])):
                                if month_detail.get('month') == month_key:
                                    # 分配事件ID
                                    event['id'] = event_id_counter
                                    
                                    # 检查是否与events_by_theme中的事件匹配
                                    event_name = event.get('name', '').strip()
                                    if events_by_theme:
                                        for theme_data in events_by_theme:
                                            for theme_event in theme_data.get('events', []):
                                                theme_event_name = theme_event.get('name', '').strip()
                                                if event_name == theme_event_name:
                                                    # 如果匹配，记录主题和事件ID
                                                    theme_name = theme_data.get('theme_name', '未知主题')
                                                    # 检查是否已有该主题的记录
                                                    existing_theme = next((item for item in same_theme_arr if item.get('theme_summary') == theme_name), None)
                                                    if existing_theme:
                                                        existing_theme['event_ids'].append(event_id_counter)
                                                    else:
                                                        same_theme_arr.append({
                                                            'theme_summary': theme_name,
                                                            'event_ids': [event_id_counter]
                                                        })
                                                    break
                                            else:
                                                continue
                                            break
                                    
                                    # 将事件添加到该月份的事件列表中
                                    updated_timeline['monthly_details'][i]['events'].append({
                                        'id': event_id_counter,
                                        'description': event.get('description', ''),
                                        'date': f"{start_time_str}至{end_time_str}",
                                        'belongs_to_theme': event.get('type', '其他')
                                    })
                                    same_event_ids.append(event_id_counter)
                                    print(f"已将事件 '{event.get('name', '未知事件')}' (发生时间 {idx+1}) 插入到{month_key}, ID: {event_id_counter}")
                                    event_id_counter += 1
                                    month_found = True
                                    break
                            
                            if not month_found:
                                print(f"警告：未找到{month_key}的数据，无法插入事件")
                                
                        except Exception as e:
                            print(f"解析事件时间失败: {str(e)}, 事件: {event.get('name', '未知事件')}, 发生时间: {idx+1}")
                
                # 检查是否是发生频率大于1的事件，记录ID组合
                event_name = event.get('name', '未知事件')
                if len(same_event_ids) > 1:  # 同一个事件发生多次（多个时间点）
                    frequency_id_groups.append(same_event_ids)
            
            # 新增轮次：生成变化事件
            print("开始第二轮：生成变化事件...")
            
            # 构建生成变化事件的提示
            prompt_gen_creative_events = template_generate_creative_events.format(
                persona=json.dumps(persona_info, ensure_ascii=False),
                reference_events=reference_events_str,
                timeline=json.dumps(updated_timeline, ensure_ascii=False)
            )
            
            # 调用LLM生成创新事件
            response_gen_creative = self.llm_call_sr(prompt_gen_creative_events,1)
            #print("LLM生成创新事件结果：",response_gen_creative)
            # 提取JSON部分 - 预处理可能的引号问题
            processed_response = response_gen_creative.replace('\\"', '"').replace('""', '\"')
            start_idx = processed_response.find('[')
            end_idx = processed_response.rfind(']')
            if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                json_response = processed_response[start_idx:end_idx + 1]
                try:
                    generated_events_creative = json.loads(json_response)
                    print(f"成功生成{len(generated_events_creative)}个创新性事件")
                except json.JSONDecodeError as e:
                    print(f"解析创新事件JSON失败: {str(e)}")
                    #print(f"尝试解析的响应内容: {json_response}")
                    generated_events_creative = []
            else:
                print("无法从创新事件生成响应中提取JSON")
                #print(f"响应内容: {response_gen_creative}")
                generated_events_creative = []
            
            # 第三轮：生成不基于个人画像的事件和人类共性事件
            print("开始第三轮：生成不基于个人画像的事件和人类共性事件...")
            
            # 构建第三轮事件生成的提示
            prompt_gen_third_round = template_third_round_events.format(
                persona=json.dumps(persona_info, ensure_ascii=False),
                timeline=json.dumps(updated_timeline, ensure_ascii=False)
            )
            
            # 调用LLM生成第三轮事件
            response_gen_third = self.llm_call_sr(prompt_gen_third_round)
            #print("LLM生成第三轮事件结果：", response_gen_third)
            
            # 提取JSON部分 - 预处理可能的引号问题
            processed_response = response_gen_third.replace('\\"', '"').replace('""', '\"')
            start_idx = processed_response.find('[')
            end_idx = processed_response.rfind(']')
            if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                json_response = processed_response[start_idx:end_idx + 1]
                try:
                    generated_events_third = json.loads(json_response)
                    print(f"成功生成{len(generated_events_third)}个不基于个人画像的事件和人类共性事件")
                except json.JSONDecodeError as e:
                    print(f"解析第三轮生成的事件JSON失败: {str(e)}")
                    #print(f"尝试解析的响应内容: {json_response}")
                    generated_events_third = []
            else:
                print("无法从第三轮生成事件的响应中提取JSON")
                #print(f"响应内容: {response_gen_third}")
                generated_events_third = []
            
            # 合并第二轮和第三轮生成的事件
            combined_second_third_events = generated_events_creative + generated_events_third
            print(f"第二、三轮共生成{len(combined_second_third_events)}个待筛选事件")
            
            # 对第二轮和第三轮事件进行分组筛选分析
            print("开始第四轮：分组筛选分析并插入事件...")
            
            # 将事件分成每组5个
            group_size = 5
            grouped_events = [combined_second_third_events[i:i + group_size] 
                              for i in range(0, len(combined_second_third_events), group_size)]
            
            processed_events = 0
            
            # 定义处理单个事件组的函数
            def process_event_group(group_data):
                group_idx, event_group = group_data
                print(f"正在处理第{group_idx + 1}组事件 ({len(event_group)}个事件)...")
                
                # 构建筛选分析的提示
                event_group_json = json.dumps(event_group, ensure_ascii=False, indent=2)
                
                prompt_analyze_group = template_analyze_group_events.format(
                    persona=json.dumps(persona_info, ensure_ascii=False),
                    timeline=json.dumps(updated_timeline, ensure_ascii=False),
                    event_group=event_group_json
                )
                
                response_analyze = self.llm_call_sr(prompt_analyze_group)
                #print(f"第{group_idx + 1}组分析结果：", response_analyze[:200] + "..." if len(response_analyze) > 200 else response_analyze)
                
                # 提取分析结果JSON - 预处理可能的引号问题
                processed_response = response_analyze.replace('\\"', '"').replace('""', '\"')
                start_idx = processed_response.find('[')
                end_idx = processed_response.rfind(']')
                if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                    json_response = processed_response[start_idx:end_idx + 1]
                    try:
                        analyzed_group = json.loads(json_response)
                        
                        # 收集要插入的事件而不是直接插入，避免多线程写入冲突
                        events_to_insert = []
                        theme_event_mapping = []
                        
                        for analyzed_event in analyzed_group:
                            # 处理事件主题中的所有事件（新格式：theme_summary作为主题名称）
                            theme_name = analyzed_event.get('theme_summary', '其他')
                            
                            # 处理event_sequence中的事件（新格式中所有事件都在event_sequence中）
                            event_sequence = analyzed_event.get('event_sequence', [])
                            
                            # 记录当前主题的所有事件ID占位符
                            current_theme_ids = []
                            
                            # 如果event_sequence为空，但分析事件本身包含事件信息，则将其作为单独事件处理
                            if not event_sequence:
                                # 获取开始时间和结束时间，可能是数组
                                start_times = analyzed_event.get('start_time', [])
                                end_times = analyzed_event.get('end_time', [])
                                
                                # 确保start_times和end_times是列表
                                if not isinstance(start_times, list):
                                    start_times = [start_times] if start_times else []
                                if not isinstance(end_times, list):
                                    end_times = [end_times] if end_times else []
                                
                                # 遍历所有发生时间
                                for idx, (start_time_str, end_time_str) in enumerate(zip(start_times, end_times)):
                                    if start_time_str:
                                        try:
                                            event_date = datetime.strptime(start_time_str.split(' ')[0], '%Y-%m-%d')
                                            month_key = f"2025-{event_date.month:02d}"
                                            
                                            # 添加事件到待插入列表
                                            events_to_insert.append({
                                                'month_key': month_key,
                                                'event': {
                                                    'description': analyzed_event.get('description', ''),
                                                    'date': f"{start_time_str}至{end_time_str}",
                                                    'belongs_to_theme': theme_name  # 直接使用theme_summary
                                                },
                                                'event_name': f"{analyzed_event.get('name', '未知事件')} (发生时间 {idx+1})"
                                            })
                                            current_theme_ids.append(0)  # 临时占位符，后续分配实际ID
                                        except Exception as e:
                                            print(f"解析分析后事件时间失败: {str(e)}, 事件: {analyzed_event.get('name', '未知事件')}, 发生时间: {idx+1}")
                            else:
                                # 处理event_sequence中的所有事件
                                for seq_event in event_sequence:
                                    # 获取开始时间和结束时间，可能是数组
                                    start_times = seq_event.get('start_time', [])
                                    end_times = seq_event.get('end_time', [])
                                    
                                    # 确保start_times和end_times是列表
                                    if not isinstance(start_times, list):
                                        start_times = [start_times] if start_times else []
                                    if not isinstance(end_times, list):
                                        end_times = [end_times] if end_times else []
                                    
                                    # 遍历所有发生时间
                                    for idx, (start_time_str, end_time_str) in enumerate(zip(start_times, end_times)):
                                        if start_time_str:
                                            try:
                                                event_date = datetime.strptime(start_time_str.split(' ')[0], '%Y-%m-%d')
                                                month_key = f"2025-{event_date.month:02d}"
                                                
                                                # 添加序列事件到待插入列表
                                                events_to_insert.append({
                                                    'month_key': month_key,
                                                    'event': {
                                                        'description': seq_event.get('description', ''),
                                                        'date': f"{start_time_str}至{end_time_str}",
                                                        'belongs_to_theme': theme_name  # 直接使用theme_summary
                                                    },
                                                    'event_name': f"{seq_event.get('name', '未知事件')} (发生时间 {idx+1})"
                                                })
                                                current_theme_ids.append(0)  # 临时占位符，后续分配实际ID
                                            except Exception as e:
                                                print(f"解析序列事件时间失败: {str(e)}, 事件: {seq_event.get('name', '未知事件')}, 发生时间: {idx+1}")
                            
                            # 如果有事件属于当前主题，记录主题和事件ID占位符
                            if current_theme_ids:
                                theme_event_mapping.append({
                                    'theme_summary': theme_name,
                                    'event_id_placeholders': current_theme_ids
                                })
                    
                        return events_to_insert, theme_event_mapping
                    except json.JSONDecodeError as e:
                            print(f"解析第{group_idx + 1}组分析JSON失败: {str(e)}")
                            #print(f"尝试解析的响应内容: {json_response}")
                            return [], []
                else:
                    print(f"无法从第{group_idx + 1}组分析响应中提取JSON: {response_analyze[:100]}...")
                    return [], []
            
            # 准备带索引的组数据
            indexed_groups = [(i, group) for i, group in enumerate(grouped_events)]
            
            # 使用线程池并行处理所有组
            all_events_to_insert = []
            all_theme_event_mappings = []
            
            with ThreadPoolExecutor(max_workers=min(len(indexed_groups), 8)) as executor:
                # 提交所有任务
                future_to_group = {executor.submit(process_event_group, group_data): group_data[0] 
                                   for group_data in indexed_groups}
                
                # 收集结果
                for future in as_completed(future_to_group):
                    group_idx = future_to_group[future]
                    try:
                        events_batch, theme_mapping_batch = future.result()
                        all_events_to_insert.extend(events_batch)
                        all_theme_event_mappings.extend(theme_mapping_batch)
                        print(f"第{group_idx + 1}组事件处理完成")
                    except Exception as e:
                        print(f"第{group_idx + 1}组事件处理出错: {e}")
            
            # 为所有要插入的事件分配ID并更新主题事件映射
            event_id_mapping = []  # 记录占位符索引到实际ID的映射
            for idx, event_data in enumerate(all_events_to_insert):
                event_id_mapping.append(event_id_counter)
                event_data['event']['id'] = event_id_counter
                
                # 检查是否与events_by_theme中的事件匹配
                event_name = event_data.get('event_name', '').split(' (')[0].strip()  # 去除发生时间后缀
                if events_by_theme:
                    for theme_data in events_by_theme:
                        for theme_event in theme_data.get('events', []):
                            theme_event_name = theme_event.get('name', '').strip()
                            if event_name == theme_event_name:
                                # 如果匹配，记录主题和事件ID
                                theme_name = theme_data.get('theme_name', '未知主题')
                                # 检查是否已有该主题的记录
                                existing_theme = next((item for item in same_theme_arr if item.get('theme_summary') == theme_name), None)
                                if existing_theme:
                                    existing_theme['event_ids'].append(event_id_counter)
                                else:
                                    same_theme_arr.append({
                                        'theme_summary': theme_name,
                                        'event_ids': [event_id_counter]
                                    })
                                break
                        else:
                            continue
                        break
                
                event_id_counter += 1
            
            # 更新主题事件映射中的实际ID
            current_placeholder_idx = 0
            for theme_mapping in all_theme_event_mappings:
                actual_event_ids = []
                for placeholder in theme_mapping['event_id_placeholders']:
                    if current_placeholder_idx < len(event_id_mapping):
                        actual_event_ids.append(event_id_mapping[current_placeholder_idx])
                        current_placeholder_idx += 1
                
                # 将主题和实际事件ID添加到同主题数组
                if actual_event_ids:
                    same_theme_arr.append({
                        'theme_summary': theme_mapping['theme_summary'],
                        'event_ids': actual_event_ids
                    })
            
            # 统一插入所有处理好的事件
            for event_data in all_events_to_insert:
                month_key = event_data['month_key']
                event = event_data['event']
                event_name = event_data['event_name']
                
                # 查找对应的月份索引并插入事件
                month_found = False
                for i, month_detail in enumerate(updated_timeline.get('monthly_details', [])):
                    if month_detail.get('month') == month_key:
                        updated_timeline['monthly_details'][i]['events'].append(event)
                        print(f"已将事件 '{event_name}' 插入到{month_key}")
                        processed_events += 1
                        month_found = True
                        break
                
                if not month_found:
                    print(f"警告：未找到{month_key}的数据，无法插入事件")
            
            print(f"事件生成和插入完成！第一轮直接插入{len(generated_events_round1)}个事件，筛选分析后插入{processed_events}个事件")
            
            # 构造返回结果
            result = {
                'updated_timeline': updated_timeline,
                'same_theme_arr': same_theme_arr,
                'frequency_id_groups': frequency_id_groups
            }
            
            return result
            
        except Exception as e:
            print(f"生成和插入事件过程中出错: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'updated_timeline': timeline_data, 'same_theme_arr': [], 'frequency_id_groups': []}

    def optimize_events_by_category(self, month, events, persona, calendar_data):
        """
        按事件类别优化事件的方法

        参数:
            month: 月份（如"1月"）
            events: 原始事件列表
            persona: 人物画像数据
            calendar_data: 日历数据

        返回:
            优化后的事件列表
        """
        import csv
        import os
        from event.template_s import (
            category_definitions,
            template_career_optimization,
            template_education_optimization,
            template_relationships_optimization,
            template_family_living_optimization,
            template_personal_life_optimization,
            template_finance_optimization,
            template_health_optimization
        )
        
        # 读取event_schema.csv文件，获取各类别的事件参考
        schema_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'event_schema.csv')
        category_schema = {}
        
        try:
            import csv
            with open(schema_file_path, 'r', encoding='utf-8-sig', newline='') as f:
                csv_reader = csv.reader(f)
                rows = list(csv_reader)
                if len(rows) > 1:  # 确保文件至少有标题行和一行数据
                    # 跳过标题行，从第二行开始处理
                    previous_category = ""  # 保存上一个非空的类别
                    for row in rows[1:]:
                        if len(row) >= 4:
                            # 检查是否是空行或只有逗号的行
                            if not any(cell.strip() for cell in row):
                                continue
                            
                            # 如果当前行类别为空，则使用上一个非空类别
                            current_category = row[0].strip()
                            if current_category:
                                previous_category = current_category
                            else:
                                current_category = previous_category
                            
                            if current_category:  # 确保类别有效
                                if current_category not in category_schema:
                                    category_schema[current_category] = []
                                
                                stage_event = row[1].strip()
                                atomic_event = row[2].strip()
                                behavior = row[3].strip()
                                
                                if stage_event or atomic_event or behavior:
                                    category_schema[current_category].append({
                                        'stage_event': stage_event,
                                        'atomic_event': atomic_event,
                                        'behavior': behavior
                                    })
        except Exception as e:
            print(f"读取event_schema.csv文件时出错: {e}")
            # 如果读取失败，使用空的事件参考
            category_schema = {}

        # 打印category_schema内容进行调试
        print("\ncategory_schema构建结果:")
        for key in category_schema:
            print(f"- {key}: {len(category_schema[key])}个事件参考")
        print("\n")
        
        # 事件类别到模板的映射（只保留7个主要类别）
        category_to_template = {
            "Health": template_health_optimization,
            "Career": template_career_optimization,
            "Education": template_education_optimization,
            "Relationships": template_relationships_optimization,
            "Family&Living Situation": template_family_living_optimization,
            "Personal Life": template_personal_life_optimization,
            "Finance": template_finance_optimization,
        }

        # 准备通用参数
        all_events_json = json.dumps(events, ensure_ascii=False)
        persona_data_str = json.dumps(persona, ensure_ascii=False)
        
        # 并行处理每个类别的函数
        def process_category(category, template):
            print(f"调用LLM从{category}类别角度优化{month}的事件...")
            
            # 获取类别定义
            category_definition = category_definitions.get(category, "")
            
            try:
                # 获取当前类别的事件参考
                category_reference = category_schema.get(category, [])
                category_reference_json = json.dumps(category_reference, ensure_ascii=False)
                print(f"{category}类别参考数据: {category_reference}")
                
                # 格式化提示词
                prompt = template.format(
                    month=month,
                    category=category,
                    category_definition=category_definition,
                    original_events=all_events_json,
                    profile_data=persona_data_str,
                    calendar_data=calendar_data,
                    category_reference=category_reference_json
                )
                
                # 调用LLM进行优化
                category_result = self.llm_call_s(prompt)
                #print(f"LLM返回的{category}类别优化结果: {category_result}")
                
                # 解析优化结果，先提取JSON部分（第一个{到最后一个}）
                try:
                    # 找到第一个{和最后一个}的位置
                    first_brace = category_result.find('{')
                    last_brace = category_result.rfind('}')
                    if first_brace != -1 and last_brace != -1 and first_brace < last_brace:
                        # 提取JSON部分
                        json_str = category_result[first_brace:last_brace+1]
                        category_result_json = json.loads(json_str)
                    else:
                        # 如果没有找到有效的JSON结构，尝试直接解析
                        category_result_json = json.loads(category_result)
                except json.JSONDecodeError as e:
                    # 如果直接解析也失败，打印错误并跳过这个类别的优化
                    print(f"解析{category}类别优化结果失败: {str(e)}")
                    return []
                
                # 所有类别使用相同的处理逻辑：处理操作序列数组
                # 直接使用解析后的数组作为操作序列
                if isinstance(category_result_json, list):
                    operations = category_result_json
                else:
                    # 获取操作序列数组
                    operations = category_result_json.get("operations", [])
                
                print(f"{category}类别操作序列处理完成，共{len(operations)}个操作")
                return operations
            except Exception as e:
                print(f"处理{category}类别时发生错误: {str(e)}")
                return []
        
        # 使用多线程并行处理所有类别
        import concurrent.futures
        all_operations = []
        
        print(f"开始并行处理{len(category_to_template)}个类别...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(category_to_template)) as executor:
            # 提交所有任务
            future_to_category = {
                executor.submit(process_category, category, template): category 
                for category, template in category_to_template.items()
            }
            
            # 收集结果
            for future in concurrent.futures.as_completed(future_to_category):
                category = future_to_category[future]
                try:
                    category_operations = future.result()
                    all_operations.extend(category_operations)
                    print(f"成功获取{category}类别的{len(category_operations)}个操作")
                except Exception as e:
                    print(f"获取{category}类别操作时发生错误: {str(e)}")
        
        print(f"所有类别并行处理完成，共收集{len(all_operations)}个操作")
        
        # 创建操作分析提示词，让LLM决定保留哪些操作
        print(f"让LLM分析操作序列并决定保留哪些操作...")
        
        # 构建分析提示词
        operations_analysis_prompt = f'''
        请基于以下人物画像、该月已有原事件数据和收集到对原数据修改的建议操作序列，分析并决定保留哪些操作。
        
        人物画像：{json.dumps(persona, ensure_ascii=False)}
        
        该月已有原事件数据：{json.dumps(events, ensure_ascii=False)}
        
        收集到的操作序列：{json.dumps(all_operations, ensure_ascii=False)}
        
        操作类型说明：
        1. **add**（添加操作）：
           - 向事件列表中添加新的事件
           - 格式：{{"type": "add", "event": {{事件详细信息}}}}
           - 作用：补充缺失的事件或丰富事件数据
        
        2. **delete**（删除操作）：
           - 从事件列表中删除指定名称的事件
           - 格式：{{"type": "delete", "event_name": "事件名称"}}
           - 作用：移除冗余、错误或不合理的事件
        
        3. **rewrite**（重写操作）：
           - 修改事件列表中指定名称的事件内容
           - 格式：{{"type": "rewrite", "event_name": "事件名称", "event": {{新的事件详细信息}}}}
           - 作用：修正事件信息、更新事件内容或优化事件描述
        
        分析要求：
        1. **评估操作与原事件数据的冲突**：
           - 检查每个操作所修改的事件是否与原事件数据存在冲突（如时间冲突、内容矛盾等）
           - 若操作与原事件数据冲突，优先依据原事件数据，摒弃该操作。
        
        2. **检查操作之间的冲突**：
           - 识别操作序列中相互冲突的操作（如对同一事件的不同修改）
           - 评估冲突操作的优先级，保留更合理、更必要的操作
        
        3. **评估操作的合理性和必要性**：
           - 操作是否符合原事件的整体逻辑和发展脉络
           - 操作是否能提升事件数据的完整性和合理性多样性。
           - 避免保留冗余、不必要或与原事件主旨不符的操作
           - 考虑新增事件是否合理，是否符合原事件的发展脉络，是否重复，是否导致某时间事件过多
           - 评估该月已有事件密度，避免新增事件安排过多导致该月份的事件安排过密
           - **避免新增与已有事件相似的事件**：检查新增事件与已有事件的名称、描述、类型是否高度相似，若存在高度相似的事件，应摒弃新增操作
           - **新增事件需保持主题多样性**：检查拟保留的新增事件之间的主题是否相似，避免添加多个主题重复或高度相似的事件（如避免添加多个学习类、工作类或休闲类事件），确保新增事件能够丰富人物的活动类型，提供多样化的生活体验
           - **考虑个人化特点进行事件类型取舍**：根据人物画像的职业、身份、经济状况等特征，合理调整事件类型的比例：
             * 若人物是工作者（如职场人士、上班族），应适当减少学习类事件的比例
             * 若人物是学生（如在校学生、研究生），应适当减少工作类事件的比例
             * 若人物经济状况较差（如低收入群体、贫困人口），应适当减少消费类事件的比例
             * 其他个人化特征也应作为参考，确保事件类型与人物身份、生活状态相符
           
        4. **优先级规则**：
           - 原事件数据优先级高于新操作
           - 重要事件的操作优先级高于次要事件
           - 能增强事件连贯性和合理性的操作优先级更高
           - 解决明显矛盾或错误的操作优先级更高
           - 符合并体现人物画像特征的事件类型优先级更高
           
        
        输出要求：
        请以JSON格式输出需要保留的操作序列，格式与输入的操作序列完全一致。
        只输出JSON内容，不要添加任何额外的文本、注释或格式。
        严格遵循JSON格式规范，在JSON字符串值中避免使用双引号，如果需要表示引号，请使用[]或其他替代符号，或者使用转义字符\\"，只输出JSON对象，不要输出任何额外的文本或注释。以[]开头。
        重要限制：
        1. **新增的事件（add操作）总数不得超过7个，一个月的事件总数不得超过25个。**
        2. 在满足限制的前提下，优先保留最重要的事件
        3. 如果超过限制，选择性保留最符合上下文、逻辑和人物画像特征的事件
        '''
        
        # 调用LLM分析操作序列
        retained_operations_result = self.llm_call_sr(operations_analysis_prompt)
        #print(f"LLM返回的保留操作序列: {retained_operations_result}")
        
        # 在解析JSON之前，先匹配第一个[和最后一个]
        import re
        bracket_pattern = r'\[(.*)\]'
        matches = re.findall(bracket_pattern, retained_operations_result, re.DOTALL)
        if matches:
            # 取第一个[到最后一个]之间的内容
            json_content = f"[{matches[0]}]"
        else:
            # 如果没有找到[], 则使用原始内容
            json_content = retained_operations_result
        
        # 解析LLM返回的结果，获取保留的操作
        try:
            retained_operations = json.loads(json_content)
            if not isinstance(retained_operations, list):
                # 如果返回的不是列表，尝试从JSON中提取operations字段
                retained_operations = retained_operations.get("operations", [])
            print(f"LLM决定保留{len(retained_operations)}个操作")
        except json.JSONDecodeError as e:
            print(f"解析保留操作序列失败: {str(e)}")
            # 如果解析失败，使用所有操作
            retained_operations = all_operations
            print(f"解析失败，使用所有操作")
        
        # 执行LLM保留的操作
        optimized_events = events.copy()
        
        print(f"开始执行LLM保留的操作...")
        for op in retained_operations:
            action = op.get("action", "")
            
            if action == "add":
                # 直接添加事件到数组，新增事件id为0
                event = op.get("event", {})
                if event and "name" in event:
                    event["id"] = 0  # 新增事件id为0
                    optimized_events.append(event)
                    print(f"执行add操作：添加事件'{event['name']}'，id=0")
                else:
                    print(f"add操作事件信息不完整，跳过")
            
            elif action == "delete":
                # 从原数组匹配名字删除事件
                delete_event = op.get("event", {})
                delete_name = delete_event.get("name", "")
                if delete_name:
                    # 找到所有匹配名称的事件并删除
                    original_length = len(optimized_events)
                    optimized_events = [e for e in optimized_events if e.get("name", "") != delete_name]
                    deleted_count = original_length - len(optimized_events)
                    if deleted_count > 0:
                        print(f"执行delete操作：删除{deleted_count}个名为'{delete_name}'的事件")
                    else:
                        print(f"delete操作：未找到名为'{delete_name}'的事件，跳过")
                else:
                    print(f"delete操作事件名称缺失，跳过")
            
            elif action == "rewrite":
                # 匹配名字重写事件
                original_event = op.get("original_event", {})
                original_name = original_event.get("name", "")
                new_event = op.get("new_event", {})
                
                if original_name and new_event and "name" in new_event:
                    # 找到第一个匹配名称的事件并替换
                    found = False
                    for i, e in enumerate(optimized_events):
                        if e.get("name", "") == original_name:
                            # 保留原始事件的id，赋值给新事件
                            original_id = e.get("id", 0)
                            new_event["id"] = original_id
                            optimized_events[i] = new_event
                            print(f"执行rewrite操作：将事件'{original_name}'重写为'{new_event['name']}'，保留原id={original_id}")
                            found = True
                            break
                    if not found:
                        print(f"rewrite操作：未找到名为'{original_name}'的事件，跳过")
                else:
                    print(f"rewrite操作事件信息不完整，跳过")
            
            else:
                print(f"未知操作类型：{action}，跳过")
        
        print(f"所有保留操作执行完成，最终事件数：{len(optimized_events)}")
        final_optimized_events = optimized_events

        return final_optimized_events

    def process_single_month(self, month_data):
            """
            处理单个月数据的内部方法

            参数:
                month_data: 单个月的数据，可能包含profile_changes_context字段

            返回:
                优化后的单个月数据
            """
            from event.template_s import template_monthly_analysis, category_definitions
            import re
            import json

            month = month_data["month"]
            print(f"\n开始处理{month}的事件...")

            # 生成这个月的日历数据
            # 从"YYYY-MM"格式解析月份数字
            month_num = int(month.split('-')[1])
            # 使用现有的get_month_calendar方法获取日历数据
            calendar_data = self.get_month_calendar(2025, month_num)

            # 第一步：调用LLM分析这个月的事件，给出修改建议
            monthly_data_str = json.dumps(month_data, ensure_ascii=False)
            persona_data_str = json.dumps(self.persona, ensure_ascii=False)

            # 确保每个事件都有id字段
            for event in month_data["events"]:
                if "id" not in event:
                    event["id"] = 0  # 如果没有id，默认为0
            
            # 提取id数组
            event_ids = [event["id"] for event in month_data["events"]]
            
            # 获取profile_changes_context，如果不存在则设为空数组的JSON字符串
            profile_changes_context = month_data.get("profile_changes_context", [])
            profile_changes_context_str = json.dumps(profile_changes_context, ensure_ascii=False)
            
            # 获取previous_month_final_status，如果不存在则设为空对象的JSON字符串
            previous_month_final_status = month_data.get("previous_month_final_status", {})
            previous_month_final_status_str = json.dumps(previous_month_final_status, ensure_ascii=False)
            
            prompt_analysis = template_monthly_analysis.format(
                month=month,
                monthly_data=monthly_data_str,
                persona_data=persona_data_str,
                calendar_data=calendar_data,
                event_ids=event_ids,
                profile_changes_context=profile_changes_context_str,
                previous_month_final_status=previous_month_final_status_str
            )
            print(monthly_data_str)
            print(f"调用LLM分析{month}的事件...")
            analysis_result = self.llm_call_sr(prompt_analysis)
            #print(f"LLM返回的优化建议: {analysis_result}")
            # 解析LLM返回的结果
            try:
                # 提取第一个{到最后一个}之间的有效JSON内容
                start_idx = analysis_result.find('{')
                end_idx = analysis_result.rfind('}')
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    valid_json_str = analysis_result[start_idx:end_idx+1]
                    analysis_result_json = json.loads(valid_json_str)
                else:
                    print(f"无法从分析结果中提取有效JSON")
                    raise json.JSONDecodeError("Invalid JSON format", analysis_result, 0)
                optimized_events = analysis_result_json.get("events", month_data["events"])
                
                # 添加事件完整性检查
                print(f"\n事件完整性检查：")
                print(f"输入事件数量：{len(month_data['events'])}")
                print(f"输出事件数量：{len(optimized_events)}")

                # 检查所有输入事件ID是否在输出中出现
                input_event_ids = set(event_ids)
                output_event_ids = set(event["id"] for event in optimized_events if event["id"] != 0)

                # 找出缺失的事件ID
                missing_event_ids = input_event_ids - output_event_ids
                if missing_event_ids:
                    print(f"警告：发现缺失的事件ID：{missing_event_ids}")
                    print(f"输入事件ID列表：{input_event_ids}")
                    print(f"输出事件ID列表：{output_event_ids}")

                    # 获取缺失的事件详情
                    # missing_events = [event for event in month_data["events"] if event["id"] in missing_event_ids]
                    # print(f"缺失的事件详情：{missing_events}")


            except json.JSONDecodeError:
                print(f"解析{month}的LLM分析结果失败，使用原始事件")
                optimized_events = month_data["events"]

            print(f"完成{month}的事件分析，最终事件：{optimized_events}")

            # 第二步：按9个事件类别进行优化
            print(f"开始按9个事件类别优化{month}的事件...")
            final_optimized_events = self.optimize_events_by_category(
                month=month,
                events=optimized_events,
                persona=self.persona,
                calendar_data=calendar_data
            )
            print(f"完成{month}的事件类别优化")

            # 更新该月的事件
            optimized_month_data = final_optimized_events
            print(f"更新{month}的事件为：{optimized_month_data}")
            
            print(f"{month}的事件处理完成")
            
            # 返回最终优化后的单个月数据
            return {
                "month": month,
                "events": optimized_month_data
            }

    def monthly_event_planning(self, timeline_data):
        """
        月度事件规划与分析整合方法（串行处理每个月的数据）

        参数:
            timeline_data: 时间线数据（gi.json格式）

        返回:
            优化后的月度事件数据和分析结果
        """
        import json
        import os
        from datetime import datetime
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import event.event_refiner

        # 检查输入数据格式
        if not isinstance(timeline_data, dict) or 'monthly_details' not in timeline_data:
            raise ValueError("输入数据格式错误，缺少'monthly_details'字段")

        # 初始化EventRefiner实例
        refiner = event.event_refiner.EventRefiner(self.persona, {})

        optimized_timeline = {
            "category": timeline_data.get("category", "综合事件"),
            "comprehensive_summary": timeline_data.get("comprehensive_summary", ""),
            "monthly_details": [],
            "analysis_results": {}  # 新增分析结果字段
        }

        # 支持"X月"和"2025-XX"格式
        def get_month_num(month_str):
            if "月" in month_str:
                return int(month_str.replace("月", ""))
            elif "-" in month_str:
                return int(month_str.split("-")[1])
            else:
                return 13  # 默认值，确保无法解析的月份排在最后
        
        # 按月份顺序排序
        sorted_month_details = sorted(timeline_data["monthly_details"], key=lambda x: get_month_num(x["month"]))

        # 串行处理每个月的数据
        results = []
        previous_analysis = None
        
        for month_data in sorted_month_details:
            month = month_data["month"]
            print(f"\n开始处理{month}的数据...")
            
            # 准备事件规划的输入数据
            # 如果有前一个月的分析结果，提取profile_changes和final_day_status作为背景
            if previous_analysis and 'transition_analysis' in previous_analysis:
                prev_transition_analysis = previous_analysis['transition_analysis']
                # 将profile_changes添加到month_data中作为背景信息
                month_data['profile_changes_context'] = prev_transition_analysis.get('profile_changes', [])
                # 将final_day_status添加到month_data中作为背景信息
                month_data['previous_month_final_status'] = prev_transition_analysis.get('final_day_status', {})
                print(f"使用前一个月的profile_changes和final_day_status作为{month}的背景信息")
            
            # 处理单个月的事件规划
            result = self.process_single_month(month_data)
            
            # # 将每个月的原始结果保存到record文件中
            # record_dir = os.path.join(os.path.dirname(__file__), '../output/new/refine')
            # os.makedirs(record_dir, exist_ok=True)
            #
            # # 生成唯一的record文件名
            # timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]  # 包含毫秒的时间戳
            # record_filename = f"record_{month.replace('-', '_')}_{timestamp}.json"
            # record_filepath = os.path.join(record_dir, record_filename)
            #
            # # 保存原始结果到record文件
            # with open(record_filepath, 'w', encoding='utf-8') as f:
            #     json.dump(result, f, ensure_ascii=False, indent=2)
            # print(f"{month}的原始数据已保存到: {record_filepath}")
            
            results.append(result)
            print(f"{month}的事件规划完成")
            
            # 调用分析函数进行健康、生活和转换分析
            print(f"开始分析{month}的事件...")
            
            # 准备初始状态数据
            initial_health_state = None
            if previous_analysis and 'health_analysis' in previous_analysis:
                try:
                    prev_health_data = previous_analysis['health_analysis']
                    initial_health_state = prev_health_data.get('end_of_month_state')
                    if initial_health_state:
                        print(f"使用上个月的健康最终状态作为{month}月份的初始状态")
                except Exception as e:
                    print(f"解析上个月健康状态时出错: {e}")
            
            initial_life_state = None
            if previous_analysis and 'life_analysis' in previous_analysis:
                initial_life_state = previous_analysis['life_analysis'].get('final_state')
                if initial_life_state:
                    print(f"使用上个月的生活最终状态作为{month}月份的初始状态")
            
            prev_transition_analysis = previous_analysis['transition_analysis'] if previous_analysis and 'transition_analysis' in previous_analysis else None
            
            # 并行调用分析函数
            with ThreadPoolExecutor(max_workers=12) as executor:
                # 提交所有分析任务
                future_health = executor.submit(refiner.health_analysis, result, self.persona, initial_state=initial_health_state)
                future_life = executor.submit(refiner.life_analysis, result, self.persona, initial_state=initial_life_state)
                future_transition = executor.submit(refiner.month_transition_analysis, result, self.persona, previous_analysis=prev_transition_analysis)
                
                # 获取分析结果
                health_result = future_health.result()
                life_result = future_life.result()
                transition_result = future_transition.result()
                
            print(f"{month}的所有分析任务已完成")
            
            # 保存本月的分析结果
            month_analysis_results = {
                'month': month,
                'health_analysis': health_result,
                'life_analysis': life_result,
                'transition_analysis': transition_result
            }
            
            # 添加到分析结果字典
            optimized_timeline['analysis_results'][month] = month_analysis_results
            
            # 更新previous_analysis为当前月份的所有分析结果
            previous_analysis = {
                'health_analysis': health_result,
                'life_analysis': life_result,
                'transition_analysis': transition_result
            }

        # 为所有id为0的事件统一分配新id（从全年最大id开始递增）
        all_events = []
        for month_data in results:
            all_events.extend(month_data["events"])
        
        if len(all_events) > 0:
            # 找到全年最大id
            max_id = max(event.get("id", 0) for event in all_events)
            
            # 为所有id=0的事件重新赋值
            for month_data in results:
                for event in month_data["events"]:
                    if event.get("id", 0) == 0:
                        max_id += 1
                        event["id"] = max_id
                        print(f"为新增事件'{event.get('name', '')}'分配新id: {max_id}")
        
        optimized_timeline["monthly_details"] = results

        # # 保存分析结果
        # output_dir = os.path.join(os.path.dirname(__file__), '../analysis_results')
        # os.makedirs(output_dir, exist_ok=True)
        
        # # 保存所有月份的综合分析结果
        # all_results_file = os.path.join(output_dir, f"all_months_analysi.json")
        # with open(all_results_file, 'w', encoding='utf-8') as f:
        #     json.dump(optimized_timeline['analysis_results'], f, ensure_ascii=False, indent=2)
        # print(f"\n所有月份分析结果已保存到: {all_results_file}")

        # # 保存最终调整过ID的完整结果
        # final_output_dir = os.path.join(os.path.dirname(__file__), '../output/new')
        # os.makedirs(final_output_dir, exist_ok=True)
        
        # final_output_file = os.path.join(final_output_dir, f"final_monthly_planning_{datetime.now().strftime('%Y%m%d%H%M%S')}.json")
        # with open(final_output_file, 'w', encoding='utf-8') as f:
        #     json.dump(optimized_timeline, f, ensure_ascii=False, indent=2)
        # print(f"\n最终调整过ID的月度规划结果已保存到: {final_output_file}")

        return optimized_timeline
    def process_monthly_details(self, monthly_details_data, output_file_prefix):
        """
        处理monthly_details格式的数据，对事件进行分组并调用EventTree类进行事件分解

        参数:
            monthly_details_data: 包含monthly_details字段的数组格式数据
            output_file_prefix: 输出文件的前缀

        返回:
            Dict: 分解后的事件树结构
        """
        if not isinstance(monthly_details_data, list):
            raise ValueError("输入数据格式错误，monthly_details应为数组格式")

        # 将所有月份的事件合并到一个列表中
        all_events = []

        for month_data in monthly_details_data:
            if not isinstance(month_data, dict) or 'events' not in month_data:
                continue

            for event in month_data['events']:
                # 确保每个事件都有必要的字段
                if isinstance(event, dict):
                    # 保留事件原有的event_id
                    event_copy = event.copy()

                    # 将id字段替换为event_id
                    if 'id' in event_copy:
                        event_copy['event_id'] = event_copy.pop('id')
                    # 如果没有id字段，确保event_id字段存在
                    event_copy.setdefault('event_id', 0)

                    # 确保所有必要字段都存在
                    event_copy.setdefault('name', '未命名事件')
                    event_copy.setdefault('description', '')
                    event_copy.setdefault('type', 'Other')
                    event_copy.setdefault('date', [])

                    all_events.append(event_copy)

        print(f"共处理{len(all_events)}个事件")

        # 创建EventTree实例并调用事件分解函数
        event_tree = EventTree(self.persona)
        event_tree.event_decomposer(all_events, output_file_prefix, max_workers=self.decompose_workers)

        return event_tree.decompose_schedule
    def generate_yearly_timeline_draft(self, persona, output_path="output/", meidan_path=None):
        """
        生成年度时间线草稿（优化版：添加错误处理和输出保存）

        参数:
            persona: 人物画像数据
            output_path: 每日状态数据输出路径
            meidan_path: 除每日状态外的其他数据输出路径

        返回:
            生成的年度时间线草稿数据，或在发生错误时返回None
        """
        import os
        import json
        import traceback
        from datetime import datetime

        # 如果meidan_path未指定，使用output_path加process文件夹
        if meidan_path is None:
            meidan_path = os.path.join(output_path, 'process')
        
        # 确保输出路径存在
        os.makedirs(output_path, exist_ok=True)
        os.makedirs(meidan_path, exist_ok=True)

        try:
            # 步骤1: 提取重要节点
            print("\n=== 步骤1: 提取重要节点 ===")
            important_nodes_path = os.path.join(meidan_path, "important_nodes.json")
            if os.path.exists(important_nodes_path):
                print(f"✓ 重要节点文件已存在，直接读取: {important_nodes_path}")
                with open(important_nodes_path, 'r', encoding='utf-8') as f:
                    important_nodes = json.load(f)
            else:
                important_nodes = self.extract_important_nodes(persona=persona)
                print(f"✓ 成功提取{len(important_nodes)}个重要节点")
                # 保存结果
                with open(important_nodes_path, 'w', encoding='utf-8') as f:
                    json.dump(important_nodes, f, ensure_ascii=False, indent=2)
                print(f"✓ 重要节点已保存到: {important_nodes_path}")

            # 步骤2: 生成事件时间线
            print("\n=== 步骤2: 生成事件时间线 ===")
            event_timelines_path = os.path.join(meidan_path, "event_timelines.json")
            if os.path.exists(event_timelines_path):
                print(f"✓ 事件时间线文件已存在，直接读取: {event_timelines_path}")
                with open(event_timelines_path, 'r', encoding='utf-8') as f:
                    event_timelines = json.load(f)
            else:
                event_timelines = self.generate_event_timeline(important_nodes, max_workers=12)
                print(f"✓ 成功生成{len(event_timelines)}个事件时间线")
                # 保存结果
                with open(event_timelines_path, 'w', encoding='utf-8') as f:
                    json.dump(event_timelines, f, ensure_ascii=False, indent=2)
                print(f"✓ 事件时间线已保存到: {event_timelines_path}")

            # 步骤3: 合并相似时间线
            print("\n=== 步骤3: 合并相似时间线 ===")
            merged_timelines_path = os.path.join(meidan_path, "merged_timelines.json")
            if os.path.exists(merged_timelines_path):
                print(f"✓ 合并后的时间线文件已存在，直接读取: {merged_timelines_path}")
                with open(merged_timelines_path, 'r', encoding='utf-8') as f:
                    merged_timelines = json.load(f)
            else:
                merged_timelines = self.merge_similar_timelines(event_timelines)
                print(f"✓ 成功合并为{len(merged_timelines)}个时间线")
                # 保存结果
                with open(merged_timelines_path, 'w', encoding='utf-8') as f:
                    json.dump(merged_timelines, f, ensure_ascii=False, indent=2)
                print(f"✓ 合并后的时间线已保存到: {merged_timelines_path}")

            # 步骤4: 优化合并后的时间线
            print("\n=== 步骤4: 优化合并后的时间线 ===")
            optimized_timelines_path = os.path.join(meidan_path, "optimized_timelines.json")
            if os.path.exists(optimized_timelines_path):
                print(f"✓ 优化后的时间线文件已存在，直接读取: {optimized_timelines_path}")
                with open(optimized_timelines_path, 'r', encoding='utf-8') as f:
                    optimized_timelines = json.load(f)
                # 仍然需要执行convert_timeline_to_events_with_llm
                optimized_timelines = self.convert_timeline_to_events_with_llm(optimized_timelines)
            else:
                optimized_timelines = self.optimize_merged_timelines(merged_timelines)
                print(f"✓ 成功优化为{len(optimized_timelines)}个时间线")
                # 保存结果
                with open(optimized_timelines_path, 'w', encoding='utf-8') as f:
                    json.dump(optimized_timelines, f, ensure_ascii=False, indent=2)
                print(f"✓ 优化后的时间线已保存到: {optimized_timelines_path}")
                optimized_timelines = self.convert_timeline_to_events_with_llm(optimized_timelines)

            # 步骤5: 生成并插入事件
            print("\n=== 步骤5: 生成并插入事件 ===")
            rich_timeline_path = os.path.join(meidan_path, "rich_timeline.json")
            if os.path.exists(rich_timeline_path):
                print(f"✓ 丰富后的时间线文件已存在，直接读取: {rich_timeline_path}")
                with open(rich_timeline_path, 'r', encoding='utf-8') as f:
                    rich_timeline = json.load(f)
            else:
                rich_timeline = self.generate_and_insert_events(optimized_timelines["timeline_data"],optimized_timelines["events_by_theme"])
                print(f"✓ 成功生成并插入事件")
                # 保存结果
                with open(rich_timeline_path, 'w', encoding='utf-8') as f:
                    json.dump(rich_timeline, f, ensure_ascii=False, indent=2)
                print(f"✓ 丰富后的时间线已保存到: {rich_timeline_path}")

            # 步骤6: 月度事件规划
            print("\n=== 步骤6: 月度事件规划 ===")
            final_timeline_path = os.path.join(meidan_path, "final_timeline.json")
            if os.path.exists(final_timeline_path):
                print(f"✓ 最终时间线文件已存在，直接读取: {final_timeline_path}")
                with open(final_timeline_path, 'r', encoding='utf-8') as f:
                    final_timeline = json.load(f)
            else:
                final_timeline = self.monthly_event_planning(rich_timeline["updated_timeline"])
                print(f"✓ 成功完成月度事件规划")
                # 保存结果
                with open(final_timeline_path, 'w', encoding='utf-8') as f:
                    json.dump(final_timeline, f, ensure_ascii=False, indent=2)
                print(f"✓ 最终时间线已保存到: {final_timeline_path}")
            #步骤7: 处理月度详情
            print("\n=== 步骤7: 处理月度详情 ===")
            event_tree_path = os.path.join(meidan_path, "event_decompose_dfs.json")
            if os.path.exists(event_tree_path):
                print(f"✓ 月度详情文件已存在，直接读取: {event_tree_path}")
                with open(event_tree_path, 'r', encoding='utf-8') as f:
                    monthly_details = json.load(f)
            else:
                self.process_monthly_details(final_timeline['monthly_details'], meidan_path)
                print(f"✓ 成功处理月度详情")
                with open(event_tree_path, 'r', encoding='utf-8') as f:
                    monthly_details = json.load(f)
            # 步骤8: 生成每日状态
            print("\n=== 步骤8: 生成每日状态 ===")
            daily_draft_file = os.path.join(output_path, 'daily_draft.json')
            if os.path.exists(daily_draft_file):
                print(f"✓ 每日状态文件已存在，跳过生成: {daily_draft_file}")
            else:
                self.parallel_daily_event_refine(final_timeline["analysis_results"],self.persona,monthly_details,daily_draft_file)
                print(f"✓ 每日状态已保存到: {daily_draft_file}")

            print("\n🎉 年度时间线草稿生成完成！")
            print(f"除每日状态外的其他数据已保存到: {meidan_path}")
            print(f"每日状态数据已保存到: {daily_draft_file}")



        except Exception as e:
            print(f"\n❌ 生成年度时间线草稿时发生错误: {str(e)}")
            traceback.print_exc()
            
            # 保存错误信息到文件
            error_info = {
                "error": str(e),
                "traceback": traceback.format_exc(),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            error_path = os.path.join(meidan_path, "error_log.json")
            with open(error_path, 'w', encoding='utf-8') as f:
                json.dump(error_info, f, ensure_ascii=False, indent=2)
            print(f"❌ 错误信息已保存到: {error_path}")
            
            return None
    
    def monthly_analysis(self, timeline=None, persona=None, output_dir=None):
        """
        串行生成每个月的健康分析数据、生活分析数据、月度转换分析数据并保存
        
        参数:
            timeline: rich_timeline格式的数据，参考rich_timeline.json格式
            persona: 人物画像信息
            output_dir: 分析结果保存目录
        
        返回:
            包含所有月份分析结果的字典
        """
        import event.event_refiner
        import json
        import os
        from datetime import datetime
        
        # 初始化EventRefiner实例
        refiner = event.event_refiner.EventRefiner(persona,{})
        
        # 存储所有月份的分析结果
        all_analysis_results = {}
        
        # 处理输入参数
        # 验证timeline参数格式
        if not timeline or not isinstance(timeline, dict) or 'monthly_details' not in timeline:
            print("timeline必须是有效的rich_timeline格式数据，包含'monthly_details'字段")
            return all_analysis_results
        
        # 将rich_timeline格式转换为timeline格式
        rich_timeline = timeline
        timeline = []
        for month_data in rich_timeline.get('monthly_details', []):
            month_str = month_data.get('month', '')
            # 假设年份为2025，将"1月"转换为"2025-01"格式
            if month_str and '月' in month_str:
                month_num = int(month_str.replace('月', ''))
                month_key = f"2025-{month_num:02d}"
                
                # 提取事件数据
                events = month_data.get('events', [])
                
                # 构建timeline元素
                timeline_item = {
                    'month': month_key,
                    'events': events
                }
                timeline.append(timeline_item)
        
        print(f"成功转换 {len(timeline)} 个月的数据")
        
        # 验证转换后的timeline参数
        if not timeline or not isinstance(timeline, list):
            print("timeline必须包含有效的'monthly_details'数据")
            return all_analysis_results
            
        if not persona or not isinstance(persona, dict):
            print("persona必须是有效的人物画像字典")
            return all_analysis_results
            
        # 设置保存目录
        if output_dir and isinstance(output_dir, str):
            # 如果提供了保存目录参数，使用该目录
            output_dir = os.path.abspath(output_dir)
        else:
            # 否则使用默认目录
            output_dir = os.path.join(os.path.dirname(__file__), '../analysis_results')
            
        # 创建保存目录
        os.makedirs(output_dir, exist_ok=True)
        print(f"分析结果将保存到: {output_dir}")
        
        # 将timeline数组转换为字典格式，方便处理
        monthly_data = {}
        for month_item in timeline:
            if not isinstance(month_item, dict) or 'month' not in month_item:
                print("timeline中的元素必须包含'month'字段")
                continue
                
            month_key = month_item['month']
            monthly_data[month_key] = month_item
            
        print(f"成功加载 {len(monthly_data)} 个月的事件数据")
        
        # 如果没有获取到有效数据，返回空结果
        if not monthly_data:
            print("没有获取到有效的月度事件数据")
            return all_analysis_results
        
        # 遍历每个月的数据
        previous_analysis = None
        from concurrent.futures import ThreadPoolExecutor
        
        for month, month_data in sorted(monthly_data.items()):
            print(f"\n开始分析 {month} 月份的数据...")
            print(month_data)
            # 确保month_data包含必要的字段
            if not isinstance(month_data, dict) or 'events' not in month_data:
                print(f"{month} 月份数据格式不正确，跳过")
                continue
            
            # 准备初始状态数据
            initial_health_state = None
            if previous_analysis and 'health_analysis' in previous_analysis:
                try:
                    # 解析上个月的健康分析结果
                    import json
                    prev_health_data = json.loads(previous_analysis['health_analysis'])
                    initial_health_state = prev_health_data.get('end_of_month_state')
                    if initial_health_state:
                        print(f"使用上个月的健康最终状态作为 {month} 月份的初始状态")
                except Exception as e:
                    print(f"解析上个月健康状态时出错: {e}")
            
            initial_life_state = None
            if previous_analysis and 'life_analysis' in previous_analysis:
                initial_life_state = previous_analysis['life_analysis'].get('final_state')
                if initial_life_state:
                    print(f"使用上个月的生活最终状态作为 {month} 月份的初始状态")
            
            prev_transition_analysis = previous_analysis['transition_analysis'] if previous_analysis and 'transition_analysis' in previous_analysis else None
            
            # 使用线程池并行执行三个分析任务
            print(f"并行执行 {month} 月份的健康分析、生活分析和转换分析...")
            
            def run_health_analysis():
                print(f"健康分析线程开始执行 {month} 月份")
                result = refiner.health_analysis(month_data, persona, initial_state=initial_health_state)
                print(f"健康分析线程完成 {month} 月份")
                return result
            
            def run_life_analysis():
                print(f"生活分析线程开始执行 {month} 月份")
                result = refiner.life_analysis(month_data, persona, initial_state=initial_life_state)
                print(f"生活分析线程完成 {month} 月份")
                return result
            
            def run_transition_analysis():
                print(f"转换分析线程开始执行 {month} 月份")
                result = refiner.month_transition_analysis(month_data, persona, previous_analysis=prev_transition_analysis)
                print(f"转换分析线程完成 {month} 月份")
                return result
            
            with ThreadPoolExecutor(max_workers=3) as executor:
                # 提交三个分析任务
                health_future = executor.submit(run_health_analysis)
                life_future = executor.submit(run_life_analysis)
                transition_future = executor.submit(run_transition_analysis)
                
                # 获取分析结果
                health_result = health_future.result()
                life_result = life_future.result()
                transition_result = transition_future.result()
            
            # 保存本月的分析结果
            month_results = {
                'month': month,
                'health_analysis': health_result,
                'life_analysis': life_result,
                'transition_analysis': transition_result
            }
            
            # 保存到字典中
            all_analysis_results[month] = month_results
            
            # 保存到文件
            month_output_file = os.path.join(output_dir, f"{month}_analysis.json")
            with open(month_output_file, 'w', encoding='utf-8') as f:
                json.dump(month_results, f, ensure_ascii=False, indent=2)
            print(f"{month} 月份分析结果已保存到: {month_output_file}")
            
            # 更新previous_analysis为当前月份的所有分析结果
            previous_analysis = {
                'health_analysis': health_result,
                'life_analysis': life_result,
                'transition_analysis': transition_result
            }
        
        # 保存所有月份的综合分析结果
        all_results_file = os.path.join(output_dir, f"all_months_analysis_{datetime.now().strftime('%Y%m%d%H%M%S')}.json")
        with open(all_results_file, 'w', encoding='utf-8') as f:
            json.dump(all_analysis_results, f, ensure_ascii=False, indent=2)
        print(f"\n所有月份分析结果已保存到: {all_results_file}")
        
        return all_analysis_results
    
    def parallel_daily_event_refine(self, monthly_analysis_results: Dict[str, Dict], persona: Dict, timeline: List[Dict], output_dir: str = None) -> Dict[str, Dict]:
        """
        读取monthly_analysis的分析结果作为输入，先调用annual_event_refine，再并行对每个月数据执行daily_event_refine
        
        参数:
            monthly_analysis_results: monthly_analysis方法的输出结果，包含每个月的分析数据
            persona: 人物画像信息
            timeline: 事件时间线数据，直接传递给daily_event_refine处理，包含所有事件数据
            output_dir: 保存结果的路径（可选），可以是目录路径或JSON文件路径
            
        返回:
            包含每个月daily_event_refine结果的字典
        """
        from concurrent.futures import ThreadPoolExecutor
        import os
        import json
        from datetime import datetime, timedelta
        import copy


        # 首先调用annual_event_refine
        print("开始执行年度事件调整...")
        from event.event_refiner import EventRefiner
        refiner = EventRefiner(persona=persona, events=timeline)
        
        start_date = '2025-01-01'
        end_date = '2025-12-31'
        
        # # 调用annual_event_refine方法
        # refined_timeline = refiner.annual_event_refine(
        #     events=timeline,
        #     start_date=start_date,
        #     end_date=end_date,
        #     context="",
        #     max_workers=24
        # )
        # print("年度事件调整完成")
        refined_timeline = timeline
        # 定义一个辅助函数，用于对单个月份执行daily_event_refine
        def process_monthly_refine(month: str, analysis_results: Dict, refined_timeline: List[Dict], persona: Dict):
            """对单个月份执行daily_event_refine"""
            print(f"开始处理 {month} 月份的daily_event_refine...")
            
            # 从分析结果中提取必要数据
            health_analysis = analysis_results.get('health_analysis', {})
            life_analysis = analysis_results.get('life_analysis', {})
            
            # 确保health_analysis是字典格式
            if isinstance(health_analysis, str):
                try:
                    health_analysis = json.loads(health_analysis)
                except json.JSONDecodeError:
                    print(f"解析{month}月份健康分析结果失败，使用空数据")
                    health_analysis = {}
            elif not isinstance(health_analysis, dict):
                # 如果health_analysis既不是字符串也不是字典，使用空字典
                print(f"{month}月份健康分析结果格式不正确，使用空数据")
                health_analysis = {}
            
            # 确保life_analysis是字典格式
            if isinstance(life_analysis, str):
                try:
                    life_analysis = json.loads(life_analysis)
                except json.JSONDecodeError:
                    print(f"解析{month}月份生活分析结果失败，使用空数据")
                    life_analysis = {}
            elif not isinstance(life_analysis, dict):
                # 如果life_analysis既不是字符串也不是字典，使用空字典
                print(f"{month}月份生活分析结果格式不正确，使用空数据")
                life_analysis = {}
            
            # 计算月份的开始日期和结束日期
            month_parts = month.split('-')
            if len(month_parts) != 2:
                print(f"月份格式不正确: {month}")
                return month, None
            
            year, month_num = int(month_parts[0]), int(month_parts[1])
            
            # 计算该月的第一天
            start_date = datetime(year, month_num, 1)
            
            # 计算该月的最后一天
            if month_num == 12:
                next_month = datetime(year + 1, 1, 1)
            else:
                next_month = datetime(year, month_num + 1, 1)
            end_date = next_month - timedelta(days=1)
            
            # 格式化为YYYY-MM-DD字符串
            start_date_str = start_date.strftime('%Y-%m-%d')
            end_date_str = end_date.strftime('%Y-%m-%d')
            
            # 计算分割日期（月中）
            mid_month = start_date + timedelta(days=14)  # 15号作为分割日期
            split_date_str = mid_month.strftime('%Y-%m-%d')
            
            # 创建EventRefiner实例，使用已调整的timeline数据初始化
            refiner = EventRefiner(persona=persona, events=refined_timeline)
            month_transition_data = analysis_results.get('transition_analysis')
            # 将health_analysis转换为JSON字符串

            
            # 调用daily_event_refine方法，传递refined_timeline数据和控制的日期范围
            refine_result = refiner.daily_event_refine(
                events=refined_timeline,
                start_date=start_date_str,
                end_date=end_date_str,
                persona=persona,
                split_date=split_date_str,
                health_result=health_analysis,
                life_result=life_analysis,
                month_transition_analysis=month_transition_data
            )
            
            print(f"完成处理 {month} 月份的daily_event_refine")
            
            # 计算该月份的天数
            month_days = (end_date - start_date).days + 1
            
            # 处理refine_result的两种可能格式
            dailylife_data = []
            if refine_result:
                if isinstance(refine_result, dict) and 'dailylife' in refine_result:
                    # 格式1: refine_result是包含dailylife键的字典
                    dailylife_data = refine_result['dailylife']
                elif isinstance(refine_result, list):
                    # 格式2: refine_result直接是数组
                    dailylife_data = refine_result
            
            # 检查数据完整性
            if dailylife_data and isinstance(dailylife_data, list):
                # 验证并标准化每个日期对象的格式

                # 比较数据长度与月份天数
                actual_length = len(dailylife_data)
                if actual_length != month_days:
                    print(f"✗ 月份 {month} 处理不完整，实际生成 {actual_length} 天数据，预期 {month_days} 天数据")
                    return month, None  # 标记为失败
                else:
                    print(f"✓ 月份 {month} 处理完成，共 {actual_length} 天数据")
                    return month, refine_result
            else:
                print(f"✗ 月份 {month} 处理失败，返回数据格式错误")
                return month, None  # 标记为失败
        
        # 使用线程池并行处理每个月的数据
        all_refine_results = {}
        
        # 计算合适的线程数，最多24个线程
        max_workers = self.max_workers  # 最多24个线程，或等于月份数（如果月份数更少）
        
        def execute_parallel_months(months_to_process):
            """并行执行指定月份的处理"""
            temp_results = {}
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 提交任务
                futures = []
                for month in months_to_process:
                    analysis_results = monthly_analysis_results[month]
                    future = executor.submit(process_monthly_refine, month, analysis_results, refined_timeline, persona)
                    futures.append(future)
                
                # 收集结果
                for future in futures:
                    try:
                        month, result = future.result()
                        if result:
                            temp_results[month] = result
                    except Exception as e:
                        print(f"处理{month}月份数据时出错: {e}")
            return temp_results
        
        # 第一次执行：处理所有月份
        print("第一次并行处理所有月份...")
        all_refine_results = execute_parallel_months(list(monthly_analysis_results.keys()))
        
        # 检查是否有月份处理失败
        all_months = set(monthly_analysis_results.keys())
        success_months = set(all_refine_results.keys())
        failed_months = sorted(list(all_months - success_months))
        
        if failed_months:
            print(f"\n发现{len(failed_months)}个月份处理失败: {', '.join(failed_months)}")
            print("正在重新并行处理这些月份...")
            
            # 第二次执行：仅处理失败的月份
            retry_results = execute_parallel_months(failed_months)
            
            # 合并重试结果
            all_refine_results.update(retry_results)
            
            # 再次检查是否还有失败的月份
            final_failed_months = sorted(list(all_months - set(all_refine_results.keys())))
            if final_failed_months:
                print(f"\n重试后仍有{len(final_failed_months)}个月份处理失败: {', '.join(final_failed_months)}")
            else:
                print("\n✅ 所有月份重试成功！")
        else:
            print("\n✅ 第一次处理所有月份都成功！")
        
        # # 保存所有月份的事件细化结果
        # all_refine_file = os.path.join(output_dir, f"all_months_event_refine_{datetime.now().strftime('%Y%m%d%H%M%S')}.json")
        # with open(all_refine_file, 'w', encoding='utf-8') as f:
        #     json.dump(all_refine_results, f, ensure_ascii=False, indent=2)
        # print(f"\n所有月份事件细化结果已保存到: {all_refine_file}")
        
        # 生成每日状态文件
        # 检查output_dir是否是JSON文件路径
        # if output_dir and output_dir.endswith('.json'):
        #     daily_status_file = output_dir
        # else:
        #     daily_status_file = os.path.join(output_dir, 'daily_status.json')
            
        # 直接将月份字典格式的数据写入文件
        with open(output_dir, 'w', encoding='utf-8') as f:
            json.dump(all_refine_results, f, ensure_ascii=False, indent=2)
        print(f"每日状态数据已按月份字典格式保存到: {output_dir}")
        
        return all_refine_results

    def convert_timeline_to_events_with_llm(self, timeline_data):
        """使用LLM将时间线数据转换为按主题分组的事件数组

        Args:
            timeline_data: 从test5.json加载的时间线数据

        Returns:
            按主题分组的事件二维数组，每个主题数组包含多个事件对象
        """
        import json
        import re
        from event.template_s import template_convert_timeline_to_events

        # 将timeline_data转换为JSON字符串
        timeline_json = json.dumps(timeline_data, ensure_ascii=False)

        # 构建提示
        prompt = template_convert_timeline_to_events.format(timeline_json=timeline_json)

        try:
            # 调用LLM
            print("正在调用LLM进行事件转换...")
            llm_output = self.llm_call_sr(prompt)

            # 提取并解析JSON
            try:
                # 提取JSON数组
                json_pattern = r'\[.*\]'  # 匹配从第一个[到最后一个]的完整内容
                matches = re.findall(json_pattern, llm_output, re.DOTALL)

                if not matches:
                    raise ValueError("未找到JSON数组内容")

                # 解析JSON
                events_by_theme = json.loads(matches[0])

                # 验证输出格式
                if not isinstance(events_by_theme, list):
                    raise ValueError("输出不是数组格式")

                # 检查每个主题对象的结构
                for i, theme_obj in enumerate(events_by_theme):
                    if not isinstance(theme_obj, dict):
                        raise ValueError(f"第{i + 1}个主题不是对象格式")

                    # 检查主题必要字段
                    if not all(key in theme_obj for key in ['theme_name', 'theme_description', 'events']):
                        raise ValueError(f"主题缺少必要字段: {theme_obj}")

                    # 检查事件数组
                    theme_events = theme_obj['events']
                    if not isinstance(theme_events, list):
                        raise ValueError(f"主题事件不是数组格式: {theme_obj['theme_name']}")

                    # 检查每个事件的结构
                    for j, event in enumerate(theme_events):
                        if not all(key in event for key in ['name', 'description', 'date']):
                            raise ValueError(f"主题 '{theme_obj['theme_name']}' 中第{j + 1}个事件缺少必要字段: {event}")

                print("事件转换成功！")
                
                # =====================新增逻辑：生成时间线格式数据=====================
                import json
                from event.template_s import template_generate_timeline_summaries
                
                # 1. 收集所有事件并按月份分组
                all_events = []
                for theme_obj in events_by_theme:
                    for event in theme_obj['events']:
                        # 添加事件所属主题信息
                        event_with_theme = event.copy()
                        event_with_theme['belongs_to_theme'] = theme_obj['theme_name']
                        all_events.append(event_with_theme)
                
                # 2. 按月份分组事件
                events_by_month = {}
                for event in all_events:
                    # 提取事件的起始月份 (YYYY-MM格式)
                    try:
                        start_date = event['date'].split('至')[0].strip()
                        month = start_date[:7]  # 取YYYY-MM格式
                        if month not in events_by_month:
                            events_by_month[month] = []
                        events_by_month[month].append(event)
                    except:
                        # 如果日期格式有问题，跳过此事件
                        continue
                
                # 3. 构建时间线数据结构
                timeline_data = {
                    "comprehensive_summary": "",
                    "monthly_details": []
                }
                
                # 按月份排序
                sorted_months = sorted(events_by_month.keys())
                
                for month in sorted_months:
                    month_data = {
                        "month": month,
                        "monthly_summary": "",
                        "events": events_by_month[month],
                        "impact": ""
                    }
                    timeline_data["monthly_details"].append(month_data)
                
                # 4. 调用LLM生成总结字段
                print("正在调用LLM生成时间线总结...")
                timeline_json = json.dumps(timeline_data, ensure_ascii=False, indent=2)
                prompt = template_generate_timeline_summaries.format(timeline_json=timeline_json)
                llm_output = self.llm_call_sr(prompt)
                
                # 提取并解析带总结的时间线数据
                try:
                    import re
                    json_pattern = r'\{.*\}'  # 匹配从第一个{到最后一个}的完整内容
                    matches = re.findall(json_pattern, llm_output, re.DOTALL)
                    if not matches:
                        raise ValueError("未找到JSON对象内容")
                    
                    # 寻找最完整的JSON对象（包含comprehensive_summary的）
                    full_timeline = None
                    for match in matches:
                        try:
                            parsed = json.loads(match)
                            if "comprehensive_summary" in parsed and "monthly_details" in parsed:
                                full_timeline = parsed
                                break
                        except:
                            continue
                    
                    if not full_timeline:
                        # 如果没有找到完整的JSON，使用原始结构
                        full_timeline = timeline_data
                    
                    print("时间线总结生成成功！")
                    
                    # 5. 返回事件数据和时间线数据
                    return {
                        "events_by_theme": events_by_theme,
                        "timeline_data": full_timeline
                    }
                except json.JSONDecodeError as e:
                    print(f"时间线JSON解析失败: {e}")
                    print(f"LLM输出: {llm_output}")
                    # 返回原始数据结构
                    return {
                        "events_by_theme": events_by_theme,
                        "timeline_data": timeline_data
                    }

            except json.JSONDecodeError as e:
                print(f"JSON解析失败: {e}")
                print(f"LLM输出: {llm_output}")
                raise
            except ValueError as e:
                print(f"输出格式验证失败: {e}")
                print(f"LLM输出: {llm_output}")
                raise

        except Exception as e:
            print(f"事件转换过程中出错: {e}")
            raise

# 使用示例
if __name__ == "__main__":
    # 创建Scheduler实例
    from event.scheduler import Scheduler
    scheduler = Scheduler()
    
    # 示例: 准备数据并调用monthly_analysis方法
    # 1. 准备人物画像信息
    persona = {
        "name": "张三",
        "age": 30,
        "occupation": "程序员",
        "gender": "男",
        "health_condition": "良好",
        "hobbies": ["跑步", "阅读", "编程"]
    }
    
    # 2. 准备timeline数据（每月数据数组）
    timeline = [
        {
            "month": "2025-01",
            "events": [
                {
                    "event_id": "1",
                    "name": "新年聚会",
                    "date": "2025-01-01 18:00:00",
                    "type": "社交活动",
                    "description": "与朋友一起庆祝新年"
                },
                {
                    "event_id": "2",
                    "name": "跑步锻炼",
                    "date": "2025-01-02 07:00:00",
                    "type": "运动",
                    "description": "在公园跑步30分钟"
                }
            ]
        },
        {
            "month": "2025-02",
            "events": [
                {
                    "event_id": "3",
                    "name": "情人节晚餐",
                    "date": "2025-02-14 19:00:00",
                    "type": "约会",
                    "description": "与女友共进晚餐"
                },
                {
                    "event_id": "4",
                    "name": "工作加班",
                    "date": "2025-02-15 20:00:00",
                    "type": "工作",
                    "description": "为项目上线加班"
                }
            ]
        }
    ]
    
    # 3. 指定输出目录
    output_dir = "D:\\pyCharmProjects\\pythonProject4\\analysis_results"
    
    # 4. 调用monthly_analysis方法获取月度分析结果
    # 可以使用timeline数组或rich_timeline.json文件路径作为输入
    # 示例：使用rich_timeline.json文件路径
    rich_timeline_path = "D:\pyCharmProjects\pythonProject4\output\new\rich_timeline.json"
    print("开始执行月度分析...")
    # monthly_results = scheduler.monthly_analysis(timeline, persona, output_dir)  # 使用timeline数组
    monthly_results = scheduler.monthly_analysis(rich_timeline_path, persona, output_dir)  # 使用rich_timeline.json文件路径
    
    # 5. 调用parallel_daily_event_refine方法并行执行每日事件细化
    print("\n开始并行执行每日事件细化...")
    refine_results = scheduler.parallel_daily_event_refine(monthly_results, persona, timeline, "D:\\pyCharmProjects\\pythonProject4\\event_refine_results")
    
    print("\n所有操作完成！")
    print(f"月度分析结果保存在: {output_dir}")
    print(f"每日事件细化结果保存在: D:\\pyCharmProjects\\pythonProject4\\event_refine_results")
    
    # 打印结果统计信息
    if monthly_results:
        print(f"\n月度分析完成，共分析了 {len(monthly_results)} 个月的数据")
        for month, month_results in monthly_results.items():
            print(f"- {month}: 健康分析、生活分析、月度转换分析已完成")
    else:
        print("月度分析失败，未生成任何结果")
    
    if refine_results:
        print(f"\n每日事件细化完成，共处理了 {len(refine_results)} 个月的数据")
        for month in refine_results.keys():
            print(f"- {month}: 每日事件细化已完成")
    else:
        print("每日事件细化失败，未生成任何结果")



# 事件转换使用示例
if __name__ == "__main__":
    import os
    import json
    from event.scheduler import Scheduler
    
    # 创建Scheduler实例
    scheduler = Scheduler()
    
    # 读取test5.json文件
    test5_path = "D:\pyCharmProjects\pythonProject4\output\new\test5.json"
    if os.path.exists(test5_path):
        with open(test5_path, 'r', encoding='utf-8') as f:
            timeline_data = json.load(f)
        
        try:
            # 调用事件转换函数
            conversion_result = scheduler.convert_timeline_to_events_with_llm(timeline_data)
            
            # 获取主题事件和时间线数据
            events_by_theme = conversion_result['events_by_theme']
            timeline_data = conversion_result['timeline_data']
            
            # 保存主题事件结果
            events_output_path = "D:\pyCharmProjects\pythonProject4\event\events_by_theme.json"
            with open(events_output_path, 'w', encoding='utf-8') as f:
                json.dump(events_by_theme, f, ensure_ascii=False, indent=2)
            
            # 保存时间线数据结果
            timeline_output_path = "D:\pyCharmProjects\pythonProject4\event\timeline_data.json"
            with open(timeline_output_path, 'w', encoding='utf-8') as f:
                json.dump(timeline_data, f, ensure_ascii=False, indent=2)
            
            print(f"事件转换完成！结果已保存到:")
            print(f"  - 主题事件数据: {events_output_path}")
            print(f"  - 时间线数据: {timeline_output_path}")
            
            # 打印主题事件统计信息
            print(f"\n主题事件统计:")
            print(f"共转换了 {len(events_by_theme)} 个主题的事件")
            total_events = 0
            for i, theme_obj in enumerate(events_by_theme):
                theme_name = theme_obj['theme_name']
                event_count = len(theme_obj['events'])
                print(f"主题 {i+1} '{theme_name}': {event_count} 个事件")
                total_events += event_count
            print(f"总事件数: {total_events}")
            
            # 打印时间线数据统计信息
            print(f"\n时间线数据统计:")
            print(f"包含 {len(timeline_data['monthly_details'])} 个月的数据")
            
        except Exception as e:
            print(f"事件转换失败: {e}")
    else:
        print(f"找不到test5.json文件: {test5_path}")