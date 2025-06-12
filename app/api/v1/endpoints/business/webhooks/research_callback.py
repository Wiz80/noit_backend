from fastapi import APIRouter, HTTPException
import logging
from fastapi import Request
from sqlalchemy.orm import Session
from fastapi import Depends, Path
from app.api import deps
from datetime import datetime
import json
from app.services.storage.minio_service import MinioService
from app.controllers.research_controller import ResearchController
from fastapi.responses import JSONResponse
import re
from app.models.business.competitive_analysis.business_competitor import CompetitorResearch


router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/research-callback/{task_id}")
async def research_callback(
    task_id: str = Path(..., description="ID of the research task or competitor research request"),
    request: Request = None,
    db: Session = Depends(deps.get_db),
    minio_client: MinioService = Depends(deps.get_minio_client)
) -> JSONResponse:
    """
    Unified webhook endpoint for all research callbacks from n8n
    
    This endpoint receives research results from n8n and processes them
    based on the research_type field in the request body. It will route
    the request to the appropriate handler for the specific research type.
    
    The task_id parameter can be either:
    - For state_of_art/market_research: A ResearchTask.id
    - For competitor_analysis: A CompetitorResearch.id
    
    Expected webhook body structure from n8n:
    ```json
    {
      "request_id": "request_id_from_original_task",
      "business_id": "business_id_from_original_request",
      "status": "completed",
      "search_prompt": "original_search_prompt",
      "text": "research_answer_text_content",
      "research_type": "market_research, state_of_art, or competitor_analysis",
      "citations": "",
      "base_url": "callback_url_from_original_request"
    }
    ```
    
    At minimum, the webhook body must contain the "text" field with the research content.
    """
    logger.info(f"RESEARCH CALLBACK received for task: {task_id}")
    
    try:
        # Get and parse request body
        body = await request.body()
        body_str = body.decode('utf-8')
        logger.info(f"Research callback body (first 200 chars): {body_str[:200]}...")
        
        # Parse JSON
        try:
            body_json = json.loads(body_str)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON from callback body: {body_str}")
            return JSONResponse(
                status_code=400,
                content={
                    "message": "Invalid JSON in callback body",
                    "status": "error",
                    "task_id": task_id
                }
            )
        
        # Validate that the required fields exist
        if "text" not in body_json:
            logger.error(f"Missing 'text' field in callback body")
            return JSONResponse(
                status_code=400,
                content={
                    "message": "Missing required 'text' field in callback body",
                    "status": "error",
                    "task_id": task_id
                }
            )
        
        # Check status field
        status = body_json.get("status", "").lower()
        if status != "completed":
            logger.warning(f"Research status is not 'completed': {status}")
            # If not completed, we still proceed but log the warning
        
        # Process citations (might be empty string or array)
        citations = body_json.get("citations", "")
        if isinstance(citations, str) and not citations:
            # If citations is an empty string, convert to empty array
            body_json["citations"] = []
        
        # Create research controller
        research_controller = ResearchController()
        
        # Process the callback with the controller
        result = await research_controller.process_research_callback(
            task_id=task_id,
            body_json=body_json,
            db=db,
            minio_client=minio_client
        )
        
        # Return response based on the result
        if result.get("status") == "error":
            logger.error(f"Error processing research callback: {result.get('message')}")
            return JSONResponse(
                status_code=200,  # Return 200 even on error to prevent n8n retries
                content={
                    "message": result.get("message", "Error processing research callback"),
                    "task_id": task_id,
                    "status": "error_processing"
                }
            )
        else:
            # Return success
            return JSONResponse(
                status_code=200,
                content={
                    "message": "Research callback processed successfully",
                    "task_id": task_id,
                    "business_id": result.get("business_id", "unknown"),
                    "status": "success",
                    "processed": result.get("processed", True)
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

@router.post("/market-research-callback/{task_id}")
async def market_research_callback(
    task_id: str = Path(..., description="ID of the market research task"),
    request: Request = None,
    db: Session = Depends(deps.get_db),
    minio_client: MinioService = Depends(deps.get_minio_client)
) -> JSONResponse:
    """
    Webhook endpoint for market research callbacks from n8n
    
    This endpoint receives market research results from n8n and processes them.
    The task_id parameter is a ResearchTask.id for a market research task.
    
    Expected webhook body structure from n8n:
    ```json
    {
      "request_id": "request_id_from_original_task",
      "business_id": "business_id_from_original_request",
      "status": "completed",
      "search_prompt": "original_search_prompt",
      "text": "research_answer_text_content",
      "research_type": "market_research",
      "citations": "",
      "base_url": "callback_url_from_original_request"
    }
    ```
    
    At minimum, the webhook body must contain the "text" field with the research content.
    """
    logger.info(f"MARKET RESEARCH CALLBACK received for task: {task_id}")
    
    try:
        # Get and parse request body
        body = await request.body()
        body_str = body.decode('utf-8')
        logger.info(f"Market research callback body (first 200 chars): {body_str[:200]}...")
        
        # Parse JSON
        try:
            body_json = json.loads(body_str)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON from callback body: {body_str}")
            return JSONResponse(
                status_code=400,
                content={
                    "message": "Invalid JSON in callback body",
                    "status": "error",
                    "task_id": task_id
                }
            )
        
        # Validate that the required fields exist
        if "text" not in body_json:
            logger.error(f"Missing 'text' field in callback body")
            return JSONResponse(
                status_code=400,
                content={
                    "message": "Missing required 'text' field in callback body",
                    "status": "error",
                    "task_id": task_id
                }
            )
        
        # Ensure research_type is market_research
        body_json["research_type"] = "market_research"
        
        # Process citations (might be empty string or array)
        citations = body_json.get("citations", "")
        if isinstance(citations, str) and not citations:
            # If citations is an empty string, convert to empty array
            body_json["citations"] = []
        
        # Create research controller
        research_controller = ResearchController()
        
        # Process the callback with the controller
        result = await research_controller.process_research_callback(
            task_id=task_id,
            body_json=body_json,
            db=db,
            minio_client=minio_client
        )
        
        # Return response based on the result
        if result.get("status") == "error":
            logger.error(f"Error processing market research callback: {result.get('message')}")
            return JSONResponse(
                status_code=200,  # Return 200 even on error to prevent n8n retries
                content={
                    "message": result.get("message", "Error processing market research callback"),
                    "task_id": task_id,
                    "status": "error_processing"
                }
            )
        else:
            # Return success
            return JSONResponse(
                status_code=200,
                content={
                    "message": "Market research callback processed successfully",
                    "task_id": task_id,
                    "business_id": result.get("business_id", "unknown"),
                    "status": "success",
                    "processed": result.get("processed", True)
                }
            )
    except Exception as e:
        logger.error(f"Error processing market research callback: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=200,  # Return 200 even on error to prevent n8n retries
            content={
                "message": f"Error processing market research callback: {str(e)}",
                "task_id": task_id,
                "status": "error_processing"
            }
        )

@router.post("/state-of-art-callback/{task_id}")
async def state_of_art_callback(
    task_id: str = Path(..., description="ID of the state of art research task"),
    request: Request = None,
    db: Session = Depends(deps.get_db),
    minio_client: MinioService = Depends(deps.get_minio_client)
) -> JSONResponse:
    """
    Webhook endpoint for state of art research callbacks from n8n
    
    This endpoint receives state of art research results from n8n and processes them.
    The task_id parameter is a ResearchTask.id for a state of art research task.
    
    Expected webhook body structure from n8n:
    ```json
    {
      "request_id": "request_id_from_original_task",
      "business_id": "business_id_from_original_request",
      "status": "completed",
      "search_prompt": "original_search_prompt",
      "text": "research_answer_text_content",
      "research_type": "state_of_art",
      "citations": "",
      "base_url": "callback_url_from_original_request"
    }
    ```
    
    At minimum, the webhook body must contain the "text" field with the research content.
    """
    logger.info(f"STATE OF ART CALLBACK received for task: {task_id}")
    
    try:
        # Get and parse request body
        body = await request.body()
        body_str = body.decode('utf-8')
        logger.info(f"State of art callback body (first 200 chars): {body_str[:200]}...")
        
        # Parse JSON
        try:
            body_json = json.loads(body_str)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON from callback body: {body_str}")
            return JSONResponse(
                status_code=400,
                content={
                    "message": "Invalid JSON in callback body",
                    "status": "error",
                    "task_id": task_id
                }
            )
        
        # Validate that the required fields exist
        if "text" not in body_json:
            logger.error(f"Missing 'text' field in callback body")
            return JSONResponse(
                status_code=400,
                content={
                    "message": "Missing required 'text' field in callback body",
                    "status": "error",
                    "task_id": task_id
                }
            )
        
        # Ensure research_type is state_of_art
        body_json["research_type"] = "state_of_art"
        
        # Process citations (might be empty string or array)
        citations = body_json.get("citations", "")
        if isinstance(citations, str) and not citations:
            # If citations is an empty string, convert to empty array
            body_json["citations"] = []
        
        # Create research controller
        research_controller = ResearchController()
        
        # Process the callback with the controller
        result = await research_controller.process_research_callback(
            task_id=task_id,
            body_json=body_json,
            db=db,
            minio_client=minio_client
        )
        
        # Return response based on the result
        if result.get("status") == "error":
            logger.error(f"Error processing state of art callback: {result.get('message')}")
            return JSONResponse(
                status_code=200,  # Return 200 even on error to prevent n8n retries
                content={
                    "message": result.get("message", "Error processing state of art callback"),
                    "task_id": task_id,
                    "status": "error_processing"
                }
            )
        else:
            # Return success
            return JSONResponse(
                status_code=200,
                content={
                    "message": "State of art callback processed successfully",
                    "task_id": task_id,
                    "business_id": result.get("business_id", "unknown"),
                    "status": "success",
                    "processed": result.get("processed", True)
                }
            )
    except Exception as e:
        logger.error(f"Error processing state of art callback: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=200,  # Return 200 even on error to prevent n8n retries
            content={
                "message": f"Error processing state of art callback: {str(e)}",
                "task_id": task_id,
                "status": "error_processing"
            }
        )

@router.post("/competitor-analysis-callback/{request_id}")
async def competitor_analysis_callback(
    request_id: str = Path(..., description="ID of the competitor research request"),
    request: Request = None,
    db: Session = Depends(deps.get_db),
) -> JSONResponse:
    """
    Dedicated webhook endpoint for competitor analysis callbacks.
    """
    logger.info(f"COMPETITOR ANALYSIS CALLBACK received for request: {request_id}")
    
    try:
        body = await request.body()
        body_str = body.decode('utf-8')
        logger.info(f"Competitor analysis callback body (first 500 chars): {body_str[:500]}...")
        
        try:
            body_json = json.loads(body_str)
        except json.JSONDecodeError:
            # If direct parsing fails, try to find JSON within markdown
            match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', body_str, re.DOTALL)
            if match:
                logger.info("Found JSON block wrapped in markdown in callback body.")
                json_str = match.group(1)
                body_json = json.loads(json_str)
            else:
                logger.error(f"Failed to parse JSON from callback body: {body_str}")
                return JSONResponse(status_code=400, content={"message": "Invalid JSON in callback body"})

        # Manually add business_id and request_id if they are not in the main body
        if "request_id" not in body_json:
            body_json["request_id"] = request_id
        
        # The controller expects the business_id, so we fetch it from the research record
        research = db.query(CompetitorResearch).filter(CompetitorResearch.id == request_id).first()
        if research and "business_id" not in body_json:
            body_json["business_id"] = research.business_id

        # Instantiate the controller and process the data
        from app.controllers.competitive_analysis.webhook_controller import WebhookController
        webhook_controller = WebhookController()
        
        await webhook_controller.process_competitor_data(
            body_json=body_json,
            db=db
        )
        
        return JSONResponse(
            status_code=200,
            content={
                "message": "Competitor analysis callback processed successfully.",
                "request_id": request_id,
                "status": "success"
            }
        )

    except Exception as e:
        logger.error(f"Error processing competitor analysis callback: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "message": f"Internal server error: {str(e)}",
                "request_id": request_id
            }
        ) 