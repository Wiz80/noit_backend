import logging
from typing import List, Dict, Any, Callable
from datetime import datetime

from .broker import broker
from app.controllers.competitive_analysis.website_extraction_controller import WebsiteExtractionController
from app.db.session import SessionLocal
from app.services.cache.task_progress_service import get_task_progress_service

# Configure logging
logger = logging.getLogger(__name__)

@broker.task
async def extract_social_media_from_websites_task(
    business_id: str,
    competitor_ids: List[str],
    task_id: str,
    update_db: bool = True
) -> Dict[str, Any]:
    """
    TaskIQ task for extracting social media information from competitor websites.
    
    Args:
        business_id: UUID of the business idea
        competitor_ids: List of competitor IDs to process
        task_id: Task identifier for progress tracking
        update_db: Whether to update the database with the results
        
    Returns:
        Dict with task result information
    """
    logger.info(f"🔍 Starting social media extraction task for business {business_id}, task {task_id}")
    
    # Get progress service
    progress_service = get_task_progress_service()
    
    # Mark task as processing
    progress_service.set_task_progress(
        task_id=task_id,
        progress=10,
        status="processing"
    )
    
    db = None
    try:
        # Create database session
        db = SessionLocal()
        
        # Initialize controller
        controller = WebsiteExtractionController(business_id=business_id)
        
        # Create a progress callback that updates Redis
        def progress_callback(task_id: str, progress: int, status: str, results: Dict[str, Any]):
            logger.info(f"📊 Task {task_id} progress: {progress}% - Status: {status}")
            progress_service.set_task_progress(
                task_id=task_id,
                progress=progress,
                status=status,
                results=results
            )
        
        # Execute the social media extraction
        final_result = await controller.run_website_social_media_extraction(
            competitor_ids=competitor_ids,
            task_id=task_id,
            update_db=update_db,
            db=db,
            progress_callback=progress_callback
        )
        
        # Mark task as completed
        progress_service.set_task_completed(
            task_id=task_id,
            results=final_result["results"]
        )
        
        logger.info(f"✅ Social media extraction task completed for business {business_id}, task {task_id}")
        
        return {
            "status": final_result["status"],
            "results": final_result["results"],
            "error": final_result.get("error"),
            "business_id": business_id,
            "task_id": task_id,
            "completed_at": datetime.now().isoformat(),
            "task_type": "social_media_extraction"
        }
        
    except Exception as e:
        logger.error(f"❌ Social media extraction task failed for business {business_id}, task {task_id}: {str(e)}")
        
        # Mark task as failed
        progress_service.set_task_failed(
            task_id=task_id,
            error=str(e)
        )
        
        return {
            "status": "failed",
            "error": str(e),
            "business_id": business_id,
            "task_id": task_id,
            "completed_at": datetime.now().isoformat(),
            "task_type": "social_media_extraction"
        }
    finally:
        if db:
            db.close() 