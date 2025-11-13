import ast
import json
import re

import holidays
from pyarrow import string

from utils.IO import *
from datetime import datetime, timedelta
from utils.llm_call import *
from event.memory import *
from typing import List, Dict, Optional
class Data_extract:
    def __init__(self):
        self.events = []
        self.persona = ""
        self.persona_withoutrl = ""
        self.context = ""
        self.atomic_events : Optional[List[Dict]] = None

    def _get_bottom_level_events(self) -> List[Dict]:
        """
        【内部辅助方法】递归提取所有最底层事件（subevent为空），结果缓存到self.bottom_events
        :return: 最底层事件列表
        """
        if self.atomic_events is not None:
            return self.atomic_events  # 已计算过，直接返回缓存

        def recursive_extract(events: List[Dict]) -> List[Dict]:
            result = []
            for event in events:
                subevents = event.get("subevent", [])
                if not subevents:
                    result.append(event)
                else:
                    result.extend(recursive_extract(subevents))
            return result

        self.bottom_events = recursive_extract(self.events)
        return self.bottom_events
    def update_bottom_level_events(self):
        def recursive_extract(events: List[Dict]) -> List[Dict]:
            result = []
            for event in events:
                subevents = event.get("subevent", [])
                if not subevents:
                    result.append(event)
                else:
                    result.extend(recursive_extract(subevents))
            return result

        self.bottom_events = recursive_extract(self.events)
        return self.bottom_events
    @staticmethod
    def is_date_match(target_date_str: str, event_date_str: str) -> bool:
        """
        【静态方法】判断事件日期是否包含目标日期（支持单个日期/日期范围）
        :param target_date_str: 目标日期（格式：YYYY-MM-DD）
        :param event_date_str: 事件日期（格式：YYYY-MM-DD 或 YYYY-MM-DD至YYYY-MM-DD）
        :return: 匹配结果（True/False）
        """
        # 验证目标日期格式
        try:
            target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError(f"目标日期格式错误：{target_date_str}，需符合YYYY-MM-DD")

        # 处理日期范围
        if "至" in event_date_str:
            try:
                start_str, end_str = event_date_str.split("至")
                start_date = datetime.strptime(start_str.strip(), "%Y-%m-%d").date()
                end_date = datetime.strptime(end_str.strip(), "%Y-%m-%d").date()
            except ValueError:
                raise ValueError(f"事件日期格式错误：{event_date_str}，范围需符合YYYY-MM-DD至YYYY-MM-DD")
            return start_date <= target_date <= end_date
        # 处理单个日期
        else:
            try:
                event_date = datetime.strptime(event_date_str.strip(), "%Y-%m-%d").date()
            except ValueError:
                raise ValueError(f"事件日期格式错误：{event_date_str}，单个日期需符合YYYY-MM-DD")
            return event_date == target_date

    def filter_by_date(self, target_date: str) -> List[Dict]:
        """
        【核心接口方法】筛选指定日期的最底层事件
        :param target_date: 目标日期（格式：YYYY-MM-DD）
        :return: 匹配的事件列表
        """
        # 步骤1：获取所有底层事件（自动缓存）
        bottom_events = self._get_bottom_level_events()

        def extract_start_date(date_str: str) -> str:
            """
            从时间字符串中提取起始日期，兼容两种格式：
            1. 时间区间（如"2025-01-01 07:30:00至2025-01-01 08:45:00"）
            2. 单个时间（如"2025-01-01 07:30:00"或"2025-01-01"）

            参数:
                date_str: 输入的时间字符串（支持含"至"的区间和不含"至"的单个时间）

            返回:
                str: 提取的起始日期，格式固定为"YYYY-MM-DD"

            异常:
                ValueError: 输入字符串不符合支持的时间格式时抛出
            """
            # 步骤1：分割字符串，提取起始时间部分（含"至"则取左边，不含则取全部）
            if "至" in date_str:
                # 分割"至"，取左侧的起始时间（如"2025-01-01 07:30:00"）
                start_time_part = date_str.split("至")[0].strip()
            else:
                # 无"至"，整个字符串即为起始时间（如"2025-01-01 07:30:00"或"2025-01-01"）
                start_time_part = date_str.strip()

            # 步骤2：解析起始时间部分，提取纯日期（支持两种子格式）
            supported_formats = [
                "%Y-%m-%d %H:%M:%S",  # 带秒级时间的格式（如"2025-01-01 07:30:00"）
                "%Y-%m-%d",  # 纯日期格式（如"2025-01-01"）
                "%Y-%m-%d %H:%M",
                "%Y-%m-%d %H"
            ]

            for fmt in supported_formats:
                try:
                    # 解析时间后，按"YYYY-MM-DD"格式返回起始日期
                    start_datetime = datetime.strptime(start_time_part, fmt)
                    return start_datetime.strftime("%Y-%m-%d")
                except ValueError:
                    # 一种格式解析失败，尝试下一种
                    continue

            # 所有格式都解析失败时，抛出明确错误
            raise ValueError(
                f"时间格式不支持！请输入以下格式之一：\n"
                f"1. 时间区间（如'2025-01-01 07:30:00至2025-01-01 08:45:00'）\n"
                f"2. 单个时间（如'2025-01-01 07:30:00'或'2025-01-01'）\n"
                f"当前输入：{date_str}"
            )
        # 步骤2：筛选匹配日期的事件
        matched = []
        for event in bottom_events:
            # 统一处理date为数组或单个字符串的情况，转为可迭代对象
            date_values = event.get("date", [])
            if not isinstance(date_values, list):
                date_values = [date_values]  # 若为单个字符串，转为单元素列表

            for date_str in date_values:
                date_str = extract_start_date(date_str)
                if self.is_date_match(target_date, date_str):
                    matched.append(event)
                    break # 避免同一事件因多个日期重复加入

        return matched
    def load_from_json(self,event,persona):

            self.persona = persona
            self.events = event
            del persona["relation"]
            self.persona_withoutrl = persona
            return False

