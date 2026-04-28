"""
推送通知操作生成器模块
负责生成手机推送通知数据
"""

import json
import random
from typing import List, Dict
from src.lifebench.utils.llm_call import llm_call, llm_call_j


class PushOperationGenerator:
    """
    推送通知操作生成器
    根据事件信息生成推送通知数据
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
    
    def validate_and_fix_push_data(self, data: Dict, all_daily_events: List[Dict], user_name: str) -> tuple:
        """
        校验推送数据合理性并修正
        
        Args:
            data: 单条推送数据
            all_daily_events: 当天所有事件列表（用于判断是否为合理的噪声事件）
            user_name: 用户姓名（用于检测是否出现本人姓名）
            
        Returns:
            (is_valid: bool, fixed_data: Dict or None, error_message: str)
            - is_valid: 是否通过校验
            - fixed_data: 如果 LLM 修正了数据，返回修正后的数据；否则为 None
            - error_message: 错误信息
        """
        try:
            format_example = '''**推送类型 (type="push") 修正示例：**
{
  "type": "push",
  "event_id": "1",
  "title": "支付宝：外卖支付成功提醒",
  "content": "【支付宝】支付成功，订单#8765 金额 58 元，账单已同步至我的账单",
  "datetime": "2025-10-01 12:03:00",
  "source": "支付宝",
  "push_status": "未读",
  "jump_path": "支付宝→我的账单→订单#8765"
}'''
            
            analysis_prompt = f"""请分析以下手机推送数据的合理性，检查是否存在以下问题：

### 检查项
1. **必填字段缺失**：是否缺少 event_id、type、title、content、datetime、source、push_status、jump_path
2. **时间逻辑错误**：datetime 年份是否为 2025 年
3. **内容不合理**：title 和 content 是否贴合 APP 话术，是否合理
4. **格式错误**：数据是否符合输出格式示例

### 重要说明
- **event_id 含义**：手机数据的 event_id 字段指的是其对应的当日事件的具体事件 ID，多个推送可以对应同一个事件（如支付成功提醒、订单备餐提醒等都可以对应同一个订单事件），因此 event_id 重复是正常的，不应视为错误
- **随机推送说明**：一些推送数据会在随机时间推送，与用户当前在做什么无关（如个性化推荐、系统通知、新闻推送等），这类信息基本不会有错误，只要内容合理即可视为正常
- 该推送数据可能是与当日事件无明显关联的**噪声事件**（如系统通知、个性化推荐等）
- 如果是噪声事件，只要不与当日事件冲突、符合基本生活逻辑即可视为合理
- 只有当数据存在明显的逻辑错误、格式错误才需要修正

### 用户信息
- 用户姓名：{user_name}

### 当天所有事件（用于判断是否冲突）
{json.dumps(all_daily_events, ensure_ascii=False, indent=2)}

