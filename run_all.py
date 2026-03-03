import subprocess
import sys
import time
import os
import json
import pypinyin
import shutil
import argparse
# 获取项目根目录并加入 sys.path
sys.path.append('D:\pyCharmProjects\pythonProject4')

def parse_args():
    parser = argparse.ArgumentParser(description='批量运行人物数据生成')
    parser.add_argument('--persona-folder', type=str, default='data/',
                        help='人物数据文件夹路径')
    parser.add_argument('--start-id', type=int, default=0,
                        help='开始的人物ID')
    parser.add_argument('--end-id', type=int, default=0,
                        help='结束的人物ID')
    
    # 添加run.py支持的参数
    parser.add_argument('--process-path', type=str, default='process/',
                        help='处理文件路径（相对于base-path）')
    parser.add_argument('--max-workers', type=int, default=None,
                        help='最大工作线程数（默认：CPU核心数×2）')
    parser.add_argument('--generate-phone-data', type=int, default=1,
                        help='是否生成手机数据（默认：1）')
    parser.add_argument('--generate-monthly-report', type=int, default=1,
                        help='是否执行月度报告的生成（默认：1）')
    parser.add_argument('--generate-qa', type=int, default=1,
                        help='是否执行QA生成（默认：1）')
    parser.add_argument('--year', type=int, default=2025,
                        help='生成数据的年份（默认：2025）')
    return parser.parse_args()

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

def run_for_persona(persona_data, persona_folder, instance_id, args):
    """
    为单个画像执行完整流程
    :param persona_data: 画像数据
    :param persona_folder: 画像文件夹路径
    :param instance_id: 人物实例ID
    :param args: 命令行参数
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
    
    # 检查是否需要运行run.py（基于关键输出文件的存在性）
    # run.py会自动检查其内部各个模块是否需要运行
    # 这里我们可以基于最终合并的QA文件来判断是否需要运行整个流程
    merged_qa_path = os.path.join(persona_folder, "QA", "QA.json")
    need_run = not os.path.exists(merged_qa_path)
    
    if need_run:
        # 构建run.py的命令行参数
        run_args = [
            "--base-path", persona_folder+'/', 
            "--instance-id", str(instance_id),
            "--process-path", args.process_path,
            "--generate-phone-data", str(args.generate_phone_data),
            "--generate-monthly-report", str(args.generate_monthly_report),
            "--generate-qa", str(args.generate_qa),
            "--year", str(args.year)
        ]
        
        # 添加可选参数
        if args.max_workers is not None:
            run_args.extend(["--max-workers", str(args.max_workers)])
        
        # 调用集成好的run.py
        scripts = [{
            "path": "run.py",
            "description": "集成生成模块",
            "args": run_args
        }]
    else:
        print(f"检测到合并后的QA文件: {merged_qa_path}")
        print(f"跳过运行集成生成模块")
        scripts = []

    
    # 按顺序运行每个脚本（现在只有run.py一个脚本）
    all_success = True
    for script in scripts:
        if not run_script(script["path"], script["description"], script["args"]):
            all_success = False
            print(f"\n❌ 流程中断: {script['description']} 运行失败")
            break
    
    # 删除memory_file目录下的所有文件
    memory_file_dir = "memory_file"
    if os.path.exists(memory_file_dir):
        # 遍历目录中的所有文件并删除
        for filename in os.listdir(memory_file_dir):
            file_path = os.path.join(memory_file_dir, filename)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
                    print(f"已删除临时文件: {file_path}")
            except Exception as e:
                print(f"删除文件 {file_path} 时出错: {str(e)}")
    
    return all_success

def main():
    """
    主函数，实现批量运行功能
    """
    
    # 解析命令行参数
    args = parse_args()
    
    # 设置工作目录为脚本所在目录
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # 读取person.json文件
    person_json_path = os.path.join(args.persona_folder, "person.json")
    if not os.path.exists(person_json_path):
        print(f"❌ 错误: {person_json_path} 文件不存在")
        return 1
    
    with open(person_json_path, 'r', encoding='utf-8') as f:
        personas = json.load(f)
    
    if not isinstance(personas, list):
        print(f"❌ 错误: {person_json_path} 不是有效的画像数组")
        return 1
    
    # 根据start-id和end-id过滤人物
    if args.start_id > 0 or args.end_id > 0:
        start_idx = args.start_id - 1 if args.start_id > 0 else 0
        end_idx = args.end_id if args.end_id > 0 else len(personas)
        personas = personas[start_idx:end_idx]
        print(f"\n根据ID范围过滤后，需要处理的人物数: {len(personas)}")
    
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
        if run_for_persona(persona, persona_folder, i+1, args):
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