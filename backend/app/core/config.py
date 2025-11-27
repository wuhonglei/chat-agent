"""Application configuration"""

from pydantic import Field, field_validator, ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""

    # Application
    APP_NAME: str = "AI Assistant"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000

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
    CONFLUENCE_PERSONAL_TOKEN: str = ""

    # Web Search
    TAVILY_API_KEY: str = ""

    # Storage
    UPLOAD_DIR: str = "./data/documents"
    AVATAR_DIR: str = "./data/avatars"

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
    JWT_ALGORITHM: str = "RS256"
    JWT_PRIVATE_KEY_PATH: str = "./private_keys/v1_private_key.pem"
    JWT_PUBLIC_KEY_PATH: str = "./private_keys/v1_public_key.pem"

    # Cloudbase
    CLOUDBASE_ENV_ID: str = Field(...,
                                  description="The environment ID of the Cloudbase")

    # 腾讯云存储服务
    STORAGE_SECRET_ID: str = Field(...,
                                   description="The secret ID of the storage")
    STORAGE_SECRET_KEY: str = Field(...,
                                    description="The secret key of the storage")
    STORAGE_REGION: str = Field('ap-guangzhou',
                                description="The region of the storage")
    STORAGE_BUCKET: str = Field("ai-chat-1258352625",
                                description="The bucket of the storage")

    # PostgreSQL
    PG_HOST: str = "localhost"
    PG_PORT: int = 5432
    PG_DB: str = "ai_assistant_db"
    PG_USER_NAME: str = Field(...,
                              description="The username of the PostgreSQL database")
    PG_PASSWORD: str = Field(...,
                             description="The password of the PostgreSQL database")

    # MCP Config
    CONTEXT7_API_KEY: str = ""

    model_config = ConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=True,
        env_ignore_empty=True,
        extra='ignore'
    )


settings = Settings()
