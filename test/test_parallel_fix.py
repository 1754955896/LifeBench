import subprocess
import os
import json
import shutil

# 测试配置
output_dir = "D:\pyCharmProjects\pythonProject4\test_output"
start_date = "2025-01-01"
end_date = "2025-01-03"
max_workers = 20

# 清理测试目录
if os.path.exists(output_dir):
    shutil.rmtree(output_dir)
os.makedirs(output_dir)

# 复制必要的配置文件
shutil.copy("D:\pyCharmProjects\pythonProject4\data\xujing\persona.json", output_dir)

# 创建phone_data目录
os.makedirs(os.path.join(output_dir, "phone_data"))

# 复制联系人文件
shutil.copy("D:\pyCharmProjects\pythonProject4\data\xujing\phone_data\contact.json", os.path.join(output_dir, "phone_data"))

print("开始测试修改后的代码...")

# 运行phone_gen.py
try:
    result = subprocess.run([
        "python", "D:\pyCharmProjects\pythonProject4\phone_gen.py",
        "--file-path", output_dir + "\\",
        "--start-time", start_date,
        "--end-time", end_date,
        "--max-workers", str(max_workers)
    ], check=True, capture_output=True, text=True, encoding="utf-8")
    
    print("\n命令执行成功！输出：")
    print(result.stdout)
    
    # 检查生成的文件
    phone_data_dir = os.path.join(output_dir, "phone_data")
    generated_files = [f for f in os.listdir(phone_data_dir) if f.endswith(".json")]
    
    print("\n生成的文件：")
    for file in generated_files:
        file_path = os.path.join(phone_data_dir, file)
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"{file}: {len(data)} 条记录")
        
        # 检查是否有数据
        if len(data) == 0:
            print(f"警告：文件 {file} 没有数据")
            
except subprocess.CalledProcessError as e:
    print("\n命令执行失败！错误：")
    print(e.stderr)
    print(e.stdout)
except Exception as e:
    print(f"\n测试过程中发生错误：{str(e)}")

print("\n测试完成！")