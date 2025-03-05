from pydantic import BaseModel
from typing import List
from app.services.business.competitive_analysis.business_competitors_extraction import CompetitorInfo

class CompetitorAnalysisRequest(BaseModel):
    """Request model for competitor analysis"""
    search_prompt: str
    language: str = "es"
    validator_provider: str = "deepseek"
    validator_model: str = "deepseek-reasoner"

class CompetitorAnalysisResponse(BaseModel):
    """Response model for competitor analysis"""
    competitors: List[CompetitorInfo]
    analysis_questions: List[str]
    business_model_summary: dict