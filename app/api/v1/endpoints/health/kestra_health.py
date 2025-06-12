from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
import httpx
import logging
from app.core.config import settings
import os

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/kestra")
async def check_kestra_health():
    """
    Health check endpoint to verify Kestra connectivity and webhook availability.
    """
    kestra_base_url = settings.KESTRA_URL.rstrip('/')
    
    # Test basic connectivity to Kestra
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Test basic Kestra health
            health_url = f"{kestra_base_url}/health"
            health_response = await client.get(health_url)
            
            kestra_status = "healthy" if health_response.status_code == 200 else "unhealthy"
            
            # Test webhook endpoints
            webhooks_status = {}
            
            # Test competitor analysis webhook
            competitor_webhook_key = settings.KESTRA_COMPETITOR_ANALYSIS_KEY
            competitor_webhook_url = f"{kestra_base_url}/api/v1/executions/webhook/noit.backend/start-competitor-analysis/{competitor_webhook_key}"
            try:
                webhook_response = await client.get(competitor_webhook_url)
                webhooks_status["competitor_analysis"] = {
                    "url": competitor_webhook_url,
                    "status": webhook_response.status_code,
                    "available": webhook_response.status_code != 404
                }
            except Exception as e:
                webhooks_status["competitor_analysis"] = {
                    "url": competitor_webhook_url,
                    "error": str(e),
                    "available": False
                }
            
            # Test social media extraction webhook
            social_webhook_key = settings.KESTRA_SOCIAL_MEDIA_SCRAPER_KEY
            social_webhook_url = f"{kestra_base_url}/api/v1/executions/webhook/noit.backend/social-media-extraction-trigger/{social_webhook_key}"
            try:
                social_response = await client.get(social_webhook_url)
                webhooks_status["social_media_extraction"] = {
                    "url": social_webhook_url,
                    "status": social_response.status_code,
                    "available": social_response.status_code != 404
                }
            except Exception as e:
                webhooks_status["social_media_extraction"] = {
                    "url": social_webhook_url,
                    "error": str(e),
                    "available": False
                }
            
            # Test Instagram analysis webhook
            instagram_webhook_key = settings.KESTRA_INSTAGRAM_ANALYSIS_KEY
            instagram_webhook_url = f"{kestra_base_url}/api/v1/executions/webhook/noit.backend/instagram-competitor-full-analysis/{instagram_webhook_key}"
            try:
                instagram_response = await client.get(instagram_webhook_url)
                webhooks_status["instagram_analysis"] = {
                    "url": instagram_webhook_url,
                    "status": instagram_response.status_code,
                    "available": instagram_response.status_code != 404
                }
            except Exception as e:
                webhooks_status["instagram_analysis"] = {
                    "url": instagram_webhook_url,
                    "error": str(e),
                    "available": False
                }
            
            return JSONResponse(
                status_code=200,
                content={
                    "kestra_base_url": kestra_base_url,
                    "kestra_health": kestra_status,
                    "kestra_response_code": health_response.status_code,
                    "webhooks": webhooks_status,
                    "message": "Kestra connectivity check completed"
                }
            )
            
    except httpx.ConnectError as e:
        logger.error(f"Failed to connect to Kestra at {kestra_base_url}: {str(e)}")
        return JSONResponse(
            status_code=503,
            content={
                "kestra_base_url": kestra_base_url,
                "error": "Cannot connect to Kestra",
                "details": str(e),
                "suggestion": "Check if Kestra service is running and accessible"
            }
        )
    except Exception as e:
        logger.error(f"Unexpected error checking Kestra health: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "kestra_base_url": kestra_base_url,
                "error": "Unexpected error checking Kestra health",
                "details": str(e)
            }
        ) 