### 待分析的推送数据
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
- fixed_data 必须是完整的推送数据对象，包含所有必填字段
- datetime 格式必须为 "YYYY-MM-DD HH:MM:SS"，年份必须为 2025
- push_status 只能为 "已读"、"未读"、"已删除" 之一
- 不要添加任何额外文本、注释或代码块标记
"""
            
            result = llm_call_j(analysis_prompt)
            result = self.remove_json_wrapper(result, "object")
            analysis_result = json.loads(result)
            
            if analysis_result.get("is_valid", False):
                return True, None, ""
            
            if not analysis_result.get("is_valid", True) and "fixed_data" in analysis_result:
                fixed_data = analysis_result["fixed_data"]
                issues = analysis_result.get("issues", [])
                print(f"  LLM 检测到问题: {issues}")
                format_valid, format_error = self._validate_format_only(fixed_data)
                if format_valid:
                    return True, fixed_data, ""
                else:
                    return False, None, f"LLM 修正后格式仍错误: {format_error}"
            
            return False, None, f"LLM 检测到合理性问题但未提供修正: {analysis_result.get('issues', [])}"
            
        except Exception as e:
            return False, None, f"LLM 合理性分析异常: {str(e)}"
    
    def _validate_format_only(self, data: Dict) -> tuple:
        """
        仅校验推送数据格式（不涉及合理性），并删除多余字段
        
        Args:
            data: 单条推送数据
            
        Returns:
            (is_valid: bool, error_message: str)
        """
        try:
            required_fields = [
                "event_id", "type", "title", "content", "datetime",
                "source", "push_status", "jump_path"
            ]
            missing_fields = [f for f in required_fields if f not in data]
            if missing_fields:
                return False, f"推送数据缺少必填字段: {missing_fields}"
            
            # 删除多余字段
            extra_fields = [k for k in data.keys() if k not in required_fields]
            for field in extra_fields:
                del data[field]
            
            from datetime import datetime
            try:
                dt = datetime.strptime(data["datetime"], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return False, f"datetime 格式错误: {data['datetime']}，应为 'YYYY-MM-DD HH:MM:SS'"
            
            if dt.year != 2025:
                return False, f"年份不是2025年: {data['datetime']}，实际年份为 {dt.year}"
            
            valid_status = ["已读", "未读", "已删除"]
            if data.get("push_status") not in valid_status:
                return False, f"push_status 取值错误: {data.get('push_status')}，应为 {valid_status}"
            
            return True, ""
            
        except Exception as e:
            return False, f"格式校验异常: {str(e)}"
    
    def phone_gen_push(self, date, contact, file_path, extool=None):
        """
        生成指定日期的推送通知数据

        Args:
            date: 日期
            contact: 联系人列表
            file_path: 文件路径
            extool: Data_extract 实例，如果为 None 则从模块导入

        Returns:
            生成的推送通知数据列表
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
            请基于用户提供的{{当日事件}}、{{个人画像}}和{{短信数据}}，逐事件挖掘动作细节，分析推送场景匹配度及生成概率，仅输出概率建模结果，不涉及具体内容生成。核心规则：严格去重（与短信重复不生成）、场景精准匹配动作、控制推送频率。

### 一、概率建模核心规则
#### 1. 事件动作挖掘与推送场景映射
- **第一步：动作提取**：从事件中提取具体行为动作（支付/预定/下单/改签/退款/收藏等），无明确动作的事件标记"无核心动作"
- **第二步：场景匹配**（动作→场景→来源 APP，严格对应）：
  | 核心动作       | 推送场景                          | 关联来源 APP 示例                  |
  |----------------|-----------------------------------|-----------------------------------|
  | 支付           | 支付成功提醒、账单同步            | 支付宝、微信支付                  |
  | 预定           | 预定成功、时间临近、变更提醒      | 美团、携程、12306                 |
  | 下单           | 订单确认、发货/备餐、物流/送达    | 淘宝、京东、美团外卖              |
  | 改签/退款      | 改签成功、退款到账                | 12306、携程                       |
  | 收藏/关注      | 内容更新、对象上新                | 抖音、小红书、淘宝                |
  | 无核心动作     | 个性化推荐、系统常规通知          | 基于画像的 APP、系统模块          |

#### 2. 推送场景概率分配（总和 100%，按优先级排序）
- 事件动作关联场景：80%（优先匹配动作对应的核心场景）
- 关键节点提醒场景：15%（仅事件含明确时间时生成，如会议前 30 分钟）
- 个性化推荐场景：25%（基于个人画像行为偏好/爱好/信息/人群，如股民→雪球）
- 系统常规通知场景：1%（仅电量/存储/健康等系统触发）

#### 3. 生成约束规则
- **去重**：与短信数据内容重复的推送场景概率强制 0%
- **频率控制**：同一 APP 同一事件 24 小时内最多生成 2 个推送场景（优先保留动作关联和关键节点）
- **时间适配**：按 APP 类型约束推送时间窗口（工作类 9:00-18:00/娱乐类 12:00-14:00&19:00-22:00 等），不符合窗口的场景概率 -30%（最低 0%）
- **社交排除**：微信/QQ 等社交平台通信类推送概率强制 0%

