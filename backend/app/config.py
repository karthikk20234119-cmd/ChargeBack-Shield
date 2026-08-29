import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Chargeback Shield"
    RAZORPAY_KEY_ID: str = "rzp_test_samplekeyid123"

    RAZORPAY_KEY_SECRET: str = "samplesecretkey123456"
    RAZORPAY_WEBHOOK_SECRET: str = "samplewebhooksecret123"
    
    OPENAI_API_KEY: str = "sk-proj-sampleopenaikey123"
    
    DATABASE_URL: str = "sqlite+aiosqlite:///./chargeback_shield.db"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    
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

settings = Settings()
