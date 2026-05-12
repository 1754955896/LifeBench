"""
手机操作数据生成器
用于为 QA 问题生成对应的手机操作数据（sms, call, calendar 等）
"""

import json
from typing import List, Dict, Any
from src.lifebench.utils.llm_call import llm_call, llm_call_j


class PhoneOperationGenerator:
    """
    手机操作数据生成器
    
    功能：
    - 根据事件和问题生成相关的手机操作数据
    - 支持多种类型：sms, call, calendar, note, gallery 等
    - 确保生成的数据能够支撑问题的回答
    """
    
    # 支持的手机数据类型（与 type_specs 中的键保持一致）
    SUPPORTED_TYPES = {'sms', 'call', 'photo', 'push', 'note', 'calendar', 'agent_chat'}

    # 各数据类型允许的字段（用于清理多余字段）
    ALLOWED_FIELDS = {
        'sms': {'type', 'message_content', 'contactName', 'phoneNumber', 'datetime', 'message_type', 'daily_event_id', 'event_id'},
        'call': {'type', 'phoneNumber', 'contactName', 'datetime', 'datetime_end', 'direction', 'call_result', 'daily_event_id', 'event_id'},
        'photo': {'type', 'caption', 'title', 'datetime', 'location', 'faceRecognition', 'imageTag', 'ocrText', 'shoot_mode', 'image_size', 'daily_event_id', 'event_id'},
        'push': {'type', 'title', 'content', 'datetime', 'source', 'push_status', 'jump_path', 'daily_event_id', 'event_id'},
        'note': {'type', 'title', 'content', 'datetime', 'daily_event_id', 'event_id'},
        'calendar': {'type', 'title', 'description', 'start_time', 'end_time', 'datetime', 'daily_event_id', 'event_id'},
        'agent_chat': {'type', 'date', 'conversation', 'daily_event_id', 'event_id'}
    }

    def __init__(self):
        self.operation_types = ['sms', 'call', 'calendar', 'note', 'gallery', 'contact']

    def _convert_unsupported_type(self, operation_type: str, generation_hint: str, original_event: Dict[str, Any]) -> tuple:
        """
        将不支持的操作类型转换为支持的操作类型，同时保留 generation_hint 的核心信息

        Args:
            operation_type: 不支持的操作类型
            generation_hint: 原始的生成提示
            original_event: 原始事件数据

        Returns:
            tuple: (转换后的操作类型, 转换后的生成提示)
        """
        event_info = json.dumps(original_event, ensure_ascii=False, indent=2) if isinstance(original_event, dict) else str(original_event)

        convert_prompt = f"""
作为手机操作类型转换专家，请将不支持的操作类型转换为支持的操作类型，并调整生成要求。

【背景】
当前系统支持以下手机操作类型：
- sms（短信）
- call（通话）
- photo（照片）
- push（推送通知）
- note（笔记）
- calendar（日程）

【原始请求】
- 操作类型：{operation_type}
- 原始事件全部信息：
{event_info}
- 生成要求：{generation_hint if generation_hint else '无特殊要求'}

【转换要求】
1. 分析原始请求中 operation_type 和 generation_hint 要表达的核心信息和意图
2. 从支持的类型中选择最合适的一种或多种来表达这个意图
3. 调整 generation_hint，使其符合转换后操作类型的特点，同时保留原始核心信息
4. 如果原始类型已是支持类型，直接返回

【输出格式】
请以 JSON 格式返回：
{{
    "converted_type": "转换后的操作类型（如 sms/call/photo/push/note/calendar）",
    "converted_hint": "调整后的生成要求，保留原始核心信息，符合新类型特点",
    "reason": "转换理由"
}}

请直接输出 JSON，不要其他说明文字：
"""
        try:
            result = llm_call_j(convert_prompt)
            start_idx = result.find('{')
            end_idx = result.rfind('}') + 1
            if start_idx != -1 and end_idx != -1:
                converted = json.loads(result[start_idx:end_idx])
                converted_type = converted.get('converted_type', 'sms')
                converted_hint = converted.get('converted_hint', generation_hint)

                # 确保转换后的类型是支持的
                if converted_type not in self.SUPPORTED_TYPES:
                    converted_type = 'sms'

                print(f"[PhoneOperationGenerator] 类型转换: {operation_type} -> {converted_type}")
                print(f"[PhoneOperationGenerator] 转换理由: {converted.get('reason', 'N/A')}")

                return converted_type, converted_hint
        except Exception as e:
            print(f"[PhoneOperationGenerator] 类型转换失败: {e}，使用默认类型 sms")

        return 'sms', generation_hint

    def generate(self,
                 operation_type: str,
                 original_event: Dict[str, Any],
                 question: str,
                 generation_hint: str = None) -> List[Dict[str, Any]]:
        """
        生成手机操作数据

        Args:
            operation_type: 操作类型（sms/call/calendar 等）
            original_event: 原始事件数据
            question: 相关问题
            generation_hint: 生成提示/要求

        Returns:
            手机操作数据列表
        """
        print(f"[PhoneOperationGenerator] 生成 {operation_type} 类型数据")

        # 统一外部操作类型到内部标准类型
        normalized_type = operation_type
        if operation_type == 'phonecall':
            normalized_type = 'call'
        if operation_type in {'gallery', 'contact'}:
            normalized_type = 'photo'  # gallery 和 contact 归类为 photo

        # 检查操作类型是否支持，如果不支持则进行类型转换
        if normalized_type not in self.SUPPORTED_TYPES:
            print(f"[PhoneOperationGenerator] 检测到不支持的操作类型: {operation_type}，正在进行类型转换...")
            normalized_type, generation_hint = self._convert_unsupported_type(
                normalized_type, generation_hint, original_event
            )
            print(f"[PhoneOperationGenerator] 转换后的类型: {normalized_type}")

        operation_type = normalized_type

        max_fix_attempts = 2  # 最多修正2次

        for fix_attempt in range(max_fix_attempts):
            # 构建生成提示
            prompt = self._build_generation_prompt(
                operation_type,
                original_event,
                question,
                generation_hint
            )

            # 调用 LLM 生成
            result = llm_call_j(prompt)

            # 解析结果
            operations = self._parse_result(result, operation_type, original_event)

            # 格式硬校验
            if not operations:
                if fix_attempt < max_fix_attempts - 1:
                    print(f"[PhoneOperationGenerator] 生成数据为空，开始第 {fix_attempt + 2} 轮生成...")
                    continue
                else:
                    return []

            valid_ops, invalid_data, invalid_reasons = self._validate_format(operations, operation_type)

            if not invalid_data:
                # 所有数据格式都正确
                print(f"[PhoneOperationGenerator] 格式校验通过，共 {len(valid_ops)} 条数据")
                return valid_ops

            # 格式不正确，尝试逐条修正
            if fix_attempt < max_fix_attempts - 1:
                print(f"[PhoneOperationGenerator] 格式校验失败，共 {len(invalid_data)} 条格式错误，开始修正...")
                for idx, invalid_op in invalid_data:
                    error_reason = invalid_reasons.get(idx, "未知错误")
                    fixed_op = self._fix_single_format(
                        invalid_op, error_reason, operation_type, original_event
                    )
                    if fixed_op:
                        valid_ops.append(fixed_op)
                        print(f"  [修正成功] 索引 {idx}: {error_reason}")

                # 修正后再次校验
                valid_ops, invalid_data, _ = self._validate_format(valid_ops, operation_type)
                if not invalid_data:
                    print(f"[PhoneOperationGenerator] 修正后格式校验通过，共 {len(valid_ops)} 条数据")
                    return valid_ops
                else:
                    print(f"[PhoneOperationGenerator] 修正后仍有 {len(invalid_data)} 条格式错误数据，继续修正...")
            else:
                print(f"[PhoneOperationGenerator] 格式校验失败，抛弃 {len(invalid_data)} 条格式错误数据")
                return valid_ops if valid_ops else []

        # 生成结束后校验并修正 daily_event_id 和 event_id
        final_valid_ops = []
        for op in valid_ops:
            # 校验 daily_event_id：不存在、非正整数、非数字字符串则默认为 0
            deid = op.get('daily_event_id')
            if isinstance(deid, int):
                pass  # 有效
            elif isinstance(deid, str) and deid.isdigit():
                pass  # 有效
            else:
                op['daily_event_id'] = "0"
            # 确保 event_id 字段存在（至少为空数组）
            if 'event_id' not in op:
                op['event_id'] = []
            final_valid_ops.append(op)

        return final_valid_ops
    
    def _build_generation_prompt(self,
                                  operation_type: str,
                                  original_event: Dict[str, Any],
                                  question: str,
                                  generation_hint: str = None) -> str:
        """
        构建生成提示
        
        Args:
            operation_type: 操作类型
            original_event: 原始事件
            question: 问题
            generation_hint: 生成提示
            
        Returns:
            完整的提示词
        """
        event_info = json.dumps(original_event, ensure_ascii=False, indent=2)
        
        # 提取事件类型
        event_type = original_event.get('type', '未知事件') if isinstance(original_event, dict) else '未知事件'
        event_name = original_event.get('name', original_event.get('event_name', '未命名事件')) if isinstance(original_event, dict) else '未命名事件'
        
        hint_text = f"\n生成要求：{generation_hint}" if generation_hint else ""

        # 统一外部操作类型到内部标准类型
        # phonecall 和 call 都统一为 call
        normalized_type = operation_type
        if operation_type == 'phonecall':
            normalized_type = 'call'

        # operation_type 到 type_spec key 的映射
        type_spec_key_map = {
            'call': 'phonecall',
            'sms': 'sms',
            'photo': 'photo',
            'push': 'push',
            'note': 'note',
            'calendar': 'calendar'
        }
        type_spec_key = type_spec_key_map.get(normalized_type, normalized_type)

        # 根据事件类型提供特定的生成指导
        event_type_guidance = self._get_event_type_guidance(event_type, type_spec_key)

        prompt = f"""
        作为手机操作数据生成器，请根据以下信息生成{operation_type}类型的操作数据。
        
        【原始事件】
        {event_info}
        
        【事件类型分析】
        - 事件类型：{event_type}
        - 事件名称：{event_name}
        {event_type_guidance}
        
        【生成目标】
        生成的{operation_type}数据应该：
        1. 与原始事件（{event_name}）相关且合理
        2. 符合真实用户在{event_type}场景下的使用习惯
        3. 格式规范、内容完整
        4. **严格遵循以下特定要求**：{generation_hint if generation_hint else '无特殊要求'}
        
        **【重要】数据数量要求**
        - **严格按照要求生成指定数量的数据**
        - **如果没有明确要求多个数据，只生成 1 条**
        - 不要过度生成，避免冗余数据
        - 每条数据都应该是必要且有意义的
        
        **【重要】数据真实性要求**
        - 生成的数据必须符合真实手机使用场景
        - 时间、内容、联系人等细节要合理自然
        - 避免生硬、刻意或不符合常理的数据
        - 确保数据之间的逻辑连贯性
        
        【输出格式要求】
        请以 JSON 数组格式返回，每个操作包含以下字段：
        - phone_id: 唯一标识（字符串，从"1"开始编号）
        - type: 操作类型 "{operation_type}"
        - date: 日期时间（格式：YYYY-MM-DD HH:MM:SS）
        - 其他类型特定字段（见下方说明）
        
        【不同类型的数据结构】
        """

        type_specs = {
            'sms': """
        SMS 短信：
        {{
            "type": "sms",
            "message_content": "短信内容（应与{event_type}事件相关）",
            "contactName": "联系人姓名",
            "phoneNumber": "电话号码",
            "datetime": "2025-03-15 14:30:00",
            "message_type": "发送/接收",
            "daily_event_id": "输入事件的 id",
            "event_id": []
        }}
        """,
            'phonecall': """
        Phone Call 通话：
        {{
            "type": "call",
            "phoneNumber": "电话号码",
            "contactName": "联系人姓名",
            "datetime": "2025-03-15 14:30:00",
            "datetime_end": "2025-03-15 14:35:00",
            "direction": 1,
            "call_result": "接通",
            "daily_event_id": "输入事件的 id",
            "event_id": []
        }}
        """,
            'photo': """
        Photo 照片：
        {{
            "type": "photo",
            "caption": "照片描述（应与{event_type}事件相关）",
            "title": "IMG_20250315_143000",
            "datetime": "2025-03-15 14:30:00",
            "location": {{
                "province": "省份",
                "city": "城市",
                "district": "区域",
                "streetName": "街道名",
                "streetNumber": "门牌号",
                "poi": "地点名称"
            }},
            "faceRecognition": "人物姓名",
            "imageTag": ["标签 1", "标签 2"],
            "ocrText": "OCR 识别文字",
            "shoot_mode": "拍摄模式",
            "image_size": "图片尺寸",
            "daily_event_id": "输入事件的 id",
            "event_id": []
        }}
        """,
            'push': """
        Push Notification 推送通知：
        {{
            "type": "push",
            "title": "推送标题",
            "content": "推送内容",
            "datetime": "2025-03-15 14:30:00",
            "source": "应用名称",
            "push_status": "已读/未读",
            "jump_path": "跳转路径",
            "daily_event_id": "输入事件的 id",
            "event_id": []
        }}
        """,
            'note': """
        Note 笔记：
        {{
            "type": "note",
            "title": "笔记标题（应与{event_type}事件相关）",
            "content": "笔记内容",
            "datetime": "2025-03-15 14:30:00",
            "daily_event_id": "输入事件的 id",
            "event_id": []
        }}
        """,
            'calendar': """
        Calendar 日程：
        {{
            "type": "calendar",
            "title": "日程标题",
            "description": "详细描述（应与{event_type}事件相关）",
            "start_time": "开始时间 YYYY-MM-DD HH:MM:SS",
            "end_time": "结束时间 YYYY-MM-DD HH:MM:SS",
            "datetime": "2025-03-15 14:30:00",
            "daily_event_id": "输入事件的 id",
            "event_id": []
        }}
        """,
            'agent_chat': """
        Agent Chat 智能体对话：
        {{
            "type": "agent_chat",
            "date": "2025-03-15",
            "conversation": {{
                "turn 1": {{
                    "user": {{
                        "action": "topic query / need inference / need confirmation / solution discussion",
                        "content": "用户的问题或内容"
                    }},
                    "assistant": {{
                        "action": "topic query / need inference / need confirmation / solution discussion",
                        "content": "AI 助手的回复"
                    }}
                }},
                "turn 2": {{
                    "user": {{
                        "action": "topic query / need inference / need confirmation / solution discussion",
                        "content": "用户的进一步询问"
                    }},
                    "assistant": {{
                        "action": "topic query / need inference / need confirmation / solution discussion",
                        "content": "AI 助手的建议或解答"
                    }}
                }}
            }},
            "daily_event_id": "输入事件的 id",
            "event_id": []
        }}
        """
        }

        prompt += type_specs.get(type_spec_key, "").format(event_type=event_type)
        
        prompt += """
        
        请确保生成的数据：
        1. 数量合理
        2. 时间逻辑正确（在事件发生前后合理分布）
        3. 内容连贯
       
        
        只返回 JSON 数组，不要其他说明文字。
        """
        
        return prompt
    
    def _get_event_type_guidance(self, event_type: str, operation_type: str) -> str:
        """
        根据事件类型和操作类型提供特定的生成指导
        
        Args:
            event_type: 事件类型（如会议、电话、健身等）
            operation_type: 操作类型（sms, phonecall, photo, push, note, calendar）
            
        Returns:
            针对性的生成指导建议
        """
        # 定义常见事件类型的生成指导
        guidance_map = {
            '会议': {
                'sms': '- 短信内容可能涉及会议通知、会议变更、参会确认等\n- 发送者可能是组织者、参会者或秘书',
                'phonecall': '- 通话内容可能涉及会议讨论、参会确认、紧急联系等\n- 通话对象可能是同事、客户或会议组织者',
                'photo': '- 照片可能是会议现场、PPT、参会人员合影等\n- 地点应该是会议室或活动场所',
                'push': '- 推送可能是会议提醒、日程更新、会议软件通知等\n- 应用可能是日历、钉钉、企业微信等',
                'note': '- 笔记可能是会议纪要、待办事项、重要记录等\n- 内容应包含会议要点和决策',
                'calendar': '- 日程应包含会议标题、时间、地点、参会人等\n- 时间应该明确具体'
            },
            '电话': {
                'sms': '- 短信可能是通话后的补充信息、回电请求等\n- 内容应与通话对象相关',
                'phonecall': '- 通话记录应包含合理的时长、呼叫类型\n- 联系人应与事件中的角色一致',
                'photo': '- 照片可能性较低，除非是视频通话截图',
                'push': '- 推送可能是来电提醒、未接来电通知等',
                'note': '- 笔记可能是通话要点记录、待回复事项等',
                'calendar': '- 日程可能是预约回电、后续跟进等'
            },
            '健身': {
                'sms': '- 短信可能是教练通知、健身房提醒、朋友邀约等\n- 内容与健身计划相关',
                'phonecall': '- 通话可能是预约私教课、咨询健身问题等\n- 对象可能是教练、健友',
                'photo': '- 照片可能是健身打卡、器材使用、身材对比等\n- 地点在健身房或运动场所',
                'push': '- 推送可能是健身提醒、课程通知、健康数据同步等\n- 应用可能是 Keep、健身类 APP',
                'note': '- 笔记可能是训练计划、饮食记录、体重变化等',
                'calendar': '- 日程应包含固定的健身时间安排'
            },
            '日程': {
                'sms': '- 短信可能是日程提醒、活动变更通知等',
                'phonecall': '- 通话可能是确认行程安排、协调时间等',
                'photo': '- 照片可能是活动现场、景点打卡等\n- 与日程内容相关',
                'push': '- 推送主要是日程提醒、闹钟通知等',
                'note': '- 笔记可能是行程规划、旅行清单等',
                'calendar': '- 日程本身是核心数据，应详细准确'
            },
            '社交': {
                'sms': '- 短信频繁，涉及朋友聊天、聚会安排等',
                'phonecall': '- 通话对象多是朋友、家人\n- 内容轻松日常',
                'photo': '- 照片最多，包括聚餐、游玩、合影等\n- 地点多样',
                'push': '- 推送来自社交软件，如微信、QQ 等',
                'note': '- 笔记较少，可能是心情记录',
                'calendar': '- 日程可能是生日派对、聚会约定等'
            },
            '工作': {
                'sms': '- 短信涉及工作通知、客户沟通等\n- 语气正式',
                'phonecall': '- 通话多是工作讨论、业务联系\n- 时长较长',
                'photo': '- 照片可能是工作文档、项目现场等',
                'push': '- 推送来自办公软件、邮件客户端等',
                'note': '- 笔记包括工作计划、项目记录等\n- 内容专业',
                'calendar': '- 日程密集，包括会议、汇报、deadline 等'
            },
            '医疗': {
                'sms': '- 短信可能是医院通知、预约确认、检查提醒等',
                'phonecall': '- 通话可能是咨询医生、预约就诊等',
                'photo': '- 照片可能是检查报告、处方单等\n- 注意隐私',
                'push': '- 推送可能是复诊提醒、用药提醒等',
                'note': '- 笔记可能是症状记录、用药记录等',
                'calendar': '- 日程包括就诊时间、复查时间等'
            },
            '购物': {
                'sms': '- 短信包括订单通知、物流信息、促销信息等',
                'phonecall': '- 通话可能是联系商家、快递配送等',
                'photo': '- 照片是商品实拍、购物小票等',
                'push': '- 推送来自电商平台、支付软件等',
                'note': '- 笔记可能是购物清单、比价记录等',
                'calendar': '- 日程较少，可能是取货时间等'
            },
            '旅行': {
                'sms': '- 短信包括航班/火车通知、酒店预订、景点门票等',
                'phonecall': '- 通话可能是联系酒店、旅行社、同行人员等',
                'photo': '- 照片大量，包括风景、建筑、美食等\n- 地点在旅游目的地',
                'push': '- 推送来自旅游 APP、航司酒店通知等',
                'note': '- 笔记可能是游记、攻略、花费记录等',
                'calendar': '- 日程是整个行程安排'
            }
        }
        
        # 获取对应事件的指导
        event_guidance = guidance_map.get(event_type, {})
        specific_guidance = event_guidance.get(operation_type, '')
        
        if specific_guidance:
            return f"\n【{event_type}事件的{operation_type}数据特点】\n{specific_guidance}"
        else:
            return f"\n【通用建议】\n- 确保{operation_type}数据与{event_type}事件场景相符\n- 保持时间和内容的合理性"

    def _validate_format(self, operations: List[Dict[str, Any]], operation_type: str) -> tuple:
        """
        校验操作数据格式

        Args:
            operations: 操作数据列表
            operation_type: 操作类型

        Returns:
            (valid_ops: List, invalid_data: List, invalid_reasons: Dict) - 有效数据列表、无效数据列表、无效数据的错误原因
        """
        from datetime import datetime

        valid_ops = []
        invalid_data = []  # [(index, op_dict), ...]
        invalid_reasons = {}  # {index: error_message}

        # 定义各类型的必填字段
        field_specs = {
            'sms': ["type", "message_content", "contactName", "phoneNumber", "datetime", "message_type"],
            'call': ["type", "phoneNumber", "contactName", "datetime", "datetime_end", "direction", "call_result"],
            'photo': ["type", "caption", "title", "datetime", "location", "faceRecognition", "imageTag", "ocrText", "shoot_mode", "image_size"],
            'push': ["type", "title", "content", "datetime", "source", "push_status", "jump_path"],
            'note': ["type", "title", "content", "datetime"],
            'calendar': ["type", "title", "description", "start_time", "end_time", "datetime"],
            'agent_chat': ["type", "date", "conversation"]
        }

        required_fields = field_specs.get(operation_type, [])
        location_fields = ["province", "city", "district", "streetName", "streetNumber", "poi"]

        for idx, op in enumerate(operations):
            if not isinstance(op, dict):
                invalid_reasons[idx] = f"数据不是字典类型: {type(op)}"
                invalid_data.append((idx, op))
                continue

            # 1. 校验必填字段
            missing_fields = [f for f in required_fields if f not in op]
            if missing_fields:
                invalid_reasons[idx] = f"缺少必填字段: {missing_fields}"
                invalid_data.append((idx, op))
                continue

            # 2. 校验 type 字段
            if op.get('type') != operation_type:
                invalid_reasons[idx] = f"type 字段错误: 期望 '{operation_type}', 实际 '{op.get('type')}'"
                invalid_data.append((idx, op))
                continue

            # 3. 校验 datetime 格式
            try:
                dt = datetime.strptime(op["datetime"], "%Y-%m-%d %H:%M:%S")
                if dt.year != 2025:
                    invalid_reasons[idx] = f"datetime 年份不是 2025: {op['datetime']}"
                    invalid_data.append((idx, op))
                    continue
            except ValueError as e:
                invalid_reasons[idx] = f"datetime 格式错误: {op['datetime']}, 应为 'YYYY-MM-DD HH:MM:SS'"
                invalid_data.append((idx, op))
                continue

            # 4. 校验 location 嵌套字段（仅 photo 类型）
            if operation_type == 'photo':
                location = op.get('location')
                if not isinstance(location, dict):
                    invalid_reasons[idx] = f"location 格式错误，应为字典"
                    invalid_data.append((idx, op))
                    continue
                missing_location = [f for f in location_fields if f not in location]
                if missing_location:
                    invalid_reasons[idx] = f"location 缺少字段: {missing_location}"
                    invalid_data.append((idx, op))
                    continue

            # 5. 校验 call 类型特有字段
            if operation_type == 'call':
                direction = op.get('direction')
                if direction not in [0, 1]:
                    invalid_reasons[idx] = f"direction 取值错误: {direction}, 应为 0 或 1"
                    invalid_data.append((idx, op))
                    continue
                call_result = op.get('call_result')
                if call_result not in ["接通", "未接通", "已挂断", "拒接"]:
                    invalid_reasons[idx] = f"call_result 取值错误: {call_result}"
                    invalid_data.append((idx, op))
                    continue
                try:
                    datetime_end = datetime.strptime(op["datetime_end"], "%Y-%m-%d %H:%M:%S")
                    if datetime_end <= dt:
                        invalid_reasons[idx] = f"datetime_end 早于或等于 datetime"
                        invalid_data.append((idx, op))
                        continue
                except ValueError:
                    invalid_reasons[idx] = f"datetime_end 格式错误: {op['datetime_end']}"
                    invalid_data.append((idx, op))
                    continue

            # 6. 校验 calendar 类型特有字段
            if operation_type == 'calendar':
                try:
                    start_dt = datetime.strptime(op["start_time"], "%Y-%m-%d %H:%M:%S")
                    end_dt = datetime.strptime(op["end_time"], "%Y-%m-%d %H:%M:%S")
                    if end_dt < start_dt:
                        invalid_reasons[idx] = f"end_time 早于 start_time"
                        invalid_data.append((idx, op))
                        continue
                except ValueError as e:
                    invalid_reasons[idx] = f"start_time 或 end_time 格式错误: {str(e)}"
                    invalid_data.append((idx, op))
                    continue

            # 7. 校验 push 类型特有字段
            if operation_type == 'push':
                push_status = op.get('push_status')
                if push_status not in ["已读", "未读", "已删除"]:
                    invalid_reasons[idx] = f"push_status 取值错误: {push_status}"
                    invalid_data.append((idx, op))
                    continue

            # 8. 校验 sms 类型特有字段
            if operation_type == 'sms':
                message_type = op.get('message_type')
                if message_type not in ["发送", "接收"]:
                    invalid_reasons[idx] = f"message_type 取值错误: {message_type}"
                    invalid_data.append((idx, op))
                    continue

            # 9. 校验 agent_chat 类型特有字段
            if operation_type == 'agent_chat':
                conversation = op.get('conversation')
                if not isinstance(conversation, dict):
                    invalid_reasons[idx] = f"conversation 格式错误，应为字典"
                    invalid_data.append((idx, op))
                    continue
                # 检查 turn 1 和 turn 2
                for turn_key in ['turn 1', 'turn 2']:
                    if turn_key in conversation:
                        turn = conversation[turn_key]
                        if not isinstance(turn, dict):
                            invalid_reasons[idx] = f"conversation.{turn_key} 格式错误，应为字典"
                            invalid_data.append((idx, op))
                            continue
                        for role in ['user', 'assistant']:
                            if role in turn:
                                role_data = turn[role]
                                if not isinstance(role_data, dict):
                                    invalid_reasons[idx] = f"conversation.{turn_key}.{role} 格式错误，应为字典"
                                    invalid_data.append((idx, op))
                                    continue
                                if 'action' not in role_data or 'content' not in role_data:
                                    invalid_reasons[idx] = f"conversation.{turn_key}.{role} 缺少 action 或 content 字段"
                                    invalid_data.append((idx, op))
                                    continue

            valid_ops.append(op)

        return valid_ops, invalid_data, invalid_reasons

    def _get_type_spec(self, operation_type: str) -> str:
        """
        获取指定操作类型的格式规范

        Args:
            operation_type: 操作类型

        Returns:
            格式规范字符串
        """
        type_specs = {
            'sms': '''
字段格式：
- type: 固定 "sms"
- message_content: 短信内容
- contactName: 联系人姓名
- phoneNumber: 电话号码
- datetime: 格式 "YYYY-MM-DD HH:MM:SS"，年份为 2025
- message_type: 只能是 "发送" 或 "接收"
示例：
{{
    "type": "sms",
    "message_content": "短信内容",
    "contactName": "联系人姓名",
    "phoneNumber": "+8613912345678",
    "datetime": "2025-03-15 14:30:00",
    "message_type": "发送"
}}
''',
            'call': '''
字段格式：
- type: 固定 "call"
- phoneNumber: 电话号码
- contactName: 联系人姓名
- datetime: 格式 "YYYY-MM-DD HH:MM:SS"，年份为 2025
- datetime_end: 格式 "YYYY-MM-DD HH:MM:SS"，年份为 2025，必须晚于 datetime
- direction: 只能是 0 或 1
- call_result: 只能是 "接通"、"未接通"、"已挂断" 或 "拒接"
示例：
{{
    "type": "call",
    "phoneNumber": "+8613912345678",
    "contactName": "联系人姓名",
    "datetime": "2025-03-15 14:30:00",
    "datetime_end": "2025-03-15 14:35:00",
    "direction": 1,
    "call_result": "接通"
}}
''',
            'photo': '''
字段格式：
- type: 固定 "photo"
- caption: 照片描述
- title: 格式 "IMG_YYYYMMDD_HHMMSS"，如 "IMG_20250315_143025"
- datetime: 格式 "YYYY-MM-DD HH:MM:SS"，年份为 2025
- location: 嵌套对象，包含 province, city, district, streetName, streetNumber, poi
- faceRecognition: 字符串，如 "人物姓名" 或 "无"
- imageTag: 数组，如 ["标签1", "标签2"]
- ocrText: OCR 识别文字，无则填 "无"
- shoot_mode: 只能是 "正常拍照"、"夜景"、"人像" 或 "微距"
- image_size: 只能是 "4032×3024"、"3024×4032"、"2048×1536" 或 "1536×2048"
示例：
{{
    "type": "photo",
    "caption": "照片描述",
    "title": "IMG_20250315_143025",
    "datetime": "2025-03-15 14:30:00",
    "location": {{
        "province": "省份",
        "city": "城市",
        "district": "区域",
        "streetName": "街道名",
        "streetNumber": "门牌号",
        "poi": "地点名称"
    }},
    "faceRecognition": "人物姓名",
    "imageTag": ["标签1", "标签2"],
    "ocrText": "无",
    "shoot_mode": "正常拍照",
    "image_size": "4032×3024"
}}
''',
            'push': '''
字段格式：
- type: 固定 "push"
- title: 推送标题
- content: 推送内容
- datetime: 格式 "YYYY-MM-DD HH:MM:SS"，年份为 2025
- source: 应用名称
- push_status: 只能是 "已读"、"未读" 或 "已删除"
- jump_path: 跳转路径
示例：
{{
    "type": "push",
    "title": "推送标题",
    "content": "推送内容",
    "datetime": "2025-03-15 14:30:00",
    "source": "应用名称",
    "push_status": "未读",
    "jump_path": "路径"
}}
''',
            'note': '''
字段格式：
- type: 固定 "note"
- title: 笔记标题
- content: 笔记内容
- datetime: 格式 "YYYY-MM-DD HH:MM:SS"，年份为 2025
示例：
{{
    "type": "note",
    "title": "笔记标题",
    "content": "笔记内容",
    "datetime": "2025-03-15 14:30:00"
}}
''',
            'calendar': '''
字段格式：
- type: 固定 "calendar"
- title: 日程标题
- description: 详细描述
- start_time: 格式 "YYYY-MM-DD HH:MM:SS"，年份为 2025
- end_time: 格式 "YYYY-MM-DD HH:MM:SS"，年份为 2025，必须不早于 start_time
- datetime: 格式 "YYYY-MM-DD HH:MM:SS"，年份为 2025
示例：
{{
    "type": "calendar",
    "title": "日程标题",
    "description": "详细描述",
    "start_time": "2025-03-15 14:00:00",
    "end_time": "2025-03-15 15:00:00",
    "datetime": "2025-03-15 14:30:00"
}}
''',
            'agent_chat': '''
字段格式：
- type: 固定 "agent_chat"
- date: 格式 "YYYY-MM-DD"，年份为 2025
- conversation: 对话对象，包含 turn 1 和 turn 2
  - turn 1: 第一轮对话，包含 user 和 assistant
    - user: 包含 action 和 content 字段
    - assistant: 包含 action 和 content 字段
  - turn 2: 第二轮对话（可选），格式同 turn 1
  - action 可选值：topic query, need inference, need confirmation, solution discussion
示例：
{{
    "type": "agent_chat",
    "date": "2025-03-15",
    "conversation": {{
        "turn 1": {{
            "user": {{
                "action": "topic query",
                "content": "用户的问题"
            }},
            "assistant": {{
                "action": "need inference",
                "content": "AI 的回复"
            }}
        }},
        "turn 2": {{
            "user": {{
                "action": "need confirmation",
                "content": "用户的确认"
            }},
            "assistant": {{
                "action": "solution discussion",
                "content": "AI 的解答"
            }}
        }}
    }}
}}
'''
        }
        return type_specs.get(operation_type, "")

    def _fix_single_format(self, invalid_op: Dict, error_reason: str, operation_type: str,
                            original_event: Dict[str, Any]) -> Dict:
        """
        调用 LLM 修正单条格式错误的数据

        Args:
            invalid_op: 格式错误的数据
            error_reason: 错误原因
            operation_type: 操作类型
            original_event: 原始事件数据

        Returns:
            修正后的数据，如果修正失败返回 None
        """
        event_info = json.dumps(original_event, ensure_ascii=False, indent=2)
        type_spec = self._get_type_spec(operation_type)

        fix_prompt = f"""
作为数据修正专家，请修正以下 {operation_type} 类型数据的格式错误。

【错误原因】
{error_reason}

【原始事件】
{event_info}

【正确格式】
{type_spec}

【待修正数据】
{json.dumps(invalid_op, ensure_ascii=False, indent=2)}

【修正要求】
1. 仅修正格式问题，不要大幅改变数据的核心内容
2. 确保所有必填字段存在且格式正确
3. datetime 相关字段年份必须为 2025
4. 字段取值必须在允许范围内
5. 只返回修正后的 JSON 对象，不要其他说明文字

请直接输出修正后的 JSON：
"""
        result = llm_call_j(fix_prompt)

        try:
            start_idx = result.find('{')
            end_idx = result.rfind('}') + 1
            if start_idx != -1 and end_idx != -1:
                fixed_op = json.loads(result[start_idx:end_idx])
                # 设置必填字段
                event_id_str = str(original_event.get('event_id', '0') or '0')
                fixed_op['daily_event_id'] = event_id_str
                fixed_op['event_id'] = []
                if 'phone_id' in fixed_op:
                    del fixed_op['phone_id']
                # 清理多余字段
                allowed_fields = self.ALLOWED_FIELDS.get(operation_type, set())
                if allowed_fields:
                    extra_fields = [k for k in fixed_op.keys() if k not in allowed_fields]
                    for extra_field in extra_fields:
                        del fixed_op[extra_field]
                return fixed_op
        except Exception as e:
            print(f"[PhoneOperationGenerator] 修正解析失败: {e}")

        return None

    def _parse_result(self, result: str, operation_type: str, original_event: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        解析 LLM 返回结果
        
        Args:
            result: LLM 返回的文本
            operation_type: 操作类型
            original_event: 原始事件数据，用于设置 daily_event_id
            
        Returns:
            解析后的操作数据列表
        """
        try:
            # 查找 JSON 数组
            start_idx = result.find('[')
            end_idx = result.rfind(']') + 1
            
            if start_idx != -1 and end_idx != -1:
                operations = json.loads(result[start_idx:end_idx])
                
                # 获取原始事件的 id（转换为字符串）
                event_id_value = original_event.get('event_id', '0')
                event_id_str = str(event_id_value) if event_id_value else '0'
                
                # 验证和规范化
                validated_ops = []
                allowed_fields = self.ALLOWED_FIELDS.get(operation_type, set())
                for i, op in enumerate(operations):
                    if isinstance(op, dict):
                        # 确保必需字段存在
                        if 'type' not in op:
                            op['type'] = operation_type

                        # **强制设置** daily_event_id 和 event_id，保障正确性
                        op['daily_event_id'] = event_id_str
                        op['event_id'] = []

                        # 移除 phone_id 如果存在
                        if 'phone_id' in op:
                            del op['phone_id']

                        # 清理多余字段，只保留允许的字段
                        if allowed_fields:
                            extra_fields = [k for k in op.keys() if k not in allowed_fields]
                            for extra_field in extra_fields:
                                del op[extra_field]

                        validated_ops.append(op)
                
                print(f"[PhoneOperationGenerator] 成功生成 {len(validated_ops)} 条{operation_type}数据")
                print(f"  - daily_event_id 已设置为：{event_id_str}")
                return validated_ops
            else:
                print(f"[PhoneOperationGenerator] 未找到有效的 JSON 数组")
                return []
                
        except Exception as e:
            print(f"[PhoneOperationGenerator] 解析失败：{e}")
            return []
    
    def generate_for_question(self,
                              question_data: Dict[str, Any],
                              search_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        为整个问题生成所需的手机操作数据
        
        Args:
            question_data: 问题数据（包含 required_events_id, evidence 等）
            search_result: 搜索结果
            
        Returns:
            所有需要的手机操作数据
        """
        all_operations = []
        
        # 获取需要用到的事件
        events = search_result.get('events', [])
        required_ids = question_data.get('required_events_id', [])
        
        # 过滤相关事件
        relevant_events = [
            evt for evt in events 
            if str(evt.get('event_id', '')) in required_ids or str(evt.get('id', '')) in required_ids
        ]
        
        # 如果没有指定事件 ID，使用所有事件
        if not relevant_events:
            relevant_events = events[:3]  # 最多使用 3 个事件
        
        # 为每个事件生成手机操作
        for event in relevant_events:
            # 确定需要生成的操作类型
            event_type = event.get('type', '')
            
            # 基于事件类型推断需要的手机操作
            operations_to_generate = self._infer_operation_types(event_type)
            
            # 生成每种类型的操作
            for op_type in operations_to_generate:
                operations = self.generate(
                    operation_type=op_type,
                    original_event=event,
                    question=question_data.get('question', ''),
                    generation_hint=f"基于{event_type}事件生成{op_type}数据，用于回答问题"
                )
                all_operations.extend(operations)
        
        return all_operations
    
    def _infer_operation_types(self, event_type: str) -> List[str]:
        """
        根据事件类型推断需要的手机操作类型
        
        Args:
            event_type: 事件类型
            
        Returns:
            需要生成的操作类型列表
        """
        # 简单的映射规则，可以根据实际情况调整
        mapping = {
            '会议': ['calendar', 'sms', 'call'],
            '电话': ['call'],
            '健身': ['calendar', 'gallery', 'note'],
            '日程': ['calendar', 'note'],
            '社交': ['sms', 'call', 'gallery'],
            '工作': ['calendar', 'sms', 'note'],
            '学习': ['calendar', 'note'],
            '医疗': ['calendar', 'sms'],
            '购物': ['sms', 'gallery'],
            '旅行': ['calendar', 'gallery', 'note']
        }
        
        # 默认返回
        default_ops = ['sms', 'calendar']
        
        # 查找匹配的类型
        for key, ops in mapping.items():
            if key in event_type:
                return ops
        
        return default_ops
