# -*- coding: utf-8 -*-
"""结构化记忆存储：MemoryStore。

从 memory_structure.memory.PersonalMemoryManager 迁移而来，去单例化——
每个 Mind（分片）持有独立实例与独立文件，消除分片并行下的写竞争与跨分片污染。
接口与行为与 PersonalMemoryManager 完全一致（add_memory / search_by_date /
search_by_topic_embedding / search_by_date_and_topic / get_memory_by_id /
delete_memories_before_month / save_to_file / load_from_file）。
"""
import json
import os
import threading
from datetime import datetime
from typing import List, Dict, Any, Optional

import numpy as np

from src.lifebench.event.simulation.memory.embedding import EmbeddingModel


class MemoryStore:
    def __init__(self,
                 memory_file: str = os.path.join("memory_file", "personal_memories.json"),
                 model_path: str = None):
        self.memory_file = memory_file
        if model_path is None:
            model_path = EmbeddingModel.default_model_path()
        self.model_path = os.path.abspath(model_path)
        self.memories = {}  # {日期(YYYY-MM-DD): [记忆对象列表]}
        self.embeddings = {}  # {事件ID: 向量}
        self.event_id_counter = 0
        self.event_id_map = {}  # {事件ID: (日期(YYYY-MM-DD), 记忆索引)}
        self._lock = threading.RLock()  # 使用可重入锁，避免递归锁请求导致的死锁

        self._ensure_directory_exists()
        self.embedding_model = EmbeddingModel(model_path=self.model_path)
        self._load_or_init_memory_file()

    def _ensure_directory_exists(self) -> None:
        memory_dir = os.path.dirname(self.memory_file)
        if memory_dir and not os.path.exists(memory_dir):
            os.makedirs(memory_dir, exist_ok=True)
        model_dir = os.path.dirname(self.model_path)
        if model_dir and not os.path.exists(model_dir):
            os.makedirs(model_dir, exist_ok=True)

    def _load_or_init_memory_file(self) -> None:
        if os.path.exists(self.memory_file):
            try:
                self.load_from_file()
            except json.JSONDecodeError:
                print(f"警告: {self.memory_file} 文件损坏，将创建新文件")
                self.save_to_file()
        else:
            self.save_to_file()

    # ------------------------------
    # 通用日期工具：提取秒级时间中的纯日期（YYYY-MM-DD）
    # ------------------------------
    def _extract_date(self, time_str: str) -> str:
        supported_formats = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]
        for fmt in supported_formats:
            try:
                return datetime.strptime(time_str, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        raise ValueError(
            f"时间格式不支持！请输入'YYYY-MM-DD'或'YYYY-MM-DD HH:MM:SS'（如'2025-11-02'或'2025-11-02 08:30:15'），"
            f"当前输入：{time_str}"
        )

    # ------------------------------
    # 1. 添加记忆（支持秒级时间输入）
    # ------------------------------
    def add_memory(self, memory: Dict[str, str]) -> str:
        required_fields = ["date", "topic", "events", "thought"]
        for field in required_fields:
            if field not in memory or not memory[field].strip():
                raise ValueError(f"记忆缺少必填字段或字段为空: {field}")

        raw_time = memory["date"]
        date = self._extract_date(raw_time)
        memory["date"] = date  # 覆盖为纯日期存储

        with self._lock:  # 线程安全保护
            self.event_id_counter += 1
            event_id = f"event_{self.event_id_counter}"

            if date not in self.memories:
                self.memories[date] = []
            memory_index = len(self.memories[date])
            memory["event_id"] = event_id  # 记忆自标识，便于检索层回报命中 ID（不改变对外语义）
            self.memories[date].append(memory)

            self.event_id_map[event_id] = (date, memory_index)
            self._generate_topic_embedding(event_id, memory["topic"])

            self.save_to_file()
        return event_id

    def _generate_topic_embedding(self, event_id: str, topic: str) -> None:
        self.embeddings[event_id] = self.embedding_model.encode(topic.strip())

    # ------------------------------
    # 2. 基础检索：日期检索（支持秒级时间输入）
    # ------------------------------
    def search_by_date(self, start_time: str, end_time: Optional[str] = None) -> List[Dict[str, str]]:
        # 提取纯日期
        start_date = self._extract_date(start_time)
        end_date = self._extract_date(end_time) if end_time else start_date

        # 验证日期逻辑
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError as e:
            raise ValueError(f"日期解析失败：{str(e)}")

        if start_dt > end_dt:
            raise ValueError(f"开始日期 {start_date} 不能晚于结束日期 {end_date}")

        # 筛选记忆
        memory_array = []
        for date_str in self.memories:
            date_dt = datetime.strptime(date_str, "%Y-%m-%d")
            if start_dt <= date_dt <= end_dt:
                memory_array.extend(self.memories[date_str])
        return memory_array

    # ------------------------------
    # 3. 基础检索：Topic嵌入检索（无日期输入，无需适配）
    # ------------------------------
    def search_by_topic_embedding(self, query_topic: str, top_n: int = 10) -> List[Dict[str, str]]:
        query_emb = self.embedding_model.encode(query_topic.strip())
        similarity_list = [
            (eid, np.dot(query_emb, emb) / (np.linalg.norm(query_emb) * np.linalg.norm(emb) + 1e-8))
            for eid, emb in self.embeddings.items()
        ]
        # 按相似度降序排序
        similarity_list.sort(key=lambda x: x[1], reverse=True)

        # 提取纯记忆数组
        memory_array = []
        for eid, _ in similarity_list[:top_n]:
            if eid not in self.event_id_map:
                continue
            date, idx = self.event_id_map[eid]
            memory_array.append(self.memories[date][idx])
        return memory_array

    # ------------------------------
    # 4. 混合检索：日期+Topic组合检索（新增，支持秒级时间输入）
    # ------------------------------
    def search_by_date_and_topic(self,
                                 query_topic: str,
                                 start_time: str,
                                 end_time: Optional[str] = None,
                                 top_n: int = 10) -> List[Dict[str, str]]:
        """
        组合检索：筛选指定日期范围内、且与Topic语义相似的记忆（支持秒级时间输入）
        """
        # 第一步：筛选指定日期范围内的记忆
        date_filtered_memories = self.search_by_date(start_time, end_time)
        if not date_filtered_memories:
            return []  # 无符合日期条件的记忆，直接返回空

        # 第二步：为日期筛选后的记忆计算Topic相似度
        query_emb = self.embedding_model.encode(query_topic.strip())
        memory_similarity = []
        for mem in date_filtered_memories:
            # 用记忆的Topic生成嵌入向量
            mem_topic_emb = self.embedding_model.encode(mem["topic"].strip())
            # 计算相似度
            sim = np.dot(query_emb, mem_topic_emb) / (np.linalg.norm(query_emb) * np.linalg.norm(mem_topic_emb) + 1e-8)
            memory_similarity.append((mem, float(sim)))

        # 第三步：按相似度降序排序，取前top_n
        memory_similarity.sort(key=lambda x: x[1], reverse=True)
        return [mem for mem, _ in memory_similarity[:top_n]]

    # ------------------------------
    # 5. 单条检索：ID检索（无日期输入，无需适配）
    # ------------------------------
    def get_memory_by_id(self, event_id: str) -> Optional[Dict[str, str]]:
        if event_id not in self.event_id_map:
            return None
        date, idx = self.event_id_map[event_id]
        return self.memories[date][idx]

    # ------------------------------
    # 6. 删除功能：删除i月之前记忆（无时间输入，无需适配）
    # ------------------------------
    def delete_memories_before_month(self, target_year: int, target_month: int) -> Dict[str, int]:
        if not isinstance(target_year, int) or target_year < 1970:
            raise ValueError(f"年份必须≥1970，当前输入：{target_year}")
        if not isinstance(target_month, int) or not (1 <= target_month <= 12):
            raise ValueError(f"月份必须1-12，当前输入：{target_month}")

        with self._lock:  # 线程安全保护
            delete_threshold = datetime(target_year, target_month, 1)
            retained_memories = {}
            deleted_count = 0

            for date_str, mem_list in self.memories.items():
                date_dt = datetime.strptime(date_str, "%Y-%m-%d")
                if date_dt < delete_threshold:
                    deleted_count += len(mem_list)
                else:
                    retained_memories[date_str] = mem_list

            # 同步更新关联数据
            self.memories = retained_memories
            retained_eids = set()
            for date_str, mem_list in self.memories.items():
                for idx in range(len(mem_list)):
                    for eid, (d, i) in self.event_id_map.items():
                        if d == date_str and i == idx:
                            retained_eids.add(eid)
                            break

            # 删除无效ID和嵌入向量
            for eid in list(self.event_id_map.keys()):
                if eid not in retained_eids:
                    del self.event_id_map[eid]
                    if eid in self.embeddings:
                        del self.embeddings[eid]

            self.save_to_file()
            return {
                "deleted_memory_count": deleted_count,
                "deleted_date_count": len(self.memories) - len(retained_memories)
            }

    # ------------------------------
    # 数据持久化
    # ------------------------------
    def save_to_file(self) -> None:
        with self._lock:  # 线程安全保护
            serializable_embeddings = {k: v.tolist() for k, v in self.embeddings.items()}
            data = {
                "memories": self.memories,
                "embeddings": serializable_embeddings,
                "event_id_counter": self.event_id_counter,
                "event_id_map": self.event_id_map
            }
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

    def load_from_file(self) -> None:
        with self._lock:  # 线程安全保护
            with open(self.memory_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.memories = data.get("memories", {})
            self.embeddings = {k: np.array(v) for k, v in data.get("embeddings", {}).items()}
            self.event_id_counter = data.get("event_id_counter", 0)
            self.event_id_map = data.get("event_id_map", {})
