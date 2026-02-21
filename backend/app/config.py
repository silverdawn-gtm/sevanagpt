from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://myscheme:myscheme_dev@localhost:5432/myscheme"
    DATABASE_URL_SYNC: str = "postgresql://myscheme:myscheme_dev@localhost:5432/myscheme"

    MISTRAL_API_KEY: str = ""
    MISTRAL_CHAT_MODEL: str = "mistral-small-latest"
    MISTRAL_EMBED_MODEL: str = "mistral-embed"

    # Groq (free alternative for chat — get key at console.groq.com)
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.1-70b-versatile"

    BHASHINI_USER_ID: str = ""
    BHASHINI_API_KEY: str = ""
    BHASHINI_PIPELINE_URL: str = "https://dhruva-api.bhashini.gov.in/services/inference"

    KAGGLE_USERNAME: str = ""
    KAGGLE_KEY: str = ""
    DATAGOV_API_KEY: str = ""

    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    EMBEDDING_DIM: int = 1024

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
