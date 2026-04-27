import pandas as pd
import os

# 获取当前脚本所在目录
script_dir = os.path.dirname(os.path.abspath(__file__))

# 定义Excel文件路径
xlsx_file = os.path.join(script_dir, 'schema.xlsx')

# 定义输出CSV文件路径
csv_file = os.path.join(script_dir, 'event_schema.csv')

try:
    # 读取Excel文件
    # 如果Excel文件有多个sheet，可以指定sheet_name参数
    # 例如：df = pd.read_excel(xlsx_file, sheet_name='Sheet1')
    df = pd.read_excel(xlsx_file)
    
    # 将DataFrame写入CSV文件
    df.to_csv(csv_file, index=False, encoding='utf-8-sig')
    
    print(f"转换成功！Excel文件 '{xlsx_file}' 已转换为CSV文件 '{csv_file}'")
    print(f"转换的行数: {len(df)}")
    print(f"转换的列数: {len(df.columns)}")
    print(f"列名: {list(df.columns)}")
    
except Exception as e:
    print(f"转换失败: {str(e)}")