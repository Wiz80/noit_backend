import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query, Path, Body
from sqlalchemy.orm import Session
from sqlalchemy import and_
import sys
import os
from dotenv import load_dotenv
from app.api.deps import get_db
from app.services.storage.minio_service import MinioService
from app.schemas.business.competitive_analysis_linkedin import (
    CompetitorAnalysisRequest,
    CompetitorAnalysisResponse,
    BusinessCompetitiveAnalysisRequest,
    BusinessCompetitiveAnalysisResponse,
)
from app.models.business.competitive_analysis.competitors import Competitor
from app.services.business.competitive_analysis.linkedin.linkedin_analysis_service import LinkedInAnalysisService
from scripts.linkedin_library_caller import build_search_url

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Create router
router = APIRouter()


@router.post(
    "/analyze/competitor/{business_id}/{competitor_id}",
    response_model=CompetitorAnalysisResponse,
    summary="Analyze LinkedIn data for a specific competitor",
    description="Performs NLP and ML analysis on LinkedIn data for a specific competitor, including sentiment analysis, keyword extraction, topic modeling, and more."
)
async def analyze_competitor_linkedin(
    business_id: str = Path(..., description="The business ID"),
    competitor_id: str = Path(..., description="The competitor ID"),
    request_data: CompetitorAnalysisRequest = Body(...),
    db: Session = Depends(get_db)
):
    """
    Analyze LinkedIn data for a specific competitor using NLP and ML
    
    Args:
        business_id: The business ID
        competitor_id: The competitor ID
        request_data: Request body containing analysis options
        db: Database session
        
    Returns:
        CompetitorAnalysisResponse: The analysis results
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
    
    # Initialize the LinkedIn analysis service
    linkedin_analysis_service = LinkedInAnalysisService()
    
    # Perform analysis
    result = await linkedin_analysis_service.analyze_competitor(
        business_id=business_id,
        competitor_id=competitor_id,
        competitor_name=competitor.competitor_name,
        analysis_types=request_data.analysis_types,
        force_refresh=request_data.force_refresh
    )
    
    # Format response
    response = {
        "business_id": business_id,
        "analysis_id": result.get("analysis_id", ""),
        "status": result.get("status", "completed"),
        "competitor_id": competitor_id,
        "competitor_name": competitor.competitor_name,
        "insights": result.get("insights", {}),
        "results": result
    }
    
    return response

@router.post(
    "/analyze/business/{business_id}",
    response_model=BusinessCompetitiveAnalysisResponse,
    summary="Analyze LinkedIn data for all competitors of a business",
    description="Performs NLP and ML analysis on LinkedIn data for all competitors of a business, including comparison and recommendations."
)
async def analyze_business_competitors_linkedin(
    business_id: str = Path(..., description="The business ID"),
    request_data: BusinessCompetitiveAnalysisRequest = Body(...),
    db: Session = Depends(get_db)
):
    """
    Analyze LinkedIn data for all competitors of a business using NLP and ML
    
    Args:
        business_id: The business ID
        request_data: Request body containing analysis options
        db: Database session
        
    Returns:
        BusinessCompetitiveAnalysisResponse: The analysis results
    """
    # Get all competitors for the business using SQLAlchemy query
    competitors = db.query(Competitor).filter(Competitor.business_id == business_id).all()
    
    if not competitors:
        raise HTTPException(
            status_code=404,
            detail=f"No competitors found for business {business_id}"
        )
    
    # Initialize the LinkedIn analysis service
    linkedin_analysis_service = LinkedInAnalysisService()
    
    # Collect competitor IDs and names
    competitor_ids = []
    competitor_names = []
    
    for competitor in competitors:
        competitor_ids.append(competitor.id)
        competitor_names.append(competitor.competitor_name)
    
    # Perform business-wide analysis
    result = await linkedin_analysis_service.analyze_business_competitors(
        business_id=business_id,
        competitor_ids=competitor_ids,
        competitor_names=competitor_names,
        analysis_types=request_data.analysis_types,
        include_comparison=request_data.include_comparison,
        force_refresh=request_data.force_refresh
    )
    
    # Format response
    response = {
        "business_id": business_id,
        "analysis_id": result.get("analysis_id", ""),
        "status": result.get("status", "completed"),
        "competitors": result.get("competitors", []),
        "comparison": result.get("comparison", {}),
        "recommendations": result.get("recommendations", []),
        "results": result
    }
    
    return response

@router.get(
    "/analyze/competitor/{business_id}/{competitor_id}",
    response_model=CompetitorAnalysisResponse,
    summary="Get LinkedIn analysis for a specific competitor",
    description="Retrieves existing NLP and ML analysis for a specific competitor from Minio storage."
)
async def get_competitor_linkedin_analysis(
    business_id: str = Path(..., description="The business ID"),
    competitor_id: str = Path(..., description="The competitor ID"),
    db: Session = Depends(get_db)
):
    """
    Get LinkedIn analysis for a specific competitor
    
    Args:
        business_id: The business ID
        competitor_id: The competitor ID
        db: Database session
        
    Returns:
        CompetitorAnalysisResponse: The analysis results
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
    
    # Initialize MinIO service
    minio_service = MinioService(bucket_name="lattice-businesses")
    
    # Define the path for the analysis data
    analysis_path = f"{business_id}/competitor-analysis/linkedin/{competitor.competitor_name.lower()}/analysis.json"
    
    # Check if the object exists
    if not minio_service.object_exists(analysis_path):
        raise HTTPException(
            status_code=404,
            detail=f"LinkedIn analysis not found for competitor {competitor.competitor_name}"
        )
    
    # Get the data
    try:
        result = minio_service.download_json(analysis_path)
        
        # Format response
        response = {
            "business_id": business_id,
            "analysis_id": result.get("analysis_id", ""),
            "status": result.get("status", "completed"),
            "competitor_id": competitor_id,
            "competitor_name": competitor.competitor_name,
            "insights": result.get("insights", {}),
            "results": result
        }
        
        return response
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving LinkedIn analysis: {str(e)}"
        )

