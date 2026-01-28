import json
import os
import tiktoken

def calculate_text_length(item):
    """计算单个条目的文本总长度"""
    total_length = 0
    if isinstance(item, dict):
        for key, value in item.items():
            total_length += calculate_text_length(value)
    elif isinstance(item, list):
        for element in item:
            total_length += calculate_text_length(element)
    elif isinstance(item, str):
        total_length += len(item)
    return total_length

def calculate_token_count(item, encoding_name="cl100k_base"):
    """计算单个条目的token数目"""
    # 获取编码
    encoding = tiktoken.get_encoding(encoding_name)
    total_tokens = 0
    if isinstance(item, dict):
        for key, value in item.items():
            total_tokens += calculate_token_count(value)
    elif isinstance(item, list):
        for element in item:
            total_tokens += calculate_token_count(element)
    elif isinstance(item, str):
        total_tokens += len(encoding.encode(item))
    elif isinstance(item, (int, float, bool)):
        total_tokens += len(encoding.encode(str(item)))
    return total_tokens

def analyze_file(file_path):
    """分析单个JSON文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 计算条目数量
        if isinstance(data, list):
            item_count = len(data)
        elif isinstance(data, dict):
            # 如果是字典，假设键是类型，值是列表
            item_count = sum(len(value) for value in data.values() if isinstance(value, list))
        else:
            item_count = 0
        
        # 计算总文本量和总token数
        total_text_length = 0
        total_token_count = 0
        if isinstance(data, list):
            for item in data:
                total_text_length += calculate_text_length(item)
                total_token_count += calculate_token_count(item)
        elif isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, list):
                    for item in value:
                        total_text_length += calculate_text_length(item)
                        total_token_count += calculate_token_count(item)
                else:
                    total_text_length += calculate_text_length(value)
                    total_token_count += calculate_token_count(value)
        
        # 计算平均值
        average_text_length = total_text_length / item_count if item_count > 0 else 0
        average_token_count = total_token_count / item_count if item_count > 0 else 0
        
        return item_count, total_text_length, average_text_length, total_token_count, average_token_count
        
    except Exception as e:
        print(f"处理文件 {file_path} 时出错: {e}")
        return 0, 0, 0, 0, 0

def main():
    """主函数"""
    # 设置文件路径
    directory = "D:\\pyCharmProjects\\pythonProject4\\output\\maxiaomei\\phone_data"
    
    # 获取所有JSON文件
    json_files = [f for f in os.listdir(directory) if f.endswith('.json')]
    
    print("手机操作统计结果：")
    print("-" * 90)
    print(f"{'操作类型':<20} {'条目数量':<10} {'总文本量':<10} {'平均文本量':<10} {'总token数':<10} {'平均token数':<10}")
    print("-" * 90)
    
    # 遍历所有文件进行分析
    for file_name in json_files:
        file_path = os.path.join(directory, file_name)
        item_count, total_text, avg_text, total_tokens, avg_tokens = analyze_file(file_path)
        
        # 提取操作类型名称（去掉.json和event_前缀）
        operation_type = file_name.replace('.json', '')
        if operation_type.startswith('event_'):
            operation_type = operation_type[6:]
        
        print(f"{operation_type:<20} {item_count:<10} {total_text:<10} {avg_text:<10.2f} {total_tokens:<10} {avg_tokens:<10.2f}")
    
    print("-" * 90)

if __name__ == "__main__":
    main()