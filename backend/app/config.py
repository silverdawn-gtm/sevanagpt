from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://myscheme:myscheme_dev@localhost:5433/myscheme"
    DATABASE_URL_SYNC: str = "postgresql://myscheme:myscheme_dev@localhost:5433/myscheme"

    MISTRAL_API_KEY: str = ""
    MISTRAL_CHAT_MODEL: str = "mistral-small-latest"
    MISTRAL_EMBED_MODEL: str = "mistral-embed"

    # Groq (free alternative for chat — get key at console.groq.com)
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.1-70b-versatile"

    KAGGLE_USERNAME: str = ""
    KAGGLE_KEY: str = ""
    DATAGOV_API_KEY: str = ""

    # IndicTrans2 microservice
    INDICTRANS_URL: str = ""  # e.g. "http://indictrans:7860" — empty = disabled
    INDICTRANS_TIMEOUT: float = 10.0
    INDICTRANS_BATCH_TIMEOUT: float = 60.0
    INDICTRANS_ENABLED: bool = True

    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    EMBEDDING_DIM: int = 1024

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
