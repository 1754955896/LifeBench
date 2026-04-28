"""
相册操作生成器模块
负责生成照片和图片数据
"""

import json
import random
from typing import List, Dict
from src.lifebench.utils.llm_call import llm_call, llm_call_j


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

### 重要说明
- **重点分析**：输入的手机数据的 event_id 所指示的事件为对应的场景，应重点分析该事件与相册数据的匹配度
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
    
    def phone_gen_gallery(self, date, contact, file_path, extool=None):
        """
        生成照片数据的主方法

        Args:
            date: 日期
            contact: 联系人列表
            file_path: 文件路径
            extool: Data_extract 实例，如果为 None 则从模块导入

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

        template = '''
        请基于用户提供的{{当日事件}}和{{个人画像}}，逐事件分析拍照行为的生成概率、场景细分及图片数量，仅输出概率建模结果，不涉及任何具体内容生成。核心规则：拍照场景与概率严格匹配事件类型，单个事件生成 1-3 张图片，避免过度生成。

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
- 无视觉价值事件（如"电话沟通""线上会议"）：所有场景概率 0%，图片数量 0 张
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
        prompt = template.format(daily_events=res, persona=extool.persona)
        print(prompt)
        a = llm_call_j(prompt)
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
        res = llm_call_j(prompt)
        print(res)
        res = self.remove_json_wrapper(res, "array")
        data = json.loads(res)
        
        # ========== 新增：合理性校验与格式校验环节 ==========
        print(f"\n开始相册数据校验，共 {len(data)} 条数据...")
        
        # 获取用户姓名（从 persona 中提取）
        user_name = extool.persona.get("name", "") or extool.persona.get("姓名", "")
        if not user_name:
            print("警告：未找到用户姓名，跳过本人姓名检测")
        
        # 第一轮：合理性校验 + LLM 修正
        valid_data = []
        need_format_check = []  # 需要进一步格式校验的数据
        
        for idx, item in enumerate(data):
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
        
        print(f"\n合理性校验结果：通过 {len(need_format_check)} 条，抛弃 {len(data) - len(need_format_check)} 条")
        
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
