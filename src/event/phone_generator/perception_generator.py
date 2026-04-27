"""
感知数据生成器模块
负责从事件中提取用户的感知数据（如景点浏览、购物、出行等）
"""

import json
from typing import List, Dict, Any
from utils.llm_call import llm_call_skip, llm_call_j


class PerceptionDataGenerator:
    """
    感知数据生成器
    从事件列表中提取属于指定类别的事件作为感知数据
    """
    
    def __init__(self, schema: List[str] = None, profile: Dict = None):
        """
        初始化感知数据生成器
        
        Args:
            schema: 事件类别列表，用于判断事件类型。如果不提供，将使用默认的事件类型列表。
            profile: 用户画像数据，包含用户的基本信息，如常居地等。
        """
        # 默认事件类型列表，按类别分类
        default_schema = {
            "移动状态": [
                "行走", "跑步", "停留"
            ],
            "通行状态": [
                "乘飞机", "乘火车", "乘地铁", "开车", "乘车", "乘交通工具"
            ],
            "运动状态": [
                "户外步行", "室内步行", "徒步", "爬楼", "椭圆机", "操场赛跑", "越野跑", "跑酷", "游泳", "健身锻炼", "骑行", "室内骑行", "BMX 自行车", "武术", "舞蹈", "芭蕾舞", "肚皮舞", "爵士舞", "拉丁舞", "街舞", "羽毛球", "棒球", "足球", "篮球", "轮滑", "健美操", "漫步机", "射箭", "射击射箭", "沙滩足球", "沙滩排球", "冬季两项", "搏击操", "保龄球", "拳击", "闭气测试", "闭气训练", "蹦极", "皮划艇", "核心训练", "板球", "越野滑雪", "Crossfit", "冰壶", "飞镖", "自由潜水", "躲避球", "龙舟", "漂流", "椭圆机", "击剑", "自由搏击", "自由训练", "飞盘", "功能性训练", "门球", "打高尔夫", "高尔夫场地模式", "高尔夫练习场模式", "手球", "HIIT", "曲棍球", "骑马", "马术", "呼啦圈", "冰球", "跳绳", "空手道", "剑道", "放风筝", "登山", "障碍赛", "开放水域游泳", "定向越野", "笼式网球", "跳伞", "双杠", "体能训练", "普拉提", "广场舞", "台球", "泳池游泳", "赛车", "攀岩", "划船机", "赛艇", "橄榄球", "帆船", "水肺潜水", "体感运动", "藤球", "毽球", "单杠", "滑板", "滑冰", "溜冰", "滑雪橇", "滑雪", "单板滑雪", "雪地摩托", "垒球", "动感单车", "壁球", "力量训练", "桨板冲浪", "冲浪", "秋千", "乒乓球", "跆拳道", "太极拳", "网球", "铁人三项", "拔河", "排球", "瑜伽"
            ],
            "出行与娱乐": [
                "出发", "返程", "城市切换","景点浏览", "购物", "逛街", "城市漫游", "出海游船", "露营", "度假村放松", "酒店休息", "就餐", "游玩主题乐园", "参观动物园", "参观博物馆", "参观美术馆", "参观海洋馆", "看演唱会", "看话剧", "看音乐剧", "看展览", "看脱口秀", "看相声", "看音乐会", "看音乐节", "看戏曲", "看电竞赛事", "看舞蹈", "看体育赛事", "看魔术", "看电影", "看亲子演出", "划船", "按摩足疗", "洗浴汗蒸", "密室逃脱", "游戏厅", "网吧", "采摘农家乐", "撸宠", "K 歌", "酒吧", "轰趴", "剧本杀", "电子游戏", "做 SPA", "桌游", "茶馆棋牌", "DIY 手工"
            ],
            "出差": [
                "办公", "会议研讨", "出发", "返程", "城市切换"
            ],
            "探亲": [
                "节假日回乡", "居家拜访", "扫墓"
            ]
        }
        
        # 如果用户提供了 schema，则使用用户提供的，否则使用默认的
        self.schema = schema if schema is not None else default_schema
        
        # 保存用户画像数据
        self.profile = profile
        
        # 为了保持兼容性，将分类后的 schema 转换为扁平列表
        self.flat_schema = []
        if isinstance(self.schema, dict):
            for category in self.schema.values():
                self.flat_schema.extend(category)
    
    def generate_perception_data(self, date: str, extool) -> List[Dict]:
        """
        生成感知数据
        
        Args:
            date: 日期，格式为 YYYY-MM-DD
            extool: Data_extract 实例，提供事件数据
            
        Returns:
            感知数据列表，每个条目包含 type, event_type, event_id, date, time 等字段
        """
        # 获取当日事件
        daily_events = extool.filter_by_date(date)
        
        # 准备所有事件数据
        valid_events = []
        for event in daily_events:
            # 直接使用event的所有信息
            valid_events.append(event)
        
        if not valid_events:
            return []
        
        # 只选择移动状态、通行状态和运动状态的事件类型
        filtered_categories = []
        if isinstance(self.schema, dict):
            # 如果 schema 是分类结构，只选择移动状态、通行状态和运动状态
            if "移动状态" in self.schema:
                filtered_categories.extend(self.schema["移动状态"])
            if "通行状态" in self.schema:
                filtered_categories.extend(self.schema["通行状态"])
            if "运动状态" in self.schema:
                filtered_categories.extend(self.schema["运动状态"])
        else:
            # 如果是扁平列表，使用所有类别（保持兼容性）
            filtered_categories = self.schema
        
        # 构建 prompt 让 LLM 从事件列表中提取属于移动状态、通行状态和运动状态的事件
        prompt = f"""
        你是一位事件分类专家，请根据以下事件信息和事件类别列表，识别并提取当日生活中的个人所处状态，包括运动状态、移动状态和通行状态。请按照以下思考过程进行分析：
        
        思考过程：
        1. 首先，通读所有事件信息，识别出当天实际发生的动作，排除规划、准备或回忆的内容
        2. 对于每个实际发生的动作，分析其属于哪种状态类型：
           - 运动状态：是否涉及体育锻炼或身体活动
           - 移动状态：是否在同一地点内的活动（包括静止）
           - 通行状态：是否在不同地点之间转换并使用交通工具
        3. 确定每个状态的时间范围，包括开始时间和结束时间
        4. 提取事件的相关信息，如事件ID、发生地点等
        5. 根据事件类别列表，为每个状态选择最合适的类别名称
        6. 检查是否存在连续的时间段且位于同一个建筑/位置的移动状态数据（除了时间，其他内容基本不变），如果有，将它们合并为一个时间跨度包含可合并数据的数据
        7. 按照要求的格式生成输出
        
        状态识别说明：
        1. 运动状态：当用户在进行体育锻炼或身体活动时的状态
           示例类别：跑步、游泳、健身锻炼、骑行、羽毛球、篮球、瑜伽等
        2. 移动状态：用户在同一地点内的活动状态，包括静止状态
           示例类别：行走、户外步行、室内步行、广义静止、绝对静止、相对静止、停留等
        3. 通行状态：用户在不同地点之间转换时使用交通工具的状态
           示例类别：乘飞机、乘火车、乘地铁、开车、乘车、上班通勤、下班通勤等
        
        重要要求：
        - 只提取当天实际发生的动作，而不是规划或准备做的事情
        - 例如："今天去公园跑步"属于实际动作，应提取；"计划明天去公园跑步"属于规划，不应提取
        - 例如："今天开会讨论项目"属于实际动作，但不属于移动、通行或运动状态，不应提取
        - 只有当天事件实际执行了属于移动状态、通行状态或运动状态的动作，才进行提取
        - 对于静止状态，需要分析用户某段时间是否处于静止状态
        - 对于通行状态，需要分析用户在地点转换时的状态
        - 合并规则：如果多个状态事件在时间上连续（前一个事件的结束时间与后一个事件的开始时间相邻）且除了时间外其他内容基本相同，则将它们合并为一个事件，时间跨度为从第一个事件的开始时间到最后一个事件的结束时间
        
        事件类别列表：{json.dumps(filtered_categories, ensure_ascii=False)}
        
        输出要求：
        1. 仅输出一个 JSON 数组，包含所有符合条件的事件
        2. 每个事件必须包含以下字段：
           - event_id: 事件 ID，与输入保持一致
           - dataname: 事件类型，必须从给定的事件类别列表中选择
           - inTimestamp: 开始时间，格式为 YYYY-MM-DD HH:MM:SS
           - outTimestamp: 结束时间，格式为 YYYY-MM-DD HH:MM:SS
           - location: 事件发生地点，格式为 JSON 对象：{{"country":"", "province":"", "city":"", "district":"", "streetName":"", "streetNumber":"", "POI":""}}，对于地址的填写，填充可填写字段（如位于地铁，可不填街道或区只填写POI）
           - date: 事件日期，格式为 YYYY-MM-DD
        3. 只返回 JSON 数据，不要包含任何解释或其他文本
        4. 确保每个事件的 dataname 字段都是事件类别列表中的有效类别
        5. 仅包含那些确实属于移动状态、通行状态或运动状态且实际发生的事件，不要为每个事件都分配类别
        6. 如果某个事件不属于移动状态、通行状态或运动状态，或者只是规划/准备/回忆而不是实际执行的动作，请不要将其包含在输出中
        7. 时间格式：将 date 和 time 组合成完整的日期时间，格式为 YYYY-MM-DD HH:MM:SS
        
        输出示例：
        [
            {{"event_id": "1", "dataname": "跑步", "inTimestamp": "2025-01-01 09:00:00", "outTimestamp": "2025-01-01 10:00:00", "location": {{"country": "中国", "province": "江苏省", "city": "徐州市", "district": "云龙区", "streetName": "云台山路", "streetNumber": "", "POI": "云台山公园"}}, "date": "2025-01-01"}},
            {{"event_id": "2", "dataname": "乘地铁", "inTimestamp": "2025-01-01 14:00:00", "outTimestamp": "2025-01-01 14:30:00", "location": {{"country": "中国", "province": "江苏省", "city": "徐州市", "district": "", "streetName": "", "streetNumber": "", "POI": "地铁2号线"}}, "date": "2025-01-01"}},
            {{"event_id": "3", "dataname": "广义静止", "inTimestamp": "2025-01-01 12:00:00", "outTimestamp": "2025-01-01 13:00:00", "location": {{"country": "中国", "province": "江苏省", "city": "徐州市", "district": "鼓楼区", "streetName": "淮海路", "streetNumber": "123号", "POI": "坛小福餐厅"}}, "date": "2025-01-01"}}
        ]
        
        事件信息：
        {json.dumps(valid_events, ensure_ascii=False, indent=2)}
        """
        
        try:
            # 使用 llm_call_skip 避免影响共享对话历史
            response = llm_call_j(prompt).strip()
            print(f"LLM 返回的响应：{response}")
            
            # 移除 JSON 包装
            response = self.remove_json_wrapper(response, 'array')
            
            # 解析 JSON 响应
            perception_data = json.loads(response)
            
            # 验证返回的数据格式和内容
            if not isinstance(perception_data, list):
                print("LLM 返回的不是 JSON 数组，返回空列表")
                return []
            
            # 过滤确保所有事件类型都在 schema 中且包含必要字段，并确保新字段存在
            filtered_data = []
            for item in perception_data:
                if isinstance(item, dict) and 'dataname' in item and 'event_id' in item and 'date' in item and 'inTimestamp' in item and 'outTimestamp' in item and 'location' in item and item['dataname'] in filtered_categories:
                    # 设置 type 字段为'perception'
                    item['type'] = 'perception'
                    filtered_data.append(item)

            # 调用 generate_perception_data_with_levels 生成1级事件和2级事件数据
            level_data = self.generate_perception_data_with_levels(date, extool, profile=self.profile)
            # 合并结果
            filtered_data.extend(level_data)

            return filtered_data
            
        except Exception as e:
            print(f"生成感知数据时出错：{str(e)}")
            return []
    
    def generate_perception_data_with_levels(self, start_date: str, extool, max_days: int = 30, profile: Dict = None) -> List[Dict]:
        """
        生成感知数据，包含1级事件和2级事件的处理
        先用一轮prompt识别是否开始了一级事件，然后迭代每日数据，添加2级事件，直到判断给出1级事件已经结束
        
        Args:
            start_date: 开始日期，格式为 YYYY-MM-DD
            extool: Data_extract 实例，提供事件数据
            max_days: 最大迭代天数，默认30天
            profile: 用户画像数据，包含用户的基本信息，如常居地等
            
        Returns:
            感知数据列表，包含1级事件和2级事件
        """
        import datetime
        
        # 转换开始日期为datetime对象
        current_date = datetime.datetime.strptime(start_date, "%Y-%m-%d")
        
        # 存储所有感知数据
        all_perception_data = []
        # 存储当前活跃的1级事件
        current_first_level_event = None
        
        # 第一步：识别是否开始了1级事件
        start_date_str = current_date.strftime("%Y-%m-%d")
        start_events = extool.filter_by_date(start_date_str)
        
        # 准备开始日期的事件数据
        start_valid_events = []
        for event in start_events:
            start_valid_events.append(event)
        
        # 构建识别1级事件的prompt
        # 提取用户画像中的常居地信息
        user_location = ""
        if profile and 'home_address' in profile:
            home_address = profile['home_address']
            if isinstance(home_address, dict):
                # 构建完整的地址信息
                location_parts = []
                if 'country' in home_address and home_address['country']:
                    location_parts.append(home_address['country'])
                if 'province' in home_address and home_address['province']:
                    location_parts.append(home_address['province'])
                if 'city' in home_address and home_address['city']:
                    location_parts.append(home_address['city'])
                if 'district' in home_address and home_address['district']:
                    location_parts.append(home_address['district'])
                user_location = " ".join(location_parts)
            else:
                user_location = str(home_address)
        
        start_prompt = f"""
        你是一位事件分类专家，请根据以下事件信息和用户画像数据，判断当天是否开始了1级事件（市内出游、跨市出游、出差、探亲）。
        
        用户画像数据：
        - 常居地：{user_location}
        
        思考过程：
        1. 通读所有事件信息，识别出当天实际发生的动作，排除规划、准备或回忆的内容
        2. 检查是否有1级事件的开始（出发），包括：
           - 市内出游（CityTravel）：在同一城市内的游玩活动
           - 跨市出游（Journey）：跨越城市的游玩活动，或出现城市切换的情况
           - 出差（BusinessTravel）：因工作原因的出行
           - 探亲（FamilyReunion）：因探亲访友的出行
        3. 分析城市切换情况：
           - 使用用户画像中的常居地信息来判断城市切换的性质
           - 如果城市切换后的目的地城市为常居地，则代表这次城市切换是返程，不是1级事件的开始
           - 只有当城市切换的目的地不是常居地时，才可能是1级事件的开始
           - 只有1级事件的开始才要识别，所以当遇到出行城市切换时，要仔细判断是开始还是结束。
        4. 如果识别到1级事件，提取相关信息并确定开始时间
        5. 按照要求的格式生成输出
        
        事件类别列表：{json.dumps(self.flat_schema, ensure_ascii=False)}
        
        输出要求：
        1. 仅输出一个 JSON 对象，包含以下字段：
           - hasFirstLevelEvent: 布尔值，表示是否识别到1级事件
           - firstLevelEvent: 如果识别到1级事件，包含事件详情；否则为null
        2. 1级事件详情必须包含以下字段：
           - dataname: 事件类型，必须从给定的事件类别列表中选择
           - inTimestamp: 开始时间，格式为 YYYY-MM-DD HH:MM:SS
           - inDate: 开始日期，格式为 YYYY-MM-DD
           - description: 一级场景的描述
        3. 其他字段暂时为空
        4. 只返回 JSON 数据，不要包含任何解释或其他文本
        5. 确保 dataname 字段是事件类别列表中的有效类别
        6. 仅包含那些确实属于1级事件且实际发生的事件
        7. 如果某个事件不属于1级事件，或者只是规划/准备/回忆而不是实际执行的动作，请不要将其包含在输出中
        8. 时间格式：将 date 和 time 组合成完整的日期时间，格式为 YYYY-MM-DD HH:MM:SS
        9. 请注意分别是否跨城市(设计地点上城市的变动，或者乘火车飞机等交通)，还是在城市内的出游。
        
        输出示例：
        {{{{
            "hasFirstLevelEvent": true,
            "firstLevelEvent": {{
                "dataname": "城市旅游", 
                "inTimestamp": "2025-01-02 08:00:00", 
                "inDate": "2025-01-02", 
                "description": "用户开始了一天的城市旅游活动"
            }}
        }}}}
        
        事件信息：
        {json.dumps(start_valid_events, ensure_ascii=False, indent=2)}
        """
        
        try:
            # 使用 llm_call_j 调用LLM
            start_response = llm_call_j(start_prompt).strip()
            print(f"识别1级事件的响应：{start_response}")
            
            # 移除 JSON 包装
            start_response = self.remove_json_wrapper(start_response, 'object')
            
            # 解析 JSON 响应
            start_result = json.loads(start_response)
            
            # 检查是否识别到1级事件
            if start_result.get('hasFirstLevelEvent', False):
                current_first_level_event = start_result.get('firstLevelEvent')
                if current_first_level_event:
                    # 确保必要字段存在
                    if 'dataname' in current_first_level_event and 'inTimestamp' in current_first_level_event and 'inDate' in current_first_level_event and 'description' in current_first_level_event:
                        # 初始化其他字段
                        current_first_level_event['sceneList'] = []
                        # 设置 type 字段为'perception'
                        current_first_level_event['type'] = 'perception'
                        print(f"识别到1级事件：{current_first_level_event['dataname']}")
        except Exception as e:
            print(f"识别1级事件时出错：{str(e)}")
        
        # 如果没有识别到1级事件，直接返回
        if not current_first_level_event:
            print("未识别到1级事件，返回空列表")
            return []
        
        # 第二步：迭代每日数据，添加2级事件，直到1级事件结束
        for day in range(1, max_days):
            if day > 1:
                current_date += datetime.timedelta(days=1)
            date_str = current_date.strftime("%Y-%m-%d")
            print(f"处理日期：{date_str}")
            
            # 获取当日事件
            daily_events = extool.filter_by_date(date_str)
            
            # 准备当日事件数据
            valid_events = []
            for event in daily_events:
                valid_events.append(event)
            
            if not valid_events:
                # 如果当日没有事件，直接跳过添加2级事件的步骤
                # 后续会统一执行check_prompt来判断1级事件是否结束
                pass
            
            # 确定1级事件类型对应的2级事件类别
            first_level_type = current_first_level_event.get('dataname', '')
            secondary_categories = []
            
            # 首先使用出行与娱乐类别作为基础
            secondary_categories = self.schema.get('出行与娱乐', [])
            
            # 根据1级事件类型添加相应的增量数据
            if first_level_type in ['出差', 'BusinessTravel']:
                secondary_categories.extend(self.schema.get('出差', []))
            elif first_level_type in ['探亲', 'FamilyReunion']:
                secondary_categories.extend(self.schema.get('探亲', []))
            
            # 构建添加2级事件的prompt
            add_scene_prompt = f"""
            你是一位事件分类专家，请根据以下事件信息，为当前活跃的1级事件添加当天的2级事件。
            
            思考过程：
            1. 通读所有事件信息，识别出当天实际发生的动作，排除规划、准备或回忆的内容
            2. 分析哪些动作属于当前1级事件的具体活动（2级事件）
            3. 确定每个2级事件的时间范围，包括开始时间和结束时间
            4. 提取事件的相关信息，如事件ID、发生地点等
            5. 根据事件类别列表，为每个2级事件选择最合适的类别名称
            6. 按照要求的格式生成输出
            
            当前活跃的1级事件：
            {json.dumps(current_first_level_event, ensure_ascii=False, indent=2)}
            
            2级事件类别：{json.dumps(secondary_categories, ensure_ascii=False)}
            其中"出发", "返程", "城市切换"一定要识别到，出发是从初始地点到目标地点，返程是从目标地点回到初始地点，旅行过程中返回临时居住地不是返程。城市切换是指从一个城市到另一个城市的行为，对于在某一城市内部的移动不算。
            输出要求：
            1. 仅输出一个 JSON 对象，包含以下字段：
               - sceneList: 当天属于该1级事件的2级事件数组
            2. 2级事件必须包含以下字段：
               - event_id: 事件 ID，与输入保持一致
               - dataname: 事件类型，必须从给定的2级事件类别中选择
               - inTimestamp: 开始时间，格式为 YYYY-MM-DD HH:MM:SS
               - outTimestamp: 结束时间，格式为 YYYY-MM-DD HH:MM:SS
               - location: 事件发生地点，格式为 JSON 对象：{{"country":"", "province":"", "city":"", "district":"", "streetName":"", "streetNumber":"", "POI":""}}，对于地址的填写，填充可填写字段（如位于地铁，可不填街道或区只填写POI）
               - date: 事件日期，格式为 YYYY-MM-DD
            3. 只返回 JSON 数据，不要包含任何解释或其他文本
            4. 确保每个事件的 dataname 字段都是给定的2级事件类别中的有效类别
            5. 仅包含那些确实属于2级事件且实际发生的事件，不要为每个事件都分配类别
            6. 如果某个事件不属于2级事件，或者只是规划/准备/回忆而不是实际执行的动作，请不要将其包含在输出中
            7. 时间格式：将 date 和 time 组合成完整的日期时间，格式为 YYYY-MM-DD HH:MM:SS
            8.请仔细分析事件是否严格属于某个2级事件类别，宁愿忽略，也不要将事件错误分配到不正确类别。
            
            输出示例：
            {{
                "sceneList": [
                    {{
                        "event_id": "7", 
                        "dataname": "购物", 
                        "inTimestamp": "2025-01-03 10:00:00", 
                        "outTimestamp": "2025-01-03 12:00:00", 
                        "location": {{
                            "country": "中国",
                            "province": "江苏省",
                            "city": "徐州市",
                            "district": "泉山区",
                            "streetName": "彭城路",
                            "streetNumber": "56号",
                            "POI": "购物中心"
                        }}, 
                        "date": "2025-01-03"
                    }}, 
                    {{
                        "event_id": "8", 
                        "dataname": "就餐", 
                        "inTimestamp": "2025-01-03 12:30:00", 
                        "outTimestamp": "2025-01-03 13:30:00", 
                        "location": {{
                            "country": "中国",
                            "province": "江苏省",
                            "city": "徐州市",
                            "district": "泉山区",
                            "streetName": "淮海路",
                            "streetNumber": "88号",
                            "POI": "餐厅"
                        }}, 
                        "date": "2025-01-03"
                    }}
                ]
            }}
            
            事件信息：
            {json.dumps(valid_events, ensure_ascii=False, indent=2)}
            """
            
            try:
                # 使用 llm_call_j 调用LLM
                response = llm_call_j(add_scene_prompt).strip()
                print(f"添加2级事件的响应：{response}")
                
                # 移除 JSON 包装
                response = self.remove_json_wrapper(response, 'object')
                
                # 解析 JSON 响应
                result = json.loads(response)
                
                # 添加2级事件到1级事件的sceneList
                if 'sceneList' in result:
                    new_scenes = result['sceneList']
                    if isinstance(new_scenes, list):
                        current_first_level_event['sceneList'].extend(new_scenes)
                
            except Exception as e:
                print(f"添加2级事件时出错：{str(e)}")
            
            # 无论当天是否有事件，都检查1级事件是否结束
            check_prompt = f"""
            请判断以下1级事件是否已经结束，并总结到目前为止的主要经历、位置和进度。
            
            1级事件：
            {json.dumps(current_first_level_event, ensure_ascii=False, indent=2)}
            
            思考指导：
            1. 首先识别1级事件的类型（出差、探亲、市内出游、跨市出游等），并明确其出发地和目标地
            2. 分析事件的时间线，包括开始时间、持续时间和当前进度
            3. 关注事件描述中的关键信息，如交通方式、住宿地点、活动安排等
            4. 特别注意与"返回"相关的描述，判断是否是返回常居地（正式结束旅行）还是临时居住地（旅行还未结束）
            5. 综合考虑事件的性质和合理持续时间，判断是否应该结束
            
            判断标准：
            1. 如果事件描述中明确提到返回（返回自己的常居地，而非临时居住地）等关键词，则认为事件结束
            2. 如果事件已经持续了合理的时间（例如出差通常不超过1个月，旅游通常不超过2周），且没有明确的延续计划，则认为事件结束
            3. 如果没有明确信息，假设事件仍在进行中
            
            输出要求：
            1. 仅输出一个 JSON 对象，包含以下字段：
               - isEnded: 布尔值，表示事件是否结束
               - summary: 字符串，总结到目前为止该一级事件的主要经历、位置和进度
               - endTime: 字符串，表示事件结束的时间，格式为 YYYY-MM-DD HH:MM:SS（如果事件结束则输出）
            2. 总结内容应包括：
               - 事件的主要活动和经历
               - 涉及的主要位置
               - 事件的当前进度
            3. 只返回 JSON 数据，不要包含任何解释或其他文本
            
            输出示例：
            {{
                "isEnded": true, 
                "summary": "用户已完成城市旅游，游览了云龙山和博物馆，品尝了当地特色美食，购物活动已完成，于当天下午5点返回常居地",
                "endTime": "2025-01-02 17:00:00"
            }}
            
            另一个示例：
            {{
                "isEnded": false, 
                "summary": "用户已进行了2天的城市旅游，主要游览了云龙山和博物馆，品尝了当地特色美食，购物活动已完成，旅游行程已完成约60%",
                "endTime": null
            }}
            """
            
            try:
                response = llm_call_j(check_prompt).strip()
                print(f"检查1级事件结束状态的响应：{response}")
                
                # 移除 JSON 包装
                response = self.remove_json_wrapper(response, 'object')
                
                # 解析 JSON 响应
                result = json.loads(response)
                
                # 提取总结信息并更新事件
                if 'summary' in result:
                    current_first_level_event['summary'] = result['summary']
                
                # 检查事件是否结束
                if result.get('isEnded', False):
                    # 标记事件结束
                    end_time = result.get('endTime', f"{date_str} 23:59:59")
                    current_first_level_event['outTimestamp'] = end_time
                    # 从结束时间中提取日期作为outDate
                    out_date = end_time.split(' ')[0]
                    current_first_level_event['outDate'] = out_date
                    # 将事件添加到感知数据中
                    all_perception_data.append(current_first_level_event)
                    print(f"1级事件已结束，结束时间：{end_time}")
                    return all_perception_data
            except Exception as e:
                print(f"检查1级事件结束状态时出错：{str(e)}")
        
        # 如果达到最大天数，标记1级事件结束
        if current_first_level_event:
            # 为未结束的事件设置结束时间为最后处理日期的当天结束
            end_date_str = current_date.strftime('%Y-%m-%d')
            current_first_level_event['outTimestamp'] = f"{end_date_str} 23:59:59"
            current_first_level_event['outDate'] = end_date_str
            all_perception_data.append(current_first_level_event)
        
        return all_perception_data
    
    @staticmethod
    def remove_json_wrapper(s: str, json_type: str = 'array') -> str:
        """
        处理字符串，移除 JSON 包装
        
        Args:
            s: 输入字符串
            json_type: JSON 类型，'object'对应{}，'array'对应[]，默认为'array'
            
        Returns:
            处理后的字符串，若不存在有效 JSON 则返回原字符串
        """
        # 1. 先移除开头的 ```json 和结尾的 ```标记
        import re
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