phone_event_MSM_template = '''
请基于用户提供的事件列表、联系人列表和个人画像，统一分析生成手机通信事件（通话+短信），确保数据唯一不重复。生成需严格遵循以下要求：
1. 事件列表分析依据：
需先提取事件列表中的关键要素（时间、场景、参与对象、行为目的），明确事件与通信行为的关联性：
- 时间要素：识别事件的具体时间（如“2023-10-01 12:00点外卖”），通信时间需匹配事件时间线（外卖下单后1-5分钟内收到订单确认短信）
- 场景要素：按以下场景分类精准匹配通信方式：
  - 紧急事务（突发工作/家人急事）：通话90%/短信10%
  - 服务通知（外卖/快递/订单/预约）：短信80%/通话20%
  - 日常社交（约饭/闲聊/互助）：通话30%/短信70%
  - 商务交互（洽谈/汇报/会议）：通话60%/短信40%
  - 系统告知（账单/验证码/账户变动）：短信100%
（概率可根据事件紧急度±10%动态调整）
2. 关联交互规则：按30%概率生成核心通信的反向交互（标注“原ID_related_序号”），如通话后短信补充、短信互相回复，但需保证时间线连贯（关联交互时间晚于主事件）

二、字段规则（通话+短信统一整合）
（一）通话类事件（Phone Call）：含7个字段
event_id：复用原始标识；关联交互填“原ID_related_序号”
type：固定“call”
phoneNumber：优先用联系人列表；机构类填400/010号段或“官方服务号”
contactName：优先用联系人列表；机构类填官方名称
start_time：与事件时间一致/相近，格式“YYYY-MM-DD HH:MM:SS”
end_time：按场景设定时长（±波动），晚于start_time：
- 家人闲聊：3-8分钟±1分钟
- 工作汇报：2-5分钟±30秒
- 客户沟通：5-12分钟±1分钟
- 骚扰电话：10-30秒
direction：0=呼入，1=呼出
call_result：接通/未接通/忙线/拒接；未接通需标注原因（如“用户正在开会”）

（二）短信类事件（Phone SMS）：含7个字段
event_id：复用原始标识；关联交互填“原ID_related_序号”；非事件关联/随机短信填“non_event”
type：固定“sms”
message_content：符合场景逻辑：
例子：
- 个人联系人：日常沟通语气，含对话上下文（例：用户发“明天聚餐地点？”→对方回“XX餐厅，要订位吗？”）
- 机构/APP/运营商：含固定格式+脱敏信息（例：【XX银行】尾号1234卡10:00支出500元，余额12345元）
- 随机广告短信（电商类）：【XX电商】双11预售开启！您常购的XX品牌满300减100，点击链接领券：xxx，退订回T
- 随机广告短信（服务类）：【XX医美】秋季皮肤护理特惠，光子嫩肤体验价599元，预约电话400-XXX-XXXX，退订回T
- 随机公益短信：【XX公益】世界粮食日，节约粮食从光盘开始，让我们共同践行绿色生活~
- 随机通知短信：【XX运营商】您的手机套餐本月剩余流量5GB，可办理流量加油包，回复1立即开通
message_category：“事件关联”“非事件关联”“随机信息”（非事件关联占比≤15%，随机信息占比≤10%）
随机信息类型（random_type）：仅“随机信息”类别需填写，可选“电商广告”“服务营销”“公益通知”“运营商提醒”；其他类别填“无”
contactName：优先用联系人列表；机构类填官方名称（外卖填“XX外卖”，广告填“XX电商/XX机构”）
contact_phone_number：优先用联系人列表；机构类填1069/400号段（广告统一用10690000XXX-10699999XXX号段）
timestamp：遵循“时间偏移阈值”：
- 即时沟通：与事件时差≤5分钟
- 服务通知（外卖/快递/预约）：下单/触发后1-5分钟内
- 账单类：每日9:00-11:00或15:00-17:00
- 随机信息：随机分布在8:00-21:00（避免凌晨/深夜），格式“YYYY-MM-DD HH:MM:SS”
message_type：“发送”或“接收”（外卖/广告/机构类均为“接收”）

三、生成原则
1. 去重约束：同一event_id不得同时生成独立通话和独立短信，仅允许核心通信+关联交互的组合
2. 时间线逻辑：关联交互时间晚于主事件（如主通话10:00-10:05，关联短信10:06发送）
3. 未接后续：未接通通话后5分钟内生成短信提醒
4. 真实性校验：机构短信/通话号码需符合真实模板，禁止虚构格式
5. 场景推理优先级：优先基于事件明确场景，无明确关键词时结合行为目的推理。
6. 随机信息生成逻辑：
   - 生成概率：每5-8个事件可生成1条随机短信（整体占比≤10%）
   - 画像适配：广告内容需匹配用户画像（如宝妈→母婴用品广告，职场人→办公设备/培训广告）
   - 真实性：广告需包含“退订回T”等真实要素，公益短信需符合官方话术

四、输出格式要求
输出格式严格要求,仅输出JSON格式内容，不添加任何额外文本、注释或代码块标记。只输出一个数组，无论有没有事件来源都放在该数组内。示例：
[{{"type":"call","event_id":"11","phoneNumber":"+8613912345678","contactName":"张三","start_time":"2023-10-01 09:30:00","end_time":"2023-10-01 09:35:20","direction":1,"call_result":"接通"}},{{"type":"sms","event_id":"1","message_content":"刚才没听清，会议资料需要电子版吗？","message_category":"事件关联","contactName":"张三","contact_phone_number":"+8613912345678","timestamp":"2023-10-01 09:36:00","message_type":"接收"}},{{"type":"sms","event_id":"non_event","message_content":"【脉脉】有3位HR查看了您的简历，点击了解详情","message_category":"非事件关联","contactName":"脉脉","contact_phone_number":"10690000123","timestamp":"2023-10-01 10:30:00","message_type":"接收"}}]

请基于事件列表：{event}、联系人列表：{contacts}、个人画像{persona}生成。
'''

phone_event_Callrecord_template = '''
请基于用户提供的事件列表、联系人列表和个人画像，分析事件列表中可能产生的手机通信类操作事件（包含通话和短信），生成结构化的 “手机通信事件（Phone Communication Events）”。生成需严格遵循以下要求：
一、核心规则：避免重复冲突
同一原始事件（同一 event_id）仅可生成通话或短信中的一种通信记录，不可同时生成两种，确保事件交互方式唯一。
通信方式概率分布：根据事件场景合理性分配（例：紧急事项更可能通话，通知类更可能短信；日常沟通类事件按 3:7 概率随机生成通话 / 短信）。
可基于同一事件的延伸场景生成配套交互（例：用户先发短信咨询（事件 A），对方回电解答（可作为事件 A 的关联补充，复用 event_id 并标注 “关联交互”）），但需保证主事件仅一种核心通信方式。
二、字段规则（通话 / 短信分类型定义）
（一）通话类事件（Phone Call）
包含且仅包含以下 6 个字段：
来源事件 ID（event_id）：复用原始事件唯一标识，关联补充交互需标注 “原 ID+_related”（例：“evt001_related”）。
电话号码（phoneNumber）：优先使用联系人列表号码；机构类可填 400/010 等官方号段或 “官方服务号”。
联系人姓名（contactName）：优先用联系人列表姓名；无对应联系人时填机构名称（例：“京东客服”）。
通话开始时间（start_time）：与原始事件时间一致或相近，格式 “YYYY-MM-DD HH:MM:SS”。
通话结束时间（end_time）：基于场景设定合理时长（日常 1-5 分钟，业务 3-10 分钟），晚于开始时间，格式同上。
通话方向（direction）：0 代表呼入（他人拨打），1 代表呼出（用户拨打）。
（二）短信类事件（Phone SMS）
包含且仅包含以下 6 个字段：
来源事件 ID（event_id）：复用原始事件唯一标识，关联补充交互需标注 “原 ID+_related”（例：“evt002_related”）。
短信内容（message_content）：个人联系人贴近日常语气；机构类含固定格式（例：【XX 银行】...）；无明确内容时基于场景推测。
联系人姓名（contactName）：优先用联系人列表姓名；机构类填官方名称（例：“中国移动”）。
联系人电话号码（contact_phone_number）：优先用联系人列表号码；机构类可填 1069 等号段或 “官方专用号”。
时间戳（timestamp）：与原始事件时间一致或相近，格式 “YYYY-MM-DD HH:MM:SS”。
收发类型（message_type）：“发送”（用户主动）或 “接收”（他人 / 机构推送）。
三、生成原则
仅保留与 “通话” 或 “短信” 直接相关的事件，无通信交互的事件需排除。
原始信息不明确时，基于事件场景（如 “快递咨询”“预约确认”）合理推测，符合常识；可结合个人画像推理更多场景，补充更多生活细节类通信（如家人问候、朋友事项沟通，广告，提醒等）。
必须关联联系人列表：事件对象在列表中时，直接使用姓名和电话；机构类按场景补充名称和常见号码。
关联交互生成逻辑：同一事件主通信方式生成后，可按 30% 概率生成反向交互（如回复对方，或被对方回复），但需保证时间线连贯（关联交互时间晚于主事件）。
四、输出格式要求
以 JSON 数组格式返回，同时包含通话和短信事件，仅输出JSON格式内容，直接以[]作为开头结尾，不添加任何额外文本、注释或代码块标记。不要输出```json等无关字段，示例如下：[{{"type": "call","event_id": "evt001","phoneNumber": "+8613912345678","contactName": "张三","start_time": "2023-10-01 09:30:00","end_time": "2023-10-01 09:35:20","direction": 1}},{{"type": "sms","event_id": "evt002","message_content": "【美团外卖】您的订单 #12345 已接单，预计 30 分钟送达","contactName": "美团外卖","contact_phone_number": "10690000123","timestamp": "2023-10-01 12:10:15","message_type": "接收"}},{{"type": "call","event_id": "evt001_related","phoneNumber": "+8613912345678","contactName": "张三","start_time": "2023-10-01 10:05:10","end_time": "2023-10-01 10:08:33","direction": 0}}]
请基于用户提供的事件列表：{event}、联系人列表：{contacts} 和个人画像 {persona}，按上述要求生成手机通信事件。
'''

