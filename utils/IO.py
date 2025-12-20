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


def write_json_file(file_path, data):
    """
    将数据写入JSON文件

    参数:
        file_path (str): JSON文件的路径
        data (dict/list): 要写入的数据

    返回:
        bool: 如果写入成功则返回True，否则返回False
    """
    try:
        # 创建文件所在目录（如果不存在）
        import os
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            
        # 打开并写入JSON文件
        with open(file_path, 'w', encoding='utf-8') as file:
            # 将数据写入文件，使用indent=2增加可读性，ensure_ascii=False保留中文字符
            json.dump(data, file, ensure_ascii=False, indent=2)
        return True

    except PermissionError:
        print(f"错误: 没有写入文件 '{file_path}' 的权限")
    except Exception as e:
        print(f"写入文件时发生错误: {str(e)}")

    return False