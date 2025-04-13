from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.models.base import Base, generate_uuid
from datetime import datetime
import uuid

class BusinessIdea(Base):
    __tablename__ = "business_ideas"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String, nullable=False)
    
    # Fields aligned with ETAPA 1: ENTENDIMIENTO DEL NEGOCIO
    description = Column(Text, nullable=True)  # Qué hace la empresa/cuál es el propósito
    value_proposal = Column(Text, nullable=True)  # Cuál es su propuesta de valor
    products_services = Column(Text, nullable=True)  # Qué productos/servicios ofrece y a quiénes
    ideal_customer = Column(Text, nullable=True)  # Cuál es el cliente ideal
    problem_solved = Column(Text, nullable=True)  # Qué problema resuelve
    differentiators = Column(Text, nullable=True)  # Qué los hace diferentes frente a la competencia
    challenges_opportunities = Column(Text, nullable=True)  # Qué desafíos u oportunidades clave enfrentan hoy
    
    # Relationships
    progress = relationship("BusinessProgress", back_populates="business", uselist=False, cascade="all, delete-orphan")
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)