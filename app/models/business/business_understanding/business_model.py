from sqlalchemy import Column, String, Text, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import Base, generate_uuid
from datetime import datetime, UTC
import enum

class ValidationStatus(enum.Enum):
    """Estados posibles de una validación de negocio"""
    PENDING = "pending"
    COMPLETED = "completed"
    ERROR = "error"

class BusinessValidation(Base):
    """
    Modelo para registrar las validaciones de ideas de negocio.
    Mantiene un historial de las validaciones realizadas y su estado.
    """
    __tablename__ = "business_validations"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    business_id = Column(String, ForeignKey("business_ideas.id"))
    status = Column(Enum(ValidationStatus), default=ValidationStatus.PENDING)
    error_message = Column(Text, nullable=True)
    
    # URLs de los archivos en MinIO
    data_url = Column(String, nullable=True)