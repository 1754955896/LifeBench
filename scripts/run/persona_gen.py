"""Command-line entry point for persona generation."""

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.lifebench.persona.persona_gen import PersonaGenerator


def build_parser():
    parser = argparse.ArgumentParser(description="人物画像生成模块")
    parser.add_argument("--file-path", type=str, default="data/persona/", help="数据文件路径")
    parser.add_argument("--start", type=int, default=0, help="开始生成的人物索引")
    parser.add_argument("--end", type=int, default=1, help="结束生成的人物索引")
    parser.add_argument("--ref-file", type=str, default="profile_ref.json", help="参考数据库文件名")
    parser.add_argument("--input-file", type=str, default="processed_features.json", help="输入特征文件名")
    parser.add_argument("--output-file", type=str, default="persona_list.json", help="输出人物画像文件名")
    parser.add_argument("--as-of-date", type=str, default="2021-12-31", help="画像年龄等派生值的基准日期")
    parser.add_argument("--seed", type=int, default=None, help="参考数据采样随机种子")
    parser.add_argument("--max-workers", type=int, default=None, help="并行线程上限")
    parser.add_argument("--max-stage-retries", type=int, default=2, help="单个 LLM 阶段最大重试次数")
    parser.add_argument("--keep-checkpoints", action="store_true", help="保留中间画像文件用于排查")
    parser.add_argument("--input-mode", choices=["canonical", "auto"], default="canonical", help="canonical 使用旧标准输入；auto 使用 LLM 规范化任意输入")
    parser.add_argument("--input-format", default="auto", help="任意输入容器格式：auto/json/jsonl/csv/tsv/txt/xlsx")
    parser.add_argument("--variants-per-input", type=int, default=1, help="每条任意输入生成的差异化画像数量")
    parser.add_argument("--diversity", choices=["low", "medium", "high"], default="high", help="任意输入画像的差异等级")
    parser.add_argument("--skip-location-generation", action="store_true", help="跳过画像阶段的真实地址落地与 location sidecar 生成")
    parser.add_argument("--location-output", default=None, help="location sidecar 文件名；默认使用 <output>_locations.json")
    parser.add_argument("--reserved-address-file", default=None, help="已有画像或 location JSON；其地址会加入占用池以减少跨批次重复")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.max_workers is not None and args.max_workers < 1:
        print("错误：--max-workers 必须大于 0")
        return 2
    if args.max_stage_retries < 0:
        print("错误：--max-stage-retries 不能小于 0")
        return 2
    if args.variants_per_input < 1:
        print("错误：--variants-per-input 必须大于 0")
        return 2
    try:
        print(f"开始生成人物画像，索引范围 [{args.start}, {args.end})，输入文件：{args.input_file}，输出文件：{args.output_file}")
        generator = PersonaGenerator(
            os.path.join(args.file_path, args.ref_file),
            as_of_date=args.as_of_date,
            seed=args.seed,
            max_stage_retries=args.max_stage_retries,
            keep_checkpoints=args.keep_checkpoints,
            generate_locations=not args.skip_location_generation,
        )
        if args.reserved_address_file and generator.address_service is not None:
            reserved_path = args.reserved_address_file if os.path.isabs(args.reserved_address_file) else os.path.join(args.file_path, args.reserved_address_file)
            with open(reserved_path, "r", encoding="utf-8") as stream:
                generator.address_service.reserve_existing_addresses(json.load(stream))
        input_path = os.path.join(args.file_path, args.input_file)
        output_path = os.path.join(args.file_path, args.output_file)
        location_output_path = None
        if args.location_output:
            location_output_path = args.location_output if os.path.isabs(args.location_output) else os.path.join(args.file_path, args.location_output)
        if args.input_mode == "auto":
            result = generator.generate_from_any(
                source=input_path,
                out_file_path=output_path,
                input_format=args.input_format,
                variants_per_input=args.variants_per_input,
                diversity=args.diversity,
                seed=args.seed,
                start_id=args.start,
                end_id=args.end,
                location_out_file_path=location_output_path,
            )
        else:
            result = generator.gen_profile(
                start_id=args.start,
                end_id=args.end,
                in_file_path=input_path,
                out_file_path=output_path,
                max_workers=args.max_workers,
                location_out_file_path=location_output_path,
            )
        return 0 if result is not None else 3
    except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
        print("参数或输入错误：%s" % exc)
        return 2
    except Exception as exc:
        print("画像生成失败：%s" % exc)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
