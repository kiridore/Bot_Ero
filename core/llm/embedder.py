from __future__ import annotations

import threading


class Embedder:
    """句向量模型封装；进程内单例，多次 ``Embedder()`` 只初始化一次底层模型。"""

    _instance: Embedder | None = None
    _init_lock = threading.Lock()

    def __new__(cls) -> Embedder:
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer("BAAI/bge-small-zh")
        self._initialized = True

    def embed(self, texts):
        if isinstance(texts, str):
            texts = [texts]
        return self.model.encode(texts, normalize_embeddings=True)


def preload_embedder_model() -> Embedder:
    """在进程启动时调用，提前加载句向量模型，避免首条依赖向量的任务长时间阻塞。"""
    return Embedder()
