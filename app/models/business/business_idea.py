from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.models.base import Base, generate_uuid
from app.models.business.business_progress import BusinessProgress
from datetime import datetime
import uuid

class BusinessIdea(Base):
    __tablename__ = "business_ideas"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    website_url = Column(String, nullable=True)
    
    # Relationships
    progress = relationship("BusinessProgress", back_populates="business", uselist=False, cascade="all, delete-orphan")
    business_model = relationship("BusinessModel", back_populates="business_idea", uselist=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)