from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any

class LinkedInScrapeSettings(BaseModel):
    """Settings for LinkedIn scraping operations"""
    use_proxy: bool = Field(True, description="Whether to use proxy for scraping")
    proxy_country: str = Field("US", description="Country code for proxy")
    min_delay: int = Field(2, description="Minimum delay between requests in seconds")
    max_delay: int = Field(8, description="Maximum delay between requests in seconds")
    deep_scrape: bool = Field(True, description="Whether to perform deep scraping")

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
    business_id: str = Field(..., description="Business ID")
    competitor_id: str = Field(..., description="Competitor ID") 
    linkedin_url: str = Field(..., description="LinkedIn URL of the competitor")
    scrape_company: bool = Field(True, description="Whether to scrape company data")
    scrape_posts: bool = Field(True, description="Whether to scrape posts")
    scrape_ads: bool = Field(True, description="Whether to scrape ads")
    company_settings: Optional[LinkedInCompanyScrapeSettings] = Field(None, description="Settings for company scraping")
    post_settings: Optional[LinkedInPostScrapeSettings] = Field(None, description="Settings for post scraping")
    ads_settings: Optional[LinkedInAdsScrapeSettings] = Field(None, description="Settings for ads scraping")
    
    @field_validator('linkedin_url')
    @classmethod
    def validate_linkedin_url(cls, v):
        if not v.startswith('https://www.linkedin.com/'):
            raise ValueError('LinkedIn URL must start with https://www.linkedin.com/')
        return v

class BusinessCompetitorsScrapingRequest(BaseModel):
    """Request model for scraping all competitors for a business"""
    business_id: str = Field(..., description="Business ID")
    scrape_company: bool = Field(True, description="Whether to scrape company data")
    scrape_posts: bool = Field(True, description="Whether to scrape posts")
    scrape_ads: bool = Field(True, description="Whether to scrape ads")
    combine_data: bool = Field(True, description="Whether to combine data from all competitors")
    company_settings: Optional[LinkedInCompanyScrapeSettings] = Field(None, description="Settings for company scraping")
    post_settings: Optional[LinkedInPostScrapeSettings] = Field(None, description="Settings for post scraping")
    ads_settings: Optional[LinkedInAdsScrapeSettings] = Field(None, description="Settings for ads scraping")

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