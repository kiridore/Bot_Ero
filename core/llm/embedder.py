from __future__ import annotations

import math
import os
import threading
from typing import Sequence

import requests


class Embedder:
    """在线 embedding 客户端封装；进程内单例。"""

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
        api_key = os.getenv("SIFLOW_API_KEY", "").strip()
        if not api_key:
            raise ValueError("Missing SIFLOW_API_KEY for embedding API.")

        self.base_url = "https://api.siliconflow.cn/v1/embeddings"
        self.model = "BAAI/bge-m3"
        self.timeout = 30
        self.session = requests.Session()
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self._initialized = True

    @staticmethod
    def _normalize(vector: Sequence[float]) -> list[float]:
        norm = math.sqrt(sum(float(x) * float(x) for x in vector))
        if norm <= 0:
            return [float(x) for x in vector]
        return [float(x) / norm for x in vector]

    def _embed_one(self, text: str) -> list[float]:
        payload = {"model": self.model, "input": text}
        response = self.session.post(
            self.base_url,
            json=payload,
            headers=self.headers,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        items = data.get("data")
        if not isinstance(items, list) or not items:
            raise ValueError(f"Invalid embedding response: {data}")
        embedding = items[0].get("embedding")
        if not isinstance(embedding, list):
            raise ValueError(f"Invalid embedding vector: {data}")
        return self._normalize(embedding)

    def embed(self, texts):
        if isinstance(texts, str):
            texts = [texts]
        vectors: list[list[float]] = []
        for text in texts:
            vectors.append(self._embed_one(str(text)))
        return vectors
