import os
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

class EmbeddingProvider(str, Enum):
    AZURE_OPENAI = "azure_openai"
    OPENAI = "openai"
    LOCAL = "local"

class TransportType(str, Enum):
    STDIO = "stdio"
    SSE = "sse"

class Settings(BaseSettings):
    # Azure AD Auth
    TENANT_ID: str = ""
    CLIENT_ID: str = ""
    CLIENT_SECRET: str = ""
    
    # Embedding Service
    EMBEDDING_PROVIDER: EmbeddingProvider = EmbeddingProvider.AZURE_OPENAI
    
    # Azure OpenAI
    AZURE_OPENAI_ENDPOINT: Optional[str] = None
    AZURE_OPENAI_KEY: Optional[str] = None
    AZURE_OPENAI_DEPLOYMENT: str = "text-embedding-3-small"
    OPENAI_API_VERSION: str = "2023-05-15"
    
    # OpenAI
    OPENAI_API_KEY: Optional[str] = None
    
    # Local
    LOCAL_MODEL_NAME: str = "all-MiniLM-L6-v2"
    
    # MCP Server
    MCP_TRANSPORT: TransportType = TransportType.STDIO
    MCP_PORT: int = 8080
    
    # Application
    LOG_LEVEL: str = "INFO"
    DATA_DIR: Path = Path("data")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def get_data_dir(self) -> Path:
        """Ensure data directory exists and return it."""
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        return self.DATA_DIR

    def get_zvec_dir(self) -> Path:
        """Return path for zvec collections."""
        zvec_path = self.get_data_dir() / "zvec"
        zvec_path.mkdir(exist_ok=True)
        return zvec_path

    def get_config_dir(self) -> Path:
        """Return path for config files."""
        config_path = self.get_data_dir() / "config"
        config_path.mkdir(exist_ok=True)
        return config_path

settings = Settings()
