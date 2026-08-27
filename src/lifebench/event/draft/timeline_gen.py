# -*- coding: utf-8 -*-
"""时间线生成类，负责处理时间线相关的操作"""
import json
import re
from datetime import timedelta
from src.lifebench.utils.llm_call import *
from src.lifebench.utils.date_utils import TimeSpec, DEFAULT_YEAR
from src.lifebench.event.templates.template_scheduler import *
import holidays  # 需安装：pip install holidays


class TimelineGen:
    def __init__(self, persona, file_path, spec: TimeSpec = None):
        """初始化时间线生成器

        参数:
            persona: 人物画像数据
            file_path: 基础数据路径
            spec: 时间范围规格（年份 + 模拟月数），默认 2025 全年
        """
        self.persona = persona
        self.file_path = file_path
        self.spec = spec or TimeSpec()
    
    def generate_initial_timeline(self):
        """
        生成初始时间线，包含年度综合总结和月度详情框架
        
        返回:
            dict: 包含综合总结和月度详情的时间线数据
        """
        print("开始生成初始时间线...")
        
        # 从人物画像中提取姓名
        person_name = self.persona.get('name', '人物')
        
        # 生成完整的时间线数据，包含年度综合总结和月度详情
        # 示例月份按 spec 动态生成，避免 months=3 时示例里仍出现 12 个月、把模型引回 2025 全年
        example_months = ",\n".join(
            f'                {{{{\n'
            f'                    "month": "{mk}",\n'
            f'                    "events": [],\n'
            f'                    "main topics": [],\n'
            f'                    "changes": ""\n'
            f'                }}}}'
            for mk in self.spec.month_keys
        )
        timeline_prompt = f"""
        你是一位专业的人生规划师和故事作家，请根据以下人物画像，为{person_name}的{self.spec.year}年生成一份完整的时间线数据。

        人物画像：
        {json.dumps(self.persona, ensure_ascii=False, indent=2)}

        思考过程：
        1. 首先分析人物画像，了解{person_name}的背景、职业、性格和目标
        2. 基于人物画像，构思{self.spec.year}年的整体发展脉络

        时间线字段说明：
        - comprehensive_summary：年度综合总结，描述{person_name}{self.spec.year}年的整体发展情况，包括专业、财务、健康和家庭责任等方面的变化
        - monthly_details：月度详情列表，包含{self.spec.months}个月的详细信息
          - month：月份，格式为YYYY-MM
          - events：该月发生的事件列表
          - main topics：该月的主要事件的主题列表
          - changes：该月的个人变化描述

        输出格式：
        仅返回JSON格式的时间线数据，不包含任何其他内容

        输出示例：
        {{
            "comprehensive_summary": "",
            "monthly_details": [
{example_months}
            ]
        }}
        """

        try:
            # 使用llm_call_j获取JSON格式响应
            response = llm_call_j(timeline_prompt)
            # 移除JSON包装
            cleaned_response = self.remove_json_wrapper(response, 'object')
            # 解析JSON响应
            initial_timeline = json.loads(cleaned_response)
            print("成功生成初始时间线")
        except Exception as e:
            print(f"生成初始时间线失败: {str(e)}")
            # 生成默认时间线
            comprehensive_summary = f"{person_name}的{self.spec.year}年是充满挑战与成长的一年，在专业、财务、健康和家庭责任方面都取得了显著进展。"
            monthly_details = []
            for month in self.spec.month_nums:
                month_str = self.spec.month_key(month)
                monthly_details.append({
                    "month": month_str,
                    "events": [],
                    "main topics": [],
                    "changes": ""
                })
            initial_timeline = {
                "comprehensive_summary": comprehensive_summary,
                "monthly_details": monthly_details
            }
        
        print("初始时间线生成完成")
        return initial_timeline

    def _time_guard(self) -> str:
        """与 Scheduler 一致的时间范围约束头，避免模板中的 2025 示例牵引出错误年份。"""
        lines = [
            "【时间范围硬性约束】",
            f"本次生成的目标年份为 {self.spec.year} 年，模拟范围为 {self.spec.describe()}。",
            f"1. 所有日期必须落在 {self.spec.start_date} 至 {self.spec.end_date} 之间，"
            f"不得生成该范围之外的任何日期。",
        ]
        if self.spec.year != DEFAULT_YEAR:
            lines.append(
                f"2. 下文提示词与示例中出现的年份（如 {DEFAULT_YEAR}）仅供格式参考，"
                f"一律以本约束的 {self.spec.year} 年为准，不得照搬。"
            )
        if self.spec.months < 12:
            lines.append(
                f"{len(lines) - 1}. 月份仅限 1 至 {self.spec.months} 月；"
                f"不要生成第 {self.spec.months + 1} 月及以后的内容，"
                f"全年总结也只覆盖这 {self.spec.months} 个月。"
            )
        lines.append("-" * 40)
        return "\n".join(lines) + "\n"

    def llm_call_sr(self, prompt, record=0):
        """调用大模型的函数"""
        res = llm_call_reason_j(self._time_guard() + prompt)
        return res

    def llm_call_s(self, prompt, record=0):
        """调用大模型的函数"""
        res = llm_call_j(self._time_guard() + prompt)
        return res

    def get_month_calendar(self, year, month):
        """
        生成指定年月的每日星期几和节日对照表
        :param year: 年份（如2025）
        :param month: 月份（如1-12）
        :return: 列表，每个元素为{"date": "YYYY-MM-DD", "weekday": "星期X", "holiday": "节日名称或空"}
        """
        # 初始化中国节假日数据集
        cn_holidays = holidays.China(years=year)

        # 获取当月第一天和最后一天
        first_day = datetime(year, month, 1)
        # 计算当月最后一天（下个月第一天减1天）
        if month == 12:
            next_month_first = datetime(year + 1, 1, 1)
        else:
            next_month_first = datetime(year, month + 1, 1)
        last_day = (next_month_first - timedelta(days=1)).day

        calendar = []
        for day in range(1, last_day + 1):
            current_date = datetime(year, month, day)
            date_str = current_date.strftime("%Y-%m-%d")

            # 转换星期几（0=周一，6=周日 → 调整为"星期一"至"星期日"）
            weekday_map = {0: "星期一", 1: "星期二", 2: "星期三", 3: "星期四",
                           4: "星期五", 5: "星期六", 6: "星期日"}
            weekday = weekday_map[current_date.weekday()]

            # 获取节日（优先法定节假日，再传统节日）
            holiday = cn_holidays.get(current_date, "")

            calendar.append({
                "date": date_str,
                "weekday": weekday,
                "holiday": holiday
            })

        return calendar

    def remove_json_wrapper(self, input_str: str, json_type: str = 'object') -> str:
        """
        移除JSON字符串的前后包装（如```json ```标签、非法转义字符等）
        并根据json_type参数提取对应的JSON内容：
        - json_type='object'：提取第一个{到最后一个}之间的内容
        - json_type='array'：提取第一个[到最后一个]之间的内容

        参数:
            input_str: 输入字符串
            json_type: JSON类型，'object'对应{}，'array'对应[]，默认为'object'

        返回:
            str: 清理后的字符串
        """
        # 步骤1：去除开头的```json（含空格/换行）和结尾的```（含空格）
        pattern = r'^\s*```json\s*\n?|\s*```\s*$'
        result = re.sub(pattern, '', input_str, flags=re.MULTILINE)

        # 步骤2：根据json_type提取对应的括号内容
        if json_type == 'array':
            first_bracket = result.find('[')
            last_bracket = result.rfind(']')
            if first_bracket != -1 and last_bracket != -1 and first_bracket < last_bracket:
                result = result[first_bracket:last_bracket + 1]
        else:  # 默认处理JSON对象
            first_brace = result.find('{')
            last_brace = result.rfind('}')
            if first_brace != -1 and last_brace != -1 and first_brace < last_brace:
                result = result[first_brace:last_brace + 1]

        # 步骤3：清理 JSON 非法控制字符
        # 保留：JSON 允许的控制字符（\n换行、\r回车、\t制表符、\b退格、\f换页）+ 可见ASCII字符（0x20-0x7E）+ 中文/全角字符
        valid_pattern = r'[^\x20-\x7E\n\r\t\b\f\u4E00-\u9FFF\u3000-\u303F\uFF00-\uFFEF\u2000-\u206F\u2E80-\u2EFF]'
        result = re.sub(valid_pattern, '', result)

        # 步骤4：规范空格和换行
        result = result.strip()  # 去除首尾多余空格/换行
        result = result.replace('\u3000', ' ')  # 全角空格转半角空格
        result = re.sub(r'\r\n?', '\n', result)  # 统一换行符为 \n
        return result

    def extract_important_nodes(self, persona):
        """
        基于人物画像提取今年（2025年）的重要节点

        参数:
            persona: 人物画像数据

        返回:
            dict: 包含个人重要节点和社交关系相关人士重要节点的字典
        """
        result = {"personal_nodes": [], "social_nodes": []}

        # 1. 单独提取个人重要节点
        print("开始提取个人重要节点...")
        personal_prompt = template_important_nodes.format(persona=persona)
        personal_res = self.llm_call_s(personal_prompt)

        try:
            # 解析个人重要节点
            # 使用remove_json_wrapper函数处理JSON字符串
            cleaned_json_str = self.remove_json_wrapper(personal_res, 'object')
            if cleaned_json_str:
                try:
                    personal_result = json.loads(cleaned_json_str)
                    if "personal_nodes" in personal_result:
                        result["personal_nodes"] = personal_result["personal_nodes"]
                        print(f"成功提取{len(result['personal_nodes'])}个个人重要节点")
                except json.JSONDecodeError as e:
                    print(f"解析个人重要节点失败: {str(e)}")
        except Exception as e:
            print(f"提取个人重要节点失败: {str(e)}")

        # 2. 单独提取社交关系相关人士的重要节点（每10个社交关系为一组进行生成）
        print("\n开始提取社交关系重要节点...")

        # 检查persona中是否包含社交关系信息
        if "relation" not in persona or not persona["relation"]:
            print("persona中没有社交关系信息")
        else:
            try:
                # 创建main_persona：原个人信息去除relation之后的信息
                main_persona = persona.copy()
                if "relation" in main_persona:
                    del main_persona["relation"]

                # 从persona中提取所有社交关系
                all_relations = []
                for relation_group in persona["relation"]:
                    if isinstance(relation_group, list):
                        all_relations.extend(relation_group)
                    else:
                        all_relations.append(relation_group)

                print(f"共提取到{len(all_relations)}个社交关系")

                # 将社交关系按每10个一组进行分组
                for i in range(0, len(all_relations), 10):
                    batch_relations = all_relations[i:i+10]
                    print(f"\n处理第{int(i/10)+1}组社交关系，共{len(batch_relations)}个")

                    # 调用LLM生成当前批次社交关系的重要节点
                    batch_prompt = template_social_nodes.format(main_persona=main_persona, social_group=batch_relations)
                    batch_res = self.llm_call_s(batch_prompt)
                    print(f"第{int(i/10)+1}组社交关系重要节点提取结果:")
                    print(batch_res)

                    # 解析当前批次的结果
                    # 使用remove_json_wrapper函数处理JSON字符串
                    cleaned_json_str = self.remove_json_wrapper(batch_res, 'object')
                    if cleaned_json_str:
                        try:
                            batch_result = json.loads(cleaned_json_str)
                            if "social_nodes" in batch_result:
                                result["social_nodes"].extend(batch_result["social_nodes"])
                                print(f"成功提取第{int(i/10)+1}组{len(batch_result['social_nodes'])}个社交关系重要节点")
                        except json.JSONDecodeError as e:
                            print(f"解析第{int(i/10)+1}组社交关系重要节点失败: {str(e)}")
                            # 继续处理下一个批次，不影响后续生成
            except Exception as e:
                print(f"提取社交关系重要节点失败: {str(e)}")
                import traceback
                traceback.print_exc()

        print(f"\n社交关系重要节点提取完成，共提取{len(result['social_nodes'])}个")

        return result

    def extract_personal_change_timelines(self, persona):
        """
        提取个人变化节点，为四个指定主题各生成一个时间线

        参数:
            persona: 人物画像数据

        返回:
            list: 包含个人变化时间线的列表
        """
        print("\n开始提取个人变化事件时间线...")
        personal_change_timelines = []

        try:
            # 初始化历史记录
            history_records = []

            # 定义四个主题字典
            event_types = [
                {"type": "工作变动", "description": "包括升职、降薪、转行、职业发展等相关事件"},
                {"type": "家庭变动",
                 "description": "包括搬家、家庭成员变动（指成员的里程碑事件，如升职，结婚等）、家庭资产变动（如大物件购置，环境改造）相关事件"},
                {"type": "爱好变动", "description": "包括新增爱好相关事件"},
                {"type": "偏好变动", "description": "包括新增偏好、偏好转变等相关事件"}
            ]

            # 为每个主题生成一个事件时间线
            for idx, event_type in enumerate(event_types):
                print(f"\n为主题 '{event_type['type']}' 生成个人变化事件...")

                # 准备历史记录字符串
                if history_records:
                    history_str = "\n".join(
                        [f"{j + 1}. 主题：{record['name']}，描述：{record['description']}" for j, record in
                         enumerate(history_records)])
                else:
                    history_str = "暂无历史记录"

                # 构建prompt，传入指定主题
                changes_prompt = template_personal_changes.format(
                    persona=persona,
                    history=history_str,
                    event_type=event_type['type']
                )

                # 调用LLM生成个人变化事件时间线
                changes_res = self.llm_call_s(changes_prompt)
                # print(f"主题 '{event_type['type']}' 生成结果:")
                # print(changes_res)

                # 解析个人变化事件时间线
                # 使用remove_json_wrapper函数处理JSON字符串
                cleaned_json_str = self.remove_json_wrapper(changes_res, 'object')
                if cleaned_json_str:
                    try:
                        event_timeline = json.loads(cleaned_json_str)
                        # 添加主题类型字段
                        event_timeline["theme"] = event_type['type']
                        personal_change_timelines.append(event_timeline)

                        # 记录历史，避免主题重复
                        history_records.append({
                                "name": event_timeline["topic"],
                                "description": event_timeline["detailed_description"]
                        })

                        print(f"成功提取 '{event_type['type']}' 主题事件：{event_timeline['topic']}")
                    except json.JSONDecodeError as e:
                        print(f"解析 '{event_type['type']}' 主题事件失败: {str(e)}")
                        # 继续处理下一个主题，不影响后续生成
        except Exception as e:
            print(f"提取个人变化事件时间线失败: {str(e)}")
            import traceback
            traceback.print_exc()

        print(f"\n个人变化事件时间线提取完成，共提取{len(personal_change_timelines)}个事件时间线")

        return personal_change_timelines

    def generate_event_timeline(self, important_nodes, max_workers=None):
        """
        基于提取的重要节点生成主题时间线

        参数:
            important_nodes: 包含个人节点和社交节点的字典
            max_workers: 最大并发线程数，当前禁用多线程

        返回:
            dict: 按类别分类的主题时间线，每个主题包含结构化的主题、详细描述和月度描述
        """
        # 1. 按类别分类所有事件
        categorized_events = {}

        # 首先初始化所有在event_type_descriptions中定义的事件类别
        event_type_descriptions = {
            "Career": "职业工作相关（如“参加行业高峰论坛”“参与新产品研发项目”）",
            "Education": "教育学习相关（如“上课”“考取专业资格证”，学生角色该类事件较多，其他角色相关事件会较少）",
            "Relationships": "人际关系（如“为父母筹备生日宴”“组织闺蜜旅行”）",
            "Family&Living Situation": "家庭生活与居住环境（如“智能家居安装”“组织家庭活动”）",
            "Personal Life": "自我关怀、娱乐与生活方式（SelfCare & Entertainment & Lifesyle）（如“定期SPA护理”“短途旅行”“组织同学聚会”“KTV娱乐”）",
            "Finance": "个人资产财务、个人收入与购物消费（如“购买理财产品”“汽车保养与维修”“工资收入”“购物消费”）",
            "Health": "健康管理、运动偏好与生活作息，饮食习惯变化（如“中医调理”“瑜伽静修营”“定期健身”“跑步锻炼”）",
        }

        # 初始化所有事件类别为[]
        for event_type in event_type_descriptions:
            categorized_events[event_type] = []

        # 处理个人重要节点
        for event in important_nodes.get("personal_nodes", []):
            event_type = event.get("type", "Other")
            if event_type not in categorized_events:
                categorized_events[event_type] = []
            categorized_events[event_type].append(event)

        # 处理社交重要节点（按事件自身的type分类）
        for event in important_nodes.get("social_nodes", []):
            # 使用事件自身的type字段进行分类
            event_type = event.get("type", "Relationships")
            if event_type not in categorized_events:
                categorized_events[event_type] = []
            categorized_events[event_type].append(event)

        # 3. 为每个类别生成额外的重要事件（测试阶段只生成Family&Living Situation类别）
        from src.lifebench.event.templates.template_scheduler import template_important_events_generation
        import json

        # 为所有类别生成额外重要事件（多线程版本）
        from concurrent.futures import ThreadPoolExecutor

        def generate_important_events_for_category(event_type, existing_events):
            """为单个事件类别生成额外重要事件"""
            print(f"\n开始为{event_type}类别生成额外重要事件...")

            # 定义不同事件类别的描述
            event_type_descriptions = {
                "Career": "职业工作相关（如“参加行业高峰论坛”“参与新产品研发项目”）",
                "Education": "教育学习相关（如“上课”“考取专业资格证”，学生角色该类事件较多，其他角色相关事件会较少）",
                "Relationships": "人际关系（如“为父母筹备生日宴”“组织闺蜜旅行”）",
                "Family&Living Situation": "家庭生活与居住环境（如“智能家居安装”“组织家庭活动”）",
                "Personal Life": "自我关怀、娱乐与生活方式（SelfCare & Entertainment & Lifesyle）（如“定期SPA护理”“短途旅行”“组织同学聚会”“KTV娱乐”）",
                "Finance": "个人资产财务、个人收入与购物消费（如“购买理财产品”“汽车保养与维修”“工资收入”“购物消费”）",
                "Health": "健康管理、运动偏好与生活作息，饮食习惯变化（如“中医调理”“瑜伽静修营”“定期健身”“跑步锻炼”）",
            }

            # 获取当前事件类别的描述，如果没有则使用默认描述
            event_type_with_description = event_type
            if event_type in event_type_descriptions:
                event_type_with_description = f"{event_type}：{event_type_descriptions[event_type]}"

            # 准备prompt，将已有重要节点作为参考输入
            prompt = template_important_events_generation.format(
                persona=self.persona,
                event_type=event_type_with_description,
                existing_events=json.dumps(existing_events, ensure_ascii=False) if existing_events else "[]"
            )

            generated_events = []

            # 调用LLM生成重要事件
            try:
                response = self.llm_call_s(prompt)

                # 提取JSON部分
                start_idx = response.find('[')
                end_idx = response.rfind(']')
                if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                    json_response = response[start_idx:end_idx + 1]
                    raw_events = json.loads(json_response)

                    # 转换为与原有事件格式一致的结构
                    generated_events = [{
                        "name": event["name"],
                        "type": event_type,
                        "description": event["description"],
                        "impact": event["potential_impact"],
                        "reason": event["reason"]
                    } for event in raw_events]

                    print(f"成功为{event_type}类别生成{len(generated_events)}个额外重要事件")
                else:
                    print(f"无法提取{event_type}类别生成的重要事件JSON")
            except json.JSONDecodeError as e:
                print(f"解析{event_type}类别重要事件JSON时出错: {e}")
                # print(f"LLM响应内容: {response}")
            except Exception as e:
                print(f"为{event_type}类别生成重要事件时发生错误: {e}")
                import traceback
                traceback.print_exc()

            return (event_type, generated_events)

        # 使用线程池并行处理所有事件类别
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有事件类别的处理任务
            future_to_category = {
                executor.submit(generate_important_events_for_category, event_type, events): event_type
                for event_type, events in categorized_events.items()
            }

            # 收集处理结果
            for future in future_to_category:
                try:
                    event_type, result = future.result()
                    if result:
                        categorized_events[event_type].extend(result)
                except Exception as e:
                    event_type = future_to_category[future]
                    print(f"处理{event_type}类别额外重要事件时发生错误: {e}")
                    import traceback
                    traceback.print_exc()

        # 2. 为每个类别生成事件变动时间线
        event_timelines = {}

        # 如果没有事件类型，直接返回空字典
        if not categorized_events:
            return event_timelines

        def generate_topic_timelines(event_type, events):
            """生成单个类别的主题时间线JSON数组，每十个事件调用一次LLM生成"""
            import json
            print(f"\n开始生成{event_type}类别的主题时间线...")

            # 定义不同事件类别的描述
            event_type_descriptions = {
                "Career": "职业工作相关（如“参加行业高峰论坛”“参与新产品研发项目”）",
                "Education": "教育学习相关（如“上课”“考取专业资格证”，学生角色该类事件较多，其他角色相关事件会较少）",
                "Relationships": "人际关系（如“为父母筹备生日宴”“组织闺蜜旅行”）",
                "Family&Living Situation": "家庭生活与居住环境（如“家居装修”“智能家居安装”）",
                "Personal Life": "自我关怀、娱乐与生活方式（SelfCare & Entertainment & Lifesyle）（如“定期SPA护理”“短途旅行”“组织同学聚会”）",
                "Finance": "个人资产财务、个人收入与购物消费（如“购买理财产品”“汽车保养与维修”“工资收入”“购物消费”）",
                "Health": "健康管理、运动偏好与生活作息，饮食习惯变化（如“中医调理”“瑜伽静修营”“定期健身”“跑步锻炼”）",
                "Unexpected Events": "突发应对（如“车辆小事故处理”“临时加班替班”）",
                "Other": "其他未涉及类别"
            }

            # 获取当前事件类别的描述，如果没有则使用默认描述
            event_type_with_description = event_type
            if event_type in event_type_descriptions:
                event_type_with_description = f"{event_type}：{event_type_descriptions[event_type]}"

            # 将事件按每10个一组进行分组
            events_per_group = 10
            event_groups = [events[i:i + events_per_group] for i in range(0, len(events), events_per_group)]

            all_timeline_data = []

            # 处理每组事件
            for group_idx, event_group in enumerate(event_groups):
                print(f"\n处理{event_type}类别第{group_idx + 1}/{len(event_groups)}组事件，共{len(event_group)}个事件")

                # 准备prompt
                prompt = template_event_timeline.format(
                    event_type=event_type_with_description,
                    persona=self.persona,
                    important_nodes=json.dumps(event_group, ensure_ascii=False)
                )

                # 调用LLM生成时间线JSON
                try:
                    response = self.llm_call_sr(prompt)
                    # print(f"{event_type}类别第{group_idx+1}组主题时间线生成结果:")
                    # print(response)

                    # 提取JSON部分：匹配第一个[和最后一个]之间的内容
                    start_idx = response.find('[')
                    end_idx = response.rfind(']')
                    if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                        json_response = response[start_idx:end_idx + 1]
                        timeline_data = json.loads(json_response)
                        all_timeline_data.extend(timeline_data)
                    else:
                        print(f"第{group_idx + 1}组无法提取JSON内容")
                        print(f"LLM响应内容: {response}")
                except json.JSONDecodeError as e:
                    print(f"解析{event_type}第{group_idx + 1}组时间线JSON时出错: {e}")
                    print(f"LLM响应内容: {response}")
                except Exception as e:
                    print(f"生成{event_type}第{group_idx + 1}组时间线时出错: {str(e)}")
                    import traceback
                    traceback.print_exc()

            print(f"\n{event_type}类别所有组时间线生成完成，共生成{len(all_timeline_data)}个主题时间线")
            return all_timeline_data

        # 处理所有类别的事件，使用多线程并行处理
        from concurrent.futures import ThreadPoolExecutor

        def process_event_category(event_type, events):
            """处理单个事件类别的时间线生成"""
            print(f"\n开始处理{event_type}类别...")

            # 生成主题时间线数据（直接返回，不再进行冲突消解和时间线统一）
            topic_timelines_data = generate_topic_timelines(event_type, events)

            if topic_timelines_data:
                print(f"{event_type}类别主题时间线生成完成")
                return (event_type, topic_timelines_data)
            else:
                print(f"{event_type}类别没有生成主题时间线数据")
                return (event_type, [])

        # 使用线程池并行处理所有事件类别
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有事件类别的处理任务
            future_to_category = {
                executor.submit(process_event_category, event_type, events): event_type
                for event_type, events in categorized_events.items()
            }

            # 收集处理结果
            for future in future_to_category:
                try:
                    event_type, result = future.result()
                    if result:
                        event_timelines[event_type] = result
                except Exception as e:
                    event_type = future_to_category[future]
                    print(f"处理{event_type}类别时发生错误: {e}")
                    import traceback
                    traceback.print_exc()

        # 调用个人变化时间线提取函数，将结果作为"persona change"类别的时间线
        persona_change_timelines = self.extract_personal_change_timelines(self.persona)
        if persona_change_timelines:
            event_timelines["persona change"] = persona_change_timelines

        return event_timelines

    def filter_and_rank_timelines(self, event_timelines, persona, max_workers=None):
        """
        Filter similar timelines and rank them by quality, without quantity control

        Args:
            event_timelines: Event timeline dictionary, key is event type, value is topic timeline list
            persona: 人物画像数据
            max_workers: Maximum number of concurrent threads, default uses CPU core count

        Returns:
            tuple: (Filtered timeline list, Filtered timeline id list)
        """
        import json

        print("\n开始处理所有类别的相似主题筛选重排...")

        # 1. 收集所有事件类型的时间线到一个列表
        all_timelines = []
        timeline_metadata = []  # 保存时间线的原始事件类型信息

        for event_type, timelines in event_timelines.items():
            for timeline in timelines:
                all_timelines.append(timeline)
                timeline_metadata.append({
                    'original_event_type': event_type
                })

        print(f"共收集到{len(all_timelines)}个主题时间线")

        # 如果时间线数量小于2，无需筛选
        if len(all_timelines) < 2:
            print(f"只有{len(all_timelines)}个主题时间线，无需筛选")
            # 为时间线生成id
            selected_ids = []
            for i, (timeline, metadata) in enumerate(zip(all_timelines, timeline_metadata), 1):
                event_type = metadata['original_event_type']
                timeline_id = f"{event_type}_{i}"
                selected_ids.append(timeline_id)
            return all_timelines, selected_ids

        # 2. 按主题长度排序（可选，有助于后续处理）
        sorted_timelines = sorted(all_timelines, key=lambda x: len(x.get('topic', '')), reverse=True)

        # 3. 首先过滤掉完全不合理或不符合画像的时间线
        print("开始过滤不合理或不符合画像的时间线...")
        filtered_timelines = []
        filtered_metadata = []
        
        if len(sorted_timelines) > 0:
            # 准备过滤用的时间线信息
            filter_timeline_info = []
            for i, timeline in enumerate(sorted_timelines, 1):
                topic = timeline.get('topic', '')
                description = timeline.get('detailed_description', '')[:150]  # 截取部分描述以控制prompt长度
                filter_timeline_info.append(f"序号{i}: 主题: {topic}\n描述: {description}...")
            
            # 构建过滤prompt
            filter_prompt = f"""
            人物画像信息：
            {persona}

            以下是一系列主题时间线的信息：
            {chr(10).join(filter_timeline_info)}

            请仔细分析这些主题时间线，并执行以下过滤任务：

            1. 过滤标准：
               - 完全不合理的时间线（如事件时间、地点、逻辑明显矛盾）
               - 不符合人物画像的时间线（与人物背景、职业、生活状况等明显不符）
               - 内容明显不真实或不符合常理的时间线
               - 事件安排过于密集或时间分布不合理的时间线

            2. 输出格式要求：
               仅返回JSON对象，格式如下：
               {{  "removed_timelines": [序号1, 序号2, 序号3, ...]  }}  # 去除的时间线序号列表

               请确保输出的JSON格式正确，不包含任何无关解释、注释或代码，直接以{{}}开头。
            """
            
            print("过滤不合理时间线prompt: ", filter_prompt)
            # 调用LLM进行过滤
            filter_result = {}
            try:
                response = self.llm_call_sr(filter_prompt)
                print(f"LLM过滤响应内容: {response}")
                # 提取JSON部分
                start_idx = response.find('{')
                end_idx = response.rfind('}')
                if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                    json_response = response[start_idx:end_idx + 1]
                    filter_result = json.loads(json_response)
                    print(
                        f"成功获取LLM过滤结果：共保留{len(filter_result.get('filtered_timelines', []))}个时间线")
                else:
                    print("无法提取过滤结果的JSON")
            except json.JSONDecodeError as e:
                print(f"解析过滤结果JSON时出错: {e}")
            except Exception as e:
                print(f"过滤时间线时发生错误: {e}")
                import traceback
                traceback.print_exc()
            
            # 处理过滤结果
            removed_indices = filter_result.get('removed_timelines', [])
            
            if removed_indices:
                # 计算保留的序号
                all_indices = list(range(1, len(sorted_timelines) + 1))
                filtered_indices = [idx for idx in all_indices if idx not in removed_indices]
                
                for idx in filtered_indices:
                    if 1 <= idx <= len(sorted_timelines):
                        filtered_timelines.append(sorted_timelines[idx - 1])
                        filtered_metadata.append(timeline_metadata[idx - 1])
                print(f"成功过滤：保留{len(filtered_indices)}个时间线，去除{len(removed_indices)}个时间线")
                print(f"去除的时间线序号：{removed_indices}")
            else:
                print("LLM未返回过滤结果，使用所有时间线")
                filtered_timelines = sorted_timelines
                filtered_metadata = timeline_metadata
        else:
            filtered_timelines = sorted_timelines
            filtered_metadata = timeline_metadata
        
        print(f"过滤完成，保留{len(filtered_timelines)}个时间线")
        
        # 如果过滤后时间线数量小于2，无需进一步筛选
        if len(filtered_timelines) < 2:
            print(f"过滤后只有{len(filtered_timelines)}个主题时间线，无需进一步筛选")
            # 为时间线生成id
            selected_ids = []
            for i, (timeline, metadata) in enumerate(zip(filtered_timelines, filtered_metadata), 1):
                event_type = metadata['original_event_type']
                timeline_id = f"{event_type}_{i}"
                selected_ids.append(timeline_id)
            return filtered_timelines, selected_ids
        
        # 4. 准备LLM提示，判断主题相似性
        timeline_info = []
        for i, timeline in enumerate(filtered_timelines, 1):
            topic = timeline.get('topic', '')
            description = timeline.get('detailed_description', '')[:150]  # 截取部分描述以控制prompt长度
            timeline_info.append(f"序号{i}: 主题: {topic}\n描述: {description}...")

        # 构建相似性判断和选择prompt
        similarity_prompt = f"""
        以下是一系列主题时间线的信息：
        {chr(10).join(timeline_info)}

        请仔细分析这些主题时间线，并执行以下任务：

        1. 相似簇判断：找出所有主题相似的簇。相似的标准是主题内容大部分重复或高度相关，没有必要单独作为一个主题时间线。
        2. 相似簇选择：从每个相似簇中选择一个最具代表性、最全面、事件时间分布最真实丰富的时间线，返回其序号。
        3. 主题多样性优先：确保最终剩余的时间线主题间尽量差异明显，避免内容重复，优先保留不同类别的主题（如工作、学习、健康、生活、社交、爱好等）。
        4. 真实丰富时间优先：在选择时间线时，优先选择事件时间分布真实、丰富、符合生活逻辑的时间线，避免选择时间过于集中或事件安排不真实的时间线。避免变化过于曲折而违和的时间线。
        5. 冲突处理：
           - 对于存在冲突（事件时间、地点、影响等不一致）的时间线，选择冲突较少、更合理的时间线
           - 确保时间线的连贯性和合理性
        6. 事件真实性检查：
           - 对于主题相同的事件（如都是患病类事件），需考虑整合后是否会导致一年中该类事件过多而不真实
           - 确保最终的时间线组合符合实际生活逻辑，避免出现不真实的事件密集情况

        输出格式要求：
        1. 仅返回JSON对象，格式如下：
        {{  "selected_timelines": [序号1, 序号2, 序号3, ...],  # 保留的时间线序号列表
            "similar_clusters": [[序号1, 序号2], [序号3, 序号4], ...]  # 相似簇列表（用于冲突分析）
        }}
        2. 确保selected_timelines中的序号没有重复，和similar_clusters中的簇的序号对应
        3. 每个相似簇至少包含2个序号
        4. 请确保输出的JSON格式正确，不包含任何无关解释、注释或代码，直接以{{}}开头。
        """
        print("相似主题判断和选择prompt: ", similarity_prompt)
        # 调用LLM判断相似性并选择时间线
        llm_result = {}
        try:
            response = self.llm_call_sr(similarity_prompt)
            print(f"LLM响应内容: {response}")
            # 提取JSON部分
            start_idx = response.find('{')
            end_idx = response.rfind('}')
            if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                json_response = response[start_idx:end_idx + 1]
                llm_result = json.loads(json_response)
                print(
                    f"成功获取LLM选择结果：共选择{len(llm_result.get('selected_timelines', []))}个时间线，识别{len(llm_result.get('similar_clusters', []))}个相似主题簇")
            else:
                print("无法提取相似主题和选择结果的JSON")
        except json.JSONDecodeError as e:
            print(f"解析相似主题和选择结果JSON时出错: {e}")
            # print(f"LLM响应内容: {response}")
        except Exception as e:
            print(f"判断主题相似性时发生错误: {e}")
            import traceback
            traceback.print_exc()

        # 4. 处理LLM返回的选择结果
        selected_timelines = []
        selected_ids = []

        # 获取LLM选择的时间线序号和相似簇
        selected_indices = llm_result.get('selected_timelines', [])
        similar_clusters = llm_result.get('similar_clusters', [])

        if selected_indices and similar_clusters:
            print(f"开始处理LLM选择的{len(selected_indices)}个时间线...")

            # 收集所有相似簇中的序号
            all_cluster_indices = set()
            for cluster in similar_clusters:
                all_cluster_indices.update(cluster)
            
            # 收集没有归类到相似簇的序号
            all_indices = set(range(1, len(filtered_timelines) + 1))
            non_cluster_indices = all_indices - all_cluster_indices
            
            # 合并选择的序号和非相似簇的序号
            final_selected_indices = set(selected_indices) | non_cluster_indices
            
            # 添加最终选择的时间线
            for idx in sorted(final_selected_indices):
                if 1 <= idx <= len(filtered_timelines):
                    timeline = filtered_timelines[idx - 1]
                    selected_timelines.append(timeline)
                    # 为时间线生成id
                    event_type = filtered_metadata[idx - 1]['original_event_type']
                    timeline_id = f"{event_type}_{idx}"
                    selected_ids.append(timeline_id)
            
            print(f"处理完成：保留了{len(selected_indices)}个相似簇选择的时间线和{len(non_cluster_indices)}个非相似簇时间线")
        else:
            print("LLM未返回选择结果或相似簇，使用默认策略：按主题长度排序")
            # 默认策略：按主题长度排序
            selected_timelines = filtered_timelines
            for i, timeline in enumerate(selected_timelines, 1):
                event_type = filtered_metadata[i - 1]['original_event_type']
                timeline_id = f"{event_type}_{i}"
                selected_ids.append(timeline_id)

        # 随机抽样筛选出65%的数据（保障大于等于10）
        import random
        total_count = len(selected_timelines)
        target_count = max(10, int(total_count * 0.65))
        
        if total_count > target_count:
            # 随机抽样
            sampled_indices = random.sample(range(total_count), target_count)
            sampled_timelines = [selected_timelines[i] for i in sampled_indices]
            sampled_ids = [selected_ids[i] for i in sampled_indices]
            print(f"随机抽样完成，从{total_count}个时间线中抽取{target_count}个")
            return sampled_timelines, sampled_ids
        else:
            print(f"时间线数量{total_count}不足，直接返回所有时间线")
            return selected_timelines, selected_ids


    def generate_yearly_timeline_plot(self, persona, output_path="output/", meidan_path=None):
        """
        生成年度时间线草稿（优化版：添加错误处理和输出保存）

        参数:
            persona: 人物画像数据
            output_path: 每日状态数据输出路径
            meidan_path: 除每日状态外的其他数据输出路径

        返回:
            生成的年度时间线草稿数据，或在发生错误时返回None
        """
        import os
        import json
        import traceback
        from datetime import datetime

        # 如果meidan_path未指定，使用output_path加process文件夹
        if meidan_path is None:
            meidan_path = os.path.join(output_path, 'process')

        # 确保输出路径存在
        os.makedirs(output_path, exist_ok=True)
        os.makedirs(meidan_path, exist_ok=True)

        try:
            # 步骤1: 提取重要节点
            print("\n=== 步骤1: 提取重要节点 ===")
            important_nodes_path = os.path.join(meidan_path, "important_nodes.json")
            if os.path.exists(important_nodes_path):
                print(f"✓ 重要节点文件已存在，直接读取: {important_nodes_path}")
                with open(important_nodes_path, 'r', encoding='utf-8') as f:
                    important_nodes = json.load(f)
            else:
                important_nodes = self.extract_important_nodes(persona=persona)
                print(f"✓ 成功提取{len(important_nodes)}个重要节点")
                # 保存结果
                with open(important_nodes_path, 'w', encoding='utf-8') as f:
                    json.dump(important_nodes, f, ensure_ascii=False, indent=2)
                print(f"✓ 重要节点已保存到: {important_nodes_path}")

            # 步骤2: 生成事件时间线
            print("\n=== 步骤2: 生成事件时间线 ===")
            event_timelines_path = os.path.join(meidan_path, "event_timelines.json")
            if os.path.exists(event_timelines_path):
                print(f"✓ 事件时间线文件已存在，直接读取: {event_timelines_path}")
                with open(event_timelines_path, 'r', encoding='utf-8') as f:
                    event_timelines = json.load(f)
            else:
                event_timelines = self.generate_event_timeline(important_nodes, max_workers=12)
                print(f"✓ 成功生成{len(event_timelines)}个事件时间线")
                # 保存结果
                with open(event_timelines_path, 'w', encoding='utf-8') as f:
                    json.dump(event_timelines, f, ensure_ascii=False, indent=2)
                print(f"✓ 事件时间线已保存到: {event_timelines_path}")

            # 步骤3: 合并相似时间线
            print("\n=== 步骤3: 合并相似时间线 ===")
            merged_timelines_path = os.path.join(meidan_path, "merged_timelines.json")
            if os.path.exists(merged_timelines_path):
                print(f"✓ 合并后的时间线文件已存在，直接读取: {merged_timelines_path}")
                with open(merged_timelines_path, 'r', encoding='utf-8') as f:
                    merged_timelines = json.load(f)
            else:
                merged_timelines, _ = self.filter_and_rank_timelines(event_timelines, persona)
                print(f"✓ 成功筛选重排为{len(merged_timelines)}个时间线")
                # 保存结果
                with open(merged_timelines_path, 'w', encoding='utf-8') as f:
                    json.dump(merged_timelines, f, ensure_ascii=False, indent=2)
                print(f"✓ 合并后的时间线已保存到: {merged_timelines_path}")

        except Exception as e:
            print(f"\n❌ 生成年度时间线草稿时发生错误: {str(e)}")
            traceback.print_exc()

            # 保存错误信息到文件
            error_info = {
                "error": str(e),
                "traceback": traceback.format_exc(),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            error_path = os.path.join(meidan_path, "error_log.json")
            with open(error_path, 'w', encoding='utf-8') as f:
                json.dump(error_info, f, ensure_ascii=False, indent=2)
            print(f"❌ 错误信息已保存到: {error_path}")

    def enhance_main_timeline(self, main_timeline, reference_timelines):
        """
        基于参考时间线数据，增强和润色主要时间线数据

        参数:
            main_timeline: 主要的确定时间线数据
            reference_timelines: 筛选后的参考时间线数据列表

        返回:
            dict: 增强和润色后的主要时间线数据
        """
        print("\n开始基于参考时间线增强主要时间线...")

        try:
            # 初始化增强结果为原始主要时间线
            enhanced_result = main_timeline.copy()
            
            # 循环处理每条参考时间线，每次只输入一条参考数据
            for i, ref_timeline in enumerate(reference_timelines):
                print(f"\n处理第{i+1}条参考时间线...")
                
                # 提取当前主要时间线信息（完整数据）
                import json
                current_main = json.dumps(enhanced_result, ensure_ascii=False, indent=2)
                
                # 提取当前参考时间线信息（完整数据）
                current_ref = json.dumps(ref_timeline, ensure_ascii=False, indent=2)
                
                # 构建增强prompt，只包含当前一条参考时间线
                enhance_prompt = f"""
                主要时间线完整数据：
                {current_main}

                参考时间线完整数据：
                {current_ref}

                请分析这条参考时间线数据，找出其中有用、有创意、可加入到主要时间线的情节、事件、信息，然后重写修改润色主要时间线数据。

                要求：
                1. 保持主要时间线的核心内容和结构
                2. 融入参考时间线中相关的、有价值的信息
                3. 确保增强后的时间线逻辑连贯、内容丰富、情节合理
                4. 保持语言风格一致，自然流畅
                5. 不要添加与主要时间线无关的内容

                输出格式要求：
                仅返回JSON对象，格式如下：
                {{  "enhanced_timeline": {{
                        "topic": "增强后的主题",
                        "detailed_description": "增强后的详细描述",
                        "monthly_description": [
                            {{
                                "month": "1月",
                                "content": "月度内容",
                                "impact": "影响描述",
                                "core_events": ["核心事件1", "核心事件2"]
                            }},
                            ...
                        ]
                    }}
                }}

                请确保输出的JSON格式正确，不包含任何无关解释、注释或代码，直接以{{}}开头。
                """

                print(f"增强主要时间线prompt (处理第{i+1}条参考时间线): ", enhance_prompt)
                # 调用LLM增强时间线
                response = self.llm_call_sr(enhance_prompt)
                print(f"增强主要时间线响应: {response}")

                # 解析增强后的时间线
                start_idx = response.find('{')
                end_idx = response.rfind('}')
                if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                    json_response = response[start_idx:end_idx + 1]
                    result = json.loads(json_response)
                    enhanced_timeline = result.get('enhanced_timeline', {})

                    # 确保返回的数据结构完整
                    if enhanced_timeline:
                        enhanced_result = enhanced_timeline
                        print(f"成功处理第{i+1}条参考时间线")
                    else:
                        print(f"未提取到增强后的时间线，继续使用当前结果")
                else:
                    print(f"无法提取增强后的时间线JSON，继续使用当前结果")

            print("成功完成所有参考时间线的处理")
            return enhanced_result
        except Exception as e:
            print(f"增强主要时间线时发生错误: {str(e)}")
            import traceback
            traceback.print_exc()
            return main_timeline