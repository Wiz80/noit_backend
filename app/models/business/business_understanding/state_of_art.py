# app/models/business_understanding.py
from sqlalchemy import Column, String, Text, ForeignKey, DateTime, Enum, JSON
from sqlalchemy.sql import func
from app.models.base import Base, generate_uuid
from sqlalchemy.orm import relationship
from enum import Enum as PyEnum
import json

class StatusEnum(str, PyEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

class ResearchTypeEnum(str, PyEnum):
    MARKET_RESEARCH = "market_research"
    STATE_OF_ART = "state_of_art"

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
    
    # Relationship with research tasks
    research_tasks = relationship("ResearchTask", back_populates="business_understanding")

class ResearchTask(Base):
    __tablename__ = "research_tasks"
    
    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    business_understanding_id = Column(String, ForeignKey("business_understanding.id"))
    business_idea_id = Column(String, nullable=False)
    request_id = Column(String, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Task info
    research_type = Column(String, nullable=False)  # "market_research" or "state_of_art"
    depth = Column(String, default="normal")
    chunk_index = Column(String, nullable=False)  # Which chunk of questions (e.g. "1/3")
    questions = Column(Text, nullable=False)  # JSON string of questions in this chunk
    
    # Status
    status = Column(String, default=StatusEnum.PENDING)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    answer = Column(Text, nullable=True)  # JSON string of answers when complete
    error_message = Column(Text, nullable=True)
    
    # Relationship
    business_understanding = relationship("MarketStateOfArt", back_populates="research_tasks")
    
    def add_questions(self, questions_list):
        """Store questions as JSON string"""
        self.questions = json.dumps(questions_list)
        
    def get_questions(self):
        """Get questions as Python list"""
        return json.loads(self.questions) if self.questions else []
        
    def add_answer(self, answer_data):
        """Store answer as JSON string"""
        self.answer = json.dumps(answer_data)
        self.status = StatusEnum.COMPLETED
        self.completed_at = func.now()
        
    def get_answer(self):
        """Get answer as Python object"""
        return json.loads(self.answer) if self.answer else None