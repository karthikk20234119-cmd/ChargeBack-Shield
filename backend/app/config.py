import os
from typing import List, Optional, Union
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Chargeback Shield"
    APP_ENV: str = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # API & Docs Settings
    API_PREFIX: str = "/api"
    ENABLE_DOCS: bool = True
    ENABLE_OPENAPI: bool = True
    FRONTEND_URL: str = "http://localhost:3000"
    CORS_ALLOWED_ORIGINS: Union[List[str], str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Security & Timeout Safeguards
    REQUEST_TIMEOUT: int = 30
    MAX_REQUEST_SIZE: int = 10485760  # 10 MB limit for total request payload

    # Secrets (Loaded strictly from environment; no hardcoded defaults)
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "qwen/qwen3.8-27b"
    
    DATABASE_URL: str = "sqlite+aiosqlite:///./chargeback_shield.db"
    ENVIRONMENT: str = "development"
    
    # Upload & Processing Directories
    UPLOAD_DIR: str = "./storage/evidence"
    PROCESSED_DIR: str = "./storage/processed"
    
    # File Size Ceilings
    MAX_PDF_SIZE_BYTES: int = 2097152    # 2 MB limit for PDFs
    MAX_IMAGE_SIZE_BYTES: int = 4194304  # 4 MB limit for Images
    
    # PDF & Image Processing Safeguards
    POPPLER_PATH: Optional[str] = None
    DEFAULT_RASTER_DPI: int = 200
    MAX_PDF_PAGES: int = 10
    MAX_IMAGE_PIXELS: int = 25_000_000   # 25 Megapixels (Decompression Bomb protection)

    # Razorpay API Client Settings
    RAZORPAY_API_BASE_URL: str = "https://api.razorpay.com"
    RAZORPAY_CONNECT_TIMEOUT: float = 5.0
    RAZORPAY_READ_TIMEOUT: float = 15.0
    RAZORPAY_MAX_RETRIES: int = 3

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production" or self.ENVIRONMENT.lower() == "production"

    def is_debug(self) -> bool:
        if self.is_production():
            return False
        return self.DEBUG

    def get_cors_origins(self) -> List[str]:
        if isinstance(self.CORS_ALLOWED_ORIGINS, str):
            return [o.strip() for o in self.CORS_ALLOWED_ORIGINS.split(",") if o.strip()]
        return list(self.CORS_ALLOWED_ORIGINS)

settings = Settings()

