# -*- coding: utf-8 -*-
"""短期记忆检索：从 MemoryStore 构建唯一的结构化短期记忆上下文。"""
import calendar
from datetime import datetime, timedelta
from typing import List

from src.lifebench.utils.date_utils import recent_dates

def build_short_memory(mind, dailyevent, date):
    """更新短期记忆：插入今日事件并检索相关历史事件。

    参数:
        mind: Mind 实例
        dailyevent: 今日事件内容（反思 JSON 字典）
        date: 当前日期字符串（格式：YYYY-MM-DD）

    返回:
        None: 直接更新 mind.short_memory_context
    """
    # 记忆库插入今天事件
    written_ids = []
    if dailyevent != "":
        # 短期情景库只保存可检索的日记四字段；activity_metrics、
        # next_day_context 和完整 long_memory 分别由各自状态字段持有，避免逐日重复。
        memory_record = {
            key: str(dailyevent.get(key) or "")
            for key in ("date", "topic", "events", "thought")
        } if isinstance(dailyevent, dict) else dailyevent
        written_id = mind.mem_module.add_memory(memory_record)
        written_ids.append(written_id)

    # 本日检索命中 ID 收集器（供 memory_trace 回报）
    retrieved_ids = []

    def _collect(res):
        for j in res:
            eid = j.get("event_id")
            if eid:
                retrieved_ids.append(eid)
    def get_next_day(date_str: str, date_format: str = "%Y-%m-%d") -> str:
        """
        输入字符串日期，返回其「后一天」的日期（同格式字符串）

        参数:
            date_str: 输入日期字符串，默认格式"YYYY-MM-DD"（如"2025-02-28"）
            date_format: 日期格式，默认"%Y-%m-%d"，可自定义（如"%Y/%m/%d"）

        返回:
            str: 后一天的日期字符串（与输入格式一致）

        异常:
            ValueError: 输入日期格式错误或日期无效（如"2025-02-30"）时抛出
        """
        # 1. 将字符串转为datetime对象（自动校验日期有效性）
        try:
            current_date = datetime.strptime(date_str, date_format)
        except ValueError as e:
            raise ValueError(f"日期错误！需符合'{date_format}'格式且为有效日期（如'2025-02-28'），错误：{str(e)}")

        # 2. 加1天（自动处理月份/年份交替，如2025-02-28→2025-03-01、2025-12-31→2026-01-01）
        next_day_date = current_date + timedelta(days=1)

        # 3. 转回原格式字符串并返回
        return next_day_date.strftime(date_format)

    def get_cycle_dates_array(date_str: str, date_format: str = "%Y-%m-%d") -> List[str]:
        """
        根据输入字符串日期，返回「上个月同日、上周同星期」的日期数组（按固定顺序排列）

        参数:
            date_str: 输入日期字符串，默认格式"YYYY-MM-DD"（如"2025-03-15"）
            date_format: 日期格式，默认"%Y-%m-%d"，可自定义（如"%Y/%m/%d"）

        返回:
            List[str]: 日期数组，顺序为 [上个月同日, 上周同星期]

        异常:
            ValueError: 输入日期格式不匹配时抛出
        """
        # 1. 解析输入日期
        try:
            current_date = datetime.strptime(date_str, date_format)
        except ValueError as e:
            raise ValueError(f"日期格式错误！需符合'{date_format}'（如'2025-03-15'），错误：{str(e)}")

        # 2. 计算上个月同日（处理当月无同日场景）
        def _get_last_month_same_day(date: datetime) -> datetime:
            """
            计算上个月的同日
            正确处理月份边界（1月→上年12月）
            """
            year = date.year
            month = date.month
            day = date.day

            if month == 1:
                # 1月减1变成去年12月
                year -= 1
                month = 12
            else:
                month -= 1

            # 检查目标月份是否有该日期（如3月31日→2月无31日）
            try:
                return date.replace(year=year, month=month, day=day)
            except ValueError:
                # 目标月份天数不足（如3月31日→2月），取目标月份最后一天
                last_day_of_month = calendar.monthrange(year, month)[1]
                return date.replace(year=year, month=month, day=last_day_of_month)

        last_month_day = _get_last_month_same_day(current_date).strftime(date_format)

        # 3. 计算上周同星期（固定减7天）
        last_week_weekday = (current_date - timedelta(days=7)).strftime(date_format)

        # 4. 直接返回数组（顺序：上个月同日 → 上周同星期）
        return [last_month_day, last_week_weekday]

    # 最终增加前五天事件、上周同日事件、上月同日事件、检索最相似2日事件。
    # 按「来源」分桶组织（recent/periodic/similar），避免扁平列表丢失时间与语义来源；
    # event_id / source 等记账字段不写入记录，只保留对 LLM 有意义的语义字段。
    date_set = set()
    buckets = {"recent": [], "periodic": [], "similar": []}
    record_keys = set()
    _source_to_bucket = {"recent": "recent", "fuzzy": "recent", "periodic": "periodic", "similar": "similar"}

    def add_record(item, source, fallback_date=None):
        if not isinstance(item, dict):
            return
        events = str(item.get("events") or "")
        event_date = item.get("date") or fallback_date
        event_id = item.get("event_id")
        key = str(event_id or "%s|%s" % (event_date, events[:80]))
        if not events or key in record_keys:
            return
        record_keys.add(key)
        buckets[_source_to_bucket.get(source, "recent")].append({
            "date": event_date,
            "topic": str(item.get("topic") or ""),
            "events": events,
            "thought": str(item.get("thought") or ""),
            "confidence": 1.0 if event_id else 0.55,
        })

    for i in recent_dates(date):
        res = mind.mem_module.search_by_date(start_time=i)
        _collect(res)
        for j in res:
            date_set.add(j['date'])
            add_record(j, "recent")
        if res == []:
            fuzzy = mind.get_fuzzy_short_memory(i) or ""
            add_record({"date": i, "events": fuzzy}, "fuzzy", i)

    for i in get_cycle_dates_array(get_next_day(date)):
        res = mind.mem_module.search_by_date(start_time=i)
        _collect(res)
        for j in res:
            date_set.add(j['date'])
            add_record(j, "periodic")
    arr = mind.filter_by_date(get_next_day(date))
    res = ""
    for item in arr:
        name = item['name']
        res += name
    res = mind.mem_module.search_by_topic_embedding(res, 2)
    _collect(res)
    for i in res:
        if i['date'] in date_set:
            continue
        add_record(i, "similar")
    mind.short_memory_context = {
        "recent": buckets["recent"],
        "periodic": buckets["periodic"],
        "similar": buckets["similar"],
    }

    # 回报本日命中/写入 ID（若 Mind 持有 trace 记录器）
    recorder = getattr(mind, "memory_trace", None)
    if recorder is not None:
        recorder.record(date, retrieved=retrieved_ids, written=written_ids)
