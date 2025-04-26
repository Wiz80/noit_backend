import uuid
import enum
from sqlalchemy import Column, String, Text, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base
from datetime import datetime, UTC

class CompetitorResearchStatus(str, enum.Enum):
    """Status of a competitor research process"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"

class CompetitorResearch(Base):
    """Model for tracking competitor research requests"""
    __tablename__ = "competitor_research"
    
    id = Column(String, primary_key=True, index=True)
    business_id = Column(String, ForeignKey("business_ideas.id"), nullable=False)
    status = Column(Enum(CompetitorResearchStatus), default=CompetitorResearchStatus.PENDING)
    language = Column(String, nullable=False)
    model = Column(String, nullable=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now(UTC))
    updated_at = Column(DateTime, default=datetime.now(UTC), onupdate=datetime.now(UTC))
    completed_at = Column(DateTime, nullable=True)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.id:
            self.id = str(uuid.uuid4()) 