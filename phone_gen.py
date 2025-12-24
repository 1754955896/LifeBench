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


# 单个日期的完整处理任务
def process_single_date(date, contact, file_path, initial_a, initial_b, initial_c, initial_d, initial_e):
    """
    处理单个日期的所有数据生成和文件写入
    :param date: 要处理的日期
    :param contact: 联系人信息
    :param file_path: 文件保存路径
    :param initial_a: communication操作的初始数据
    :param initial_b: note&calendar操作的初始数据
    :param initial_c: gallery操作的初始数据
    :param initial_d: push操作的初始数据
    :param initial_e: fitness_health操作的初始数据
    :return: 处理结果（成功/失败，日期）
    """
    try:
        # 内部并行执行5个生成器任务
        with ThreadPoolExecutor(max_workers=5) as inner_executor:
            # 提交所有内部任务
            future_a = inner_executor.submit(run_communication_task, date, contact, file_path, initial_a)
            future_b = inner_executor.submit(run_notecalendar_task, date, contact, file_path, initial_b)
            future_c = inner_executor.submit(run_gallery_task, date, contact, file_path, initial_c)
            future_d = inner_executor.submit(run_push_task, date, contact, file_path, initial_d)
            future_e = inner_executor.submit(run_fitness_health_task, date, contact, file_path, initial_e)

            # 获取执行结果
            a_result = future_a.result()
            b_result = future_b.result()
            c_result = future_c.result()
            d_result = future_d.result()
            e_result = future_e.result()

        # 文件写入（使用锁确保线程安全，避免多个线程同时写同一文件）
        file_lock = threading.Lock()

        # 注意：原代码中文件命名和数据的对应关系看起来可能有误（a→gallery.json, b→push.json等）
        # 这里保持原有的映射关系不变
        with file_lock:
            # 创建phone_data文件夹（如果不存在）
            phone_data_dir = os.path.join(file_path, "phone_data")
            os.makedirs(phone_data_dir, exist_ok=True)
            
            with open(os.path.join(phone_data_dir, "event_note.json"), "w", encoding="utf-8") as f:
                json.dump(b_result, f, ensure_ascii=False, indent=2)

            with open(os.path.join(phone_data_dir, "event_call.json"), "w", encoding="utf-8") as f:
                json.dump(a_result, f, ensure_ascii=False, indent=2)

            with open(os.path.join(phone_data_dir, "event_gallery.json"), "w", encoding="utf-8") as f:
                json.dump(c_result, f, ensure_ascii=False, indent=2)

            with open(os.path.join(phone_data_dir, "event_push.json"), "w", encoding="utf-8") as f:
                json.dump(d_result, f, ensure_ascii=False, indent=2)

            with open(os.path.join(phone_data_dir, "event_fitness_health.json"), "w", encoding="utf-8") as f:
                json.dump(e_result, f, ensure_ascii=False, indent=2)

        print(f"成功处理日期：{date}")
        return (True, date)

    except Exception as e:
        print(f"处理日期 {date} 时出错：{str(e)}")
        return (False, date)


# 主函数：多线程并行处理所有日期
def parallel_process_dates(start_time, end_time, contact, file_path, initial_a, initial_b, initial_c, initial_d, initial_e,
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
    :param max_workers: 最大并行线程数
    :return: 处理统计结果
    """
    # 收集所有处理结果
    success_dates = []
    failed_dates = []

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
                initial_e=initial_e
            )
            futures.append(future)

        # 等待所有任务完成并收集结果
        for future in as_completed(futures):
            success, date = future.result()
            if success:
                success_dates.append(date)
            else:
                failed_dates.append(date)

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


if __name__ == "__main__":
    import argparse
    
    # 命令行参数解析
    parser = argparse.ArgumentParser(description='手机操作生成模块')
    parser.add_argument('--file-path', type=str, default='output/', help='数据文件路径')
    parser.add_argument('--start-time', type=str, default='2025-01-01', help='开始日期')
    parser.add_argument('--end-time', type=str, default='2025-12-31', help='结束日期')
    parser.add_argument('--max-workers', type=int, default=32, help='最大并行线程数')
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
        contact = remove_json_wrapper(contact)
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
    extool.load_from_json(read_json_file(file_path + 'output/outputs.json'), persona)
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


    # 执行并行处理
    # max_workers建议根据CPU核心数和IO密集程度调整，IO密集型任务可设置较大值
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
        max_workers=32  # 可根据实际情况调整
    )