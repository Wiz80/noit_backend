from sqlalchemy.orm import Session
import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional
from dotenv import load_dotenv
import httpx

from app.models.business.business_understanding.state_of_art import ResearchTask, StatusEnum, ResearchTypeEnum, MarketStateOfArt
from app.models.business.business_idea import BusinessIdea
from app.models.business.competitive_analysis.business_competitor import CompetitorResearch
from app.services.storage.minio_service import MinioService
from app.api import deps
from app.controllers.business_understanding.state_of_art import StateOfArtController
from app.core.config import settings

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ResearchController:
    """
    Controller for processing research callbacks.
    Handles different types of research responses based on research_type.
    """
    
    def __init__(self):
        """
        Initialize the research controller.
        """
        # Initialize state of art controller for handling specific research types
        self.state_of_art_controller = StateOfArtController()
    
    async def process_research_callback(
        self,
        task_id: str,
        body_json: Dict[str, Any],
        db: Session,
        minio_client: Optional[MinioService] = None
    ) -> Dict[str, Any]:
        """
        Process a research callback based on its research_type
        
        Args:
            task_id: ID of the research task or request
            body_json: JSON data from the webhook request, with this structure:
                {
                    "request_id": "original_request_id",
                    "business_id": "business_id",
                    "status": "completed",
                    "search_prompt": "original_search_prompt",
                    "text": "research_result_text",
                    "research_type": "market_research, state_of_art, or competitor_analysis",
                    "citations": "", # Empty string, will be converted to []
                    "base_url": "callback_url"
                }
            db: Database session
            minio_client: MinIO client (optional)
            
        Returns:
            Dict with processing result information
        """
        logger.info(f"Processing research callback for task/request: {task_id}")
        
        # Extract key fields
        research_type = body_json.get("research_type", "unknown")
        business_id = body_json.get("business_id", "unknown")
        search_prompt = body_json.get("search_prompt", "")
        text = body_json.get("text", "")
        request_id = body_json.get("request_id", "")
        
        logger.info(f"Research type: {research_type}, Business ID: {business_id}")
        logger.info(f"Request ID: {request_id}")
        logger.info(f"Search prompt length: {len(search_prompt)}")
        logger.info(f"Result text length: {len(text)}")
        
        try:
            # Initialize MinIO client if not provided
            if minio_client is None:
                minio_client = MinioService(bucket_name=settings.MINIO_BUCKET_NAME)
            
            # Route based on research type first
            if research_type in ["market_research", "state_of_art"]:
                # For state of art research, find the task in ResearchTask model
                task = db.query(ResearchTask).filter(ResearchTask.id == task_id).first()
                
                if not task:
                    logger.error(f"ResearchTask with ID {task_id} not found")
                    return {
                        "status": "error",
                        "message": f"ResearchTask with ID {task_id} not found"
                    }
                
                # Process state of art or market research
                logger.info(f"Processing business understanding research for task: {task_id}")
                if research_type == "state_of_art":
                    return await self.state_of_art_controller.process_state_of_art_research(task, body_json, db, minio_client)
                elif research_type == "market_research":
                    return await self.state_of_art_controller.process_market_research(task, body_json, db, minio_client)
                
            elif research_type == "competitor_analysis":
                # For competitor analysis, we don't need to validate against ResearchTask
                # Instead, the webhook_controller will handle the CompetitorResearch model
                logger.info(f"Processing competitor analysis research for request: {task_id}")
                
                # Import here to avoid circular imports
                from app.controllers.competitive_analysis.webhook_controller import WebhookController
                
                # Clone and prepare the body_json for the webhook controller
                competitor_json = body_json.copy()
                
                # Ensure competitors field exists, using text field if not present
                if "competitors" not in competitor_json and "text" in competitor_json:
                    competitor_json["competitors"] = competitor_json.get("text", "")
                
                # Create webhook controller for competitor analysis
                webhook_controller = WebhookController()
                
                # Process the competitor data directly with the dedicated controller
                await webhook_controller.process_competitor_data(
                    body_json=competitor_json,
                    db=db
                )
                
                # After successfully processing competitor data, trigger Kestra workflow
                try:
                    await self._trigger_kestra_social_media_extraction(business_id, task_id)
                    logger.info(f"Successfully triggered Kestra social media extraction workflow for business: {business_id}")
                except Exception as kestra_error:
                    logger.error(f"Failed to trigger Kestra workflow: {str(kestra_error)}", exc_info=True)
                    # Don't fail the whole process if Kestra call fails, just log the error
                
                return {
                    "status": "success",
                    "message": "Competitor analysis data processed and Kestra workflow triggered",
                    "request_id": task_id,
                    "business_id": business_id
                }
                
            else:
                # Unknown research type
                logger.error(f"Unknown research type: {research_type}")
                return {
                    "status": "error",
                    "message": f"Unknown research type: {research_type}"
                }
                
        except Exception as e:
            logger.error(f"Error processing research callback: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "message": f"Error processing research callback: {str(e)}"
            }
    
    async def _trigger_kestra_social_media_extraction(self, business_id: str, request_id: str) -> None:
        """
        Trigger Kestra social media extraction workflow after competitor analysis completion
        
        Args:
            business_id: ID of the business that completed competitor analysis
            request_id: ID of the original competitor analysis request
        """
        logger.info(f"Triggering Kestra social media extraction workflow for business: {business_id}")
        
        # Prepare webhook payload
        webhook_payload = {
            "event": "business_model_completed",  # Required by Kestra workflow condition
            "business_id": business_id,
            "triggered_by": "competitor_analysis_completion",
            "original_request_id": request_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Construct Kestra webhook URL
        kestra_base_url = settings.KESTRA_URL.rstrip('/')
        webhook_key = "competitor_analysis_trigger"  # Key from the Kestra workflow
        webhook_url = f"{kestra_base_url}/api/v1/executions/webhook/noit.backend/start-competitor-analysis/{webhook_key}"
        
        logger.info(f"Calling Kestra webhook: {webhook_url}")
        logger.info(f"Payload: {json.dumps(webhook_payload, indent=2)}")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    webhook_url,
                    json=webhook_payload,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "NoitBackend-ResearchController/1.0"
                    }
                )
                
                logger.info(f"Kestra webhook response status: {response.status_code}")
                logger.info(f"Kestra webhook response body: {response.text}")
                
                if response.status_code in [200, 201, 202]:
                    logger.info("✅ Kestra social media extraction workflow triggered successfully")
                else:
                    logger.error(f"❌ Kestra webhook call failed with status {response.status_code}: {response.text}")
                    raise Exception(f"Kestra webhook failed with status {response.status_code}")
                    
        except httpx.TimeoutException:
            logger.error("⏰ Timeout calling Kestra webhook")
            raise Exception("Timeout calling Kestra webhook")
        except Exception as e:
            logger.error(f"💥 Error calling Kestra webhook: {str(e)}")
            raise