from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any, Union

class LinkedInScrapeSettings(BaseModel):
    """Settings for LinkedIn scraping operations"""
    use_proxy: bool = Field(True, description="Whether to use proxy for scraping")
    proxy_country: str = Field("US", description="Country code for proxy")
    min_delay: int = Field(2, description="Minimum delay between requests in seconds")
    max_delay: int = Field(8, description="Maximum delay between requests in seconds")
    deep_scrape: bool = Field(True, description="Whether to perform deep scraping")
    timeout_secs: int = Field(600, description="Timeout in seconds for Apify actor calls")

class LinkedInCompanyScrapeSettings(LinkedInScrapeSettings):
    """Settings specific to company scraping"""
    location: Optional[str] = Field(None, description="Optional location to filter results")

class LinkedInPostScrapeSettings(LinkedInScrapeSettings):
    """Settings specific to post scraping"""
    cookies: Optional[List[Dict[str, Any]]] = Field(None, description="Optional LinkedIn cookies for authentication")

class LinkedInAdsScrapeSettings(LinkedInScrapeSettings):
    """Settings specific to ads scraping"""
    word_search: Optional[str] = Field(None, description="Keyword to search for in ads")
    date_option: str = Field("last-30-days", description="Date option for ads (last-24-hours, last-7-days, last-30-days, etc.)")
    date_start: Optional[str] = Field(None, description="Start date for custom range (YYYY-MM-DD)")
    date_end: Optional[str] = Field(None, description="End date for custom range (YYYY-MM-DD)")
    country: str = Field("ALL", description="Country code to filter ads by")
    limit: int = Field(50, description="Maximum number of ads to scrape")
    
    @field_validator('date_option')
    @classmethod
    def validate_date_option(cls, v):
        valid_options = ["last-24-hours", "last-7-days", "last-30-days", "last-90-days", 
                          "current-month", "last-month", "custom"]
        if v not in valid_options:
            raise ValueError(f"Date option must be one of {valid_options}")
        return v

class CompetitorScrapingRequest(BaseModel):
    """Request model for scraping competitor LinkedIn data"""
    business_id: Optional[str] = Field(None, description="Business ID")
    competitor_id: Optional[str] = Field(None, description="Competitor ID") 
    linkedin_url: Optional[str] = Field(None, description="LinkedIn URL of the competitor")
    scrape_company: bool = Field(True, description="Whether to scrape company data")
    scrape_posts: bool = Field(True, description="Whether to scrape posts")
    scrape_ads: bool = Field(True, description="Whether to scrape ads")
    company_settings: Optional[LinkedInCompanyScrapeSettings] = Field(None, description="Settings for company scraping")
    post_settings: Optional[LinkedInPostScrapeSettings] = Field(None, description="Settings for post scraping")
    ads_settings: Optional[LinkedInAdsScrapeSettings] = Field(None, description="Settings for ads scraping")
    timeout_secs: Optional[int] = Field(6000, description="Timeout in seconds for Apify actor calls")
    
    @field_validator('linkedin_url')
    @classmethod
    def validate_linkedin_url(cls, v):
        if v and not v.startswith('https://www.linkedin.com/'):
            raise ValueError('LinkedIn URL must start with https://www.linkedin.com/')
        return v

class BusinessCompetitorsScrapingRequest(BaseModel):
    """Request model for scraping all competitors for a business"""
    business_id: Optional[str] = Field(None, description="Business ID")
    scrape_company: bool = Field(True, description="Whether to scrape company data")
    scrape_posts: bool = Field(True, description="Whether to scrape posts")
    scrape_ads: bool = Field(True, description="Whether to scrape ads")
    combine_data: bool = Field(True, description="Whether to combine data from all competitors")
    company_settings: Optional[LinkedInCompanyScrapeSettings] = Field(None, description="Settings for company scraping")
    post_settings: Optional[LinkedInPostScrapeSettings] = Field(None, description="Settings for post scraping")
    ads_settings: Optional[LinkedInAdsScrapeSettings] = Field(None, description="Settings for ads scraping")
    timeout_secs: Optional[int] = Field(600, description="Timeout in seconds for Apify actor calls")

