from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query, status
from typing import Dict, List, Optional, Any
import logging
import json
import asyncio
from datetime import datetime
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from pydantic import ValidationError

from app.api import deps
from app.services.business.business_understanding.brief_agent_service import (
    BriefAgentService,
    validate_llm_model,
)
from app.services.cache.redis_service import RedisChatService
from app.controllers.business_understanding.brief_controller import BriefController
from app.models.user import User
from app.models.business.business_idea import BusinessIdea
from app.models.business.business_understanding.business_model import BusinessModel
from app.crud.crud_user import CRUDUser
from app.core.config import settings

# Configure logger
logger = logging.getLogger(__name__)

router = APIRouter()

class WebSocketManager:
    """Manager for WebSocket connections and message handling"""
    
    def __init__(self):
        # Dictionary to store active connections: {connection_id: websocket}
        self.active_connections: Dict[str, WebSocket] = {}
        # Dictionary to store connection metadata: {connection_id: metadata}
        self.connection_metadata: Dict[str, Dict] = {}
    
    async def connect(self, websocket: WebSocket, connection_id: str, user_id: str, business_id: str):
        """Accept a new WebSocket connection"""
        await websocket.accept()
        self.active_connections[connection_id] = websocket
        self.connection_metadata[connection_id] = {
            "user_id": user_id,
            "business_id": business_id,
            "connected_at": datetime.now().isoformat(),
            "session_id": None
        }
        logger.info(f"WebSocket connection established: {connection_id}")
    
    def disconnect(self, connection_id: str):
        """Remove a WebSocket connection"""
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
        if connection_id in self.connection_metadata:
            del self.connection_metadata[connection_id]
        logger.info(f"WebSocket connection closed: {connection_id}")
    
    async def send_message(self, connection_id: str, message: Dict):
        """Send a message to a specific connection"""
        if connection_id in self.active_connections:
            websocket = self.active_connections[connection_id]
            try:
                await websocket.send_json(message)
                return True
            except Exception as e:
                logger.error(f"Error sending message to {connection_id}: {str(e)}")
                self.disconnect(connection_id)
                return False
        return False
    
    async def send_typing_indicator(self, connection_id: str, is_typing: bool):
        """Send typing indicator to client"""
        message = {
            "type": "typing_indicator",
            "is_typing": is_typing,
            "timestamp": datetime.now().isoformat()
        }
        await self.send_message(connection_id, message)
    
    async def send_progress_update(self, connection_id: str, progress: int, status: str):
        """Send progress update to client"""
        message = {
            "type": "progress_update",
            "progress": progress,
            "status": status,
            "timestamp": datetime.now().isoformat()
        }
        await self.send_message(connection_id, message)
    
    async def send_complete_response(self, connection_id: str, response_data: Dict):
        """Send complete response to client"""
        message = {
            "type": "complete_response",
            "data": response_data,
            "timestamp": datetime.now().isoformat()
        }
        await self.send_message(connection_id, message)
    
    async def send_error(self, connection_id: str, error_message: str, error_code: str = "GENERAL_ERROR"):
        """Send error message to client"""
        message = {
            "type": "error",
            "error_code": error_code,
            "message": error_message,
            "timestamp": datetime.now().isoformat()
        }
        await self.send_message(connection_id, message)

# Global WebSocket manager instance
websocket_manager = WebSocketManager()

async def authenticate_websocket_user(token: str, db: Session) -> User:
    """
    Authenticate WebSocket user using JWT token.
    Uses the exact same logic as deps.get_current_user() for consistency.
    """
    try:
        # Decode JWT token (exact same logic as deps.get_current_user)
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        token_data = payload.get("sub")
        if token_data is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Could not validate credentials",
            )
        
        # Get user from database using the same CRUD pattern as deps
        crud_user = CRUDUser(User)
        current_user = crud_user.get(db, id=token_data)
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="User not found"
            )
        
        return current_user
        
    except (JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication failed"
        )

