from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.sql import func
from app.models.base import Base, generate_uuid
from sqlalchemy.orm import relationship

class BusinessIdea(Base):
    __tablename__ = "business_ideas"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"))
    title = Column(String)
    description = Column(Text)
    mission = Column(Text)
    vision = Column(Text)
    
    user = relationship("User")