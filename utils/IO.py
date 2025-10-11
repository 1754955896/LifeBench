import json


def read_json_file(file_path):
    """
    从JSON文件中读取数据并返回

    参数:
        file_path (str): JSON文件的路径

    返回:
        dict/list: 解析后的JSON数据，如果出错则返回None
    """
    try:
        # 打开并读取JSON文件
        with open(file_path, 'r', encoding='utf-8') as file:
            # 解析JSON数据
            json_data = json.load(file)
            return json_data

    except FileNotFoundError:
        print(f"错误: 文件 '{file_path}' 不存在")
    except json.JSONDecodeError:
        print(f"错误: 文件 '{file_path}' 不是有效的JSON格式")
    except Exception as e:
        print(f"读取文件时发生错误: {str(e)}")

    return None