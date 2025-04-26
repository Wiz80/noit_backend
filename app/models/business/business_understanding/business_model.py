from sqlalchemy import Column, String, Text, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import Base, generate_uuid
from datetime import datetime
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

class BusinessModel(Base):
    """
    Modelo para almacenar los datos estructurados del modelo de negocio.
    Contiene los componentes clave del análisis de modelo de negocio.
    """
    __tablename__ = "business_models"
    
    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    business_id = Column(String, ForeignKey("business_ideas.id"), index=True)
    
    # Campos clave del modelo de negocio
    problem_definition = Column(Text, nullable=True)
    industry = Column(Text, nullable=True)
    customer_persona = Column(Text, nullable=True)
    value_proposition = Column(Text, nullable=True)
    competitive_advantage = Column(Text, nullable=True)
    products_services = Column(Text, nullable=True)
    challenges_opportunities = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relación con la idea de negocio
    business_idea = relationship("BusinessIdea", back_populates="business_model")