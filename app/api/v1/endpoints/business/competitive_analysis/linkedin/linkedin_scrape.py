import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query, Path, Body
from sqlalchemy.orm import Session
from sqlalchemy import and_
import sys
import os
from dotenv import load_dotenv

from app.api.deps import get_db
from app.services.business.competitive_analysis.linkedin.linkedin_service import LinkedInService
from app.schemas.business.competitive_analysis_linkedin import (
    CompetitorScrapingRequest,
    BusinessCompetitorsScrapingRequest,
    LinkedInScrapingResponse,
    BusinessCombinedDataResponse
)
from app.models.business.competitive_analysis.competitors import Competitor
from app.services.storage.minio_service import MinioService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

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
    request_data: CompetitorScrapingRequest = Body(...),
    db: Session = Depends(get_db)
):
    """
    Scrape LinkedIn data for a specific competitor
    
    Args:
        business_id: The business ID
        competitor_id: The competitor ID  
        request_data: Request body containing scraping options
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
    
    # Get API token from environment
    apify_api_token = os.getenv("APIFY_API_KEY")
    if not apify_api_token:
        raise HTTPException(
            status_code=500, 
            detail="APIFY_API_KEY environment variable is not set"
        )
    
    # Initialize LinkedIn service with API token
    linkedin_service = LinkedInService(
        apify_api_token=apify_api_token,
        timeout_secs=request_data.timeout_secs
    )
    
    # Prepare kwargs for services with default settings
    kwargs = {
        "use_proxy": True,
        "proxy_country": "US",
        "min_delay": 2,
        "max_delay": 8,
        "deep_scrape": True
    }
    
    # For ads, build a search URL if needed
    if request_data.scrape_ads:
        # Extract company name/ID from LinkedIn URL
        company_url_parts = competitor.linkedin_url.split('/')
        company_id = company_url_parts[-1] if company_url_parts[-1] else company_url_parts[-2]
        
        # Add settings for ads scraping
        ads_kwargs = {
            "date_option": "last-30-days",
            "country": "ALL",
            "limit": 5,
            "timeout_secs": request_data.timeout_secs
        }
        kwargs.update(ads_kwargs)
    
    # Scrape competitor data
    result = await linkedin_service.scrape_competitor_data(
        business_id=business_id,
        competitor=competitor,
        scrape_company=request_data.scrape_company,
        scrape_posts=request_data.scrape_posts,
        scrape_ads=request_data.scrape_ads,
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
    request_data: BusinessCompetitorsScrapingRequest = Body(...),
    db: Session = Depends(get_db)
):
    """
    Scrape LinkedIn data for all competitors of a business
    
    Args:
        business_id: The business ID
        request_data: Request body containing scraping options
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
    
    # Get API token from environment
    apify_api_token = os.getenv("APIFY_API_KEY")
    if not apify_api_token:
        raise HTTPException(
            status_code=500, 
            detail="APIFY_API_KEY environment variable is not set"
        )
    
    # Initialize LinkedIn service with API token
    linkedin_service = LinkedInService(
        apify_api_token=apify_api_token,
        timeout_secs=request_data.timeout_secs
    )
    
    # Scrape data for each competitor
    results = {}
    competitor_ids = []
    competitor_names = []
    
    for competitor in competitors:
        # Skip competitors without a LinkedIn URL
        if not competitor.linkedin_url:
            continue
        
        competitor_ids.append(competitor.id)
        competitor_names.append(competitor.competitor_name)
        
        # Scrape competitor data
        result = await linkedin_service.scrape_competitor_data(
            business_id=business_id,
            competitor=competitor,
            scrape_company=request_data.scrape_company,
            scrape_posts=request_data.scrape_posts,
            scrape_ads=request_data.scrape_ads,
            timeout_secs=request_data.timeout_secs
        )
        
        results[competitor.id] = result
    
    # Combine data if requested
    if request_data.combine_data and competitor_ids:
        combined_result = await linkedin_service.generate_combined_data(
            business_id=business_id,
            competitor_ids=competitor_ids,
            competitor_names=competitor_names
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
    timeout_secs: Optional[int] = Query(600, description="Timeout in seconds for the Apify actor calls"),
    db: Session = Depends(get_db)
):
    """
    Combine existing LinkedIn data for all competitors of a business
    
    Args:
        business_id: The business ID
        timeout_secs: Timeout in seconds for the Apify actor calls
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
    
    # Get API token from environment
    apify_api_token = os.getenv("APIFY_API_KEY")
    if not apify_api_token:
        raise HTTPException(
            status_code=500, 
            detail="APIFY_API_KEY environment variable is not set"
        )
    
    # Initialize LinkedIn service with API token
    linkedin_service = LinkedInService(
        apify_api_token=apify_api_token,
        timeout_secs=timeout_secs
    )
    
    # Get competitor IDs
    competitor_ids = []
    competitor_names = []
    for competitor in competitors:
        competitor_ids.append(competitor.id)
        competitor_names.append(competitor.competitor_name)
    
    # Combine data
    combined_result = await linkedin_service.generate_combined_data(
        business_id=business_id,
        competitor_ids=competitor_ids,
        competitor_names=competitor_names
    )
    
    return combined_result

@router.get(
    "/competitor/{business_id}/{competitor_id}/company",
    response_model=Any,
    summary="Get LinkedIn company data for a specific competitor",
    description="Retrieves LinkedIn company data for a specific competitor from Minio storage."
)
async def get_competitor_linkedin_company(
    business_id: str = Path(..., description="The business ID"),
    competitor_id: str = Path(..., description="The competitor ID"),
    db: Session = Depends(get_db)
):
    """
    Get LinkedIn company data for a specific competitor
    
    Args:
        business_id: The business ID
        competitor_id: The competitor ID  
        db: Database session
        
    Returns:
        Any: The company data
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
    
    competitor_name = competitor.competitor_name.lower()
    
    # Initialize MinIO service
    minio_service = MinioService(bucket_name=settings.MINIO_BUCKET_NAME)
    
    # Define the path for the company data
    object_path = f"{business_id}/competitor-analysis/linkedin/{competitor_name}/company.json"
    
    # Check if the object exists
    if not minio_service.object_exists(object_path):
        raise HTTPException(
            status_code=404,
            detail=f"LinkedIn company data not found for competitor {competitor.competitor_name}"
        )
    
    # Get the data
    try:
        data = minio_service.download_json(object_path)
        return data
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving LinkedIn company data: {str(e)}"
        )

