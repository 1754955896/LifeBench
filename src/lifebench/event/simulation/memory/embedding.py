# -*- coding: utf-8 -*-
"""嵌入模型加载与编码。

从 PersonalMemoryManager 抽出本地 SentenceTransformer 模型的加载与单条编码逻辑，
供 MemoryStore 使用（语义不变，仅结构调整）。
"""
import os

from sentence_transformers import SentenceTransformer

DEFAULT_MODEL_DIRNAME = "all-MiniLM-L6-v2"
REQUIRED_MODEL_FILES = ["config.json", "pytorch_model.bin", "tokenizer_config.json", "vocab.txt"]


class EmbeddingModel:
    """本地 SentenceTransformer 模型的加载与编码封装。"""

    def __init__(self, model_path: str = None):
        os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
        if model_path is None:
            model_path = self.default_model_path()
        self.model_path = os.path.abspath(model_path)
        self.model = self._load()

    @staticmethod
    def default_model_path() -> str:
        # embedding.py 位于 src/lifebench/event/simulation/memory/
        # 向上 3 层到 src/lifebench/event，再拼接 local_models
        event_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return os.path.join(event_dir, "local_models", DEFAULT_MODEL_DIRNAME)

    def _load(self) -> SentenceTransformer:
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(
                f"本地模型目录不存在: {self.model_path}\n"
                "请从以下地址下载模型：\n"
                "https://gitee.com/mirrors/sentence-transformers-all-MiniLM-L6-v2/archive/refs/heads/main.zip"
            )
        if not os.path.isdir(self.model_path):
            raise NotADirectoryError(f"{self.model_path} 不是有效目录")

        missing_files = [f for f in REQUIRED_MODEL_FILES if not os.path.exists(os.path.join(self.model_path, f))]
        if missing_files:
            raise FileNotFoundError(f"模型缺少关键文件: {', '.join(missing_files)}")

        try:
            return SentenceTransformer(self.model_path)
        except Exception as e:
            raise RuntimeError(f"模型加载失败: {str(e)}")

    def encode(self, text: str):
        return self.model.encode(text)
