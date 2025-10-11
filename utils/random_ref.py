import json
import random
from typing import List, Union


class JSONRandomSelector:
    def __init__(self, file_path: str):
        """
        初始化JSON随机选择器

        参数:
            file_path: JSON文件的路径
        """
        self.data = self._load_json(file_path)

    def _load_json(self, file_path: str) -> dict:
        """加载JSON文件内容"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"找不到文件: {file_path}")
        except json.JSONDecodeError:
            raise ValueError(f"文件 {file_path} 不是有效的JSON格式")
        except Exception as e:
            raise Exception(f"加载文件时出错: {str(e)}")

    def get_available_keys(self) -> List[str]:
        """获取JSON中所有可用的关键词"""
        return list(self.data.keys())

    def random_select(self, key: str, count: int, unique: bool = True) -> Union[List[str], str]:
        """
        从指定关键词的数组中随机抽取指定个数的参考值

        参数:
            key: 要抽取的关键词
            count: 要抽取的数量
            unique: 是否允许重复，True表示不允许重复，False表示允许

        返回:
            抽取的结果列表，如果count为1则返回单个字符串
        """
        # 检查关键词是否存在
        if key not in self.data:
            raise ValueError(f"关键词 '{key}' 不存在，可用关键词: {self.get_available_keys()}")

        # 获取该关键词对应的数组
        items = self.data[key]
        if not isinstance(items, list) or len(items) == 0:
            raise ValueError(f"关键词 '{key}' 对应的不是有效的非空数组")

        # 检查抽取数量是否合理
        if count < 1:
            raise ValueError(f"抽取数量必须大于0，当前为: {count}")

        if unique and count > len(items):
            raise ValueError(f"当不允许重复时，抽取数量({count})不能超过数组长度({len(items)})")

        # 执行随机抽取
        if unique:
            # 不允许重复，使用sample
            selected = random.sample(items, count)
        else:
            # 允许重复，使用choices
            selected = random.choices(items, k=count)

        # 如果只抽取一个，返回单个元素
        return selected[0] if count == 1 else selected


def convert_list_to_string(input_list):
    """
    将列表转换为包含单引号的字符串形式，如['a', 'b']

    参数:
        input_list: 要转换的列表

    返回:
        转换后的字符串
    """
    # 确保输入是列表
    if not isinstance(input_list, list):
        raise TypeError("输入必须是列表类型")

    # 处理空列表情况
    if not input_list:
        return "[]"

    # 对列表中的每个元素进行处理，添加单引号
    quoted_elements = [f"'{str(element)}'" for element in input_list]

    # 拼接成最终的字符串格式
    return f"[{', '.join(quoted_elements)}]"

# 使用示例
if __name__ == "__main__":
    # 替换为你的JSON文件路径
    json_file_path = "../data_persona/profile_ref.json"

    try:
        selector = JSONRandomSelector(json_file_path)

        # 查看可用的关键词
        print("可用关键词:", selector.get_available_keys())

        # 示例1: 随机抽取3个不重复的年龄
        ages = selector.random_select("年龄", 3)
        print(f"随机抽取的3个年龄: {ages}")

        # 示例2: 随机抽取5个不重复的住址
        addresses = selector.random_select("住址", 5)
        print(f"随机抽取的5个住址: {addresses}")

        # 示例3: 随机抽取1个年龄
        single_age = selector.random_select("年龄", 1)
        print(f"随机抽取的1个年龄: {single_age}")

        # 示例4: 允许重复，抽取10个住址
        repeated_addresses = selector.random_select("住址", 10, unique=False)
        print(f"允许重复的10个住址: {repeated_addresses}")
        print(convert_list_to_string(["a", "b", "c"]))  # 英文元素
        print(convert_list_to_string([1, 2, 3]))  # 数字元素
        print(convert_list_to_string(["混合", 123, "测试"]))  # 混合类型
    except Exception as e:
        print(f"发生错误: {str(e)}")