phone_event_Gallery_template = '''
请基于用户提供的事件列表和个人画像，分析可能产生的拍照行为，生成结构化的“手机图片/拍照数据（Phone Photo Data）”。生成需严格遵循以下要求：
一、核心规则：场景细分与概率
1. 拍照场景概率分配（按事件类型）：
- 旅行事件：风景打卡30%、人物合影20%、美食记录20%、导视牌/门票15%、细节特写15%
- 会议事件：PPT截图40%、参会人员20%、会议纪要手写板20%、会场环境20%
- 日常事件：美食25%、宠物20%、物品收纳15%、街头风景15%、文档扫描25%
2. 数量约束：单个事件生成2-4张图片，避免过度生成

二、字段规则（含新增字段）
需包含且仅包含以下字段：
event_id：复用原始事件唯一标识
type：固定“photo”
caption：详细描述（主体+动作+背景），例：“李华在西湖断桥边打卡，身后有湖面与游船”
title：“IMG_年月日_时分秒”格式，与datetime一致
datetime：与事件时间一致/相近，格式“YYYY-MM-DD HH:MM:SS”
location：嵌套对象，遵循“地点层级约束”：
- province：省份
- city：城市
- district：区县
- streetName：真实街道名称
- streetNumber：门牌号（无则填“XX号”）
- poi：真实POI（如“朝阳公园”“三里屯太古里”）
faceRecognition：联系人列表姓名/“无”/“XX若干”
imageTag：5-15个关键词（场景+主体+动作+属性），例：“拿铁咖啡、玻璃吸管、木质桌面、下午茶”
ocrText：图片中真实文字（门票/海报/导视牌），无则填“无”
拍摄模式（shoot_mode）：正常拍照/夜景/人像/微距（人像关联faceRecognition）
图片尺寸（image_size）：如“4032×3024”“3024×4032”

三、生成原则
1. 地点真实性：无明确地点时，基于画像“常居地/常去地”生成真实POI
2. 标签精准性：避免泛化关键词，需贴合具体内容
3. OCR合理性：门票/海报需包含“名称+时间+价格”等真实信息

四、输出格式要求
输出格式严格要求,仅输出JSON格式内容，不添加任何额外文本、注释或代码块标记。只输出一个数组，无论有没有事件来源都放在该数组内。示例：
[{{"event_id":"evt_003","type":"photo","caption":"王芳在杭州西湖断桥边拍摄风景，湖面游船与雷峰塔清晰可见","title":"IMG_20231001_143025","datetime":"2023-10-01 14:30:25","location":{{"province":"浙江省","city":"杭州市","district":"西湖区","streetName":"北山街","streetNumber":"XX号","poi":"西湖断桥景区"}},"faceRecognition":["王芳"],"imageTag":["西湖","断桥","游船","雷峰塔","秋日","湖面"],"ocrText":"西湖断桥 - 国家5A级旅游景区","shoot_mode":"正常拍照","image_size":"4032×3024"}}]

请基于事件列表：{event}、个人画像{persona}生成。
'''

phone_event_Calendar_template = '''
请基于用户提供的事件列表、事件背景列表和个人画像，分析可能产生的日历/笔记行为，按概率生成结构化的“手机日历与笔记数据（Phone Calendar & Note Data）”。生成需严格遵循以下要求：
一、核心规则：生成逻辑与优先级
1. 日历生成特殊场景：
- 出行预定场景：铁路/飞机预定事件，若涉及携程、12306、飞猪等出行APP，默认触发APP自动添加日历（生成概率95%），日历内容需包含“车次/航班号+出发时间+目的地+预定码”核心信息。只有出行类APP会自动添加，不考虑其他APP。
2. 事件类型生成概率（按重要度与场景）：
- 日历：仅针对重要事件（出行预定、重要会议、医疗预约、旅行计划），生成概率80%-95%.无重要事件不生成。
- 笔记：包含两类事件——重要事件（会议/预约/出行/学习，生成概率60%-80%）、非重要但感兴趣事件（如兴趣爱好、特色体验、小众发现等，生成概率30%-50%）
- 日常购物/普通社交（非感兴趣）：10%笔记（不生成日历）
- 无时间约束/低重要度且无兴趣关联事件：0%日历，0%笔记
3. 数量约束：总输出≤3个；无重要事件且无感兴趣事件时可返回空数组

二、字段规则
（一）日历日程（Calendar）：含6个字段
event_id：复用原始事件标识
type：固定“calendar”
title：简洁概括（场景+关键信息），例：“G1234次列车（北京-上海）”“李主任门诊预约”
description：包含核心要素，对日历日程进行描述：
- 出行预定例：“G1234次列车（北京南站→上海虹桥站），2023-10-05 08:00发车，预定码E12345，凭身份证检票，来源：12306”
- 会议例：“与李总洽谈合作，2023-10-10 14:00-15:30公司2楼会客室，需带报价单”
start_time：与约定时间一致，格式“YYYY-MM-DD HH:MM:SS”
end_time：出行类填发车/起飞时间（与start_time一致），会议/预约类填合理时长后时间

（二）笔记（Note）：含6个字段
event_id：复用原始事件标识；纯兴趣主题总结填“theme_主题关键词”（如“theme_手冲咖啡技巧”）
type：固定“note”
title：单一主题+记录类型，例：“项目周会待办清单”“10月5日出行物品清单”“手冲咖啡水温测试记录”
content：聚焦单一主题的结构化表述（分点/分层），类型包括：
- 重要事件记录：含待办/关键信息/核心结论，例：“一、会议决议：1. 确定Q4预算为500万；2. 市场部负责新品推广”
- 感兴趣事件记录：含体验细节/心得/要点，例：“一、手冲咖啡测试：1. 水温92℃时酸度适中；2. 闷蒸30秒风味更浓郁”
- 兴趣主题总结：含知识/技巧/观点，例：“一、多肉植物养护要点：1. 春秋季每周浇水1次；2. 避免阳光直射正午强光”
（禁止对全天所有事件进行总结，需围绕单个事件或单个主题展开）
datetime：事件发生时/后1小时内（重要/感兴趣事件）或主题学习后（兴趣总结），格式“YYYY-MM-DD HH:MM:SS”
关联事件ID（related_event_ids）：单个事件填原ID；纯兴趣主题填“无”；同类事件汇总填多个ID（如“evt001,evt002”）

三、生成原则
1. 重要度与兴趣区分：日历仅筛选“预定”“会议”“医疗”“出行”等重要事件；笔记可覆盖重要事件及“兴趣爱好”“特色体验”等非重要但感兴趣事件
2. 笔记主题唯一性：笔记内容仅关注单个事件或单个兴趣主题，避免跨事件、跨主题的全天总结
3. 内容差异化：日历侧重时间与核心凭证信息，笔记侧重单一主题的细节、心得或要点
4. 来源标注：APP自动添加的日历需在description末尾明确“来源：XXAPP”

四、输出格式要求
输出格式严格要求,仅输出JSON格式内容，不添加任何额外文本、注释或代码块标记。只输出一个数组，无论有没有事件来源都放在该数组内。示例：
[{{"type":"calendar","event_id":"5","title":"G1234次列车（北京-上海）","description":"G1234次列车（北京南站→上海虹桥站），2023-10-05 08:00发车，预定码E12345，凭身份证检票，来源：12306","start_time":"2023-10-05 08:00:00","end_time":"2023-10-05 08:00:00"}},{{"type":"note","event_id":"6","title":"手冲咖啡体验记录","content":"一、使用咖啡豆：埃塞俄比亚耶加雪菲\n二、冲泡参数：1. 粉水比1:15；2. 水温90℃；3. 萃取时间2分30秒\n三、口感心得：花香明显，酸度柔和，回甘持久","datetime":"2023-10-05 15:20:00","related_event_ids":"evt_006"}}]

请基于事件列表：{event}、事件背景列表：{back}、个人画像{persona}生成。

'''

