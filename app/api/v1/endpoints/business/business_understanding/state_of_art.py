import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session
from app.services.business.business_understanding.state_of_art import MarketStateOfArtService
from app.services.storage.minio_service import MinioService
from app.api import deps
from typing import Dict, Optional
from app.models.business.business_idea import BusinessIdea
from app.models.business.business_understanding.state_of_art import MarketStateOfArt, StatusEnum, ResearchTask, ResearchTypeEnum
import json
from pydantic import BaseModel, Field
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()

class StateOfArtRequest(BaseModel):
    language: str = Field(default="es", description="Language for the state of art analysis")
    depth: str = Field(default="normal", description="Depth of analysis: very simple, simple, normal, pro, deep")
    model: str = Field(default="sonar", description="Perplexity model to use: sonar, sonar-pro, sonar-deep-research, sonar-reasoning-pro, sonar-reasoning")
    base_url: Optional[str] = Field(None, description="Base URL for webhook callbacks (without redirects)")
    force_update: bool = Field(default=False, description="If True, forces a new analysis even if one already exists")

    model_config = {
        "json_schema_extra": {
            "example": {
                "language": "es",
                "depth": "normal",
                "model": "sonar",
                "base_url": "https://example.com",
                "force_update": False
            }
        }
    }

class StateOfArtUpdateRequest(BaseModel):
    market_research_status: StatusEnum = Field(..., description="Status of market research")
    state_of_art_status: StatusEnum = Field(..., description="Status of state of art research")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "market_research_status": "COMPLETED",
                "state_of_art_status": "COMPLETED"
            }
        }
    }

