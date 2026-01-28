import json
import os
from typing import List, Dict, Any

# 导入所需的生成器类
from event.qa_single_generator import QASingleGenerator
from event.qa_muti_generator import QAMutiGenerator
from event.qa_reasoning_generator import QAReasoningGenerator

class QAGenerator:
    """
    问答生成器主类，整合单跳、多跳、模式识别和推理问题生成功能
    """
    
    def __init__(self, data_path: str):
        """
        初始化QAGenerator
        
        Args:
            data_path: 用户数据路径，包含persona.json、event_tree.json、daily_event.json等文件
        """
        self.data_path = data_path
        
        # 获取phone_data_dir路径
        self.phone_data_dir = os.path.join(data_path, "phone_data")
        
        # 初始化各个生成器
        self.single_hop_generator = QASingleGenerator(phone_data_dir=self.phone_data_dir)
        self.multi_hop_generator = QAMutiGenerator(phone_data_dir=self.phone_data_dir)
        self.reasoning_generator = QAReasoningGenerator(phone_data_dir=self.phone_data_dir)
        
        # 为每个生成器设置更新flag
        self.single_hop_generator._data_updated = False
        self.multi_hop_generator._data_updated = False
        self.reasoning_generator._data_updated = False
        
        # 加载数据到各个生成器
        self.single_hop_generator.load_data_from_path(data_path)
        self.multi_hop_generator.load_data_from_path(data_path)
        self.reasoning_generator.load_data_from_path(data_path)
        
        # 初始同步一次所有数据
        self._share_phone_data()
        
   
    
    def generate_all_qa(self, year: int, themes: List[Dict[str, Any]] = None, event_id_groups: List[List[int]] = None):
        """
        生成所有类型的问答对
        
        Args:
            year: 年份（例如：2025）
            themes: 用于生成推理问题的theme数组
            event_id_groups: 用于生成推理问题的事件ID组数组
        """
        print("开始生成所有类型的问答对...")
        
        # 1. 生成年度单跳问答
        print("\n1. 开始生成年度单跳问答...")
        self.single_hop_generator.generate_yearly_single_hop_qa(year)
        # 设置单跳生成器的数据更新标记
        self.single_hop_generator._data_updated = True
        # 共享数据
        self._share_phone_data()
        print("年度单跳问答生成完成")
        
        # 2. 生成年度模式识别问题
        print("\n2. 开始生成年度模式识别问题...")
        self.multi_hop_generator.generate_yearly_pattern_recognition_questions(str(year), num_questions_per_month=5)
        # 设置多跳生成器的数据更新标记
        self.multi_hop_generator._data_updated = True
        # 共享数据
        self._share_phone_data()
        print("年度模式识别问题生成完成")
        
        # 3. 生成年度多跳问题
        print("\n3. 开始生成年度多跳问题...")
        self.multi_hop_generator.generate_yearly_multi_hop_questions(str(year), num_questions_per_month=8, num_persona_questions=6)
        # 设置多跳生成器的数据更新标记
        self.multi_hop_generator._data_updated = True
        # 共享数据
        self._share_phone_data()
        print("年度多跳问题生成完成")
        
        # 4. 生成推理问题（如果提供了themes或event_id_groups）
        if themes:
            print("\n4. 开始基于主题生成推理问题...")
            self.reasoning_generator.generate_reasoning_questions_by_themes(themes)
            # 设置推理生成器的数据更新标记
            self.reasoning_generator._data_updated = True
            # 共享数据
            self._share_phone_data()
            print("基于主题的推理问题生成完成")

        if event_id_groups:
            print("\n5. 开始基于事件ID组生成推理问题...")
            self.reasoning_generator.generate_reasoning_questions_from_event_tree_id_groups(event_id_groups)
            # 设置推理生成器的数据更新标记
            self.reasoning_generator._data_updated = True
            # 共享数据
            self._share_phone_data()
            print("基于事件ID组的推理问题生成完成")
        else:
            print("\n4. 未提供themes或event_id_groups数据，跳过推理问题生成")
        
        print("\n所有问答对生成完成！")
        
        # 保存所有手机数据到新目录
        print("\n开始保存所有手机数据...")
        # 创建new子文件夹路径
        new_phone_data_dir = os.path.join(self.phone_data_dir, "new")
        # 由于所有生成器的数据都是同步的，选择任意一个生成器保存即可
        self.single_hop_generator.save_phone_data_to_dir(new_phone_data_dir)
        print(f"所有手机数据已保存到: {new_phone_data_dir}！")
    
    def load_themes_from_file(self, themes_file_path: str) -> List[Dict[str, Any]]:
        """
        从文件加载themes数据
        
        Args:
            themes_file_path: themes文件路径
            
        Returns:
            List[Dict[str, Any]]: themes数组
        """
        if os.path.exists(themes_file_path):
            with open(themes_file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            print(f"Themes文件不存在: {themes_file_path}")
            return []
    
    def _share_phone_data(self):
        """
        根据更新flag判断哪个生成器的数据发生了变化，并将其数据同步到其他生成器
        """
        # 检查单跳生成器是否更新了数据
        if self.single_hop_generator._data_updated:
            print("检测到单跳生成器数据更新，开始同步到其他生成器...")
            # 将单跳生成器的数据同步到多跳和推理生成器
            self.multi_hop_generator.phonedata = self.single_hop_generator.phonedata.copy()
            self.multi_hop_generator.phone_id_counters = self.single_hop_generator.phone_id_counters.copy()
            self.reasoning_generator.phonedata = self.single_hop_generator.phonedata.copy()
            self.reasoning_generator.phone_id_counters = self.single_hop_generator.phone_id_counters.copy()
            # 重置更新标记
            self.single_hop_generator._data_updated = False
        
        # 检查多跳生成器是否更新了数据
        elif self.multi_hop_generator._data_updated:
            print("检测到多跳生成器数据更新，开始同步到其他生成器...")
            # 将多跳生成器的数据同步到单跳和推理生成器
            self.single_hop_generator.phonedata = self.multi_hop_generator.phonedata.copy()
            self.single_hop_generator.phone_id_counters = self.multi_hop_generator.phone_id_counters.copy()
            self.reasoning_generator.phonedata = self.multi_hop_generator.phonedata.copy()
            self.reasoning_generator.phone_id_counters = self.multi_hop_generator.phone_id_counters.copy()
            # 重置更新标记
            self.multi_hop_generator._data_updated = False
        
        # 检查推理生成器是否更新了数据
        elif self.reasoning_generator._data_updated:
            print("检测到推理生成器数据更新，开始同步到其他生成器...")
            # 将推理生成器的数据同步到单跳和多跳生成器
            self.single_hop_generator.phonedata = self.reasoning_generator.phonedata.copy()
            self.single_hop_generator.phone_id_counters = self.reasoning_generator.phone_id_counters.copy()
            self.multi_hop_generator.phonedata = self.reasoning_generator.phonedata.copy()
            self.multi_hop_generator.phone_id_counters = self.reasoning_generator.phone_id_counters.copy()
            # 重置更新标记
            self.reasoning_generator._data_updated = False
        
        # 如果没有生成器更新数据
        else:
            print("没有检测到数据更新，无需同步")