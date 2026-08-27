# -*- coding: utf-8 -*-
"""
事件树分解模块
负责将事件递归分解为原子事件，形成树形结构
"""

import json
import re
from typing import Dict, List, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.lifebench.utils.llm_call import llm_call


class EventTree:
    def __init__(self, persona: str):
        self.persona = persona
        self.decompose_schedule = []  # 最终分解结果（完整树形结构）
        self.yearly_summary = ""  # 全年各月下个月指导总结
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
                    基于以下待分解事件，完成推理、分解，并直接输出子事件JSON数组（无需额外分析文本），目标是将事件分解为粒度小于一天的原子事件：

                    1. 分解原则：
                       - **严格依据题面主体**：分解内容必须严格围绕原事件描述的主体核心，不允许发散到与主体无关的额外事件。
                       - **不做过多扩展，例如计划事件仅分解计划**：如果原事件描述的是计划、预约或尚未执行的安排（如"计划去旅行"、"安排聚会"），则分解内容仅涵盖计划相关的准备工作（如确定时间地点、通知参与者），不应扩展到假设性的执行过程（旅行的整体流程）或后续事件。
                       - **禁止无关扩展**：严禁引入原描述中完全不存在的新情节线，也不得基于假设生成后续没在时间范围内的情节。
                    2. 事件扩展：
                       - 可参考事件描述进行分解，但原事件可能不完整，不具体，甚至不合理，需合理丰富简单的**前置（准备/规划/预定）、具体过程，以及其他相关事件**，补充后使其完整丰富。
                       - **扩展约束：新增情节时必须严格遵循以下两条规则：**
                         - **规则一（细节补充）：仅允许补充粒度≤1天的简单关联事件，如订票、交通通行、预约、沟通确认、物资准备等，且这些事件必须与原描述情节直接相关，不得引入原描述中完全不存在的新情节线。**
                         - **规则二（细化执行）：允许在原描述基础上进行具体化设计，将粗略安排（如"杭州3天旅行"）细化为可执行的分段安排（如"第一天西湖观光，第二天灵隐寺参访，第三天河坊街购物"），此类新增情节是对原描述的深化实现，而非引入与原描述无关的重大新情节。**
                         - **禁止：严禁生成与原事件核心情节存在较大差异、涉及多环节影响或改变事件性质的新情节（如临时新增旅行目的地、临时改变活动主题，新增未提及的第二次旅行等），扩展后的子事件应与原事件保持情节一致性，仅对原描述未涉及的细节进行补充完善。**
                    3. 粒度与阶段分解规则：
                       - 阶段事件：针对跨度长（超过7天）、流程复杂、重要性高的原事件，可拆分为「阶段性子事件」（如项目立项→执行→验收、旅行准备→行程执行→收尾），等后续再分解为粒度为一天的原子事件。
                         - 阶段事件特征：date格式为跨天区间（如["2025-01-01至2025-01-15"]），覆盖一个完整阶段的时间范围，decompose=1，表示其后续将被递归分解。
                         - 阶段划分原则：按「时间顺序+流程逻辑」拆分，每个阶段聚焦一个核心目标，避免阶段重叠或遗漏。注意，如果原事件时间范围小于一天，则不用拆分为阶段事件，直接拆分为原子事件。
                       - 原子事件：粒度≤1天，date格式为当天日期（如["2025-01-01"]）。具体可执行，多次发生需拆分为多个日期（如["2025-01-01","2025-02-01"]而非["2025-01-01至2025-02-01"]），decompose=0（无需继续分解）。
                       - **注意，不可以输出空数组，如果原事件很简单，你也要分解为不同的原子事件，或推理相关后续/前置事件，只不过都为粒度小于1天的原子事件，decompose=0即可。**
                    4. 时间范围约束（关键）：
                       - **子事件日期应在父事件时间范围内**。如需扩展事件到父事件时间范围之外，**最多不得超过父事件起止时间向前或向后各7天**（如父事件为2025-01-01至2025-01-15，则子事件最早可为2024-12-25，最晚可为2025-01-22）。
                       - 超出此范围的子事件不允许生成。
                       - 同一父事件的子事件时间范围应避免重叠（除非有明确的并行执行逻辑）。
                    5. 递归分解约束：
                       - 分解的子事件数量**严格控制在10个以内**（建议3-8个，避免过度拆分）。
                       - 事件ID中的'-'代表层级，每多一个'-'表示多一层分解。
                       - **如果你分解出的子事件为阶段事件，date格式为跨天区间（如["2025-01-01至2025-01-15"]），则其decompose一定为1。**
                       - **如果分解出的子事件为原子事件，date格式为当天日期（如["2025-01-01"]），则其decompose一定为0。**
                    6. 分解策略：
                       - 分解需多样化：并非所有事件都需经过准备/规划流程，同一类事件在不同场景下流程可不同。
                       - 时间分布：无需均匀分布事件，按真实场景合理安排（持续时间长不代表每天都有相关动作）；阶段事件的时间区间需覆盖原事件核心流程，原子事件可穿插在阶段内。
                    7. 合理性优化：可修改原事件不合理信息，避免事件间安排冲突，确保描述真实丰富；阶段事件的时间区间需衔接自然，无明显断层。

                    --- 输出格式强制要求 ---
                    1. **仅返回JSON数组（直接子事件列表），以[]开头结尾，无任何额外文本（包括分析、注释、代码块标记）。**
                    2. 每个子事件必须包含以下字段（缺一不可，语法严格正确）：
                       - event_id：格式为「父事件ID-序号」（如父ID=1，子事件ID=1-1、1-2），确保层级关联。
                       - name：事件名称（简洁明了）。
                       - date：时间数组（单个日期/多个日期，粒度≤1天；跨天事件用"至"连接，如["2025-01-01至2025-01-03"]）。
                       - type：取值范围（必选其一）：Career、Education、Relationships、Family&Living Situation、Personal Life、Finance、Health、Unexpected Events、Other。
                       - **description：事件详细描述，必须完整描述整个事件的全部内容过程，包括：事件的具体动作和执行过程、涉及的所有人物及其角色、发生的具体地点和环境背景。描述要具体、完整、不遗漏关键信息，让读者能通过description完整了解事件的来龙去脉。**
                       - participant：参与者数组，格式：[{{"name":"姓名","relation":"关系"}}]，优先从用户画像选择；无合适关系可合理编造，自己参与则为[{{"name":"自己名字","relation":"自己"}}]。
                       - location：城市+POI类别描述（如"上海市-家中书房"、"杭州市-灵隐寺"）。
                       - **decompose：0（原子事件，时间跨度小于一天），1=需要继续分解（时间跨度大于一天）。一定要检查，若子事件date中含至，即跨度大于1天，一定要decompose=1**
                    3. JSON语法要求：
                       - 字段名用双引号包裹，字段间用逗号分隔（无多余逗号）。
                       - 字符串值用双引号包裹，无语法错误。

                    -- 输出示例 --
                    假设待分解事件为：{{"event_id":"1","name":"2025年1月1日至2025年1月15日的欧洲旅行","date":["2025-01-01至2025-01-15"],"type":"Personal Life","description":"为期15天的欧洲旅行","participant":[{{"name":"张三","relation":"自己"}}],"location":"欧洲","decompose":1}}
                    输出：
                    [{{"event_id":"1-1","name":"旅行前准备","date":["2024-12-25至2024-12-31"],"type":"Personal Life","description":"准备欧洲旅行所需的签证、机票、酒店预订等","participant":[{{"name":"张三","relation":"自己"}}],"location":"北京市-家中","decompose":1}},{{"event_id":"1-2","name":"欧洲旅行行程执行","date":["2025-01-01至2025-01-15"],"type":"Personal Life","description":"按照计划在欧洲各国旅行","participant":[{{"name":"张三","relation":"自己"}}],"location":"欧洲各国","decompose":1}},{{"event_id":"1-3","name":"旅行后整理","date":["2025-01-16至2025-01-22"],"type":"Personal Life","description":"整理旅行照片和购买的纪念品","participant":[{{"name":"张三","relation":"自己"}}],"location":"北京市-家中","decompose":0}}]

                    假设待分解事件为（计划类）：{{"event_id":"2","name":"计划国庆假期旅行","date":["2025-09-15"],"type":"Personal Life","description":"与家人商量国庆假期去杭州旅行的计划","participant":[{{"name":"张三","relation":"自己"}}],"location":"家中","decompose":1}}
                    输出：
                    [{{"event_id":"2-1","name":"讨论旅行目的地和时间","date":["2025-09-15"],"type":"Personal Life","description":"与家人商量国庆假期去杭州旅行的具体安排","participant":[{{"name":"张三","relation":"自己"}}],"location":"家中","decompose=0}},{{"event_id":"2-2","name":"查询酒店和交通","date":["2025-09-16至2025-09-22"],"type":"Personal Life","description":"查询杭州酒店和往返交通信息","participant":[{{"name":"张三","relation":"自己"}}],"location":"家中","decompose":0}}]

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
                      - 每一层分解的子事件数量**严格控制在10个以内**（建议2-7个，避免过度拆分）。
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
                      - **description：事件详细描述，必须完整描述整个事件的全部内容过程，包括：事件的具体动作和执行步骤、涉及的所有人物及其角色、发生的具体地点和环境背景。描述要具体、完整、不遗漏关键信息，让读者能通过description完整了解事件的来龙去脉。**
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
