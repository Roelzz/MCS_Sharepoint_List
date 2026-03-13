from typing import List
from enum import Enum

from openai import AsyncAzureOpenAI, AsyncOpenAI
# from sentence_transformers import SentenceTransformer  # Requires optional dependency

from ..config import settings, EmbeddingProvider

class Embedder:
    def __init__(self):
        self._client = None

    @property
    def provider(self):
        return settings.EMBEDDING_PROVIDER

    @property
    def client(self):
        if self._client is None:
            if self.provider == EmbeddingProvider.AZURE_OPENAI:
                self._client = AsyncAzureOpenAI(
                    api_key=settings.AZURE_OPENAI_KEY,
                    api_version=settings.OPENAI_API_VERSION,
                    azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
                )
            elif self.provider == EmbeddingProvider.OPENAI:
                self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        return self._client

    async def embed_texts(self, texts: List[str], batch_size: int = 256) -> List[List[float]]:
        if not texts:
            return []

        if self.provider in [EmbeddingProvider.AZURE_OPENAI, EmbeddingProvider.OPENAI]:
            all_embeddings: List[List[float]] = []
            for i in range(0, len(texts), batch_size):
                batch = texts[i : i + batch_size]
                response = await self.client.embeddings.create(
                    input=batch,
                    model=settings.AZURE_OPENAI_DEPLOYMENT,
                )
                all_embeddings.extend(data.embedding for data in response.data)
            return all_embeddings

        elif self.provider == EmbeddingProvider.LOCAL:
            return [[0.0] * 384 for _ in texts]

        return []

# Singleton
embedder = Embedder()
