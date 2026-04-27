import json
from collections import defaultdict
from utils.IO import *
from datetime import datetime, timedelta


def is_consecutive(date1, date2):
    """判断两个日期是否连续（相差1天）"""
    fmt = "%Y-%m-%d"
    d1 = datetime.strptime(date1, fmt)
    d2 = datetime.strptime(date2, fmt)
    return (d2 - d1) == timedelta(days=1)


def convert_schedule(input_data):
    # 存储每个事件出现的所有日期
    event_dates = defaultdict(list)

    # 处理输入数据类型
    if isinstance(input_data, str):
        schedule_data = json.loads(input_data)
    elif isinstance(input_data, dict):
        schedule_data = input_data
    else:
        raise TypeError("输入数据必须是JSON字符串或字典")

    # 收集所有事件及其日期
    for date, details in schedule_data.items():
        for event in details["事件"]:
            event_dates[event].append(date)

    # 处理结果：按连续日期分组
    result = []
    for event, dates in event_dates.items():
        # 对日期进行排序
        sorted_dates = sorted(dates)
        # 按连续日期分组
        date_groups = []
        if sorted_dates:
            current_group = [sorted_dates[0]]
            for date in sorted_dates[1:]:
                if is_consecutive(current_group[-1], date):
                    current_group.append(date)
                else:
                    date_groups.append(current_group)
                    current_group = [date]
            date_groups.append(current_group)  # 添加最后一组

        # 生成各分组的起止日期
        period_list = []
        for group in date_groups:
            start = group[0]
            end = group[-1]
            period_list.append(f"{start}至{end}")

        result.append({
            "事件": event,
            "起止日期": period_list
        })

    return result


if __name__ == "__main__":
    # 示例日程数据
    schedule_json = read_json_file('../utils/event_final_all.json')

    # 转换并打印结果
    converted = convert_schedule(schedule_json)
    print(json.dumps(converted, ensure_ascii=False, indent=4))
    with open("../data_event/history/event_fenghaoran.json", "w", encoding="utf-8") as json_f:
        json.dump(converted, json_f, ensure_ascii=False, indent=4)
    print("所有数据处理完成，JSON文件已生成")