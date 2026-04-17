"""
测试WritingAgent类的功能
"""

import json
import unittest
from event.edit import WritingAgent


class TestWritingAgent(unittest.TestCase):
    """
    测试WritingAgent类的功能
    """
    
    def setUp(self):
        """
        初始化测试环境
        """
        # 使用测试用的persona.json文件
        self.persona_path = r"D:\pyCharmProjects\pythonProject4\test\persona.json"
        self.agent = WritingAgent(self.persona_path)
    
    def test_interact_with_user(self):
        """
        测试与用户交互方法
        """
        # 测试生成新情节
        print("\033[1;32m===== 测试1: 新增情节，该用户在2025年1月去北京出差，参加医学会议 =====\033[0m")
        plot1 = self.agent.interact_with_user("新增情节，该用户在2025年1月去北京出差，参加医学会议")
        print("当前情节数据：")
        print(json.dumps(plot1, ensure_ascii=False, indent=2))
        print(f"历史记录长度: {len(self.agent.plot_history)}")
        
        # 测试优化上一个情节
        print("\n\033[1;32m===== 测试2: 我希望该用户在2025年遇到了一位新闺蜜，她们迅速成为要好的朋友，但是闺蜜在年末去了伊朗，两人分离 =====\033[0m")
        plot2 = self.agent.interact_with_user("我希望该用户在2025年遇到了一位新闺蜜，她们迅速成为要好的朋友，但是闺蜜在年末去了伊朗，两人分离", current_plot=plot1)
        print("当前情节数据：")
        print(json.dumps(plot2, ensure_ascii=False, indent=2))
        print(f"历史记录长度: {len(self.agent.plot_history)}")
        
        # 测试撤销指令
        print("\n\033[1;32m===== 测试3: 撤销 =====\033[0m")
        plot3 = self.agent.interact_with_user("撤销")
        print("当前情节数据：")
        print(json.dumps(plot3, ensure_ascii=False, indent=2))
        print(f"历史记录长度: {len(self.agent.plot_history)}")
        
        # 测试无关内容指令
        print("\n\033[1;32m===== 测试4: 今天天气怎么样？ =====\033[0m")
        plot4 = self.agent.interact_with_user("今天天气怎么样？", current_plot=plot3)
        print("当前情节数据：")
        print(json.dumps(plot4, ensure_ascii=False, indent=2))
        print(f"历史记录长度: {len(self.agent.plot_history)}")


if __name__ == '__main__':
    unittest.main()