class StreamingBriefAgentService(BriefAgentService):
    """Extended BriefAgentService with streaming capabilities"""
    
    def __init__(self, connection_id: str, websocket_manager: WebSocketManager, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.connection_id = connection_id
        self.websocket_manager = websocket_manager
    
    async def stream_agent_turn(self, message: str, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a turn with streaming updates to the WebSocket client"""
        try:
            # Send initial progress update
            await self.websocket_manager.send_progress_update(
                self.connection_id, 10, "Procesando tu mensaje..."
            )
            
            # Parse session data
            current_index = session_data.get("current_question_index", 0)
            answers = session_data.get("answers", {})
            business_data = session_data.get("business_idea", {})
            chat_history = session_data.get("langchain_chat_history", [])
            
            # Check if we're starting or continuing
            is_start = current_index == 0 and len(chat_history) == 0
            
            if is_start:
                await self.websocket_manager.send_progress_update(
                    self.connection_id, 30, "Preparando bienvenida..."
                )
                return await self._stream_welcome_flow(current_index, business_data, answers, chat_history)
            else:
                await self.websocket_manager.send_progress_update(
                    self.connection_id, 20, "Analizando tu respuesta..."
                )
                return await self._stream_conversation_flow(message, current_index, business_data, answers, chat_history)
                
        except Exception as e:
            logger.error(f"Error in stream_agent_turn: {str(e)}")
            await self.websocket_manager.send_error(
                self.connection_id, 
                f"Error procesando mensaje: {str(e)}", 
                "PROCESSING_ERROR"
            )
            return {
                "reply": "Lo siento, ocurrió un error. Por favor, intenta de nuevo.",
                "updated_current_question_index": session_data.get("current_question_index", 0),
                "updated_answers": session_data.get("answers", {}),
                "updated_chat_history": session_data.get("langchain_chat_history", []),
                "session_finished": False
            }
    
    async def _stream_welcome_flow(self, current_index: int, business_data: Dict, answers: Dict, chat_history: List) -> Dict[str, Any]:
        """Stream the welcome message and first question"""
        
        # Get first question
        phase, question = self.get_current_question(current_index)
        
        await self.websocket_manager.send_progress_update(
            self.connection_id, 50, "Generando sugerencias contextuales..."
        )
        
        # Send typing indicator
        await self.websocket_manager.send_typing_indicator(self.connection_id, True)
        
        # Get static suggestion
        from app.utils.brief_suggestions import get_suggestion_answer
        suggestion_answer = get_suggestion_answer(question)
        
        await self.websocket_manager.send_progress_update(
            self.connection_id, 70, "Creando respuesta contextual..."
        )
        
        # Generate suggestion response
        suggestion_response = await self._generate_suggestion_with_progress(question, business_data)
        
        await self.websocket_manager.send_progress_update(
            self.connection_id, 90, "Finalizando preparación..."
        )
        
        # Create welcome message
        welcome_msg = f"""¡Hola! Bienvenido al proceso de Brief para definir tu negocio y estrategia de comunicación.

Te haré {self.total_questions} preguntas organizadas en 3 etapas:
1. Entendimiento del Negocio
2. Necesidad/Oportunidad de Comunicación  
3. Estrategia de Comunicación

Comenzemos con la primera pregunta:

**{phase}**
**Pregunta:** {question}"""
        
        # Stop typing indicator
        await self.websocket_manager.send_typing_indicator(self.connection_id, False)
        
        # Update chat history
        updated_history = chat_history + [
            {"role": "assistant", "content": welcome_msg}
        ]
        
        result = {
            "reply": welcome_msg,
            "suggestion_answer": suggestion_answer,
            "suggestion_response": suggestion_response, 
            "updated_current_question_index": current_index,
            "updated_answers": answers,
            "updated_chat_history": updated_history,
            "session_finished": False,
            "total_questions": self.total_questions,
            "current_question_index": current_index
        }
        
        # Send complete response
        await self.websocket_manager.send_complete_response(self.connection_id, result)
        
        return result
    
    async def _stream_conversation_flow(self, message: str, current_index: int, business_data: Dict, answers: Dict, chat_history: List) -> Dict[str, Any]:
        """Stream the conversation flow with real-time updates"""
        
        # Check if session is completed
        if current_index >= len(self.flat_questions):
            await self.websocket_manager.send_progress_update(
                self.connection_id, 100, "Completando brief..."
            )
            return await self._stream_completion(answers, chat_history)
        
        await self.websocket_manager.send_progress_update(
            self.connection_id, 30, "Validando tu respuesta..."
        )
        
        # Send typing indicator for validation
        await self.websocket_manager.send_typing_indicator(self.connection_id, True)
        
        # Use the parent class method for the core logic
        result = await super()._handle_conversation_flow(message, current_index, business_data, answers, chat_history)
        
        await self.websocket_manager.send_progress_update(
            self.connection_id, 80, "Preparando siguiente pregunta..."
        )
        
        # Stop typing indicator
        await self.websocket_manager.send_typing_indicator(self.connection_id, False)
        
        # Send complete response
        await self.websocket_manager.send_complete_response(self.connection_id, result)
        
        return result
    
    async def _stream_completion(self, answers: Dict, chat_history: List) -> Dict[str, Any]:
        """Stream the completion flow"""
        
        await self.websocket_manager.send_typing_indicator(self.connection_id, True)
        
        # Process completion
        result = self._handle_completion(answers, chat_history)
        
        await self.websocket_manager.send_typing_indicator(self.connection_id, False)
        await self.websocket_manager.send_complete_response(self.connection_id, result)
        
        return result
    
    async def _generate_suggestion_with_progress(self, question: str, business_data: Dict) -> str:
        """Generate suggestion with progress updates"""
        try:
            suggestion_task = self._create_suggestion_response_task(question, business_data)
            
            from crewai import Crew, Process
            crew = Crew(
                agents=[self.suggestions_agent],
                tasks=[suggestion_task],
                process=Process.sequential,
                verbose=False
            )
            
            # Execute crew
            crew.kickoff()
            
            suggestion_response = suggestion_task.output.raw if hasattr(suggestion_task.output, 'raw') else str(suggestion_task.output)
            
            return suggestion_response
            
        except Exception as e:
            logger.error(f"Error generating suggestion: {str(e)}")
            return "Excelente, continuemos con la siguiente pregunta."

@router.websocket("/business/{business_id}/brief/chat")
async def websocket_brief_chat(
    websocket: WebSocket,
    business_id: str,
    # Query parameters for authentication and configuration
    token: str = Query(..., description="JWT token for authentication"),
    llm_model: str = Query("gpt-4o-mini", description="LLM model to use"),
    llm_temperature: float = Query(0.7, description="LLM temperature"),
    llm_max_tokens: int = Query(4000, description="LLM max tokens"),
):
    """WebSocket endpoint for real-time business brief chat"""
    
    connection_id = f"brief_{business_id}_{datetime.now().timestamp()}"
    
    try:
        # Get dependencies
        db = next(deps.get_db())
        redis_service = deps.get_redis_service()
        
        # Authenticate user using the same logic as HTTP endpoints
        try:
            current_user = await authenticate_websocket_user(token, db)
        except HTTPException as e:
            logger.error(f"WebSocket authentication failed: {e.detail}")
            # Map HTTP status codes to WebSocket close codes (4xxx range for client errors)
            if e.status_code == 403:
                await websocket.close(code=4003, reason="Could not validate credentials")
            elif e.status_code == 404:
                await websocket.close(code=4004, reason="User not found")
            elif e.status_code == 500:
                await websocket.close(code=4500, reason="Authentication server error")
            else:
                await websocket.close(code=4001, reason="Authentication failed")
            return
        except Exception as e:
            logger.error(f"Unexpected authentication error: {str(e)}")
            await websocket.close(code=4500, reason="Authentication server error")
            return
        
        # Verify business exists and belongs to user
        business = db.query(BusinessIdea).filter(
            BusinessIdea.id == business_id,
            BusinessIdea.user_id == current_user.id
        ).first()
        
        if not business:
            await websocket.close(code=4004, reason="Business not found or access denied")
            return
        
        # Validate LLM model
        if not validate_llm_model(llm_model):
            logger.warning(f"Invalid LLM model {llm_model}, using default")
            llm_model = "gpt-4o-mini"
        
        # Accept WebSocket connection
        await websocket_manager.connect(websocket, connection_id, current_user.id, business_id)
        
        # Initialize streaming brief service
        brief_service = StreamingBriefAgentService(
            connection_id=connection_id,
            websocket_manager=websocket_manager,
            llm_model=llm_model,
            llm_temperature=llm_temperature,
            llm_max_tokens=llm_max_tokens
        )
        
        # Send initial connection confirmation
        await websocket_manager.send_message(connection_id, {
            "type": "connection_established",
            "connection_id": connection_id,
            "business_id": business_id,
            "llm_model": llm_model,
            "total_questions": brief_service.get_total_questions(),
            "timestamp": datetime.now().isoformat()
        })
        
        # Main message handling loop
        while True:
            try:
                # Receive message from client
                data = await websocket.receive_json()
                message_type = data.get("type", "chat_message")
                
                if message_type == "chat_message":
                    await handle_chat_message(
                        data, connection_id, business_id, current_user.id, 
                        brief_service, redis_service, db
                    )
                elif message_type == "ping":
                    # Handle ping/pong for connection health
                    await websocket_manager.send_message(connection_id, {
                        "type": "pong",
                        "timestamp": datetime.now().isoformat()
                    })
                else:
                    await websocket_manager.send_error(
                        connection_id, 
                        f"Unknown message type: {message_type}",
                        "INVALID_MESSAGE_TYPE"
                    )
                    
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected: {connection_id}")
                break
            except Exception as e:
                logger.error(f"Error processing WebSocket message: {str(e)}")
                await websocket_manager.send_error(
                    connection_id, 
                    f"Error processing message: {str(e)}",
                    "MESSAGE_PROCESSING_ERROR"
                )
    
    except Exception as e:
        logger.error(f"WebSocket connection error: {str(e)}")
    
    finally:
        websocket_manager.disconnect(connection_id)

async def handle_chat_message(
    data: Dict, 
    connection_id: str, 
    business_id: str, 
    user_id: str,
    brief_service: StreamingBriefAgentService,
    redis_service: RedisChatService,
    db: Session
):
    """Handle incoming chat messages"""
    
    try:
        message = data.get("message", "")
        session_id = data.get("session_id")
        
        if not message.strip():
            await websocket_manager.send_error(
                connection_id, 
                "Message cannot be empty",
                "EMPTY_MESSAGE"
            )
            return
        
        # Prepare business data
        business = db.query(BusinessIdea).filter(BusinessIdea.id == business_id).first()
        business_data = {
            "id": business.id,
            "title": business.title,
            "description": business.description,
            "website_url": getattr(business, "website_url", None)
        }
        
        # Handle session management
        session = None
        if session_id:
            session = await redis_service.get_session(session_id)
            if not session or session.user_id != user_id or session.business_id != business_id:
                await websocket_manager.send_error(
                    connection_id,
                    "Invalid session",
                    "INVALID_SESSION"
                )
                return
        
        # Create new session if needed
        if not session:
            session = await redis_service.create_session(
                user_id=user_id,
                business_id=business_id,
                metadata={
                    "brief_state": {
                        "current_question_index": 0,
                        "answers": {},
                        "session_finished": False
                    },
                    "llm_config": {
                        "model": brief_service.llm_model,
                        "temperature": 0.7,
                        "max_tokens": 4000
                    }
                }
            )
            
            # Send session created notification
            await websocket_manager.send_message(connection_id, {
                "type": "session_created",
                "session_id": session.id,
                "timestamp": datetime.now().isoformat()
            })
        
        # Get session state
        brief_state = session.metadata.get("brief_state", {})
        current_question_index = brief_state.get("current_question_index", 0)
        answers = brief_state.get("answers", {})
        session_finished = brief_state.get("session_finished", False)
        
        if session_finished:
            await websocket_manager.send_message(connection_id, {
                "type": "session_completed",
                "message": "El brief ya está completo. Puedes acceder al reporte final.",
                "session_id": session.id,
                "timestamp": datetime.now().isoformat()
            })
            return
        
        # Prepare session data for brief service
        session_data = {
            "current_question_index": current_question_index,
            "answers": answers,
            "langchain_chat_history": session.messages,
            "business_idea": business_data
        }
        
        # Process message with streaming
        result = await brief_service.stream_agent_turn(message, session_data)
        
        # Update session with results
        updated_brief_state = {
            "current_question_index": result["updated_current_question_index"],
            "answers": result["updated_answers"],
            "session_finished": result["session_finished"]
        }
        
        updated_metadata = session.metadata.copy()
        updated_metadata["brief_state"] = updated_brief_state
        session = await redis_service.update_session_metadata(
            session_id=session.id,
            metadata=updated_metadata
        )
        
        # Add messages to session
        if message:
            user_message = {
                "role": "user", 
                "content": message,
                "timestamp": datetime.now().isoformat()
            }
            session = await redis_service.add_message(session.id, user_message)
        
        assistant_message = {
            "role": "assistant",
            "content": result["reply"],
            "timestamp": datetime.now().isoformat(),
            "llm_model": brief_service.llm_model
        }
        session = await redis_service.add_message(session.id, assistant_message)
        
        # Handle session completion
        if result["session_finished"]:
            try:
                # Save brief to MinIO
                minio_client = deps.get_minio_client()
                minio_path = BriefController.save_brief_to_minio(
                    business_id, 
                    result["updated_answers"], 
                    minio_client
                )
                
                await websocket_manager.send_message(connection_id, {
                    "type": "brief_completed",
                    "message": "Brief completado y guardado exitosamente",
                    "minio_path": minio_path,
                    "timestamp": datetime.now().isoformat()
                })
                
            except Exception as e:
                logger.error(f"Error saving completed brief: {str(e)}")
        
    except Exception as e:
        logger.error(f"Error handling chat message: {str(e)}")
        await websocket_manager.send_error(
            connection_id,
            f"Error processing message: {str(e)}",
            "CHAT_PROCESSING_ERROR"
        ) 