"""Application configuration"""

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""

    # Application
    APP_NAME: str = "AI Doc Q&A System"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # CORS
    CORS_ORIGINS: list[str] | str = [
        "http://localhost:3000", "http://localhost:5173"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if v is None or v == "":
            return ["http://localhost:3000", "http://localhost:5173"]
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    # LLM Model API
    LLM_API_KEY: str
    LLM_API_BASE: str = "https://api.deepseek.com/v1"
    LLM_MODEL: str = "deepseek-chat"
    LLM_THINK_MODEL: str = "deepseek-reasoner"

    # Embedding Model API
    EMBEDDING_API_KEY: str
    EMBEDDING_API_BASE: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    EMBEDDING_MODEL: str = "text-embedding-v4"

    # Re-rank API Configuration
    RE_RANK_API_KEY: str
    RE_RANK_API_BASE: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    RE_RANK_MODEL: str

    # Chroma
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8000
    CHROMA_PERSIST_DIRECTORY: str = "./data/vectordb"
    CHROMA_COLLECTION_NAME: str = "documents"

    # Document Processing
    MAX_FILE_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: list[str] | str = ["pdf", "docx", "txt", "md"]
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200

    @field_validator("ALLOWED_EXTENSIONS", mode="before")
    @classmethod
    def parse_allowed_extensions(cls, v):
        if v is None or v == "":
            return ["pdf", "docx", "txt", "md"]
        if isinstance(v, str):
            return [ext.strip() for ext in v.split(",")]
        return v

    # External Integrations
    CONFLUENCE_URL: str = ""
    CONFLUENCE_USERNAME: str = ""
    CONFLUENCE_API_TOKEN: str = ""

    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/google/callback"

    # Web Search
    TAVILY_API_KEY: str = ""

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""
    CACHE_TTL: int = 3600

    # Storage
    UPLOAD_DIR: str = "./data/documents"
    TEMP_DIR: str = "./data/temp"

    # Search
    SEARCH_TOP_K: int = 10
    USE_RERANK: bool = True
    RERANK_TOP_K: int = 3
    MIN_RELEVANCE_SCORE: float = 0.3

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "./logs/app.log"
    LOG_ROTATION: str = "10 MB"
    LOG_RETENTION: str = "30 days"

    # Security
    SECRET_KEY: str = "your-secret-key-here"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    class Config:
        env_file = ".env"
        case_sensitive = True
        env_ignore_empty = True


settings = Settings()
