import sys
import os
import time
import argparse
import subprocess
import json


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

    # 交互参数
    parser.add_argument('--interactive', action='store_true',
                        help='启用交互模式，情节优化时迭代与LLM交互直到用户输入包含"结束"')

    # 功能控制参数
    parser.add_argument('--generate-phone-data', type=int, default=1,
                        help='是否生成手机数据（默认：1）')
    parser.add_argument('--generate-monthly-report', type=int, default=1,
                        help='是否执行月度报告的生成（默认：1）')
    parser.add_argument('--generate-qa', type=int, default=1,
                        help='是否生成QA（默认：1）')
    parser.add_argument('--year', type=int, default=2025,
                        help='生成数据的年份（默认：2025）')
    parser.add_argument('--dry-run', action='store_true',
                        help='仅创建占位文件，不实际生成数据（用于测试流程）')

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
        script_dir = os.path.dirname(os.path.abspath(__file__))
        cmd = [sys.executable, os.path.join(script_dir, 'run', 'draft_gen.py')]
        
        # 添加参数
        if args.base_path:
            cmd.extend(['--base-path', args.base_path])
        if args.process_path:
            cmd.extend(['--process-path', args.process_path])
        if args.instance_id is not None:
            cmd.extend(['--instance-id', str(args.instance_id)])
        if args.max_workers is not None:
            cmd.extend(['--max-workers', str(args.max_workers)])
        if args.interactive:
            cmd.append('--interactive')

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
        script_dir = os.path.dirname(os.path.abspath(__file__))
        cmd = [sys.executable, os.path.join(script_dir, 'run', 'simulator.py')]
        
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


def run_qa_gen(args):
    """
    运行QA生成系统
    :param args: 命令行参数
    :return: 是否成功运行
    """
    print(f"\n{'='*60}")
    print(f"开始运行: QA生成系统")
    print(f"开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    try:
        # 构建命令行参数
        cmd = [
            sys.executable,
            '-u',  # 强制无缓冲输出
            os.path.join(os.path.dirname(__file__), 'run', 'qa_gen.py'),
            '--data-path', args.base_path,
            '--year', str(args.year)
        ]

        print(f"执行命令: {' '.join(cmd)}")

        # 运行脚本
        result = subprocess.run(cmd, check=True, stdout=None, stderr=None)

        print(f"\n{'='*60}")
        print(f"QA生成系统运行成功!")
        print(f"结束时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n{'='*60}")
        print(f"错误: QA生成系统运行失败!")
        print(f"退出码: {e.returncode}")
        print(f"{'='*60}")
        return False
    except Exception as e:
        print(f"\n{'='*60}")
        print(f"错误: 运行QA生成系统时发生异常!")
        print(f"错误信息: {str(e)}")
        print(f"{'='*60}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    # 解析命令行参数
    args = parse_args()

    # 将 base-path 转换为绝对路径
    # 规则：
    # - 绝对路径：直接使用
    # - 相对路径 .. 开头：相对于 scripts/ 解析
    # - 其他相对路径：相对于项目根目录解析
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    if args.base_path:
        if os.path.isabs(args.base_path):
            pass  # 绝对路径直接使用
        elif args.base_path.startswith('..'):
            # ../ 开头，相对于 scripts/ 解析
            args.base_path = os.path.join(script_dir, args.base_path)
        else:
            # 其他相对路径，相对于项目根目录解析
            args.base_path = os.path.join(project_root, args.base_path)

    # 设置工作目录为脚本所在目录
    os.chdir(script_dir)

    # 将项目根目录添加到 sys.path，确保可以导入 src 模块
    project_root = os.path.dirname(script_dir)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    # DRY_RUN 模式：创建所有占位文件
    if args.dry_run:
        print(f"\n{'='*60}")
        print(f"[DRY RUN] 创建占位文件")
        print(f"{'='*60}")

        # 确保 base_path 目录存在
        os.makedirs(args.base_path, exist_ok=True)

        # 创建核心占位文件
        placeholder_files = ['daily_draft.json', 'daily_event.json', 'event_tree.json']
        for filename in placeholder_files:
            filepath = os.path.join(args.base_path, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump({}, f)
            print(f"已创建占位文件: {filepath}")

        # 创建 process 文件夹及占位文件
        process_folder = os.path.join(args.base_path, args.process_path)
        os.makedirs(process_folder, exist_ok=True)
        with open(os.path.join(process_folder, 'final_timeline.json'), 'w', encoding='utf-8') as f:
            json.dump({}, f)
        print(f"已创建: {process_folder}/final_timeline.json")

        # 创建 phone_data 占位文件
        phone_data_dir = os.path.join(args.base_path, 'phone_data')
        os.makedirs(phone_data_dir, exist_ok=True)
        with open(os.path.join(phone_data_dir, 'contact.json'), 'w', encoding='utf-8') as f:
            json.dump([], f)
        print(f"已创建占位文件: {phone_data_dir}/contact.json")

        # 创建 QA 占位文件
        qa_dir = os.path.join(args.base_path, 'QA_all')
        os.makedirs(qa_dir, exist_ok=True)
        with open(os.path.join(qa_dir, 'QA.json'), 'w', encoding='utf-8') as f:
            json.dump([], f)
        print(f"已创建占位文件: {qa_dir}/QA.json")

        # 创建 summary 占位文件
        summary_dir = os.path.join(args.base_path, 'summary')
        os.makedirs(summary_dir, exist_ok=True)
        with open(os.path.join(summary_dir, 'all_monthly_health_reports.json'), 'w', encoding='utf-8') as f:
            json.dump([], f)
        print(f"已创建占位文件: {summary_dir}/all_monthly_health_reports.json")

        print(f"\n{'='*60}")
        print(f"[DRY RUN] 所有占位文件创建完成")
        print(f"{'='*60}")
        sys.exit(0)

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

        # 调用 check_event_matching 进行事件匹配，为 daily_event 等文件添加匹配字段
        print(f"\n{'='*60}")
        print(f"开始执行事件匹配分析")
        print(f"{'='*60}")

        try:
            from src.lifebench.event.tools.check_event_matching import main as check_event_matching_main

            # 使用 process_folder 作为数据路径进行事件匹配
            # match_main 会更新 event_tree.json、daily_draft.json、daily_event.json
            check_event_matching_main(base_path=args.base_path, output_path=args.base_path)

            print(f"\n{'='*60}")
            print(f"事件匹配分析完成")
            print(f"{'='*60}")
        except Exception as e:
            print(f"\n{'='*60}")
            print(f"错误: 事件匹配分析时发生异常!")
            print(f"错误信息: {str(e)}")
            print(f"{'='*60}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

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
                '--file-path', args.base_path + '/',
                '--start-time', '2025-01-01',  # 使用默认开始日期
                '--end-time', '2025-12-31',    # 使用默认结束日期
                '--max-workers', '40',          # 使用默认线程数
            ]

            # 执行phone_gen.py脚本
            try:
                result = subprocess.run(phone_gen_cmd, check=True, capture_output=True, encoding='utf-8', errors='ignore')
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

        # 根据参数决定是否生成QA
        if args.generate_qa == 1:
            print(f"\n{'='*60}")
            print(f"开始生成QA...")
            print(f"{'='*60}")

            if not run_qa_gen(args):
                print(f"\n{'='*60}")
                print(f"错误: QA生成系统运行失败!")
                print(f"{'='*60}")
                sys.exit(1)
        else:
            print(f"\n{'='*60}")
            print(f"跳过生成QA")
            print(f"{'='*60}")

        sys.exit(0)
    else:
        sys.exit(1)