import json
import os
import importlib
from typing import List, Dict, Any
from event.qa_generator.base_generator import BaseQAGenerator


class QAGenerator:
    """
    问答生成器主类，自动发现并整合所有 QA 生成器
    通过动态导入 qa_generator 目录下的所有生成器类实现自动注册
    """
    
    # 生成器配置：定义生成器名称、类名和默认参数
    GENERATOR_CONFIG = {
        'qa_single_generator': {
            'class_name': 'QASingleGenerator',
            'qagen_params': {},  # 默认参数
            'order': 1
        },
        # 'qa_multi_hop_generator': {
        #     'class_name': 'QAMultiHopGenerator',
        #     'qagen_params': {
        #         'num_questions_per_month': 8,
        #         'num_persona_questions': 6
        #     },
        #     'order': 3
        # },
        'qa_pattern_recognition_generator': {
            'class_name': 'QAPatternRecognitionGenerator',
            'qagen_params': {
                'num_questions_per_month': 5
            },
            'order': 2
        },
        # 'qa_reasoning_generator': {
        #     'class_name': 'QAReasoningGenerator',
        #     'qagen_params': {
        #         'num_questions_per_theme': 2,
        #         'num_questions_per_group': 2
        #     },
        #     'order': 4
        # }
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
        
        # 尝试从 event.qa_generator 包的__init__.py 中获取所有导出类
        try:
            import event.qa_generator as qa_pkg
            print(f"✓ 成功导入 event.qa_generator 包")
            
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
                    print(f"正在导入模块：event.qa_generator.{module_name}")
                    module = importlib.import_module(f'event.qa_generator.{module_name}')
                    # 获取类
                    generator_class = getattr(module, class_name)
                    print(f"✓ 找到类：{class_name}")
                    
                    # 初始化生成器
                    generator = generator_class(phone_data_dir=self.phone_data_dir)
                    
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
        
        # 加载数据到所有生成器
        self._load_data_to_generators()
        
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
        
        # 依次调用每个生成器
        for idx, (gen_name, gen_data) in enumerate(ordered_generators, 1):
            generator = gen_data['instance']
            config = gen_data['config']
            
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
                
                print(f"✓ {gen_name}问题生成完成")
                
            except Exception as e:
                print(f"✗ {gen_name}问题生成失败：{e}")
                import traceback
                traceback.print_exc()
        
        print("\n所有问答对生成完成！")
        
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
                    other_gen.phonedata = source_gen.phonedata.copy()
                    other_gen.phone_id_counters = source_gen.phone_id_counters.copy()
            
            # 重置更新标记
            source_gen._data_updated = False
        else:
            print("没有检测到数据更新，无需同步")
