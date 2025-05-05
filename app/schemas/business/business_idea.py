from pydantic import BaseModel
from datetime import datetime
from typing import Dict, Any, Optional

class BusinessIdeaBase(BaseModel):
    title: str
    description: Optional[str] = None
    website_url: Optional[str] = None

class BusinessIdeaCreate(BaseModel):
    title: str
    description: str
    website_url: Optional[str] = None

class BusinessIdeaUpdate(BusinessIdeaBase):
    pass

class BusinessIdeaInDBBase(BusinessIdeaBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime | None

    class Config:
        from_attributes = True