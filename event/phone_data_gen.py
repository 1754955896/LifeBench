import ast
import json
import re
import holidays
from pyarrow import string
from utils.IO import *
from datetime import datetime, timedelta
from utils.llm_call import *
from event.memory import *
import random
from typing import List, Dict, Optional, Tuple
class Data_extract:
    def __init__(self):
        self.events = []
        self.persona = ""
        self.persona_withoutrl = ""
        self.context = "你是一位手机数据专家和深度用户"
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
(注意message_content中不要包含双引号)
三、生成原则
仅保留与 “通话” 或 “短信” 直接相关的事件，无通信交互的事件需排除。
原始信息不明确时，基于事件场景（如 “快递咨询”“预约确认”）合理推测，符合常识；可结合个人画像推理更多场景，补充更多生活细节类通信（如家人问候、朋友事项沟通，广告，提醒等）。
必须关联联系人列表：事件对象在列表中时，直接使用姓名和电话；机构类按场景补充名称和常见号码。
关联交互生成逻辑：同一事件主通信方式生成后，可按 30% 概率生成反向交互（如回复对方，或被对方回复），但需保证时间线连贯（关联交互时间晚于主事件）。
四、输出格式要求
以 JSON 数组格式返回，同时包含通话和短信事件，仅输出JSON格式内容，直接以[]作为开头结尾，不添加任何额外文本、注释或代码块标记。不要输出```json等无关字段，示例如下：

[{{"type": "call","event_id": "evt001","phoneNumber": "+8613912345678","contactName": "张三","start_time": "2023-10-01 09:30:00","end_time": "2023-10-01 09:35:20","direction": 1}},{{"type": "sms","event_id": "evt002","message_content": "【美团外卖】您的订单 #12345 已接单，预计 30 分钟送达","contactName": "美团外卖","contact_phone_number": "10690000123","timestamp": "2023-10-01 12:10:15","message_type": "接收"}},{{"type": "call","event_id": "evt001_related","phoneNumber": "+8613912345678","contactName": "张三","start_time": "2023-10-01 10:05:10","end_time": "2023-10-01 10:08:33","direction": 0}}]

请基于用户提供的事件列表：{event}、联系人列表：{contacts} 和个人画像 {persona}，按上述要求生成手机通信事件。
'''

phone_event_Gallery_template = '''
请基于用户提供的事件列表和个人画像，分析可能产生的拍照行为，生成结构化的“手机图片/拍照数据（Phone Photo Data）”。生成需严格遵循以下要求：
一、核心规则：场景细分与概率
1. 拍照场景概率分配（按事件类型）：
- 旅行事件：风景打卡30%、人物合影20%、美食记录20%、导视牌/门票15%、细节特写15%
- 会议事件：PPT截图40%、参会人员20%、会议纪要手写板20%、会场环境20%
- 日常事件：美食25%、宠物20%、物品收纳15%、街头风景15%、文档扫描25%
2. 数量约束：单个事件生成1-3张图片，避免过度生成

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
(注意description中不要包含双引号)
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
(注意content中不要包含双引号)
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
4. 画像匹配：个人类推送需包含用户行为偏好（如股民→雪球股票行情，宝妈→宝宝树育儿提醒）,出画像外也可以基于事件描述的内容生成用户感兴趣的推送。

四、输出格式要求
输出格式严格要求,仅输出JSON格式内容，不添加任何额外文本、注释或代码块标记。只输出一个数组，无论有没有事件来源都放在该数组内。(注意推送内容中不要包含双引号,不要出现如"content":"【网易云音乐】为您推荐"长途驾驶放松音乐"歌单，陪伴您的货运旅程"这样双引号包裹双引号的情况，会导致字符串转json失败。示例：
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

def contact_gen(persona):
    temp = '''
    请根据以下 Persona 信息，参考给出的 Few-Shot 示例格式，生成对应的联系人列表。要求如下：
提取 Persona 中「relation」字段下所有关联人物，不遗漏任何一位，确保覆盖所有社交圈层；
联系人列表固定包含 8 个字段，字段顺序严格遵循示例：「name」「relation」「gender」「nickname」「phoneNumber」「personalEmail」「workEmail」「idNumber」；
各字段需与 Persona 中对应人物属性一致：phoneNumber 按人物所属省份合理虚构手机号段，personalEmail 结合姓名、所在城市拼音缩写 + 常见邮箱后缀（163.com/qq.com/126.com等），workEmail 结合姓名、所属组织拼音 / 英文缩写 + 常见后缀，idNumber 按人物 birth_date 和性别规则虚构（18 位，第 17 位男性为奇数、女性为偶数）；
最终输出标准 JSON 数组结构，无额外文字说明，格式整洁无冗余。
示例：
[{{"name": "徐明","relation": "父亲","gender": "男","nickname": "老爸","phoneNumber": "13917895623","personalEmail": "xuming_sh@163.com","workEmail": "xuming@mingfangfushi.com","idNumber": "310101196503124517"}},{{"name": "王丽","relation": "闺蜜","gender": "女","nickname": "丽丽","phoneNumber": "13681792345","personalEmail": "wangli_xh@163.com","workEmail": "wangli@shad.com","idNumber": "310104199303152826"}}]
参考persona:{persona}
    '''
    prompt = temp.format(persona=persona)
    res = llm_call(prompt)
    print(res)
    return res

extool = Data_extract()


def clean_json_string(json_str: str) -> str:
    """
    清理JSON字符串，使其能正常解析
    主要处理：
    1. 去除字符串值中的未转义换行符
    2. 处理值中的双引号（转义或去除，可选）
    3. 清理多余的空白字符
    4. 确保JSON格式合法
    """
    # 1. 先清理字符串两端的空白字符（包括换行、制表符等）
    cleaned = json_str.strip()

    # 2. 处理字符串值中的未转义换行符和双引号
    # 正则匹配JSON中的字符串值部分（"key": "value" 中的value）
    def replace_in_value(match: re.Match) -> str:
        # match.group(1) 是 key 部分，match.group(2) 是 value 部分
        key_part = match.group(1)
        value_part = match.group(2)

        # 处理value中的换行符：替换为空格或转义符（根据需求选择）
        # 方案1：替换为空格（推荐，可读性更好）
        value_part = value_part.replace('\n', ' ')
        # 方案2：转义为 \n（如果需要保留换行结构）
        # value_part = value_part.replace('\n', '\\n')

        # 处理value中的双引号：可以选择去除或转义
        # 方案1：去除双引号
        value_part = value_part.replace('"', '')
        # 方案2：转义双引号（如果需要保留双引号）
        # value_part = value_part.replace('"', '\\"')

        # 清理多余的空格（连续多个空格合并为一个）
        value_part = re.sub(r'\s+', ' ', value_part).strip()

        return f'"{key_part}": "{value_part}"'

    # 正则匹配所有 "key": "value" 格式的字符串
    # 匹配规则："任意key": "任意value"（value中可以包含除未转义双引号外的任意字符）
    cleaned = re.sub(
        r'"([^"]+)":\s*"([^"]*)"',
        replace_in_value,
        cleaned,
        flags=re.DOTALL  # 让.匹配换行符（虽然我们之后会处理换行）
    )

    # 3. 处理数组和对象末尾可能的逗号（防止多余逗号导致报错）
    cleaned = re.sub(r',\s*]', ']', cleaned)
    cleaned = re.sub(r',\s*}', '}', cleaned)

    return cleaned

def phone_gen(date,contact,file_path,a,b,c,d):
    #获取今日daily_event
    res1 = extool.filter_by_date(date)
    res = []
    for i in range(len(res1)):
        if "-" in res1[i]['event_id']:
            continue
        res.append(res1[i])
        print(res1[i]['event_id'])
    #callrecord+message
    prompt = phone_event_MSM_template.format(event=res, contacts=contact, persona=extool.persona_withoutrl)
    res = llm_call(prompt, extool.context)
    print(res)
    res = remove_json_wrapper(res)
    res = clean_json_string(res)
    data = json.loads(res)
    c += data
    #gallery
    prompt = phone_event_Gallery_template.format(event=res, persona=extool.persona)
    resx = llm_call(prompt, extool.context)
    print(resx)
    resx = remove_json_wrapper(resx)
    resx = clean_json_string(resx)
    data = json.loads(resx)
    a+=data
    #push
    prompt = phone_event_Push_template.format(event=res,contacts=contact,persona=extool.persona_withoutrl,msm=resx)
    res = llm_call(prompt, extool.context)
    print(res)
    res = remove_json_wrapper(res)
    res = clean_json_string(res)
    data = json.loads(res)
    b += data
    #calendar+note
    prompt = phone_event_Calendar_template.format(event=res,back = get_daily_events_with_subevent(extool.events,date),persona=extool.persona_withoutrl)
    res = llm_call(prompt,extool.context)
    print(res)
    res = remove_json_wrapper(res)
    res = clean_json_string(res)
    data =json.loads(res)
    d += data
    with open(file_path+"phone_data/event_note.json", "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    with open(file_path+"phone_data/event_call.json", "w", encoding="utf-8") as f:
        json.dump(c, f, ensure_ascii=False, indent=2)
    with open(file_path+"phone_data/event_gallery.json", "w", encoding="utf-8") as f:
        json.dump(a, f, ensure_ascii=False, indent=2)
    with open(file_path+"phone_data/event_push.json", "w", encoding="utf-8") as f:
        json.dump(b, f, ensure_ascii=False, indent=2)

    return

class CommunicationOperationGenerator:
    def __init__(self, random_seed: int = 42):
        random.seed(random_seed)
        self.supported_scenes = ["紧急事务", "服务通知", "日常社交", "商务交互", "无通信需求"]

    def parse_llm_prob_json(self, llm_json_str: str) -> List[Dict]:
        """
        核心优化：直接提取首尾[]之间的内容，忽略所有包裹标记（```json、换行、空格等）
        不管 LLM 输出格式如何，只要核心是[]包裹的JSON数组，就能解析
        """
        try:
            # 第一步：找到第一个[和最后一个]的位置，提取中间内容
            start_idx = llm_json_str.find('[')
            end_idx = llm_json_str.rfind(']')
            if start_idx == -1 or end_idx == -1 or start_idx >= end_idx:
                print("错误：未找到有效的JSON数组（缺少[]包裹）")
                return []

            # 提取[]之间的核心JSON内容，清理首尾空白
            core_json_str = llm_json_str[start_idx:end_idx + 1].strip()

            # 第二步：解析JSON数组
            events = json.loads(core_json_str)

            # 第三步：校验必填字段（确保精简后的字段完整）
            required_fields = [
                "event_id", "event_name", "event_basic", "communication_scene",
                "trigger_probability", "type_probability", "multi_sms_probability",
                 "scene_reasoning"
            ]
            valid_events = []
            for event in events:
                if isinstance(event, dict) and all(f in event for f in required_fields):
                    # 校验event_basic必填子字段
                    basic_required = ["time", "is_multi_topic", "duration"]
                    if all(sub_f in event["event_basic"] for sub_f in basic_required):
                        valid_events.append(event)
                    else:
                        print(
                            f"警告：事件{event.get('event_id', '未知ID')}的event_basic缺少子字段（time/is_multi_topic/duration），跳过")
                else:
                    print(f"警告：事件{event.get('event_id', '未知ID')}缺少必要字段或格式错误，跳过")
            return valid_events
        except json.JSONDecodeError as e:
            print(f"JSON解析失败：位置{e.pos}，原因{e.msg}")
            print(f"提取的核心JSON前200字符：{core_json_str[:200]}...")  # 辅助排查
            return []
        except Exception as e:
            print(f"解析异常：{str(e)}")
            return []

    def _prob_sample(self, prob_str: str) -> bool:
        """概率触发抽样（如"30%"→True/False）"""
        try:
            prob = int(prob_str.strip('%'))
            return random.random() < max(0, min(100, prob)) / 100
        except:
            print(f"警告：概率格式错误（{prob_str}），默认返回False")
            return False

    def _sample_type(self, prob_dict: Dict[str, str]) -> str:
        """抽样通信类型（call/sms）"""
        items = []
        for k, v in prob_dict.items():
            try:
                prob = int(v.strip('%'))
                items.append((k, prob))
            except:
                print(f"警告：通信类型概率格式错误（{k}: {v}），跳过该选项")
                continue
        if not items:
            return "sms"  # 默认短信
        keys, probs = zip(*items)
        total = sum(probs)
        return random.choices(keys, weights=[p / total for p in probs], k=1)[0]

    def _sample_sms_count(self, multi_sms_info: Dict) -> int:
        """抽样多短信数量（基于multi_sms_probability）"""
        sms_count_list = multi_sms_info["sms_count"]
        count_probs = []
        for item in sms_count_list:
            try:
                count_str, prob_str = item.split(':')
                count = int(count_str.replace('条', ''))
                prob = int(prob_str.strip('%'))
                count_probs.append((count, prob))
            except:
                print(f"警告：多短信概率格式错误（{item}），跳过该选项")
                continue
        if not count_probs:
            return 1  # 默认1条短信
        counts, probs = zip(*count_probs)
        total = sum(probs)
        return random.choices(counts, weights=[p / total for p in probs], k=1)[0]

    def process_single_event(self, event: Dict) -> List[str]:
        """处理单个事件，生成通信操作指令（含多短信逻辑）"""
        event_id = event["event_id"]
        event_name = event["event_name"]
        scene = event["communication_scene"]
        event_time = event["event_basic"]["time"]
        is_multi_topic = event["event_basic"]["is_multi_topic"] == "是"
        operations = []

        # 1. 处理事件相关通信
        related_trigger = event["trigger_probability"]["related"]
        if self._prob_sample(related_trigger) and scene != "无通信需求":
            comm_type = self._sample_type(event["type_probability"]["related"])
            # 若为短信，抽样短信条数（多主题自动生成多条）
            if comm_type == "sms":
                sms_count = self._sample_sms_count(event["multi_sms_probability"])
                for i in range(1, sms_count + 1):
                    topic_note = f"（主题{i}/{sms_count}，对应事件子主题）" if is_multi_topic else ""
                    instr = (
                        f"【事件相关通信】event_id：{event_id}_sms{i}，事件名称：{event_name}，"
                        f"场景：{scene}，通信类型：短信{topic_note}"
                    )
                    operations.append(instr)
            # 若为通话
            else:
                instr = (
                    f"【事件相关通信】event_id：{event_id}_call，事件名称：{event_name}，"
                    f"场景：{scene}，通信类型：通话，"
                )
                operations.append(instr)

        # 2. 处理事件无关通信
        unrelated_trigger = event["trigger_probability"]["unrelated"]
        if self._prob_sample(unrelated_trigger):
            comm_type = self._sample_type(event["type_probability"]["unrelated"])
            if comm_type == "sms":
                instr = (
                    f"【事件无关通信】event_id：{event_id}_unrelated_sms，事件名称：{event_name}，"
                    f"场景：事项提醒/亲友问候/生活咨询，通信类型：短信，时间：{event_time}当日8-21点，"
                )
                operations.append(instr)
            else:
                instr = (
                    f"【事件无关通信】event_id：{event_id}_unrelated_call，事件名称：{event_name}，"
                    f"场景：亲友问候，通信类型：通话，时间：{event_time}当日8-21点，"
                )
                operations.append(instr)

        return operations

    def generate_llm_instructions(self, llm_json_str: str) -> str:
        """入口函数：生成最终LLM操作指令字符串"""
        events = self.parse_llm_prob_json(llm_json_str)
        if not events:
            return "无有效事件数据，无需生成通信操作。"

        all_instructions = []
        for event in events:
            all_instructions.extend(self.process_single_event(event))

        if not all_instructions:
            return "所有事件未触发通信操作，无需生成手机操作数据。"

        # 格式化指令（清晰易读，LLM可直接解析）
        final_instr = (
                "请按以下指令生成手机通信操作（通话/短信），严格遵循字段要求和内容逻辑：\n"
        )

        for idx, instr in enumerate(all_instructions):
            final_instr += f"{idx}. {instr}\n" + "-" * 60 + "\n"

        return final_instr
    def phone_gen_callandmsm(self,date, contact, file_path, c):
            event_classify = '''
               请基于用户提供的{{当日事件}}和{{个人画像}}，逐一对每个事件进行独立分析，输出精简后的核心属性及通信概率（无需方向字段），按真实场景常识判断多短信个数概率。分析需严格遵循以下要求，可结合事件细节灵活微调概率（±5%内），确保概率逻辑自洽、贴合现实生活规律：

                ### 一、分析核心维度（每个事件必须完整输出以下8项，字段不可缺失）
                #### 1. 事件基础信息
                - 输出字段：event_id（严格沿用原事件唯一标识，不添加任何额外文本）、event_name（完整保留原事件名称）
                - 输出格式：`"event_id": "xxx", "event_name": "xxx"`
                
                #### 2. 事件基础属性提取
                - 提取关键要素：事件时间（精确到分钟，格式YYYY-MM-DD HH:MM）、场景关键词（2-4个核心词，如"家庭早餐/互动"）、行为目的（简洁描述核心诉求，如"家庭情感交流"）、是否面对面（是/否，严格按事件场景判断）、关联人员状态（说明关系+数量，可填多个用“/”分隔，如"家人2人/朋友1人"）、持续时长（按事件实际合理估算，格式xx分钟）、是否多主题（是/否，判断事件是否包含≥2个独立诉求）
                - 输出格式：`"event_basic": {{"time": "xxx", "scene_keyword": "xxx", "purpose": "xxx", "is_face_to_face": "xxx", "related_person_status": "xxx", "duration": "xx分钟", "is_multi_topic": "xxx"}}`
                
                #### 3. 通信场景分类（主场景唯一归属，严格匹配事件核心属性）
                事件相关通信可选分类：紧急事务（如突发情况处理、重要事项紧急协调）、服务通知（如订单提醒、机构告知、业务办理通知）、社交互动（如亲友问候、聚会约见、情感交流）、商务交互（如工作对接、会议协调、客户沟通）、日常生活（如购物咨询、出行规划、便民服务）、无通信需求（如独自休闲、无外部关联的个人行为）
                - 输出格式：`"communication_scene": "xxx"`
                
                #### 4. 通信触发概率（分“事件相关”和“事件无关”，取值0%-100%，保留整数）
                - 计算依据（基础值+修正项，总和强制约束在0%-100%，逻辑优先级：基础值→核心修正→微调）：
                  - 基础概率（贴合场景本质通信需求）：
                    - 相关通信：紧急事务90%、服务通知85%、社交互动70%、商务交互80%、日常生活45%、无通信需求0%；
                    - 无关通信（随机外部干扰/主动联络）：基础15%（无特殊情况默认此值）。
                  - 核心修正规则（按影响程度排序，叠加计算）：
                    1. 面对面场景：事件相关通信-35%（现场已直接交流，大幅降低远程沟通需求）；若相关通信基础值≤35%，修正后最低保留0%；
                    2. 多主题/关联人员≥2人：相关通信+10%（需求复杂/涉及多人，需额外沟通确认）；
                    3. 高频时段（8:00-9:00/12:00-13:00/19:00-21:00）：无关通信+5%（该时段为社交/事务活跃期，随机联络概率提升）；
                    4. 低频时段（0:00-7:00/22:00-24:00）：无关通信-8%（夜间休息时段，随机联络概率降低，最低保留5%）；
                    5. 个人画像修正：社交型人格→相关通信+10%/无关通信+5%（主动沟通意愿强）；职场人→商务类相关通信+10%（工作场景沟通需求更高）；内向型人格→相关通信-5%/无关通信-3%（被动沟通为主）；
                    6. 事件属性修正：短时长事件（≤15分钟）→相关通信-5%（事务简单，沟通需求低）；长时长事件（≥60分钟）→相关通信+5%（事务复杂，需多轮沟通）。
                  - 特殊规则：
                    1. 无关通信概率最低保留5%（即使低频时段/内向人格，仍存在极小概率随机联络）；
                    2. 无通信需求场景：相关通信强制0%，无关通信按规则计算（最低5%）；
                    3. 最终概率可在±5%内微调（基于事件合理性，如“独自看电影”无关通信可降至5%，“节日期间社交”无关通信可升至20%）。
                - 输出格式：`"trigger_probability": {{"related": "xx%", "unrelated": "xx%"}}`
                
                #### 5. 通信类型概率（通话/短信，触发概率>0时计算，两类概率总和100%，保留整数）
                - 基础规则（贴合场景沟通习惯）：
                  - 相关通信：
                    - 紧急事务：通话90%/短信10%（紧急情况需实时沟通，优先通话）；
                    - 服务通知：短信80%/通话20%（机构通知以低成本短信为主，重要通知可能电话补充）；
                    - 社交互动：短信70%/通话30%（日常社交以异步短信为主，亲密关系可能通话）；
                    - 商务交互：通话60%/短信40%（工作沟通需高效确认，通话占比更高）；
                    - 日常生活：短信75%/通话25%（便民服务/购物咨询以短信为主，复杂需求可能通话）；
                  - 无关通信：
                    - 亲友问候：短信60%/通话40%（日常问候短信便捷，亲密关系可能通话）；
                    - 事项提醒：短信85%/通话15%（提醒类信息无需实时响应，优先短信）；
                    - 生活咨询：短信50%/通话50%（咨询可能涉及细节，通话/短信概率均等）；
                    - 其他交流：短信70%/通话30%（随机交流以短信为主，避免打扰对方）。
                - 修正项（叠加计算，总和保持100%）：
                  1. 面对面场景→相关通信短信概率-10%/通话概率+10%（现场已交流，远程短信需求降低，若需补充沟通优先简短通话）；
                  2. 多参与者/复杂事项→短信概率+10%/通话概率-10%（需传递明确信息，短信可留痕、便于多人同步）；
                  3. 高频时段→通话概率+5%（对方接听概率高，优先通话）；
                  4. 低频时段→通话概率-10%（避免打扰对方，优先短信，最低保留5%）。
                - 输出格式：`"type_probability": {{"related": {{"call": "xx%", "sms": "xx%"}}, "unrelated": {{"call": "xx%", "sms": "xx%"}}}}`
                
                #### 6. 多短信生成概率（仅短信类型触发时计算，各类概率总和100%，保留整数）
                - 核心逻辑：基于事件复杂度、参与者数量、沟通目的，按常识分配概率，同时考虑“发送必要性”和“接收响应概率”，避免不合理的多短信场景：
                  - 简单场景（单参与者+事项单一+无后续需求，如“给家人报平安”“接收快递通知”）：1条85%、2条15%（2条仅为补充说明，无多余信息）；
                  - 一般场景（2-3个参与者/事项较简单+需确认，如“同事对接工作进度”“约2个朋友聚餐”）：1条60%、2条30%、3条10%（2条用于核心沟通，3条仅为细节补充）；
                  - 复杂场景（≥3个参与者/事项繁琐+多轮确认，如“组织部门团建协调时间”“多人旅行规划”）：1条10%、2条50%、3条35%、4条5%（需多轮同步信息，4条为上限，避免过度冗余）；
                  - 服务通知类（如“订单状态更新”“账单提醒”）：1条95%、2条5%（2条仅为补发场景，如首次未收到，无重复通知）。
                - 输出格式：`"multi_sms_probability": {{"sms_count": ["1条:xx%", "2条:xx%", ...], "note": "xxx"}}`（note需明确说明判断依据，如“2个参与者+事项简单，按一般场景分配；高频时段修正短信概率+5%”）
                
                #### 7. 场景推理说明（逻辑清晰、论据充分，覆盖3个核心点）
                - 必须包含：
                  1. 场景判定依据（结合事件时间、目的、参与者等属性说明为何归类该场景）；
                  2. 触发概率修正原因（逐一说明适用的修正规则，如“面对面场景-35%+多主题+10%，最终相关通信概率为XX%”）；
                  3. 多短信场景归类原因（说明场景复杂度/参与者数量，为何选择该概率分配）。
                - 输出格式：`"scene_reasoning": "xxx"`
                
                ### 二、分析原则（严格遵守，确保结果合理性）
                1. 概率逻辑自洽：修正项叠加后不得出现矛盾（如相关通信概率不可为负，通话/短信概率总和必须100%）；
                2. 贴合现实规律：避免极端概率（如无关通信不超过30%，复杂场景4条短信概率不超过10%）；
                3. 适配个人画像：通信概率需与用户人格特征匹配（如内向型人格通话概率低于外向型）；
                4. 输出精简规范：仅保留指定8项字段，无任何额外文本、注释，严格按JSON数组格式输出，字段顺序与要求一致。
                
                ### 三、输出格式要求（严格遵循，否则视为无效）
                仅输出JSON数组，每个元素对应一个事件，字段无缺失、无冗余，示例如下（可直接参考格式）：
                [
                  {{
                    "event_id": "5902",
                    "event_name": "早餐准备与家庭交流",
                    "event_basic": {{"time": "2025-12-01 07:00", "scene_keyword": "家庭早餐/互动", "purpose": "家庭情感交流", "is_face_to_face": "是", "related_person_status": "家人2人", "duration": "30分钟", "is_multi_topic": "否"}},
                    "communication_scene": "社交互动",
                    "trigger_probability": {{"related": "45%", "unrelated": "20%"}},
                    "type_probability": {{"related": {{"call": "35%", "sms": "65%"}}, "unrelated": {{"call": "40%", "sms": "60%"}}}},
                    "multi_sms_probability": {{"sms_count": ["1条:85%", "2条:15%"], "note": "单参与者+事项单一，按简单场景分配；面对面场景修正短信概率-10%"}},
                    "scene_reasoning": "判定为社交互动场景（事件目的为家庭情感交流，场景关键词符合）；触发概率修正：基础相关通信70%→面对面-35%→最终45%，无关通信基础15%+高频时段5%→最终20%；多短信按简单场景分配（单参与者+事项单一，无复杂沟通需求）"
                  }},
                  {{
                    "event_id": "5913",
                    "event_name": "组织部门团建协调时间",
                    "event_basic": {{"time": "2025-12-01 20:12", "scene_keyword": "商务+协调", "purpose": "团队活动组织", "is_face_to_face": "否", "related_person_status": "同事5人", "duration": "78分钟", "is_multi_topic": "是"}},
                    "communication_scene": "商务交互",
                    "trigger_probability": {{"related": "95%", "unrelated": "20%"}},
                    "type_probability": {{"related": {{"call": "45%", "sms": "55%"}}, "unrelated": {{"call": "15%", "sms": "85%"}}}},
                    "multi_sms_probability": {{"sms_count": ["1条:10%", "2条:50%", "3条:35%", "4条:5%"], "note": "≥3个参与者+事项繁琐，按复杂场景分配；多参与者修正短信概率+10%"}},
                    "scene_reasoning": "判定为商务交互场景（事件目的为团队活动组织，涉及同事关系，属于工作协调）；触发概率修正：基础相关通信80%→多主题+10%+长时长+5%→最终95%，无关通信基础15%+高频时段5%→最终20%；多短信按复杂场景分配（5个参与者+事项繁琐，需多轮同步信息）；通信类型修正：多参与者+10%短信概率，基础通话60%→45%、短信40%→55%"
                  }}
                ]
                
                请基于<当日事件>：{daily_events}、<个人画像>：{persona}，严格按上述要求逐事件分析并输出结果，确保每个字段的概率逻辑可追溯、符合现实场景。
            '''
            # 获取今日daily_event
            res1 = extool.filter_by_date(date)
            res = []
            for i in range(len(res1)):
                if "-" in res1[i]['event_id']:
                    continue
                res.append(res1[i])
                print(res1[i]['event_id'])
            mid = (len(res) + 1) // 2  # 向上取整（如5→3，4→2）
            # mid = len(arr) // 2  # 向下取整（如5→2，4→2，后半部分多1个）
            res1,res2 = res[:mid], res[mid:]
            prompt = event_classify.format(daily_events=res1, persona=extool.persona)
            a = llm_call(prompt)
            print(a)
            prompt = event_classify.format(daily_events=res2, persona=extool.persona)
            b = llm_call(prompt)
            print(b)
            resx1 = self.generate_llm_instructions(a)
            resx2 = self.generate_llm_instructions(b)
            print(resx1)
            print(resx2)
            template = '''
请基于用户提供的{{当日事件}}、{{联系人列表}}和{{操作指令}}，生成具体的手机通信操作（通话/短信），严格遵循以下字段规则、生成原则和输出格式，确保数据真实、唯一、无重复，优化时间逻辑和收发方向推断：

### 一、核心遵循原则（优先级：指令要求 > 场景逻辑 > 个人画像适配）
1. 指令强绑定：每个核心通信操作必须严格对应一条操作指令，完全遵守「event_id、通信场景、通信类型、时间范围、内容要求」，不得偏离核心诉求；关联交互需基于指令衍生，标注清晰关联关系。
2. 联系人优先规则：所有个人通信优先从联系人列表匹配`contactName`和`phoneNumber`；无联系人列表时，按场景合理虚构真实关系的联系人（如商务场景→“王经理”“李同事”，社交场景→“张朋友”“妈妈”）及11位有效手机号（格式`+861xxxxxxxxx`）。
3. 个人画像深度适配：通信内容、沟通语气、联系人选择、交互频率需贴合用户画像（如社交型人格倾向主动问候、多轮互动；职场人多商务沟通，语气专业简洁；内向型人格以被动接收为主，沟通内容简短）；事件无关通信需基于联系人关系设计合理场景（家人→生活关心、同事→工作寒暄、朋友→约饭/闲聊、客户→节日问候）。
4. 额外信息补充规则：
   - 关联交互：按20%概率生成核心通信的反向交互（如短信回复、通话后短信补充），`event_id`格式为“原ID_related_序号”（如`5903_sms1_related_1`）；
   - 广告/通知类短信：在指令生成短信基础上，额外增加10%的随机信息（占总短信数），类型含电商广告、服务营销、公益通知、运营商提醒，需贴合个人画像（如宝妈→母婴用品广告，职场人→办公设备/培训广告）；
   - 未接后续：未接通通话后5分钟内生成短信提醒（如“刚才给你打电话没通，有急事请回电”）。
### 二、字段规则（通话/短信严格按以下格式生成）
#### （一）通话类事件（type固定为"call"）
需包含7个字段，缺一不可：
- event_id：直接使用指令中的event_id（如"5904_call"）；关联交互（30%概率生成）填“原ID_related_序号”（如"5904_call_related_1"）
- type：固定值"call"
- phoneNumber：个人联系人填11位手机号（如"+86138xxxx7890"）；机构类填400/010号段或“官方服务号”
- contactName：个人通信填联系人列表中的真实姓名；机构类填官方名称（如"XX保险公司"）
- start_time：按指令时间范围+场景逻辑生成，格式"YYYY-MM-DD HH:MM:SS"：
  - 事件相关：
    - 提前通知类（如会议、活动协调）：事件发生前30分钟-24小时；
    - 同步/核对类（如数据、工作对接）：事件发生中或结束后10分钟内；
    - 紧急事务：事件发生时±5分钟；
  - 事件无关：指令指定时段内（如"2025-12-01 15:20当日8-21点"）随机生成合理时间
- end_time：按场景设定时长（±波动），晚于start_time：
  - 商务交互（工作对接/数据核对）：5-8分钟±30秒
  - 日常社交（亲友问候/约饭）：2-5分钟±30秒
  - 服务通知（机构确认/业务办理）：3-5分钟±30秒
- direction：0=呼入，1=呼出（按场景+关系合理推断，规则见“生成原则2”）
- call_result：固定"接通"（按指令要求）

#### （二）短信类事件（type固定为"sms"）
需包含7个字段，缺一不可：
- event_id：直接使用指令中的event_id（如"5903_sms1"）；关联交互（30%概率生成）填“原ID_related_序号”（如"5903_sms1_related_1"）；非事件关联填指令中的event_id（如"5901_unrelated_sms"）
- type：固定值"sms"
- message_content：符合场景逻辑、指令要求及联系人关系：
  - 事件关联（个人）：
    - 提前通知：明确时间、事项、要求（如“明天10点销售会议，记得带数据报表”）；
    - 同步/核对：简洁传递核心信息（如“商圈考察已完成，核心竞品活动总结已发你邮箱”）；
    - 服务通知：机构官方格式+脱敏信息（如【XX保险】您的保单已归档，保单号XXX，如需预约可回复“预约”）；
  - 事件无关（个人）：基于联系人关系设计场景（如家人→“最近降温，记得添衣”、同事→“上次你要的报表已整理好，需要发你吗”、朋友→“周末去新开的甜品店，一起吗”）
- message_category：事件关联通信填"事件关联"；事件无关通信填"非事件关联"；随机信息填"随机信息"（无需生成）
- random_type：固定填"无"（无需生成随机信息）
- contactName：优先联系人列表；个人通信填真实姓名；机构类填官方名称（如"XX电商"“XX保险公司”）
- contact_phone_number：个人填11位手机号；机构类填1069/400号段（如服务通知填10690000XXXX）
- timestamp：按指令时间范围+场景逻辑生成，格式"YYYY-MM-DD HH:MM:SS"（规则同通话类start_time）
- message_type：“发送”或“接收”（按场景+关系推断，规则见“生成原则2”）

### 三、生成原则
1. 时间逻辑优化：
   - 事件相关通信不再局限于“与事件时间接近”，而是按“通知/同步/紧急”三类场景分配时间（如“会议通知”提前1小时，“数据核对”事件中，“紧急协调”即时）；
   - 所有通信时间需在当日8:00-21:00，避免凌晨/深夜；关联交互时间晚于主事件1-5分钟，内容呼应主操作（如主短信“明天开会”→关联回复“收到，准时参加”）。
2. 收发方向推断（核心优化）：
   - 呼出/发送（主动）：
     - 事件相关：用户发起的通知、核对、协调（如“同步销售数据”“预约服务”）；
     - 事件无关：用户主动联系亲友/同事（如社交型人格问候家人、主动约朋友聚餐）；
     - 关系场景：用户对长辈、上级的问候/汇报，对平级的协调/约见。
   - 呼入/接收（被动）：
     - 事件相关：他人发起的与事件相关的沟通（如同事核对数据、机构通知保单归档）；
     - 事件无关：亲友/同事主动联系用户（如朋友约饭、家人关心生活）；
     - 关系场景：用户接收长辈的叮嘱、上级的安排、机构的服务通知。
3. 联系人与场景匹配：
   - 事件相关：优先选择与事件目的相关的联系人（如“销售数据核对”→同事/上级，“保险办理”→保险公司专员）；
   - 事件无关：基于联系人关系生成合理交流场景（如家人→生活关心、同事→工作寒暄、朋友→娱乐约见、客户→节日问候），避免无意义的泛泛沟通。
4. 合理优化，避免生成的短信同质，短信与短信之间也要协调连贯。
5. 去重与真实性：
   - 同一核心event_id仅生成1个核心操作，关联交互不视为重复；
   - 手机号格式规范（个人11位，机构1069/400/010号段），短信内容自然（个人口语化，机构官方化），无虚构格式。
### 四、输出格式要求
仅输出JSON数组内容，不添加任何额外文本、注释或代码块标记。每个元素对应1个通信操作，核心操作和关联交互按时间顺序排列。示例：
[
{{"type":"sms","event_id":"5901_unrelated_sms","message_content":"妈妈：宝贝，今天降温记得穿厚点，晚上回家给你炖了汤","message_category":"非事件关联","random_type":"无","contactName":"妈妈","contact_phone_number":"+86135xxxx2345","timestamp":"2025-12-01 09:15:30","message_type":"接收"}},
{{"type":"sms","event_id":"5903_sms1","message_content":"我：王总，明天10点销售会议，记得带最新数据报表，地点在3楼会议室","message_category":"事件关联","random_type":"无","contactName":"王总","contact_phone_number":"+86139xxxx6789","timestamp":"2025-12-01 09:00:10","message_type":"发送"}},
{{"type":"sms","event_id":"5903_sms1_related_1","message_content":"王总：收到，数据已整理好，准时参加","message_category":"事件关联","random_type":"无","contactName":"王总","contact_phone_number":"+86139xxxx6789","timestamp":"2025-12-01 09:02:20","message_type":"接收"}},
{{"type":"call","event_id":"5904_call","phoneNumber":"+86136xxxx8901","contactName":"李同事","start_time":"2025-12-01 08:10:00","end_time":"2025-12-01 08:16:30","direction":1,"call_result":"接通","type":"call"}},
{{"type":"sms","event_id":"5904_call_related_1","message_content":"李同事：数据核对无误，已同步给财务部门","message_category":"事件关联","random_type":"无","contactName":"李同事","contact_phone_number":"+86136xxxx8901","timestamp":"2025-12-01 08:20:15","message_type":"接收"}}
]

请基于{{操作指令}}：{instructions}、{{联系人列表}}：{contacts}、{{当日事件}}：{daily_events}生成具体通信操作。
'''
            prompt = template.format(daily_events=res1, contacts=contact, instructions=resx1)
            res = llm_call(prompt, extool.context)
            print(res)
            res = remove_json_wrapper(res)
            data = json.loads(res)
            c += data
            prompt = template.format(daily_events=res2, contacts=contact, instructions=resx2)
            res = llm_call(prompt, extool.context)
            print(res)
            res = remove_json_wrapper(res)
            data = json.loads(res)
            c += data
            print(c)
            return c

class NoteCalendarOperationGenerator:
    def __init__(self, random_seed: int = 42):
        """初始化生成器（设置随机种子确保可复现）"""
        random.seed(random_seed)
        # 核心约束：日历+笔记总数≤4（不常用操作，仅重要事件生成）
        self.max_total_output = 4
        # 非事件相关笔记额外约束：每天最多1个
        self.max_unrelated_note = 1
        # 定义事件类型优先级（确保重要事件优先生成）
        self.event_priority = [
            "重要事件-出行预定", "重要事件-重要会议",
            "重要事件-医疗预约", "重要事件-旅行计划",
            "日常事件-购物", "日常事件-普通社交",
            "非事件相关-兴趣爱好"
        ]
        # 明确概率范围（贴合"不常用"设定，整体调低概率）
        self.default_prob_ranges = {
            "calendar": (60, 85),  # 极重要事件才生成，概率低于之前
            "note_related": (50, 70),  #事件相关笔记概率降低
            "note_unrelated": (10, 20),  # 非事件相关笔记（诗词/知识点）概率10%-20%
            "calendar_invalid": 0,  # 非重要事件日历概率0%
            "note_related_daily": (0, 5)  #日常事件笔记概率0%-5%
        }

    def parse_llm_prob_json(self, llm_json_str: str) -> List[Dict]:
        """
        核心优化：直接提取首尾[]之间的内容，忽略所有包裹标记（```json、换行、空格等）
        不管 LLM 输出格式如何，只要核心是[]包裹的JSON数组，就能解析
        """
        try:
            # 第一步：找到第一个[和最后一个]的位置，提取中间内容
            start_idx = llm_json_str.find('[')
            end_idx = llm_json_str.rfind(']')
            if start_idx == -1 or end_idx == -1 or start_idx >= end_idx:
                print("错误：未找到有效的JSON数组（缺少[]包裹）")
                return []

            # 提取[]之间的核心JSON内容，清理首尾空白
            core_json_str = llm_json_str[start_idx:end_idx + 1].strip()

            # 第二步：解析JSON数组
            events = json.loads(core_json_str)

            return events
        except json.JSONDecodeError as e:
            print(f"JSON解析失败：位置{e.pos}，原因{e.msg}")
            return []
        except Exception as e:
            print(f"解析异常：{str(e)}")
            return []

    def _build_prob_modeling_prompt(self, daily_events: List[Dict], persona) -> str:
        """
        第一步Prompt：概率建模（仅输出事件ID和生成概率，差异化设计）
        核心：不涉及任何内容生成，仅判断"是否生成"及概率
        """
        return f'''
请基于用户提供的当日事件和个人画像，逐事件分析生成概率，仅输出事件ID和各类操作的生成概率，不涉及具体内容。
核心规则：日历和笔记是不常用操作，仅极重要事件才生成，总数一天不超过4个。

### 一、概率定义与约束
#### 1. 事件分类（严格对应）
- 极重要事件：出行预定、重要会议、医疗预约、旅行计划
- 较重要事件: 重要聚会，重要节点（婚礼、考试）等
- 日常事件：普通社交、购物、休闲等非重要场景
- 非事件相关：与当日事件无关，基于个人兴趣的记录（如诗词、知识点）

#### 2. 各类生成概率规则（必须严格遵循）
- 日历（calendar）：
  - 极重要事件：80%-90%（按重要度微调，出行预定/核心会议最高）
  - 较重要事件: 60%-80%
  - 日常事件/非事件相关：0%（强制不生成）
- 事件相关笔记（note_related）：
  - 极重要事件：60%-80%（记录待办/要点/注意事项）
  - 较重要事件：20%-40%
  - 日常事件：0%-5%（概率极低，几乎不生成）
- 非事件相关笔记（note_unrelated）：
  - 定义：与当日事件无关，基于用户兴趣的记录（如读到的诗词、咖啡知识点）
  - 概率：10%-15%（每天最多1个）其他事件都是0%。
  - 无兴趣关联：0%

#### 3. 个人画像适配
- 非事件相关笔记需匹配用户兴趣（如诗词、咖啡、多肉）
- 整体概率需贴合"不常用"习惯，避免高概率生成

#### 4. 其他约束
大部分事件不生成笔记或日历，甚至可以所有事件都不生成。只关注重要事件。

### 二、输出字段要求（仅保留以下6个字段，无额外内容）
每个事件必须包含：
- event_id：沿用原事件ID；非事件相关填"theme_序号"（如theme_001）
- event_name：事件名称；非事件相关填兴趣主题（如"古典诗词记录"）
- event_type：分类格式「类型-子类型」（如"重要事件-出行预定"、"非事件相关-兴趣爱好"）
- calendar_prob：日历生成概率（百分比字符串，如"80%"）
- note_related_prob：事件相关笔记生成概率（百分比字符串）
- note_unrelated_prob：非事件相关笔记生成概率（百分比字符串）

### 三、输出格式要求
仅输出JSON数组，无任何注释、额外文本或代码块。示例：
[
  {{
    "event_id": "evt001",
    "event_name": "G1234次列车北京→上海",
    "event_type": "重要事件-出行预定",
    "calendar_prob": "85%",
    "note_related_prob": "65%",
    "note_unrelated_prob": "0%"
  }},
  {{
    "event_id": "theme_001",
    "event_name": "古典诗词记录",
    "event_type": "非事件相关-兴趣爱好",
    "calendar_prob": "0%",
    "note_related_prob": "0%",
    "note_unrelated_prob": "10%"
  }}
]

请基于<当日事件>：{daily_events}、<个人画像>：{persona}，严格按上述要求输出概率建模结果。
'''

    def phone_gen_noteandcalendar(self,date, contact, file_path, c):
        res1 = extool.filter_by_date(date)
        res = []
        for i in range(len(res1)):
            if "-" in res1[i]['event_id']:
                continue
            res.append(res1[i])
            print(res1[i]['event_id'])
        prompt = self._build_prob_modeling_prompt(res,extool.persona)
        a = llm_call(prompt)
        print(a)
        a = self.parse_llm_prob_json(a)
        def sample(p1):
            prob = int(p1.strip('%'))
            return random.random() < max(0, min(100, prob)) / 100
        instruction = ""
        f = True
        for item in a:
            event_id= item['event_id']
            event_name= item['event_name']
            event_type= item['event_type']

            p1 = item['calendar_prob']
            p2 = item['note_related_prob']
            p3 = item['note_unrelated_prob']

            if sample(p1):
                instruction+=f'''\n--------------------------------------------------\n
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
请基于用户提供的{{生成项清单}}、{{当日事件}}和{{个人画像}}，生成具体的手机日历与笔记数据，数据总条目不超过4个，严格按照**{{生成项清单}}**提供的指令生成，若其为空则不生成，输出空数组。
核心约束：1. 仅生成清单中的项目，不额外新增,若清单中数目超过4则挑选最重要的4个生成；2. 若清单为空则直接输出空数组[]；3. 内容高保真、结构化；4. 无任何双引号。

### 一、个人画像适配（确保内容贴合用户习惯）
用户信息：
- 非事件相关笔记（note_unrelated）：基于画像生成用户与事件无关的笔记内容，如兴趣、新闻、知识等，或是某事的总结，内容真实自然
- 事件相关笔记（note_related）：聚焦核心信息（待办/要点/注意事项），不冗余
- 日历（calendar）：仅保留关键凭证和时间信息，来源明确

### 二、字段规则（严格遵循，缺一不可）
#### （一）日历日程（item_type=calendar）
- event_id：复用生成项中的event_id
- type：固定"calendar"
- title：简洁（场景+核心信息），例："G1234次列车（北京-上海）"
- description：包含"时间+核心要素+来源"，例："G1234次列车（北京南站→上海虹桥站），2023-10-05 08:00发车，预定码E12345，凭身份证检票，来源：12306"
- start_time：事件时间（格式YYYY-MM-DD HH:MM:SS）
- end_time：出行类=start_time；会议/预约类=合理时长后（如1.5小时）

#### （二）事件相关笔记（item_type=note_related）
- event_id：复用生成项中的event_id
- type：固定"note"
- title：事件名称+记录类型，例："Q4项目会议待办清单"
- content：结构化分点，例："一、会议前准备：1. 预算报表；2. PPT优化；二、核心议题：1. 资源调配；2. 节点确认"
- datetime：事件发生前30分钟内或发生后1小时内（格式YYYY-MM-DD HH:MM:SS）
- related_event_ids：原事件ID（如"evt002"）

#### （三）非事件相关笔记（item_type=note_unrelated）
- event_id：none
- type：固定"note"
- title：兴趣主题+记录类型，例："喜爱诗词记录"、"手冲咖啡知识点"
- content：结构化分点，例："一、诗句：人生若只如初见；二、作者：纳兰性德；三、赏析：情感细腻，适合文案灵感"
- datetime：当日合理时间（8:00-21:00，格式YYYY-MM-DD HH:MM:SS）
- related_event_ids：固定"无"

### 三、生成项清单（**仅生成以下项目，不新增**）
{instruct}

### 四、输出格式要求
仅输出JSON数组，严格遵循下面的格式，不添加任何额外文本/注释/代码块。示例：
[
{{"type":"calendar","event_id":"evt001","title":"G1234次列车（北京-上海）","description":"G1234次列车（北京南站→上海虹桥站），2023-10-05 08:00发车，预定码E12345，凭身份证检票，来源：12306","start_time":"2023-10-05 08:00:00","end_time":"2023-10-05 08:00:00"}},
{{"type":"note","event_id":"evt002_note","title":"Q4项目会议待办清单","content":"一、会议前准备：1. 整理Q4预算明细；2. 优化项目进度PPT；3. 预约会议室设备；二、核心议题：1. 预算审批；2. 资源调配；3. 里程碑节点确认","datetime":"2023-10-08 13:45:00","related_event_ids":"evt002"}}
]

### 五、今日事件背景参考
{event}

### 六、个人画像
{persona}
'''
            prompt = template.format(instruct=instruction,event=res,persona=extool.persona)
            res = llm_call(prompt)
            print(res)
            res = remove_json_wrapper(res)
            data = json.loads(res)
            c += data
            print(c)
            return c

class GalleryOperationGenerator:
    def __init__(self, random_seed: int = 42):
        """初始化生成器（设置随机种子确保可复现）"""
        random.seed(random_seed)

    def parse_llm_prob_json(self, llm_json_str: str) -> List[Dict]:
        """
        核心优化：直接提取首尾[]之间的内容，忽略所有包裹标记（```json、换行、空格等）
        不管 LLM 输出格式如何，只要核心是[]包裹的JSON数组，就能解析
        """
        try:
            # 第一步：找到第一个[和最后一个]的位置，提取中间内容
            start_idx = llm_json_str.find('[')
            end_idx = llm_json_str.rfind(']')
            if start_idx == -1 or end_idx == -1 or start_idx >= end_idx:
                print("错误：未找到有效的JSON数组（缺少[]包裹）")
                return []

            # 提取[]之间的核心JSON内容，清理首尾空白
            core_json_str = llm_json_str[start_idx:end_idx + 1].strip()

            # 第二步：解析JSON数组
            events = json.loads(core_json_str)

            return events
        except json.JSONDecodeError as e:
            print(f"JSON解析失败：位置{e.pos}，原因{e.msg}")
            return []
        except Exception as e:
            print(f"解析异常：{str(e)}")
            return []


    def phone_gen_gallery(self, date, contact, file_path, c):
        res1 = extool.filter_by_date(date)
        res = []
        for i in range(len(res1)):
            if "-" in res1[i]['event_id']:
                continue
            res.append(res1[i])
            print(res1[i]['event_id'])

        template = '''
        请基于用户提供的{{当日事件}}和{{个人画像}}，逐事件分析拍照行为的生成概率、场景细分及图片数量，仅输出概率建模结果，不涉及任何具体内容生成。核心规则：拍照场景与概率严格匹配事件类型，单个事件生成1-3张图片，避免过度生成。

### 一、概率建模核心规则
#### 1. 事件类型与拍照场景映射（基础概率固定，可按画像微调±5%）
| 事件类型 | 拍照场景（含基础概率） |
|----------|------------------------|
| 旅行事件 | 风景打卡30%、人物合影20%、美食记录20%、导视牌/门票15%、细节特写15% |
| 会议事件 | PPT截图40%、参会人员20%、会议纪要手写板20%、会场环境20% |
| 日常事件 | 美食25%、宠物20%、物品收纳15%、街头风景15%、文档扫描25% |

#### 2. 图片数量概率分配（单个事件必选其一）
- 1张图片：60%（默认优先，避免过度生成）
- 2张图片：30%（事件场景丰富时）
- 3张图片：10%（仅旅行/重要会议等复杂事件）

#### 3. 个人画像微调规则
- 兴趣适配：用户兴趣（如“美食爱好者”）对应场景概率+5%（如日常事件“美食”场景从25%→30%）
- 行为习惯：“不爱拍照”人格所有场景概率-10%；“摄影爱好者”所有场景概率+10%（但不超过基础概率+5%上限）
- 常居地关联：无明确地点的事件，拍照场景默认关联用户常居地POI（概率建模时无需体现具体地点，仅标记“需关联常居地”）

#### 4. 生成约束
- 非外出类事件（如“居家办公”“独自学习”）：仅保留“文档扫描”“物品收纳”场景，其他场景概率强制0%
- 无视觉价值事件（如“电话沟通”“线上会议”）：所有场景概率0%，图片数量0张
- 单个事件最多生成3张图片，不可超额

### 二、输出字段要求（仅保留以下6个字段，无额外内容）
每个事件必须包含：
- event_id：严格沿用原事件唯一标识，不添加额外文本
- event_name：完整保留原事件名称
- event_type：分类为“旅行事件”“会议事件”“日常事件”“无视觉价值事件”
- photo_scene_prob：字典格式，key=场景名称，value=百分比字符串（如{{"风景打卡":"35%","人物合影":"20%"}}）
- photo_count_prob：字典格式，key=图片数量（1/2/3），value=百分比字符串（如{{"1":"60%","2":"30%","3":"10%"}}）
- reasoning：简洁说明（含2点：1. 场景概率分配依据；2. 数量概率分配依据）

### 三、输出格式要求
仅输出JSON数组，无任何注释、额外文本或代码块标记。示例：
[
  {{
    "event_id": "evt001",
    "event_name": "杭州西湖一日游",
    "event_type": "旅行事件",
    "photo_scene_prob": {{
      "风景打卡": "35%",
      "人物合影": "20%",
      "美食记录": "20%",
      "导视牌/门票": "15%",
      "细节特写": "10%"
    }},
    "photo_count_prob": {{
      "1": "40%",
      "2": "40%",
      "3": "20%"
    }},
    "reasoning": "1. 场景概率：用户兴趣为旅行摄影，风景打卡+5%；2. 数量概率：旅行事件场景丰富，3张图片概率提升至20%"
  }},
  {{
    "event_id": "evt002",
    "event_name": "线上项目沟通会",
    "event_type": "无视觉价值事件",
    "photo_scene_prob": {{}},
    "photo_count_prob": {{"1":"0%","2":"0%","3":"0%"}},
    "reasoning": "1. 场景概率：线上会议无视觉价值，所有场景概率0%；2. 数量概率：无拍照行为，图片数量0张"
  }}
]

请基于<当日事件>：{daily_events}、<个人画像>：{persona}，严格按上述要求逐事件输出概率建模结果。
        '''
        prompt = template.format(daily_events = res, persona = extool.persona)
        print(prompt)
        a = llm_call(prompt)
        print(a)
        a = self.parse_llm_prob_json(a)

        def sample(p1):
            prob = int(p1.strip('%'))
            return random.random() < max(0, min(100, prob)) / 100

        instruction = ""

        for item in a:
            event_id = item['event_id']
            event_name = item['event_name']
            instruction += f'''\n--------------------------------------------------\n
                                                'event_id':'{event_id}',
                                                'event_name':'{event_name}',
                                            '''
            p1 = item['photo_scene_prob']
            for k in p1:
                if sample(p1[k]):
                    instruction+=f''' 'photo_scene':'{k}',
                                '''


        print(instruction)
        template = '''
    请基于用户提供的{{事件生成指令}}、{{当日事件}}、{{个人画像}}，生成结构化的手机图片/拍照数据，严格遵循字段规则、生成原则和输出格式，确保数据高保真、字段完整、逻辑自洽。

### 一、核心生成原则
1. 严格绑定事件生成指令：仅生成指定事件的拍照场景和图片数量，不新增场景或超额生成。
2. 地点真实性：无明确地点的事件，基于个人画像“常居地/常去地”生成真实层级化地点信息（省份→门牌号→POI）
3. 字段强约束：
   - caption：需包含“主体+动作+背景”，描述具体且生动
   - title：严格遵循“IMG_年月日_时分秒”格式（与datetime一致）
   - imageTag：5-15个关键词，精准贴合内容（场景+主体+动作+属性），不泛化
   - ocrText：仅导视牌/门票/海报/文档场景填写真实文字（含名称+时间/价格），其他场景填“无”
   - shoot_mode：人像模式必须关联faceRecognition（非“无”），夜景/微距需贴合场景（如夜景→暗光环境）
   - image_size：仅支持“4032×3024”“3024×4032”“2048×1536”“1536×2048”四种格式

### 二、字段规则（含嵌套字段，缺一不可）
需包含且仅包含以下字段：
- event_id：复用概率建模结果中的event_id
- type：固定“photo”
- caption：详细描述（主体+动作+背景），例：“李华在西湖断桥边打卡，身后有湖面与游船”
- title：“IMG_年月日_时分秒”格式（如“IMG_20231001_143025”），与datetime完全一致
- datetime：与事件时间一致或相近（±1小时内），格式“YYYY-MM-DD HH:MM:SS”
- location：嵌套对象（所有字段必填，无门牌号填“XX号”）：
  - province：真实省份名称（如“浙江省”）
  - city：真实城市名称（如“杭州市”）
  - district：真实区县名称（如“西湖区”）
  - streetName：真实街道名称（如“北山街”）
  - streetNumber：门牌号（如“10号”，无则填“XX号”）
  - poi：真实POI名称（如“西湖断桥景区”“三里屯太古里”）
- faceRecognition：联系人列表姓名数组/“无”/“XX若干”（例：["李华","张明"]、“无”、“游客若干”）
- imageTag：5-15个关键词（场景+主体+动作+属性），例：“拿铁咖啡、玻璃吸管、木质桌面、下午茶”
- ocrText：图片中真实文字（门票/海报/导视牌含“名称+时间+价格”），无则填“无”
- shoot_mode：正常拍照/夜景/人像/微距（人像模式必须对应faceRecognition非“无”）
- image_size：四种格式之一（“4032×3024”“3024×4032”“2048×1536”“1536×2048”）

### 三、待生成清单（事件生成指令，仅生成以下内容）
{instruct}

### 四、输出格式要求
仅输出JSON数组，无任何额外文本、注释或代码块标记。每个元素对应1张图片，按datetime升序排列。示例：
[
  {{
    "event_id": "evt001",
    "type": "photo",
    "caption": "李华在杭州西湖断桥边拍摄风景，湖面游船与雷峰塔清晰可见",
    "title": "IMG_20231001_143025",
    "datetime": "2023-10-01 14:30:25",
    "location": {{
      "province": "浙江省",
      "city": "杭州市",
      "district": "西湖区",
      "streetName": "北山街",
      "streetNumber": "XX号",
      "poi": "西湖断桥景区"
    }},
    "faceRecognition": ["李华"],
    "imageTag": ["西湖", "断桥", "游船", "雷峰塔", "秋日", "湖面"],
    "ocrText": "西湖断桥 - 国家5A级旅游景区",
    "shoot_mode": "正常拍照",
    "image_size": "4032×3024"
  }},
  {{
    "event_id": "evt001",
    "type": "photo",
    "caption": "李华与张明在西湖边品尝东坡肉，餐具为青花瓷碗，背景是木质餐桌",
    "title": "IMG_20231001_181540",
    "datetime": "2023-10-01 18:15:40",
    "location": {{
      "province": "浙江省",
      "city": "杭州市",
      "district": "西湖区",
      "streetName": "孤山路",
      "streetNumber": "15号",
      "poi": "楼外楼（孤山路店）"
    }},
    "faceRecognition": ["李华", "张明"],
    "imageTag": ["东坡肉", "青花瓷碗", "木质餐桌", "杭州美食", "聚餐"],
    "ocrText": "楼外楼 - 东坡肉 68元/份 2023-10-01",
    "shoot_mode": "人像",
    "image_size": "3024×4032"
  }}
]

请基于<事件生成指令>：{instruct}、<当日事件>：{event}、<个人画像>：{persona}严格按上述要求生成图片数据。
    '''
        prompt = template.format(instruct=instruction, event=res, persona=extool.persona)
        res = llm_call(prompt)
        print(res)
        res = remove_json_wrapper(res)
        data = json.loads(res)
        c += data
        print(c)
        return c


class PushOperationGenerator:
    def __init__(self, random_seed: int = 42):
        """初始化生成器（设置随机种子确保可复现）"""
        random.seed(random_seed)

    def parse_llm_prob_json(self, llm_json_str: str) -> List[Dict]:
        """
        核心优化：直接提取首尾[]之间的内容，忽略所有包裹标记（```json、换行、空格等）
        不管 LLM 输出格式如何，只要核心是[]包裹的JSON数组，就能解析
        """
        try:
            # 第一步：找到第一个[和最后一个]的位置，提取中间内容
            start_idx = llm_json_str.find('[')
            end_idx = llm_json_str.rfind(']')
            if start_idx == -1 or end_idx == -1 or start_idx >= end_idx:
                print("错误：未找到有效的JSON数组（缺少[]包裹）")
                return []

            # 提取[]之间的核心JSON内容，清理首尾空白
            core_json_str = llm_json_str[start_idx:end_idx + 1].strip()

            # 第二步：解析JSON数组
            events = json.loads(core_json_str)

            return events
        except json.JSONDecodeError as e:
            print(f"JSON解析失败：位置{e.pos}，原因{e.msg}")
            return []
        except Exception as e:
            print(f"解析异常：{str(e)}")
            return []

    def phone_gen_push(self, date, contact, file_path,  c):
        res1 = extool.filter_by_date(date)
        res = []
        for i in range(len(res1)):
            if "-" in res1[i]['event_id']:
                continue
            res.append(res1[i])
            print(res1[i]['event_id'])

        template = '''
            请基于用户提供的{{当日事件}}、{{个人画像}}和{{短信数据}}，逐事件挖掘动作细节，分析推送场景匹配度及生成概率，仅输出概率建模结果，不涉及具体内容生成。核心规则：严格去重（与短信重复不生成）、场景精准匹配动作、控制推送频率。

### 一、概率建模核心规则
#### 1. 事件动作挖掘与推送场景映射
- **第一步：动作提取**：从事件中提取具体行为动作（支付/预定/下单/改签/退款/收藏等），无明确动作的事件标记“无核心动作”
- **第二步：场景匹配**（动作→场景→来源APP，严格对应）：
  | 核心动作       | 推送场景                          | 关联来源APP示例                  |
  |----------------|-----------------------------------|-----------------------------------|
  | 支付           | 支付成功提醒、账单同步            | 支付宝、微信支付                  |
  | 预定           | 预定成功、时间临近、变更提醒      | 美团、携程、12306                 |
  | 下单           | 订单确认、发货/备餐、物流/送达    | 淘宝、京东、美团外卖              |
  | 改签/退款      | 改签成功、退款到账                | 12306、携程                       |
  | 收藏/关注      | 内容更新、对象上新                | 抖音、小红书、淘宝                |
  | 无核心动作     | 个性化推荐、系统常规通知          | 基于画像的APP、系统模块           |

#### 2. 推送场景概率分配（总和100%，按优先级排序）
- 事件动作关联场景：80%（优先匹配动作对应的核心场景）
- 关键节点提醒场景：15%（仅事件含明确时间时生成，如会议前30分钟）
- 个性化推荐场景：20%（基于个人画像行为偏好，如股民→雪球）
- 系统常规通知场景：5%（仅电量/存储/健康等系统触发）

#### 3. 生成约束规则
- **去重**：与短信数据内容重复的推送场景概率强制0%
- **频率控制**：同一APP同一事件24小时内最多生成2个推送场景（优先保留动作关联和关键节点）
- **时间适配**：按APP类型约束推送时间窗口（工作类9:00-18:00/娱乐类12:00-14:00&19:00-22:00等），不符合窗口的场景概率-30%（最低0%）
- **社交排除**：微信/QQ等社交平台通信类推送概率强制0%

### 二、输出字段要求（仅保留以下7个字段，无额外内容）
每个事件必须包含：
- event_id：严格沿用原事件唯一标识，系统通知填“system”
- event_name：完整保留原事件名称
- core_action：提取的核心动作（多个用“/”分隔，无则填“无核心动作”）
- push_scene_prob：字典格式，key=场景名称，value=百分比字符串（如{{"支付成功提醒":"60%","个性化推荐":"20%"}}）
- source_app_candidate：数组格式，推荐匹配的来源APP（如["支付宝","美团"]）
- is_duplicate_with_sms：是否与短信重复（是/否）
- reasoning：简洁说明（含3点：1. 动作提取依据；2. 场景概率分配原因；3. 约束规则应用情况）

### 三、输出格式要求
仅输出JSON数组，无任何注释、额外文本或代码块标记。 **格式强约束**："reasoning"的内容中不要生成任何引号，名称强调使用【】来进行。示例：
[
  {{
    "event_id": "evt001",
    "event_name": "美团外卖下单支付（订单#8765）",
    "core_action": "下单/支付",
    "push_scene_prob": {{
      "支付成功提醒": "60%",
      "订单备餐提醒": "15%",
      "个性化推荐": "20%",
      "系统常规通知": "5%"
    }},
    "source_app_candidate": ["支付宝", "美团外卖"],
    "is_duplicate_with_sms": "否",
    "reasoning": "1. 动作提取：事件含“下单”“支付”行为；2. 概率分配：动作关联场景60%、关键节点15%、个性化20%、系统5%；3. 约束应用：无短信重复，美团外卖在生活类时间窗口内"
  }},
  {{
    "event_id": "evt002",
    "event_name": "微信好友聊天",
    "core_action": "无核心动作",
    "push_scene_prob": {{}},
    "source_app_candidate": [],
    "is_duplicate_with_sms": "否",
    "reasoning": "1. 动作提取：仅社交聊天，无推送关联动作；2. 概率分配：社交平台推送强制0%；3. 约束应用：符合社交排除规则"
  }}
]

请基于<当日事件>：{daily_events}、<个人画像>：{persona}、<短信数据>：{sms_data}，严格按上述要求逐事件输出概率建模结果。
            '''
        prompt = template.format(daily_events=res, persona=extool.persona,sms_data = "")
        print(prompt)
        a = llm_call(prompt)
        print(a)
        a = self.parse_llm_prob_json(a)

        def sample(p1):
            prob = int(p1.strip('%'))
            return random.random() < max(0, min(100, prob)) / 100

        instruction = ""

        for item in a:
            event_id = item['event_id']
            event_name = item['event_name']
            instruction += f'''\n--------------------------------------------------\n
                                                    'event_id':'{event_id}',
                                                    'event_name':'{event_name}',
                                                '''
            p1 = item['push_scene_prob']
            print(p1)
            for k in p1:
                if sample(p1[k]):
                    instruction += f''' 'action_scene':'{k}',
                                    '''

        template = '''
        请基于用户提供的{{概率建模结果}}、{{当日事件}}、{{个人画像}}和{{短信数据}}，生成结构化的手机推送数据，严格遵循字段规则、生成原则和输出格式，确保数据真实贴合APP话术、字段完整无缺失、JSON解析无错误。

### 一、核心生成原则
1. **严格绑定建模结果**：仅生成概率建模中筛选的推送场景，按概率从高到低选择（同一事件最多生成2个场景，总数无上限但需符合频率约束）
2. **去重与话术适配**：
   - 与短信数据重复的内容坚决不生成
   - 推送标题/内容需贴合来源APP真实话术风格（如支付宝带“【支付宝】”前缀，美团强调“预定码/订单号”）
3. **细节与画像匹配**：
   - 内容必须包含事件具体信息（金额/时间/订单号/预定码等），禁止泛化
   - 个性化推荐需匹配个人画像偏好（如宝妈→宝宝树育儿提醒，股民→雪球行情）
   - 系统通知需符合触发条件（电量≤20%/存储≤10%）
4. **格式强约束**：推送内容中不要生成任何引号，名称强调使用【】来进行。

### 二、字段规则（含约束说明，缺一不可）
需包含且仅包含以下字段：
- event_id：复用概率建模结果中的event_id，系统通知填“system”
- type：固定“push”
- title：含“来源APP+动作/场景+关键对象”，例：“支付宝：外卖支付成功提醒”“美团：餐厅预定成功通知”
- content：贴合APP话术，含动作结果+核心信息（格式参考示例），双引号需转义
- datetime：按场景时间约束生成：
  - 支付/下单/预定动作：完成后1-3分钟内
  - 关键节点提醒：事件前30分钟-1小时
  - 系统通知：电量/存储触发时（随机生成合理时间）
  - 其他场景：对应APP时间窗口内（工作类9:00-18:00等）
- source：具体来源APP/系统模块（从建模结果source_app_candidate中选择）
- push_status：已读/未读/已删除（未读占比≤40%，随机分配）
- jump_path：APP内跳转路径，例：“支付宝→我的账单→订单#8765”“美团→我的→预定订单”

### 三、待生成清单（基于概率建模筛选，仅生成以下内容）
{instruct}

### 四、输出格式要求
仅输出JSON数组，无任何额外文本、注释或代码块标记。示例：
[
  {{
    "type": "push",
    "event_id": "evt001",
    "title": "支付宝：外卖支付成功提醒",
    "content": "【支付宝】您已成功支付美团外卖订单#8765，金额58元，账单已同步至“我的账单”",
    "datetime": "2023-10-01 12:03:00",
    "source": "支付宝",
    "push_status": "未读",
    "jump_path": "支付宝→我的账单→订单#8765"
  }},
  {{
    "type": "push",
    "event_id": "evt001",
    "title": "美团外卖：订单备餐提醒",
    "content": "【美团外卖】您的订单#8765正在备餐中，预计12:30送达，骑手已接单（姓名：张师傅，电话：138****1234）",
    "datetime": "2023-10-01 12:10:00",
    "source": "美团外卖",
    "push_status": "未读",
    "jump_path": "美团外卖→我的订单→订单#8765"
  }},
  {{
    "type": "push",
    "event_id": "system",
    "title": "系统：电量低提醒",
    "content": "【系统通知】当前手机电量已低于20%，请及时充电，避免影响使用",
    "datetime": "2023-10-01 16:45:00",
    "source": "系统电池管理",
    "push_status": "已读",
    "jump_path": "设置→电池"
  }}
]

请基于<概率建模结果>：{instruct}、<当日事件>：{event}、<个人画像>：{persona}、<短信数据>：{sms_data}，严格按上述要求生成推送数据。
        '''
        prompt = template.format(instruct=instruction, event=res, persona=extool.persona,sms_data = '')
        res = llm_call(prompt)
        print(res)
        res = remove_json_wrapper(res)
        data = json.loads(res)
        c += data
        print(c)
        return c