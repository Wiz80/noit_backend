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

from app.models.business.business_idea import BusinessIdea
from app.models.business.business_understanding.state_of_art import ResearchTask
from app.services.business.competitive_analysis.business_competitors_extraction import EnhancedBusinessAnalyzer, BusinessModel
from app.services.business.business_understanding.state_of_art import MarketStateOfArtService
import app.prompts.business.prompts_business_competitors as prompts
from fastapi.responses import JSONResponse
#background tasks
from fastapi import BackgroundTasks
from app.utils.decode_json import clean_json_encoding
from app.controllers.competitive_analysis.webhook_controller import WebhookController

# Configurar logger
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/callback")
async def handle_callback():
    """
    Endpoint básico para manejar callbacks.
    """
    return {"status": "received"} 

@router.post("/receive-webhook")
async def receive_webhook(
    request: Request
) -> JSONResponse:
    """
    Simple endpoint to receive any webhook data
    """
    logger.info("WEBHOOK ENDPOINT WAS CALLED")
    
    try:
        # Get request body
        body = await request.body()
        body_str = body.decode('utf-8')
        logger.info(f"Webhook received body: {body_str}")
        
        # Try to parse JSON
        try:
            body_json = json.loads(body_str)
            data = body_json
        except:
            data = {"raw": body_str}
        
        # Return success with content
        return JSONResponse(
            status_code=200,
            content={
                "message": "Webhook received successfully",
                "timestamp": datetime.now().isoformat(),
                "data": data
            }
        )
    except Exception as e:
        logger.error(f"Error in webhook: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "message": f"Error processing webhook: {str(e)}"
            }
        )