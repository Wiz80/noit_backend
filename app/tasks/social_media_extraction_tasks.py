import logging
from typing import List, Dict, Any, Callable
from datetime import datetime
import httpx
import os

from .broker import broker
from app.controllers.competitive_analysis.website_extraction_controller import WebsiteExtractionController
from app.db.session import SessionLocal
from app.services.cache.task_progress_service import get_task_progress_service
from app.core.config import settings

# Configure logging
logger = logging.getLogger(__name__)

async def trigger_instagram_analysis_webhook(business_id: str, competitor_id: str):
    """Triggers a Kestra webhook to start the full Instagram analysis for a single competitor."""
    kestra_base_url = settings.KESTRA_URL.rstrip('/')
    namespace = "noit.backend"
    flow_id = "instagram-competitor-full-analysis"
    webhook_key = settings.KESTRA_INSTAGRAM_ANALYSIS_KEY
    
    webhook_url = f"{kestra_base_url}/api/v1/executions/webhook/{namespace}/{flow_id}/{webhook_key}"
    
    payload = {
        "business_id": business_id,
        "competitor_id": competitor_id
    }
    
    try:
        async with httpx.AsyncClient() as client:
            logger.info(f"Triggering Kestra webhook for Instagram analysis: {webhook_url} for competitor {competitor_id}")
            response = await client.post(webhook_url, json=payload, timeout=30.0)
            
            if response.status_code >= 400:
                logger.error(
                    f"Error triggering Kestra Instagram analysis webhook for competitor {competitor_id}. "
                    f"Status: {response.status_code}, Response: {response.text}"
                )
            else:
                logger.info(
                    f"Kestra Instagram analysis webhook for competitor {competitor_id} triggered successfully. "
                    f"Execution ID: {response.json().get('executionId')}"
                )
    except httpx.RequestError as e:
        logger.error(f"RequestError while triggering Kestra Instagram analysis webhook for competitor {competitor_id}: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error while triggering Kestra Instagram analysis webhook for competitor {competitor_id}: {str(e)}")

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
        
        # Check if there were any failures in the results
        if final_result["status"] == "failed" or any(
            res.get("status") == "failed" for res in final_result.get("results", {}).values()
        ):
            # Mark task as failed if any sub-task failed
            error_message = final_result.get("error", "One or more sub-tasks failed.")
            progress_service.set_task_failed(
                task_id=task_id,
                error=error_message,
                results=final_result["results"]
            )
            logger.error(f"❌ Social media extraction task completed with failures for business {business_id}, task {task_id}")
            # Raise an exception to mark the task as failed in TaskIQ
            raise Exception(error_message)

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
        
        # Re-raise the exception so TaskIQ marks the task as failed
        raise e
    finally:
        if db:
            db.close()

@broker.task
async def extract_social_media_from_single_competitor_task(
    business_id: str,
    competitor_id: str,
    task_id: str,
    update_db: bool = True
) -> Dict[str, Any]:
    """
    TaskIQ task for extracting social media information from a single competitor website.
    
    Args:
        business_id: UUID of the business idea
        competitor_id: ID of the competitor to process
        task_id: Task identifier for progress tracking
        update_db: Whether to update the database with the results
        
    Returns:
        Dict with task result information
    """
    logger.info(f"🔍 Starting social media extraction task for competitor {competitor_id}, task {task_id}")
    
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
        
        # Execute the social media extraction for single competitor
        final_result = await controller.run_website_social_media_extraction(
            competitor_ids=[competitor_id],  # Single competitor in list
            task_id=task_id,
            update_db=update_db,
            db=db,
            progress_callback=progress_callback
        )
        
        # Extract the single competitor result
        competitor_result = final_result.get("results", {}).get(competitor_id, {})
        
        # Check if the extraction failed
        if final_result["status"] == "failed":
            error_message = final_result.get("error", "Social media extraction failed")
            progress_service.set_task_failed(
                task_id=task_id,
                error=error_message,
                results=competitor_result
            )
            logger.error(f"❌ Social media extraction task failed for competitor {competitor_id}, task {task_id}: {error_message}")
            raise Exception(error_message)
        
        # Check if the specific competitor result failed
        if competitor_result.get("status") == "failed":
            error_message = competitor_result.get("error", "Competitor social media extraction failed")
            progress_service.set_task_failed(
                task_id=task_id,
                error=error_message,
                results=competitor_result
            )
            logger.error(f"❌ Social media extraction task failed for competitor {competitor_id}, task {task_id}: {error_message}")
            raise Exception(error_message)
            
        # Additional validation: Check if we have valid results
        if not competitor_result:
            error_message = f"No results returned for competitor {competitor_id}"
            progress_service.set_task_failed(
                task_id=task_id,
                error=error_message,
                results={}
            )
            logger.error(f"❌ Social media extraction task failed for competitor {competitor_id}, task {task_id}: {error_message}")
            raise Exception(error_message)

        # Mark task as completed
        progress_service.set_task_completed(
            task_id=task_id,
            results=competitor_result
        )
        
        logger.info(f"✅ Social media extraction task completed for competitor {competitor_id}, task {task_id}")
        
        # Check if an Instagram URL was found before triggering the next workflow
        if competitor_result.get("social_media", {}).get("instagram", {}).get("url"):
            logger.info(f"Instagram URL found for {competitor_id}. Triggering full Instagram analysis workflow.")
            await trigger_instagram_analysis_webhook(business_id=business_id, competitor_id=competitor_id)
        else:
            logger.info(f"No Instagram URL found for {competitor_id}. Skipping Instagram analysis trigger.")

        return {
            "status": "completed",
            "results": competitor_result,
            "competitor_id": competitor_id,
            "business_id": business_id,
            "task_id": task_id,
            "completed_at": datetime.now().isoformat(),
            "task_type": "single_competitor_social_media_extraction"
        }
        
    except Exception as e:
        error_message = str(e)
        logger.error(f"❌ Social media extraction task failed for competitor {competitor_id}, task {task_id}: {error_message}")
        
        # Mark task as failed in Redis
        progress_service.set_task_failed(
            task_id=task_id,
            error=error_message
        )
        
        # Re-raise the exception so TaskIQ marks the task as failed
        # This is crucial for TaskIQ to recognize the task as failed
        raise Exception(f"Social media extraction failed for competitor {competitor_id}: {error_message}")
    finally:
        if db:
            db.close() 