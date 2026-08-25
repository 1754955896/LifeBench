# -*- coding: utf-8 -*-
"""每日模拟引擎：日期分片并行驱动器 + 事务 checkpoint。

将 MindController 的分片并行逻辑抽到独立引擎。执行模型：
- 并行粒度 = 日期分片（方案 A），分片之间并行、分片内逐日串行；
- 每个分片冷启动（草稿预测记忆），内部再逐日演化；
- 每个分片维护一个事务 checkpoint，用于失败续跑与重试幂等。

引擎不反向依赖 daily_simulator.Mind：Mind 实例通过 mind_factory 注入。
"""
import os
import glob
import json

from concurrent.futures import ThreadPoolExecutor

from src.lifebench.utils.date_utils import iterate_dates
from src.lifebench.event.simulation.state import CognitiveState
from src.lifebench.event.simulation.telemetry import save_manifest, MemoryTraceRecorder


class DailySimulationEngine:
    """每日生活模拟引擎。

    以「日期分片」为并行粒度，分片内串行调用 mind.daily_event_gen1。
    """

    def __init__(self, mind_factory, events, persona, daily_draft, checkpoint_dir, instance_id=0):
        """
        参数:
            mind_factory: 无参可调用对象，返回一个未初始化的 Mind 实例
            events: 事件数据
            persona: 人物画像数据
            daily_draft: 每日大纲数据（传给 mind.initialize 的 daily_draft）
            checkpoint_dir: checkpoint 文件目录
            instance_id: 人物实例 ID，用于命名 checkpoint
        """
        self.mind_factory = mind_factory
        self.events = events
        self.persona = persona
        self.daily_draft = daily_draft
        self.checkpoint_dir = checkpoint_dir
        self.instance_id = instance_id

    # ------------------------------------------------------------------
    # checkpoint（事务化：写临时文件后原子替换）
    # ------------------------------------------------------------------
    def _checkpoint_path(self, interval_start):
        return os.path.join(
            self.checkpoint_dir,
            f"checkpoint_{self.instance_id}_{interval_start}.json",
        )

    def _save_checkpoint(self, interval_start, mind, completed_dates):
        os.makedirs(self.checkpoint_dir, exist_ok=True)
        state = {
            "completed_dates": completed_dates,
            "mind_state": mind.to_cognitive_state().to_dict(),
        }
        path = self._checkpoint_path(interval_start)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)

    def _load_checkpoint(self, interval_start):
        path = self._checkpoint_path(interval_start)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    # ------------------------------------------------------------------
    # 单分片处理
    # ------------------------------------------------------------------
    def _process_interval(self, interval_dates):
        """处理单个日期区间：区间内逐日串行，带事务 checkpoint 与重试。"""
        interval_start = interval_dates[0]
        mind = self.mind_factory()
        mind.initialize(
            self.events,
            self.persona,
            interval_start,
            daily_state=None,
            daily_draft=self.daily_draft,
        )

        # 续跑：载入 checkpoint 恢复记忆状态与已完成日期
        completed_dates = set()
        checkpoint = self._load_checkpoint(interval_start)
        if checkpoint:
            mind.restore_cognitive_state(CognitiveState.from_dict(checkpoint.get("mind_state", {})))
            completed_dates = set(checkpoint.get("completed_dates", []))

        print(f"  开始处理区间：{interval_dates[0]} 到 {interval_dates[-1]}")

        interval_results = []
        for date in interval_dates:
            if date in completed_dates:
                interval_results.append((date, True, None, None))
                print(f"    {date} 已在 checkpoint 中，跳过")
                continue

            success = False
            for attempt in range(2):
                try:
                    success = mind.daily_event_gen1(date)
                except Exception as e:
                    success = False
                    print(f"    处理日期 {date} 时抛出异常 ({type(e).__name__}): {str(e)}，第 {attempt + 1} 次尝试")
                if success:
                    if attempt > 0:
                        print(f"    {date} 重试后成功")
                    break
                if attempt < 1:
                    print(f"    处理日期 {date} 失败，第 {attempt + 1} 次重试")

            if success:
                interval_results.append((date, True, None, None))
                completed_dates.add(date)
                self._save_checkpoint(interval_start, mind, sorted(completed_dates))
            else:
                interval_results.append((date, False, None, None))

        print(f"  区间处理完成：{interval_dates[0]} 到 {interval_dates[-1]}")

        # 落盘本分片 memory_trace（逐日检索/写入命中 ID）
        trace_path = os.path.join(
            self.checkpoint_dir,
            f"memory_trace_{self.instance_id}_{interval_start}.json",
        )
        mind.memory_trace.save(trace_path)

        return interval_results

    # ------------------------------------------------------------------
    # 并行驱动器
    # ------------------------------------------------------------------
    def run(self, start_date, end_date, max_workers=5, interval_days=2):
        """
        分片并行生成指定日期范围内的事件。

        返回:
            List: 执行结果列表，元素为 (date, success, error_type, error_msg)
        """
        print(f"=== 开始分片并行生成事件，日期范围：{start_date} 到 {end_date}，最大并行区间数：{max_workers}，区间大小：{interval_days}天 ===")

        date_list = iterate_dates(start_date, end_date)
        intervals = [
            date_list[i:i + interval_days]
            for i in range(0, len(date_list), interval_days)
        ]

        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_interval = {
                executor.submit(self._process_interval, interval): interval
                for interval in intervals
            }
            for future in future_to_interval:
                try:
                    interval_results = future.result()
                    results.extend(interval_results)
                except Exception as e:
                    print(f"  处理区间时出错: {str(e)}")

        # 合并各分片 memory_trace 为单一 memory_trace.json（日期不重叠，取并集）
        self._merge_memory_traces()
        # 写 manifest.json（模型/温度/seed/模板哈希/config/依赖版本）
        save_manifest(os.path.join(self.checkpoint_dir, "manifest.json"))

        print(f"\n=== 所有日期的事件生成完成，共生成 {len(results)} 天的事件 ===")
        return results

    def _merge_memory_traces(self):
        """合并各分片 trace 为单一 memory_trace.json（§3.3）。"""
        pattern = os.path.join(
            self.checkpoint_dir, f"memory_trace_{self.instance_id}_*.json")
        traces = []
        for path in sorted(glob.glob(pattern)):
            with open(path, "r", encoding="utf-8") as f:
                traces.append(json.load(f))
        merged = MemoryTraceRecorder.merge(traces)
        out = os.path.join(self.checkpoint_dir, "memory_trace.json")
        tmp = out + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)
        os.replace(tmp, out)
