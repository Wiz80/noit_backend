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

# -----------------------------------------------------------------------------
# Legacy business model endpoint (kept for backward compatibility)
# -----------------------------------------------------------------------------
@router.post("/business-model/{business_id}")
async def business_model(
    business_id: str,
    update: Optional[bool] = Query(False, description="If True, a new validation will be executed"),
    db: Session = Depends(deps.get_db),
    minio_client: MinioService = Depends(deps.get_minio_client)
):
    """
    Validate a business idea
    if there is a previous successful validation and update=False, return that validation
    if update=True or there is no previous successful validation, execute a new validation
    """
    try:
        # Verify business idea exists
        business_idea = db.query(BusinessIdea).filter(BusinessIdea.id == business_id).first()
        if not business_idea:
            raise HTTPException(status_code=404, detail="Business idea not found")

        # Search for the most recent successful validation
        existing_validation = (
            db.query(BusinessValidation)
            .filter(
                BusinessValidation.business_id == business_id,
                BusinessValidation.status == ValidationStatus.COMPLETED
            )
            .order_by(BusinessValidation.created_at.desc())
            .first()
        )

        # If there is a successful validation and we don't want to update, return it
        if existing_validation and not update:
            return {
                "success": True,
                "business_id": business_id,
                "report_url": existing_validation.report_url,
                "data_url": existing_validation.data_url,
                "results": json.loads(minio_client.get_object_data(existing_validation.data_url))
            }

        # Create a new validation record
        validation = BusinessValidation(
            business_id=business_id,
            status=ValidationStatus.PENDING
        )
        db.add(validation)
        db.commit()

        try:
            # Construct the business idea text
            business_idea_text = f"""
            {business_idea.title}:
            
            MISIÓN:
            {business_idea.mission}
            
            VISIÓN:
            {business_idea.vision}
            
            DESCRIPCIÓN:
            {business_idea.description}
            """

            # Configure the validator
            config = ValidatorConfig(
                business_idea=business_idea_text,
                perplexity_api_key=os.getenv("PERPLEXITY_API_KEY"),
                validator_api_keys={"openai": os.getenv("OPENAI_API_KEY")},
                validator_provider="openai",
                validator_model="openai:gpt-4o",
                language="es"
            )
            
            validator = BusinessValidator(config)
            # Execute the validation
            results = await validator.run()
            
            # Define paths for the validation report and structured data in MinIO
            business_folder = f"{business_id}/business-understanding"

            json_path = f"{business_folder}/business_model.json"
            
            # If we are updating, add a version suffix to the file names
            if update:
                minio_client.delete_object(f"{business_folder}/business_model.json")
            

            await minio_client.upload_content(
                object_name=json_path,
                data=json.dumps(results.json_output["es"], indent=2),
                content_type="application/json",
                metadata={
                    "business_id": business_id,
                    "validation_id": validation.id
                }
            )

            # Update the validation record
            validation.status = ValidationStatus.COMPLETED
            validation.data_url = json_path
            db.commit()

            # Save results to the BusinessModel database entity
            try:
                market_research_data = results.json_output["es"].get("MarketResearchModule", {})
                
                # Check if a business model already exists
                existing_model = db.query(BusinessModel).filter(
                    BusinessModel.business_id == business_id
                ).first()
                
                if existing_model:
                    # Update existing model
                    existing_model.problem_definition = market_research_data.get("problem_definition")
                    existing_model.industry = market_research_data.get("industry")
                    existing_model.customer_persona = market_research_data.get("customer_persona")
                    existing_model.value_proposition = market_research_data.get("value_proposition")
                    existing_model.competitive_advantage = market_research_data.get("competitive_advantage")
                    existing_model.key_resources = market_research_data.get("key_resources")
                    existing_model.minio_url = json_path
                    existing_model.updated_at = datetime.now()
                else:
                    # Create new model
                    db_model = BusinessModel(
                        business_id=business_id,
                        problem_definition=market_research_data.get("problem_definition"),
                        industry=market_research_data.get("industry"),
                        customer_persona=market_research_data.get("customer_persona"),
                        value_proposition=market_research_data.get("value_proposition"),
                        competitive_advantage=market_research_data.get("competitive_advantage"),
                        key_resources=market_research_data.get("key_resources"),
                        minio_url=json_path
                    )
                    db.add(db_model)
                
                db.commit()
                logger.info(f"BusinessModel for {business_id} saved to database")
            except Exception as e:
                logger.error(f"Error saving BusinessModel to database: {e}")
                # Continue even if saving to database fails

            return {
                "success": True,
                "business_id": business_id,
                "data_url": json_path,
                "results": results.json_output["es"]
            }

        except Exception as e:
            # In case of error, update the validation record
            validation.status = ValidationStatus.ERROR
            validation.error_message = str(e)
            db.commit()
            raise

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------------------------------------------------------------
# Chat-based business model endpoints
# -----------------------------------------------------------------------------
@router.post("/{business_id}/chat", response_model=BusinessModelMessageResponse)
async def process_business_model_message(
    business_id: str = Path(..., description="ID del negocio"),
    request: BusinessModelMessageRequest = None,
    redis_service: RedisChatService = Depends(deps.get_redis_service),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    minio_client: MinioService = Depends(deps.get_minio_client)
):
    """
    Process a message in a business model chat session.
    If no session_id is provided, a new session is created.
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
        
        # Initialize the business model service
        business_model_service = BusinessModelChatService()
        total_questions = business_model_service.get_total_questions()
        
        # Get the user_id of the authenticated user
        user_id = current_user.id
        
        # Convert the business object to a dictionary for use in suggestions
        business_data = {
            "id": business_idea.id,
            "title": business_idea.title,
            "description": business_idea.description
        }
        
        # Check if an existing session_id is provided
        if request.session_id:
            # Get the existing session
            session = await redis_service.get_session(request.session_id)
            
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")
            
            # Verify that the session belongs to the correct user and business
            if session.user_id != user_id or session.business_id != business_id:
                raise HTTPException(status_code=403, detail="You don't have access to this session")
            
            # Check if the session is from another endpoint and marked for business model
            orchestrator_state = session.metadata.get("orchestrator_state", {})
            is_redirect_from_chat = orchestrator_state.get("mode") in ["redirect_to_business_model", "business_model_started"]
            
            if is_redirect_from_chat:
                # It's a session redirected from chat
                logger.info(f"Session redirected from chat: {request.session_id}")
                
                # Update metadata to indicate it's now in the business model flow
                business_model_state = {
                    "current_index": 0,
                    "mode": "normal",
                    "pending_correction": None,
                    "answers": {},
                    "session_finished": False
                }
                
                # Preserve business data from chat if it exists
                business_data_from_chat = orchestrator_state.get("business_data", {})
                if business_data_from_chat:
                    for key, value in business_data_from_chat.items():
                        if value and key in business_data:
                            business_data[key] = value
                
                # Update metadata
                session = await redis_service.update_session_metadata(
                    session_id=session.id,
                    metadata={"business_model_state": business_model_state, "came_from_chat": True}
                )
                
                # Get the first question
                first_question = business_model_service.get_question(0)
                
                # Get suggestion for the first question
                first_phase, first_question_text, _ = business_model_service.flat_questions[0]
                
                # Generate contextual suggestion using business data
                initial_history = [{"role": "system", "content": "Inicio de sesión de modelo de negocio."}]
                first_suggestion = await business_model_service.generate_contextual_suggestion(
                    initial_history,
                    first_question_text,
                    business_data
                )
                
                # Prepare welcome message with suggestion if available
                welcome_content = f"¡Bienvenido al proceso de definición del modelo de negocio! Comenzaremos con la siguiente pregunta:\n\n{first_question}"
                
                if first_suggestion:
                    welcome_content += f"\n\n{first_suggestion}"
                
                # Add system message with the first question
                welcome_message = {
                    "role": "assistant",
                    "content": welcome_content,
                    "timestamp": datetime.now().isoformat()
                }
                
                # Add message to the session
                session = await redis_service.add_message(session.id, welcome_message)
                
                # Add user message if one was sent
                if request.message:
                    user_message = {
                        "role": "user",
                        "content": request.message,
                        "timestamp": datetime.now().isoformat()
                    }
                    session = await redis_service.add_message(session.id, user_message)
                
                # Return response with the first question
                return BusinessModelMessageResponse(
                    session_id=session.id,
                    reply=welcome_content,
                    current_question_index=0,
                    total_questions=total_questions,
                    session_finished=False
                )
        
        # CASE 1: No session_id provided - create a new business model session
        if not request.session_id:
            # Initialize a new session
            metadata = {
                "business_model_state": {
                    "current_index": 0,
                    "mode": "normal",
                    "pending_correction": None,
                    "answers": {},
                    "session_finished": False
                }
            }
            
            # Initial system message
            initial_messages = [{
                "role": "system",
                "content": "Inicio de sesión de modelo de negocio. El sistema guiará al usuario a través de una serie de preguntas para crear un modelo de negocio.",
                "timestamp": datetime.now().isoformat()
            }]
            
            # Get the first question
            first_question = business_model_service.get_question(0)
            
            # Get first question details
            first_phase, first_question_text, _ = business_model_service.flat_questions[0]
            
            # Generate contextual suggestion
            initial_history = [{"role": "system", "content": "Inicio de sesión de modelo de negocio."}]
            first_suggestion = await business_model_service.generate_contextual_suggestion(
                initial_history,
                first_question_text,
                business_data
            )
            
            # Prepare welcome message with suggestion if available
            welcome_content = f"¡Bienvenido al proceso de definición del modelo de negocio! Comenzaremos con la siguiente pregunta:\n\n{first_question}"
            
            if first_suggestion:
                welcome_content += f"\n\n{first_suggestion}"
            
            # Add system message with the first question
            welcome_message = {
                "role": "assistant",
                "content": welcome_content,
                "timestamp": datetime.now().isoformat()
            }
            
            # Create session in Redis
            session = await redis_service.create_session(
                user_id=user_id,
                business_id=business_id,
                metadata=metadata,
                initial_messages=initial_messages
            )
            
            # Add welcome message
            session = await redis_service.add_message(session.id, welcome_message)
            
            # Return response with the first question
            return BusinessModelMessageResponse(
                session_id=session.id,
                reply=welcome_message["content"],
                current_question_index=0,
                total_questions=total_questions,
                session_finished=False
            )
        
        # CASE 2: Existing session with business model state - Process the message
        
        # Get the current business model state from metadata
        business_model_state = session.metadata.get("business_model_state", {
            "current_index": 0,
            "mode": "normal", 
            "pending_correction": None,
            "answers": {},
            "session_finished": False
        })
        
        # Add the user message to the session
        user_message = {
            "role": "user",
            "content": request.message,
            "timestamp": datetime.now().isoformat()
        }
        session = await redis_service.add_message(session.id, user_message)
        
        # Extract message history for processing
        conversation_history = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in session.messages
        ]
        
        # Process the message through the business model service
        result = await business_model_service.process_message_internal(
            message=request.message,
            current_index=business_model_state["current_index"],
            mode=business_model_state["mode"],
            pending_correction=business_model_state["pending_correction"],
            answers=business_model_state["answers"],
            history=conversation_history,
            business_idea=business_data
        )
        
        # Update the business model state in session metadata
        business_model_state.update({
            "current_index": result["current_index"],
            "mode": result["mode"],
            "pending_correction": result["pending_correction"],
            "answers": result["answers"],
            "session_finished": result["session_finished"]
        })
        session = await redis_service.update_session_metadata(
            session_id=session.id,
            metadata={"business_model_state": business_model_state}
        )
        
        # If the session is finished, save the business model
        if result["session_finished"]:
            try:
                logger.info(f"Business model session completed. Saving for business_id: {business_id}, session_id: {session.id}")
                logger.info(f"Answers collected: {len(result['answers'])} phases with data")
                
                # Check if we have valid answers to save
                if not result["answers"]:
                    logger.error("No answers collected in the session, cannot save business model")
                else:
                    # Try to save with detailed error handling
                    save_result = await business_model_service.save_business_model(
                        answers=result["answers"],
                        business_id=business_id,
                        session_id=session.id,
                        db=db,
                        minio_client=minio_client
                    )
                    
                    # Check save result
                    if save_result and save_result.get("success"):
                        logger.info(f"Business model saved successfully for business_id: {business_id}")
                        logger.info(f"Model ID: {save_result.get('model_id')}, MinIO path: {save_result.get('minio_path')}")
                    else:
                        error_msg = save_result.get("error") if save_result else "Unknown error"
                        logger.error(f"Could not save business model for business_id: {business_id}. Error: {error_msg}")
                        
                        # Try again with a direct database approach as fallback
                        try:
                            logger.info("Attempting fallback save method for business model")
                            # Get flattened answers from the result directly
                            flat_answers = {}
                            for phase, phase_answers in result["answers"].items():
                                for question, answer in phase_answers.items():
                                    # Use the question as the field name if we can't map it properly
                                    field_name = question.lower().replace(" ", "_").replace("?", "")[:50]
                                    flat_answers[field_name] = answer
                            
                            # Save to additional_data JSON field which can accommodate any structure
                            existing_model = db.query(BusinessModel).filter(
                                BusinessModel.business_id == business_id
                            ).first()
                            
                            if existing_model:
                                existing_model.additional_data = flat_answers
                                existing_model.updated_at = datetime.now()
                            else:
                                new_model = BusinessModel(
                                    business_id=business_id,
                                    additional_data=flat_answers
                                )
                                db.add(new_model)
                            
                            db.commit()
                            logger.info("Successfully saved using fallback method to additional_data field")
                        except Exception as fallback_error:
                            logger.error(f"Fallback save also failed: {str(fallback_error)}")
            except Exception as e:
                # Catch any error during saving but continue with the response
                logger.error(f"Error saving business model: {str(e)}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Add assistant response to the session
        assistant_message = {
            "role": "assistant",
            "content": result["reply"],
            "timestamp": datetime.now().isoformat()
        }
        session = await redis_service.add_message(session.id, assistant_message)
        
        # Return the response
        return BusinessModelMessageResponse(
            session_id=session.id,
            reply=result["reply"],
            current_question_index=result["current_index"],
            total_questions=total_questions,
            session_finished=result["session_finished"]
        )
        
    except Exception as e:
        logger.error(f"Error in business model processing: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

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