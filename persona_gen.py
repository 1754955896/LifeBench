from persona.persona_gen import *
import argparse

# 命令行参数解析
parser = argparse.ArgumentParser(description='人物画像生成模块')
parser.add_argument('--file-path', type=str, default='data/persona/', help='数据文件路径')
parser.add_argument('--start', type=int, default=0, help='开始生成的人物索引')
parser.add_argument('--end', type=int, default=1, help='结束生成的人物索引')
parser.add_argument('--ref-file', type=str, default='profile_ref.json', help='参考数据库文件名')
parser.add_argument('--input-file', type=str, default='processed_features.json', help='输入特征文件名')
parser.add_argument('--output-file', type=str, default='persona_list.json', help='输出人物画像文件名')
args = parser.parse_args()

# 输入：profile_ref.json参考数据库、processed_features.json从问卷数据预处理出的格式化基础数据
# 输出：persona_list.json

# 数据库json地址
generator = PersonaGenerator(args.file_path + args.ref_file)
generator.gen_profile(start_id=args.start, end_id=args.end,
                      in_file_path=args.file_path + args.input_file,
                      out_file_path=args.file_path + args.output_file)