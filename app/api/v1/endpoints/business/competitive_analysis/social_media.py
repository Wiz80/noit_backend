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
from app.models.user import User

# Import TaskIQ tasks
from app.tasks.social_media_extraction_tasks import extract_social_media_from_websites_task, extract_social_media_from_single_competitor_task
# Import task progress service
from app.services.cache.task_progress_service import get_task_progress_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/{business_id}", response_model=WebsiteSocialMediaScrapingResponse)
async def extract_social_media_from_websites(
    business_id: UUID,
    request: WebsiteSocialMediaScrapingRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_superuser)
):
    """
    Extract social media information from competitor websites using AI-powered scraping.
    This endpoint creates separate TaskIQ tasks for each competitor for distributed processing.
    
    Args:
        business_id: UUID of the business idea
        request: WebsiteSocialMediaScrapingRequest with optional competitor_ids list and update_db flag
        background_tasks: FastAPI background tasks (not used with TaskIQ)
        db: Database session
        current_user: Current active superuser
        
    Returns:
        WebsiteSocialMediaScrapingResponse: Task information
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

        # Generate a main task ID for tracking all sub-tasks
        main_task_id = str(uuid.uuid4())
        
        # Get progress service
        progress_service = get_task_progress_service()
        
        # Initialize main task progress in Redis
        progress_service.set_task_progress(
            task_id=main_task_id,
            progress=0,
            status="queued",
            results={
                "total_competitors": len(competitors_with_websites),
                "completed_competitors": 0,
                "sub_tasks": {}
            }
        )

        # Create separate tasks for each competitor
        sub_task_ids = []
        failed_tasks = []
        
        for competitor in competitors_with_websites:
            try:
                # Generate unique task ID for this competitor
                sub_task_id = str(uuid.uuid4())
                sub_task_ids.append({
                    "competitor_id": competitor.id,
                    "competitor_name": competitor.competitor_name,
                    "task_id": sub_task_id
                })
                
                # Initialize sub-task progress
                progress_service.set_task_progress(
                    task_id=sub_task_id,
                    progress=0,
                    status="queued"
                )
                
                # Queue individual TaskIQ task for this competitor
                taskiq_task = await extract_social_media_from_single_competitor_task.kiq(
                    business_id=str(business_id),
                    competitor_id=competitor.id,
                    task_id=sub_task_id,
                    update_db=request.update_db
                )
                
                logger.info(f"📤 TaskIQ task queued with ID: {taskiq_task.task_id} for competitor {competitor.competitor_name}")
                
                # Update sub-task progress to indicate it was queued
                progress_service.update_task_progress(sub_task_id, {
                    "status": "queued",
                    "taskiq_task_id": taskiq_task.task_id,
                    "competitor_name": competitor.competitor_name
                })
                
            except Exception as e:
                logger.error(f"❌ Failed to queue TaskIQ task for competitor {competitor.competitor_name}: {str(e)}")
                failed_tasks.append({
                    "competitor_id": competitor.id,
                    "competitor_name": competitor.competitor_name,
                    "error": str(e)
                })
                progress_service.set_task_failed(sub_task_id, f"Failed to queue task: {str(e)}")

        # Update main task with sub-task information
        main_task_results = {
            "total_competitors": len(competitors_with_websites),
            "completed_competitors": 0,
            "queued_tasks": len(sub_task_ids),
            "failed_to_queue": len(failed_tasks),
            "sub_tasks": {task["task_id"]: task for task in sub_task_ids},
            "failed_tasks": failed_tasks
        }
        
        if failed_tasks and len(failed_tasks) == len(competitors_with_websites):
            # All tasks failed to queue
            progress_service.set_task_failed(
                main_task_id, 
                "Failed to queue any tasks",
                results=main_task_results
            )
            raise HTTPException(status_code=500, detail="Failed to queue extraction tasks for any competitor")
        else:
            # At least some tasks were queued successfully
            status = "partially_queued" if failed_tasks else "queued"
            progress_service.update_task_progress(main_task_id, {
                "status": status,
                "results": main_task_results
            })

        return WebsiteSocialMediaScrapingResponse(
            task_id=main_task_id,
            status=status,
            results=main_task_results
        )

    except Exception as e:
        # If there was a main_task_id created, update its status
        if 'main_task_id' in locals():
            progress_service = get_task_progress_service()
            progress_service.set_task_failed(main_task_id, str(e))
        
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
    # Get progress service
    progress_service = get_task_progress_service()
    
    # Get progress data from Redis
    progress_data = progress_service.get_task_progress(task_id)
    
    if progress_data is None:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return WebsiteSocialMediaScrapingResponse(
        task_id=task_id,
        status=progress_data["status"],
        results=progress_data.get("results")
    )