@router.post("/{business_idea_id}/market-research", response_model=Dict)
async def create_market_research(
    business_idea_id: str = Path(..., description="ID of the business idea"),
    request: StateOfArtRequest = None,
    db: Session = Depends(deps.get_db),
    minio_client: MinioService = Depends(deps.get_minio_client),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Generate market research analysis for a business idea.
    Creates a market research structure, generates questions, and saves results in MinIO.
    
    Request body parameters:
    - language: Language for the analysis (default: "es")
    - depth: Controls how many large requests will be made
    - model: Determines which Perplexity model to use
    - base_url: Specifies the base URL for webhook callbacks
    - force_update: If True, forces a new analysis even if one already exists
    
    Requires authentication with a valid JWT token.
    """
    # Use empty request if none provided
    if request is None:
        request = StateOfArtRequest()
        
    language = request.language
    depth = request.depth
    model = request.model
    base_url = request.base_url
    force_update = request.force_update
    
    logger.info(f"Starting market research analysis for business idea: {business_idea_id}")
    logger.info(f"Using model: {model}, depth: {depth}, language: {language}")
    logger.info(f"Request initiated by user: {current_user.id}")
    
    # Validate model parameter
    valid_models = ["sonar", "sonar-pro", "sonar-deep-research", "sonar-reasoning-pro", "sonar-reasoning"]
    if model not in valid_models:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid model parameter. Must be one of: {', '.join(valid_models)}"
        )
    
    # Set base URL for callbacks if provided
    if base_url:
        logger.info(f"Using custom base URL for webhooks: {base_url}")
        # Set environment variable temporarily for this request
        import os
        os.environ["API_CALLBACK_BASE_URL"] = base_url
    
    try:
        # If force_update is True, reset the state in the database
        if force_update:
            logger.info("Force update requested, resetting state in the database")
            business_understanding = db.query(MarketStateOfArt).filter(
                MarketStateOfArt.business_idea_id == business_idea_id
            ).first()
            
            if business_understanding:
                logger.info("Found existing market research record, resetting status")
                business_understanding.market_research_status = StatusEnum.PENDING
                business_understanding.error_message = None
                db.commit()
                logger.info("Reset status in database")
            else:
                logger.info("No existing market research record found, will create a new one")
        
        # Initialize the service with the database session and MinIO client
        logger.info("Initializing MarketStateOfArtService")
        service = MarketStateOfArtService(
            db_session=db, 
            minio_client=minio_client,
            language=language,
            depth=depth,
            model=model,
            base_url=base_url
        )
        
        # Process the market research asynchronously
        logger.info("Starting process_market_research")
        result = await service.process_market_research(
            business_idea_id=business_idea_id,
            force_update=force_update,
            depth=depth,
            model=model
        )
        logger.info("Completed process_market_research")
        
        # Return the result with additional information
        output = {
            "business_idea_id": business_idea_id,
            "status": "success",
            "model": model,
            "depth": depth,
            "language": language,
            "user_id": current_user.id,
            "result": result
        }
            
        return output
    
    except Exception as e:
        logger.error(f"Error in market research analysis: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"Error in market research analysis: {str(e)}"
        )

@router.post("/{business_idea_id}/state-of-art-research", response_model=Dict)
async def create_state_of_art_research(
    business_idea_id: str = Path(..., description="ID of the business idea"),
    request: StateOfArtRequest = None,
    db: Session = Depends(deps.get_db),
    minio_client: MinioService = Depends(deps.get_minio_client),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Generate state of art research analysis for a business idea.
    Creates a state of art research structure, generates questions, and saves results in MinIO.
    
    Request body parameters:
    - language: Language for the analysis (default: "es")
    - depth: Controls how many large requests will be made
    - model: Determines which Perplexity model to use
    - base_url: Specifies the base URL for webhook callbacks
    - force_update: If True, forces a new analysis even if one already exists
    
    Requires authentication with a valid JWT token.
    """
    # Use empty request if none provided
    if request is None:
        request = StateOfArtRequest()
        
    language = request.language
    depth = request.depth
    model = request.model
    base_url = request.base_url
    force_update = request.force_update
    
    logger.info(f"Starting state of art research analysis for business idea: {business_idea_id}")
    logger.info(f"Using model: {model}, depth: {depth}, language: {language}")
    logger.info(f"Request initiated by user: {current_user.id}")
    
    # Validate model parameter
    valid_models = ["sonar", "sonar-pro", "sonar-deep-research", "sonar-reasoning-pro", "sonar-reasoning"]
    if model not in valid_models:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid model parameter. Must be one of: {', '.join(valid_models)}"
        )
    
    # Set base URL for callbacks if provided
    if base_url:
        logger.info(f"Using custom base URL for webhooks: {base_url}")
        # Set environment variable temporarily for this request
        import os
        os.environ["API_CALLBACK_BASE_URL"] = base_url
    
    try:
        # If force_update is True, reset the state in the database
        if force_update:
            logger.info("Force update requested, resetting state in the database")
            business_understanding = db.query(MarketStateOfArt).filter(
                MarketStateOfArt.business_idea_id == business_idea_id
            ).first()
            
            if business_understanding:
                logger.info("Found existing state of art record, resetting status")
                business_understanding.state_of_art_status = StatusEnum.PENDING
                business_understanding.error_message = None
                db.commit()
                logger.info("Reset status in database")
            else:
                logger.info("No existing state of art record found, will create a new one")
        
        # Initialize the service with the database session and MinIO client
        logger.info("Initializing MarketStateOfArtService")
        service = MarketStateOfArtService(
            db_session=db, 
            minio_client=minio_client,
            language=language,
            depth=depth,
            model=model,
            base_url=base_url
        )
        
        # Process the state of art research asynchronously
        logger.info("Starting process_state_of_art")
        result = await service.process_state_of_art(
            business_idea_id=business_idea_id,
            force_update=force_update,
            depth=depth,
            model=model
        )
        logger.info("Completed process_state_of_art")
        
        # Return the result with additional information
        output = {
            "business_idea_id": business_idea_id,
            "status": "success",
            "model": model,
            "depth": depth,
            "language": language,
            "user_id": current_user.id,
            "result": result
        }
            
        return output
    
    except Exception as e:
        logger.error(f"Error in state of art research analysis: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"Error in state of art research analysis: {str(e)}"
        )

