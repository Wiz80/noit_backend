from typing import Generator
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import ValidationError
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.user import User
from app.core import security
from app.api.v1.endpoints.crud.crud_user import CRUDUser
from app.services.storage.minio_service import MinioService
from app.services.cache.redis_service import RedisChatService
import logging

crud_user = CRUDUser(User)

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login"
)

def get_db() -> Generator:
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()

async def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> User:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        token_data = payload.get("sub")
        if token_data is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Could not validate credentials",
            )
    except (JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    
    user = crud_user.get(db, id=token_data)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

def get_current_active_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    return current_user

# Create a singleton instance of MinioService
_minio_service_instance = None

def get_minio_client() -> MinioService:
    """
    Returns a MinioService instance for handling object storage operations.
    Uses a singleton pattern to avoid multiple initializations.
    The client connection is only established when the actual MinIO operations are performed.
    """
    global _minio_service_instance
    if _minio_service_instance is None:
        # Just create the service object without connecting to MinIO
        # The actual connection will be established on first use
        _minio_service_instance = MinioService(bucket_name=settings.MINIO_BUCKET_NAME)
        logging.info("MinioService instance created (lazy loading - not connected yet)")
    return _minio_service_instance

# Create a singleton instance of RedisChatService
_redis_service_instance = None

def get_redis_service() -> RedisChatService:
    """
    Returns a RedisChatService instance for handling chat sessions in Redis.
    Uses a singleton pattern to avoid multiple initializations.
    """
    global _redis_service_instance
    if _redis_service_instance is None:
        # Conectar al servidor Redis definido en docker-compose.yml
        try:
            _redis_service_instance = RedisChatService(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD,
                default_ttl=86400  # 24 horas de caducidad por defecto
            )
            # Probar conexión
            _redis_service_instance.redis.ping()
            logging.info(f"Conectado exitosamente a Redis en {settings.REDIS_HOST}:{settings.REDIS_PORT}")
        except Exception as e:
            logging.error(f"Error al conectar con Redis: {str(e)}")
            # Fallback local para desarrollo
            _redis_service_instance = RedisChatService(
                host="localhost", 
                port=6379,
                password=None,
                default_ttl=86400
            )
            logging.info("Usando conexión local a Redis como fallback")
    
    return _redis_service_instance