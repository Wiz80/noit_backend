from sqlalchemy import Column, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import Base, generate_uuid

class BusinessCanvas(Base):
    __tablename__ = "business_canvas"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    business_idea_id = Column(String, ForeignKey("business_ideas.id"))

    file_name = Column(String, nullable=False)  # Minio File name
    file_path = Column(String, nullable=False)  # Full path
    mime_type = Column(String, nullable=False)  # MIME type
    bucket_name = Column(String, nullable=False)