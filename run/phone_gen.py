import json
import os.path
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from event.phone_data_gen import *

def run_communication_task(date, contact, file_path, initial_data):
    """执行通讯数据生成任务"""
    g1 = CommunicationOperationGenerator()
    return g1.phone_gen_callandmsm(date, contact, file_path, initial_data)


def run_notecalendar_task(date, contact, file_path, initial_data):
    """执行笔记日历数据生成任务"""
    g2 = NoteCalendarOperationGenerator(random_seed=42)
    return g2.phone_gen_noteandcalendar(date, contact, file_path, initial_data)


def run_gallery_task(date, contact, file_path, initial_data):
    """执行相册数据生成任务"""
    g3 = GalleryOperationGenerator(random_seed=42)
    return g3.phone_gen_gallery(date, contact, file_path, initial_data)


def run_push_task(date, contact, file_path, initial_data):
    """执行推送数据生成任务"""
    g4 = PushOperationGenerator(random_seed=42)
    return g4.phone_gen_push(date, contact, file_path, initial_data)


def run_fitness_health_task(date, contact, file_path, initial_data):
    """执行运动健康数据生成任务"""
    g5 = FitnessHealthOperationGenerator(random_seed=42)
    return g5.phone_gen_fitness_health(date, contact, file_path, initial_data)


def run_chat_task(date, contact, file_path, initial_data):
    """执行聊天数据生成任务"""
    g6 = ChatOperationGenerator(random_seed=42)
    return g6.phone_gen_agent_chat(date, contact, file_path, initial_data)


def run_perception_task(date, contact, file_path, initial_data):
    """执行感知数据生成任务"""
    g7 = PerceptionDataGenerator()
    return g7.generate_perception_data(date,initial_data)


# 单个日期的完整处理任务
def process_single_date(date, contact, file_path, initial_a, initial_b, initial_c, initial_d, initial_e, initial_f, initial_g):
    """
    处理单个日期的所有数据生成（不进行文件写入）
    :param date: 要处理的日期
    :param contact: 联系人信息
    :param file_path: 文件保存路径
    :param initial_a: communication操作的初始数据
    :param initial_b: note&calendar操作的初始数据
    :param initial_c: gallery操作的初始数据
    :param initial_d: push操作的初始数据
    :param initial_e: fitness_health操作的初始数据
    :param initial_f: chat操作的初始数据
    :param initial_g: perception操作的初始数据
    :return: 处理结果（成功/失败，日期，生成的数据字典）
    """
    try:
        # 内部并行执行7个生成器任务
        with ThreadPoolExecutor(max_workers=7) as inner_executor:
            # 提交所有内部任务
            future_a = inner_executor.submit(run_communication_task, date, contact, file_path, initial_a)
            future_b = inner_executor.submit(run_notecalendar_task, date, contact, file_path, initial_b)
            future_c = inner_executor.submit(run_gallery_task, date, contact, file_path, initial_c)
            future_d = inner_executor.submit(run_push_task, date, contact, file_path, initial_d)
            future_e = inner_executor.submit(run_fitness_health_task, date, contact, file_path, initial_e)
            future_f = inner_executor.submit(run_chat_task, date, contact, file_path, initial_f)
            future_g = inner_executor.submit(run_perception_task, date, contact, file_path, initial_g)

            # 获取执行结果
            a_result = future_a.result()
            b_result = future_b.result()
            c_result = future_c.result()
            d_result = future_d.result()
            e_result = future_e.result()
            f_result = future_f.result()
            g_result = future_g.result()

        # 整理生成的数据
        generated_data = {
            "event_note.json": b_result,
            "event_call.json": a_result,
            "event_gallery.json": c_result,
            "event_push.json": d_result,
            "event_fitness_health.json": e_result,
            "event_chat.json": f_result,
            "event_perception.json": g_result
        }

        print(f"成功处理日期：{date}")
        return (True, date, generated_data)

    except Exception as e:
        print(f"处理日期 {date} 时出错：{str(e)}")
        import traceback
        traceback.print_exc()
        return (False, date, None)