@router.get("/{business_idea_id}/research-status", response_model=Dict)
async def get_research_status(
    business_idea_id: str,
    db: Session = Depends(deps.get_db),
    minio_client: MinioService = Depends(deps.get_minio_client),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Get the status of research tasks for a business idea.
    This includes both market research and state of art research tasks.
    
    Requires authentication with a valid JWT token.
    """
    logger.info(f"Getting research status for business idea: {business_idea_id}")
    logger.info(f"Request initiated by user: {current_user.id}")
    
    try:
        # Get business understanding record
        business_understanding = db.query(MarketStateOfArt).filter(
            MarketStateOfArt.business_idea_id == business_idea_id
        ).first()
        
        if not business_understanding:
            raise HTTPException(
                status_code=404,
                detail=f"No business understanding record found for business idea: {business_idea_id}"
            )
        
        # Get all research tasks for this business understanding
        market_research_tasks = db.query(ResearchTask).filter(
            ResearchTask.business_understanding_id == business_understanding.id,
            ResearchTask.research_type == ResearchTypeEnum.MARKET_RESEARCH
        ).all()
        
        state_of_art_tasks = db.query(ResearchTask).filter(
            ResearchTask.business_understanding_id == business_understanding.id,
            ResearchTask.research_type == ResearchTypeEnum.STATE_OF_ART
        ).all()
        
        # Calculate progress for market research
        market_research_total = len(market_research_tasks)
        market_research_completed = sum(1 for task in market_research_tasks if task.status == StatusEnum.COMPLETED)
        market_research_progress = round((market_research_completed / market_research_total * 100) if market_research_total > 0 else 0)
        
        # Calculate progress for state of art
        state_of_art_total = len(state_of_art_tasks)
        state_of_art_completed = sum(1 for task in state_of_art_tasks if task.status == StatusEnum.COMPLETED)
        state_of_art_progress = round((state_of_art_completed / state_of_art_total * 100) if state_of_art_total > 0 else 0)
        
        # Get the status of each task
        market_research_task_status = [{
            "id": task.id,
            "status": task.status,
            "chunk_index": task.chunk_index,
            "questions_count": len(task.get_questions()) if task.questions else 0,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "error_message": task.error_message
        } for task in market_research_tasks]
        
        state_of_art_task_status = [{
            "id": task.id,
            "status": task.status,
            "chunk_index": task.chunk_index,
            "questions_count": len(task.get_questions()) if task.questions else 0,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "error_message": task.error_message
        } for task in state_of_art_tasks]
        
        # Prepare response
        result = {
            "business_idea_id": business_idea_id,
            "business_understanding_id": business_understanding.id,
            "user_id": current_user.id,
            "market_research": {
                "status": business_understanding.market_research_status,
                "progress": market_research_progress,
                "total_tasks": market_research_total,
                "completed_tasks": market_research_completed,
                "tasks": market_research_task_status,
                "path": business_understanding.market_research_path
            },
            "state_of_art": {
                "status": business_understanding.state_of_art_status,
                "progress": state_of_art_progress,
                "total_tasks": state_of_art_total,
                "completed_tasks": state_of_art_completed,
                "tasks": state_of_art_task_status,
                "path": business_understanding.state_of_art_path
            }
        }
        
        return result
    
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error getting research status: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error getting research status: {str(e)}"
        )

#get state of art
@router.get("/{business_idea_id}/state-of-art", response_model=Dict)
async def get_state_of_art(
    business_idea_id: str,
    db: Session = Depends(deps.get_db),
    minio_client: MinioService = Depends(deps.get_minio_client),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Get the state of art analysis for a business idea.
    Retrieves the state of art JSON data from MinIO storage.
    
    Requires authentication with a valid JWT token.
    """
    logger.info(f"Getting state of art for business idea: {business_idea_id}")
    logger.info(f"Request initiated by user: {current_user.id}")
    
    try:
        # Get the business idea
        business_idea = db.query(BusinessIdea).filter(
            BusinessIdea.id == business_idea_id
        ).first()
        
        if not business_idea:
            raise HTTPException(status_code=404, detail="Business idea not found")
        
        # Get the state of art record
        state_of_art = db.query(MarketStateOfArt).filter(
            MarketStateOfArt.business_idea_id == business_idea_id
        ).first()
        
        if not state_of_art:
            raise HTTPException(status_code=404, detail="State of art not found")
        
        # Get the path to the state of art file in MinIO
        state_of_art_path = state_of_art.state_of_art_path
        
        if not state_of_art_path:
            logger.warning(f"State of art path is empty for business idea: {business_idea_id}")
            raise HTTPException(status_code=404, detail="State of art file not found in storage")
        
        # Retrieve the state of art data from MinIO
        logger.info(f"Retrieving state of art data from MinIO path: {state_of_art_path}")
        state_of_art_data = minio_client.get_object_data(state_of_art_path)
        
        if not state_of_art_data:
            logger.error(f"Failed to retrieve state of art data from MinIO: {state_of_art_path}")
            raise HTTPException(status_code=404, detail="State of art data not found in storage")
        
        # Parse the JSON data
        try:
            state_of_art_json = json.loads(state_of_art_data.decode('utf-8'))
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing state of art JSON data: {str(e)}")
            raise HTTPException(status_code=500, detail="Error parsing state of art data")
        
        # Prepare the response
        result = {
            "business_idea_id": business_idea_id,
            "user_id": current_user.id,
            "state_of_art_status": state_of_art.state_of_art_status,
            "data": state_of_art_json
        }
        
        return result
    
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error in get_state_of_art: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"Error in get_state_of_art: {str(e)}"
        )

