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
    
    def __init__(self):
        self.operation_types = ['sms', 'call', 'calendar', 'note', 'gallery', 'contact']
    
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
        
        return operations
    
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
        
        # 根据事件类型提供特定的生成指导
        event_type_guidance = self._get_event_type_guidance(event_type, operation_type)
        
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
        
        # 添加类型特定的字段说明
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
            "faceRecognition": ["人物姓名"],
            "imageTag": ["标签 1", "标签 2"],
            "ocrText": "OCR 识别文字",
            "shoot_mode": "拍摄模式",
            "image_size": "图片尺寸",
            "summarized_info": "照片内容总结",
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
            "summarized_info": "推送内容总结",
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
            "summarized_info": "笔记内容总结",
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
            "summarized_info": "日程内容总结",
            "daily_event_id": "输入事件的 id",
            "event_id": []
        }}
        """
        }
        
        prompt += type_specs.get(operation_type, "").format(event_type=event_type)
        
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
                event_id_value = original_event.get('event_id', '')
                if event_id_value is not None:
                    event_id_str = str(event_id_value)
                else:
                    event_id_str = ''
                
                # 验证和规范化
                validated_ops = []
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