@router.get(
    "/analyze/business/{business_id}",
    response_model=BusinessCompetitiveAnalysisResponse,
    summary="Get LinkedIn analysis for all competitors of a business",
    description="Retrieves existing NLP and ML analysis for all competitors of a business from Minio storage."
)
async def get_business_linkedin_analysis(
    business_id: str = Path(..., description="The business ID"),
    db: Session = Depends(get_db)
):
    """
    Get LinkedIn analysis for all competitors of a business
    
    Args:
        business_id: The business ID
        db: Database session
        
    Returns:
        BusinessCompetitiveAnalysisResponse: The analysis results
    """
    # Check if the business exists
    competitors = db.query(Competitor).filter(Competitor.business_id == business_id).all()
    
    if not competitors:
        raise HTTPException(
            status_code=404,
            detail=f"No competitors found for business {business_id}"
        )
    
    # Initialize MinIO service
    minio_service = MinioService(bucket_name="lattice-businesses")
    
    # Define the path for the analysis data
    analysis_path = f"{business_id}/competitor-analysis/linkedin/business_analysis.json"
    
    # Check if the object exists
    if not minio_service.object_exists(analysis_path):
        raise HTTPException(
            status_code=404,
            detail=f"LinkedIn analysis not found for business {business_id}"
        )
    
    # Get the data
    try:
        result = minio_service.download_json(analysis_path)
        
        # Format response
        response = {
            "business_id": business_id,
            "analysis_id": result.get("analysis_id", ""),
            "status": result.get("status", "completed"),
            "competitors": result.get("competitors", []),
            "comparison": result.get("comparison", {}),
            "recommendations": result.get("recommendations", []),
            "results": result
        }
        
        return response
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving LinkedIn analysis: {str(e)}"
        ) 