class LinkedInScrapingResponse(BaseModel):
    """Response model for LinkedIn scraping operations"""
    business_id: str
    competitor_id: Optional[str] = None
    linkedin_url: Optional[str] = None
    company: Dict[str, Any]
    posts: Dict[str, Any]
    ads: Dict[str, Any]

class BusinessCombinedDataResponse(BaseModel):
    """Response model for combined data operations"""
    business_id: str
    company: Dict[str, Any]
    posts: Dict[str, Any]
    ads: Dict[str, Any]

# New schemas for LinkedIn data analysis

class LinkedInAnalysisRequest(BaseModel):
    """Base request model for LinkedIn data analysis"""
    business_id: str = Field(..., description="The business ID")
    competitor_ids: Optional[List[str]] = Field(None, description="Optional list of competitor IDs to analyze. If not provided, all competitors will be analyzed.")
    force_refresh: bool = Field(False, description="Whether to force refresh the analysis even if it already exists")

class LinkedInAnalysisResponse(BaseModel):
    """Base response model for LinkedIn data analysis"""
    business_id: str
    analysis_id: str
    status: str
    results: Dict[str, Any]

class SentimentResult(BaseModel):
    """Results of sentiment analysis"""
    positive: float
    negative: float
    neutral: float
    compound: float = Field(..., description="Overall compound score (-1 to 1)")

class KeywordExtractionResult(BaseModel):
    """Results of keyword extraction"""
    keywords: List[Dict[str, Union[str, float]]]
    entities: Optional[List[Dict[str, Any]]] = None

class TopicModelingResult(BaseModel):
    """Results of topic modeling"""
    topics: List[Dict[str, Any]]
    dominant_topic: Dict[str, Any]

class EngagementStat(BaseModel):
    """Engagement statistics for posts"""
    total_likes: int
    total_comments: int
    total_shares: int
    avg_likes_per_post: float
    avg_comments_per_post: float
    avg_shares_per_post: float
    engagement_rate: float = Field(..., description="(Likes+Comments+Shares)/Followers")

class ContentDistribution(BaseModel):
    """Content type distribution"""
    text_posts: int
    image_posts: int
    video_posts: int
    total_posts: int
    text_percentage: float
    image_percentage: float
    video_percentage: float

class AdMetrics(BaseModel):
    """Ad metrics and distribution"""
    total_ads: int
    ad_types: Dict[str, int]
    cta_distribution: Dict[str, int]
    countries_distribution: Dict[str, float]
    target_languages: List[str]
    target_locations: List[str]

class CompetitorInsights(BaseModel):
    """Complete insights for a single competitor"""
    competitor_id: str
    competitor_name: str
    linkedin_url: str
    company_profile: Dict[str, Any]
    sentiment_analysis: Optional[SentimentResult] = None
    keyword_extraction: Optional[KeywordExtractionResult] = None
    topic_modeling: Optional[TopicModelingResult] = None
    engagement_stats: Optional[EngagementStat] = None
    content_distribution: Optional[ContentDistribution] = None
    ad_metrics: Optional[AdMetrics] = None
    recommendations: Optional[List[str]] = None

class CompetitorAnalysisRequest(LinkedInAnalysisRequest):
    """Request model for analyzing a specific competitor's LinkedIn data"""
    analysis_types: List[str] = Field(
        ["sentiment", "keywords", "topics", "engagement", "content", "ads"],
        description="Types of analysis to perform"
    )

class CompetitorAnalysisResponse(LinkedInAnalysisResponse):
    """Response model for competitor LinkedIn analysis"""
    competitor_id: str
    competitor_name: str
    insights: CompetitorInsights

class BusinessCompetitiveAnalysisRequest(LinkedInAnalysisRequest):
    """Request model for analyzing all competitors of a business"""
    analysis_types: List[str] = Field(
        ["sentiment", "keywords", "topics", "engagement", "content", "ads"],
        description="Types of analysis to perform"
    )
    include_comparison: bool = Field(True, description="Whether to include comparison between competitors")

class BusinessCompetitiveAnalysisResponse(LinkedInAnalysisResponse):
    """Response model for business-wide competitive analysis"""
    competitors: List[CompetitorInsights]
    comparison: Dict[str, Any]
    recommendations: List[str]