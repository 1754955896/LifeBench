import subprocess
import sys
import time
import os
import json
import pypinyin
import shutil
import argparse

def parse_args():
    parser = argparse.ArgumentParser(description='批量运行人物数据生成')
    parser.add_argument('--persona-folder', type=str, default='input/',
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
    parser.add_argument('--dry-run', action='store_true',
                        help='仅打印将要执行的操作，不实际运行')
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

def run_for_persona(persona_data, persona_folder, instance_id, args, location_data=None):
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
    if location_data is not None or not folder_exists or not os.path.exists(persona_json_path):
        with open(persona_json_path, 'w', encoding='utf-8') as f:
            json.dump(persona_data, f, ensure_ascii=False, indent=2)
        print(f"已保存persona.json文件")
    else:
        print(f"\n{'='*60}")
        print(f"人物 {persona_data.get('name', '未知')} 的文件夹已存在: {persona_folder}")
        print(f"跳过保存persona.json文件")

    # 新画像生成流程会输出与画像数组一一对齐的 location sidecar。
    # 在模拟开始前将对应项写入人物目录，确保 simulator 不再重新随机生成地址。
    if location_data is not None:
        location_json_path = os.path.join(persona_folder, "location.json")
        with open(location_json_path, 'w', encoding='utf-8') as f:
            json.dump(location_data, f, ensure_ascii=False, indent=2)
        print(f"已保存与画像一致的location.json文件")
    
    # 检查是否需要运行run.py（基于关键输出文件的存在性）
    # run.py会自动检查其内部各个模块是否需要运行
    if args.generate_qa == 1:
        # QA模式：检查 merged_qa_path
        merged_qa_path = os.path.join(persona_folder, "QA_all", "QA.json")
        need_run = not os.path.exists(merged_qa_path)
    else:
        # 非QA模式：检查 contact.json
        contact_path = os.path.join(persona_folder, "phone_data", "contact.json")
        need_run = not os.path.exists(contact_path)
    
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

        # 添加 dry-run 参数
        if args.dry_run:
            run_args.append("--dry-run")
        
        # 调用集成好的run.py
        scripts = [{
            "path": "run.py",
            "description": "集成生成模块",
            "args": run_args
        }]
    else:
        if args.generate_qa == 1:
            print(f"检测到合并后的QA文件: {merged_qa_path}")
        else:
            print(f"检测到 contact.json 文件: {contact_path}")
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

def format_duration(seconds):
    """
    将秒数格式化为可读的时长字符串（如 1h 23m 45s）
    """
    if seconds is None:
        return "N/A"
    seconds = int(round(seconds))
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    if days > 0:
        return f"{days}d {hours}h {minutes}m {secs}s"
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    if minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def empty_usage():
    """返回一个空的 token 用量结构"""
    return {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "call_count": 0,
        "models": {},
    }


def merge_usage(acc, usage):
    """把单个 usage 快照累加到累加器 acc（原地修改并返回 acc）"""
    if not usage:
        return acc
    for key in ("prompt_tokens", "completion_tokens", "total_tokens", "call_count"):
        acc[key] = acc.get(key, 0) + (usage.get(key) or 0)
    models = acc.setdefault("models", {})
    for model, stats in (usage.get("models") or {}).items():
        target = models.setdefault(model, {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "call_count": 0,
        })
        for key in ("prompt_tokens", "completion_tokens", "total_tokens", "call_count"):
            target[key] = target.get(key, 0) + (stats.get(key) or 0)
    return acc


def aggregate_token_files(token_dir):
    """
    聚合目录下所有 token_<pid>.json 文件中的 token 用量
    :param token_dir: 存放 token 统计文件的目录
    :return: 合并后的 usage 字典
    """
    acc = empty_usage()
    if not token_dir or not os.path.isdir(token_dir):
        return acc
    for filename in os.listdir(token_dir):
        if not (filename.startswith("token_") and filename.endswith(".json")):
            continue
        file_path = os.path.join(token_dir, filename)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                usage = json.load(f)
            merge_usage(acc, usage)
        except Exception as e:
            print(f"  警告: 读取 token 统计文件失败 {file_path}: {str(e)}")
    return acc


def read_stage_times(persona_folder):
    """读取某个画像目录下 run.py 写入的 stage_times.json（不存在则返回 None）"""
    path = os.path.join(persona_folder, "stage_times.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("stages")
    except Exception as e:
        print(f"  警告: 读取阶段耗时文件失败 {path}: {str(e)}")
        return None


def write_report(report, output_root):
    """
    将报告写入输出目录（JSON 与可读文本两份）
    :param report: 报告内容字典
    :param output_root: 输出根目录（即 output/）
    """
    os.makedirs(output_root, exist_ok=True)
    json_path = os.path.join(output_root, "synthesis_report.json")
    txt_path = os.path.join(output_root, "synthesis_report.txt")

    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 报告文件已生成: {json_path}")
    except Exception as e:
        print(f"\n❌ 写入报告文件失败 {json_path}: {str(e)}")

    try:
        lines = []
        lines.append("=" * 70)
        lines.append("合成数据报告")
        lines.append(f"生成时间: {report.get('generated_at', '')}")
        lines.append(f"画像总数: {report.get('persona_count', 0)}")
        lines.append(f"成功数量: {report.get('success_count', 0)}")
        lines.append(f"失败数量: {report.get('failed_count', 0)}")
        lines.append(f"总耗时: {report.get('total_duration_human', '')}")
        lines.append("")
        tokens = report.get("total_tokens", {})
        lines.append(f"Token 消耗总量: {tokens.get('total_tokens', 0)}")
        lines.append(f"  - 输入 tokens: {tokens.get('prompt_tokens', 0)}")
        lines.append(f"  - 输出 tokens: {tokens.get('completion_tokens', 0)}")
        lines.append(f"  - LLM 调用次数: {tokens.get('call_count', 0)}")
        models = tokens.get("models", {})
        if models:
            lines.append("  按模型统计:")
            for model, stats in models.items():
                lines.append(f"    - {model}: 输入 {stats.get('prompt_tokens', 0)} / "
                             f"输出 {stats.get('completion_tokens', 0)} / "
                             f"总计 {stats.get('total_tokens', 0)} / "
                             f"调用 {stats.get('call_count', 0)} 次")
        stage_times = report.get("stage_times")
        if stage_times:
            lines.append("")
            lines.append("各阶段累计耗时:")
            for stage, duration in stage_times.items():
                lines.append(f"  - {stage}: {format_duration(duration)}")
        lines.append("")
        lines.append("各画像明细:")
        for p in report.get("personas", []):
            lines.append(f"  - [{p.get('status', '')}] {p.get('name', '')} "
                         f"(耗时 {p.get('duration_human', '')}, "
                         f"tokens {p.get('tokens', {}).get('total_tokens', 0)})")
        lines.append("=" * 70)
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"✅ 报告文件已生成: {txt_path}")
    except Exception as e:
        print(f"\n❌ 写入可读报告失败 {txt_path}: {str(e)}")


def main():
    """
    主函数，实现批量运行功能
    """

    # 解析命令行参数
    args = parse_args()

    # 设置工作目录为脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    # 将 persona_folder 转为绝对路径，确保相对于项目根目录解析
    if not os.path.isabs(args.persona_folder):
        project_root = os.path.dirname(script_dir)
        args.persona_folder = os.path.join(project_root, args.persona_folder)

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

    location_batches = None
    location_sidecar_path = os.path.splitext(person_json_path)[0] + "_locations.json"
    if os.path.exists(location_sidecar_path):
        with open(location_sidecar_path, 'r', encoding='utf-8') as f:
            location_batches = json.load(f)
        if not isinstance(location_batches, list) or len(location_batches) != len(personas):
            print(f"❌ 错误: {location_sidecar_path} 必须是与画像数量一致的二维地址数组")
            return 1
        print(f"已加载画像阶段生成的地址数据: {location_sidecar_path}")
    
    # 根据start-id和end-id过滤人物
    if args.start_id > 0 or args.end_id > 0:
        start_idx = args.start_id - 1 if args.start_id > 0 else 0
        end_idx = args.end_id if args.end_id > 0 else len(personas)
        personas = personas[start_idx:end_idx]
        if location_batches is not None:
            location_batches = location_batches[start_idx:end_idx]
        print(f"\n根据ID范围过滤后，需要处理的人物数: {len(personas)}")
    
    # 记录总开始时间
    total_start_time = time.time()
    print(f"\n{'='*80}")
    print(f"开始执行批量生成流程")
    print(f"总开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"总共有 {len(personas)} 个画像需要处理")
    print(f"{'='*80}")

    # 输出根目录（报告文件将写入这里）
    output_root = os.path.join(os.path.dirname(script_dir), "output")

    # 为每个画像执行流程，并统计每个画像（阶段）的耗时与 token 用量
    success_count = 0
    persona_records = []
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
        # 使用绝对路径，确保传递给 run.py 时路径正确
        persona_folder = os.path.join(output_root, persona_folder_name)

        # 为当前画像设置 token 统计落盘目录（环境变量会传递给 run.py 及其所有子进程）
        token_dir = os.path.join(persona_folder, "token_stats")
        os.environ["LIFEBENCH_TOKEN_DIR"] = token_dir

        # 执行流程（记录单个画像耗时）
        location_data = location_batches[i] if location_batches is not None else None
        persona_start_time = time.time()
        success = run_for_persona(persona, persona_folder, i+1, args, location_data=location_data)
        persona_duration = time.time() - persona_start_time

        if success:
            success_count += 1
            print(f"\n✅ 人物 {name} 处理成功!")
        else:
            print(f"\n❌ 人物 {name} 处理失败!")

        # 汇总该画像的 token 用量与阶段耗时
        tokens = aggregate_token_files(token_dir)
        stage_times = read_stage_times(persona_folder)
        persona_records.append({
            "index": i + 1,
            "name": name,
            "folder": persona_folder_name,
            "status": "success" if success else "failed",
            "duration_seconds": round(persona_duration, 3),
            "duration_human": format_duration(persona_duration),
            "tokens": tokens,
            "stages": stage_times,
        })
        print(f"人物 {name} 耗时: {format_duration(persona_duration)}, "
              f"累计 tokens: {tokens.get('total_tokens', 0)}")

    # 记录总结束时间
    total_end_time = time.time()
    total_duration = total_end_time - total_start_time

    # 汇总 token 用量与各阶段累计耗时
    total_tokens = empty_usage()
    for record in persona_records:
        merge_usage(total_tokens, record.get("tokens"))

    total_stage_times = {}
    for record in persona_records:
        stages = record.get("stages") or {}
        for stage, duration in stages.items():
            total_stage_times[stage] = total_stage_times.get(stage, 0.0) + duration

    print(f"\n{'='*80}")
    print(f"批量生成流程执行结束")
    print(f"总结束时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"总耗时: {format_duration(total_duration)}")
    print(f"总处理人物数: {len(personas)}")
    print(f"成功处理人物数: {success_count}")
    print(f"失败处理人物数: {len(personas) - success_count}")
    print(f"Token 消耗总量: {total_tokens.get('total_tokens', 0)} "
          f"(输入 {total_tokens.get('prompt_tokens', 0)} / 输出 {total_tokens.get('completion_tokens', 0)})")
    print(f"LLM 调用次数: {total_tokens.get('call_count', 0)}")

    if success_count == len(personas):
        print(f"✅ 所有人物处理成功!")
    else:
        print(f"❌ 部分人物处理失败!")
    print(f"{'='*80}")

    # 生成报告文件（写入输出目录）
    report = {
        "generated_at": time.strftime('%Y-%m-%d %H:%M:%S'),
        "persona_count": len(personas),
        "success_count": success_count,
        "failed_count": len(personas) - success_count,
        "total_duration_seconds": round(total_duration, 3),
        "total_duration_human": format_duration(total_duration),
        "total_tokens": total_tokens,
        "stage_times": total_stage_times,
        "personas": persona_records,
    }
    write_report(report, output_root)

    return 0 if success_count == len(personas) else 1

if __name__ == "__main__":
    sys.exit(main())
