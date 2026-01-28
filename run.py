import sys
import os
import time
import argparse
import subprocess
import json

def merge_qa_files(base_path):
    """
    合并QA文件并移动原文件到指定目录
    
    Args:
        base_path: 基础数据路径
    """
    print(f"\n{'='*60}")
    print(f"开始合并QA文件...")
    print(f"{'='*60}")
    
    # 定义需要合并的QA文件列表
    qa_files = [
        "muti_hop_qa.json",
        "reasoning_qa.json",
        "single_hop_qa.json",
        "updating_qa.json",
        "user_modeling_qa.json"
    ]
    
    # 初始化合并后的QA列表
    merged_qa = []
    
    # 初始化统计字典
    statistics = {
        "file_distribution": {},  # 每个文件的问答对数量
        "type_distribution": {},  # 不同类型问答对的分布（基于question_type字段）
        "total_count": 0  # 总问答对数量
    }
    
    # 确保输出目录存在
    output_dir = os.path.join(base_path, "QA")
    process_dir = os.path.join(base_path, "process")
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"创建输出目录: {output_dir}")
    
    if not os.path.exists(process_dir):
        os.makedirs(process_dir)
        print(f"创建处理目录: {process_dir}")
    
    # 遍历每个QA文件
    for qa_file in qa_files:
        # 先检查base_path下是否存在
        file_path = os.path.join(base_path, qa_file)
        file_exists = os.path.exists(file_path)
        
        # 如果base_path下不存在，检查process_dir下是否存在
        if not file_exists:
            file_path = os.path.join(process_dir, qa_file)
            file_exists = os.path.exists(file_path)
        
        if file_exists:
            try:
                # 打开并读取JSON文件
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 检查数据类型是否为列表
                if isinstance(data, list):
                    # 处理single_hop_qa.json文件，确保每个问答对都有question_type字段
                    if qa_file == "single_hop_qa.json":
                        print(f"正在为 {qa_file} 中的所有问答对添加question_type:'single_hop'字段...")
                        processed_data = []
                        for qa in data:
                            # 添加或更新question_type字段
                            qa["question_type"] = "single_hop"
                            processed_data.append(qa)
                        merged_qa.extend(processed_data)
                        file_data = processed_data
                    else:
                        merged_qa.extend(data)
                        file_data = data
                    
                    # 更新文件分布统计
                    file_name = os.path.splitext(qa_file)[0]  # 获取不带扩展名的文件名
                    statistics["file_distribution"][file_name] = len(data)
                    
                    # 统计当前文件中不同类型的问答对
                    for qa in file_data:
                        # 检查问答对是否有question_type字段
                        if "question_type" in qa:
                            qa_type = qa["question_type"]
                            if qa_type in statistics["type_distribution"]:
                                statistics["type_distribution"][qa_type] += 1
                            else:
                                statistics["type_distribution"][qa_type] = 1
                    
                    print(f"成功合并 {qa_file}，添加了 {len(data)} 个问答对")
                    
                    # 只有当文件在base_path下时才移动到process目录
                    if file_path.startswith(base_path) and not file_path.startswith(process_dir):
                        target_path = os.path.join(process_dir, qa_file)
                        os.rename(file_path, target_path)
                        print(f"已将 {qa_file} 移动到 {target_path}")
                else:
                    print(f"警告：{qa_file} 的数据类型不是列表，跳过该文件")
                    
            except json.JSONDecodeError:
                print(f"警告：{qa_file} 不是有效的JSON文件，跳过该文件")
            except Exception as e:
                print(f"处理 {qa_file} 时出错：{str(e)}")
        else:
            print(f"警告：{qa_file} 文件不存在于 {base_path} 或 {process_dir}，跳过该文件")
    
    # 更新总问答对数量
    statistics["total_count"] = len(merged_qa)
    
    # 按照ask_time字段排序（升序）
    print(f"\n正在按ask_time字段对问答对进行排序...")
    merged_qa_sorted = sorted(merged_qa, key=lambda x: x.get("ask_time", "9999-99"))
    
    # 将排序后的QA列表写入新的JSON文件
    output_file = os.path.join(output_dir, "QA.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(merged_qa_sorted, f, ensure_ascii=False, indent=2)
    
    # 打印详细统计信息
    print(f"\n{'='*60}")
    print(f"合并完成！")
    print(f"所有问答对已合并到 {output_file}")
    print(f"总共合并了 {len(merged_qa)} 个问答对")
    
    print(f"\n=== 数据分布统计 ===")
    print(f"\n1. 按文件分布：")
    for file_name, count in statistics["file_distribution"].items():
        percentage = (count / statistics["total_count"]) * 100 if statistics["total_count"] > 0 else 0
        print(f"   {file_name}: {count} 个 ({percentage:.2f}%)")
    
    print(f"\n2. 按类型分布：")
    if statistics["type_distribution"]:
        for qa_type, count in statistics["type_distribution"].items():
            percentage = (count / statistics["total_count"]) * 100 if statistics["total_count"] > 0 else 0
            print(f"   {qa_type}: {count} 个 ({percentage:.2f}%)")
    else:
        print("   未找到带有question_type字段的问答对")
    
    # 统计没有question_type字段的问答对数量
    no_type_count = statistics["total_count"] - sum(statistics["type_distribution"].values())
    if no_type_count > 0:
        percentage = (no_type_count / statistics["total_count"]) * 100 if statistics["total_count"] > 0 else 0
        print(f"   无类型标识: {no_type_count} 个 ({percentage:.2f}%)")
    
    print(f"\n=== 统计结束 ===")
    print(f"{'='*60}")
    
    # 新增功能：处理phone_data文件夹
    print(f"\n{'='*60}")
    print(f"开始处理phone_data文件夹...")
    print(f"{'='*60}")
    
    # 1. 将base_path+phone_data文件夹中的所有json文件移动到base_path+process/phone_data2
    phone_data_dir = os.path.join(base_path, 'phone_data')
    phone_data2_dir = os.path.join(process_dir, 'phone_data2')
    
    # 确保phone_data2目录存在
    if not os.path.exists(phone_data2_dir):
        os.makedirs(phone_data2_dir)
        print(f"创建目录: {phone_data2_dir}")
    
    # 移动phone_data中的所有json文件到phone_data2
    if os.path.exists(phone_data_dir):
        for filename in os.listdir(phone_data_dir):
            if filename.endswith('.json') and filename != 'new':
                src_path = os.path.join(phone_data_dir, filename)
                dst_path = os.path.join(phone_data2_dir, filename)
                os.rename(src_path, dst_path)
                print(f"已将 {filename} 从 {phone_data_dir} 移动到 {phone_data2_dir}")
    
    # 2. 把base_path+phone_data/new的json文件移动到base_path+phone_data
    new_phone_data_dir = os.path.join(phone_data_dir, 'new')
    if os.path.exists(new_phone_data_dir):
        for filename in os.listdir(new_phone_data_dir):
            if filename.endswith('.json'):
                src_path = os.path.join(new_phone_data_dir, filename)
                dst_path = os.path.join(phone_data_dir, filename)
                os.rename(src_path, dst_path)
                print(f"已将 {filename} 从 {new_phone_data_dir} 移动到 {phone_data_dir}")
    
    # 3. 删除base_path+phone_data/new
    if os.path.exists(new_phone_data_dir):
        os.rmdir(new_phone_data_dir)
        print(f"已删除目录: {new_phone_data_dir}")
    
    print(f"\n{'='*60}")
    print(f"phone_data文件夹处理完成！")
    print(f"{'='*60}")


def parse_args():
    """
    解析命令行参数
    :return: 解析后的参数对象
    """
    parser = argparse.ArgumentParser(description='年度时间线草稿生成系统')
    
    # 路径参数
    parser.add_argument('--base-path', type=str, default='output/fenghaoran/',
                        help='基础数据路径')
    parser.add_argument('--process-path', type=str, default='process/',
                        help='处理文件路径（相对于base-path，同时作为除每日状态外的其他数据输出路径）')
    parser.add_argument('--instance-id', type=int, default=0,
                        help='人物实例ID')
    
    # 线程/进程参数
    parser.add_argument('--max-workers', type=int, default=None,
                        help='最大工作线程数（默认：CPU核心数×2）')
    
    # 功能控制参数
    parser.add_argument('--generate-phone-data', type=bool, default=False,
                        help='是否生成手机数据（默认：True）')
    parser.add_argument('--year', type=int, default=2025,
                        help='生成数据的年份（默认：2025）')
    
    return parser.parse_args()


def run_draft_gen(args):
    """
    运行年度时间线草稿生成系统
    :param args: 命令行参数
    :return: 是否成功运行
    """
    print(f"\n{'='*60}")
    print(f"开始运行: 年度时间线草稿生成系统")
    print(f"开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    try:
        # 构建命令行参数
        cmd = [sys.executable, os.path.join('run', 'draft_gen.py')]
        
        # 添加参数
        if args.base_path:
            cmd.extend(['--base-path', args.base_path])
        if args.process_path:
            cmd.extend(['--process-path', args.process_path])
        if args.instance_id is not None:
            cmd.extend(['--instance-id', str(args.instance_id)])
        if args.max_workers is not None:
            cmd.extend(['--max-workers', str(args.max_workers)])
        
        print(f"执行命令: {' '.join(cmd)}")
        
        # 运行脚本
        result = subprocess.run(cmd, check=True, capture_output=False, text=True)
        
        print(f"\n{'='*60}")
        print(f"年度时间线草稿生成系统运行成功!")
        print(f"结束时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n{'='*60}")
        print(f"错误: 年度时间线草稿生成系统运行失败!")
        print(f"退出码: {e.returncode}")
        print(f"{'='*60}")
        return False
    except Exception as e:
        print(f"\n{'='*60}")
        print(f"错误: 运行年度时间线草稿生成系统时发生异常!")
        print(f"错误信息: {str(e)}")
        print(f"{'='*60}")
        import traceback
        traceback.print_exc()
        return False


def run_simulator(args):
    """
    运行模拟器系统
    :param args: 命令行参数
    :return: 是否成功运行
    """
    print(f"\n{'='*60}")
    print(f"开始运行: 模拟器系统")
    print(f"开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    try:
        # 构建命令行参数
        cmd = [sys.executable, os.path.join('run', 'simulator.py')]
        
        # 添加参数（根据simulator.py的需求）
        if args.base_path:
            cmd.extend(['--file-path', args.base_path])
        if args.instance_id is not None:
            cmd.extend(['--instance-id', str(args.instance_id)])
        # 注意：不添加--refine-events参数，因为用户说这个参数已经没有用了
        
        print(f"执行命令: {' '.join(cmd)}")
        
        # 运行脚本
        result = subprocess.run(cmd, check=True, capture_output=False, text=True)
        
        print(f"\n{'='*60}")
        print(f"模拟器系统运行成功!")
        print(f"结束时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n{'='*60}")
        print(f"错误: 模拟器系统运行失败!")
        print(f"退出码: {e.returncode}")
        print(f"{'='*60}")
        return False
    except Exception as e:
        print(f"\n{'='*60}")
        print(f"错误: 运行模拟器系统时发生异常!")
        print(f"错误信息: {str(e)}")
        print(f"{'='*60}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    # 设置工作目录为脚本所在目录
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # 解析命令行参数
    args = parse_args()
    
    # 检查对应文件夹中是否存在daily_draft.json文件
    daily_draft_path = os.path.join(args.base_path, 'daily_draft.json')
    if os.path.exists(daily_draft_path):
        print(f"检测到{daily_draft_path}文件，跳过年度时间线草稿生成系统")
        draft_gen_success = True
    else:
        # 运行年度时间线草稿生成系统
        draft_gen_success = run_draft_gen(args)
    
    # 检查是否存在daily_event.json文件，如果存在则跳过simulator步骤
    daily_event_path = os.path.join(args.base_path, 'daily_event.json')
    if draft_gen_success:
        if os.path.exists(daily_event_path):
            print(f"\n{'='*60}")
            print(f"检测到{daily_event_path}文件，跳过模拟器系统")
            print(f"{'='*60}")
        else:
            # 运行模拟器系统
            simulator_success = run_simulator(args)
            if not simulator_success:
                sys.exit(1)
        
        # 移动除daily_draft、daily_event、persona外的其他json文件到process文件夹
        print(f"\n{'='*60}")
        print(f"开始移动文件到process文件夹")
        print(f"{'='*60}")
        
        # 确保process文件夹存在
        process_folder = os.path.join(args.base_path, args.process_path)
        os.makedirs(process_folder, exist_ok=True)
        
        # 要保留的文件名
        keep_files = {'daily_draft.json', 'daily_event.json', 'persona.json'}
        
        # 获取base_path下的所有json文件
        for filename in os.listdir(args.base_path):
            if filename.endswith('.json') and filename not in keep_files:
                src_path = os.path.join(args.base_path, filename)
                dst_path = os.path.join(process_folder, filename)
                
                # 如果目标文件已存在，先删除
                if os.path.exists(dst_path):
                    os.remove(dst_path)
                    print(f"已删除目标路径下的文件: {dst_path}")
                
                # 移动文件
                os.rename(src_path, dst_path)
                print(f"已移动文件: {filename} -> {args.process_path}/{filename}")
        
        print(f"\n{'='*60}")
        print(f"文件移动完成")
        print(f"{'='*60}")
        
        # 调用parallel_monthly_health_report_generation生成月度健康报告
        print(f"\n{'='*60}")
        print(f"开始生成月度健康报告")
        print(f"{'='*60}")
        
        try:
            # 导入EventRefiner类
            from event.event_refiner import EventRefiner
            import json
            
            # 加载persona数据
            persona_path = os.path.join(args.base_path, 'persona.json')
            with open(persona_path, 'r', encoding='utf-8') as f:
                persona_data = json.load(f)
            
            # 构建文件路径
            health_analysis_file = os.path.join(args.base_path, args.process_path, 'final_timeline.json')
            event_data_path = os.path.join(args.base_path, 'daily_draft.json')
            output_dir = os.path.join(args.base_path, 'summary')
            all_reports_file = os.path.join(output_dir, 'all_monthly_health_reports.json')
            context = "你是一个生活分析师，健康分析师，报告专家。"
            
            # 确保output_dir存在
            os.makedirs(output_dir, exist_ok=True)
            
            # 检查是否已经有月度报告文件
            if os.path.exists(all_reports_file):
                print(f"\n{'='*60}")
                print(f"月度健康报告已存在，跳过生成")
                print(f"报告文件位置: {all_reports_file}")
                print(f"{'='*60}")
            else:
                # 调用静态方法
                reports = EventRefiner.parallel_monthly_health_report_generation(
                    persona=persona_data,
                    event_data_path=event_data_path,
                    health_analysis_file=health_analysis_file,
                    output_dir=output_dir,
                    context=context
                )
                
                print(f"\n{'='*60}")
                print(f"月度健康报告生成完成")
                print(f"报告已保存至: {output_dir}")
                print(f"{'='*60}")
            
        except Exception as e:
            print(f"\n{'='*60}")
            print(f"错误: 生成月度健康报告时发生异常!")
            print(f"错误信息: {str(e)}")
            print(f"{'='*60}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
        
        # 根据参数决定是否生成手机数据
        if args.generate_phone_data:
            print(f"\n{'='*60}")
            print(f"开始生成手机数据...")
            print(f"{'='*60}")
            
            # 构建phone_gen.py的命令行参数
            phone_gen_cmd = [
                sys.executable,
                os.path.join(os.path.dirname(__file__), 'run', 'phone_gen.py'),
                '--file-path', args.base_path,
                '--start-time', '2025-01-01',  # 使用默认开始日期
                '--end-time', '2025-12-31',    # 使用默认结束日期
                '--max-workers', '40',          # 使用默认线程数
            ]
            
            # 执行phone_gen.py脚本
            try:
                result = subprocess.run(phone_gen_cmd, check=True, capture_output=True, text=True)
                print(f"\n{'='*60}")
                print(f"手机数据生成完成")
                print(f"{'='*60}")
            except subprocess.CalledProcessError as e:
                print(f"\n{'='*60}")
                print(f"错误: 生成手机数据时发生异常!")
                print(f"错误信息: {e.stderr}")
                print(f"{'='*60}")
                sys.exit(1)
        else:
            print(f"\n{'='*60}")
            print(f"跳过生成手机数据")
            print(f"{'='*60}")
        
        # 检查是否需要执行QA生成
        updating_qa_path = os.path.join(args.base_path, 'updating_qa.json')
        qa_folder_path = os.path.join(args.base_path, 'QA')
        process_path = os.path.join(args.base_path, 'process')
        process_updating_qa_path = os.path.join(process_path, 'updating_qa.json')

        if os.path.exists(updating_qa_path) or os.path.exists(qa_folder_path) or os.path.exists(process_updating_qa_path):
            print(f"\n{'='*60}")
            print(f"跳过生成问答数据")
            print(f"{'='*60}")
            if os.path.exists(updating_qa_path):
                print(f"原因: {updating_qa_path} 文件已存在")
            if os.path.exists(qa_folder_path):
                print(f"原因: {qa_folder_path} 文件夹已存在")
        else:
            # 调用QA_gen生成问答数据
            print(f"\n{'='*60}")
            print(f"开始生成问答数据...")
            print(f"{'='*60}")
            
            # 构建QA_gen.py的命令行参数
            qa_gen_cmd = [
                sys.executable,
                os.path.join(os.path.dirname(__file__), 'run', 'QA_gen.py'),
                '--data-path', args.base_path,
                '--year', str(args.year),
            ]
            
            # 执行QA_gen.py脚本
            try:
                result = subprocess.run(qa_gen_cmd, check=True, capture_output=True, text=True)
                print(f"\n{'='*60}")
                print(f"问答数据生成完成")
                print(f"{'='*60}")
            except subprocess.CalledProcessError as e:
                print(f"\n{'='*60}")
                print(f"错误: 生成问答数据时发生异常!")
                print(f"错误信息: {e.stderr}")
                print(f"{'='*60}")
                sys.exit(1)
        
        # 合并QA文件
        merge_qa_files(args.base_path)
        
        sys.exit(0)
    else:
        sys.exit(1)