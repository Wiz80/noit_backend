from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
import logging
from fastapi import Request
from sqlalchemy.orm import Session
from app.api import deps
from app.models.business.competitive_analysis.business_competitor import CompetitorResearch, CompetitorResearchStatus
from datetime import datetime
import json
from app.services.storage.minio_service import MinioService
from app.models.business.business_understanding.state_of_art import ResearchTask
from app.services.business.business_understanding.state_of_art import MarketStateOfArtService
from fastapi.responses import JSONResponse
from app.controllers.competitive_analysis.webhook_controller import WebhookController   

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/competitor-research")
async def competitor_research_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(deps.get_db)
) -> JSONResponse:
    """
    Webhook endpoint for competitor research results
    """
    logger.info("COMPETITOR RESEARCH WEBHOOK CALLED")
    
    try:
        # Get request body
        body = await request.body()
        body_str = body.decode('utf-8')
        logger.info(f"Webhook received body: {body_str}")
        
        # Parse JSON
        body_json = json.loads(body_str)
        
        # Extract key fields
        request_id = body_json.get("request_id", "missing")
        business_id = body_json.get("business_id", "missing")
        status = body_json.get("status", "missing")
        
        logger.info(f"Received webhook - request_id: {request_id}, business_id: {business_id}, status: {status}")
        
        # Use the webhook controller to process data in the background
        controller = WebhookController()
        logger.info(f"Using WebhookController to process competitor data for business_id {business_id}")
        # background_tasks.add_task(
        #     controller.process_competitor_data,
        #     body_json=body_json,
        #     db=db
        # )
        
        await controller.process_competitor_data(
            body_json=body_json,
            db=db
        )


        # Return success immediately
        return JSONResponse(
            status_code=200,
            content={
                "message": "Webhook received successfully, processing in background",
                "request_id": request_id,
                "business_id": business_id,
                "status": "processing"
            }
        )
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return JSONResponse(
            status_code=200,  # Return 200 even on error to prevent n8n retries
            content={
                "message": f"Error receiving webhook: {str(e)}",
                "status": "error_receiving"
            }
        )