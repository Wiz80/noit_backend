import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session
from app.services.business.business_understanding.state_of_art import MarketStateOfArtService
from app.services.storage.minio_service import MinioService
from app.api import deps
from typing import Dict
from app.models.business.business_idea import BusinessIdea
from app.models.business.business_understanding.state_of_art import MarketStateOfArt, StatusEnum, ResearchTask, ResearchTypeEnum
import json

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/business/{business_idea_id}/state-of-art", response_model=Dict)
async def create_state_of_art(
    business_idea_id: str,
    language: str = "es",
    depth: str = "normal",
    force_update: bool = Query(False, description="If True, forces a new analysis even if one already exists"),
    db: Session = Depends(deps.get_db),
    minio_client: MinioService = Depends(deps.get_minio_client)
):
    """
    Generate state of art analysis for a business idea.
    Creates a market research structure, generates questions, and saves results in MinIO.
    
    depth parameter controls how many large requests will be made:
    - very simple: All questions in 1 request
    - simple: Questions split into 2 requests
    - normal: Questions split into 3 requests
    - pro: Questions split into 4 requests
    - deep: Questions split into 6 requests
    """
    logger.info(f"Starting state-of-art analysis for business idea: {business_idea_id}")
    
    try:
        # If force_update is True, reset the state in the database
        if force_update:
            logger.info("Force update requested, resetting state in the database")
            business_understanding = db.query(MarketStateOfArt).filter(
                MarketStateOfArt.business_idea_id == business_idea_id
            ).first()
            
            if business_understanding:
                logger.info("Found existing state of art record, resetting status")
                business_understanding.market_research_status = StatusEnum.PENDING
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
            depth=depth
        )
        
        # Process the business understanding asynchronously
        logger.info("Starting process_business_understanding")
        result = await service.process_business_understanding(
            business_idea_id=business_idea_id,
            force_update=force_update,
            depth=depth
        )
        logger.info("Completed process_business_understanding")
        
        # Return the result with additional information
        output = {
            "business_idea_id": business_idea_id,
            "status": "success",
            "result": result
        }
            
        return output
    
    except Exception as e:
        logger.error(f"Error in state-of-art analysis: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"Error in state-of-art analysis: {str(e)}"
        )

@router.get("/business/{business_idea_id}/research-status", response_model=Dict)
async def get_research_status(
    business_idea_id: str,
    db: Session = Depends(deps.get_db),
    minio_client: MinioService = Depends(deps.get_minio_client)
):
    """
    Get the status of research tasks for a business idea.
    This includes both market research and state of art research tasks.
    """
    logger.info(f"Getting research status for business idea: {business_idea_id}")
    
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
@router.get("/business/{business_idea_id}/state-of-art", response_model=Dict)
async def get_state_of_art(
    business_idea_id: str,
    db: Session = Depends(deps.get_db)
):
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
        
        return state_of_art.to_dict()
    
    except Exception as e:
        logger.error(f"Error in get_state_of_art: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"Error in get_state_of_art: {str(e)}"
        )

#Delete state of art
@router.delete("/business/{business_idea_id}/state-of-art", response_model=Dict)
async def delete_state_of_art(
    business_idea_id: str,
    db: Session = Depends(deps.get_db)
):
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
        
        return {"message": "State of art deleted successfully"}
    
    except Exception as e:
        logger.error(f"Error in delete_state_of_art: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) 
    
#Update state of art
@router.put("/business/{business_idea_id}/state-of-art", response_model=Dict)
async def update_state_of_art(
    business_idea_id: str,
    state_of_art: MarketStateOfArt,
    db: Session = Depends(deps.get_db)
):
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

        # Update the state of art
        state_of_art.market_research_status = state_of_art.market_research_status
        state_of_art.state_of_art_status = state_of_art.state_of_art_status
        db.commit()

        return state_of_art.to_dict()
    
    except Exception as e:
        logger.error(f"Error in update_state_of_art: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) 
    