@router.get(
    "/competitor/{business_id}/{competitor_id}/posts",
    response_model=Any,
    summary="Get LinkedIn posts data for a specific competitor",
    description="Retrieves LinkedIn posts data for a specific competitor from Minio storage."
)
async def get_competitor_linkedin_posts(
    business_id: str = Path(..., description="The business ID"),
    competitor_id: str = Path(..., description="The competitor ID"),
    db: Session = Depends(get_db)
):
    """
    Get LinkedIn posts data for a specific competitor
    
    Args:
        business_id: The business ID
        competitor_id: The competitor ID  
        db: Database session
        
    Returns:
        Any: The posts data
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
    
    competitor_name = competitor.competitor_name.lower()
    
    # Initialize MinIO service
    minio_service = MinioService(bucket_name=settings.MINIO_BUCKET_NAME)
    
    # Define the path for the posts data
    object_path = f"{business_id}/competitor-analysis/linkedin/{competitor_name}/post.json"
    
    # Check if the object exists
    if not minio_service.object_exists(object_path):
        raise HTTPException(
            status_code=404,
            detail=f"LinkedIn posts data not found for competitor {competitor.competitor_name}"
        )
    
    # Get the data
    try:
        data = minio_service.download_json(object_path)
        return data
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving LinkedIn posts data: {str(e)}"
        )

@router.get(
    "/competitor/{business_id}/{competitor_id}/ads",
    response_model=Any,
    summary="Get LinkedIn ads data for a specific competitor",
    description="Retrieves LinkedIn ads data for a specific competitor from Minio storage."
)
async def get_competitor_linkedin_ads(
    business_id: str = Path(..., description="The business ID"),
    competitor_id: str = Path(..., description="The competitor ID"),
    db: Session = Depends(get_db)
):
    """
    Get LinkedIn ads data for a specific competitor
    
    Args:
        business_id: The business ID
        competitor_id: The competitor ID  
        db: Database session
        
    Returns:
        Any: The ads data
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
    
    competitor_name = competitor.competitor_name.lower()
    
    # Initialize MinIO service
    minio_service = MinioService(bucket_name=settings.MINIO_BUCKET_NAME)
    
    # Define the path for the ads data
    object_path = f"{business_id}/competitor-analysis/linkedin/{competitor_name}/ads.json"
    
    # Check if the object exists
    if not minio_service.object_exists(object_path):
        raise HTTPException(
            status_code=404,
            detail=f"LinkedIn ads data not found for competitor {competitor.competitor_name}"
        )
    
    # Get the data
    try:
        data = minio_service.download_json(object_path)
        return data
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving LinkedIn ads data: {str(e)}"
        )

