import json
import os
import copy
import importlib
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor
from src.lifebench.event.qa_generator.base_generator import BaseQAGenerator
from src.lifebench.utils.llm_call import llm_call_j, llm_call_reason_j


class QAGenerator:
    """
    问答生成器主类，自动发现并整合所有 QA 生成器
    通过动态导入 qa_generator 目录下的所有生成器类实现自动注册
    """
    
    # 生成器配置：定义生成器名称、类名和默认参数
    GENERATOR_CONFIG = {
        'qa_single_generator': {
            'class_name': 'QASingleGenerator',
            'order': 1,
            'qagen_params': {
                'year': 2025,
                'output_path': None
            }
        },
        'qa_temporal_generator': {
            'class_name': 'QATemporalGenerator',
            'order': 2,
            'qagen_params': {
                'year': '2025'
            }
        },
        'qa_multi_hop_generator': {
            'class_name': 'QAMultiHopGenerator',
            'order': 3,
            'qagen_params': {
                'year': 2025,
                'num_questions_per_month': 7
            }
        },
        'qa_pattern_recognition_generator': {
            'class_name': 'QAPatternRecognitionGenerator',
            'order': 4,
            'qagen_params': {
                'year': '2025',
                'num_questions_per_month': 6
            }
        },
        'qa_conflict_generator': {
            'class_name': 'QAConflictGenerator',
            'order': 5,
            'qagen_params': {
                'year': 2025,
                'num_samples': 60
            }
        },
        # 'qa_harmful_memory_generator': {
        #     'class_name': 'QAHarmfulMemoryGenerator',
        #     'order': 6,
        #     'qagen_params': {}
        # },
        'qa_unanswerable_generator': {
            'class_name': 'QAUnanswerableGenerator',
            'order': 7,
            'qagen_params': {
                'year': 2025,
                'num_questions_per_month': 4
            }
        },
        'qa_knowledge_updating_generator': {
            'class_name': 'QAKnowledgeUpdatingGenerator',
            'order': 8,
            'qagen_params': {
                'max_questions_per_topic': 10
            }
        },
        'qa_hidden_info_generator': {
            'class_name': 'QAHiddenInfoGenerator',
            'order': 9,
            'qagen_params': {}
        },
        'qa_causal_generator': {
            'class_name': 'QACausalGenerator',
            'order': 10,
            'qagen_params': {
                'year': 2025,
                'num_questions_per_month': 7
            }
        }
    }
    
    def __init__(self, data_path: str, auto_discover: bool = True):
        """
        初始化 QAGenerator
        
        Args:
            data_path: 用户数据路径，包含 persona.json、event_tree.json、daily_event.json 等文件
            auto_discover: 是否自动发现并加载所有生成器（默认 True）
        """
        self.data_path = data_path
        self.phone_data_dir = os.path.join(data_path, "phone_data")
        self.generators = {}  # 存储所有生成器实例
        
        if auto_discover:
            # 自动发现并初始化所有生成器
            self._discover_and_load_generators()
    
    def _discover_and_load_generators(self):
        """
        自动发现 event.qa_generator 包下的所有生成器类并初始化
        通过导入包的__all__或扫描模块实现
        """
        print("开始自动发现和加载 QA 生成器...")
        
        # 先加载数据
        print("\n[Step 1] 加载基础数据...")
        persona_data = {}
        daily_event = []
        event_tree = []
        draft_event = {}
        phonedata = {}
        
        # 加载 persona
        persona_path = os.path.join(self.data_path, "persona.json")
        if os.path.exists(persona_path):
            with open(persona_path, 'r', encoding='utf-8') as f:
                persona_data = json.load(f)
            print(f"✓ 加载 persona: {len(persona_data)} 个字段")
        
        # 加载 daily_event
        daily_event_path = os.path.join(self.data_path, "daily_event.json")
        if os.path.exists(daily_event_path):
            with open(daily_event_path, 'r', encoding='utf-8') as f:
                daily_event = json.load(f)
            print(f"✓ 加载 daily_event: {len(daily_event)} 个事件")
        
        # 加载 event_tree
        event_tree_path = os.path.join(self.data_path, "event_tree.json")
        if os.path.exists(event_tree_path):
            with open(event_tree_path, 'r', encoding='utf-8') as f:
                event_tree = json.load(f)
            print(f"✓ 加载 event_tree: {len(event_tree)} 个节点")
        
        # 加载 draft_event
        draft_event_path = os.path.join(self.data_path, "daily_draft.json")
        if os.path.exists(draft_event_path):
            with open(draft_event_path, 'r', encoding='utf-8') as f:
                draft_event = json.load(f)
            print(f"✓ 加载 draft_event: {len(draft_event)} 个月份")
        
        # 加载 phone data
        if os.path.exists(self.phone_data_dir):
            print(f"\n[Step 2] 加载手机数据从 {self.phone_data_dir}...")
            for filename in os.listdir(self.phone_data_dir):
                if filename.endswith('.json'):
                    filepath = os.path.join(self.phone_data_dir, filename)
                    data_type = filename.replace('.json', '')
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            data_list = json.load(f)
                            if isinstance(data_list, list):
                                phonedata[data_type] = data_list
                    except Exception as e:
                        print(f"✗ {data_type} 加载失败: {e}")
            print(f"✓ 加载手机数据: {len(phonedata)} 种类型")
        
        # 尝试从 event.qa_generator 包的__init__.py 中获取所有导出类
        try:
            import src.lifebench.event.qa_generator as qa_pkg
            print(f"\n[Step 3] 导入 event.qa_generator 包")
            
            # 检查是否有__all__定义
            if hasattr(qa_pkg, '__all__'):
                # __all__中是类名列表
                class_names = qa_pkg.__all__
                print(f"从__all__获取类名：{class_names}")
            else:
                # 如果没有__all__，使用配置中的类名
                class_names = [config['class_name'] for config in self.GENERATOR_CONFIG.values()]
                print(f"使用配置中的类名：{class_names}")
            
            # 遍历配置中的所有生成器
            for module_name, config in self.GENERATOR_CONFIG.items():
                class_name = config['class_name']
                
                # 跳过 base_generator
                if class_name == 'BaseQAGenerator':
                    continue
                
                # 检查该类是否在可用类名列表中
                if class_name not in class_names:
                    print(f"跳过不在__all__中的类：{class_name}")
                    continue
                
                try:
                    # 动态导入模块
                    print(f"\n正在导入模块：src.lifebench.event.qa_generator.{module_name}")
                    module = importlib.import_module(f'src.lifebench.event.qa_generator.{module_name}')
                    # 获取类
                    generator_class = getattr(module, class_name)
                    print(f"✓ 找到类：{class_name}")
                    
                    # 根据类的构造函数签名初始化生成器
                    import inspect
                    sig = inspect.signature(generator_class.__init__)
                    params = sig.parameters
                    
                    # 准备初始化参数
                    init_kwargs = {'phone_data_dir': self.phone_data_dir}
                    
                    # 如果构造函数需要其他参数，添加它们
                    if 'persona_data' in params:
                        init_kwargs['persona_data'] = persona_data
                    if 'daily_event' in params:
                        init_kwargs['daily_event'] = daily_event
                    if 'event_tree' in params:
                        init_kwargs['event_tree'] = event_tree
                    if 'draft_event' in params:
                        init_kwargs['draft_event'] = draft_event
                    if 'phonedata' in params:
                        init_kwargs['phonedata'] = phonedata
                    if 'year' in params:
                        init_kwargs['year'] = config['qagen_params'].get('year', 2025)

                    # 初始化生成器
                    generator = generator_class(**init_kwargs)
                    
                    # 存储生成器实例
                    self.generators[module_name] = {
                        'instance': generator,
                        'config': config,
                        'order': config.get('order', 999)
                    }
                    
                    print(f"✓ 成功加载生成器：{module_name} ({class_name})")
                    
                except Exception as e:
                    print(f"✗ 加载生成器失败 {module_name}: {e}")
                    import traceback
                    traceback.print_exc()
        
        except ImportError as e:
            print(f"✗ 无法导入 event.qa_generator 包：{e}")
            import traceback
            traceback.print_exc()
            return
        
        # 初始同步一次所有数据
        self._share_phone_data()
        
        print(f"\n共加载 {len(self.generators)} 个生成器")
        print(f"生成器列表：{', '.join([name for name in sorted(self.generators.keys(), key=lambda x: self.generators[x]['order'])])}\n")
    
    def _load_data_to_generators(self):
        """
        加载数据到所有生成器
        """
        for gen_name, gen_data in self.generators.items():
            generator = gen_data['instance']
            generator.load_data_from_path(self.data_path)
            generator._data_updated = False
    
    def generate_all_qa(self, year: int, themes: List[Dict[str, Any]] = None, 
                       event_id_groups: List[List[int]] = None, 
                       generator_orders: List[str] = None):
        """
        按顺序调用所有已注册的生成器生成问答对
        
        Args:
            year: 年份（例如：2025）
            themes: 用于生成推理问题的 theme 数组
            event_id_groups: 用于生成推理问题的事件 ID 组数组
            generator_orders: 自定义生成器执行顺序（可选），默认为配置中的 order
        """
        print("开始生成所有类型的问答对...")
        
        # 确定生成器执行顺序
        if generator_orders:
            # 使用自定义顺序
            ordered_generators = [
                (name, self.generators[name]) 
                for name in generator_orders 
                if name in self.generators
            ]
        else:
            # 使用配置中的 order 排序
            ordered_generators = sorted(
                self.generators.items(), 
                key=lambda x: x[1]['order']
            )
        
        # 创建 QA_all 文件夹
        qa_all_dir = os.path.join(self.data_path, "QA_all")
        if not os.path.exists(qa_all_dir):
            os.makedirs(qa_all_dir)
            print(f"✓ 创建 QA_all 文件夹: {qa_all_dir}")
        
        # 存储所有生成的问题
        all_questions = []
        
        # 依次调用每个生成器
        for idx, (gen_name, gen_data) in enumerate(ordered_generators, 1):
            generator = gen_data['instance']
            config = gen_data['config']
            
            # 检查对应的文件是否已存在
            single_output_path = os.path.join(qa_all_dir, f"{gen_name}.json")
            if os.path.exists(single_output_path):
                print(f"\n{idx}. 跳过 {gen_name}（文件已存在: {single_output_path}）")
                # 加载已有文件并添加到总列表，后续会统一经过分类处理
                try:
                    with open(single_output_path, 'r', encoding='utf-8') as f:
                        existing_questions = json.load(f)
                    if isinstance(existing_questions, list):
                        # 加载已有文件时也先过滤格式，只保留指定字段
                        allowed_fields = ["question", "answer", "score_points", "required_events_id", "question_type", "evidence", "ask_time"]
                        filtered_existing = []
                        for item in existing_questions:
                            filtered_item = {k: v for k, v in item.items() if k in allowed_fields}
                            filtered_existing.append(filtered_item)
                        all_questions.extend(filtered_existing)
                        print(f"   ✓ 已加载 {len(filtered_existing)} 个已有问题（已过滤字段），将统一经过分类处理")
                except Exception as e:
                    print(f"   ⚠️ 加载已有文件失败: {e}")
                continue
            
            print(f"\n{idx}. 开始生成{gen_name}问题...")
            
            # 准备 QAGen 的参数
            qagen_kwargs = config['qagen_params'].copy()
            
            # 特殊处理：添加年份参数
            if 'year' not in qagen_kwargs:
                qagen_kwargs['year'] = str(year)
            
            # 对于推理生成器，添加额外参数
            if gen_name == 'reasoning':
                if themes:
                    qagen_kwargs['themes'] = themes
                if event_id_groups:
                    qagen_kwargs['event_id_groups'] = event_id_groups
            
            # 调用 QAGen
            try:
                result = generator.QAGen(**qagen_kwargs)
                
                # 设置更新标记
                generator._data_updated = True
                
                # 共享数据
                self._share_phone_data()
                
                # 单独保存该生成器的问题
                if result and isinstance(result, list):
                    with open(single_output_path, 'w', encoding='utf-8') as f:
                        json.dump(result, f, ensure_ascii=False, indent=2)
                    print(f"✓ {gen_name}问题生成完成，共 {len(result)} 个问题，已保存到 {single_output_path}")
                    
                    # 添加到总列表前先过滤格式，只保留指定字段
                    filtered_result = []
                    allowed_fields = ["question", "answer", "score_points", "required_events_id", "question_type", "evidence", "ask_time"]
                    for item in result:
                        filtered_item = {k: v for k, v in item.items() if k in allowed_fields}
                        filtered_result.append(filtered_item)

                    all_questions.extend(filtered_result)
                else:
                    print(f"✓ {gen_name}问题生成完成，但未返回问题")
                
            except Exception as e:
                print(f"✗ {gen_name}问题生成失败：{e}")
                import traceback
                traceback.print_exc()
        
        print("\n所有问答对生成完成！")

        # 整合所有问题到 QA.json
        if all_questions:
            # 先过滤不可回答的问题（并行 LLM 调用）
            all_questions_before_filter = all_questions
            persona_name = ""
            persona_path = os.path.join(self.data_path, "persona.json")
            if os.path.exists(persona_path):
                with open(persona_path, 'r', encoding='utf-8') as f:
                    persona_data = json.load(f)
                    persona_name = persona_data.get("name", "")
            print(f"可回答性过滤：用户名为 {persona_name}")
            answerable_qa, discard_stats = self._filter_unanswerable_qa_parallel(all_questions, persona_name)
            all_questions = answerable_qa

            # 按原问题类型统计抛弃数量
            answerable_qa_ids = set(id(qa) for qa in answerable_qa)
            type_discard_stats = {}
            for qa in all_questions_before_filter:
                if id(qa) not in answerable_qa_ids:
                    q_types = qa.get('question_type', [])
                    if isinstance(q_types, list):
                        type_key = tuple(sorted(q_types))
                    else:
                        type_key = (str(q_types),)
                    type_discard_stats[type_key] = type_discard_stats.get(type_key, 0) + 1

            if type_discard_stats:
                print("\n按原问题类型统计的抛弃数量:")
                for type_key, count in sorted(type_discard_stats.items(), key=lambda x: -x[1]):
                    print(f"  - {type_key}: {count} 个")

            # 对可回答的问题进行类型重新分类（并行 LLM 调用）
            all_questions = self._classify_qa_types_parallel(all_questions)

            # 重新生成 score_points（并行 LLM 调用）
            all_questions = self._regenerate_score_points_parallel(all_questions, persona_name)

            final_output_path = os.path.join(qa_all_dir, "QA.json")
            with open(final_output_path, 'w', encoding='utf-8') as f:
                json.dump(all_questions, f, ensure_ascii=False, indent=2)
            print(f"\n✓ 所有问题已整合保存到: {final_output_path}")
            print(f"✓ 总计 {len(all_questions)} 个问题")

            # 统计各类型问题数量
            type_count = {}
            for qa in all_questions:
                q_types = qa.get('question_type', [])
                if isinstance(q_types, list):
                    for q_type in q_types:
                        type_count[q_type] = type_count.get(q_type, 0) + 1
                else:
                    q_type = q_types
                    type_count[q_type] = type_count.get(q_type, 0) + 1

            print("\n问题类型统计:")
            for q_type, count in sorted(type_count.items()):
                print(f"  - {q_type}: {count} 个问题")

            # hidden_info 格式转换已移至 qa_hidden_info_generator.py 的 QAGen 方法中

        # 保存所有手机数据到新目录
        print("\n开始保存所有手机数据...")
        new_phone_data_dir = os.path.join(self.phone_data_dir, "new")
        
        # 使用任意一个生成器保存数据（因为数据是同步的）
        if self.generators:
            first_generator = next(iter(self.generators.values()))['instance']
            first_generator.save_phone_data_to_dir(new_phone_data_dir)
            print(f"所有手机数据已保存到：{new_phone_data_dir}！")

    def get_registered_generators(self) -> List[str]:
        """
        获取所有已注册的生成器名称列表
        
        Returns:
            生成器名称列表（按执行顺序排序）
        """
        return [name for name, data in sorted(
            self.generators.items(), 
            key=lambda x: x[1]['order']
        )]
    
    def add_generator(self, name: str, generator_class: type, 
                     qagen_params: Dict[str, Any] = None, order: int = 999):
        """
        手动添加新的生成器（适用于不在配置文件中的新类型）
        
        Args:
            name: 生成器名称（用于标识）
            generator_class: 生成器类（必须是 BaseQAGenerator 的子类）
            qagen_params: QAGen 方法的默认参数
            order: 执行顺序（数字越小越先执行）
        """
        if not issubclass(generator_class, BaseQAGenerator):
            raise TypeError(f"生成器类必须是 BaseQAGenerator 的子类")
        
        try:
            # 初始化生成器
            generator = generator_class(phone_data_dir=self.phone_data_dir)
            
            # 加载数据
            generator.load_data_from_path(self.data_path)
            generator._data_updated = False
            
            # 注册生成器
            self.generators[name] = {
                'instance': generator,
                'config': {'class_name': generator_class.__name__, 'qagen_params': qagen_params or {}},
                'order': order
            }
            
            print(f"✓ 成功添加生成器：{name} ({generator_class.__name__})")
            
        except Exception as e:
            print(f"✗ 添加生成器失败 {name}: {e}")
            raise
    
    def remove_generator(self, name: str):
        """
        移除已注册的生成器
        
        Args:
            name: 生成器名称
        """
        if name in self.generators:
            del self.generators[name]
            print(f"✓ 已移除生成器：{name}")
        else:
            print(f"✗ 生成器不存在：{name}")
    
    def load_themes_from_file(self, themes_file_path: str) -> List[Dict[str, Any]]:
        """
        从文件加载 themes 数据
        
        Args:
            themes_file_path: themes 文件路径
            
        Returns:
            List[Dict[str, Any]]: themes 数组
        """
        if os.path.exists(themes_file_path):
            with open(themes_file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            print(f"Themes 文件不存在：{themes_file_path}")
            return []
    
    def _share_phone_data(self):
        """
        根据更新 flag 判断哪个生成器的数据发生了变化，并将其数据同步到其他生成器
        """
        if not self.generators:
            return
        
        # 获取所有生成器列表
        all_generators = list(self.generators.values())
        
        # 检查是否有生成器更新了数据
        updated_gen = None
        for gen_name, gen_data in self.generators.items():
            if gen_data['instance']._data_updated:
                updated_gen = gen_data
                break
        
        if updated_gen:
            print(f"检测到{updated_gen['instance'].__class__.__name__}数据更新，开始同步到其他生成器...")
            
            # 将更新的生成器的数据同步到所有其他生成器
            source_gen = updated_gen['instance']
            for other_name, other_data in self.generators.items():
                other_gen = other_data['instance']
                if other_gen != source_gen:
                    other_gen.phonedata = copy.deepcopy(source_gen.phonedata)
                    other_gen.phone_id_counters = copy.deepcopy(source_gen.phone_id_counters)
            
            # 重置更新标记
            source_gen._data_updated = False
        else:
            print("没有检测到数据更新，无需同步")

    def _classify_qa_types_parallel(self, qa_list: List[Dict[str, Any]], max_workers: int = 20) -> List[Dict[str, Any]]:
        """
        并行调用 LLM 对每个问答对进行类型重新分类

        Args:
            qa_list: 问答对列表
            max_workers: 最大并行线程数

        Returns:
            更新类型后的问答对列表
        """
        def classify_single_qa(qa: Dict[str, Any]) -> Dict[str, Any]:
            """对单个问答对进行类型分类"""
            # 如果原类型已经是 Unanswerable，直接保留
            original_type = qa.get('question_type', '')
            is_knowledge_update = original_type == 'Knowledge_update'
            is_conflict = original_type == 'Conflict'
            is_hidden_info = original_type == 'Hidden_info'

            if original_type == 'Unanswerable':
                qa['question_type'] = ['Unanswerable']
                return qa

            question = qa.get('question', '')
            answer = qa.get('answer', '')
            evidence = qa.get('evidence', [])

            prompt = f"""请分析以下问答对的问题、答案和证据，判断该问题最适合的分类类型有哪些。

### 问题类型说明
- Single_hop: 单跳问题，可以从单个事件/证据直接回答
- Multi_hop: 多跳问题，需要结合多个事件/证据才能回答
- Temporal: 时间推理问题，涉及排序，持续时间长推理,时序推理、时间顺序，日期/时间计算的问题。当题目明确给出时间且不需要时间的推理时，不算 Temporal 类型
- Causal: 因果推理问题，涉及询问原因和结果的问题
- Knowledge_update: 知识更新问题，涉及认知或知识更新的问题,或者体现用户变化，对用户的变化进行询问的问题。
- Conflict: 冲突问题，部分证据之间存在冲突，如"A说C发生在7月，B说C发生在8月"，涉及安排修改，回忆错误等产生矛盾信息的场景。请你仔细分析证据字段是否出现过描述不一致的信息，即使证据包含纠正信息，也把该问题归类为Conflict类型。
- Pattern_recognition(Non-declarative): 模式识别问题，关注个人习惯，偏好，行为模式，一段时间的总结等方面
- Hidden_info: 隐式偏好挖掘问题，需要从证据信息中推断隐含的用户画像信息，用户个人偏好的问题，可能涉及物品推荐场景，偏好询问场景。

### 输出要求
分析问题特点，从上述类型中选择最匹配的 1-3 个类型标签，按匹配程度从高到低排列。
只输出 JSON 数组格式，不要添加任何解释文字。

### 问答对信息
问题：{question}
答案：{answer}
证据：{json.dumps(evidence, ensure_ascii=False, indent=2) if evidence else '无证据'}

请直接输出类型标签数组，格式如：["Single_hop", "Pattern_recognition(Non-declarative)"]
"""
            try:
                result = llm_call_j(prompt)
                result = result.strip()

                # 尝试解析 LLM 返回的 JSON 数组
                # 移除可能的 ```json 包装
                if result.startswith('```'):
                    import re
                    result = re.sub(r'```json\s*|\s*```', '', result, flags=re.MULTILINE)

                result = result.strip()
                if result.startswith('['):
                    types = json.loads(result)
                    if isinstance(types, list) and all(isinstance(t, str) for t in types):
                        qa['question_type'] = types[:3]  # 最多保留3个类型
                        # 如果原类型是 Knowledge_update，确保它在结果中
                        if is_knowledge_update and 'Knowledge_update' not in qa['question_type']:
                            qa['question_type'].append('Knowledge_update')
                        # 如果原类型是 Conflict，确保它在结果中
                        if is_conflict and 'Conflict' not in qa['question_type']:
                            qa['question_type'].append('Conflict')
                        # 如果原类型是 Hidden_info，确保它在结果中
                        if is_hidden_info and 'Hidden_info' not in qa['question_type']:
                            qa['question_type'].append('Hidden_info')
                        return qa
            except Exception as e:
                print(f"类型分类失败: {str(e)}, 保持原类型")

            # 如果失败，保持原类型（可能是单个字符串）
            original_type = qa.get('question_type', 'Unknown')
            if isinstance(original_type, str):
                qa['question_type'] = [original_type]
            return qa

        print(f"\n开始并行分类 QA 类型，共 {len(qa_list)} 个问题...")

        updated_qa_list = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(classify_single_qa, qa_list))
            updated_qa_list = results

        # 统计新类型分布
        type_count = {}
        for qa in updated_qa_list:
            types = qa.get('question_type', [])
            if isinstance(types, list):
                for t in types:
                    type_count[t] = type_count.get(t, 0) + 1
            else:
                type_count[str(types)] = type_count.get(str(types), 0) + 1

        print(f"类型分类完成，新类型统计:")
        for t, count in sorted(type_count.items()):
            print(f"  - {t}: {count} 个问题")

        return updated_qa_list

    def _filter_unanswerable_qa_parallel(self, qa_list: List[Dict[str, Any]], persona_name: str = "", max_workers: int = 20) -> tuple:
        """
        并行调用 LLM 分析每个问答对的可回答性，过滤掉不可回答的问题

        Args:
            qa_list: 问答对列表
            persona_name: 用户姓名（用于明确问题中"我"的指代）
            max_workers: 最大并行线程数

        Returns:
            (answerable_qa_list, discard_stats: Dict[str, int])
            - answerable_qa_list: 可回答的问答对列表
            - discard_stats: 被抛弃的问题统计，按抛弃原因分类
        """
        def filter_single_qa(qa: Dict[str, Any]) -> tuple:
            """对单个问答对进行可回答性分析
            Returns: (qa_or_none, discard_reason)
            """
            # 如果原类型已经是 Unanswerable 或 Conflict，直接保留
            original_type = qa.get('question_type', '')
            if original_type in ('Unanswerable', 'Conflict'):
                return (qa, None)

            question = qa.get('question', '')
            answer = qa.get('answer', '')
            evidence = qa.get('evidence', [])

            prompt = f"""请严格基于证据分析以下问答对，按三个步骤进行判断。

### 重要前提
- 题目中的"我"均指代{persona_name}，而非回答者或其他人，当某个描述确实主语时，默认为{persona_name}。
- 请基于此前提判断问题的可回答性

### 第一步：问题可回答性分析
检查问题是否可以通过证据回答：
- 问题询问的信息是否在证据覆盖的时间范围内？
- 证据是否包含了回答问题所需的全部关键信息？
- 问题描述的关键事件/活动在证据中是否存在对应？
- 如果问题描述的核心前提在证据中缺失（如"夜跑后"但无夜跑记录），则问题不可回答

### 第二步：问题合理性分析
检查问题本身是否合理：
- 主体匹配：问题以"我"提问时，证据中的行为主体是否确实是{persona_name}？
- 时间逻辑：证据显示的事件时间与问题询问的时间是否匹配？
- 描述正确：问题的描述是否与证据一致？

### 第三步：答案合理性分析
在确认问题可回答且合理后，检查答案：
- 答案中的每个细节（时间、地点、人物、状态、事件等）是否在证据中有对应？
- 答案是否有证据中不存在的细节？

### 综合判断
根据以上分析，输出以下三种结果之一：

【情况1 - 通过】
问题和答案均合理，答案与证据完全对应，不存在证据回答不出的内容。
输出：{{"result": "pass", "reason": "通过理由"}}

【情况2 - 修改】
答案有少量细节与证据不符，但核心正确，可通过微调答案使其与证据一致。
输出：{{"result": "modify", "modified_answer": "修正后的答案", "reason": "需要修改的细节及原因"}}

【情况3 - 放弃】
问题不可回答，或答案与证据矛盾，或关键信息缺失无法修复。
输出：{{"result": "discard", "reason": "放弃原因"}}

### 输出格式
请直接输出 JSON 对象，不要添加任何解释文字：
{{"result": "pass/modify/discard", "modified_answer": "修正后答案（仅modify时填写）", "reason": "判断理由"}}

### 问答对信息
问题：{question}
答案：{answer}
证据：{json.dumps(evidence, ensure_ascii=False, indent=2) if evidence else '无证据'}

请直接输出 JSON 对象：
"""
            try:
                result = llm_call_reason_j(prompt)
                result = result.strip()

                # 移除可能的 ```json 包装
                if result.startswith('```'):
                    import re
                    result = re.sub(r'```json\s*|\s*```', '', result, flags=re.MULTILINE)

                result = result.strip()
                analysis = json.loads(result)

                result_type = analysis.get("result", "pass")

                if result_type == "pass":
                    return (qa, None)
                elif result_type == "modify":
                    # 修改答案
                    modified_answer = analysis.get("modified_answer", "")
                    if modified_answer:
                        qa["answer"] = modified_answer
                    return (qa, None)
                else:  # discard
                    reason = analysis.get("reason", "未知原因")
                    print(f"  抛弃问题: {question[:50]}... 原因: {reason}")
                    return (None, reason)

            except Exception as e:
                print(f"可回答性分析失败: {str(e)}, 保留该问题")
                return (qa, None)

        print(f"\n开始并行分析 QA 可回答性，共 {len(qa_list)} 个问题...")

        answerable_qa = []
        discard_stats = {}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(filter_single_qa, qa_list))

        for qa, reason in results:
            if qa is not None:
                answerable_qa.append(qa)
            else:
                reason_category = reason if reason else "未知原因"
                discard_stats[reason_category] = discard_stats.get(reason_category, 0) + 1

        print(f"\n可回答性过滤完成:")
        print(f"  - 保留问题: {len(answerable_qa)} 个")
        print(f"  - 抛弃问题: {len(qa_list) - len(answerable_qa)} 个")

        if discard_stats:
            print(f"  抛弃原因统计:")
            for reason, count in sorted(discard_stats.items(), key=lambda x: -x[1]):
                print(f"    - {reason}: {count} 个")

        return answerable_qa, discard_stats

    def _regenerate_score_points_parallel(self, qa_list: List[Dict[str, Any]], persona_name: str = "", max_workers: int = 20) -> List[Dict[str, Any]]:
        """
        并行调用 LLM 重新生成问答对的 score_points

        Args:
            qa_list: 问答对列表
            persona_name: 用户姓名（用于明确问题中"我"的指代）
            max_workers: 最大并行线程数

        Returns:
            更新 score_points 后的问答对列表
        """
        def regenerate_single_qa(qa: Dict[str, Any]) -> Dict[str, Any]:
            """对单个问答对重新生成 score_points"""
            question = qa.get('question', '')
            answer = qa.get('answer', '')
            evidence = qa.get('evidence', [])

            prompt = f"""请为以下问答对设计评分标准（score_points），用于评估模型回答该问题的准确程度。

### 重要前提
- 题目中的"我"均指代{persona_name}，而非回答者或其他人
- 请基于此前提设计评分标准

### 要求
1. 总分必须为 10 分
2. **得分点内容必须严格基于证据可推断的内容**：
   - 每个得分点的 description 必须能在证据中找到对应或可合理推理
   - 不能出现证据中没有或推理不出的内容
   - 得分点描述的应该是证据中明确包含或可间接推断的关键信息
3. 得分点应反映回答该问题所需的关键推理步骤或知识点
4. 每个得分点的 description 应清晰描述得分点内容，score 为该得分点的分值
5. 得分点数量建议 2-5 个，每个得分点的分值根据重要性和难度分配

### 输出格式
请直接输出 JSON 数组格式，不要添加任何解释文字：
[
  {{
    "description": "得分点1描述（必须在证据中有对应或可推理）",
    "score": X
  }},
  {{
    "description": "得分点2描述（必须在证据中有对应或可推理）",
    "score": Y
  }}
]

### 问答对信息
问题：{question}
答案：{answer}
证据：{json.dumps(evidence, ensure_ascii=False, indent=2) if evidence else '无证据'}

请直接输出 JSON 数组：
"""
            try:
                result = llm_call_j(prompt)
                result = result.strip()

                # 移除可能的 ```json 包装
                if result.startswith('```'):
                    import re
                    result = re.sub(r'```json\s*|\s*```', '', result, flags=re.MULTILINE)

                result = result.strip()
                if result.startswith('['):
                    score_points = json.loads(result)
                    # 检查是否为有效的得分点列表
                    if isinstance(score_points, list) and all(
                        isinstance(item, dict) and 'description' in item and 'score' in item
                        for item in score_points
                    ):
                        # 检查总分是否为 10
                        total = sum(item.get('score', 0) for item in score_points)
                        if total == 10:
                            qa['score_points'] = score_points
                            return qa
                        else:
                            # 总分不为 10，尝试调整
                            if total > 0:
                                scale = 10 / total
                                for item in score_points:
                                    item['score'] = round(item['score'] * scale)
                                qa['score_points'] = score_points
                                return qa

                # 解析失败，使用默认得分点
                qa['score_points'] = [
                    {
                        "description": "正确回答出答案",
                        "score": 10
                    }
                ]
                return qa

            except Exception as e:
                # 异常时使用默认得分点
                qa['score_points'] = [
                    {
                        "description": "正确回答出答案",
                        "score": 10
                    }
                ]
                return qa

        print(f"\n开始重新生成 score_points，共 {len(qa_list)} 个问题...")

        updated_qa_list = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(regenerate_single_qa, qa_list))
            updated_qa_list = results

        print(f"score_points 重新生成完成")

        return updated_qa_list
