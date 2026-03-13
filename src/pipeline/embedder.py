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

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        if self.provider in [EmbeddingProvider.AZURE_OPENAI, EmbeddingProvider.OPENAI]:
            response = await self.client.embeddings.create(
                input=texts,
                model=settings.AZURE_OPENAI_DEPLOYMENT
            )
            return [data.embedding for data in response.data]
        
        elif self.provider == EmbeddingProvider.LOCAL:
            # return self.model.encode(texts).tolist()
            # Placeholder for now as we don't want to install torch/transformers in this step
            # unless requested.
            return [[0.0] * 384 for _ in texts]  # Mock
            
        return []

# Singleton
embedder = Embedder()