# 主函数：多线程并行处理所有日期
def process_phone_data(file_path):
    """
    处理手机数据的后处理操作：分类、排序、添加phone_id
    :param file_path: 数据文件路径
    """
    # 数据后处理：分类、排序、添加phone_id
    print(f"\n开始数据后处理...")
    
    # 1. 定义需要处理的文件（除了contact.json和event_perception.json）
    phone_data_dir = os.path.join(file_path, "phone_data")
    
    # 直接删除event_perception.json文件
    event_perception_file = os.path.join(phone_data_dir, "event_perception.json")
    if os.path.exists(event_perception_file):
        os.remove(event_perception_file)
        print(f"已删除event_perception.json文件: {event_perception_file}")
    
    files_to_process = [f for f in os.listdir(phone_data_dir) if f.endswith('.json') and f.startswith('event_')]
    
    # 2. 创建process文件夹
    process_dir = os.path.join(file_path, "process")
    process_dir = os.path.join(process_dir,"phone_data")
    os.makedirs(process_dir, exist_ok=True)
    
    # 3. 处理每个文件
    for filename in files_to_process:
        file_path_old = os.path.join(phone_data_dir, filename)
        
        # 读取原始数据
        with open(file_path_old, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 按type分类
        type_dict = {}
        for item in data:
            if 'type' in item:
                data_type = item['type']
                if data_type not in type_dict:
                    type_dict[data_type] = []
                type_dict[data_type].append(item)
            else:
                # 如果没有type字段，使用文件名作为类型
                data_type = filename.replace('event_', '').replace('.json', '')
                if data_type not in type_dict:
                    type_dict[data_type] = []
                type_dict[data_type].append(item)
        
        # 生成新文件并排序
        for data_type, type_data in type_dict.items():
            # 排序
            if data_type in ['call', 'gallery', 'note', 'calendar', 'push','photo','sms']:
                # 使用datetime字段排序
                sorted_data = sorted(type_data, key=lambda x: x.get('datetime', ''))
            elif data_type == 'perception':
                # 先按date排序，再按time数组的第一个元素排序
                sorted_data = sorted(type_data, key=lambda x: (x.get('date', ''), x.get('time', [''])[0]))
            elif data_type == 'fitness_health':
                # 按日期字段排序
                sorted_data = sorted(type_data, key=lambda x: x.get('日期', ''))
            elif data_type == 'agent_chat':
                # 按date字段排序
                sorted_data = sorted(type_data, key=lambda x: x.get('date', ''))
            else:
                # 默认按datetime排序
                sorted_data = sorted(type_data, key=lambda x: x.get('datetime', ''))
            
            # 添加phone_id
            for i, item in enumerate(sorted_data):
                item['phone_id'] = i
            
            # 保存新文件
            new_filename = f"{data_type}.json"
            new_file_path = os.path.join(phone_data_dir, new_filename)
            with open(new_file_path, 'w', encoding='utf-8') as f:
                json.dump(sorted_data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ 生成新文件：{new_filename}，共 {len(sorted_data)} 条记录")
        
        # 将老文件移动到process文件夹
        new_file_path_old = os.path.join(process_dir, filename)
        os.replace(file_path_old, new_file_path_old)
        print(f"📁 已将原文件 {filename} 移动到 process 文件夹")
    
    print(f"\n数据后处理完成！")


def parallel_process_dates(start_time, end_time, contact, file_path, initial_a, initial_b, initial_c, initial_d, initial_e, initial_f, initial_g,
                           max_workers=8):
    """
    多线程并行处理所有日期
    :param start_time: 开始时间
    :param end_time: 结束时间
    :param contact: 联系人信息
    :param file_path: 文件保存路径
    :param initial_a: communication操作的初始数据
    :param initial_b: note&calendar操作的初始数据
    :param initial_c: gallery操作的初始数据
    :param initial_d: push操作的初始数据
    :param initial_e: fitness_health操作的初始数据
    :param initial_f: chat操作的初始数据
    :param initial_g: perception操作的初始数据
    :param max_workers: 最大并行线程数
    :return: 处理统计结果
    """
    # 收集所有处理结果
    success_dates = []
    failed_dates = []
    
    # 收集所有生成的数据
    data_collector = {
        "event_note.json": [],
        "event_call.json": [],
        "event_gallery.json": [],
        "event_push.json": [],
        "event_fitness_health.json": [],
        "event_chat.json": [],
        "event_perception.json": []
    }

    # 创建线程池，并行处理所有日期
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有日期的处理任务
        futures = []
        for date in iterate_dates(start_time, end_time):
            future = executor.submit(
                process_single_date,
                date=date,
                contact=contact,
                file_path=file_path,
                initial_a=initial_a,
                initial_b=initial_b,
                initial_c=initial_c,
                initial_d=initial_d,
                initial_e=initial_e,
                initial_f=initial_f,
                initial_g=initial_g
            )
            futures.append(future)

        # 等待所有任务完成并收集结果
        for future in as_completed(futures):
            success, date, generated_data = future.result()
            if success:
                success_dates.append(date)
                # 合并生成的数据到收集器
                for filename, data in generated_data.items():
                    if isinstance(data, list) and isinstance(data_collector[filename], list):
                        data_collector[filename].extend(data)
                    else:
                        data_collector[filename] = data
            else:
                failed_dates.append(date)

    # 创建phone_data文件夹（如果不存在）
    phone_data_dir = os.path.join(file_path, "phone_data")
    os.makedirs(phone_data_dir, exist_ok=True)
    
    # 将所有收集的数据写入文件（增量式，保留原有数据）
    for filename, data in data_collector.items():
        file_path = os.path.join(phone_data_dir, filename)
        try:
            # 读取原有数据
            existing_data = []
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    file_content = f.read().strip()
                    if file_content:
                        existing_data = json.loads(file_content)
                    else:
                        existing_data = []
            
            # 合并数据
            if isinstance(data, list) and isinstance(existing_data, list):
                # 如果都是列表，合并列表
                merged_data = existing_data + data
            else:
                # 否则，使用新数据
                merged_data = data
            
            # 写入合并后的数据
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(merged_data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ 数据成功写入文件：{filename}")
            print(f"   共写入 {len(merged_data)} 条数据")
        except json.JSONDecodeError as e:
            print(f"❌ 文件 {filename} JSON格式错误，将覆盖原有文件：{str(e)}")
            # 如果JSON格式错误，使用新数据覆盖
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"❌ 写入文件 {filename} 时出错：{str(e)}")

    # 输出统计信息
    total_dates = len(success_dates) + len(failed_dates)
    print(f"\n处理完成统计：")
    print(f"总日期数：{total_dates}")
    print(f"成功处理：{len(success_dates)} 个")
    print(f"处理失败：{len(failed_dates)} 个")
    if failed_dates:
        print(f"失败日期：{failed_dates}")

    return {
        "total": total_dates,
        "success": len(success_dates),
        "failed": len(failed_dates),
        "failed_dates": failed_dates
    }


def parallel_process_perception_only(start_time, end_time, contact, file_path, initial_g, max_workers=8):
    """
    多线程并行处理所有日期的感知数据生成（仅运行感知数据任务）
    :param start_time: 开始时间
    :param end_time: 结束时间
    :param contact: 联系人信息
    :param file_path: 文件保存路径
    :param initial_g: perception操作的初始数据
    :param max_workers: 最大并行线程数
    :return: 处理统计结果
    """
    # 收集所有处理结果
    success_dates = []
    failed_dates = []
    
    # 收集所有生成的感知数据
    all_perception_data = []
    
    # 创建phone_data文件夹（如果不存在）
    phone_data_dir = os.path.join(file_path, "phone_data")
    os.makedirs(phone_data_dir, exist_ok=True)
    
    # 单个感知任务处理函数
    def process_perception_date(date):
        try:
            # 运行感知数据生成任务
            result = run_perception_task(date, contact, file_path, initial_g)
            
            print(f"成功生成感知数据：{date}")
            return (True, date, result)
        except Exception as e:
            print(f"生成感知数据 {date} 时出错：{str(e)}")
            return (False, date, None)
    
    # 创建线程池，并行处理所有日期
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有日期的处理任务
        futures = []
        for date in iterate_dates(start_time, end_time):
            future = executor.submit(process_perception_date, date)
            futures.append(future)
    
        # 等待所有任务完成并收集结果
        for future in as_completed(futures):
            success, date, result = future.result()
            if success and result is not None:
                success_dates.append(date)
                # 收集生成的数据
                if isinstance(result, list):
                    all_perception_data.extend(result)
                else:
                    all_perception_data.append(result)
            else:
                failed_dates.append(date)
    
    # 增量式写入文件（保留原有数据）
    perception_file_path = os.path.join(phone_data_dir, "event_perception.json")
    try:
        # 读取原有数据
        existing_data = []
        if os.path.exists(perception_file_path):
            with open(perception_file_path, "r", encoding="utf-8") as f:
                file_content = f.read().strip()
                if file_content:
                    existing_data = json.loads(file_content)
                else:
                    existing_data = []
        
        # 合并数据
        if isinstance(all_perception_data, list) and isinstance(existing_data, list):
            # 如果都是列表，合并列表
            merged_data = existing_data + all_perception_data
        else:
            # 否则，使用新数据
            merged_data = all_perception_data
        
        # 写入合并后的数据
        with open(perception_file_path, "w", encoding="utf-8") as f:
            json.dump(merged_data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 感知数据成功写入文件：{perception_file_path}")
        print(f"   共写入 {len(merged_data)} 条数据")
    except json.JSONDecodeError as e:
        print(f"❌ JSON格式错误，将覆盖原有文件：{str(e)}")
        # 如果JSON格式错误，使用新数据覆盖
        with open(perception_file_path, "w", encoding="utf-8") as f:
            json.dump(all_perception_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"❌ 写入感知数据文件时出错：{str(e)}")
    
    # 输出统计信息
    total_dates = len(success_dates) + len(failed_dates)
    print(f"\n感知数据处理完成统计：")
    print(f"总日期数：{total_dates}")
    print(f"成功处理：{len(success_dates)} 个")
    print(f"处理失败：{len(failed_dates)} 个")
    if failed_dates:
        print(f"失败日期：{failed_dates}")
    
    return {
        "total": total_dates,
        "success": len(success_dates),
        "failed": len(failed_dates),
        "failed_dates": failed_dates
    }


if __name__ == "__main__":
    import argparse
    
    # 命令行参数解析
    parser = argparse.ArgumentParser(description='手机操作生成模块')
    parser.add_argument('--file-path', type=str, default='output/xujing/', help='数据文件路径')
    parser.add_argument('--start-time', type=str, default='2025-01-01', help='开始日期')
    parser.add_argument('--end-time', type=str, default='2025-12-31', help='结束日期')
    parser.add_argument('--max-workers', type=int, default=40, help='最大并行线程数')
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
        contact = contact_gen(persona)
        contact = remove_json_wrapper(contact, json_type='array')
        contact = json.loads(contact)
        # 创建phone_data文件夹（如果不存在）
        phone_data_dir = os.path.join(file_path, "phone_data")
        os.makedirs(phone_data_dir, exist_ok=True)
        with open(os.path.join(phone_data_dir, "contact.json"), "w", encoding="utf-8") as f:
            json.dump(contact, f, ensure_ascii=False, indent=2)

    a = []
    b = []
    c = []
    d = []
    e = []
    f = []
    g = []
    if os.path.exists(file_path + "phone_data/event_gallery.json"):
        a = read_json_file(file_path + "phone_data/event_gallery.json")
    if os.path.exists(file_path + "phone_data/event_push.json"):
        b = read_json_file(file_path + "phone_data/event_push.json")
    if os.path.exists(file_path + "phone_data/event_call.json"):
        c = read_json_file(file_path + "phone_data/event_call.json")
    if os.path.exists(file_path + "phone_data/event_note.json"):
        d = read_json_file(file_path + "phone_data/event_note.json")
    if os.path.exists(file_path + "phone_data/event_fitness_health.json"):
        e = read_json_file(file_path + "phone_data/event_fitness_health.json")
    if os.path.exists(file_path + "phone_data/event_chat.json"):
        f = read_json_file(file_path + "phone_data/event_chat.json")
    if os.path.exists(file_path + "phone_data/event_perception.json"):
        g = read_json_file(file_path + "phone_data/event_perception.json")
    extool.load_from_json(read_json_file(file_path + 'daily_event.json'), persona,read_json_file(file_path + 'daily_draft.json'))
    # for i in iterate_dates(start_time,end_time):
    #     phone_gen(i,contact,file_path,a,b,c,d,e)
    #
    # for i in iterate_dates(start_time,end_time):
    #
    #     g1 = CommunicationOperationGenerator()
    #     a = g1.phone_gen_callandmsm(i,contact,file_path,a)
    #     #
    #     # g2 = NoteCalendarOperationGenerator(random_seed=42)
    #     # # 生成2023-10-05的日历和笔记数据（总数≤4）
    #     # b = g2.phone_gen_noteandcalendar(i,contact,file_path,b)
    #     #
    #     # g3 = GalleryOperationGenerator(random_seed=42)
    #     # c = g3.phone_gen_gallery(i,contact,file_path,c)
    #     #
    #     # g4 = PushOperationGenerator(random_seed=42)
    #     # d = g4.phone_gen_push(i,contact,file_path,d)
    #     print('---------------------------')
    #     print(a)
    #     print('---------------------------')
    #     print(b)
    #     print('---------------------------')
    #     print(c)
    #     print('---------------------------')
    #     print(d)
    #     with open(file_path + "phone_data/event_note.json", "w", encoding="utf-8") as f:
    #         json.dump(d, f, ensure_ascii=False, indent=2)
    #     with open(file_path + "phone_data/event_call.json", "w", encoding="utf-8") as f:
    #         json.dump(c, f, ensure_ascii=False, indent=2)
    #     with open(file_path + "phone_data/event_gallery.json", "w", encoding="utf-8") as f:
    #         json.dump(a, f, ensure_ascii=False, indent=2)
    #     with open(file_path + "phone_data/event_push.json", "w", encoding="utf-8") as f:
    #         json.dump(b, f, ensure_ascii=False, indent=2)
    # 单个生成器任务的封装（用于内部并行）


    # 根据参数决定执行模式
    if args.process_only:
        print(f"仅执行数据后处理操作...")
        # 直接执行数据后处理
        process_phone_data(file_path)
    else:
        # 执行全部数据生成任务
        print(f"开始生成所有类型的手机数据，日期范围：{start_time} 到 {end_time}")
        result = parallel_process_dates(
            start_time=start_time,
            end_time=end_time,
            contact=contact,
            file_path=file_path,
            initial_a=a,
            initial_b=b,
            initial_c=c,
            initial_d=d,
            initial_e=e,
            initial_f=f,
            initial_g=g,
            max_workers=args.max_workers  # 可根据实际情况调整
        )
        
        # 执行数据后处理操作
        process_phone_data(file_path)