### 二、输出字段要求（仅保留以下 7 个字段，无额外内容）
每个事件必须包含：
- event_id：严格沿用原事件唯一标识，系统通知填"0"
- event_name：完整保留原事件名称
- core_action：提取的核心动作（多个用"/"分隔，无则填"无核心动作"）
- push_scene_prob：字典格式，key=场景名称，value=百分比字符串（如 {{"支付成功提醒":"60%","个性化推荐":"20%"}}）
- source_app_candidate：数组格式，推荐匹配的来源 APP（如 ["支付宝","美团"]）
- is_duplicate_with_sms：是否与短信重复（是/否）
- reasoning：简洁说明（含 3 点：1. 动作提取依据；2. 场景概率分配原因；3. 约束规则应用情况）

### 三、输出格式要求
仅输出 JSON 数组，无任何注释、额外文本或代码块标记。**格式强约束**："reasoning"的内容中不要生成任何引号，名称强调使用【】来进行。示例：
[
  {{
    "event_id": "1",
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
    "reasoning": "1. 动作提取：事件含"下单""支付"行为；2. 概率分配：动作关联场景 60%、关键节点 15%、个性化 20%、系统 5%；3. 约束应用：无短信重复，美团外卖在生活类时间窗口内"
  }},
  {{
    "event_id": "2",
    "event_name": "微信好友聊天",
    "core_action": "无核心动作",
    "push_scene_prob": {{}},
    "source_app_candidate": [],
    "is_duplicate_with_sms": "否",
    "reasoning": "1. 动作提取：仅社交聊天，无推送关联动作；2. 概率分配：社交平台推送强制 0%；3. 约束应用：符合社交排除规则"
  }}
]

