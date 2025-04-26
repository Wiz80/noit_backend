from sqlalchemy import Column, String, Text, ForeignKey, Float
from sqlalchemy.orm import relationship
from app.models.base import Base, generate_uuid

class Competitor(Base):
    __tablename__ = "competitors"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    business_idea_id = Column(String, ForeignKey("business_ideas.id"))
    
    # Basic info
    competitor_name = Column(String, nullable=False)
    key_feature = Column(Text)
    website = Column(String)
    
    # Social media links
    instagram_url = Column(String)
    facebook_url = Column(String)
    linkedin_url = Column(String)
    x_url = Column(String)  # Twitter/X
    youtube_url = Column(String)
    tiktok_url = Column(String)

    similarity_score = Column(Float)