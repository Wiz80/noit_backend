from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl
import os
from dotenv import load_dotenv
from typing import Optional, List

load_dotenv()

class Settings(BaseSettings):
    PROJECT_NAME: str = "Business AI API"
    API_V1_STR: str = "/api/v1"
    
    # Google
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID")
    
    # JWT
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    SUPERUSER_SECRET_KEY: str = os.getenv("SUPERUSER_SECRET_KEY")
    ALGORITHM: str = os.getenv("ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    
    # Database
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB")
    
    # MinIO
    MINIO_ROOT_USER: str = os.getenv("MINIO_ROOT_USER")
    MINIO_ROOT_PASSWORD: str = os.getenv("MINIO_ROOT_PASSWORD")
    MINIO_ENDPOINT: str = os.getenv("MINIO_ENDPOINT")
    MINIO_REGION: str = os.getenv("MINIO_REGION")
    MINIO_BUCKET_NAME: str = os.getenv("MINIO_BUCKET_NAME", "noit-businesses")
    
    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD")
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    
    # Kestra
    KESTRA_URL: str = os.getenv("KESTRA_URL", "http://kestra:8080")
    KESTRA_COMPETITOR_ANALYSIS_KEY: str = os.getenv("KESTRA_COMPETITOR_ANALYSIS_KEY", "ojdfqfuqfjmcaecf")
    KESTRA_SOCIAL_MEDIA_SCRAPER_KEY: str = os.getenv("KESTRA_SOCIAL_MEDIA_SCRAPER_KEY", "KIWsfd9QHF412@")
    KESTRA_INSTAGRAM_ANALYSIS_KEY: str = os.getenv("KESTRA_INSTAGRAM_ANALYSIS_KEY", "ajhef013adjaXJSNAScd")

    SQLALCHEMY_DATABASE_URI: str | None = None
    
    SERVER_NAME: str = "localhost"
    SERVER_HOST: AnyHttpUrl = "http://localhost:8000"
    
    @property
    def get_database_url(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

settings = Settings()