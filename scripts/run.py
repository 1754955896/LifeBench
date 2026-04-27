import sys
import os
import time
import argparse
import subprocess


def parse_args():
    """
    解析命令行参数
    :return: 解析后的参数对象
    """
    parser = argparse.ArgumentParser(description='年度时间线草稿生成系统')
    
    # 路径参数
    parser.add_argument('--base-path', type=str, default='fenghaoran/',
                        help='基础数据路径')
    parser.add_argument('--process-path', type=str, default='process/',
                        help='处理文件路径（相对于base-path，同时作为除每日状态外的其他数据输出路径）')
    parser.add_argument('--instance-id', type=int, default=0,
                        help='人物实例ID')
    
    # 线程/进程参数
    parser.add_argument('--max-workers', type=int, default=None,
                        help='最大工作线程数（默认：CPU核心数×2）')
    
    # 功能控制参数
    parser.add_argument('--generate-phone-data', type=int, default=1,
                        help='是否生成手机数据（默认：1）')
    parser.add_argument('--generate-monthly-report', type=int, default=1,
                        help='是否执行月度报告的生成（默认：1）')
    
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
        keep_files = {'daily_draft.json', 'daily_event.json', 'persona.json','event_tree.json'}
        
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
        
        # 根据参数决定是否执行月度报告生成
        if args.generate_monthly_report == 1:
            # 调用parallel_monthly_health_report_generation生成月度健康报告
            print(f"\n{'='*60}")
            print(f"开始生成月度健康报告")
            print(f"{'='*60}")
            
            try:
                # 导入EventRefiner类
                from src.lifebench.event.draft.event_refiner import EventRefiner
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
        else:
            print(f"\n{'='*60}")
            print(f"跳过生成月度健康报告")
            print(f"{'='*60}")
        
        # 根据参数决定是否生成手机数据
        if args.generate_phone_data == 1:
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
        
        sys.exit(0)
    else:
        sys.exit(1)