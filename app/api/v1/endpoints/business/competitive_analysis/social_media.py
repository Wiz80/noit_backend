from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Request, Form
from fastapi.responses import JSONResponse
from app.api import deps
from typing import List, Optional, Dict, Any
import uuid
from uuid import UUID
import logging
from app.controllers.competitive_analysis.website_extraction_controller import WebsiteExtractionController

from app.models.business.business_idea import BusinessIdea
from app.models.business.competitive_analysis.competitors import Competitor
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.schemas.business.business_competitors import WebsiteSocialMediaScrapingRequest, WebsiteSocialMediaScrapingResponse

from app.utils.decode_json import clean_json_encoding

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Simple cache to store task progress
# In production, you should use Redis or similar
analysis_progress = {}

router = APIRouter()

@router.post("/{business_id}", response_model=WebsiteSocialMediaScrapingResponse)
async def extract_social_media_from_websites(
    business_id: UUID,
    request: WebsiteSocialMediaScrapingRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(deps.get_db)
):
    """
    Extract social media information from competitor websites using AI-powered scraping.
    
    Args:
        business_id: UUID of the business idea
        request: WebsiteSocialMediaScrapingRequest with optional competitor_ids list and update_db flag
        background_tasks: FastAPI background tasks
        db: Database session
        
    Returns:
        WebsiteSocialMediaScrapingResponse: Task information and results
    """
    try:
        # Verify if business_id exists
        if not db.query(BusinessIdea).filter(BusinessIdea.id == str(business_id)).first():
            raise HTTPException(status_code=404, detail="Business idea not found")

        # Get competitors based on request.competitor_ids (if provided) or all competitors
        query = db.query(Competitor).filter(
            Competitor.business_idea_id == str(business_id)
        )
        
        # Filter by specific competitor IDs if provided
        if request.competitor_ids:
            query = query.filter(Competitor.id.in_(request.competitor_ids))
            
        competitors = query.all()

        if not competitors:
            raise HTTPException(status_code=404, detail="No competitors found with provided criteria")

        # Check that competitors have websites
        competitors_with_websites = [comp for comp in competitors if comp.website]
        if not competitors_with_websites:
            raise HTTPException(status_code=404, detail="None of the requested competitors have website URLs")

        # Generate a unique task ID
        task_id = str(uuid.uuid4())
        
        # Initialize progress
        analysis_progress[task_id] = {
            "progress": 0,
            "status": "started",
            "results": {},
            "error": None
        }

        # Initialize controller
        controller = WebsiteExtractionController(business_id=str(business_id))
        
        # Create a progress callback function
        def update_progress(task_id, progress, status, results):
            if task_id in analysis_progress:
                analysis_progress[task_id].update({
                    "progress": progress,
                    "status": status,
                    "results": results
                })

        # Run extraction here instead of in background
        await async_extraction_wrapper(
            controller=controller,
            competitor_ids=[comp.id for comp in competitors_with_websites],
            task_id=task_id,
            update_db=request.update_db,
            db=db,
            progress_callback=update_progress
        )

        return WebsiteSocialMediaScrapingResponse(
            task_id=task_id,
            status="processing",
            results=None
        )

    except Exception as e:
        # If there was a task_id created, update its status
        if 'task_id' in locals():
            analysis_progress[task_id] = {
                "status": "failed",
                "error": str(e),
                "progress": 0
            }
        
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{business_id}/task/{task_id}", response_model=WebsiteSocialMediaScrapingResponse)
async def get_social_media_extraction_progress(
    business_id: UUID,
    task_id: str,
    db: Session = Depends(deps.get_db)
):
    """
    Get the progress of social media extraction for a specific task.
    
    Args:
        business_id: UUID of the business idea
        task_id: Task identifier
        db: Database session
        
    Returns:
        WebsiteSocialMediaScrapingResponse: Task progress information
    """
    if task_id not in analysis_progress:
        raise HTTPException(status_code=404, detail="Task not found")

    progress_data = analysis_progress[task_id]
    
    return WebsiteSocialMediaScrapingResponse(
        task_id=task_id,
        status=progress_data["status"],
        results=progress_data.get("results")
    )

async def async_extraction_wrapper(
    controller: WebsiteExtractionController,
    competitor_ids: List[str],
    task_id: str,
    update_db: bool,
    db: Session,
    progress_callback: callable
):
    """
    Wrapper function to handle the controller's async execution and finalize the results.
    
    Args:
        controller: WebsiteExtractionController instance
        competitor_ids: List of competitor IDs to process
        task_id: Task identifier
        update_db: Whether to update the database with the results
        db: Database session
        progress_callback: Callback function for progress updates
    """
    try:
        # Run extraction and get final result
        final_result = await controller.run_website_social_media_extraction(
            competitor_ids=competitor_ids,
            task_id=task_id,
            update_db=update_db,
            db=db,
            progress_callback=progress_callback
        )
        
        # Update final status in progress cache
        if task_id in analysis_progress:
            analysis_progress[task_id].update({
                "progress": 100,
                "status": final_result["status"],
                "results": final_result["results"],
                "error": final_result.get("error")
            })
            
    except Exception as e:
        # Update error status in progress cache
        if task_id in analysis_progress:
            analysis_progress[task_id].update({
                "status": "failed",
                "error": str(e)
            })