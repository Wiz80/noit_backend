from pydantic import BaseModel
from datetime import datetime
from typing import Dict, Any, Optional

class BusinessIdeaBase(BaseModel):
    title: str
    description: Optional[str] = None  # Qué hace la empresa y cuál es su propósito
    value_proposal: Optional[str] = None  # Cuál es su propuesta de valor
    products_services: Optional[str] = None  # Qué productos/servicios ofrece y a quiénes
    ideal_customer: Optional[str] = None  # Cuál es el cliente ideal
    problem_solved: Optional[str] = None  # Qué problema resuelve
    differentiators: Optional[str] = None  # Qué los hace diferentes frente a la competencia
    challenges_opportunities: Optional[str] = None  # Qué desafíos u oportunidades clave enfrentan hoy

class BusinessIdeaCreate(BaseModel):
    title: str
    description: str

class BusinessIdeaUpdate(BusinessIdeaBase):
    pass

class BusinessIdeaInDBBase(BusinessIdeaBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime | None

    class Config:
        from_attributes = True