phone_event_Push_template = '''
请基于用户提供的事件列表、联系人列表、个人画像和短信数据，分析可能触发的手机推送，生成结构化的“手机推送数据（Phone Push Data）”。生成需严格遵循以下要求：
一、核心规则：事件细节挖掘与推送分配
1. 事件细节动作挖掘依据：
需先提取事件列表中的具体行为动作（如支付、预定、下单、改签、退款、收藏等），按动作类型精准匹配推送场景：
- 支付动作：关联支付APP（支付宝/微信支付）的支付成功提醒、账单同步推送
- 预定动作：关联预定类APP（美团/携程/12306）的预定成功、预约时间临近、预约变更提醒
- 下单动作：关联电商/外卖APP（淘宝/京东/美团外卖）的订单确认、发货/备餐、物流/送达提醒
- 改签/退款动作：关联出行/服务APP（12306/携程）的改签成功、退款到账通知
- 收藏/关注动作：关联内容/电商APP（抖音/小红书/淘宝）的收藏内容更新、关注对象上新提醒
2. 推送来源分类（不含社交平台通信类）：
- 工作类：腾讯会议、企业邮箱、钉钉
- 生活类：美团、淘宝、京东、银行、运营商
- 娱乐类：抖音、小红书、网易云音乐
- 工具类：支付宝、高德地图、有道云笔记
- 资讯类：今日头条、腾讯新闻
- 教育类：网易云课堂、学而思
- 个人类：基于画像的特色APP（Keep/雪球/宝宝树）
- 系统类：电量低、存储空间不足、运动健康
（注：社交平台（微信/QQ等）的聊天通信信息仅通过短信/通话模板生成，推送模板不涉及）
3. 推送场景概率：
- 事件细节动作关联（支付/预定/下单/出行等）：60%
- 关键节点提醒（会议前30分钟/预约前1小时）：15%
- 个性化推荐：20%
- 系统常规通知：5%

二、字段规则
需包含且仅包含以下字段：
event_id：复用原始事件标识；系统常规通知填“system”
type：固定“push”
推送标题（title）：含事件细节动作+关键对象，符合APP风格，例：“支付宝：外卖支付成功提醒”“美团：餐厅预定成功通知”
推送内容（content）：贴合APP真实话术，包含动作结果+核心信息（金额/时间/编号等），例：
- 支付动作：【支付宝】您已成功支付美团外卖订单#8765，金额58元，账单已同步至“我的账单”
- 预定动作：【美团】您预定的XX餐厅2人餐（10月5日18:00）已确认，到店出示预定码1234即可
- 下单动作：【淘宝】您购买的XX品牌卫衣已发货，快递单号SF123456789，点击查看物流
- 改签动作：【12306】您的G1234次列车已改签至10月3日14:00，新座位号10车12A
推送时间（datetime）：遵循动作时间线约束：
- 支付/下单/预定动作：完成后1-3分钟内
- 关键节点提醒：事件发生前30分钟-1小时
- 工作类：9:00-18:00
- 娱乐类：12:00-14:00、19:00-22:00
- 生活/工具/资讯/教育/个人类：8:00-22:00
- 系统类：电量≤20%/存储空间≤10%时
推送来源APP（source）：具体APP/系统模块名称（需与动作场景匹配）
推送状态（push_status）：已读/未读/已删除（未读占比≤40%）
跳转路径（jump_path）：如“支付宝→账单详情”“美团→我的预定”“淘宝→订单物流”

三、生成原则
1. 去重约束：与短信数据重复的交流内容不生成；社交平台通信信息不纳入推送范围
2. 细节匹配：推送内容需包含事件中的具体信息（如支付金额、预定时间、订单编号等），禁止泛化表述
3. 频率控制：同一APP同一事件24小时内推送≤2条（如支付成功+账单同步可合并为1条）
4. 画像匹配：个人类推送需包含用户行为偏好（如股民→雪球股票行情，宝妈→宝宝树育儿提醒）

四、输出格式要求
输出格式严格要求,仅输出JSON格式内容，不添加任何额外文本、注释或代码块标记。只输出一个数组，无论有没有事件来源都放在该数组内。示例：
[{{"type":"push","event_id":"evt_008","title":"支付宝：外卖支付成功提醒","content":"【支付宝】您已成功支付美团外卖订单#8765，金额58元，账单已同步至“我的账单”","datetime":"2023-10-01 12:03:00","source":"支付宝","push_status":"未读","jump_path":"支付宝→我的账单→订单#8765"}},{{"type":"push","event_id":"evt_009","title":"美团：餐厅预定成功通知","content":"【美团】您预定的XX火锅（朝阳店）2人餐（10月5日18:00）已确认，到店出示预定码1234即可，如需变更请提前2小时联系","datetime":"2023-10-01 15:40:00","source":"美团","push_status":"已读","jump_path":"美团→我的→预定订单"}}]

请基于事件列表：{event}、联系人列表：{contacts}、个人画像{persona}、短信数据{msm}生成。
'''

def get_daily_events_with_subevent(events, target_date_str):
    """
    仅按日级别匹配，获取起始日期在目标日期且包含子事件（subevent非空）的事件

    参数:
    events (list): 原始事件列表，每个事件为字典格式
    target_date_str (str): 目标日期字符串，支持三种输入格式：
                          1. "%Y-%m-%d %H:%M:%S"（如"2025-03-04 14:00:00"）
                          2. "%Y-%m-%d %H:%M"（如"2025-03-04 14:00"）
                          3. "%Y-%m-%d"（如"2025-03-04"）
                          最终均按日级别（年月日）匹配

    返回:
    list: 符合条件的事件列表
    """
    # 存储符合条件的事件
    result_events = []

    # 步骤1：解析目标日期，提取年月日（统一转为日级别）
    # 定义支持的输入格式，确保能解析三种类型的目标时间
    supported_input_formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d"
    ]
    target_date = None
    for fmt in supported_input_formats:
        try:
            # 解析目标时间
            parsed_datetime = datetime.strptime(target_date_str, fmt)
            # 提取日级别日期（转为"YYYY-MM-DD"字符串）
            target_date = parsed_datetime.strftime("%Y-%m-%d")
            break
        except ValueError:
            continue

    # 若目标日期解析失败，抛出异常
    if target_date is None:
        raise ValueError(
            f"目标日期格式错误！仅支持以下三种格式：\n1. %Y-%m-%d %H:%M:%S（如2025-03-04 14:00:00）\n2. %Y-%m-%d %H:%M（如2025-03-04 14:00）\n3. %Y-%m-%d（如2025-03-04）")

    # 步骤2：遍历事件，筛选符合条件的记录
    for event in events:
        # 条件1：事件必须包含子事件（subevent非空列表）
        if not event.get("subevent"):
            continue
        if event.get("subevent") == []:
            continue
        # 条件2：解析事件起始时间，判断是否与目标日期匹配（日级别）
        date_str_list = event.get("date", [])
        if not date_str_list:  # 无日期信息的事件跳过
            continue

        # 取第一个时间段作为事件主起始时间（默认date列表首个为核心时间）
        main_time_range = date_str_list[0]
        event_start_str = main_time_range.split("至")[0].strip()  # 分割"至"，取起始时间部分

        # 解析事件起始时间（支持三种格式）
        event_start_date = None
        for fmt in supported_input_formats:
            try:
                parsed_event_start = datetime.strptime(event_start_str, fmt)
                event_start_date = parsed_event_start.strftime("%Y-%m-%d")  # 转为日级别
                break
            except ValueError:
                continue

        # 若事件起始时间解析失败，打印警告并跳过
        if event_start_date is None:
            print(f"警告：事件{event.get('event_id')}的起始时间格式异常（{event_start_str}），跳过处理")
            continue

        # 日级别匹配：事件起始日期 == 目标日期
        if event_start_date == target_date:
            result_events.append(event)

    return result_events

