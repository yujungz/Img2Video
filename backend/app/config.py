from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Img2Video API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8102

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@postgres:5432/img2video"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # MinIO / Object Storage
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "img2video"
    MINIO_SECURE: bool = False
    MINIO_PUBLIC_ENDPOINT: str = "localhost:9000"  # For browser access

    # JWT
    SECRET_KEY: str = "your-super-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # AI API Configuration
    ANTHROPIC_BASE_URL: str = ""
    ANTHROPIC_AUTH_TOKEN: str = ""
    ANTHROPIC_MODEL_NAME: str = ""  # Model name for image generation
    ANTHROPIC_PATH_URL: str = ""    # API path for image generation
    ANTHROPIC_DEBUG: bool = False   # Enable debug logging for AI API
    ANTHROPIC_TIMEOUT: int = 300    # Timeout for AI API calls in seconds
    ANTHROPIC_IMG_PREPROMPT: str = ""  # Pre-prompt for image generation

    # Video API Configuration (Kling API)
    ANTHROPIC_BASE_URL_VIDEO: str = ""
    ANTHROPIC_AUTH_TOKEN_VIDEO: str = ""
    ANTHROPIC_MODEL_NAME_VIDEO: str = "kling-v2-6"
    ANTHROPIC_PATH_URL_VIDEO: str = "/kling/v1/videos/image2video"
    ANTHROPIC_TIMEOUT_VIDEO: int = 600  # Timeout for video generation (10 minutes)

    # Public URL for video source images (Kling API requires public image URL)
    PUBLIC_BASE_URL: str = "http://localhost:8103"

    # AI Models (fallback defaults)
    TEXT_MODEL: str = "claude-sonnet-4-6"
    IMAGE_MODEL: str = "gpt-image-1"
    VIDEO_MODEL: str = "sora-2"

    # File Upload
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS: set = {"jpg", "jpeg", "png"}

    # Task Queue
    CELERY_BROKER_URL: str = "redis://redis:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/2"

    # Email Configuration (SMTP)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 465
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    SMTP_USE_TLS: bool = True

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
