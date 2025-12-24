import subprocess
import sys
import time
import os
import json
import pypinyin


def run_script(script_path, description, args=None):
    """
    运行指定的Python脚本
    :param script_path: 脚本路径
    :param description: 脚本描述（用于日志）
    :param args: 传递给脚本的命令行参数
    :return: 是否成功运行
    """
    print(f"\n{'='*60}")
    print(f"开始运行: {description}")
    print(f"脚本路径: {script_path}")
    print(f"开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    # 构建命令
    cmd = [sys.executable, script_path]
    if args:
        cmd.extend(args)
    
    try:
        # 运行脚本并等待完成
        result = subprocess.run(cmd, check=True, capture_output=False, text=True)
        
        print(f"\n{'='*60}")
        print(f"{description} 运行成功!")
        print(f"结束时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n{'='*60}")
        print(f"错误: {description} 运行失败!")
        print(f"退出码: {e.returncode}")
        print(f"错误信息: {e.stderr}")
        print(f"{'='*60}")
        return False
    except Exception as e:
        print(f"\n{'='*60}")
        print(f"错误: 运行 {description} 时发生异常!")
        print(f"异常信息: {str(e)}")
        print(f"{'='*60}")
        return False

def run_for_persona(persona_data, persona_folder, instance_id):
    """
    为单个画像执行完整流程
    :param persona_data: 画像数据
    :param persona_folder: 画像文件夹路径
    :param instance_id: 人物实例ID
    :return: 是否成功运行
    """
    # 创建文件夹（如果不存在）
    folder_exists = os.path.exists(persona_folder)
    if not folder_exists:
        os.makedirs(persona_folder, exist_ok=True)
        print(f"\n{'='*60}")
        print(f"已为人物 {persona_data.get('name', '未知')} 创建文件夹: {persona_folder}")
    
    # 保存persona.json（如果文件夹是新创建的）
    persona_json_path = os.path.join(persona_folder, "persona.json")
    if not folder_exists or not os.path.exists(persona_json_path):
        with open(persona_json_path, 'w', encoding='utf-8') as f:
            json.dump(persona_data, f, ensure_ascii=False, indent=2)
        print(f"已保存persona.json文件")
    else:
        print(f"\n{'='*60}")
        print(f"人物 {persona_data.get('name', '未知')} 的文件夹已存在: {persona_folder}")
        print(f"跳过保存persona.json文件")
    
    # 检查是否需要运行event_gen.py
    event_decompose_path = os.path.join(persona_folder, "event_decompose_dfs.json")
    need_run_event_gen = not os.path.exists(event_decompose_path)
    
    # 定义脚本路径和描述
    scripts = []
    
    # 如果需要运行event_gen.py，则添加到脚本列表
    if need_run_event_gen:
        scripts.append({
            "path": "event_gen.py",
            "description": "人物生成模块",
            "args": ["--base-path", persona_folder+'/', "--instance-id", str(instance_id)]
        })
    else:
        print(f"检测到event_decompose_dfs.json文件，跳过运行人物生成模块")
    
    # 添加其他脚本
    # 检查是否需要运行simulator.py
    simulator_output_path = os.path.join(persona_folder, 'output', 'outputs.json')
    if not os.path.exists(simulator_output_path):
        scripts.append({
            "path": "simulator.py",
            "description": "模拟生成模块",
            "args": ["--file-path", persona_folder+'/', "--instance-id", str(instance_id)]
        })
    else:
        print(f"检测到output/outputs.json文件，跳过运行模拟生成模块")
    
    scripts.append({
        "path": "phone_gen.py",
        "description": "手机操作生成模块",
        "args": ["--file-path", persona_folder+'/']
    })
    
    # 按顺序运行每个脚本
    all_success = True
    for script in scripts:
        if not run_script(script["path"], script["description"], script["args"]):
            all_success = False
            print(f"\n❌ 流程中断: {script['description']} 运行失败")
            break
    
    return all_success

def main():
    """
    主函数，实现批量运行功能
    """
    
    # 设置工作目录为脚本所在目录
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # 读取person.json文件
    person_json_path = "output/person.json"
    if not os.path.exists(person_json_path):
        print(f"❌ 错误: {person_json_path} 文件不存在")
        return 1
    
    with open(person_json_path, 'r', encoding='utf-8') as f:
        personas = json.load(f)
    
    if not isinstance(personas, list):
        print(f"❌ 错误: {person_json_path} 不是有效的画像数组")
        return 1
    
    # 记录总开始时间
    total_start_time = time.time()
    print(f"\n{'='*80}")
    print(f"开始执行批量生成流程")
    print(f"总开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"总共有 {len(personas)} 个画像需要处理")
    print(f"{'='*80}")
    
    # 为每个画像执行流程
    success_count = 0
    for i, persona in enumerate(personas):
        print(f"\n{'='*80}")
        print(f"开始处理第 {i+1}/{len(personas)} 个画像")
        print(f"{'='*80}")
        
        # 获取人物姓名
        name = persona.get('name', f'person_{i+1}')
        
        # 将姓名转换为拼音
        pinyin_name = ''.join(pypinyin.lazy_pinyin(name))
        
        # 创建文件夹名称
        persona_folder_name = f"{pinyin_name}_{i+1}"
        persona_folder = os.path.join("output", persona_folder_name)
        
        # 执行流程
        if run_for_persona(persona, persona_folder, i+1):
            success_count += 1
            print(f"\n✅ 人物 {name} 处理成功!")
        else:
            print(f"\n❌ 人物 {name} 处理失败!")
    
    # 记录总结束时间
    total_end_time = time.time()
    total_duration = total_end_time - total_start_time
    
    print(f"\n{'='*80}")
    print(f"批量生成流程执行结束")
    print(f"总结束时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"总耗时: {time.strftime('%H:%M:%S', time.gmtime(total_duration))}")
    print(f"总处理人物数: {len(personas)}")
    print(f"成功处理人物数: {success_count}")
    print(f"失败处理人物数: {len(personas) - success_count}")
    
    if success_count == len(personas):
        print(f"✅ 所有人物处理成功!")
    else:
        print(f"❌ 部分人物处理失败!")
    print(f"{'='*80}")
    
    return 0 if success_count == len(personas) else 1

if __name__ == "__main__":
    sys.exit(main())