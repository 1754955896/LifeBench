import os
import json
import re
from concurrent.futures import ThreadPoolExecutor

# 源目录（已翻译的文件目录）
source_dir = "D:\pyCharmProjects\pythonProject4\life_bench_data\data_en"

# 需要去除的前缀
PREFIX_TO_REMOVE = "Please translate the following Chinese text into English, maintaining the original format and semantics:"

# 检查字符串是否包含需要去除的前缀
def fix_string(text):
    if isinstance(text, str):
        # 去除前缀
        if text.startswith(PREFIX_TO_REMOVE):
            fixed_text = text[len(PREFIX_TO_REMOVE):].strip()
            print(f"修复字符串: {text[:50]}... -> {fixed_text[:50]}...")
            return fixed_text
    return text

# 递归修复JSON数据
def fix_json_data(data):
    if isinstance(data, dict):
        return {key: fix_json_data(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [fix_json_data(item) for item in data]
    elif isinstance(data, str):
        return fix_string(data)
    else:
        return data

# 修复单个文件
def fix_file(file_path):
    if file_path.endswith('.json'):
        # 处理JSON文件
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            fixed_data = fix_json_data(data)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(fixed_data, f, ensure_ascii=False, indent=2)
            
            print(f"已修复JSON文件: {file_path}")
        except Exception as e:
            print(f"处理JSON文件失败 {file_path}: {e}")
    elif file_path.endswith('.txt'):
        # 处理TXT文件
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            fixed_content = fix_string(content)
            
            if fixed_content != content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(fixed_content)
                print(f"已修复TXT文件: {file_path}")
        except Exception as e:
            print(f"处理TXT文件失败 {file_path}: {e}")

# 主函数
def main():
    # 收集所有需要修复的文件
    all_files = []
    for root, dirs, files in os.walk(source_dir):
        for file in files:
            file_path = os.path.join(root, file)
            all_files.append(file_path)
    
    print(f"共找到 {len(all_files)} 个文件需要检查")
    
    # 使用ThreadPoolExecutor进行并行修复
    max_workers = 24
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        executor.map(fix_file, all_files)
    
    print("所有文件修复完成！")

if __name__ == "__main__":
    main()