请基于<当日事件>：{daily_events}、<个人画像>：{persona}、<短信数据>：{sms_data}，严格按上述要求逐事件输出概率建模结果。
            '''
        prompt = template.format(daily_events=res, persona=extool.persona, sms_data="")
        print(prompt)
        a = llm_call_j(prompt)
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
        请基于用户提供的{{概率建模结果}}、{{当日事件}}、{{个人画像}}和{{短信数据}}，生成结构化的手机推送数据，严格遵循字段规则、生成原则和输出格式，确保数据真实贴合 APP 话术、字段完整无缺失、JSON 解析无错误。

### 零、日期约束（**最高优先级**）
- **当前关注的事件日期：{date}**
- **生成原则**：请严格基于此日期进行数据生成，所有时间字段（start_time、end_time、datetime）的日期部分应以此日期为基准
- **跨天处理**：对于某些需跨天的数据（如长途出行、跨夜会议等），可以在此日期的基础上往前或往后选择合理的相邻日期，但必须严格围绕此日期展开，不得偏离过远


### 一、核心生成原则
1. **严格绑定建模结果**：仅生成概率建模中筛选的推送场景，按概率从高到低选择（同一事件最多生成 2 个场景，总数无上限但需符合频率约束）
2. **去重与话术适配**：
   - 与短信数据重复的内容坚决不生成
   - 推送标题/内容需贴合来源 APP 真实话术风格（如支付宝带"【支付宝】"前缀，美团强调"预定码/订单号"）
3. **细节与画像匹配**：
   - 内容必须包含事件具体信息（金额/时间/订单号/预定码等），禁止泛化
   - 个性化推荐需匹配个人画像偏好（如宝妈→宝宝树育儿提醒，股民→雪球行情）
   - 系统通知需符合触发条件（电量≤20%/存储≤10%）
4. **格式强约束**：推送内容中不要生成任何引号，名称强调使用【】来进行。
5. **content 简洁原则**：推送内容精炼直接，准确反映核心信息，去除无关冗余细节和修饰词

### 二、字段规则（含约束说明，缺一不可）
需包含且仅包含以下字段：
- event_id：复用概率建模结果中的 event_id，系统通知填"0"
- type：固定"push"
- title：含"来源 APP+ 动作/场景 + 关键对象"，例："支付宝：外卖支付成功提醒""美团：餐厅预定成功通知"
- content：**简洁明确，准确反映核心信息**，贴合 APP 话术，含动作结果 + 核心信息（格式参考示例），双引号需转义
- datetime：按场景时间约束生成：
  - 支付/下单/预定动作：完成后 1-3 分钟内
  - 关键节点提醒：事件前 30 分钟 -1 小时
  - 系统通知：电量/存储触发时（随机生成合理时间）
  - 其他场景：对应 APP 时间窗口内（工作类 9:00-18:00 等）
- source：具体来源 APP/系统模块（从建模结果 source_app_candidate 中选择）
- push_status：已读/未读/已删除（未读占比≤40%，随机分配）
- jump_path：APP 内跳转路径，例："支付宝→我的账单→订单#8765""美团→我的→预定订单"
### 三、待生成清单（基于概率建模筛选，仅生成以下内容）
{instruct}

### 四、输出格式要求
仅输出 JSON 数组，无任何额外文本、注释或代码块标记。示例：
[
  {{
    "type": "push",
    "event_id": "1",
    "title": "支付宝：外卖支付成功提醒",
    "content": "【支付宝】支付成功，订单#8765 金额 58 元，账单已同步至我的账单",
    "datetime": "2023-10-01 12:03:00",
    "source": "支付宝",
    "push_status": "未读",
    "jump_path": "支付宝→我的账单→订单#8765"
  }},
  {{
    "type": "push",
    "event_id": "1",
    "title": "美团外卖：订单备餐提醒",
    "content": "【美团外卖】订单#8765 备餐中，预计 12:30 送达，骑手张师傅 138****1234",
    "datetime": "2023-10-01 12:10:00",
    "source": "美团外卖",
    "push_status": "未读",
    "jump_path": "美团外卖→我的订单→订单#8765"
  }},
  {{
    "type": "push",
    "event_id": "0",
    "title": "系统：电量低提醒",
    "content": "【系统通知】手机电量低于 20%，请及时充电",
    "datetime": "2023-10-01 16:45:00",
    "source": "系统电池管理",
    "push_status": "已读",
    "jump_path": "设置→电池"
  }}
]

请基于<概率建模结果>：{instruct}、<当日事件>：{event}、<个人画像>：{persona}、<短信数据>：{sms_data}，严格按上述要求生成推送数据。
        '''
        prompt = template.format(instruct=instruction, event=res, persona=extool.persona, sms_data='' , date=date)
        # 保存 daily_event 数据，避免被后续 LLM 返回结果覆盖
        daily_events_backup = res
        res = llm_call_j(prompt)
        print(res)
        res = self.remove_json_wrapper(res, 'array')
        data = json.loads(res)
        
        # ========== 新增：合理性校验与格式校验环节 ==========
        print(f"\n开始推送数据校验，共 {len(data)} 条数据...")
        
        user_name = extool.persona.get("name", "") or extool.persona.get("姓名", "")
        if not user_name:
            print("警告：未找到用户姓名，跳过本人姓名检测")
        
        valid_data = []
        need_format_check = []
        
        for idx, item in enumerate(data):
            is_valid, fixed_data, error_msg = self.validate_and_fix_push_data(
                item, daily_events_backup, user_name
            )
            
            if is_valid:
                if fixed_data:
                    valid_data.append(fixed_data)
                    print(f"  [合理性修正成功] 索引 {idx}, event_id={item.get('event_id')}")
                else:
                    valid_data.append(item)
                format_valid, format_error = self._validate_format_only(item if not fixed_data else fixed_data)
                if format_valid:
                    need_format_check.append(item if not fixed_data else fixed_data)
                else:
                    print(f"  [格式错误] 索引 {idx}, event_id={item.get('event_id')}: {format_error}")
            else:
                print(f"  [合理性错误] 索引 {idx}, event_id={item.get('event_id')}: {error_msg}，抛弃该数据")
        
        print(f"\n合理性校验结果：通过 {len(need_format_check)} 条，抛弃 {len(data) - len(need_format_check)} 条")
        
        final_valid = []
        for item in need_format_check:
            format_valid, format_error = self._validate_format_only(item)
            if format_valid:
                final_valid.append(item)
            else:
                print(f"  [格式校验失败] event_id={item.get('event_id')}: {format_error}，抛弃该数据")
        
        c += final_valid
        print(f"\n最终保留 {len(c)} 条推送数据\n")
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