def iterate_dates(start_date: str, end_date: str) -> List[str]:
    """
    遍历从起始日期到结束日期（包含两端）的所有日期，返回日期字符串列表

    参数:
        start_date: 起始日期，格式为 'YYYY-MM-DD'（如 '2025-01-01'）
        end_date: 结束日期，格式为 'YYYY-MM-DD'（如 '2025-01-05'）

    返回:
        List[str]: 按时间顺序排列的日期列表，包含 start_date 和 end_date 之间的所有日期

    异常:
        ValueError: 日期格式错误或起始日期晚于结束日期时抛出
    """
    # 解析日期为datetime对象
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError as e:
        raise ValueError(f"日期格式错误，需为 'YYYY-MM-DD'，错误：{str(e)}")

    # 校验日期逻辑
    if start > end:
        raise ValueError(f"起始日期 {start_date} 不能晚于结束日期 {end_date}")

    # 遍历区间内所有日期
    current_date = start
    date_list = []
    while current_date <= end:
        # 转为 'YYYY-MM-DD' 格式字符串并添加到列表
        date_list.append(current_date.strftime("%Y-%m-%d"))
        # 移动到下一天
        current_date += timedelta(days=1)

    return date_list

def remove_json_wrapper(s: str) -> str:
        """
        去除字符串前后可能存在的```json  ```标记（包含可能的空格）

        参数:
            s: 输入字符串

        返回:
            处理后的字符串，若不存在标记则返回原字符串
        """
        # 正则模式：匹配开头的```json及可能的空格，和结尾的```及可能的空格
        pattern = r'^\s*```json\s*\n?|\s*```\s*$'
        # 替换匹配到的内容为空字符串
        result = re.sub(pattern, '', s, flags=re.MULTILINE)
        return result

extool = Data_extract()
a = []
b = []
c = []
d = []
# a = read_json_file('event_gallery.json')
# b = read_json_file('event_push.json')
# c = read_json_file('event_call.json')
# d = read_json_file('event_note.json')


