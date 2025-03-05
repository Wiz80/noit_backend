# app/models/business_understanding.py
from sqlalchemy import Column, String, Text, ForeignKey, DateTime, Enum, JSON
from sqlalchemy.sql import func
from app.models.base import Base, generate_uuid
from sqlalchemy.orm import relationship
from enum import Enum as PyEnum

class StatusEnum(str, PyEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

class MarketStateOfArt(Base):
    __tablename__ = "business_understanding"
    
    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    business_idea_id = Column(String, ForeignKey("business_ideas.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Paths en MinIO
    market_research_path = Column(String, nullable=True)
    state_of_art_path = Column(String, nullable=True)
    
    # Status del proceso
    market_research_status = Column(String, default=StatusEnum.PENDING)
    state_of_art_status = Column(String, default=StatusEnum.PENDING)
    
    language = Column(String, default="en")
    error_message = Column(Text, nullable=True)