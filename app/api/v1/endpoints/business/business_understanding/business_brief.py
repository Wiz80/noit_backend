from fastapi import APIRouter, Depends, HTTPException, Query, Path, BackgroundTasks
from typing import Dict, List, Optional
import logging
import json
import os
import httpx
from datetime import datetime
from sqlalchemy.orm import Session

from app.api import deps
from app.services.business.business_understanding.brief_agent_service import (
    BriefAgentService, 
    get_available_llm_models,
    validate_llm_model,
)
from app.services.cache.redis_service import RedisChatService
from app.controllers.business_understanding.brief_controller import BriefController
from app.schemas.business.business_brief import (
    BriefMessageRequest, 
    BriefMessageResponse, 
    BriefSessionInfo,
    BriefSessionListResponse,
    BriefReportResponse,
    LLMConfigResponse,
    LLMChangeRequest
)
from app.models.user import User
from app.models.business.business_idea import BusinessIdea
from app.models.business.business_understanding.business_model import BusinessModel

# Configure logger
logger = logging.getLogger(__name__)

def get_kestra_webhook_url():
    """Constructs the Kestra webhook URL from environment variables and pipeline configuration."""
    kestra_base_url = os.getenv("KESTRA_BASE_URL", "http://kestra-webserver:8080")
    # From pipelines/business-model-advanced-trigger.yml
    namespace = "noit.backend"
    flow_id = "start-competitor-analysis"
    webhook_key = os.getenv("KESTRA_COMPETITOR_SCRAPER_KEY", "ks_wht_a8hJkLp2sQ9fG3rV")
    return f"{kestra_base_url}/api/v1/executions/webhook/{namespace}/{flow_id}/{webhook_key}"

async def trigger_business_model_completed_webhook(business_id: str):
    """Triggers a Kestra webhook to start the advanced business model analysis."""
    webhook_url = get_kestra_webhook_url()
    payload = {
        "event": "business_model_completed",
        "business_id": business_id
    }
    
    try:
        async with httpx.AsyncClient() as client:
            logger.info(f"Triggering Kestra webhook for business model completion: {webhook_url}")
            response = await client.post(webhook_url, json=payload, timeout=30.0)
            
            if response.status_code >= 400:
                logger.error(
                    f"Error triggering Kestra webhook for business {business_id}. "
                    f"Status: {response.status_code}, Response: {response.text}"
                )
            else:
                logger.info(
                    f"Kestra webhook for business {business_id} triggered successfully. "
                    f"Execution ID: {response.json().get('executionId')}"
                )
    except httpx.RequestError as e:
        logger.error(f"RequestError while triggering Kestra webhook for business {business_id}: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error while triggering Kestra webhook for business {business_id}: {str(e)}")

router = APIRouter()

