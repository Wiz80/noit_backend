from fastapi import APIRouter, HTTPException
import logging
from fastapi import Request
from sqlalchemy.orm import Session
from fastapi import Depends, Path
from app.api import deps
from app.models.business.competitive_analysis.business_competitor import CompetitorResearch, CompetitorResearchStatus
from datetime import datetime
import json
from app.services.storage.minio_service import MinioService
from app.models.business.business_understanding.state_of_art import ResearchTask
from app.services.business.business_understanding.state_of_art import MarketStateOfArtService
from fastapi.responses import JSONResponse


router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/research-callback/{task_id}")
async def business_research_callback(
    task_id: str = Path(..., description="ID of the research task"),
    request: Request = None,
    db: Session = Depends(deps.get_db),
    minio_client: MinioService = Depends(deps.get_minio_client)
) -> JSONResponse:
    """
    Webhook endpoint for business research callbacks from n8n
    
    This endpoint receives research results from n8n and processes them
    to update the research task and compile results if all tasks are completed.
    """
    logger.info(f"BUSINESS RESEARCH CALLBACK received for task: {task_id}")
    
    try:
        # Get and parse request body
        body = await request.body()
        body_str = body.decode('utf-8')
        logger.info(f"Research callback body (first 200 chars): {body_str[:200]}...")
        
        # Parse JSON
        body_json = json.loads(body_str)
        
        # Find the task
        task = db.query(ResearchTask).filter(ResearchTask.id == task_id).first()
        if not task:
            logger.error(f"Task with ID {task_id} not found")
            return JSONResponse(
                status_code=404,
                content={
                    "message": f"Task with ID {task_id} not found",
                    "status": "error",
                    "task_id": task_id
                }
            )
        
        # Extract the business ID from the task
        business_id = task.business_idea_id
        
        # Create the market state of art service
        service = MarketStateOfArtService(
            db_session=db,
            minio_client=minio_client,
            depth=task.depth
        )
        
        # Process the callback data with the service
        result = await service.process_callback_data(task_id, body_json)
        
        # Return success
        return JSONResponse(
            status_code=200,
            content={
                "message": "Research callback processed successfully",
                "task_id": task_id,
                "business_id": business_id,
                "status": "success" if result else "error",
                "processed": result
            }
        )
    except Exception as e:
        logger.error(f"Error processing research callback: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=200,  # Return 200 even on error to prevent n8n retries
            content={
                "message": f"Error processing research callback: {str(e)}",
                "task_id": task_id,
                "status": "error_processing"
            }
        )