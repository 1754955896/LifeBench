import json
import os
import threading
from datetime import datetime
from collections import defaultdict
import numpy as np
from typing import List, Dict, Any, Optional

from sentence_transformers import SentenceTransformer


class MemoryModule:
    """记忆模块（全局单例/多例可选，统一管理记忆操作）"""
    _instances: Dict[str, "MemoryModule"] = {}
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls, instance_id: str = "default", memory_file: Optional[str] = None) -> "MemoryModule":
        with cls._lock:
            if instance_id not in cls._instances:
                cls._instances[instance_id] = cls()
                cls._instances[instance_id]._init_memory_manager(memory_file)
            return cls._instances[instance_id]

    def _init_memory_manager(self, memory_file: Optional[str] = None):
        """初始化记忆管理器"""
        self.mem_mgr = PersonalMemoryManager(memory_file=memory_file)

    def add_memory(self, data: Any):
        """添加记忆"""
        return self.mem_mgr.add_memory(data)

    def search_by_date(self, start_time: str) -> List[Dict]:
        """按日期检索记忆"""
        return self.mem_mgr.search_by_date(start_time)

    def search_by_topic_embedding(self, topic: str, top_k: int) -> List[Dict]:
        """按主题向量检索记忆"""
        return self.mem_mgr.search_by_topic_embedding(topic, top_k)

    @classmethod
    def destroy_instance(cls, instance_id: str = "default"):
        """销毁指定实例"""
        with cls._lock:
            if instance_id in cls._instances:
                del cls._instances[instance_id]


class PersonalMemoryManager:
    def __init__(self,
                 memory_file: str = os.path.join("memory_file", "personal_memories.json"),
                 model_path: str = "event/local_models/all-MiniLM-L6-v2"):
        os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

        self.memory_file = memory_file
        self.model_path = os.path.abspath(model_path)
        self.memories = {}  # {日期(XX-XX-XX): [记忆对象列表]}
        self.embeddings = {}  # {事件ID: 向量}
        self.event_id_counter = 0
        self.event_id_map = {}  # {事件ID: (日期(XX-XX-XX), 记忆索引)}
        self._lock = threading.RLock()  # 使用可重入锁，避免递归锁请求导致的死锁

        self._ensure_directory_exists()
        self.embedding_model = self._load_local_model()
        self._load_or_init_memory_file()

    def _load_local_model(self) -> SentenceTransformer:
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(
                f"本地模型目录不存在: {self.model_path}\n"
                "请从以下地址下载模型：\n"
                "https://gitee.com/mirrors/sentence-transformers-all-MiniLM-L6-v2/archive/refs/heads/main.zip"
            )
        if not os.path.isdir(self.model_path):
            raise NotADirectoryError(f"{self.model_path} 不是有效目录")

        required_files = ["config.json", "pytorch_model.bin", "tokenizer_config.json", "vocab.txt"]
        missing_files = [f for f in required_files if not os.path.exists(os.path.join(self.model_path, f))]
        if missing_files:
            raise FileNotFoundError(f"模型缺少关键文件: {', '.join(missing_files)}")

        try:
            return SentenceTransformer(self.model_path)
        except Exception as e:
            raise RuntimeError(f"模型加载失败: {str(e)}")

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
    # 通用日期工具：提取秒级时间中的纯日期（XX-XX-XX）
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

        参数:
            query_topic: 检索关键词（如"早餐"）
            start_time: 开始时间（支持XX-XX-XX或XX-XX-XX XX:XX:XX）
            end_time: 结束时间（可选，默认与start_time相同）
            top_n: 返回最相似的记忆数量，默认10

        返回:
            List[Dict[str, str]]: 符合条件的纯记忆单元数组（按相似度降序）
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


# ------------------------------
# 使用示例（验证所有检索功能）
# ------------------------------
if __name__ == "__main__":
    memory_manager = PersonalMemoryManager(memory_file=os.path.join("memory_file", "all_search_memories.json"))

    # 1. 添加测试记忆（含秒级时间输入）
    test_memories = [
        {"date": "2025-11-01 07:30:00", "topic": "晨间瑜伽", "events": "20分钟流瑜伽", "thought": "坚持运动"},
        {"date": "2025-11-01 08:15:00", "topic": "早餐", "events": "全麦面包+牛奶", "thought": "健康饮食"},
        {"date": "2025-11-02 14:30:00", "topic": "工作会议", "events": "项目复盘", "thought": "提前准备议题"},
        {"date": "2025-11-03", "topic": "晚餐", "events": "在家做饭", "thought": "减少外卖"}  # 纯日期输入
    ]
    for mem in test_memories:
        memory_manager.add_memory(mem)
    print("=== 初始化完成：已添加4条记忆 ===")

    # 2. 测试「日期检索」（输入秒级时间）
    print("\n=== 1. 日期检索（输入：2025-11-01 12:00:00）===")
    date_result = memory_manager.search_by_date(start_time="2025-11-01 12:00:00")
    print(f"检索结果数量：{len(date_result)}")
    for mem in date_result:
        print(f"  - 主题：{mem['topic']} | 日期：{mem['date']}")

    # 3. 测试「Topic嵌入检索」（无日期输入）
    print("\n=== 2. Topic检索（关键词：饮食）===")
    topic_result = memory_manager.search_by_topic_embedding(query_topic="饮食", top_n=2)
    print(f"检索结果数量：{len(topic_result)}")
    for mem in topic_result:
        print(f"  - 主题：{mem['topic']} | 日期：{mem['date']}")

    # 4. 测试「日期+Topic组合检索」（输入秒级时间）
    print("\n=== 3. 组合检索（时间：2025-11-01至2025-11-02 23:59:59，关键词：上午活动）===")
    combo_result = memory_manager.search_by_date_and_topic(
        query_topic="上午活动",
        start_time="2025-11-01 00:00:00",
        end_time="2025-11-02 23:59:59",
        top_n=2
    )
    print(f"检索结果数量：{len(combo_result)}")
    for mem in combo_result:
        print(f"  - 主题：{mem['topic']} | 日期：{mem['date']}")

    # 5. 测试「ID检索」
    print("\n=== 4. ID检索（ID：event_1）===")
    id_result = memory_manager.get_memory_by_id("event_1")
    print(f"检索结果：{json.dumps(id_result, ensure_ascii=False, indent=2)}")