# -----------------------------------------------------------------------------
# Main chat endpoint for CrewAI-powered brief conversation
# -----------------------------------------------------------------------------
@router.post("/business/{business_id}/brief/chat", response_model=BriefMessageResponse)
async def process_brief_message(
    background_tasks: BackgroundTasks,
    business_id: str = Path(..., description="ID del negocio"),
    request: BriefMessageRequest = None,
    redis_service: RedisChatService = Depends(deps.get_redis_service),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    minio_client = Depends(deps.get_minio_client)
):
    """
    Process a message in a business brief chat session using CrewAI.
    Handles the intelligent conversation flow with multiple AI agents.
    Supports configurable LLM models per conversation.
    """
    try:
        # Verify business exists and belongs to user
        business = db.query(BusinessIdea).filter(
            BusinessIdea.id == business_id,
            BusinessIdea.user_id == current_user.id
        ).first()
        
        if not business:
            raise HTTPException(
                status_code=404, 
                detail="Business idea not found or you don't have access to it"
            )
        
        # Validate LLM model if provided
        llm_model = request.llm_model or "claude-3-5-sonnet-20241022"
        if not validate_llm_model(llm_model):
            logger.warning(f"Invalid LLM model {llm_model}, using default")
            llm_model = "claude-3-5-sonnet-20241022"
        
        # Initialize the brief agent service with configured LLM
        brief_service = BriefAgentService(
            llm_model=llm_model,
            llm_temperature=request.llm_temperature or 0.7,
            llm_max_tokens=request.llm_max_tokens or 4000
        )
        total_questions = brief_service.get_total_questions()
        
        logger.info(f"Processing brief message with LLM: {llm_model}")
        
        # Prepare business data for suggestions
        business_data = {
            "id": business.id,
            "title": business.title,
            "description": business.description,
            "website_url": getattr(business, "website_url", None)
        }
        
        # Check if session exists
        session = None
        if request.session_id:
            session = await redis_service.get_session(request.session_id)
            
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")
            
            # Verify session belongs to user and business
            if session.user_id != current_user.id or session.business_id != business_id:
                raise HTTPException(status_code=403, detail="No access to this session")
        
        # Create new session if none exists
        if not session:
            session = await redis_service.create_session(
                user_id=current_user.id,
                business_id=business_id,
                metadata={
                    "brief_state": {
                        "current_question_index": 0,
                        "answers": {},
                        "session_finished": False
                    },
                    "llm_config": {
                        "model": llm_model,
                        "temperature": request.llm_temperature or 0.7,
                        "max_tokens": request.llm_max_tokens or 4000
                    }
                }
            )
            logger.info(f"Created new brief session: {session.id} with LLM: {llm_model}")
        
        # Get current brief state
        brief_state = session.metadata.get("brief_state", {})
        current_question_index = brief_state.get("current_question_index", 0)
        answers = brief_state.get("answers", {})
        session_finished = brief_state.get("session_finished", False)
        
        # Check if session is already finished
        if session_finished:
            return BriefMessageResponse(
                session_id=session.id,
                reply="El brief ya está completo. Puedes acceder al reporte final o iniciar un nuevo brief.",
                current_question_index=current_question_index,
                total_questions=total_questions,
                session_finished=True,
                llm_model_used=llm_model
            )
        
        # Prepare session data for brief service
        session_data = {
            "current_question_index": current_question_index,
            "answers": answers,
            "langchain_chat_history": session.messages,
            "business_idea": business_data
        }
        
        # Process message with CrewAI brief service
        result = await brief_service.run_agent_turn(request.message, session_data)
        
        # Handle ETAPA 1 completion and business model mapping
        if result.get("etapa1_completed") and result.get("business_model_mapping"):
            try:
                business_model_data = result["business_model_mapping"]
                logger.info(f"Processing ETAPA 1 completion with {len(business_model_data)} business model fields")
                
                # Update or create business model record
                business_model = db.query(BusinessModel).filter(
                    BusinessModel.business_id == business_id
                ).first()
                
                if business_model:
                    # Update existing business model
                    for field, value in business_model_data.items():
                        if hasattr(business_model, field):
                            setattr(business_model, field, value)
                    business_model.updated_at = datetime.now()
                    logger.info(f"Updated existing business model for business {business_id}")
                else:
                    # Create new business model
                    business_model = BusinessModel(
                        business_id=business_id,
                        **business_model_data
                    )
                    db.add(business_model)
                    logger.info(f"Created new business model for business {business_id}")
                
                db.commit()
                logger.info(f"Business model saved successfully after ETAPA 1 completion")
                
                # Trigger Kestra webhook in the background
                background_tasks.add_task(trigger_business_model_completed_webhook, business_id)
                
            except Exception as e:
                logger.error(f"Error saving business model after ETAPA 1: {str(e)}")
                # Don't fail the request, just log the error
                db.rollback()
        
        # Update session with new state
        updated_brief_state = {
            "current_question_index": result["updated_current_question_index"],
            "answers": result["updated_answers"],
            "session_finished": result["session_finished"]
        }
        
        # Update session metadata
        updated_metadata = session.metadata.copy()
        updated_metadata["brief_state"] = updated_brief_state
        session = await redis_service.update_session_metadata(
            session_id=session.id,
            metadata=updated_metadata
        )
        
        # Add user message to session
        if request.message:
            user_message = {
                "role": "user", 
                "content": request.message,
                "timestamp": datetime.now().isoformat()
            }
            session = await redis_service.add_message(session.id, user_message)
        
        # Add assistant response to session
        assistant_message = {
            "role": "assistant",
            "content": result["reply"],
            "timestamp": datetime.now().isoformat(),
            "llm_model": llm_model
        }
        session = await redis_service.add_message(session.id, assistant_message)
        
        # Handle session completion
        if result["session_finished"]:
            try:
                # Save brief to MinIO
                minio_path = BriefController.save_brief_to_minio(
                    business_id, 
                    result["updated_answers"], 
                    minio_client
                )
                logger.info(f"Brief saved to MinIO: {minio_path}")
                
                # Map answers to business model fields (ETAPA 1 only)
                business_model_data = BriefController.map_brief_answers_to_business_model(
                    result["updated_answers"]
                )
                
                # Update or create business model record
                if business_model_data:
                    business_model = db.query(BusinessModel).filter(
                        BusinessModel.business_id == business_id
                    ).first()
                    
                    if business_model:
                        # Update existing business model
                        for field, value in business_model_data.items():
                            if hasattr(business_model, field):
                                setattr(business_model, field, value)
                        business_model.updated_at = datetime.now()
                    else:
                        # Create new business model
                        business_model = BusinessModel(
                            business_id=business_id,
                            **business_model_data
                        )
                        db.add(business_model)
                    
                    db.commit()
                    logger.info(f"Business model updated with brief data")
                
            except Exception as e:
                logger.error(f"Error saving brief completion data: {str(e)}")
                # Don't fail the request, just log the error
        
        # Prepare response
        return BriefMessageResponse(
            session_id=session.id,
            reply=result["reply"],
            suggestion_answer=result.get("suggestion_answer"),
            suggestion_response=result.get("suggestion_response"),
            current_question_index=result["updated_current_question_index"],
            total_questions=total_questions,
            session_finished=result["session_finished"],
            answer_recorded=result.get("answer_recorded"),
            previous_action_confirmation=result.get("previous_action_confirmation"),
            llm_model_used=llm_model
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing brief message: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")

# -----------------------------------------------------------------------------
# Endpoint to list brief sessions
# -----------------------------------------------------------------------------
@router.get("/business/{business_id}/brief/sessions", response_model=BriefSessionListResponse)
async def list_brief_sessions(
    business_id: str = Path(..., description="ID del negocio"),
    redis_service: RedisChatService = Depends(deps.get_redis_service),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """List all brief sessions for a business."""
    try:
        # Verify business exists and belongs to user
        business = db.query(BusinessIdea).filter(
            BusinessIdea.id == business_id,
            BusinessIdea.user_id == current_user.id
        ).first()
        
        if not business:
            raise HTTPException(
                status_code=404, 
                detail="Business idea not found or you don't have access to it"
            )
        
        user_id = current_user.id
        
        # Get sessions belonging to user and business
        user_sessions = await redis_service.get_user_sessions(user_id)
        business_sessions = await redis_service.get_business_sessions(business_id)
        
        # Intersection of both sets
        session_ids = list(set(user_sessions).intersection(set(business_sessions)))
            
        sessions_info = []
        
        # Get details for each session
        for session_id in session_ids:
            session = await redis_service.get_session(session_id)
            
            # Check if it's a brief session (must have brief_state in metadata)
            if session and "brief_state" in session.metadata:
                brief_state = session.metadata["brief_state"]
                
                session_info = BriefSessionInfo(
                    session_id=session.id,
                    business_id=session.business_id,
                    user_id=session.user_id,
                    current_question_index=brief_state.get("current_question_index", 0),
                    total_questions=BriefAgentService().get_total_questions(),
                    session_finished=brief_state.get("session_finished", False),
                    created_at=session.created_at.isoformat() if isinstance(session.created_at, datetime) else session.created_at,
                    updated_at=session.updated_at.isoformat() if isinstance(session.updated_at, datetime) else session.updated_at
                )
                sessions_info.append(session_info)
        
        return BriefSessionListResponse(sessions=sessions_info)
        
    except Exception as e:
        logger.error(f"Error listing brief sessions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------------------------------------------------------------
# Endpoint to get brief report
# -----------------------------------------------------------------------------
@router.get("/business/{business_id}/brief/report/{session_id}", response_model=BriefReportResponse)
async def get_brief_report(
    business_id: str = Path(..., description="ID del negocio"),
    session_id: str = Path(..., description="ID de la sesión"),
    redis_service: RedisChatService = Depends(deps.get_redis_service),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Get the final brief report from a completed session."""
    try:
        # Verify business exists and belongs to user
        business = db.query(BusinessIdea).filter(
            BusinessIdea.id == business_id,
            BusinessIdea.user_id == current_user.id
        ).first()
        
        if not business:
            raise HTTPException(
                status_code=404, 
                detail="Business idea not found or you don't have access to it"
            )
        
        # Get session
        session = await redis_service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
            
        # Verify session belongs to user and business
        if session.user_id != current_user.id or session.business_id != business_id:
            raise HTTPException(status_code=403, detail="No access to this session")
            
        # Get brief state
        brief_state = session.metadata.get("brief_state", {})
        
        # Verify brief is completed
        if not brief_state.get("session_finished", False):
            raise HTTPException(status_code=400, detail="Brief session not finished yet")
            
        # Get answers
        answers = brief_state.get("answers", {})
        
        # Generate markdown report
        report_markdown = BriefController.generate_markdown_report(answers)
        
        return BriefReportResponse(
            session_id=session_id,
            business_id=business_id,
            report_markdown=report_markdown,
            answers=answers
        )
        
    except Exception as e:
        logger.error(f"Error getting brief report: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------------------------------------------------------------
# Endpoint to delete brief session
# -----------------------------------------------------------------------------
@router.delete("/business/{business_id}/brief/session/{session_id}")
async def delete_brief_session(
    business_id: str = Path(..., description="ID del negocio"),
    session_id: str = Path(..., description="ID de la sesión"),
    redis_service: RedisChatService = Depends(deps.get_redis_service),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Delete a brief session."""
    try:
        # Verify business exists and belongs to user
        business = db.query(BusinessIdea).filter(
            BusinessIdea.id == business_id,
            BusinessIdea.user_id == current_user.id
        ).first()
        
        if not business:
            raise HTTPException(
                status_code=404, 
                detail="Business idea not found or you don't have access to it"
            )
        
        # Verify session exists
        session = await redis_service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
            
        # Verify session belongs to user and business
        if session.user_id != current_user.id or session.business_id != business_id:
            raise HTTPException(status_code=403, detail="No access to this session")
            
        # Delete session
        deleted = await redis_service.delete_session(session_id)
        
        if deleted:
            return {"message": "Session deleted successfully"}
        else:
            raise HTTPException(status_code=500, detail="Could not delete session")
            
    except Exception as e:
        logger.error(f"Error deleting brief session: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------------------------------------------------------------
# LLM Configuration endpoints
# -----------------------------------------------------------------------------
@router.get("/brief/llm/config", response_model=LLMConfigResponse)
async def get_llm_configuration():
    """Get available LLM models and configuration options"""
    try:
        available_models = get_available_llm_models()
        providers = list(available_models.keys())
        
        return LLMConfigResponse(
            available_models=available_models,
            current_default="claude-3-5-sonnet-20241022",
            supported_providers=providers
        )
    except Exception as e:
        logger.error(f"Error getting LLM configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/brief/llm/validate")
async def validate_llm_configuration(request: LLMChangeRequest):
    """Validate if an LLM model configuration is supported"""
    try:
        is_valid = validate_llm_model(request.llm_model)
        
        if not is_valid:
            available_models = get_available_llm_models()
            return {
                "valid": False,
                "message": f"Model {request.llm_model} is not supported",
                "available_models": available_models
            }
        
        return {
            "valid": True,
            "message": f"Model {request.llm_model} is supported",
            "provider": "unknown"  # You could add provider detection here
        }
        
    except Exception as e:
        logger.error(f"Error validating LLM configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 