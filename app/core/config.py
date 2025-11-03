"""
Application configuration settings
"""
from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    """Application settings"""

    PROJECT_NAME: str = "RPG Document Understanding API"
    VERSION: str = "1.0.0"
    DATABASE_URL: str = "sqlite+aiosqlite:///./rpg_challenge.db"
    BUCKET_DIR: Path = Path("./bucket")
    MAX_FILE_SIZE: int = 10 * 1024 * 1024
    ALLOWED_EXTENSIONS: set = {".pdf", ".png", ".jpg", ".jpeg"}

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"

settings = Settings()
settings.BUCKET_DIR.mkdir(parents=True, exist_ok=True)

