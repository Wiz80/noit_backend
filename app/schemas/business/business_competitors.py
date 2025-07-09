from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from app.services.business.competitive_analysis.business_competitors_extraction import CompetitorInfo

class WebsiteSocialMediaScrapingRequest(BaseModel):
    update_db: bool = True
    competitor_ids: Optional[List[str]] = None

# Schema for website social media scraping response
class WebsiteSocialMediaScrapingResponse(BaseModel):
    task_id: str
    status: str
    results: Optional[dict]

# Schema for website correction request
class WebsiteCorrectionRequest(BaseModel):
    competitor_ids: Optional[List[str]] = Field(None, description="Optional: specific competitor IDs to correct. If empty/null, ALL competitors for the business will be processed (default behavior)")
    force_update: bool = Field(False, description="Whether to force update already correct URLs")

# Schema for corrected website data
class CorrectedWebsite(BaseModel):
    competitor_id: str
    competitor_name: str
    original_website: Optional[str]
    corrected_website: Optional[str]
    was_corrected: bool
    confidence_score: Optional[float] = None

# Schema for website correction response
class WebsiteCorrectionResponse(BaseModel):
    business_id: str
    total_competitors: int
    corrected_count: int
    skipped_count: int
    corrected_websites: List[CorrectedWebsite]
    success: bool
    message: Optional[str] = None

# Schema for Instagram URL correction request
class InstagramCorrectionRequest(BaseModel):
    competitor_ids: Optional[List[str]] = Field(None, description="Optional: specific competitor IDs to correct. If empty/null, ALL competitors for the business will be processed (default behavior)")
    force_update: bool = Field(False, description="Whether to force update already existing Instagram URLs")

# Schema for corrected Instagram URL data
class CorrectedInstagramUrl(BaseModel):
    competitor_id: str
    competitor_name: str
    competitor_website: Optional[str]
    original_instagram_url: Optional[str]
    corrected_instagram_url: Optional[str]
    was_corrected: bool
    confidence_score: Optional[float] = None
    reasoning: Optional[str] = None

# Schema for Instagram URL correction response
class InstagramCorrectionResponse(BaseModel):
    business_id: str
    total_competitors: int
    corrected_count: int
    skipped_count: int
    corrected_instagram_urls: List[CorrectedInstagramUrl]
    success: bool
    message: Optional[str] = None

class CompetitorAnalysisRequest(BaseModel):
    """Request model for competitor analysis"""
    search_prompt: str = Field(..., description="The search prompt to use for researching competitors")
    language: str = Field("en", description="Language for the analysis")
    validator_provider: str = Field("openai", description="Provider for validation (openai, anthropic, etc.)")
    validator_model: str = Field("gpt-4", description="Model to use for validation")
    research_model: str = Field("claude-3-haiku", description="Model to use for research")
    base_url: str = Field(..., description="Base URL for callback endpoints")

class CompetitorAnalysisResponse(BaseModel):
    """Response model for competitor analysis"""
    competitors: List[CompetitorInfo]
    analysis_questions: List[str]
    business_model_summary: dict

class CompetitorInfo(BaseModel):
    """Information about a competitor"""
    name: str
    website: Optional[str] = None
    description: str
    strengths: List[str]
    weaknesses: List[str]
    market_share: Optional[float] = None
    target_audience: Optional[str] = None
    pricing_strategy: Optional[str] = None
    unique_selling_proposition: Optional[str] = None

class Competitor(BaseModel):
    """Schema for the Competitor SQLAlchemy model, used for API responses."""
    id: str
    business_idea_id: str
    competitor_name: str
    key_feature: Optional[str] = None
    website: Optional[str] = None
    instagram_url: Optional[str] = None
    facebook_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    x_url: Optional[str] = None
    youtube_url: Optional[str] = None
    tiktok_url: Optional[str] = None
    similarity_score: Optional[float] = None

    class Config:
        from_attributes = True

class GetCompetitorsResponse(BaseModel):
    business_id: str
    competitors: List[Competitor]

class CompetitorAnalysisCallback(BaseModel):
    """Callback data from n8n when research is complete"""
    request_id: str = Field(..., description="ID of the original research request")
    status: str = Field(..., description="Status of the research (completed, error)")
    competitors: Optional[List[Dict[str, Any]] | str] = Field(None, description="List of competitors found or text results")
    error_message: Optional[str] = Field(None, description="Error message if status is error")
    timestamp: Optional[str] = Field(None, description="Timestamp of when the research was completed")
    # Making these optional to be more flexible with n8n callbacks
    search_prompt: Optional[str] = Field(None, description="Original search prompt used for research")
    business_id: Optional[str] = Field(None, description="Business ID associated with this research")
    base_url: Optional[str] = Field(None, description="Base URL for callbacks")