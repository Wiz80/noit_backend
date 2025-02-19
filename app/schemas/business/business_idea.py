from pydantic import BaseModel
from datetime import datetime

class BusinessIdeaBase(BaseModel):
    title: str
    description: str
    mission: str
    vision: str

class BusinessIdeaCreate(BusinessIdeaBase):
    pass

class BusinessIdeaUpdate(BusinessIdeaBase):
    pass

class BusinessIdeaInDBBase(BusinessIdeaBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime | None

    class Config:
        from_attributes = True