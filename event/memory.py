import json
import os
from datetime import datetime
from collections import defaultdict
import numpy as np
from typing import List, Dict, Any, Optional, Tuple

# 导入sentence-transformers库
from sentence_transformers import SentenceTransformer


class PersonalMemoryManager:
    def __init__(self,
                 memory_file: str = "personal_memories.json",
                 model_path: str = "./local_models/all-MiniLM-L6-v2"):
        """
        初始化个人记忆管理器，使用本地预训练嵌入模型

        参数:
            memory_file: 存储记忆数据的JSON文件路径
            model_path: 本地模型文件夹路径（支持相对路径或绝对路径）
        """
        # 禁用huggingface的符号链接警告
        os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

        self.memory_file = memory_file
        # 将模型路径转换为绝对路径，避免相对路径识别问题
        self.model_path = os.path.abspath(model_path)
        self.memories = {}  # 存储所有记忆 {日期: [事件列表]}
        self.keyword_index = defaultdict(list)  # 关键词索引
        self.embeddings = {}  # 嵌入向量 {事件ID: 向量}
        self.event_id_counter = 0  # 事件ID计数器
        self.event_id_map = {}  # 事件ID到(日期, 事件索引)的映射

        # 确保存储目录存在
        self._ensure_directory_exists()

        # 加载本地嵌入模型
        self.embedding_model = self._load_local_model()

        # 如果文件存在则加载
        if os.path.exists(memory_file):
            try:
                self.load_from_file()
            except json.JSONDecodeError:
                # 如果文件损坏，创建新文件
                print(f"警告: {memory_file} 文件损坏，将创建新文件")
                self.save_to_file()
        else:
            # 初始化空文件
            self.save_to_file()

    def _load_local_model(self) -> SentenceTransformer:
        """加载本地模型，确保路径被正确识别为本地目录"""
        # 检查模型路径是否存在
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(
                f"本地模型目录不存在: {self.model_path}\n"
                "请确认模型路径正确，或从以下地址下载模型：\n"
                "https://gitee.com/mirrors/sentence-transformers-all-MiniLM-L6-v2/archive/refs/heads/main.zip"
            )

        # 检查是否是目录
        if not os.path.isdir(self.model_path):
            raise NotADirectoryError(
                f"{self.model_path} 不是一个目录，请提供模型文件夹的路径"
            )

        # 检查必要的模型文件
        required_files = ["config.json", "pytorch_model.bin", "tokenizer_config.json", "vocab.txt"]
        missing_files = []
        for file in required_files:
            file_path = os.path.join(self.model_path, file)
            if not os.path.exists(file_path):
                missing_files.append(file)

        if missing_files:
            raise FileNotFoundError(
                f"模型文件不完整，缺少以下文件: {', '.join(missing_files)}\n"
                "请重新下载完整的模型文件"
            )

        # 关键修复：明确指定本地路径，避免被识别为Hugging Face仓库
        try:
            # 使用绝对路径加载，并通过参数暗示这是本地文件
            return SentenceTransformer(self.model_path)
        except Exception as e:
            # 更详细的错误提示
            raise RuntimeError(
                f"加载本地模型失败: {str(e)}\n"
                f"请检查模型路径是否正确: {self.model_path}\n"
                "确保该路径下包含完整的模型文件"
            )

    def _ensure_directory_exists(self) -> None:
        """确保存储文件和模型的目录存在"""
        # 确保记忆文件目录存在
        memory_dir = os.path.dirname(self.memory_file)
        if memory_dir and not os.path.exists(memory_dir):
            os.makedirs(memory_dir, exist_ok=True)

        # 确保模型目录存在（如果不存在会在_load_local_model中提示）
        model_dir = os.path.dirname(self.model_path)
        if model_dir and not os.path.exists(model_dir):
            os.makedirs(model_dir, exist_ok=True)

    def add_memory(self, date: str, event: Dict[str, str]) -> str:
        """
        添加新的记忆事件

        参数:
            date: 日期，格式为"YYYY-MM-DD"
            event: 事件字典，包含"事件标题"、"发生时间段"、"详细描述"、"关键词"

        返回:
            事件ID
        """
        # 验证日期格式
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise ValueError("日期格式必须为YYYY-MM-DD")

        # 确保事件包含必要字段
        required_fields = ["事件标题", "发生时间段", "详细描述", "关键词"]
        for field in required_fields:
            if field not in event:
                raise ValueError(f"事件缺少必要字段: {field}")

        # 为事件生成ID
        self.event_id_counter += 1
        event_id = f"event_{self.event_id_counter}"

        # 添加到记忆存储
        if date not in self.memories:
            self.memories[date] = []
        event_index = len(self.memories[date])
        self.memories[date].append(event)

        # 更新事件ID映射
        self.event_id_map[event_id] = (date, event_index)

        # 更新关键词索引
        keywords = [kw.strip() for kw in event["关键词"].split(',')]
        for keyword in keywords:
            self.keyword_index[keyword].append((date, event_index))

        # 使用预训练模型生成嵌入向量
        self._generate_embedding(event_id, event)

        # 保存到文件
        self.save_to_file()

        return event_id

    def _generate_embedding(self, event_id: str, event: Dict[str, str]) -> None:
        """使用预训练模型为事件生成嵌入向量"""
        # 组合事件信息生成一个文本字符串
        text_parts = [
            event["事件标题"],
            event["发生时间段"],
            event["详细描述"],
            event["关键词"]
        ]
        text = " ".join(text_parts)

        # 生成嵌入向量
        embedding = self.embedding_model.encode(text)

        self.embeddings[event_id] = embedding

    def search_by_keyword(self, keywords: List[str], top_n: Optional[int] = None) -> List[Dict[str, Any]]:
        """通过关键词检索记忆"""
        # 统计每个事件的关键词匹配次数
        match_counts = defaultdict(int)

        for keyword in keywords:
            for date, event_idx in self.keyword_index.get(keyword, []):
                match_counts[(date, event_idx)] += 1

        # 按匹配次数排序
        sorted_matches = sorted(match_counts.items(), key=lambda x: x[1], reverse=True)

        # 构建结果
        results = []
        for (date, event_idx), count in sorted_matches[:top_n]:
            event = self.memories[date][event_idx]
            results.append({
                "日期": date,
                "事件索引": event_idx,
                "匹配关键词数量": count,
                "事件详情": event
            })

        return results

    def search_by_date(self, start_date: str, end_date: Optional[str] = None) -> Dict[str, List[Dict[str, str]]]:
        """通过日期范围检索记忆"""
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d") if end_date else start
        except ValueError:
            raise ValueError("日期格式必须为YYYY-MM-DD")

        if start > end:
            raise ValueError("开始日期不能晚于结束日期")

        results = {}
        for date_str in self.memories:
            date = datetime.strptime(date_str, "%Y-%m-%d")
            if start <= date <= end:
                results[date_str] = self.memories[date_str]

        return results

    def search_by_similarity(self, query: str, top_n: int = 10) -> List[Dict[str, Any]]:
        """通过语义相似度检索记忆"""
        # 生成查询的嵌入向量
        query_embedding = self.embedding_model.encode(query)

        # 计算与所有事件的相似度
        similarities = []
        for event_id, embedding in self.embeddings.items():
            # 计算余弦相似度
            sim = np.dot(query_embedding, embedding) / (
                    np.linalg.norm(query_embedding) * np.linalg.norm(embedding) + 1e-8
            )
            similarities.append((event_id, sim))

        # 按相似度排序
        similarities.sort(key=lambda x: x[1], reverse=True)

        # 构建结果
        results = []
        for event_id, sim in similarities[:top_n]:
            if event_id not in self.event_id_map:
                continue

            date, event_idx = self.event_id_map[event_id]
            event = self.memories[date][event_idx]

            results.append({
                "日期": date,
                "事件索引": event_idx,
                "相似度": float(sim),
                "事件详情": event
            })

        return results

    def combined_search(self, keywords: List[str] = None,
                        start_date: str = None,
                        end_date: str = None,
                        query: str = None,
                        top_n: int = 10) -> List[Dict[str, Any]]:
        """组合检索，可以同时使用关键词、日期范围和语义相似度"""
        # 获取各检索方式的结果
        keyword_results = set()
        if keywords:
            for item in self.search_by_keyword(keywords):
                key = (item["日期"], item["事件索引"])
                keyword_results.add(key)

        date_results = set()
        if start_date:
            date_memories = self.search_by_date(start_date, end_date)
            for date, events in date_memories.items():
                for idx in range(len(events)):
                    date_results.add((date, idx))

        similarity_results = []
        if query:
            similarity_results = self.search_by_similarity(query)
            similarity_dict = {
                (item["日期"], item["事件索引"]): item["相似度"]
                for item in similarity_results
            }

        # 确定候选集：如果指定了多种检索方式，取交集
        candidates = set()
        has_filters = False

        if keyword_results:
            candidates.update(keyword_results)
            has_filters = True
        if date_results:
            if candidates:  # 与现有候选取交集
                candidates.intersection_update(date_results)
            else:
                candidates.update(date_results)
            has_filters = True

        # 如果没有指定任何过滤条件，使用所有记忆
        if not has_filters:
            for date, events in self.memories.items():
                for idx in range(len(events)):
                    candidates.add((date, idx))

        # 为候选计算综合分数
        scores = {}
        for (date, idx) in candidates:
            # 基础分
            score = 1.0

            # 关键词匹配加分
            if (date, idx) in keyword_results:
                # 找到匹配的关键词数量
                kw_count = next(
                    item["匹配关键词数量"] for item in self.search_by_keyword(keywords)
                    if item["日期"] == date and item["事件索引"] == idx
                )
                score += kw_count * 0.5

            # 相似度加分
            if (date, idx) in similarity_dict:
                score += similarity_dict[(date, idx)] * 0.8

            scores[(date, idx)] = score

        # 按分数排序
        sorted_candidates = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        # 构建结果
        results = []
        for (date, idx), score in sorted_candidates[:top_n]:
            event = self.memories[date][idx]
            results.append({
                "日期": date,
                "事件索引": idx,
                "综合分数": float(score),
                "事件详情": event
            })

        return results

    def get_top_20_relevant_memories(self,
                                     keywords: List[str] = None,
                                     query: str = None) -> List[Dict[str, Any]]:
        """
        基于关键词和语义相似度的混合检索，提取20个最相关记忆

        参数:
            keywords: 关键词列表
            query: 语义查询字符串

        返回:
            20个最相关的记忆列表，按综合相关性排序
        """
        # 获取各检索方式的结果
        keyword_results = set()
        if keywords:
            # 获取所有关键词匹配结果（不限制数量）
            for item in self.search_by_keyword(keywords):
                key = (item["日期"], item["事件索引"])
                keyword_results.add(key)

        similarity_results = []
        similarity_dict = {}
        if query:
            # 获取更多相似度结果用于综合评分
            similarity_results = self.search_by_similarity(query, top_n=100)
            similarity_dict = {
                (item["日期"], item["事件索引"]): item["相似度"]
                for item in similarity_results
            }

        # 确定候选集：如果指定了多种检索方式，取并集而非交集
        # 这样即使只匹配一种检索方式也能被考虑
        candidates = set()

        if keyword_results:
            candidates.update(keyword_results)
        if similarity_dict:
            candidates.update(similarity_dict.keys())

        # 如果没有指定任何检索条件，使用所有记忆
        if not candidates:
            for date, events in self.memories.items():
                for idx in range(len(events)):
                    candidates.add((date, idx))

        # 如果候选集为空，返回空列表
        if not candidates:
            return []

        # 为候选计算综合分数（关键词40% + 语义相似度60%）
        scores = {}
        for (date, idx) in candidates:
            # 基础分
            score = 0.0

            # 关键词匹配加分 (权重：40%)
            kw_score = 0.0
            if keywords and (date, idx) in keyword_results:
                # 找到匹配的关键词数量
                for item in self.search_by_keyword(keywords):
                    if item["日期"] == date and item["事件索引"] == idx:
                        kw_count = item["匹配关键词数量"]
                        # 关键词数量越多得分越高，最多匹配10个关键词
                        kw_score = min(kw_count * 0.1, 1.0)  # 0-1之间
                        break
            score += kw_score * 0.4

            # 相似度加分 (权重：60%)
            sim_score = 0.0
            if query and (date, idx) in similarity_dict:
                sim_score = similarity_dict[(date, idx)]  # 0-1之间
            score += sim_score * 0.6

            scores[(date, idx)] = score

        # 按分数排序并获取前20个
        sorted_candidates = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        # 构建结果
        results = []
        for (date, idx), score in sorted_candidates[:20]:
            event = self.memories[date][idx]
            results.append({
                "日期": date,
                "事件索引": idx,
                "综合相关分数": round(float(score), 4),
                "事件详情": event,
                "匹配分析": {
                    "关键词得分": round(kw_score, 4) if 'kw_score' in locals() else 0,
                    "语义相似度得分": round(sim_score, 4) if 'sim_score' in locals() else 0
                }
            })

        return results

    def save_to_file(self) -> None:
        """将记忆数据保存到JSON文件"""
        data = {
            "memories": self.memories,
            "keyword_index": {k: v for k, v in self.keyword_index.items()},
            "embeddings": {k: v.tolist() for k, v in self.embeddings.items()},
            "event_id_counter": self.event_id_counter,
            "event_id_map": self.event_id_map
        }

        with open(self.memory_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_from_file(self) -> None:
        """从JSON文件加载记忆数据"""
        with open(self.memory_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.memories = data["memories"]
        self.keyword_index = defaultdict(list)
        for k, v in data["keyword_index"].items():
            self.keyword_index[k] = v

        self.embeddings = {k: np.array(v) for k, v in data["embeddings"].items()}
        self.event_id_counter = data["event_id_counter"]
        self.event_id_map = data["event_id_map"]

    def get_memory_by_id(self, event_id: str) -> Optional[Dict[str, Any]]:
        """通过事件ID获取记忆"""
        if event_id not in self.event_id_map:
            return None

        date, idx = self.event_id_map[event_id]
        return {
            "日期": date,
            "事件索引": idx,
            "事件详情": self.memories[date][idx]
        }

    def get_all_dates(self) -> List[str]:
        """获取所有有记录的日期"""
        return sorted(self.memories.keys())


# 使用示例
if __name__ == "__main__":
    # 初始化记忆管理器
    memory_manager = PersonalMemoryManager("../memory/long_memory.json")

    # 示例数据
    sample_events = {
    "2025-01-01": [
        {
            "事件标题": "晨间瑜伽锻炼",
            "发生时间段": "7:30-8:00",
            "详细描述": "在客厅空地铺开瑜伽垫，播放轻音乐歌单，进行20分钟流瑜伽练习。专注于呼吸和伸展，感受肌肉微微酸痛，提醒自己BMI偏高需坚持运动。结束后喝一口温水，身体暖和起来，为全天注入活力。",
            "关键词": "徐静,瑜伽,锻炼,身体,健康"
        },
        {
            "事件标题": "早餐享用",
            "发生时间段": "8:00-8:30",
            "详细描述": "在厨房冲泡一杯热抹茶拿铁，搭配昨晚剩余的草莓蛋糕切片，坐在餐桌旁慢慢享用。蛋糕甜腻与抹茶苦涩平衡，我边吃边用手机浏览新闻，注意到元旦促销信息，顺手保存以备工作参考。",
            "关键词": "徐静,喝,抹茶拿铁,吃,蛋糕"
        },
        {
            "事件标题": "远程工作准备",
            "发生时间段": "8:30-9:30",
            "详细描述": "在书房书桌前，打开笔记本电脑，先检查电子库存盘点表格，确认明日所需标签和数据格式；同时通过工作微信群与3名店员沟通，安排明日盘点的区域分工，强调时间要求。窗外雨声渐大，我偶尔抬头看雨，心想假期还得处理工作，但提前准备能减轻明日压力。",
            "关键词": "徐静,准备,盘点工具,协调,员工"
        },
        {
            "事件标题": "元旦聚餐准备",
            "发生时间段": "9:30-11:30",
            "详细描述": "转入厨房，母亲已系好围裙，我加入她播放轻音乐，氛围轻松。我们先清洗蔬菜和猪肉，仔细切配小笼包馅料；我负责调味，加入姜末和酱油，香气弥漫。同时装饰草莓蛋糕，用奶油裱花点缀，母亲夸我手艺进步。布置餐桌时，我挑选节日主题餐垫和餐具，摆放装饰品如小蜡烛，确保氛围温馨。",
            "关键词": "徐静,准备,小笼包,装饰,蛋糕"
        },
        {
            "事件标题": "家庭聚餐互动",
            "发生时间段": "11:30-13:00",
            "详细描述": "在餐厅，父母和一位姑姑围坐餐桌，我端上热腾腾的小笼包和抹茶拿铁。大家举杯敬酒，我分享服装店销售中的趣事，如顾客试衣搞笑瞬间；讨论新年目标时，我提到开店计划，父母给出建议。餐桌上笑声连连，我拍照留念，照片中小笼包蒸汽氤氲，捕捉到家庭温馨。",
            "关键词": "徐静,分享,趣事,讨论,目标"
        },
        {
            "事件标题": "餐后清理复盘",
            "发生时间段": "13:00-14:00",
            "详细描述": "聚餐后，在厨房和餐厅与家人一起收拾：我洗碗，母亲擦桌子，整理餐具时检查是否有破损。回顾过程，我用手机备忘录记录花费和反馈，如“小笼包馅料可再加点糖”，并思考下次改进点，计划增加旅行主题装饰。",
            "关键词": "徐静,清理,餐具,记录,反馈"
        },
        {
            "事件标题": "个人爱好处理",
            "发生时间段": "14:00-15:00",
            "详细描述": "在客厅沙发休息，播放收藏的轻音乐，边喝剩余抹茶拿铁边简单查看纪念币收藏盒。取出几枚硬币用软布擦拭，检查保存状况，为周末详细整理做铺垫。雨停后阳光微露，我靠在沙发上小憩10分钟，精神恢复。",
            "关键词": "徐静,查看,纪念币,休息,音乐"
        },
        {
            "事件标题": "新年目标细化",
            "发生时间段": "15:00-16:30",
            "详细描述": "在书房安静角落，使用便签和电子表格，将目标分为短期（如每月存钱5000元用于开店）和长期（带父母旅行）。考虑薪资和资源限制，我优先排序开店步骤，评估可行性后设置截止日期。写便签时，我反思BMI问题，加入“每周瑜伽三次”具体化。",
            "关键词": "徐静,细化,目标,排序,计划"
        },
        {
            "事件标题": "周计划制定",
            "发生时间段": "16:30-18:00",
            "详细描述": "移至客厅，继续播放音乐，在笔记本电脑上制定详细周计划。创建日历事件，分配时间块：如明天库存盘点固定时段，每周三次瑜伽分解为附近健身房具体时间。记录提醒事项时，我加入供应商合同跟进，确保工作与生活平衡。",
            "关键词": "徐静,制定,计划,分配,时间"
        },
        {
            "事件标题": "合同文件整理",
            "发生时间段": "18:00-19:00",
            "详细描述": "在厨房快速准备晚餐：热剩菜和小笼包，搭配清茶。边吃边在书房打印3家供应商合同草案，用不同颜色标签分类重点条款，如价格和交货期限。我核对条款时，发现一处模糊点，标记需明日复核。",
            "关键词": "徐静,整理,合同,分类,条款"
        },
        {
            "事件标题": "家庭休闲交流",
            "发生时间段": "19:00-20:00",
            "详细描述": "在客厅与父母看电视节目，闲聊今日聚餐感受。我提到新年目标进展，父母鼓励我坚持瑜伽。突发接到闺蜜微信，约定周末电影之夜细节，我回复确认，心情放松。",
            "关键词": "徐静,交流,家庭,约定,电影"
        },
        {
            "事件标题": "晚间睡前准备",
            "发生时间段": "20:00-21:00",
            "详细描述": "在卧室用电子设备查看今日照片和备忘录，复盘目标规划进度，设置明日闹钟。洗漱时，我反思今天事件全部完成，无延迟需求，因工作事件已简化融入。睡前读几页书，渐入梦乡。",
            "关键词": "徐静,复盘,进度,准备,睡眠"
        }
    ]
}

    # 添加示例数据
    for date, events in sample_events.items():
        for event in events:
            memory_manager.add_memory(date, event)

    # 1. 关键词检索
    print("=== 关键词检索 ===")
    keyword_results = memory_manager.search_by_keyword(["早餐", "抹茶"], top_n=2)
    print(json.dumps(keyword_results, ensure_ascii=False, indent=2))

    # 2. 日期检索
    print("\n=== 日期检索 ===")
    date_results = memory_manager.search_by_date("2025-01-01", "2025-01-02")
    print(json.dumps(date_results, ensure_ascii=False, indent=2))

    # 3. 相似度检索（使用模型生成的嵌入向量）
    print("\n=== 相似度检索 ===")
    similarity_results = memory_manager.search_by_similarity("早上做的事情", top_n=3)
    print(json.dumps(similarity_results, ensure_ascii=False, indent=2))

    # 4. 组合检索
    print("\n=== 组合检索 ===")
    combined_results = memory_manager.combined_search(
        keywords=["我", "早晨"],
        start_date="2025-01-01",
        end_date="2025-01-02",
        query="早上的活动",
        top_n=3
    )
    print(json.dumps(combined_results, ensure_ascii=False, indent=2))
