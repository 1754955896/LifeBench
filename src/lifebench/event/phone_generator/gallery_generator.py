"""
相册操作生成器模块
负责生成照片和图片数据
"""

import json
import random
from typing import List, Dict
from src.lifebench.utils.llm_call import llm_call, llm_call_j,llm_call_reason_j


class GalleryOperationGenerator:
    """
    相册操作生成器
    根据事件信息生成照片数据
    """
    
    def __init__(self, random_seed: int = 42):
        """初始化生成器（设置随机种子确保可复现）"""
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
            events = json.loads(core_json_str)
            return events
        except json.JSONDecodeError as e:
            print(f"JSON 解析失败：位置{e.pos}，原因{e.msg}")
            return []
        except Exception as e:
            print(f"解析异常：{str(e)}")
            return []
    
    def validate_and_fix_gallery_data(self, data: Dict, all_daily_events: List[Dict], user_name: str) -> tuple:
        """
        校验相册数据合理性并修正
        
        Args:
            data: 单条相册数据
            all_daily_events: 当天所有事件列表（用于判断是否为合理的噪声事件）
            user_name: 用户姓名（用于检测是否出现本人姓名）
            
        Returns:
            (is_valid: bool, fixed_data: Dict or None, error_message: str)
            - is_valid: 是否通过校验
            - fixed_data: 如果 LLM 修正了数据，返回修正后的数据；否则为 None
            - error_message: 错误信息
        """
        try:
            # 根据待校验数据的 type 动态提供对应的格式示例
            format_example = '''**照片类型 (type="photo") 修正示例：**
{
  "event_id": "1",
  "type": "photo",
  "caption": "李华西湖断桥打卡，身后湖面游船雷峰塔",
  "title": "IMG_20251001_143025",
  "datetime": "2025-10-01 14:30:25",
  "location": {
    "province": "浙江省",
    "city": "杭州市",
    "district": "西湖区",
    "streetName": "北山街",
    "streetNumber": "XX 号",
    "poi": "西湖断桥景区"
  },
  "faceRecognition": ["李华"],
  "imageTag": ["西湖", "断桥", "游船", "雷峰塔"],
  "ocrText": "西湖断桥 - 国家 5A 级旅游景区",
  "shoot_mode": "正常拍照",
  "image_size": "4032×3024"
}'''
            
            analysis_prompt = f"""请分析以下手机相册数据的合理性，检查是否存在以下问题：

### 检查项
1. **必填字段缺失**：是否缺少 event_id、type、caption、title、datetime、location、faceRecognition、imageTag、ocrText、shoot_mode、image_size
2. **字段名错误**：是否有拼写错误或字段名不符合要求
3. **时间逻辑错误**：datetime 年份是否为 2025 年
4. **地点信息错误**：location 是否包含完整的层级信息（province、city、district、streetName、streetNumber、poi）
5. **event_id 格式错误**：event_id 是否为数字字符串（如 "1"、"123"），不能是非数字字符串（如 "event_001"、"daily_20250228"），如果格式错误必须修正
6. **内容对应错误**：相册数据的 caption 内容是否与对应原事件的 description/内容相关或匹配，如果完全不相关（如事件是"医院查房"但拍摄了"海边风景"）则需要修正

### 重要说明
- **event_id 修正规则**（重点）：
  - event_id 必须是数字字符串，如 "1"、"123"
  - **禁止**使用非数字字符串，如 "event_001"、"daily_20250228"、"event_id" 等
  - 必须从当天事件的 event_id 列表中选择真实存在的数字字符串
  - 如果当前 event_id 格式错误，必须修正为有效的数字字符串
- **重点分析**：输入的手机数据的 event_id 所指示的事件为对应的场景，应重点分析该事件与相册数据的匹配度，caption 内容是否与原事件描述相关
- **允许合理扩展**：基于 event_id 对应的事件场景，允许合理的扩展生成（如事件是“西湖游览”，可以拍摄断桥、游船、雷峰塔等相关场景）
- 该相册数据可能是与当日事件无明显关联的**噪声事件**（如随手拍的风景、无关的物品等）
- 如果是噪声事件，只要不与当日事件冲突、符合基本生活逻辑即可视为合理
- 只有当数据存在明显的逻辑错误（如位于长沙却拍摄了武汉的照片，2025年拍摄了2024年的照片）、格式错误才需要修正
- 注意不允许时间延迟，发生的事情必须被立刻拍照记录
- **不检查内容格式**：不需要检查 title 格式、image_size 取值、shoot_mode 取值、ocrText 内容等细节格式问题，这些由后续的格式校验环节处理

### 当天所有事件（请判断相册数据对应的场景是否可能发送冲突）
{json.dumps(all_daily_events, ensure_ascii=False, indent=2)}

### 待分析的相册数据
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
- **event_id 必须是有效的数字字符串**，如 "1"、"123"，不能是 "event_001" 等
- fixed_data 必须是完整的相册数据对象，包含所有必填字段
- 如果修正了数据，必须确保修正后的数据符合原始事件的背景和逻辑
- datetime 格式必须为 "YYYY-MM-DD HH:MM:SS"，年份必须为 2025
- title 格式必须为 "IMG_年月日_时分秒"，与 datetime 一致
- image_size 只能为 "4032×3024"、"3024×4032"、"2048×1536"、"1536×2048" 之一
- shoot_mode 只能为 "正常拍照"、"夜景"、"人像"、"微距" 之一
- location 必须包含所有嵌套字段
- 不要添加任何额外文本、注释或代码块标记
"""
            
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
    
    def _validate_format_only(self, data: Dict) -> tuple:
        """
        仅校验相册数据格式（不涉及合理性），并删除多余字段
        
        Args:
            data: 单条相册数据
            
        Returns:
            (is_valid: bool, error_message: str)
        """
        try:
            # 1. 校验必填字段是否存在，并删除多余字段
            required_fields = [
                "event_id", "type", "caption", "title", "datetime", "location",
                "faceRecognition", "imageTag", "ocrText", "shoot_mode", "image_size"
            ]
            missing_fields = [f for f in required_fields if f not in data]
            if missing_fields:
                return False, f"相册数据缺少必填字段: {missing_fields}"
            
            # 删除多余字段
            extra_fields = [k for k in data.keys() if k not in required_fields]
            for field in extra_fields:
                del data[field]

            # 1.5. 校验 event_id 格式（必须是数字字符串或数字）
            event_id = data.get("event_id")
            if event_id is None:
                return False, "event_id 字段不存在"
            if isinstance(event_id, str):
                if not event_id.isdigit():
                    return False, f"event_id 不是有效的数字字符串: '{event_id}'"
            elif isinstance(event_id, int):
                if event_id <= 0:
                    return False, f"event_id 不是有效的正整数: {event_id}"
            else:
                return False, f"event_id 类型错误: {type(event_id).__name__}"

            # 2. 校验 location 嵌套字段
            location_required = ["province", "city", "district", "streetName", "streetNumber", "poi"]
            if isinstance(data.get("location"), dict):
                missing_location = [f for f in location_required if f not in data["location"]]
                if missing_location:
                    return False, f"location 缺少必填字段: {missing_location}"
                # 删除 location 中的多余字段
                extra_location = [k for k in data["location"].keys() if k not in location_required]
                for field in extra_location:
                    del data["location"][field]
            else:
                return False, "location 字段格式错误，应为字典"
            
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
    
    def generate_main_scenario_photos(self, date, contact, file_path, extool=None):
        """
        生成主要场景照片的主方法
        在phone_gen_gallery的第一轮LLM调用之前调用

        Args:
            date: 日期
            contact: 联系人列表
            file_path: 文件路径
            extool: Data_extract 实例，如果为 None 则从模块导入

        Returns:
            生成的主要场景照片数据列表
        """
        if extool is None:
            from src.lifebench.event.phone_data_gen import extool

        # 过滤当日事件
        res1 = extool.filter_by_date(date)
        res = []
        for i in range(len(res1)):
            if "-" in res1[i]['event_id']:
                continue
            res.append(res1[i])

        template = '''
请基于<当日事件>和<个人画像>，分析并提取必定会产生照片的重要场景，并进行重要性分级。

### 一、必定产生照片的场景类型
以下类型的事件通常一定会产生照片：
1. **旅行事件**：旅行、出游、景点打卡等
2. **聚餐事件**：约会、聚餐、宴会、生日会等（注意日常饮食吃饭不被纳入）
3. **重要节假日**：春节、中秋节、国庆节、情人节等重要节日
4. **纪念节点**：生日、纪念日、毕业典礼、婚礼等重要个人节点
5. **重大会议/活动**：发布会、颁奖典礼、重要会议等
6. **摄影相关活动**：摄影爱好者参与的外拍活动等
7. **不寻常，难遇到的事件**：如特殊活动、异常事件等
请考虑事件的情景，如果用户过于忙或处于没有手机的状态是不能拍照的。

### 二、重要性分级
根据事件的规模和独特性分为三个等级：

| 等级 | 照片数量 | 适用场景 |
|------|----------|----------|
| 1级 | 2-4张 | 不重要、不独特或较小的事件，如普通聚餐、小型聚会等 |
| 2级 | 3-6张 | 中等重要性的事件，如正式聚餐、一般旅行游览等 |
| 3级 | 5-10张 | 重要且独特的事件，如大型旅行、重要纪念日、毕业典礼等 |

### 三、分析规则
1. 逐事件分析，判断该事件是否属于"必定产生照片"的场景类型
2. 如果属于，进一步判断其重要性等级
3. 重要节假日、婚礼、毕业典礼等大型活动一般为3级
4. 普通旅行游览一般为2级
5. 小型聚餐、朋友聚会等一般为1级
6. 结合个人画像中的兴趣、习惯等进行判断
7. **重要说明**：每日最多提取3个重要场景；允许一个重要场景也没有（即当日无必定产生照片的事件）；过于日常、无拍照需求的事件不提取（如居家活动、常规通勤等）

### 四、输出要求
输出JSON数组，包含event_id和importance_level字段，无任何额外文本。如果无重要场景，输出空数组[]。示例：
[
  {{"event_id": "1", "importance_level": 3}},
  {{"event_id": "3", "importance_level": 2}},
  {{"event_id": "5", "importance_level": 1}}
]
]

请基于<当日事件>：{daily_events}、<个人画像>：{persona}，输出必定会产生照片的事件及其重要性等级。
        '''
        prompt = template.format(daily_events=res, persona=extool.persona)
        print(prompt)
        a = llm_call_reason_j(prompt)
        print(a)
        a = self.remove_json_wrapper(a, "array")
        main_scenario_events = json.loads(a)

        if not main_scenario_events:
            print("未找到必定产生照片的主要场景事件")
            return []

        # 获取需要生成主要场景照片的event_id列表
        main_event_ids = [item['event_id'] for item in main_scenario_events]
        # 建立event_id到importance_level的映射
        importance_map = {item['event_id']: item.get('importance_level', 2) for item in main_scenario_events}
        print(f"主要场景事件event_ids: {main_event_ids},重要性等级: {importance_map}")

        # 筛选出主要场景事件
        main_events = [e for e in res if e['event_id'] in main_event_ids]
        if not main_events:
            print("未找到匹配的主要场景事件")
            return []

        # 逐个事件生成照片数据
        all_photos = []
        for event in main_events:
            event_id = event['event_id']
            event_name = event.get('event_name', event.get('description', '未知事件'))
            importance_level = importance_map.get(event_id, 2)
            # 根据重要性等级确定照片数量范围
            photo_count_map = {1: (1, 4), 2: (2, 6), 3: (4, 8)}
            min_photos, max_photos = photo_count_map.get(importance_level, (3, 6))
            print(f"\n为事件 {event_id} ({event_name}) 生成主要场景照片，重要性等级: {importance_level}, 生成 {min_photos}-{max_photos} 张...")

            template = '''
你是一个摄影顾问。请基于<单个事件>和<个人画像>，生成符合真实生活场景的照片数据。

### 日期约束
- **当前关注的事件日期：{date}**
- 所有时间字段的日期部分应以此日期为基准

### 现实摄影场景指导原则
生成的照片必须是**个人在实际事件中真正可能拍摄的内容**，事件描述可能不够细致，你可以合理推测额外的场景：

**合理的个人摄影场景（具体且实际，不是抽象概念）：**
- 出行记录：沿途街景、交通工具、目的地外观/入口牌匾
- 用餐场景：餐桌食物（俯拍）、餐厅环境
- 购物/买菜：商品陈列货架、购物小票
- 户外运动：运动手表数据截图、跑步路线截图、完赛证书
- 亲子/家庭：孩子活动、家人合影
- 差旅/出行：机票/车票/登机牌（屏幕上或纸质）、机场/车站环境、窗外风景
- 演唱会/活动：场馆外观、排队入场、与同伴的合影（不能拍舞台）、场外海报
- 博物馆/景点：展品外观、场馆外观、参观者视角的展览
- 购物支付：手机支付成功截图
- 日常生活中：工作台/书桌、宠物、阳台植物、手工/绘画作品


**不可能被个人拍摄的内容（禁止生成）：**
- 他人隐私场景
- 监控/官方视角的内容

### 生成要求
1. 生成{min_photos}-{max_photos} 张照片，以事件时间线为顺序
2. 按时间顺序排列，每张照片时间略有不同（递增）
3. 地点真实性：基于个人画像的常居地/常去地生成真实层级化地点
4. caption：简洁准确描述照片内容，**使用普通观众的视角和口吻**

### 字段规则
- event_id：严格沿用原事件唯一标识
- type：固定"photo"
- caption：具体准确描述照片内容，**仅描述实际可见的环境/物品/动作**，禁止描述心情、感受、情绪等抽象内容（如"感动"、"开心"、"激动"等词汇不应出现）
- title：格式"IMG_yyyyMMdd_HHmmss"，与 datetime 对应
- datetime：与事件时间一致或合理延后，格式"YYYY-MM-DD HH:MM:SS"
- location：嵌套对象（province、city、district、streetName、streetNumber、poi）
- faceRecognition：联系人姓名数组/"无"/"XX 若干"/"于晓薇"
- imageTag：2-4 个关键词
- ocrText：仅屏幕截图（手表/手机）、导视牌/门票/海报场景填写真实文字，其他填"无"
- shoot_mode：正常拍照、夜景、人像、微距、屏幕截图（任选一种）
- image_size：4032×3024、3024×4032、2048×1536、1536×2048（任选一种）

### 单个事件
{event}

### 个人画像
{persona}

### 输出示例
[
  {{
    "event_id": "1",
    "type": "photo",
    "title": "IMG_20250316_064500",
    "caption": "清晨湿漉漉的街道，天空灰蒙，行人稀少",
    "datetime": "2025-03-16 06:45:00",
    "location": {{
      "province": "香港特别行政区",
      "city": "香港",
      "district": "九龙城区",
      "streetName": "太子道西",
      "streetNumber": "XX号",
      "poi": "太子道西街景"
    }},
    "faceRecognition": ["无"],
    "imageTag": ["街景", "清晨", "雨天", "香港"],
    "ocrText": "无",
    "shoot_mode": "正常拍照",
    "image_size": "4032×3024"
  }},
  {{
    "event_id": "1",
    "type": "photo",
    "title": "IMG_20250316_074500",
    "caption": "跑步手表屏幕显示恢复性慢跑数据：3公里，配速6分35秒",
    "datetime": "2025-03-16 07:45:00",
    "location": {{
      "province": "香港特别行政区",
      "city": "香港",
      "district": "九龙城区",
      "streetName": "常盛街",
      "streetNumber": "XX号",
      "poi": "东何文田休憩公园"
    }},
    "faceRecognition": ["无"],
    "imageTag": ["跑步", "手表", "数据", "运动"],
    "ocrText": "3公里 | 6:35/km | 175步/分",
    "shoot_mode": "屏幕截图",
    "image_size": "3024×4032"
  }}
]

### 输出要求
仅输出 JSON 数组，无任何额外文本。每个元素对应 1 张图片，按 datetime 升序排列。
'''
            prompt = template.format(event=json.dumps(event, ensure_ascii=False),
                                    persona=json.dumps(extool.persona, ensure_ascii=False),
                                    date=date,
                                    min_photos=min_photos,
                                    max_photos=max_photos)
            res = llm_call_reason_j(prompt)
            print(res)
            res = self.remove_json_wrapper(res, "array")
            photos = json.loads(res)
            print(f"事件 {event_id} 生成 {len(photos)} 张照片")
            all_photos.extend(photos)

        print(f"\n主要场景共生成 {len(all_photos)} 条原始数据")
        return all_photos

    def phone_gen_gallery(self, date, contact, file_path, extool=None, enable_main_scenario_photos=False):
        """
        生成照片数据的主方法

        Args:
            date: 日期
            contact: 联系人列表
            file_path: 文件路径
            extool: Data_extract 实例，如果为 None 则从模块导入
            enable_main_scenario_photos: 是否启用主要场景照片生成，只有为 True 时才调用 main_scenario_photos

        Returns:
            生成的照片数据列表
        """
        if extool is None:
            from src.lifebench.event.phone_data_gen import extool

        c = []
        res1 = extool.filter_by_date(date)
        res = []
        for i in range(len(res1)):
            if "-" in res1[i]['event_id']:
                continue
            res.append(res1[i])
            print(res1[i]['event_id'])

        # 先调用主要场景生成方法，提取必定会产生照片的重要场景
        main_scenario_photos = []
        main_event_ids = set()
        if enable_main_scenario_photos:
            main_scenario_photos = self.generate_main_scenario_photos(date, contact, file_path, extool)
        # 记录已生成照片的事件ID集合
        main_event_ids = set(item['event_id'] for item in main_scenario_photos)
        print(f"主要场景已生成 {len(main_scenario_photos)} 条，涉及事件ID: {main_event_ids}")

        template = '''
        请基于用户提供的{{当日事件}}和{{个人画像}}，逐事件分析拍照行为的生成概率、场景细分及图片数量，仅输出概率建模结果，不涉及任何具体内容生成。核心规则：拍照场景与概率严格匹配事件类型，单个事件生成 1-3 张图片，避免过度生成。

### 重要说明
以下event_id对应的事件已在主要场景中生成照片，**不需要对这些事件进行概率建模**：
{excluded_event_ids}

### 一、概率建模核心规则
#### 1. 事件类型与拍照场景映射（基础概率作参考，可按画像微调±5%），若事件描述中明确指定拍照场景，则生成照片的概率为100%，且场景严格匹配事件描述。
| 事件类型 | 拍照场景（含基础概率） |
|----------|------------------------|
| 旅行事件 | 风景打卡 80%、人物合影 60%、美食记录 30%、导视牌/门票 15%、细节特写 20% |
| 会议事件 | PPT 截图 40%、参会人员 20%、会议纪要手写板 20%、会场环境 20% |
| 日常事件 | 美食 25%、宠物 20%、物品收纳 15%、街头风景 15%、文档扫描 25% |
其他类型可自行分配合理概率和场景

#### 2. 针对事件的图片可能数量概率进行分配，对于一些场景适应性调整：
- 0 张图片：当事件无视觉价值或用户可能不想拍照的事件 100%，一般日常场景可以为 50%-60%，动态调整。
- 1 张图片：用户有可能拍照时可以为 50%
- 2 张图片：事件场景丰富时，增加概率
- 3 张图片：仅旅行/重要会议等复杂事件增加对应概率
概率之和为 1
#### 3. 个人画像微调规则
- 兴趣适配：用户兴趣（如"美食爱好者"）对应场景概率 +5%（如日常事件"美食"场景从 25%→30%）
- 行为习惯："不爱拍照"人格所有场景概率 -10%；"摄影爱好者"所有场景概率 +10%（但不超过基础概率 +5% 上限）
- 常居地关联：无明确地点的事件，拍照场景默认关联用户常居地 POI（概率建模时无需体现具体地点，仅标记"需关联常居地"）

#### 4. 生成约束
- 非外出类事件（如"居家办公""独自学习"）：仅保留"文档扫描""物品收纳"场景，其他场景概率强制 0%
- 无视觉价值事件（如"电话沟通""线上会议"）：所有场景概率 0%，图片数量 0 张。
- 单个事件场景最多生成 3 张图片，不可超额

### 二、输出字段要求（仅保留以下 6 个字段，无额外内容）
每个事件必须包含：
- event_id：严格沿用原事件唯一标识，不添加额外文本
- event_name：完整保留原事件名称
- event_type：分类为"旅行事件""会议事件""日常事件""无视觉价值事件"
- photo_scene_prob：字典格式，key=场景名称，value=百分比字符串（如 {{"风景打卡":"35%","人物合影":"20%"}}）
- photo_count_prob：字典格式，key=图片数量（0/1/2/3），value=百分比字符串（如 {{"0":"10%","1":"50%","2":"30%","3":"10%"}}）
- reasoning：简洁说明（含 2 点：1. 场景概率分配依据；2. 数量概率分配依据）

### 三、输出格式要求
仅输出 JSON 数组，无任何注释、额外文本或代码块标记。示例：
[
  {{
    "event_id": "1",
    "event_name": "西湖游览",
    "event_type": "旅行事件",
    "photo_scene_prob": {{
      "风景打卡": "35%",
      "人物合影": "20%",
      "美食记录": "20%",
      "导视牌/门票": "15%",
      "细节特写": "10%"
    }},
    "photo_count_prob": {{
      "1": "30%",
      "2": "40%",
      "3": "30%"
    }},
    "reasoning": "1. 场景概率：用户兴趣为旅行摄影，风景打卡 +5%；2. 数量概率：旅行事件场景丰富，3 张图片概率提升至 20%"
  }},
  {{
    "event_id": "2",
    "event_name": "线上项目沟通会",
    "event_type": "无视觉价值事件",
    "photo_scene_prob": {{}},
    "photo_count_prob": {{"0":"100%","1":"0%","2":"0%","3":"0%"}},
    "reasoning": "1. 场景概率：线上会议无视觉价值，所有场景概率 0%；2. 数量概率：无拍照行为，图片数量 0 张"
  }}
]

请基于<当日事件>：{daily_events}、<个人画像>：{persona}，严格按上述要求逐事件输出概率建模结果。
        '''
        prompt = template.format(daily_events=res, persona=extool.persona, excluded_event_ids=main_event_ids)
        print(prompt)
        a = llm_call_reason_j(prompt)
        print(a)
        a = self.parse_llm_prob_json(a)

        def sample_from_distribution(distribution):
            """根据概率分布选择一个结果"""
            total = 0
            items = []
            cumulative = []
            
            for k, v in distribution.items():
                prob = int(v.strip('%')) / 100
                total += prob
                items.append(k)
                cumulative.append(total)
            
            if total > 0:
                for i in range(len(cumulative)):
                    cumulative[i] /= total
            
            r = random.random()
            for i, c in enumerate(cumulative):
                if r <= c:
                    return items[i]
            
            return items[0] if items else None

        instruction = ""

        for item in a:
            event_id = item['event_id']
            event_name = item['event_name']
            p1 = item['photo_count_prob']

            # 跳过已在主要场景中生成的事件
            if event_id in main_event_ids:
                print(f"事件 {event_id} ({event_name}) 已在主要场景中生成，跳过")
                continue

            selected_count = sample_from_distribution(p1)
            has_photo = selected_count != '0'

            if has_photo:
                instruction += f'''
--------------------------------------------------

                                                'event_id':'{event_id}',
                                                'event_name':'{event_name}',
                                            '''
                instruction += f''' 'photo_num':'{selected_count}',
                                '''
                instruction += f'''
                                photo_scene_prob':{item['photo_scene_prob']}
                                '''

        print(instruction)
        template = '''
    请基于用户提供的{{事件生成指令}}、{{当日事件}}、{{个人画像}}，生成结构化的手机图片/拍照数据，严格遵循字段规则、生成原则和输出格式，确保数据高保真、字段完整、逻辑自洽。

### 零、日期约束（**最高优先级**）
- **当前关注的事件日期：{date}**
- **生成原则**：请严格基于此日期进行数据生成，所有时间字段（start_time、end_time、datetime）的日期部分应以此日期为基准
- **跨天处理**：对于某些需跨天的数据（如长途出行、跨夜会议等），可以在此日期的基础上往前或往后选择合理的相邻日期，但必须严格围绕此日期展开，不得偏离过远


### 一、核心生成原则
1. 严格绑定事件生成指令：仅生成指定事件的拍照场景和图片数量，不新增场景或超额生成。
2. 地点真实性：无明确地点的事件，基于个人画像"常居地/常去地"生成真实层级化地点信息（省份→门牌号→POI）
3. **caption 简洁明确**：图片内容的总结，简洁准确反映事件核心信息，但又详细丰富，反映具体场景
4. 字段强约束：
   - caption：描述具体，内容简洁明确
   - title：严格遵循"IMG_年月日_时分秒"格式（与 datetime 一致）
   - imageTag：2-8 个关键词，精准贴合内容（场景 + 主体 + 动作 + 属性），不泛化
   - ocrText：仅导视牌/门票/海报/文档场景填写真实文字（含名称 + 时间/价格），其他场景填"无"
   - shoot_mode：人像模式必须关联 faceRecognition（非"无"），夜景/微距需贴合场景（如夜景→暗光环境）
   - image_size：仅支持"4032×3024""3024×4032""2048×1536""1536×2048"四种格式

### 二、字段规则（含嵌套字段，缺一不可）
需包含且仅包含以下字段：
- event_id：复用概率建模结果中的 event_id
- type：固定"photo"
- caption：简洁明确，准确反映事件核心信息，详细充实。
- title："IMG_年月日_时分秒"格式（如"IMG_20231001_143025"），与 datetime 完全一致
- datetime：与事件时间一致或相近（±1 小时内），格式"YYYY-MM-DD HH:MM:SS"
- location：嵌套对象（所有字段必填，无门牌号填"XX 号"）：
  - province：真实省份名称（如"浙江省"）
  - city：真实城市名称（如"杭州市"）
  - district：真实区县名称（如"西湖区"）
  - streetName：真实街道名称（如"北山街"）
  - streetNumber：门牌号（如"10 号"，无则填"XX 号"）
  - poi：真实 POI 名称（如"西湖断桥景区""三里屯太古里"）
- faceRecognition：联系人列表姓名数组/"无"/"XX 若干"（例：["李华","张明"]、"无"、"游客若干"）
- imageTag：2-4 个关键词（场景 + 主体 + 动作 + 属性），例："拿铁咖啡、玻璃吸管、木质桌面、下午茶"
- ocrText：图片中真实文字（门票/海报/导视牌含"名称 + 时间 + 价格"），无则填"无"
- shoot_mode：正常拍照/夜景/人像/微距（人像模式必须对应 faceRecognition 非"无"）
- image_size：四种格式之一（"4032×3024""3024×4032""2048×1536""1536×2048"）
### 三、待生成清单（事件生成指令，仅生成以下内容）
{instruct}

### 四、输出格式要求
仅输出 JSON 数组，无任何额外文本、注释或代码块标记。每个元素对应 1 张图片，按 datetime 升序排列。示例：
[
  {{ 
    "event_id": "1",
    "type": "photo",
    "caption": "李华在西湖断桥打卡，身后有湖面游船雷峰塔",
    "title": "IMG_20231001_143025",
    "datetime": "2023-10-01 14:30:25",
    "location": {{
      "province": "浙江省",
      "city": "杭州市",
      "district": "西湖区",
      "streetName": "北山街",
      "streetNumber": "XX 号",
      "poi": "西湖断桥景区"
    }},
    "faceRecognition": ["李华"],
    "imageTag": ["西湖", "断桥", "游船", "雷峰塔", "秋日", "湖面"],
    "ocrText": "西湖断桥 - 国家 5A 级旅游景区",
    "shoot_mode": "正常拍照",
    "image_size": "4032×3024"
  }},
  {{
    "event_id": "1",
    "type": "photo",
    "caption": "李华和张明西湖边一家餐厅品尝东坡肉，背景包括青花瓷碗木质餐桌，东坡肉米饭",
    "title": "IMG_20231001_181540",
    "datetime": "2023-10-01 18:15:40",
    "location": {{
      "province": "浙江省",
      "city": "杭州市",
      "district": "西湖区",
      "streetName": "孤山路",
      "streetNumber": "15 号",
      "poi": "楼外楼（孤山路店）"
    }},
    "faceRecognition": ["李华", "张明"],
    "imageTag": ["东坡肉", "青花瓷碗", "木质餐桌", "杭州美食", "聚餐"],
    "ocrText": "楼外楼 - 东坡肉 68 元/份 2023-10-01",
    "shoot_mode": "人像",
    "image_size": "3024×4032"
  }}
]

请基于<事件生成指令>：{instruct}、<当日事件>：{event}、<个人画像>：{persona}严格按上述要求生成图片数据。
    '''
        prompt = template.format(instruct=instruction, event=res, persona=extool.persona,date=date)
        # 保存 daily_event 数据，避免被后续 LLM 返回结果覆盖
        daily_events_backup = res
        res = llm_call_reason_j(prompt)
        print(res)
        res = self.remove_json_wrapper(res, "array")
        phone_gen_data = json.loads(res)

        # 合并两部分数据进行统一校验，过滤掉phone_gen_data中主场景已包含event_id的照片
        phone_gen_filtered = [item for item in phone_gen_data if item['event_id'] not in main_event_ids]
        print(f"过滤掉主场景重复照片 {len(phone_gen_data) - len(phone_gen_filtered)} 条")
        all_data = main_scenario_photos + phone_gen_filtered
        print(f"\n合并后共 {len(all_data)} 条数据，开始统一校验...")

        # ========== 统一校验环节 ==========
        print(f"\n开始相册数据校验，共 {len(all_data)} 条数据...")
        
        # 获取用户姓名（从 persona 中提取）
        user_name = extool.persona.get("name", "") or extool.persona.get("姓名", "")
        if not user_name:
            print("警告：未找到用户姓名，跳过本人姓名检测")
        
        # 第一轮：合理性校验 + LLM 修正
        valid_data = []
        need_format_check = []  # 需要进一步格式校验的数据
        
        for idx, item in enumerate(all_data):
            is_valid, fixed_data, error_msg = self.validate_and_fix_gallery_data(
                item, daily_events_backup, user_name
            )
            
            if is_valid:
                if fixed_data:
                    # LLM 修正了数据，使用修正后的数据
                    valid_data.append(fixed_data)
                    print(f"  [合理性修正成功] 索引 {idx}, event_id={item.get('event_id')}")
                else:
                    # 数据合理，无需修正
                    valid_data.append(item)
                # 对通过合理性校验的数据进行格式校验
                format_valid, format_error = self._validate_format_only(item if not fixed_data else fixed_data)
                if format_valid:
                    need_format_check.append(item if not fixed_data else fixed_data)
                else:
                    print(f"  [格式错误] 索引 {idx}, event_id={item.get('event_id')}: {format_error}")
            else:
                print(f"  [合理性错误] 索引 {idx}, event_id={item.get('event_id')}: {error_msg}，抛弃该数据")
        
        print(f"\n合理性校验结果：通过 {len(need_format_check)} 条，抛弃 {len(all_data) - len(need_format_check)} 条")
        
        # 第二轮：格式校验（年份、必填字段等）
        final_valid = []
        for item in need_format_check:
            format_valid, format_error = self._validate_format_only(item)
            if format_valid:
                final_valid.append(item)
            else:
                print(f"  [格式校验失败] event_id={item.get('event_id')}: {format_error}，抛弃该数据")
        
        c += final_valid
        print(f"\n最终保留 {len(c)} 条相册数据\n")
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
