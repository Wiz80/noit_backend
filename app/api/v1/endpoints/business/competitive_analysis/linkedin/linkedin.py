import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query, Path
from sqlalchemy.orm import Session
from sqlalchemy import and_
import sys

from app.api.deps import get_db
from app.services.business.competitive_analysis.linkedin.linkedin_service import LinkedInService
from app.services.business.competitive_analysis.linkedin.linkedin_library_scraper import build_search_url
from app.schemas.business.competitive_analysis_linkedin import (
    CompetitorScrapingRequest,
    BusinessCompetitorsScrapingRequest,
    LinkedInScrapingResponse,
    BusinessCombinedDataResponse,
)
from app.models.business.competitive_analysis.competitors import Competitor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

@router.post(
    "/competitor/{business_id}/{competitor_id}",
    response_model=LinkedInScrapingResponse,
    summary="Scrape LinkedIn data for a specific competitor",
    description="Scrapes LinkedIn data for a specific competitor, including company information, posts, and ads."
)
async def scrape_competitor_linkedin(
    business_id: str = Path(..., description="The business ID"),
    competitor_id: str = Path(..., description="The competitor ID"),
    scrape_company: bool = Query(True, description="Whether to scrape company data"),
    scrape_posts: bool = Query(True, description="Whether to scrape posts"),
    scrape_ads: bool = Query(True, description="Whether to scrape ads"),
    db: Session = Depends(get_db)
):
    """
    Scrape LinkedIn data for a specific competitor
    
    Args:
        business_id: The business ID
        competitor_id: The competitor ID  
        scrape_company: Whether to scrape company data
        scrape_posts: Whether to scrape posts
        scrape_ads: Whether to scrape ads
        db: Database session
        
    Returns:
        LinkedInScrapingResponse: The scraping results
    """
    # Verify that the competitor exists for the given business using SQLAlchemy query
    competitor = db.query(Competitor).filter(
        and_(
            Competitor.id == competitor_id,
            Competitor.business_idea_id == business_id
        )
    ).first()
    
    if not competitor:
        raise HTTPException(
            status_code=404,
            detail=f"Competitor {competitor_id} not found for business {business_id}"
        )
    
    # Check if competitor has a LinkedIn URL
    if not competitor.linkedin_url:
        raise HTTPException(
            status_code=400,
            detail=f"Competitor {competitor.competitor_name} does not have a LinkedIn URL"
        )
    
    # Initialize LinkedIn service
    linkedin_service = LinkedInService()
    
    # Prepare kwargs for services with default settings
    kwargs = {
        "use_proxy": True,
        "proxy_country": "US",
        "min_delay": 2,
        "max_delay": 8,
        "deep_scrape": True
    }
    
    # For ads, build a search URL if needed
    if scrape_ads:
        # Extract company name/ID from LinkedIn URL
        company_url_parts = competitor.linkedin_url.split('/')
        company_id = company_url_parts[-1] if company_url_parts[-1] else company_url_parts[-2]
        
        # Add settings for ads scraping
        ads_kwargs = {
            "date_option": "last-30-days",
            "country": "ALL",
            "limit": 20
        }
        kwargs.update(ads_kwargs)
    
    # Scrape competitor data
    result = await linkedin_service.scrape_competitor_data(
        business_id=business_id,
        competitor_id=competitor_id,
        linkedin_url=competitor.linkedin_url,
        scrape_company=scrape_company,
        scrape_posts=scrape_posts,
        scrape_ads=scrape_ads,
        **kwargs
    )
    
    return result


@router.post(
    "/business/{business_id}",
    response_model=Dict[str, Any],
    summary="Scrape LinkedIn data for all competitors of a business",
    description="Scrapes LinkedIn data for all competitors of a business, including company information, posts, and ads."
)
async def scrape_business_competitors_linkedin(
    business_id: str = Path(..., description="The business ID"),
    scrape_company: bool = Query(True, description="Whether to scrape company data"),
    scrape_posts: bool = Query(True, description="Whether to scrape posts"),
    scrape_ads: bool = Query(True, description="Whether to scrape ads"),
    combine_data: bool = Query(True, description="Whether to combine data from all competitors"),
    db: Session = Depends(get_db)
):
    """
    Scrape LinkedIn data for all competitors of a business
    
    Args:
        business_id: The business ID
        scrape_company: Whether to scrape company data
        scrape_posts: Whether to scrape posts
        scrape_ads: Whether to scrape ads
        combine_data: Whether to combine data from all competitors
        db: Database session
        
    Returns:
        Dict: The scraping results for each competitor
    """
    # Get all competitors for the business using SQLAlchemy query
    competitors = db.query(Competitor).filter(Competitor.business_id == business_id).all()
    
    if not competitors:
        raise HTTPException(
            status_code=404,
            detail=f"No competitors found for business {business_id}"
        )
    
    # Initialize LinkedIn service
    linkedin_service = LinkedInService()
    
    # Scrape data for each competitor
    results = {}
    competitor_ids = []
    
    for competitor in competitors:
        # Skip competitors without a LinkedIn URL
        if not competitor.linkedin_url:
            continue
        
        competitor_ids.append(competitor.id)
        
        # Scrape competitor data
        result = await linkedin_service.scrape_competitor_data(
            business_id=business_id,
            competitor_id=competitor.id,
            linkedin_url=competitor.linkedin_url,
            scrape_company=scrape_company,
            scrape_posts=scrape_posts,
            scrape_ads=scrape_ads
        )
        
        results[competitor.id] = result
    
    # Combine data if requested
    if combine_data and competitor_ids:
        combined_result = await linkedin_service.generate_combined_data(
            business_id=business_id,
            competitor_ids=competitor_ids
        )
        results["combined"] = combined_result
    
    return results


@router.post(
    "/combine/{business_id}",
    response_model=BusinessCombinedDataResponse,
    summary="Combine existing LinkedIn data for all competitors of a business",
    description="Combines existing LinkedIn data for all competitors of a business."
)
async def combine_business_competitors_linkedin(
    business_id: str = Path(..., description="The business ID"),
    db: Session = Depends(get_db)
):
    """
    Combine existing LinkedIn data for all competitors of a business
    
    Args:
        business_id: The business ID
        db: Database session
        
    Returns:
        BusinessCombinedDataResponse: The combined data results
    """
    # Get all competitors for the business using SQLAlchemy query
    competitors = db.query(Competitor).filter(Competitor.business_id == business_id).all()
    
    if not competitors:
        raise HTTPException(
            status_code=404,
            detail=f"No competitors found for business {business_id}"
        )
    
    # Initialize LinkedIn service
    linkedin_service = LinkedInService()
    
    # Get competitor IDs
    competitor_ids = [competitor.id for competitor in competitors]
    
    # Combine data
    combined_result = await linkedin_service.generate_combined_data(
        business_id=business_id,
        competitor_ids=competitor_ids
    )
    
    return combined_result 