#Delete state of art
@router.delete("/{business_idea_id}/state-of-art", response_model=Dict)
async def delete_state_of_art(
    business_idea_id: str,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Delete the state of art analysis for a business idea.
    
    Requires authentication with a valid JWT token.
    """
    logger.info(f"Deleting state of art for business idea: {business_idea_id}")
    logger.info(f"Request initiated by user: {current_user.id}")
    
    try:
        # Get the business idea
        business_idea = db.query(BusinessIdea).filter(
            BusinessIdea.id == business_idea_id
        ).first()
        
        if not business_idea:
            raise HTTPException(status_code=404, detail="Business idea not found")
        
        # Get the state of art
        state_of_art = db.query(MarketStateOfArt).filter(
            MarketStateOfArt.business_idea_id == business_idea_id
        ).first()
        
        if not state_of_art:
            raise HTTPException(status_code=404, detail="State of art not found")
        
        db.delete(state_of_art)
        db.commit()
        
        return {
            "message": "State of art deleted successfully",
            "business_idea_id": business_idea_id,
            "user_id": current_user.id
        }
    
    except Exception as e:
        logger.error(f"Error in delete_state_of_art: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) 
    
#Update state of art
@router.put("/{business_idea_id}/state-of-art", response_model=Dict)
async def update_state_of_art(
    business_idea_id: str,
    update_data: StateOfArtUpdateRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Update the state of art analysis for a business idea.
    
    Requires authentication with a valid JWT token.
    """
    logger.info(f"Updating state of art for business idea: {business_idea_id}")
    logger.info(f"Request initiated by user: {current_user.id}")
    
    try:
        # Get the business idea
        business_idea = db.query(BusinessIdea).filter(
            BusinessIdea.id == business_idea_id
        ).first()

        if not business_idea:
            raise HTTPException(status_code=404, detail="Business idea not found")

        # Get the state of art
        existing_state_of_art = db.query(MarketStateOfArt).filter(
            MarketStateOfArt.business_idea_id == business_idea_id
        ).first()

        if not existing_state_of_art:
            raise HTTPException(status_code=404, detail="State of art not found")

        # Update the state of art using the Pydantic model data
        existing_state_of_art.market_research_status = update_data.market_research_status
        existing_state_of_art.state_of_art_status = update_data.state_of_art_status
        db.commit()

        result = existing_state_of_art.to_dict()
        result["user_id"] = current_user.id
        
        return result
    
    except Exception as e:
        logger.error(f"Error in update_state_of_art: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) 
    