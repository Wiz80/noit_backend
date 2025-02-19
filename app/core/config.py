from pydantic_settings import BaseSettings
import os
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    PROJECT_NAME: str = "Business AI API"
    API_V1_STR: str = "/api/v1"
    
    # JWT
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    ALGORITHM: str = os.getenv("ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
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

    SQLALCHEMY_DATABASE_URI: str | None = None
    
    @property
    def get_database_url(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

settings = Settings()