@router.get(
    "/competitor/{business_id}/{competitor_id}/all",
    response_model=Dict[str, Any],
    summary="Get all LinkedIn data for a specific competitor",
    description="Retrieves all LinkedIn data (company, posts, and ads) for a specific competitor from Minio storage."
)
async def get_competitor_linkedin_all(
    business_id: str = Path(..., description="The business ID"),
    competitor_id: str = Path(..., description="The competitor ID"),
    db: Session = Depends(get_db)
):
    """
    Get all LinkedIn data for a specific competitor
    
    Args:
        business_id: The business ID
        competitor_id: The competitor ID  
        db: Database session
        
    Returns:
        Dict: All LinkedIn data (company, posts, and ads)
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
    
    competitor_name = competitor.competitor_name.lower()
    
    # Initialize MinIO service
    minio_service = MinioService(bucket_name=settings.MINIO_BUCKET_NAME)
    
    result = {
        "business_id": business_id,
        "competitor_id": competitor_id,
        "competitor_name": competitor.competitor_name,
        "linkedin_url": competitor.linkedin_url,
        "company": None,
        "posts": None,
        "ads": None
    }
    
    # Get company data
    company_path = f"{business_id}/competitor-analysis/linkedin/{competitor_name}/company.json"
    if minio_service.object_exists(company_path):
        try:
            result["company"] = minio_service.download_json(company_path)
        except Exception as e:
            logger.error(f"Error retrieving LinkedIn company data: {str(e)}")
    
    # Get posts data
    posts_path = f"{business_id}/competitor-analysis/linkedin/{competitor_name}/post.json"
    if minio_service.object_exists(posts_path):
        try:
            result["posts"] = minio_service.download_json(posts_path)
        except Exception as e:
            logger.error(f"Error retrieving LinkedIn posts data: {str(e)}")
    
    # Get ads data
    ads_path = f"{business_id}/competitor-analysis/linkedin/{competitor_name}/ads.json"
    if minio_service.object_exists(ads_path):
        try:
            result["ads"] = minio_service.download_json(ads_path)
        except Exception as e:
            logger.error(f"Error retrieving LinkedIn ads data: {str(e)}")
    
    # Check if we found any data
    if result["company"] is None and result["posts"] is None and result["ads"] is None:
        raise HTTPException(
            status_code=404,
            detail=f"No LinkedIn data found for competitor {competitor.competitor_name}"
        )
    
    return result

@router.get(
    "/business/{business_id}/combined",
    response_model=Dict[str, Any],
    summary="Get combined LinkedIn data for all competitors of a business",
    description="Retrieves combined LinkedIn data for all competitors of a business from Minio storage."
)
async def get_business_competitors_combined_linkedin(
    business_id: str = Path(..., description="The business ID"),
    db: Session = Depends(get_db)
):
    """
    Get combined LinkedIn data for all competitors of a business
    
    Args:
        business_id: The business ID
        db: Database session
        
    Returns:
        Dict: Combined LinkedIn data for all competitors
    """
    # Check if the business exists
    competitors = db.query(Competitor).filter(Competitor.business_id == business_id).all()
    
    if not competitors:
        raise HTTPException(
            status_code=404,
            detail=f"No competitors found for business {business_id}"
        )
    
    # Initialize MinIO service
    minio_service = MinioService(bucket_name=settings.MINIO_BUCKET_NAME)
    
    result = {
        "business_id": business_id,
        "company": None,
        "posts": None,
        "ads": None
    }
    
    # Get combined company data
    company_path = f"{business_id}/competitor-analysis/linkedin/company.json"
    if minio_service.object_exists(company_path):
        try:
            result["company"] = minio_service.download_json(company_path)
        except Exception as e:
            logger.error(f"Error retrieving combined LinkedIn company data: {str(e)}")
    
    # Get combined posts data
    posts_path = f"{business_id}/competitor-analysis/linkedin/posts.json"
    if minio_service.object_exists(posts_path):
        try:
            result["posts"] = minio_service.download_json(posts_path)
        except Exception as e:
            logger.error(f"Error retrieving combined LinkedIn posts data: {str(e)}")
    
    # Get combined ads data
    ads_path = f"{business_id}/competitor-analysis/linkedin/ads.json"
    if minio_service.object_exists(ads_path):
        try:
            result["ads"] = minio_service.download_json(ads_path)
        except Exception as e:
            logger.error(f"Error retrieving combined LinkedIn ads data: {str(e)}")
    
    # Check if we found any data
    if result["company"] is None and result["posts"] is None and result["ads"] is None:
        raise HTTPException(
            status_code=404,
            detail=f"No combined LinkedIn data found for business {business_id}"
        )
    
    return result