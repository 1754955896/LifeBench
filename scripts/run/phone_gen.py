import json
import os.path
from src.lifebench.event.phone_data_gen import (
    PhoneEventMatcher,
    extool,
    remove_json_wrapper,
    parallel_process_dates_dynamic
)

from src.lifebench.utils.utils_io import read_json_file

def process_phone_data(file_path):
    """
    处理手机数据的后处理操作：分类、排序、添加 phone_id
    :param file_path: 数据文件路径
    """
    # 数据后处理：分类、排序、添加 phone_id
    print(f"\n开始数据后处理...")

    # 1. 定义需要处理的文件（除了 contact.json）
    phone_data_dir = os.path.join(file_path, "phone_data")

    files_to_process = [f for f in os.listdir(phone_data_dir) if f.endswith('.json') and f.startswith('event_')]

    # 2. 创建 process 文件夹
    process_dir = os.path.join(file_path, "process")
    process_dir = os.path.join(process_dir, "phone_data")
    os.makedirs(process_dir, exist_ok=True)

    # 3. 处理每个文件
    for filename in files_to_process:
        file_path_old = os.path.join(phone_data_dir, filename)

        # 读取原始数据
        with open(file_path_old, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 特殊处理 event_perception.json 文件
        if filename == "event_perception.json":
            # 直接保留所有数据，不按 type 分类
            # 排序：先按 date 排序，再按 time 数组的第一个元素排序
            sorted_data = sorted(data, key=lambda x: (x.get('date', ''), x.get('time', [''])[0]))

            # 添加 phone_id
            for i, item in enumerate(sorted_data):
                item['phone_id'] = i

            # 保存为新文件 perception.json
            new_filename = "perception.json"
            new_file_path = os.path.join(phone_data_dir, new_filename)
            with open(new_file_path, 'w', encoding='utf-8') as f:
                json.dump(sorted_data, f, ensure_ascii=False, indent=2)

            print(f"✅ 生成新文件：{new_filename}，共 {len(sorted_data)} 条记录")
        else:
            # 其他文件按 type 分类
            # 按 type 分类
            type_dict = {}
            for item in data:
                if 'type' in item:
                    data_type = item['type']
                    if data_type not in type_dict:
                        type_dict[data_type] = []
                    type_dict[data_type].append(item)
                else:
                    # 如果没有 type 字段，使用文件名作为类型
                    data_type = filename.replace('event_', '').replace('.json', '')
                    if data_type not in type_dict:
                        type_dict[data_type] = []
                    type_dict[data_type].append(item)

            # 生成新文件并排序
            for data_type, type_data in type_dict.items():
                # 排序
                if data_type in ['call', 'gallery', 'note', 'calendar', 'push', 'photo', 'sms']:
                    # 使用 datetime 字段排序
                    sorted_data = sorted(type_data, key=lambda x: x.get('datetime', ''))
                elif data_type == 'fitness_health':
                    # 按日期字段排序
                    sorted_data = sorted(type_data, key=lambda x: x.get('日期', ''))
                elif data_type == 'agent_chat':
                    # 按 date 字段排序
                    sorted_data = sorted(type_data, key=lambda x: x.get('date', ''))
                else:
                    # 默认按 datetime 排序
                    sorted_data = sorted(type_data, key=lambda x: x.get('datetime', ''))

                # 添加 phone_id
                for i, item in enumerate(sorted_data):
                    item['phone_id'] = i

                # 保存新文件
                new_filename = f"{data_type}.json"
                new_file_path = os.path.join(phone_data_dir, new_filename)
                with open(new_file_path, 'w', encoding='utf-8') as f:
                    json.dump(sorted_data, f, ensure_ascii=False, indent=2)

                print(f"✅ 生成新文件：{new_filename}，共 {len(sorted_data)} 条记录")

        # 将老文件移动到 process 文件夹
        new_file_path_old = os.path.join(process_dir, filename)
        os.replace(file_path_old, new_file_path_old)
        print(f"📁 已将原文件 {filename} 移动到 process 文件夹")

    print(f"\n数据后处理完成！")


if __name__ == "__main__":
    import argparse

    # 命令行参数解析
    parser = argparse.ArgumentParser(description='手机操作生成模块')
    parser.add_argument('--file-path', type=str, default='fenghaoran/', help='数据文件路径')
    parser.add_argument('--start-time', type=str, default='2025-01-01', help='开始日期')
    parser.add_argument('--end-time', type=str, default='2025-01-31', help='结束日期')
    parser.add_argument('--max-workers', type=int, default=40, help='最大并行线程数')
    parser.add_argument('--phone-count-min', type=int, default=5, help='每天手机数据最小条数')
    parser.add_argument('--phone-count-max', type=int, default=5, help='每天手机数据最大条数')
    parser.add_argument('--process-only', action='store_true', help='仅执行数据后处理操作，不生成新数据')
    args = parser.parse_args()

    file_path = args.file_path
    start_time = args.start_time
    end_time = args.end_time
    persona = read_json_file(file_path + 'persona.json')

    contact = {}
    if os.path.exists(file_path + "phone_data/contact.json"):
        contact = read_json_file(file_path + "phone_data/contact.json")
    else:
        from src.lifebench.event.phone_data_gen import contact_gen
        contact = contact_gen(persona)
        contact = remove_json_wrapper(contact, json_type='array')
        contact = json.loads(contact)
        # 创建 phone_data 文件夹（如果不存在）
        phone_data_dir = os.path.join(file_path, "phone_data")
        os.makedirs(phone_data_dir, exist_ok=True)
        with open(os.path.join(phone_data_dir, "contact.json"), "w", encoding="utf-8") as f:
            json.dump(contact, f, ensure_ascii=False, indent=2)

    # 初始化 extool
    extool.load_from_json(read_json_file(file_path + 'daily_event.json'), persona,
                          read_json_file(file_path + 'daily_draft.json'))
    
    # 根据参数决定执行模式
    if args.process_only:
        print(f"仅执行数据后处理操作...")
        # 直接执行数据后处理（调用 phone_data_gen.py 中的函数）
        process_phone_data(file_path)
    else:
        # 在 main 中初始化 PhoneEventMatcher 实例，传入 atomic_events_file
        atomic_events_file = os.path.join(file_path, "event_tree.json")
        matcher = PhoneEventMatcher(atomic_events_file=atomic_events_file)

        # 执行全部数据生成任务（使用 dynamic 版本）
        print(f"开始生成所有类型的手机数据，日期范围：{start_time} 到 {end_time}")
        result = parallel_process_dates_dynamic(
            start_time=start_time,
            end_time=end_time,
            contact=contact,
            file_path=file_path,
            matcher=matcher,
            phone_count_control={"min": args.phone_count_min, "max": args.phone_count_max},
            max_workers=args.max_workers
        )

        # 执行数据后处理操作（调用 phone_data_gen.py 中的函数）
        process_phone_data(file_path)
