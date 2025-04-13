from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer, Enum
from sqlalchemy.orm import relationship
from enum import Enum as PyEnum
from app.models.base import Base
from datetime import datetime
import uuid

class StepStatus(str, PyEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

class BusinessProgress(Base):
    """
    Modelo para rastrear el progreso de un negocio a través de los diferentes pasos del sistema.
    Este modelo permitirá determinar qué funcionalidades están disponibles para el usuario
    y hacia dónde dirigir las conversaciones.
    """
    __tablename__ = "business_progress"
    
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    business_id = Column(String, ForeignKey("business_ideas.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Relationship with BusinessIdea
    business = relationship("BusinessIdea", back_populates="progress")
    
    # Pasos del sistema
    brief_status = Column(String, default=StepStatus.NOT_STARTED)
    business_canvas_status = Column(String, default=StepStatus.NOT_STARTED)
    competitive_analysis_status = Column(String, default=StepStatus.NOT_STARTED)
    
    # Identificadores de sesiones/recursos
    brief_session_id = Column(String, nullable=True)
    business_canvas_id = Column(String, nullable=True)
    competitive_analysis_id = Column(String, nullable=True)
    
    # Fechas de completado
    brief_completed_at = Column(DateTime, nullable=True)
    business_canvas_completed_at = Column(DateTime, nullable=True)
    competitive_analysis_completed_at = Column(DateTime, nullable=True)
    
    # Metadatos
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def get_next_step(self):
        """
        Determina el siguiente paso que el usuario debería completar
        basado en el estado actual de su progreso.
        """
        if self.brief_status != StepStatus.COMPLETED:
            return "brief"
        elif self.business_canvas_status != StepStatus.COMPLETED:
            return "business_canvas"
        elif self.competitive_analysis_status != StepStatus.COMPLETED:
            return "competitive_analysis"
        else:
            return "all_completed"
    
    def get_completed_steps(self):
        """
        Devuelve una lista de los pasos que ya han sido completados.
        """
        completed = []
        if self.brief_status == StepStatus.COMPLETED:
            completed.append("brief")
        if self.business_canvas_status == StepStatus.COMPLETED:
            completed.append("business_canvas")
        if self.competitive_analysis_status == StepStatus.COMPLETED:
            completed.append("competitive_analysis")
        return completed 