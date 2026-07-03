"""
通信操作生成器模块
负责生成手机通话和短信数据
"""

import json
import random
from typing import List, Dict
from src.lifebench.utils.llm_call import llm_call, llm_call_j, llm_call_reason_j


class CommunicationOperationGenerator:
    """
    通信操作生成器
    根据事件信息生成通话和短信数据
    """
    
    def __init__(self, random_seed: int = 42):
        """
        初始化通信操作生成器
        
        Args:
            random_seed: 随机种子，确保可复现
        """
        random.seed(random_seed)
        self.supported_scenes = ["紧急事务", "日常分享", "日常社交", "商务交互", "无通信需求"]
    
    def parse_llm_prob_json(self, llm_json_str: str) -> List[Dict]:
        """
        解析 LLM 返回的 JSON 数据，提取首尾 [] 之间的内容
        
        Args:
            llm_json_str: LLM 返回的字符串
            
        Returns:
            解析后的事件列表
        """
        try:
            # 第一步：找到第一个 [ 和最后一个] 的位置，提取中间内容
            start_idx = llm_json_str.find('[')
            end_idx = llm_json_str.rfind(']')
            if start_idx == -1 or end_idx == -1 or start_idx >= end_idx:
                print("错误：未找到有效的 JSON 数组（缺少 [] 包裹）")
                return []

            # 提取 [] 之间的核心 JSON 内容，清理首尾空白
            core_json_str = llm_json_str[start_idx:end_idx + 1].strip()

            # 第二步：解析 JSON 数组
            events = json.loads(core_json_str)

            # 第三步：校验必填字段
            required_fields = [
                "event_id", "event_name", "event_basic", "communication_scene",
                "trigger_probability", "type_probability", "multi_sms_probability"
            ]
            valid_events = []
            for event in events:
                if isinstance(event, dict) and all(f in event for f in required_fields):
                    # 校验 event_basic 必填子字段
                    basic_required = ["time", "is_multi_topic", "duration"]
                    if all(sub_f in event["event_basic"] for sub_f in basic_required):
                        valid_events.append(event)
                    else:
                        print(
                            f"警告：事件{event.get('event_id', '未知 ID')}的 event_basic 缺少子字段（time/is_multi_topic/duration），跳过")
                else:
                    print(f"警告：事件{event.get('event_id', '未知 ID')}缺少必要字段或格式错误，跳过")
            return valid_events
        except json.JSONDecodeError as e:
            print(f"JSON 解析失败：位置{e.pos}，原因{e.msg}")
            print(f"提取的核心 JSON 前 200 字符：{core_json_str[:200]}...")
            return []
        except Exception as e:
            print(f"解析异常：{str(e)}")
            return []
    
    def _prob_sample(self, prob_str: str) -> bool:
        """
        概率触发抽样（如"30%"→True/False）
        
        Args:
            prob_str: 概率字符串，如"30%"
            
        Returns:
            是否触发
        """
        try:
            prob = int(prob_str.strip('%'))
            return random.random() < max(0, min(100, prob)) / 100
        except:
            print(f"警告：概率格式错误（{prob_str}），默认返回 False")
            return False
    
    def _sample_type(self, prob_dict: Dict[str, str]) -> str:
        """
        抽样通信类型（call/sms）
        
        Args:
            prob_dict: 概率字典
            
        Returns:
            通信类型（call 或 sms）
        """
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
        """
        抽样多短信数量（基于 multi_sms_probability）
        
        Args:
            multi_sms_info: 多短信概率信息
            
        Returns:
            短信条数
        """
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
            return 1  # 默认 1 条短信
        counts, probs = zip(*count_probs)
        total = sum(probs)
        return random.choices(counts, weights=[p / total for p in probs], k=1)[0]
    
    def process_single_event(self, event: Dict) -> List[str]:
        """
        处理单个事件，生成通信操作指令（含多短信逻辑）
        
        Args:
            event: 事件字典
            
        Returns:
            通信操作指令列表
        """
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
                        f"【事件相关通信】event_id：{event_id}，事件名称：{event_name}，"
                        f"场景：{scene}，通信类型：短信{topic_note}"
                    )
                    operations.append(instr)
            # 若为通话
            else:
                instr = (
                    f"【事件相关通信】event_id：{event_id}，事件名称：{event_name}，"
                    f"场景：{scene}，通信类型：通话，"
                )
                operations.append(instr)

        # 2. 处理事件无关通信
        unrelated_trigger = event["trigger_probability"]["unrelated"]
        if self._prob_sample(unrelated_trigger):
            comm_type = self._sample_type(event["type_probability"]["unrelated"])
            if comm_type == "sms":
                instr = (
                    f"【事件无关通信】event_id：{event_id}，事件名称：{event_name}，"
                    f"场景：事项提醒/亲友问候/生活咨询，通信类型：短信，时间：{event_time}当日 8-21 点，"
                )
                operations.append(instr)
            else:
                instr = (
                    f"【事件无关通信】event_id：{event_id}，事件名称：{event_name}，"
                    f"场景：亲友问候，通信类型：通话，时间：{event_time}当日 8-21 点，"
                )
                operations.append(instr)

        return operations
    
    def generate_llm_instructions(self, llm_json_str: str) -> str:
        """
        入口函数：生成最终 LLM 操作指令字符串
        
        Args:
            llm_json_str: LLM 返回的概率建模 JSON 字符串
            
        Returns:
            操作指令字符串
        """
        events = self.parse_llm_prob_json(llm_json_str)
        if not events:
            return "无有效事件数据，无需生成通信操作。"

        all_instructions = []
        for event in events:
            all_instructions.extend(self.process_single_event(event))

        if not all_instructions:
            return "所有事件未触发通信操作，无需生成手机操作数据。"

        # 格式化指令（清晰易读，LLM 可直接解析）
        final_instr = (
                "请按以下指令生成手机通信操作（通话/短信），严格遵循字段要求和内容逻辑：\n"
        )

        for idx, instr in enumerate(all_instructions):
            final_instr += f"{idx}. {instr}\n" + "-" * 60 + "\n"

        return final_instr

    def extract_key_scenes(self, daily_events: List[Dict], persona: Dict) -> List[Dict]:
        """
        调用 LLM 从今日事件中提取重点场景

        Args:
            daily_events: 今日事件列表
            persona: 个人画像

        Returns:
            重点场景列表，每项包含 {event_id, event_name, scene_desc, enhancement_type}
            enhancement_type: "high_priority" | "emotional" | "memorable"
        """
        prompt = f"""请从以下今日事件中识别出需要"重点场景增强"的事件。

重点场景定义（仅关注服务类场景）：
1. **预约/订票场景**：预约挂号、景点/游乐园/演唱会/电影票务预约、活动预约等
2. **服务短信场景**：银行通知、运营商通知、医疗服务通知、账单提醒等
3. **出行旅游场景**：航空旅行、火车旅行、酒店住宿、旅游度假等
4. **外卖/餐饮场景**：外卖订单、餐厅预订等
5. **快递/物流场景**：快递派送、物流运输、取件通知等
6. **票务入场场景**：游乐园、演唱会、电影院、体育赛事等票务及入场信息
7. **银行卡重大支出**：大额消费、转账汇款、扣款通知等

### 个人画像摘要
- 姓名：{persona.get('name', '')}
- 职业：{persona.get('job', '')}
- 性格：{persona.get('personality', {}).get('mbti', '')}
- 爱好：{', '.join(persona.get('hobbies', [])[:5])}

### 今日事件
{json.dumps(daily_events, ensure_ascii=False, indent=2)}

### 输出要求
请全面识别所有服务类场景，输出 JSON 数组（有多少个符合的场景就输出多少个）：
[
  {{
    "event_id": "对应的事件ID",
    "event_name": "事件名称",
    "scene_desc": "对该场景的简短描述（10-20字）",
    "enhancement_type": "booking | service | travel | delivery | ticket | expense",
    "enhancement_reason": "为什么这个场景需要增强（1-2句话）"
  }}
]

**重要**：输出时仅包含 event_id、event_name、scene_desc、enhancement_type、enhancement_reason 五个字段，不要返回其他事件原始字段（原始事件信息会通过匹配 event_id 自动补全）。
仅输出 JSON 数组，不要添加任何额外文本或注释。

enhancement_type 取值说明：
- booking: 预约/订票类
- service: 服务短信类（银行/运营商/医疗等）
- travel: 出行旅游类（机票/火车票/酒店）
- delivery: 外卖/快递/物流类
- ticket: 票务入场类（游乐园/演唱会/电影）
- expense: 银行卡支出类

仅输出 JSON 数组，不要添加任何额外文本或注释。
"""
        try:
            result = llm_call(prompt)
            result = self.remove_json_wrapper(result, "array")
            scenes = json.loads(result)
            # 用 event_id 匹配，补全原始事件的完整信息（地点、描述、日期等）
            event_map = {e.get("event_id", ""): e for e in daily_events}
            enriched = []
            for s in scenes:
                eid = s.get("event_id", "")
                full_event = event_map.get(eid, {})
                # 合并：保留 LLM 输出字段 + 事件原始字段
                enriched.append({**full_event, **s})
            scenes = enriched
            print(f"✓ 重点场景提取完成，共 {len(scenes)} 个场景")
            for s in scenes:
                print(f"  - [{s.get('enhancement_type')}] {s.get('event_name')}: {s.get('scene_desc')}")
            return scenes
        except Exception as e:
            print(f"重点场景提取失败: {e}")
            return []

    def generate_key_scene_sms(self, key_scenes: List[Dict], contacts: List[Dict], persona: Dict) -> List[Dict]:
        """
        为重点场景生成增强型通信数据（主要生成短信）

        Args:
            key_scenes: 重点场景列表
            contacts: 联系人列表
            persona: 个人画像

        Returns:
            生成的通信数据列表
        """
        if not key_scenes:
            return []

        contacts_json = json.dumps(contacts, ensure_ascii=False, indent=2)
        persona_json = json.dumps(persona, ensure_ascii=False, indent=2)
        scenes_json = json.dumps(key_scenes, ensure_ascii=False, indent=2)

        prompt = f"""你是一个重点场景通信数据生成专家。请为以下重点场景生成额外的通信数据（主要是短信），用于丰富场景细节。

### 个人画像
{persona_json}

### 重点场景
{scenes_json}

### 可用联系人
{contacts_json}

### 各场景语言风格参考（严格遵循以下格式）

**航空旅行**：
- "{{航空公司}}: 您好，{{name}}，您的机票已出票。航班号为{{flight_number}}的航班，于{{MM/DD/YYYY hh:mm A}}从{{出发机场}}飞往{{到达机场}}。票号：{{ticket_number}}。值机截止时间为航班起飞前60分钟。"
- "{{航空公司}}: 尊敬的乘客，您的{{flight_number}}航班订单{{order_number}}已开放值机。请通过{{平台应用名称}}应用选座并获取电子登机牌。"
- "{{航空公司}}: 尊敬的{{name}}，{{flight_number}}航班因{{延误原因}}延误。预计新起飞时间：{{new_departure_time}}。"
- "{{航空公司}}: 您好，{{name}}，{{flight_number}}航班已开始登机。请前往登机口{{gate_number}}。"

**火车旅行**：
- "铁路服务：您好，{{name}}，您的火车票已预订成功，乘车日期为{{MM/DD/YYYY}}，车次为{{train_number}}，从{{出发站}}至{{到达站}}。座位类型：{{seat_type}}，座位号：{{seat_number}}。"
- "铁路服务：您好，{{train_number}}次列车将于{{MM/DD/YYYY hh:mm A}}发车，即将开始登车。请于开车前30分钟到达站台。"

**酒店住宿**：
- "{{平台}}: 您好，{{name}}，您的酒店预订已确认。入住日期：{{check_in_date}}，退房日期：{{check_out_date}}。酒店名称：{{hotel_name}}，房型：{{room_type}}。地址：{{address}}。"
- "{{平台}}: 尊敬的{{name}}，您在{{hotel_name}}的预订已确认，入住日期为{{check_in_date}}。入住时间：{{MM/DD/YYYY hh:mm A}}。地址：{{address}}。"
- "{{平台}}: 尊敬的{{name}}，您在{{hotel_name}}的住宿将于{{check_out_date}}结束。请于{{checkout_deadline_time}}前办理退房。"

**电子商务/快递/外卖**：
- "{{配送服务}}: 您好，{{name}}，您的订单{{order_number}}已于{{MM/DD/YYYY hh:mm A}}提交。收货地址：{{delivery_address}}。预计送达时间：{{eta_delivery_date}}。"
- "{{配送服务}}: 尊敬的{{name}}，您的订单{{order_number}}包裹已从{{origin_city}}发出，正在运往{{destination_city}}途中。预计送达时间：{{eta_delivery_date}}。"
- "{{配送服务}}: 您好，{{name}}，您的包裹已派送中，预计今日送达。请保持手机畅通。"

**预约/票务入场（游乐园/演唱会/电影）**：
- "{{平台}}: 您好，{{name}}，您的{{活动名称}}门票已购买成功。演出时间：{{MM/DD/YYYY hh:mm A}}，座位号：{{seat_number}}。请提前30分钟入场。"
- "{{平台}}: 尊敬的{{name}}，您的订单{{order_number}}已确认。{{活动类型}}：{{event_name}}，时间：{{datetime}}，地点：{{venue}}。"

**银行卡/支付通知**：
- "{{银行名称}}: 尊敬的{{name}}，您的银行卡{{card_number_tail}}于{{MM/DD/YYYY hh:mm A}}支出{{amount}}元，余额{{balance}}元。如有疑问请致电客服。"
- "{{支付平台}}: 您好，{{name}}，您的{{platform}}账户{{MM/DD/YYYY hh:mm A}}消费{{amount}}元。商户：{{merchant_name}}。"

### 生成要求
1. **虚构合理信息**：允许自行编造订单号、票号、卡号尾数、金额、数量等字段，确保符合场景逻辑且格式合理（如订单号10位数字、票号6位字母+数字组合、航班号如CA1234/ZH5678等）
2. 每个场景生成 至少1条短信，严格遵循上述对应场景的语言风格，最多三条，如果1条短信符合现实逻辑且信息充足可以不额外生成。
3. 服务类短信（航空/火车/酒店/快递/银行）一律使用"接收"类型的模板风格短信
4. 时间逻辑要合理（在事件发生前后适当时间收到/发送）
5. 航空/火车/酒店场景优先从联系人列表选对应联系人，无匹配则使用机构名称
6. 外卖/快递场景使用机构平台名称作为 contactName
7. **内容要丰富**：短信正文应包含尽可能多的场景细节（如具体地名、金额、状态描述等），信息充实不空洞
8. 信息之间的逻辑要合理（如订单号、票号、卡号尾数等字段要与场景逻辑一致，相关的订单号/车次要一致）

### 输出格式
仅输出 JSON 数组，每条数据包含以下字段：
- type: "sms"
- event_id: 对应场景的 event_id
- message_content: 短信内容，遵循上述对应场景的语言风格，**信息丰富，包含虚构的订单号/票号等细节**
- contactName: 机构名称或联系人姓名
- phoneNumber: 机构号段（1069/400/+86手机号）或联系人电话
- datetime: 时间（YYYY-MM-DD HH:MM:SS，在事件发生前后合理范围内）
- message_type: "接收"（服务类）或 "发送"/"接收"（情感类）

### 输出示例
[
  {{"type":"sms","event_id":"5901","message_content":"【东方航空】尊敬的韩海生旅客，您购买的MU5735航班已出票，航班号MU5735，将于2025-06-15 08:30从上海浦东国际机场飞往北京首都国际机场。票号：8812153674。请于航班起飞前60分钟完成值机。","contactName":"东方航空","phoneNumber":"+8613900069555","datetime":"2025-06-14 14:23:18","message_type":"接收"}},
  {{"type":"sms","event_id":"5902","message_content":"【顺丰速运】您好，韩海生，您的订单SF1023876543包裹已从杭州发出，正在运往上海途中。预计送达时间：2025-06-16。请保持手机畅通，收件时出示验证码。","contactName":"顺丰速运","phoneNumber":"+861061095533","datetime":"2025-06-15 09:15:42","message_type":"接收"}},
  {{"type":"sms","event_id":"5903","message_content":"【美团外卖】您好，韩海生，您的订单MT2025061512345已提交，商家：老盛兴生煎（徐汇店），预计送达时间10:30。地址：上海市徐汇区漕河泾开发区。","contactName":"美团外卖","phoneNumber":"+861065195533","datetime":"2025-06-15 09:05:00","message_type":"接收"}}
]

请仅输出 JSON 数组，不要添加任何额外文本、注释或代码块标记。
"""
        try:
            result = llm_call_reason_j(prompt)
            result = self.remove_json_wrapper(result, "array")
            data = json.loads(result)
            print(f"✓ 重点场景SMS生成完成，生成 {len(data)} 条数据")
            for d in data:
                print(f"  - [{d.get('event_id')}] {d.get('contactName')}: {d.get('message_content', '')[:30]}...")
            return data
        except Exception as e:
            print(f"重点场景SMS生成失败: {e}")
            return []

    def analyze_and_merge_duplicates(self, all_data: List[Dict], daily_events: List[Dict]) -> List[Dict]:
        """
        按 event_id 分组，逐组调用 LLM 分析重复和不一致，只对 modify/remove 输出决策

        Args:
            all_data: 所有通信数据列表（原生 + 重点场景增强）
            daily_events: 当日事件列表

        Returns:
            去重/修正后的通信数据列表
        """
        if len(all_data) <= 1:
            return all_data

        from collections import defaultdict

        grouped = defaultdict(list)
        for it in all_data:
            grouped[it.get("event_id", "")].append(it)

        # 为每个 item 赋予唯一 data_id（event_id + 出现序号），解决同 event_id 多条数据无法定位的问题
        data_by_data_id = {}
        for event_id, items in grouped.items():
            for idx, it in enumerate(items):
                data_id = f"{event_id}_{idx}"
                it['_data_id'] = data_id
                data_by_data_id[data_id] = it

        # 构建 event_id -> event_info 映射
        event_map = {e.get("event_id", ""): e for e in daily_events}

        print(f"✓ 开始重复/不一致分析，共 {len(grouped)} 个事件分组...")

        delete_ids = set()
        fix_map = {}
        total_analyzed = 0

        for event_id, items in grouped.items():
            # 单条数据无需分析，直接保留
            if len(items) <= 1:
                continue

            total_analyzed += 1
            event_info = event_map.get(event_id, {})
            event_desc = event_info.get("description", event_info.get("desc", ""))
            items_json = json.dumps(items, ensure_ascii=False, indent=2)

            prompt = f"""你是一个通信数据去重与一致性分析专家。请分析以下同一 event_id 的所有通信数据。

### 事件信息
- event_id: {event_id}
- 事件名称: {event_info.get('name', '未知')}
- 事件描述: {str(event_desc)[:150]}

### 该事件下所有通信数据
{items_json}

### 分析要求
1. **虚构一致性**（最重要！）：若短信内容涉及事件描述之外的信息（如订单号、航班号、车次、酒店名、票号、送达时间等），提取每条数据中的虚构字段值；若同事件多条数据虚构了同一类信息但值不同，**必须统一为同一个值**，在 fixed_data 中给出修正后的完整数据
2. **内容重复**：保留信息最完整或最合理的一条，删除其他高度重复的
3. **逻辑矛盾**：联系人、时间、收发方向等字段存在矛盾的，修正或删除

### 输出格式
**只输出需要修改或删除的数据**，keep 的不需要输出：
[
  {{
    "data_id": "_data_id值，格式为event_id_序号（如5903_0）",
    "decision": "delete | fix",
    "reason": "决定原因（简洁）",
    "fixed_data": {{修正后的完整数据，仅 decision 为 fix 时需要}}
  }}
]

- delete: 删除该数据
- fix: 修正后保留（虚构不一致必须统一，字段矛盾可以修正，必须在 fixed_data 中给出完整数据）

请仅输出 JSON 数组，不要添加任何额外文本、注释或代码块标记。
"""
            try:
                from src.lifebench.utils.llm_call import llm_call_reason_j
                result = llm_call_j(prompt)
                result = self.remove_json_wrapper(result, "array")
                decisions = json.loads(result)

                for dec in decisions:
                    did = dec.get("data_id", "")
                    decision = dec.get("decision", "")
                    reason = dec.get("reason", "")
                    if decision == "delete":
                        delete_ids.add(did)
                        print(f"  [删除] {event_id} - {did}: {reason}")
                    elif decision == "fix":
                        fixed = dec.get("fixed_data")
                        if fixed:
                            fix_map[did] = fixed
                            print(f"  [修正] {event_id} - {did}: {reason}")
            except Exception as e:
                print(f"  ⚠️ 事件 {event_id} 分析失败（{e}），跳过")

        # 应用修正
        for did, fixed_data in fix_map.items():
            if did in data_by_data_id:
                data_by_data_id[did].update(fixed_data)

        # 应用删除
        result_list = [it for it in all_data if it.get("_data_id") not in delete_ids]
        # 移除 _data_id 字段
        for it in result_list:
            it.pop("_data_id", None)
        print(f"✓ 去重分析完成：分析了 {total_analyzed} 个分组，修改 {len(fix_map)} 条，删除 {len(delete_ids)} 条，输入 {len(all_data)} 条 -> 输出 {len(result_list)} 条")

        return result_list

    def validate_and_fix_communication_data(self, data: Dict, event_context: Dict, all_daily_events: List[Dict], user_name: str) -> tuple:
        """
        校验通信数据合理性并修正
        
        Args:
            data: 单条通信数据
            event_context: 对应的事件上下文信息
            all_daily_events: 当天所有事件列表（用于判断是否为合理的噪声事件）
            user_name: 用户姓名（用于检测是否出现本人姓名）
            
        Returns:
            (is_valid: bool, fixed_data: Dict or None, error_message: str)
            - is_valid: 是否通过校验
            - fixed_data: 如果 LLM 修正了数据，返回修正后的数据；否则为 None
            - error_message: 错误信息
        """
        try:
            # 第一步：调用 LLM 分析合理性
            # 根据待校验数据的 type 动态提供对应的格式示例
            data_type = data.get("type", "")
            if data_type == "sms":
                format_example = '''**短信类型 (type="sms") 修正示例：**
{
  "type": "sms",
  "event_id": "5903",
  "message_content": "王总，明天10点销售会议，记得带最新数据报表",
  "contactName": "王总",
  "phoneNumber": "+8613912346789",
  "datetime": "2025-12-01 09:00:10",
  "message_type": "发送"
}'''
            elif data_type == "call":
                format_example = '''**通话类型 (type="call") 修正示例：**
{
  "type": "call",
  "event_id": "5910",
  "phoneNumber": "+8613807123456",
  "contactName": "冯建国",
  "datetime": "2025-12-01 08:50:00",
  "datetime_end": "2025-12-01 08:55:30",
  "direction": 1,
  "call_result": "接通"
}'''
            else:
                format_example = """**短信类型 (type="sms") 修正示例：**
{
  "type": "sms",
  "event_id": "5903",
  "message_content": "王总，明天10点销售会议，记得带最新数据报表",
  "contactName": "王总",
  "phoneNumber": "+8613912346789",
  "datetime": "2025-12-01 09:00:10",
  "message_type": "发送"
}

**通话类型 (type="call") 修正示例：**
{
  "type": "call",
  "event_id": "5910",
  "phoneNumber": "+8613807123456",
  "contactName": "冯建国",
  "datetime": "2025-12-01 08:50:00",
  "datetime_end": "2025-12-01 08:55:30",
  "direction": 1,
  "call_result": "接通"
}"""
            
            analysis_prompt = f"""请分析以下手机通信数据的合理性，检查是否存在以下问题：

### 检查项
1. **收发方向错误**：message_type（发送/接收）或 direction（呼出/呼入）是否与事件场景、联系人关系匹配
2. **联系人名称错误**：contactName 是否符合事件背景和联系人关系
3. **内容错误**：message_content 是否符合事件主题、场景逻辑
4. **本人姓名错误**：contactName 是否出现了用户本人姓名（人不会和自己发消息/打电话）
5. **时间逻辑错误**：通话时长、时间顺序等是否合理
6. **格式错误**：数据是否符合输出格式示例

### 重要说明
- 该通信数据可能是与当日事件无明显关联的**噪声事件**（如随机收到的广告短信、无关的推销电话或与别人聊天谈论其他事情等）
- 如果是噪声事件，只要不与当日事件冲突、符合基本生活逻辑即可视为合理
- 只有当数据存在明显的逻辑错误、格式错误或本人姓名错误时才需要修正
- 注意允许一些合理时间延迟，如上午发生的事情在下午进行谈论。还存在一些事件描述为我向别人发送信息，但收到别人回复的信息也是合理的。事件描述并不全面，允许一些合理事件发生。
### 用户信息
- 用户姓名：{user_name}

### 当天所有事件（用于判断是否冲突）
{json.dumps(all_daily_events, ensure_ascii=False, indent=2)}

### 待分析的通信数据
{json.dumps(data, ensure_ascii=False, indent=2)}

### 输出要求
如果数据合理，仅输出：{{"is_valid": true}}

如果数据有问题，输出 JSON 对象，包含 issues 和 fixed_data 字段：
{{
  "is_valid": false,
  "issues": ["问题描述1", "问题描述2"],
  "fixed_data": {{修正后的完整数据}}
}}

#### fixed_data 格式示例：
{format_example}

注意：
- fixed_data 必须是完整的通信数据对象，包含所有必填字段
- 如果修正了数据，必须确保修正后的数据符合原始事件的背景和逻辑
- datetime 格式必须为 "YYYY-MM-DD HH:MM:SS"，年份必须为 2025
- 不要添加任何额外文本、注释或代码块标记
"""
            
            from src.lifebench.utils.llm_call import llm_call_j
            result = llm_call_j(analysis_prompt)
            result = self.remove_json_wrapper(result, "object")
            analysis_result = json.loads(result)
            
            # 如果 LLM 认为数据合理
            if analysis_result.get("is_valid", False):
                return True, None, ""
            
            # 如果 LLM 认为数据有问题并提供了修正
            if not analysis_result.get("is_valid", True) and "fixed_data" in analysis_result:
                fixed_data = analysis_result["fixed_data"]
                issues = analysis_result.get("issues", [])
                print(f"  LLM 检测到问题: {issues}")
                # 对修正后的数据进行格式校验
                format_valid, format_error = self._validate_format_only(fixed_data)
                if format_valid:
                    return True, fixed_data, ""
                else:
                    return False, None, f"LLM 修正后格式仍错误: {format_error}"
            
            # 如果 LLM 认为有问题但未提供修正
            return False, None, f"LLM 检测到合理性问题但未提供修正: {analysis_result.get('issues', [])}"
            
        except Exception as e:
            return False, None, f"LLM 合理性分析异常: {str(e)}"
    
    def _validate_format_only(self, data: Dict, user_name: str = "") -> tuple:
        """
        仅校验通信数据格式（不涉及合理性），并删除多余字段
        
        Args:
            data: 单条通信数据
            user_name: 用户姓名（用于检测 contactName 是否为自己）
            
        Returns:
            (is_valid: bool, error_message: str)
        """
        try:
            # 1. 校验必填字段是否存在，并删除多余字段
            if data.get("type") == "sms":
                required_fields = ["event_id", "type", "message_content", "contactName", "phoneNumber", "datetime", "message_type"]
                missing_fields = [f for f in required_fields if f not in data]
                if missing_fields:
                    return False, f"短信缺少必填字段: {missing_fields}"
                
                # 删除多余字段
                extra_fields = [k for k in data.keys() if k not in required_fields]
                for field in extra_fields:
                    del data[field]
                
            elif data.get("type") == "call":
                required_fields = ["event_id", "type", "phoneNumber", "contactName", "datetime", "datetime_end", "direction", "call_result"]
                missing_fields = [f for f in required_fields if f not in data]
                if missing_fields:
                    return False, f"通话缺少必填字段: {missing_fields}"
                
                # 删除多余字段
                extra_fields = [k for k in data.keys() if k not in required_fields]
                for field in extra_fields:
                    del data[field]
            else:
                return False, f"缺少 type 字段或取值错误: {data.get('type')}"
            
            # 2. 校验 contactName 不能是用户本人（硬校验）
            if user_name and data.get("contactName"):
                contact_name = data["contactName"].strip()
                user_name_clean = user_name.strip()
                # 检查是否完全匹配或部分匹配（防止空格差异）
                if contact_name == user_name_clean or contact_name in user_name_clean or user_name_clean in contact_name:
                    return False, f"contactName 不能是用户本人: '{contact_name}'（用户姓名: '{user_name_clean}'），人不会给自己打电话/发信息"
            
            # 3. 校验时间格式
            from datetime import datetime
            try:
                dt = datetime.strptime(data["datetime"], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return False, f"datetime 格式错误: {data['datetime']}，应为 'YYYY-MM-DD HH:MM:SS'"
            
            # 4. 校验年份是否为2025年
            if dt.year != 2025:
                return False, f"年份不是2025年: {data['datetime']}，实际年份为 {dt.year}"
            
            return True, ""
            
        except Exception as e:
            return False, f"格式校验异常: {str(e)}"
    
    def fix_communication_data_format(self, invalid_data: List[Dict], event_contexts: Dict[str, Dict], user_name: str = "", contacts: List[Dict] = None) -> List[Dict]:
        """
        调用 LLM 修正格式错误的通信数据
        
        Args:
            invalid_data: 格式错误的数据列表
            event_contexts: 事件上下文字典 {event_id: event_info}
            user_name: 用户姓名（用于检测 contactName 是否为自己）
            contacts: 联系人列表（用于选择合适的 contactName）
            
        Returns:
            修正后的数据列表
        """
        if not invalid_data:
            return []
        
        # 构建联系人信息字符串
        contacts_info = ""
        if contacts:
            contacts_info = f"""### 可用联系人列表（优先从此列表中选择 contactName）
{json.dumps(contacts, ensure_ascii=False, indent=2)}

**选择规则**：
- 优先从上述联系人列表中选择合适的 contactName 和 phoneNumber
- 根据事件背景选择关系匹配的联系人（如商务场景选同事/客户，社交场景选家人/朋友）
- 如果联系人列表中没有合适的，可以合理虚构，但必须符合场景逻辑
"""
        
        # 构建修正提示词
        fix_prompt = f"""请修正以下手机通信数据的格式错误，确保符合以下要求：

### 格式要求
1. **短信 (type="sms")** 必须包含字段：event_id, type, message_content, contactName, phoneNumber, datetime, message_type
   - message_type 只能取值为 "发送" 或 "接收"
   - datetime 格式："YYYY-MM-DD HH:MM:SS"

2. **通话 (type="call")** 必须包含字段：event_id, type, phoneNumber, contactName, datetime, datetime_end, direction, call_result
   - direction 只能取值为 0（呼入）或 1（呼出）
   - call_result 只能取值为 "接通"、"未接通"、"已挂断"、"拒接"
   - datetime 和 datetime_end 格式："YYYY-MM-DD HH:MM:SS"
   - datetime_end 必须晚于 datetime

3. **时间要求**：
   - 所有时间必须在 2025 年
   - 时间必须在当日 8:00-21:00 范围内
   - datetime 格式严格为 "YYYY-MM-DD HH:MM:SS"

4. **手机号格式**：个人号码以 +86 开头，机构号码可使用 1069/400/010 号段

5. **重要：contactName 硬校验规则**：
   - contactName **绝对不能**是用户本人姓名（{user_name if user_name else "未知"}）
   - 人不会给自己打电话或发信息，如果发现 contactName 与用户姓名相同，必须修正为合理的联系人


### 待修正数据
{json.dumps(invalid_data, ensure_ascii=False, indent=2)}

### 事件背景信息
{json.dumps(event_contexts, ensure_ascii=False, indent=2)}

###联系人信息
{contacts_info}

请仅输出修正后的 JSON 数组，不要添加任何额外文本、注释或代码块标记。
"""
        
        try:
            from src.lifebench.utils.llm_call import llm_call_j
            result = llm_call_j(fix_prompt)
            result = self.remove_json_wrapper(result, "array")
            fixed_data = json.loads(result)
            
            if isinstance(fixed_data, list):
                print(f"LLM 格式修正完成，返回 {len(fixed_data)} 条数据")
                return fixed_data
            else:
                print("警告：LLM 返回的不是列表格式")
                return []
        except Exception as e:
            print(f"LLM 格式修正失败: {str(e)}")
            return []
    
    def phone_gen_callandmsm(self, date, contact, file_path, extool=None):
        """
        生成通话和短信数据的主方法

        Args:
            date: 日期
            contact: 联系人列表
            file_path: 文件路径
            extool: Data_extract 实例，如果为 None 则从模块导入

        Returns:
            生成的通信数据列表
        """
        if extool is None:
            from src.lifebench.event.phone_data_gen import extool

        c = []
        event_classify = '''
               请基于用户提供的{{当日事件}}和{{个人画像}}，逐一对每个事件进行独立分析，输出精简后的核心属性及通信概率（无需方向字段），按真实场景常识判断多短信个数概率。分析需严格遵循以下要求，可结合事件细节灵活微调概率（±5% 内），确保概率逻辑自洽、贴合现实生活规律：

                ### 一、分析核心维度（每个事件必须完整输出以下 8 项，字段不可缺失）
                #### 1. 事件基础信息
                - 输出字段：event_id（严格沿用原事件唯一标识，不添加任何额外文本）、event_name（完整保留原事件名称）
                - 输出格式：`"event_id": "xxx", "event_name": "xxx"`
                
                #### 2. 事件基础属性提取
                - 提取关键要素：事件时间（精确到分钟，格式 YYYY-MM-DD HH:MM）、场景关键词（2-4 个核心词，如"家庭早餐/互动"）、行为目的（简洁描述核心诉求，如"家庭情感交流"）、是否面对面（是/否，严格按事件场景判断）、关联人员状态（说明关系 + 数量，可填多个用"/"分隔，如"家人 2 人/朋友 1 人"）、持续时长（按事件实际合理估算，格式 xx 分钟）、是否多主题（是/否，判断事件是否包含≥2 个独立诉求）
                - 输出格式：`"event_basic": {{"time": "xxx", "scene_keyword": "xxx", "purpose": "xxx", "is_face_to_face": "xxx", "related_person_status": "xxx", "duration": "xx 分钟", "is_multi_topic": "xxx"}}`
                
                #### 3. 通信场景分类（主场景唯一归属，严格匹配事件核心属性）
                事件相关通信可选分类：紧急事务（如突发情况处理、重要事项紧急协调）、日常分享（如日常闲聊、朋友圈分享、生活点滴交流）、社交互动（如亲友问候、聚会约见、情感交流）、商务交互（如工作对接、会议协调、客户沟通）、日常生活（如购物咨询、出行规划、便民服务）、无通信需求（如独自休闲、无外部关联的个人行为）
                - 输出格式：`"communication_scene": "xxx"`
                
                #### 4. 通信触发概率（分"事件相关"和"事件无关"，取值 0%-100%，保留整数）
                - 计算依据（基础值 + 修正项，总和强制约束在 0%-100%，逻辑优先级：基础值→核心修正→微调）：
                  - 基础概率（贴合场景本质通信需求）：
                    - 相关通信：紧急事务 90%、日常分享 65%、社交互动 70%、商务交互 80%、日常生活 45%、无通信需求 0%(若事件描述中明确描述了通信事件，则概率为100%)；
                    - 无关通信（随机外部干扰/主动联络）：基础 15%（无特殊情况默认此值）。
                  - 核心修正规则（按影响程度排序，叠加计算）：
                    1. 面对面场景：事件相关通信 -35%（现场已直接交流，大幅降低远程沟通需求）；若相关通信基础值≤35%，修正后最低保留 0%；
                    2. 多主题/关联人员≥2 人：相关通信 +10%（需求复杂/涉及多人，需额外沟通确认）；
                    3. 高频时段（8:00-9:00/12:00-13:00/19:00-21:00）：无关通信 +5%（该时段为社交/事务活跃期，随机联络概率提升）；
                    4. 低频时段（0:00-7:00/22:00-24:00）：无关通信 -8%（夜间休息时段，随机联络概率降低，最低保留 5%）；
                    5. 个人画像修正：社交型人格→相关通信 +10%/无关通信 +5%（主动沟通意愿强）；职场人→商务类相关通信 +10%（工作场景沟通需求更高）；内向型人格→相关通信 -5%/无关通信 -3%（被动沟通为主）；
                    6. 事件属性修正：短时长事件（≤15 分钟）→相关通信 -5%（事务简单，沟通需求低）；长时长事件（≥60 分钟）→相关通信 +5%（事务复杂，需多轮沟通）；【仅限日常分享场景】若遇到重要事件、新奇事件、游玩事件、纪念性事件等→相关通信额外 +15%（分享意愿强烈，本规则叠加于日常分享基础概率之上）。
                  - 特殊规则：
                    1. 无关通信概率最低保留 5%（即使低频时段/内向人格，仍存在极小概率随机联络）；
                    2. 无通信需求场景：相关通信强制 0%，无关通信按规则计算（最低 5%）；
                    3. 最终概率可在±5% 内微调（基于事件合理性，如"独自看电影"无关通信可降至 5%，"节日期间社交"无关通信可升至 20%）。
                - 输出格式：`"trigger_probability": {{"related": "xx%", "unrelated": "xx%"}}`
                
                #### 5. 通信类型概率（通话/短信，触发概率>0 时计算，两类概率总和 100%，保留整数）
                - 基础规则（贴合场景沟通习惯）：
                  - 相关通信：
                    - 紧急事务：通话 90%/短信 10%（紧急情况需实时沟通，优先通话）；
                    - 日常分享：短信 85%/通话 15%（日常分享以异步短信为主，轻松随意）；
                    - 社交互动：短信 70%/通话 30%（日常社交以异步短信为主，亲密关系可能通话）；
                    - 商务交互：通话 60%/短信 40%（工作沟通需高效确认，通话占比更高）；
                    - 日常生活：短信 75%/通话 25%（便民服务/购物咨询以短信为主，复杂需求可能通话）；
                  - 无关通信：
                    - 亲友问候：短信 60%/通话 40%（日常问候短信便捷，亲密关系可能通话）；
                    - 事项提醒：短信 85%/通话 15%（提醒类信息无需实时响应，优先短信）；
                    - 生活咨询：短信 50%/通话 50%（咨询可能涉及细节，通话/短信概率均等）；
                    - 其他交流：短信 70%/通话 30%（随机交流以短信为主，避免打扰对方）。
                - 修正项（叠加计算，总和保持 100%）：
                  1. 面对面场景→相关通信短信概率 -10%/通话概率 +10%（现场已交流，远程短信需求降低，若需补充沟通优先简短通话）；
                  2. 多参与者/复杂事项→短信概率 +10%/通话概率 -10%（需传递明确信息，短信可留痕、便于多人同步）；
                  3. 高频时段→通话概率 +5%（对方接听概率高，优先通话）；
                  4. 低频时段→通话概率 -10%（避免打扰对方，优先短信，最低保留 5%）。
                - 输出格式：`"type_probability": {{"related": {{"call": "xx%", "sms": "xx%"}}, "unrelated": {{"call": "xx%", "sms": "xx%"}}}}`

                #### 6. 多短信生成概率（仅短信类型触发时计算，各类概率总和 100%，保留整数）
                - 核心逻辑：基于事件复杂度、参与者数量、沟通目的，按常识分配概率，同时考虑"发送必要性"和"接收响应概率"，避免不合理的多短信场景：
                  - 简单场景（单参与者 + 事项单一 + 无后续需求，如"给家人报平安""接收快递通知"）：1 条 85%、2 条 15%（2 条仅为补充说明，无多余信息）；
                  - 一般场景（2-3 个参与者/事项较简单 + 需确认，如"同事对接工作进度""约 2 个朋友聚餐"）：1 条 60%、2 条 30%、3 条 10%（2 条用于核心沟通，3 条仅为细节补充）；
                  - 复杂场景（≥3 个参与者/事项繁琐 + 多轮确认，如"组织部门团建协调时间""多人旅行规划"）：1 条 10%、2 条 50%、3 条 35%、4 条 5%（需多轮同步信息，4 条为上限，避免过度冗余）；
                  - 日常分享类（如"朋友圈分享""生活点滴闲聊"）：1 条 80%、2 条 20%（日常分享简短，一条足够）。
                - 输出格式：`"multi_sms_probability": {{"sms_count": ["1 条:xx%", "2 条:xx%", ...], "note": "xxx"}}`（note 需明确说明判断依据，如"2 个参与者 + 事项简单，按一般场景分配；高频时段修正短信概率 +5%"）
                
                #### 7. 场景推理说明（可选，仅用于 debug/追溯，不需要在最终输出中体现）
                - 可选说明内容（不需要输出，仅供分析过程参考）：
                  1. 场景判定依据（结合事件时间、目的、参与者等属性说明为何归类该场景）；
                  2. 触发概率修正原因（逐一说明适用的修正规则，如"面对面场景 -35%+ 多主题 +10%，最终相关通信概率为 XX%"）；
                  3. 多短信场景归类原因（说明场景复杂度/参与者数量，为何选择该概率分配）。
                - 注意：此字段仅供分析参考，**最终输出 JSON 中不需要包含 scene_reasoning 字段**

                ### 二、分析原则（严格遵守，确保结果合理性）
                1. 概率逻辑自洽：修正项叠加后不得出现矛盾（如相关通信概率不可为负，通话/短信概率总和必须 100%）；
                2. 贴合现实规律：避免极端概率（如无关通信不超过 30%，复杂场景 4 条短信概率不超过 10%）；
                3. 适配个人画像：通信概率需与用户人格特征匹配（如内向型人格通话概率低于外向型）；
                4. 输出精简规范：仅保留指定 7 项字段（event_id、event_name、event_basic、communication_scene、trigger_probability、type_probability、multi_sms_probability），无任何额外文本、注释，严格按 JSON 数组格式输出。

                ### 三、输出格式要求（严格遵循，否则视为无效）
                仅输出 JSON 数组，每个元素对应一个事件，字段无缺失、无冗余，示例如下（可直接参考格式）：
                [
                  {{
                    "event_id": "5902",
                    "event_name": "早餐准备与家庭交流",
                    "event_basic": {{"time": "2025-12-01 07:00", "scene_keyword": "家庭早餐/互动", "purpose": "家庭情感交流", "is_face_to_face": "是", "related_person_status": "家人 2 人", "duration": "30 分钟", "is_multi_topic": "否"}},
                    "communication_scene": "社交互动",
                    "trigger_probability": {{"related": "45%", "unrelated": "20%"}},
                    "type_probability": {{"related": {{"call": "35%", "sms": "65%"}}, "unrelated": {{"call": "40%", "sms": "60%"}}}},
                    "multi_sms_probability": {{"sms_count": ["1 条:85%", "2 条:15%"], "note": "单参与者 + 事项单一，按简单场景分配；面对面场景修正短信概率 -10%"}}
                  }},
                  {{
                    "event_id": "5913",
                    "event_name": "组织部门团建协调时间",
                    "event_basic": {{"time": "2025-12-01 20:12", "scene_keyword": "商务+协调", "purpose": "团队活动组织", "is_face_to_face": "否", "related_person_status": "同事 5 人", "duration": "78 分钟", "is_multi_topic": "是"}},
                    "communication_scene": "商务交互",
                    "trigger_probability": {{"related": "95%", "unrelated": "20%"}},
                    "type_probability": {{"related": {{"call": "45%", "sms": "55%"}}, "unrelated": {{"call": "15%", "sms": "85%"}}}},
                    "multi_sms_probability": {{"sms_count": ["1 条:10%", "2 条:50%", "3 条:35%", "4 条:5%"], "note": "≥3 个参与者 + 事项繁琐，按复杂场景分配；多参与者修正短信概率 +10%"}}
                  }}
                ]
                
                请基于<当日事件>：{daily_events}、<个人画像>：{persona}，严格按上述要求逐事件分析并输出结果，确保每个字段的概率逻辑可追溯、符合现实场景。
            '''
        
        # 获取 extool（需要从外部导入）
        if extool is None:
            from src.lifebench.event.phone_data_gen import extool
        
        # 获取今日 daily_event
        res1 = extool.filter_by_date(date)
        res = []
        for i in range(len(res1)):
            if "-" in res1[i]['event_id']:
                continue
            res.append(res1[i])
            print(res1[i]['event_id'])
        mid = (len(res) + 1) // 2  # 向上取整（如 5→3，4→2）
        res1, res2 = res[:mid], res[mid:]
        prompt = event_classify.format(daily_events=res1, persona=extool.persona)
        a = llm_call_reason_j(prompt)
        print(a)
        prompt = event_classify.format(daily_events=res2, persona=extool.persona)
        b = llm_call_reason_j(prompt)
        print(b)
        resx1 = self.generate_llm_instructions(a)
        resx2 = self.generate_llm_instructions(b)
        print(resx1)
        print(resx2)
        template = '''
请基于用户提供的{{当日事件}}、{{联系人列表}}和{{操作指令}}，生成具体的手机通信操作（包括短信和通话），严格遵循以下字段规则、生成原则和输出格式，确保数据真实、唯一、无重复，优化时间逻辑和收发方向推断：

### 一、核心遵循原则（优先级：指令要求 > 场景逻辑 > 个人画像适配）
1. 指令强绑定：每个核心通信操作必须严格对应一条操作指令，完全遵守「event_id、通信场景、通信类型、时间范围、内容要求」，不得偏离核心诉求。
2. 联系人优先规则：所有个人通信优先从联系人列表匹配 `contactName` 和`phoneNumber`；无联系人列表时，按场景合理虚构真实关系的联系人（如商务场景→"王经理""李同事"，社交场景→"张朋友""妈妈"）及 11 位有效手机号（格式`+861xxxxxxxxx`）。
3. 个人画像深度适配：通信内容、沟通语气、联系人选择、交互频率需贴合用户画像（如社交型人格倾向主动问候、多轮互动；职场人多商务沟通，语气专业简洁；内向型人格以被动接收为主，沟通内容简短）；事件无关通信需基于联系人关系设计合理场景（家人→生活关心、同事→工作寒暄、朋友→约饭/闲聊、客户→节日问候）。
4. **内容简洁明确**：短信文本应精炼直接，准确反映事件核心信息，避免冗长叙述和无关细节。

### 二、字段规则

#### （一）短信类事件（type 固定为"sms"）
需包含以下字段，缺一不可：
- event_id：直接使用指令中的 event_id（如"5903"），仅保留原事件 id，不要添加任何后缀
- type：固定值"sms"
- message_content：符合场景逻辑、指令要求及联系人关系，**内容简洁明确，准确反映事件核心信息**：
  - 事件关联（个人）：
    - 提前通知：明确时间、事项、要求（如"明天 10 点销售会议，带数据报表"）；
    - 同步/核对：简洁传递核心信息（如"商圈考察完成，竞品总结已发邮箱"）；
    - 日常分享：生活化、口语化（如【闲聊】周末去爬山拍了很多照片，有一张特别满意）；
  - 事件无关（个人）：基于联系人关系设计聊天/谈论场景（如家人→"降温记得添衣"、同事→"报表整理好，需要发你吗"、朋友→"考上研究生了，请你吃饭！"）
- contactName：优先联系人列表；个人通信填真实姓名；机构类填官方名称（如"XX 电商""XX 保险公司"）
- phoneNumber：个人填 11 位手机号；机构类填 1069/400 号段
- datetime：按指令时间范围 + 场景逻辑生成，格式"YYYY-MM-DD HH:MM:SS"：
  - 事件相关：
    - 提前通知类（如会议、活动协调）：事件发生前 30 分钟 -24 小时；
    - 同步/核对类（如数据、工作对接）：事件发生中或结束后 10 分钟内；
    - 紧急事务：事件发生时±5 分钟；
  - 事件无关：指令指定时段内（如"2025-12-01 15:20 当日 8-21 点"）随机生成合理时间
- message_type："发送"或"接收"（按场景 + 关系推断）

#### （二）通话类事件（type 固定为"call"）
需包含以下字段，缺一不可：
- event_id：直接使用指令中的 event_id（如"1231"），仅保留原事件 id，不要添加任何后缀
- type：固定值"call"
- phoneNumber：个人填 11 位手机号；机构类填 1069/400/010 号段
- contactName：优先联系人列表；个人通信填真实姓名；机构类填官方名称（如"XX 银行""XX 快递"）
- datetime：通话开始时间，按指令时间范围 + 场景逻辑生成，格式"YYYY-MM-DD HH:MM:SS"：
  - 事件相关：
    - 提前通知类（如会议、活动协调）：事件发生前 30 分钟 -24 小时；
    - 同步/核对类（如数据、工作对接）：事件发生中或结束后 10 分钟内；
    - 紧急事务：事件发生时±5 分钟；
  - 事件无关：指令指定时段内（如"2025-01-01 08:50 当日 8-21 点"）随机生成合理时间
- datetime_end：通话结束时间，格式"YYYY-MM-DD HH:MM:SS"，需在 datetime 之后，合理设置通话时长（如 30 秒 -10 分钟）
- direction：通话方向，1 表示呼出（用户主动拨打），0 表示呼入（用户被动接听）
- call_result：通话结果，可取值："接通"、"未接通"、"已挂断"、"拒接"

### 三、生成原则
1. 时间逻辑优化：
   - 事件相关通信不再局限于"与事件时间接近"，而是按"通知/同步/紧急"三类场景分配时间（如"会议通知"提前 1 小时，"数据核对"事件中，"紧急协调"即时）；
   - 所有通信时间需在当日 8:00-21:00，避免凌晨/深夜。
2. 收发方向推断：
   - 发送/呼出（主动）：
     - 事件相关：用户发起的通知、核对、协调（如"同步销售数据""预约服务"）；
     - 事件无关：用户主动联系亲友/同事（如社交型人格问候家人、主动约朋友聚餐）；
     - 关系场景：用户对长辈、上级的问候/汇报，对平级的协调/约见。
   - 接收/呼入（被动）：
     - 事件相关：他人发起的与事件相关的沟通（如同事核对数据、机构通知保单归档）；
     - 事件无关：亲友/同事主动联系用户（如朋友约饭、家人关心生活）；
     - 关系场景：用户接收长辈的叮嘱、上级的安排、朋友的日常分享。
3. 联系人与场景匹配：
   - 事件相关：优先选择与事件目的相关的联系人（如"销售数据核对"→同事/上级，"保险办理"→保险公司专员）；
   - 事件无关：基于联系人关系生成合理交流场景（如家人→生活关心、同事→工作寒暄、朋友→娱乐约见、客户→节日问候），避免无意义的泛泛沟通。
4. 合理优化，避免生成的通信数据同质，通信记录之间也要协调连贯。
5. 去重与真实性：
   - 同一核心 event_id 仅生成 1 个核心操作；
   - 手机号格式规范（个人 11 位，机构 1069/400/010 号段），短信内容自然（个人口语化，机构官方化），通话记录符合真实通话场景；
   - 通话时长合理，根据场景设置（如紧急事务通话较短，社交聊天通话较长）。

### 四、输出格式要求
仅输出 JSON 数组内容，不添加任何额外文本、注释或代码块标记。每个元素对应 1 个通信操作（短信或通话），按时间顺序排列。示例：
[
{{"type":"sms","event_id":"5901","message_content":"妈妈：宝贝，今天降温记得穿厚点，晚上回家给你炖了汤","contactName":"妈妈","phoneNumber":"+86135xxxx2345","datetime":"2025-12-01 09:15:30","message_type":"接收"}},
{{"type":"sms","event_id":"5903","message_content":"我：王总，明天 10 点销售会议，记得带最新数据报表，地点在 3 楼会议室","contactName":"王总","phoneNumber":"+86139xxxx6789","datetime":"2025-12-01 09:00:10","message_type":"发送"}},
{{"type":"call","event_id":"5403","phoneNumber":"+8613807123456","contactName":"冯建国","datetime":"2025-01-01 08:50:00","datetime_end":"2025-01-01 08:55:30","direction":1,"call_result":"接通"}}
]

请基于{{操作指令}}：{instructions}、{{联系人列表}}：{contacts}、{{当日事件}}：{daily_events}生成具体通信操作。
'''
        prompt = template.format(daily_events=res1, contacts=contact, instructions=resx1)
        res = llm_call_reason_j(prompt, extool.context)
        print(res)
        res = self.remove_json_wrapper(res, "array")
        data = json.loads(res)
        c += data
        prompt = template.format(daily_events=res2, contacts=contact, instructions=resx2)
        res = llm_call_j(prompt, extool.context)
        print(res)
        res = self.remove_json_wrapper(res, "array")
        data = json.loads(res)
        c += data

        # ========== 重点场景增强流程 ==========
        print(f"\n开始重点场景增强流程...")
        key_scenes = self.extract_key_scenes(res1 + res2, extool.persona)
        key_scene_data = self.generate_key_scene_sms(key_scenes, contact, extool.persona)
        if key_scene_data:
            c += key_scene_data
            print(f"✓ 合并后通信数据共 {len(c)} 条（原生 {len(c) - len(key_scene_data)} 条 + 重点场景增强 {len(key_scene_data)} 条）")
        else:
            print("⚠️  未生成重点场景增强数据，继续使用原生数据")
        # ====================================

        # ========== 重复/不一致检测 ==========
        c = self.analyze_and_merge_duplicates(c, res1 + res2)
        # ====================================

        # ========== 新增：合理性校验与格式校验环节 ==========
        print(f"\n开始通信数据校验，共 {len(c)} 条数据...")
        
        # 获取用户姓名（从 persona 中提取）
        user_name = ""
        if isinstance(extool.persona, dict):
            user_name = extool.persona.get("name", "") or extool.persona.get("姓名", "")
        if not user_name:
            print("警告：未找到用户姓名，跳过本人姓名检测")
        
        # 构建 event_id 到 daily_event 的映射
        all_events = res1 + res2
        event_to_daily = {}
        for event in all_events:
            event_id = event.get("event_id", "")
            event_to_daily[event_id] = event
        
        # 第一轮：合理性校验 + LLM 修正
        valid_data = []
        need_format_check = []  # 需要进一步格式校验的数据
        
        for idx, item in enumerate(c):
            event_id = item.get("event_id", "")
            daily_event = event_to_daily.get(event_id, {})
            context = {
                "event_name": daily_event.get("event_name", ""),
                "event_basic": daily_event.get("event_basic", {}),
                "communication_scene": daily_event.get("communication_scene", "")
            }
            
            is_valid, fixed_data, error_msg = self.validate_and_fix_communication_data(
                item, context, all_events, user_name
            )
            
            if is_valid:
                if fixed_data:
                    # LLM 修正了数据，使用修正后的数据
                    valid_data.append(fixed_data)
                    print(f"  [合理性修正成功] 索引 {idx}, event_id={event_id}")
                else:
                    # 数据合理，无需修正
                    valid_data.append(item)
                # 对通过合理性校验的数据进行格式校验
                format_valid, format_error = self._validate_format_only(item if not fixed_data else fixed_data)
                if format_valid:
                    need_format_check.append(item if not fixed_data else fixed_data)
                else:
                    print(f"  [格式错误] 索引 {idx}, event_id={event_id}: {format_error}")
            else:
                print(f"  [合理性错误] 索引 {idx}, event_id={event_id}: {error_msg}，抛弃该数据")
        
        print(f"\n合理性校验结果：通过 {len(need_format_check)} 条，抛弃 {len(c) - len(need_format_check)} 条")
        
        # 第二轮：格式校验（年份、必填字段等）
        final_valid = []
        for item in need_format_check:
            event_id = item.get("event_id", "")
            format_valid, format_error = self._validate_format_only(item)
            if format_valid:
                final_valid.append(item)
            else:
                print(f"  [格式校验失败] event_id={event_id}: {format_error}，抛弃该数据")
        
        # 更新最终结果
        c = final_valid
        print(f"\n最终保留 {len(c)} 条通信数据\n")
        # ================================================
        
        print(c)
        return c
    
    @staticmethod
    def remove_json_wrapper(s: str, json_type: str = 'array') -> str:
        """
        移除 JSON 字符串的包装
        
        Args:
            s: 输入字符串
            json_type: JSON 类型，'object'对应{}，'array'对应[]，默认为'array'
            
        Returns:
            处理后的字符串
        """
        import re
        # 1. 先移除开头的 ```json 和结尾的 ```标记
        pattern = r'^\s*```json\s*\n?|\s*```\s*$'
        result = re.sub(pattern, '', s, flags=re.MULTILINE)
        
        # 2. 根据 json_type 提取对应的括号内容
        if json_type == 'array':
            first_bracket = result.find('[')
            last_bracket = result.rfind(']')
            if first_bracket != -1 and last_bracket != -1 and first_bracket < last_bracket:
                result = result[first_bracket:last_bracket + 1]
        else:  # 默认处理 JSON 对象
            first_brace = result.find('{')
            last_brace = result.rfind('}')
            if first_brace != -1 and last_brace != -1 and first_brace < last_brace:
                result = result[first_brace:last_brace + 1]
            
        return result
