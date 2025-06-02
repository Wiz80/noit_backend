"""
Chat Orchestrator Service
Coordinates between different chat modules and handles intelligent routing
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from sqlalchemy.orm import Session

from app.services.cache.redis_service import RedisChatService
from app.services.business.business_understanding.brief_agent_service import BriefAgentService
from app.models.business.business_idea import BusinessIdea
from app.models.business.business_progress import BusinessProgress

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ChatOrchestrator:
    """
    Main orchestrator for chat conversations.
    Handles routing to different specialized chat modules based on context and intent.
    """
    
    def __init__(self, db: Session, redis_service: RedisChatService):
        self.db = db
        self.redis_service = redis_service
        
    async def process_message(
        self,
        message: str,
        business_id: str,
        user_id: str,
        session_id: Optional[str] = None,
        business_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Main method to process incoming chat messages and route to appropriate modules
        
        Args:
            message: User's message
            business_id: ID of the business
            user_id: ID of the user
            session_id: Optional existing session ID
            business_data: Optional business context data
            
        Returns:
            Dict containing the response and session information
        """
        try:
            # Get or create session
            session = None
            if session_id:
                session = await self.redis_service.get_session(session_id)
                
                if not session:
                    return {
                        "error": True,
                        "status_code": 404,
                        "detail": "Session not found"
                    }
                
                # Verify session belongs to user and business
                if session.user_id != user_id or session.business_id != business_id:
                    return {
                        "error": True,
                        "status_code": 403,
                        "detail": "Access denied to this session"
                    }
            else:
                # Create new session
                session = await self.redis_service.create_session(
                    user_id=user_id,
                    business_id=business_id,
                    metadata={
                        "orchestrator_state": {
                            "active_module": None,
                            "mode": "general"
                        }
                    }
                )
                logger.info(f"Created new orchestrator session: {session.id}")
            
            # Get orchestrator state
            orchestrator_state = session.metadata.get("orchestrator_state", {})
            active_module = orchestrator_state.get("active_module")
            mode = orchestrator_state.get("mode", "general")
            
            # Determine intent and route accordingly
            intent_result = self._analyze_intent(message, business_id, active_module, mode)
            
            if intent_result["route_to"] == "brief":
                return await self._handle_brief_routing(
                    message, business_id, user_id, session, business_data, intent_result
                )
            elif intent_result["route_to"] == "general":
                return await self._handle_general_conversation(
                    message, business_id, user_id, session, intent_result
                )
            else:
                # Handle other modules (business_model, competitive_analysis, etc.)
                return await self._handle_other_modules(
                    message, business_id, user_id, session, intent_result
                )
                
        except Exception as e:
            logger.error(f"Error in chat orchestrator: {str(e)}")
            return {
                "error": True,
                "status_code": 500,
                "detail": f"Internal error: {str(e)}"
            }
    
    def _analyze_intent(
        self, 
        message: str, 
        business_id: str, 
        active_module: Optional[str],
        mode: str
    ) -> Dict[str, Any]:
        """
        Analyze user message to determine intent and routing
        
        Args:
            message: User's message
            business_id: ID of the business
            active_module: Currently active module
            mode: Current conversation mode
            
        Returns:
            Dict containing routing decision and confidence
        """
        message_lower = message.lower().strip()
        
        # Brief-related keywords and phrases
        brief_keywords = [
            "brief", "briefing", "entendimiento", "negocio", "empresa", 
            "comenzar", "empezar", "iniciar", "primera pregunta", "definir",
            "propósito", "valor", "cliente", "producto", "servicio",
            "comunicación", "estrategia", "mensaje"
        ]
        
        # Check for brief intent
        brief_score = sum(1 for keyword in brief_keywords if keyword in message_lower)
        
        # Check business progress to determine if brief should be suggested
        progress = self.db.query(BusinessProgress).filter(
            BusinessProgress.business_id == business_id
        ).first()
        
        is_new_business = not progress or not progress.get_completed_steps()
        
        # Routing logic
        if active_module == "brief" or brief_score > 0:
            return {
                "route_to": "brief",
                "confidence": 0.9 if brief_score > 0 else 0.7,
                "reason": "Brief keywords detected or already in brief mode"
            }
        elif is_new_business and not session_id:
            return {
                "route_to": "brief",
                "confidence": 0.8,
                "reason": "New business detected, suggesting brief"
            }
        else:
            return {
                "route_to": "general",
                "confidence": 0.6,
                "reason": "General conversation"
            }
    
    async def _handle_brief_routing(
        self,
        message: str,
        business_id: str,
        user_id: str,
        session,
        business_data: Optional[Dict[str, Any]],
        intent_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Route to the brief module
        """
        try:
            # Get business information for context
            business = self.db.query(BusinessIdea).filter(
                BusinessIdea.id == business_id,
                BusinessIdea.user_id == user_id
            ).first()
            
            if not business:
                return {
                    "error": True,
                    "status_code": 404,
                    "detail": "Business not found"
                }
            
            # Prepare business data if not provided
            if not business_data:
                business_data = {
                    "id": business.id,
                    "title": business.title,
                    "description": business.description,
                    "website_url": getattr(business, "website_url", None)
                }
            
            # Update orchestrator state to indicate brief module is active
            orchestrator_state = {
                "active_module": "brief",
                "mode": "brief_conversation",
                "business_data": business_data
            }
            
            session = await self.redis_service.update_session_metadata(
                session_id=session.id,
                metadata={"orchestrator_state": orchestrator_state}
            )
            
            # Initialize brief service
            brief_service = BriefAgentService()
            
            # Check if we have brief state in session
            brief_state = session.metadata.get("brief_state")
            if not brief_state:
                # Initialize brief state
                brief_state = {
                    "current_question_index": 0,
                    "answers": {},
                    "session_finished": False
                }
                
                # Update session with brief state
                updated_metadata = session.metadata.copy()
                updated_metadata["brief_state"] = brief_state
                session = await self.redis_service.update_session_metadata(
                    session_id=session.id,
                    metadata=updated_metadata
                )
            
            # Prepare session data for brief service
            session_data = {
                "current_question_index": brief_state.get("current_question_index", 0),
                "answers": brief_state.get("answers", {}),
                "langchain_chat_history": session.messages,
                "business_idea": business_data
            }
            
            # Process message with brief service
            result = brief_service.run_agent_turn(message, session_data)
            
            # Update session with new brief state
            updated_brief_state = {
                "current_question_index": result["updated_current_question_index"],
                "answers": result["updated_answers"],
                "session_finished": result["session_finished"]
            }
            
            updated_metadata = session.metadata.copy()
            updated_metadata["brief_state"] = updated_brief_state
            
            session = await self.redis_service.update_session_metadata(
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
                await self.redis_service.add_message(session.id, user_message)
            
            assistant_message = {
                "role": "assistant",
                "content": result["reply"],
                "timestamp": datetime.now().isoformat()
            }
            await self.redis_service.add_message(session.id, assistant_message)
            
            # Return orchestrator response
            return {
                "session_id": session.id,
                "reply": result["reply"],
                "intent": "brief",
                "confidence": intent_result["confidence"],
                "mode": "brief",
                "active_module": "brief",
                "completed_steps": [],  # TODO: Implement step tracking
                "next_step": "Continue with brief questions" if not result["session_finished"] else "Brief completed"
            }
            
        except Exception as e:
            logger.error(f"Error handling brief routing: {str(e)}")
            return {
                "error": True,
                "status_code": 500,
                "detail": f"Error in brief routing: {str(e)}"
            }
    
    async def _handle_general_conversation(
        self,
        message: str,
        business_id: str,
        user_id: str,
        session,
        intent_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle general conversation that doesn't route to specific modules
        """
        try:
            # General conversation logic
            general_response = self._generate_general_response(message, business_id)
            
            # Add messages to session
            user_message = {
                "role": "user",
                "content": message,
                "timestamp": datetime.now().isoformat()
            }
            await self.redis_service.add_message(session.id, user_message)
            
            assistant_message = {
                "role": "assistant", 
                "content": general_response,
                "timestamp": datetime.now().isoformat()
            }
            await self.redis_service.add_message(session.id, assistant_message)
            
            return {
                "session_id": session.id,
                "reply": general_response,
                "intent": "general",
                "confidence": intent_result["confidence"],
                "mode": "general",
                "active_module": None,
                "completed_steps": [],
                "next_step": "Continue conversation"
            }
            
        except Exception as e:
            logger.error(f"Error handling general conversation: {str(e)}")
            return {
                "error": True,
                "status_code": 500,
                "detail": f"Error in general conversation: {str(e)}"
            }
    
    async def _handle_other_modules(
        self,
        message: str,
        business_id: str,
        user_id: str,
        session,
        intent_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle routing to other specialized modules
        """
        # Placeholder for other modules (business_model, competitive_analysis, etc.)
        return await self._handle_general_conversation(
            message, business_id, user_id, session, intent_result
        )
    
    def _generate_general_response(self, message: str, business_id: str) -> str:
        """
        Generate a general response for non-specific conversations
        """
        message_lower = message.lower().strip()
        
        # Simple response logic
        greeting_words = ["hola", "hello", "hi", "buenos días", "buenas tardes", "buenas noches"]
        help_words = ["ayuda", "help", "qué puedes hacer", "opciones"]
        
        if any(word in message_lower for word in greeting_words):
            return """¡Hola! Soy tu asistente para el desarrollo de negocios. 

Puedo ayudarte con:
- **Brief de negocio**: Definir y entender tu modelo de negocio
- **Análisis competitivo**: Investigar tu competencia
- **Modelo de negocio**: Desarrollar tu business model canvas
- **Estado del arte**: Investigación de mercado

¿En qué te gustaría que te ayude hoy? Puedes decir "quiero hacer el brief" para comenzar con la definición de tu negocio."""
        
        elif any(word in message_lower for word in help_words):
            return """Te puedo ayudar con:

📋 **Brief de Negocio**
- Definición de propósito y valor
- Identificación de clientes ideales
- Estrategia de comunicación

🔍 **Análisis Competitivo**
- Investigación de competidores
- Análisis de redes sociales
- Benchmarking

📊 **Modelo de Negocio**
- Business Model Canvas
- Propuesta de valor
- Estructura de costos e ingresos

🎯 **Estado del Arte**
- Investigación de mercado
- Tendencias de la industria

¿Con cuál te gustaría comenzar?"""
        
        else:
            return """Entiendo tu mensaje. Estoy aquí para ayudarte con el desarrollo de tu negocio.

Si quieres comenzar con algo específico, puedes decir:
- "Quiero hacer el brief" para definir tu negocio
- "Necesito analizar competidores" para análisis competitivo
- "Ayúdame con el modelo de negocio" para business model canvas

¿En qué puedo asistirte?""" 