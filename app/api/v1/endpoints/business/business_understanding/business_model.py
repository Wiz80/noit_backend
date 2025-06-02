from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session
from typing import Dict, Optional
import logging
import json
import os
from datetime import datetime

from app.api import deps
from app.services.business.business_understanding.business_model_module import ValidatorConfig, BusinessValidator
from app.services.storage.minio_service import MinioService
from app.services.cache.redis_service import RedisChatService
from app.services.business.business_understanding.business_model_chat_service import BusinessModelChatService

from app.schemas.business.business_model import (
    BusinessModelMessageRequest, 
    BusinessModelMessageResponse,
    BusinessModelSessionInfo,
    BusinessModelSessionListResponse,
    BusinessModelReportResponse,
    BusinessModelResponse
)

from app.models.business.business_understanding.business_model import BusinessValidation, ValidationStatus, BusinessModel
from app.models.business.business_idea import BusinessIdea
from app.models.user import User

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()
@router.get("/business/{business_id}/sessions", response_model=BusinessModelSessionListResponse)
async def list_business_model_sessions(
    business_id: str = Path(..., description="ID del negocio"),
    redis_service: RedisChatService = Depends(deps.get_redis_service),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    List all business model chat sessions for a business.
    Requires authentication and verifies that the business_id exists and belongs to the user.
    """
    try:
        # Verify business idea exists and belongs to the user
        business_idea = db.query(BusinessIdea).filter(
            BusinessIdea.id == business_id,
            BusinessIdea.user_id == current_user.id
        ).first()
        
        if not business_idea:
            raise HTTPException(
                status_code=404, 
                detail="Business idea not found or you don't have access to it"
            )
        
        # Get user_id of the authenticated user
        user_id = current_user.id
        
        # Get sessions belonging to the user and business
        user_sessions = await redis_service.get_user_sessions(user_id)
        business_sessions = await redis_service.get_business_sessions(business_id)
        
        # Intersection of both sets
        session_ids = list(set(user_sessions).intersection(set(business_sessions)))
        
        # List to store session information
        sessions_info = []
        
        # Get details of each session
        for session_id in session_ids:
            session = await redis_service.get_session(session_id)
            
            # Check if it's a business model session (must have business_model_state in metadata)
            if session and "business_model_state" in session.metadata:
                business_model_state = session.metadata["business_model_state"]
                
                # Create session info object
                session_info = BusinessModelSessionInfo(
                    session_id=session.id,
                    business_id=session.business_id,
                    user_id=session.user_id,
                    current_question_index=business_model_state.get("current_index", 0),
                    total_questions=BusinessModelChatService().get_total_questions(),
                    session_finished=business_model_state.get("session_finished", False),
                    created_at=session.created_at.isoformat() if isinstance(session.created_at, datetime) else session.created_at,
                    updated_at=session.updated_at.isoformat() if isinstance(session.updated_at, datetime) else session.updated_at
                )
                sessions_info.append(session_info)
        
        return BusinessModelSessionListResponse(sessions=sessions_info)
        
    except Exception as e:
        logger.error(f"Error listing business model sessions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/business/{business_id}/report/{session_id}", response_model=BusinessModelReportResponse)
async def get_business_model_report(
    business_id: str = Path(..., description="ID del negocio"),
    session_id: str = Path(..., description="ID de la sesión"),
    redis_service: RedisChatService = Depends(deps.get_redis_service),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    minio_client: MinioService = Depends(deps.get_minio_client)
):
    """
    Get the final report of a business model from a completed session.
    Requires authentication and verifies that the business_id exists and belongs to the user.
    """
    try:
        # Verify business idea exists and belongs to the user
        business_idea = db.query(BusinessIdea).filter(
            BusinessIdea.id == business_id,
            BusinessIdea.user_id == current_user.id
        ).first()
        
        if not business_idea:
            raise HTTPException(
                status_code=404, 
                detail="Business idea not found or you don't have access to it"
            )
        
        # Get the session
        session = await redis_service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
            
        # Verify that the session belongs to the correct user and business
        if session.user_id != current_user.id or session.business_id != business_id:
            raise HTTPException(status_code=403, detail="You don't have access to this session")
            
        # Get the business model state
        business_model_state = session.metadata.get("business_model_state", {})
        
        # Verify that the session is completed
        if not business_model_state.get("session_finished", False):
            raise HTTPException(status_code=400, detail="The business model session has not finished yet")
            
        # Get the answers
        answers = business_model_state.get("answers", {})
        
        # Initialize the business model service
        business_model_service = BusinessModelChatService()
        
        # Generate the report in Markdown
        report_markdown = business_model_service.generate_markdown(answers)
        
        # Save the business model if session is finished
        try:
            logger.info(f"Saving completed business model from report endpoint, business_id: {business_id}")
            save_result = await business_model_service.save_business_model(
                answers=answers,
                business_id=business_id,
                session_id=session_id,
                db=db,
                minio_client=minio_client
            )
            if save_result["success"]:
                logger.info(f"Business model saved successfully from report endpoint for business_id: {business_id}")
            else:
                logger.warning(f"Could not save business model from report endpoint for business_id: {business_id}")
        except Exception as e:
            # Catch any error but continue to return the report
            logger.error(f"Error saving business model from report endpoint: {str(e)}")
        
        return BusinessModelReportResponse(
            session_id=session_id,
            business_id=business_id,
            report_markdown=report_markdown,
            answers=answers
        )
        
    except Exception as e:
        logger.error(f"Error retrieving business model report: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/business/{business_id}", response_model=BusinessModelResponse)
async def get_business_model(
    business_id: str = Path(..., description="ID del negocio"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Get the current business model for a business from the database.
    Requires authentication and verifies that the business_id exists and belongs to the user.
    """
    try:
        # Verify business idea exists and belongs to the user
        business_idea = db.query(BusinessIdea).filter(
            BusinessIdea.id == business_id,
            BusinessIdea.user_id == current_user.id
        ).first()
        
        if not business_idea:
            raise HTTPException(
                status_code=404, 
                detail="Business idea not found or you don't have access to it"
            )
        
        # Query for the business model
        business_model = db.query(BusinessModel).filter(
            BusinessModel.business_id == business_id
        ).first()
        
        if not business_model:
            raise HTTPException(
                status_code=404,
                detail="Business model not found. Please create a business model first."
            )
        
        # Return the model
        return business_model
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error retrieving business model: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/business/{business_id}/session/{session_id}")
async def delete_business_model_session(
    business_id: str = Path(..., description="ID del negocio"),
    session_id: str = Path(..., description="ID de la sesión"),
    redis_service: RedisChatService = Depends(deps.get_redis_service),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Delete a business model chat session.
    Requires authentication and verifies that the business_id exists and belongs to the user.
    """
    try:
        # Verify business idea exists and belongs to the user
        business_idea = db.query(BusinessIdea).filter(
            BusinessIdea.id == business_id,
            BusinessIdea.user_id == current_user.id
        ).first()
        
        if not business_idea:
            raise HTTPException(
                status_code=404, 
                detail="Business idea not found or you don't have access to it"
            )
        
        # Verify that the session exists
        session = await redis_service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
            
        # Verify that the session belongs to the correct user and business
        if session.user_id != current_user.id or session.business_id != business_id:
            raise HTTPException(status_code=403, detail="You don't have access to this session")
            
        # Delete the session
        deleted = await redis_service.delete_session(session_id)
        
        if deleted:
            return {"message": "Session deleted successfully"}
        else:
            raise HTTPException(status_code=500, detail="Could not delete the session")
            
    except Exception as e:
        logger.error(f"Error deleting business model session: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 