def phone_gen(date):
    global a,b,c,d
    #获取今日daily_event
    res1 = extool.filter_by_date(date)
    res = []
    for i in range(len(res1)):
        if "-" in res1[i]['event_id']:
            continue
        res.append(res1[i])
    #callrecord+message
    prompt = phone_event_MSM_template.format(event=res, contacts=contact, persona=extool.persona_withoutrl)
    res = llm_call(prompt, extool.context)
    print(res)
    res = remove_json_wrapper(res)
    data = json.loads(res)
    c += data
    with open("phone_data/event_call.json", "w", encoding="utf-8") as f:
        json.dump(c, f, ensure_ascii=False, indent=2)
    #gallery
    prompt = phone_event_Gallery_template.format(event=res, persona=extool.persona)
    resx = llm_call(prompt, extool.context)
    print(resx)
    resx = remove_json_wrapper(resx)
    data = json.loads(resx)
    a+=data
    with open("phone_data/event_gallery.json", "w", encoding="utf-8") as f:
        json.dump(a, f, ensure_ascii=False, indent=2)
    #push
    prompt = phone_event_Push_template.format(event=res,contacts=contact,persona=extool.persona_withoutrl,msm=resx)
    res = llm_call(prompt, extool.context)
    print(res)
    res = remove_json_wrapper(res)
    data = json.loads(res)
    b += data
    with open("phone_data/event_push.json", "w", encoding="utf-8") as f:
        json.dump(b, f, ensure_ascii=False, indent=2)
    #calendar+note
    prompt = phone_event_Calendar_template.format(event=res,back = get_daily_events_with_subevent(extool.events,date),persona=extool.persona_withoutrl)
    res = llm_call(prompt,extool.context)
    print(res)
    res = remove_json_wrapper(res)
    data =json.loads(res)
    d += data
    with open("phone_data/event_note.json", "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    return


data = read_json_file('event_data/life_event/event_update1.json')
contact = read_json_file('contact.json')
persona = '''
     {
            "name": "徐静",
            "birth": "1993-07-10",
            "age": 28,
            "nationality": "汉",
            "home_address": {
                "province": "上海市",
                "city": "上海市",
                "district": "浦东新区",
                "street_name": "张杨路",
                "street_number": "123号"
            },
            "birth_place": {
                "province": "上海市",
                "city": "上海市",
                "district": "浦东新区"
            },
            "gender": "女",
            "education": "普通高中",
            "job": "服装店销售主管",
            "occupation": "时尚服饰零售企业",
            "workplace": {
                "province": "上海市",
                "city": "上海市",
                "district": "浦东新区",
                "street_name": "世纪大道",
                "street_number": "88号"
            },
            "belief": "不信仰宗教",
            "salary": 100000.0,
            "body": {
                "height": 158,
                "weight": 62.5,
                "BMI": 25.04
            },
            "family": "未婚",
            "personality": {
                "mbti": "ESFJ"
            },
            "hobbies": [
                "逛街购物",
                "听音乐",
                "羽毛球",
                "收藏纪念币"
            ],
            "favorite_foods": [
                "上海小笼包",
                "抹茶拿铁",
                "草莓蛋糕"
            ],
            "memory_date": [
                "2012-06-15：第一份工作入职纪念日",
                "2020-08-20：晋升销售主管日"
            ],
            "healthy_desc": "个人整体健康状况良好，无慢性病史，不定期进行健康体检，每年就医几次主要是常规检查。保持每周三次的体育锻炼习惯，注重个人护理和作息规律。",
            "lifestyle_desc": "日常生活高度依赖互联网，尤其喜欢使用社交媒体和购物APP获取信息。休闲活动包括每周两到三次逛街购物、在家听流行音乐、以及参加瑜伽锻炼。每月与朋友聚餐或看电影一次，每年会有一到两次短途旅行探亲或度假，生活风格偏向现代都市休闲型。",
            "economic_desc": "家庭年收入约10万元，拥有1处房产和家用汽车，目前没有股票、基金等投资活动，消费习惯偏谨慎，注重基本生活保障。",
            "work_desc": "在家族经营的服装零售企业工作，每周工作48小时，担任销售主管职务，负责店面管理和客户服务工作，工作稳定且与家庭生活紧密结合。",
            "experience_desc": "徐静自出生起便生活在上海浦东新区，2012年高中毕业后加入家族经营的服装零售企业，从基层销售员做起，通过努力逐步晋升为销售主管，负责店面运营和团队管理。她的工作经历稳定，与家庭事业深度绑定，积累了丰富的客户服务经验。",
            "description": "徐静是一位28岁的上海本地女性，高中毕业后在家族服装零售企业工作，现任销售主管。作为ESFJ人格类型，性格热情负责。日常生活中，她喜欢逛街购物、听音乐和体育锻炼，收藏纪念币是她的独特爱好。健康状况良好。经济状况稳定，拥有房产和汽车，消费观念务实。工作与家庭生活紧密结合，未来计划开设自己的服装店并保持家庭旅行传统。",
            "relation": [
                [
                    {
                        "name": "徐明",
                        "relation": "父亲",
                        "social circle": "家庭圈",
                        "gender": "男",
                        "age": 58,
                        "birth_date": "1965-03-12",
                        "home_address": {
                            "province": "上海市",
                            "city": "上海市",
                            "district": "浦东新区",
                            "street_name": "张杨路",
                            "street_number": "123号"
                        },
                        "birth_place": {
                            "province": "上海市",
                            "city": "上海市",
                            "district": "黄浦区"
                        },
                        "personality": "ISTJ",
                        "economic_level": "中产",
                        "occupation": "服装零售企业主",
                        "organization": "明芳服饰有限公司",
                        "nickname": "老爸",
                        "relation_description": "徐静的父亲，与妻子共同经营家族服装企业。年轻时从裁缝学徒做起，1990年创办服装店并逐步发展成连锁企业。现在虽已半退休，仍会每周到店里巡视指导。与女儿关系亲密，每周至少三次家庭聚餐，经常一起讨论店铺经营。支持女儿开设分店的计划，时常传授商业经验。"
                    },
                    {
                        "name": "李芳",
                        "relation": "母亲",
                        "social circle": "家庭圈",
                        "gender": "女",
                        "age": 56,
                        "birth_date": "1967-08-25",
                        "home_address": {
                            "province": "上海市",
                            "city": "上海市",
                            "district": "浦东新区",
                            "street_name": "张杨路",
                            "street_number": "123号"
                        },
                        "birth_place": {
                            "province": "江苏省",
                            "city": "苏州市",
                            "district": "姑苏区"
                        },
                        "personality": "ISFJ",
                        "economic_level": "中产",
                        "occupation": "服装企业财务主管",
                        "organization": "明芳服饰有限公司",
                        "nickname": "妈妈",
                        "relation_description": "徐静的母亲，负责家族企业的财务管理工作。原籍苏州，年轻时来上海打工认识徐明后结婚。性格温柔细心，不仅管理公司账务，还包办全家饮食起居。每天都会为女儿准备午餐便当，周末常一起逛街选购新款服装。母女关系融洽，经常交流生活琐事和情感问题。"
                    },
                    {
                        "name": "徐强",
                        "relation": "哥哥",
                        "social circle": "家庭圈",
                        "gender": "男",
                        "age": 32,
                        "birth_date": "1991-11-03",
                        "home_address": {
                            "province": "浙江省",
                            "city": "杭州市",
                            "district": "西湖区",
                            "street_name": "文三路",
                            "street_number": "456号"
                        },
                        "birth_place": {
                            "province": "上海市",
                            "city": "上海市",
                            "district": "浦东新区"
                        },
                        "personality": "ENTJ",
                        "economic_level": "中产",
                        "occupation": "电商运营总监",
                        "organization": "杭州某电商平台",
                        "nickname": "强哥",
                        "relation_description": "徐静的哥哥，大学毕业后选择在杭州发展电商事业。虽然不在家族企业工作，但经常为妹妹提供线上销售建议。每月会回上海探望父母，与妹妹见面聚餐。兄妹关系良好，通过微信保持日常联系，主要讨论工作发展和家庭事务。徐静计划开设分店时也会征求哥哥的意见。"
                    }
                ],
                [
                    {
                        "name": "王丽",
                        "relation": "闺蜜",
                        "social circle": "高中同学圈",
                        "gender": "女",
                        "age": 28,
                        "birth_date": "1993-03-15",
                        "home_address": {
                            "province": "上海市",
                            "city": "上海市",
                            "district": "徐汇区",
                            "street_name": "淮海中路",
                            "street_number": "456号"
                        },
                        "birth_place": {
                            "province": "上海市",
                            "city": "上海市",
                            "district": "徐汇区"
                        },
                        "personality": "ENFP",
                        "economic_level": "中产",
                        "occupation": "市场专员",
                        "organization": "上海某广告公司",
                        "nickname": "丽丽",
                        "relation_description": "王丽是徐静高中时期的同桌，两人从学生时代就建立了深厚的友谊。现在同在上海工作，每周会约一次逛街或下午茶，经常分享工作和生活琐事。她们保持着密切的微信联系，节假日会一起聚餐或看电影，偶尔还会约上其他高中同学聚会。"
                    },
                    {
                        "name": "张婷",
                        "relation": "闺蜜",
                        "social circle": "高中同学圈",
                        "gender": "女",
                        "age": 29,
                        "birth_date": "1992-11-22",
                        "home_address": {
                            "province": "浙江省",
                            "city": "杭州市",
                            "district": "西湖区",
                            "street_name": "文三路",
                            "street_number": "789号"
                        },
                        "birth_place": {
                            "province": "上海市",
                            "city": "上海市",
                            "district": "静安区"
                        },
                        "personality": "ISFJ",
                        "economic_level": "中产",
                        "occupation": "小学教师",
                        "organization": "杭州市某实验小学",
                        "nickname": "婷婷",
                        "relation_description": "张婷是徐静高中时期的好友，大学毕业后选择到杭州发展。虽然分隔两地，但她们每月都会视频通话两到三次，分享各自的生活近况。每年春节张婷回上海探亲时，她们必定会见面聚餐，平时通过微信保持密切联系，互相支持对方的事业发展。"
                    },
                    {
                        "name": "赵小美",
                        "relation": "高中同学",
                        "social circle": "高中同学圈",
                        "gender": "女",
                        "age": 28,
                        "birth_date": "1993-09-08",
                        "home_address": {
                            "province": "上海市",
                            "city": "上海市",
                            "district": "闵行区",
                            "street_name": "虹梅路",
                            "street_number": "321号"
                        },
                        "birth_place": {
                            "province": "上海市",
                            "city": "上海市",
                            "district": "闵行区"
                        },
                        "personality": "ISTJ",
                        "economic_level": "小康",
                        "occupation": "会计",
                        "organization": "上海某会计师事务所",
                        "nickname": "小美",
                        "relation_description": "赵小美是徐静高中同学，现在同在上海工作。她们保持着每月一次的聚会频率，通常是在周末一起吃饭或逛街。作为高中同学圈的核心成员，赵小美经常组织同学聚会，与徐静及其他同学保持着稳定的联系，彼此在工作中也会互相提供建议和支持。"
                    },
                    {
                        "name": "钱多多",
                        "relation": "高中同学",
                        "social circle": "高中同学圈",
                        "gender": "女",
                        "age": 28,
                        "birth_date": "1993-12-03",
                        "home_address": {
                            "province": "广东省",
                            "city": "深圳市",
                            "district": "南山区",
                            "street_name": "科技园路",
                            "street_number": "654号"
                        },
                        "birth_place": {
                            "province": "上海市",
                            "city": "上海市",
                            "district": "黄浦区"
                        },
                        "personality": "ENTP",
                        "economic_level": "中产",
                        "occupation": "互联网产品经理",
                        "organization": "深圳某科技公司",
                        "nickname": "多多",
                        "relation_description": "钱多多是徐静的高中同学，大学毕业后选择到深圳发展。她们主要通过微信保持联系，每季度会视频通话一次。钱多多每年回上海探亲时会与徐静见面，平时在同学群里活跃互动。虽然距离较远，但她们仍保持着深厚的同学情谊，经常分享职场经验和生活趣事。"
                    }
                ],
                [
                    {
                        "name": "陈丽",
                        "relation": "同事",
                        "social circle": "工作圈",
                        "gender": "女",
                        "age": 26,
                        "birth_date": "1997-03-15",
                        "home_address": {
                            "province": "上海市",
                            "city": "上海市",
                            "district": "浦东新区",
                            "street_name": "金桥路",
                            "street_number": "456号"
                        },
                        "birth_place": {
                            "province": "江苏省",
                            "city": "南京市"
                        },
                        "personality": "ENFP",
                        "economic_level": "中等",
                        "occupation": "服装销售员",
                        "organization": "时尚服饰零售企业",
                        "nickname": "丽丽",
                        "relation_description": "陈丽是徐静在服装店的同事，两人相识于2019年工作期间。作为销售团队的核心成员，她们每天共同处理店面事务，配合默契。工作之余会一起在商场餐厅吃午餐，周末偶尔相约逛街淘货。两人居住在同一城区，保持每周5天的工作接触和每月1-2次的私人聚会。"
                    },
                    {
                        "name": "刘伟",
                        "relation": "同事",
                        "social circle": "工作圈",
                        "gender": "男",
                        "age": 30,
                        "birth_date": "1993-11-22",
                        "home_address": {
                            "province": "上海市",
                            "city": "上海市",
                            "district": "闵行区",
                            "street_name": "虹梅路",
                            "street_number": "789号"
                        },
                        "birth_place": {
                            "province": "浙江省",
                            "city": "杭州市"
                        },
                        "personality": "ISTJ",
                        "economic_level": "中等",
                        "occupation": "仓储管理员",
                        "organization": "时尚服饰零售企业",
                        "nickname": "伟哥",
                        "relation_description": "刘伟负责店铺的仓储管理工作，与徐静在工作中密切配合已有3年。他做事严谨认真，经常协助徐静处理货品调配和库存盘点。两人主要在工作场合交流，偶尔参加公司组织的团建活动。虽然私下交往不多，但工作关系稳定可靠，保持每天工作时间的常规互动。"
                    },
                    {
                        "name": "赵敏",
                        "relation": "同事",
                        "social circle": "工作圈",
                        "gender": "女",
                        "age": 29,
                        "birth_date": "1994-05-08",
                        "home_address": {
                            "province": "上海市",
                            "city": "上海市",
                            "district": "徐汇区",
                            "street_name": "淮海中路",
                            "street_number": "321号"
                        },
                        "birth_place": {
                            "province": "上海市",
                            "city": "上海市"
                        },
                        "personality": "ESFP",
                        "economic_level": "中等",
                        "occupation": "销售助理",
                        "organization": "时尚服饰零售企业",
                        "nickname": "敏敏",
                        "relation_description": "赵敏是徐静最亲密的同事之一，两人既是工作搭档也是朋友。她们经常一起讨论销售策略，下班后偶尔相约喝咖啡聊天。赵敏性格活泼开朗，与徐静在工作上形成良好互补。两人保持每周工作日的密切合作，每月会有2-3次私人聚会，关系融洽而稳定。"
                    },
                    {
                        "name": "孙老板",
                        "relation": "供应商",
                        "social circle": "工作圈",
                        "gender": "男",
                        "age": 45,
                        "birth_date": "1978-09-12",
                        "home_address": {
                            "province": "广东省",
                            "city": "广州市",
                            "district": "天河区",
                            "street_name": "体育西路",
                            "street_number": "668号"
                        },
                        "birth_place": {
                            "province": "广东省",
                            "city": "潮州市"
                        },
                        "personality": "ENTJ",
                        "economic_level": "富裕",
                        "occupation": "服装厂老板",
                        "organization": "广州时尚制衣厂",
                        "nickname": "孙总",
                        "relation_description": "孙老板是服装店的主要供应商，与徐静保持业务往来已有5年。他每季度会来上海考察市场，徐静负责接待和洽谈订单。两人主要通过电话和微信沟通业务，见面频率较低但合作稳定。孙老板注重产品质量和商业信誉，与徐静建立了相互信任的工作关系。"
                    },
                    {
                        "name": "周经理",
                        "relation": "商场经理",
                        "social circle": "工作圈",
                        "gender": "男",
                        "age": 38,
                        "birth_date": "1985-12-03",
                        "home_address": {
                            "province": "上海市",
                            "city": "上海市",
                            "district": "静安区",
                            "street_name": "南京西路",
                            "street_number": "1000号"
                        },
                        "birth_place": {
                            "province": "上海市",
                            "city": "上海市"
                        },
                        "personality": "ESTJ",
                        "economic_level": "中高",
                        "occupation": "商场运营经理",
                        "organization": "世纪商场管理公司",
                        "nickname": "周经理",
                        "relation_description": "周经理是店铺所在商场的运营负责人，与徐静在工作上有频繁的业务往来。他负责商场的日常管理和商户协调，徐静经常需要与他沟通店铺运营事宜。两人每月会有1-2次正式会议，平时通过商场内部系统保持联系。周经理处事专业严谨，与徐静保持着良好的工作关系。"
                    }
                ],
                [
                    {
                        "name": "孙秀英",
                        "relation": "邻居",
                        "social circle": "社区圈",
                        "gender": "女",
                        "age": 65,
                        "birth_date": "1959-03-22",
                        "home_address": {
                            "province": "上海市",
                            "city": "上海市",
                            "district": "浦东新区",
                            "street_name": "张杨路",
                            "street_number": "121号"
                        },
                        "birth_place": {
                            "province": "江苏省",
                            "city": "南通市"
                        },
                        "personality": "ISFJ",
                        "economic_level": "中等",
                        "occupation": "退休教师",
                        "organization": "浦东新区实验小学（已退休）",
                        "nickname": "孙阿姨",
                        "relation_description": "孙阿姨是徐静家对门的老邻居，退休前在附近小学任教。两人因社区活动相识，孙阿姨经常关心徐静的工作生活，会分享自己做的家常菜。现在主要通过微信保持联系，每周会碰面两三次，一起在小区散步或喝茶聊天。孙阿姨把徐静当作自家晚辈般照顾，逢年过节会互相赠送小礼物。"
                    }
                ],
                [
                    {
                        "name": "周晓雯",
                        "relation": "瑜伽教练",
                        "social circle": "瑜伽圈",
                        "gender": "女",
                        "age": 32,
                        "birth_date": "1991-03-15",
                        "home_address": {
                            "province": "上海市",
                            "city": "上海市",
                            "district": "徐汇区",
                            "street_name": "淮海中路",
                            "street_number": "356号"
                        },
                        "birth_place": {
                            "province": "浙江省",
                            "city": "杭州市"
                        },
                        "personality": "ENFJ",
                        "economic_level": "中产",
                        "occupation": "瑜伽馆",
                        "organization": "静心瑜伽工作室",
                        "nickname": "周老师",
                        "relation_description": "周晓雯是徐静在静心瑜伽工作室的专职教练，拥有8年瑜伽教学经验。两人通过2019年的团体课程相识，现在保持每周三次的私教课联系。上课时周教练会针对徐静的身体状况设计个性化训练方案，课后偶尔会交流健康饮食心得。虽然周教练住在徐汇区，但工作室距离徐静工作地点仅15分钟车程，教学关系稳定持续。"
                    },
                    {
                        "name": "李娜",
                        "relation": "瑜伽伙伴",
                        "social circle": "瑜伽圈",
                        "gender": "女",
                        "age": 29,
                        "birth_date": "1994-09-22",
                        "home_address": {
                            "province": "上海市",
                            "city": "上海市",
                            "district": "浦东新区",
                            "street_name": "陆家嘴环路",
                            "street_number": "188号"
                        },
                        "birth_place": {
                            "province": "江苏省",
                            "city": "苏州市"
                        },
                        "personality": "ISFP",
                        "economic_level": "中产",
                        "occupation": "银行职员",
                        "organization": "浦东发展银行",
                        "nickname": "娜娜",
                        "relation_description": "李娜是徐静在瑜伽课上认识的固定练习伙伴，同在周教练的早课班练习两年。作为银行柜员，李娜下班后常与徐静结伴练习瑜伽，周末偶尔一起逛商场喝下午茶。两人住在同一行政区，每月会约两三次课后聚餐，交流工作和生活近况。李娜性格内向但体贴，经常与徐静分享护肤心得，是瑜伽圈里最亲近的练习搭档。"
                    },
                    {
                        "name": "王芳",
                        "relation": "瑜伽伙伴",
                        "social circle": "瑜伽圈",
                        "gender": "女",
                        "age": 31,
                        "birth_date": "1992-12-05",
                        "home_address": {
                            "province": "江苏省",
                            "city": "南京市",
                            "district": "鼓楼区",
                            "street_name": "北京西路",
                            "street_number": "72号"
                        },
                        "birth_place": {
                            "province": "安徽省",
                            "city": "合肥市"
                        },
                        "personality": "ENTP",
                        "economic_level": "小康",
                        "occupation": "自由职业者",
                        "organization": "自媒体工作室",
                        "nickname": "芳芳",
                        "relation_description": "王芳原是上海工作的瑜伽同伴，2021年移居南京发展自媒体事业，但仍通过线上群组与徐静保持联系。两人在2018年瑜伽进修班相识，曾经常结伴参加周末瑜伽工作坊。现在主要通过微信群分享瑜伽视频和健康资讯，每年王芳回沪探亲时会与徐静、李娜小聚。虽然异地发展，但三人仍维持着瑜伽圈的友谊，经常互相关注彼此的生活动态。"
                    }
                ],
                [
                    {
                        "name": "张秀英",
                        "relation": "姨妈",
                        "social circle": "亲戚圈",
                        "gender": "女",
                        "age": 58,
                        "birth_date": "1965-03-22",
                        "home_address": {
                            "province": "江苏省",
                            "city": "南京市",
                            "district": "鼓楼区",
                            "street_name": "中山北路",
                            "street_number": "256号"
                        },
                        "birth_place": {
                            "province": "上海市",
                            "city": "上海市",
                            "district": "黄浦区"
                        },
                        "personality": "ISFJ",
                        "economic_level": "小康",
                        "occupation": "退休教师",
                        "organization": "南京市鼓楼区实验小学",
                        "nickname": "张阿姨",
                        "relation_description": "张秀英是徐静母亲的姐姐，退休前在南京担任小学教师。两人虽然分居上海和南京，但每月会通过视频通话联系两到三次，主要聊家常和健康话题。每年春节和国庆节徐静会去南京探望，一起逛夫子庙、品尝南京小吃。张秀英经常关心徐静的婚姻和工作情况，是徐静重要的长辈倾诉对象。"
                    },
                    {
                        "name": "刘建国",
                        "relation": "舅舅",
                        "social circle": "亲戚圈",
                        "gender": "男",
                        "age": 55,
                        "birth_date": "1968-09-15",
                        "home_address": {
                            "province": "浙江省",
                            "city": "杭州市",
                            "district": "西湖区",
                            "street_name": "文三路",
                            "street_number": "189号"
                        },
                        "birth_place": {
                            "province": "上海市",
                            "city": "上海市",
                            "district": "静安区"
                        },
                        "personality": "ESTP",
                        "economic_level": "富裕",
                        "occupation": "餐饮企业主",
                        "organization": "杭帮菜餐饮连锁集团",
                        "nickname": "刘叔叔",
                        "relation_description": "刘建国是徐静的舅舅，在杭州经营连锁餐饮企业。他性格开朗，经常给徐静提供创业建议。两人每季度通一次电话，主要讨论商业经营和市场趋势。每年徐静会专程到杭州品尝舅舅的新菜品，同时考察当地服装市场。刘建国曾资助徐静参加商业管理培训，是她在事业上的重要支持者。"
                    },
                    {
                        "name": "陈明",
                        "relation": "表弟",
                        "social circle": "亲戚圈",
                        "gender": "男",
                        "age": 25,
                        "birth_date": "1998-12-03",
                        "home_address": {
                            "province": "广东省",
                            "city": "深圳市",
                            "district": "南山区",
                            "street_name": "科技园路",
                            "street_number": "66号"
                        },
                        "birth_place": {
                            "province": "上海市",
                            "city": "上海市",
                            "district": "浦东新区"
                        },
                        "personality": "ENTJ",
                        "economic_level": "中产",
                        "occupation": "互联网产品经理",
                        "organization": "深圳某科技公司",
                        "nickname": "小明",
                        "relation_description": "陈明是徐静姑姑的儿子，目前在深圳从事互联网行业。两人从小一起在上海长大，现在主要通过微信保持联系，每周会分享生活趣事和工作心得。陈明经常给徐静推荐新的购物APP和时尚资讯，徐静则向他请教数字化营销知识。每年春节家庭聚会时见面，会一起逛商场、讨论最新的科技产品。"
                    }
                ],
                [
                    {
                        "name": "吴明远",
                        "relation": "家庭医生",
                        "social circle": "医疗圈",
                        "gender": "男",
                        "age": 45,
                        "birth_date": "1978-03-22",
                        "home_address": {
                            "province": "上海市",
                            "city": "上海市",
                            "district": "徐汇区",
                            "street_name": "淮海中路",
                            "street_number": "568号"
                        },
                        "birth_place": {
                            "province": "江苏省",
                            "city": "南京市",
                            "district": "鼓楼区"
                        },
                        "personality": "ISTJ",
                        "economic_level": "中产",
                        "occupation": "全科医生",
                        "organization": "浦东新区社区卫生服务中心",
                        "nickname": "吴医生",
                        "relation_description": "吴医生是徐静的家庭医生，五年前通过社区健康管理项目相识。他每月为徐静提供一次健康咨询，主要通过微信进行线上沟通，偶尔在社区卫生服务中心面诊。吴医生性格严谨负责，擅长慢性病管理和健康指导，与徐静保持着专业而友好的医患关系。"
                    }
                ],
                [
                    {
                        "name": "郑明辉",
                        "relation": "健身教练",
                        "social circle": "健身圈",
                        "gender": "男",
                        "age": 32,
                        "birth_date": "1992-03-15",
                        "home_address": {
                            "province": "上海市",
                            "city": "上海市",
                            "district": "徐汇区",
                            "street_name": "漕溪北路",
                            "street_number": "258号"
                        },
                        "birth_place": {
                            "province": "江苏省",
                            "city": "南京市",
                            "district": "鼓楼区"
                        },
                        "personality": "ESTP",
                        "economic_level": "中产",
                        "occupation": "健身教练",
                        "organization": "力健健身俱乐部",
                        "nickname": "郑教练",
                        "relation_description": "郑明辉是徐静在力健健身俱乐部的私人教练，两人通过健身课程相识已有两年。他擅长制定个性化训练计划，每周指导徐静进行三次力量训练和有氧运动。平时主要通过微信沟通训练安排和饮食建议，每月会组织会员户外拓展活动。郑教练性格开朗务实，注重训练效果的同时也会关心会员的生活状态。"
                    }
                ],
                [
                    {
                        "name": "王明远",
                        "relation": "纪念币藏友",
                        "social circle": "收藏圈",
                        "gender": "男",
                        "age": 45,
                        "birth_date": "1978-03-15",
                        "home_address": {
                            "province": "北京市",
                            "city": "北京市",
                            "district": "朝阳区",
                            "street_name": "建国门外大街",
                            "street_number": "88号"
                        },
                        "birth_place": {
                            "province": "北京市",
                            "city": "北京市"
                        },
                        "personality": "ISTJ",
                        "economic_level": "中产",
                        "occupation": "金融投资顾问",
                        "organization": "北京金融投资有限公司",
                        "nickname": "老王",
                        "relation_description": "王明远是徐静在纪念币收藏展会上认识的藏友，两人因共同爱好结缘。他目前在北京市从事金融投资工作，虽然分隔两地，但每月会通过线上交流收藏心得，偶尔会互相邮寄稀有纪念币。每年徐静去北京出差时会约见面，一起参观钱币博物馆或古玩市场。"
                    }
                ],
                [
                    {
                        "name": "李雪梅",
                        "relation": "同行朋友",
                        "social circle": "行业圈",
                        "gender": "女",
                        "age": 32,
                        "birth_date": "1991-03-15",
                        "home_address": {
                            "province": "浙江省",
                            "city": "杭州市",
                            "district": "西湖区",
                            "street_name": "文三路",
                            "street_number": "456号"
                        },
                        "birth_place": {
                            "province": "浙江省",
                            "city": "杭州市"
                        },
                        "personality": "ENTJ",
                        "economic_level": "中产",
                        "occupation": "区域运营经理",
                        "organization": "江南时尚集团",
                        "nickname": "雪梅姐",
                        "relation_description": "李雪梅是徐静在行业交流会上认识的同行朋友，两人因对服装零售业的共同兴趣而结缘。她们平时主要通过微信交流行业动态，每季度会在上海或杭州见面一次，通常选择在商圈咖啡馆讨论市场趋势和经营管理经验。虽然分处两地，但会互相推荐优质供应商和客户资源，去年还合作举办过跨区域促销活动。"
                    }
                ],
                [
                    {
                        "name": "张明远",
                        "relation": "熟客",
                        "social circle": "客户圈",
                        "gender": "男",
                        "age": 35,
                        "birth_date": "1988-03-15",
                        "home_address": {
                            "province": "浙江省",
                            "city": "杭州市",
                            "district": "西湖区",
                            "street_name": "文三路",
                            "street_number": "456号"
                        },
                        "birth_place": {
                            "province": "浙江省",
                            "city": "宁波市"
                        },
                        "personality": "ENTJ",
                        "economic_level": "中产",
                        "occupation": "互联网公司市场总监",
                        "organization": "杭州某科技股份有限公司",
                        "nickname": "张总",
                        "relation_description": "张明远是徐静服装店的长期客户，五年前因工作需要购买商务服装而结识。他每季度会从杭州来上海出差时到店选购，偏好简约商务风格。两人保持着专业的客户关系，主要通过微信沟通新款到货信息，平均每两月联系一次。见面时徐静会为他提供专业的穿搭建议，偶尔会聊及各自的工作近况。"
                    }
                ]
            ]
        }
    '''
extool.load_from_json(data,json.loads(persona))
# date = '2025-02-15'
# phone_gen(date)
# print('----------------------------------------------')
# for i in get_daily_events_with_subevent(mind.events,date):
#     print(i)
for i in iterate_dates('2025-01-01','2025-03-03'):
    phone_gen(i)
# 16