import json
import logging
import os
from typing import Dict, List, Any, Optional, Union
from pydantic import BaseModel, Field
from enum import Enum
import aisuite as ai
from openai import OpenAI
from app.services.cache.redis_service import RedisChatService, ChatSession
from sqlalchemy.orm import Session
from app.models.business.business_idea import BusinessIdea
from app.crud.crud_business_idea import CRUDBusinessIdea

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Stage(str, Enum):
    """Enum for the different stages of business understanding"""
    BUSINESS_UNDERSTANDING = "business_understanding"
    COMMUNICATION_NEEDS = "communication_needs"
    COMMUNICATION_STRATEGY = "communication_strategy"
    COMPLETED = "completed"

class BusinessChatStatus(BaseModel):
    """Model for tracking business validation status"""
    stage: Stage = Stage.BUSINESS_UNDERSTANDING
    questions_answered: Dict[str, bool] = {}
    current_question: Optional[str] = None
    progress: float = 0.0  # Overall progress (0.0 to 1.0)
    
    # Stage-specific progress
    stage_progress: Dict[str, float] = Field(default_factory=lambda: {
        Stage.BUSINESS_UNDERSTANDING: 0.0,
        Stage.COMMUNICATION_NEEDS: 0.0,
        Stage.COMMUNICATION_STRATEGY: 0.0
    })
    
    # Results from each stage
    results: Dict[str, Any] = Field(default_factory=dict)

class BusinessChatConfig(BaseModel):
    """Configuration for the business chat module"""
    business_id: str
    user_id: str
    language: str = "es"
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o"
    db_session: Optional[Session] = None
    llm_client: Optional[Any] = None
    
    model_config = {"arbitrary_types_allowed": True}
    
    def __init__(self, **data):
        super().__init__(**data)
        self._init_clients()
    
    def _init_clients(self):
        """Initialize LLM clients based on provider"""
        if self.llm_provider in ["openai", "claude"]:
            self.llm_client = ai.Client()
        elif self.llm_provider == "deepseek":
            self.llm_client = OpenAI(
                api_key=os.getenv("DEEPSEEK_API_KEY"),
                base_url="https://api.deepseek.com"
            )
        else:
            raise ValueError(f"Invalid LLM provider: {self.llm_provider}")

class BusinessChatService:
    """Chat-based business understanding service"""
    
    def __init__(
        self, 
        config: BusinessChatConfig,
        redis_service: RedisChatService,
        business_crud: Optional[CRUDBusinessIdea] = None
    ):
        self.config = config
        self.redis = redis_service
        self.business_id = config.business_id
        self.user_id = config.user_id
        self.llm_client = config.llm_client
        self.llm_model = config.llm_model
        self.language = config.language
        self.db = config.db_session
        self.business_crud = business_crud
        
        # Define all questions by stage - More concise questions
        self.questions = {
            Stage.BUSINESS_UNDERSTANDING: [
                "Cuéntame brevemente, ¿qué hace tu empresa y cuál es su propósito principal?",
                "¿Cuál es tu propuesta de valor única? ¿Qué te diferencia?",
                "Describe tus productos o servicios principales y a qué clientes están dirigidos.",
                "¿Quién es tu cliente ideal? Describe sus características principales.",
                "¿Qué problema específico resuelves para tus clientes?"
            ],
            Stage.COMMUNICATION_NEEDS: [
                "¿Qué tendencias o cambios en el mercado hacen necesaria tu comunicación ahora?",
                "¿Cuál es la oportunidad de negocio que quieres aprovechar?",
                "¿Qué objetivos concretos buscas con esta comunicación?"
            ],
            Stage.COMMUNICATION_STRATEGY: [
                "Resume en una frase el mensaje clave que quieres comunicar.",
                "Describe a tu audiencia objetivo para esta comunicación.",
                "¿Qué te hace creíble ante esta audiencia?",
                "¿Cuál es el tono y estilo de comunicación que mejor representa tu marca?",
                "¿Qué métricas usarás para medir el éxito de esta comunicación?",
                "¿Qué quieres que haga tu audiencia después de recibir tu mensaje?",
                "¿Hay limitaciones o fechas clave para esta comunicación?"
            ]
        }
        
        # Fields that map to the BusinessIdea model
        self.field_mappings = {
            "Cuéntame brevemente, ¿qué hace tu empresa y cuál es su propósito principal?": "description",
            "¿Cuál es tu propuesta de valor única? ¿Qué te diferencia?": "value_proposal",
            "Describe tus productos o servicios principales y a qué clientes están dirigidos.": "products_services"
        }
        
        # Initialize question status
        self.all_questions_by_id = {}
        question_id = 1
        
        for stage, questions in self.questions.items():
            for question in questions:
                self.all_questions_by_id[str(question_id)] = {
                    "stage": stage,
                    "question": question,
                    "answered": False,
                    "answer": None
                }
                question_id += 1
    
    async def start_or_continue_chat(self) -> Dict[str, Any]:
        """
        Start a new chat session or continue an existing one
        
        Returns:
            Dictionary with session_id and next_prompt
        """
        # Check for existing sessions for this business
        business_sessions = await self.redis.get_business_sessions(self.business_id)
        
        if business_sessions:
            # Use the most recent session
            session_id = business_sessions[0]
            session = await self.redis.get_session(session_id)
            
            # Update status if it exists in metadata
            status = BusinessChatStatus()
            if session and 'status' in session.metadata:
                try:
                    status = BusinessChatStatus(**session.metadata['status'])
                except Exception as e:
                    logger.error(f"Error parsing status: {e}")
            
            greeting = "¡Hola de nuevo! Continuemos con la validación de tu idea de negocio."
            next_question = self._get_next_question(status)
            
            return {
                "session_id": session_id,
                "greeting": greeting,
                "next_question": next_question,
                "status": status.model_dump()
            }
        else:
            # Create a new session
            initial_system_message = {
                "role": "system",
                "content": self._get_system_prompt()
            }
            
            initial_assistant_message = {
                "role": "assistant",
                "content": "¡Hola! Soy tu asistente para validar tu idea de negocio. Vamos a trabajar juntos para entender y estructurar tu idea a través de un proceso de 3 etapas. Empecemos con algunas preguntas básicas sobre tu negocio."
            }
            
            # Initialize a fresh status
            status = BusinessChatStatus()
            
            # Create new session with initial message
            session = await self.redis.create_session(
                user_id=self.user_id,
                business_id=self.business_id,
                metadata={"status": status.model_dump()},
                initial_messages=[initial_system_message, initial_assistant_message]
            )
            
            next_question = self._get_next_question(status)
            
            return {
                "session_id": session.id,
                "greeting": initial_assistant_message["content"],
                "next_question": next_question,
                "status": status.model_dump()
            }
    
    def _get_system_prompt(self) -> str:
        """
        Get the system prompt for the LLM
        
        Returns:
            System prompt string
        """
        return """Eres un asistente experto en validación de ideas de negocio. Tu tarea es guiar al usuario
a través de un proceso de 3 etapas para entender y validar su idea de negocio:

ETAPA 1: ENTENDIMIENTO DEL NEGOCIO
- ¿Qué hace la empresa y cuál es su propósito?
- ¿Cuál es su propuesta de valor?
- ¿Qué productos/servicios ofrece y a quiénes?
- ¿Quién es su cliente ideal?
- ¿Qué problema resuelve?

ETAPA 2: NECESIDAD / OPORTUNIDAD DE COMUNICACIÓN
- ¿Qué tendencias de mercado hacen necesaria esta comunicación?
- ¿Cuál es la oportunidad de negocio concreta?
- ¿Qué objetivos tiene esta comunicación?

ETAPA 3: ESTRATEGIA DE COMUNICACIÓN
- Mensaje central: ¿Cuál es la idea clave?
- Audiencia: ¿A quién va dirigida?
- Credibilidad: ¿Por qué te creerían?
- Tono: ¿Cómo vas a comunicar?
- Métricas: ¿Cómo medirás el éxito?
- Acción deseada: ¿Qué quieres que haga tu audiencia?
- Limitaciones: ¿Qué restricciones existen?

Instrucciones importantes:
1. Haz preguntas CONCISAS y directas, una a la vez.
2. Mantén un tono conversacional y profesional.
3. Adapta las preguntas según lo que el usuario ya haya compartido.
4. Resume al finalizar cada etapa antes de pasar a la siguiente.
5. Busca respuestas específicas y evita información vaga.
6. Si una respuesta no es clara o completa, profundiza con una pregunta de seguimiento.
7. Guía amablemente al usuario si se desvía del tema."""
    
    def _get_next_question(self, status: BusinessChatStatus) -> Optional[str]:
        """
        Get the next question to ask based on current status
        
        Args:
            status: Current BusinessChatStatus
            
        Returns:
            Next question to ask or None if all questions are answered
        """
        current_stage = status.stage
        
        # Check if we need to move to the next stage
        if current_stage == Stage.COMPLETED:
            return None
            
        # Get questions for the current stage
        stage_questions = self.questions.get(current_stage, [])
        
        # Find the first unanswered question in this stage
        for question in stage_questions:
            if question not in status.questions_answered or not status.questions_answered[question]:
                return question
                
        # If all questions in this stage are answered, move to the next stage
        if current_stage == Stage.BUSINESS_UNDERSTANDING:
            next_stage = Stage.COMMUNICATION_NEEDS
        elif current_stage == Stage.COMMUNICATION_NEEDS:
            next_stage = Stage.COMMUNICATION_STRATEGY
        elif current_stage == Stage.COMMUNICATION_STRATEGY:
            next_stage = Stage.COMPLETED
            return None
        else:
            return None
            
        # Get the first question of the next stage
        if next_stage in self.questions and self.questions[next_stage]:
            return self.questions[next_stage][0]
            
        return None
    
    async def process_user_message(self, session_id: str, user_message: str) -> Dict[str, Any]:
        """
        Process a user message in the chat
        
        Args:
            session_id: Chat session ID
            user_message: User's message text
            
        Returns:
            Dictionary with AI response and updated status
        """
        # Get the current session
        session = await self.redis.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
            
        # Get current status
        status = BusinessChatStatus()
        if 'status' in session.metadata:
            try:
                status = BusinessChatStatus(**session.metadata['status'])
            except Exception as e:
                logger.error(f"Error parsing status: {e}")
                
        # Identify the current question being answered
        current_question = status.current_question or self._get_next_question(status)
        
        if not current_question and status.stage != Stage.COMPLETED:
            # If there's no current question but we're not done, move to the next stage
            new_stage = None
            if status.stage == Stage.BUSINESS_UNDERSTANDING:
                new_stage = Stage.COMMUNICATION_NEEDS
            elif status.stage == Stage.COMMUNICATION_NEEDS:
                new_stage = Stage.COMMUNICATION_STRATEGY
            elif status.stage == Stage.COMMUNICATION_STRATEGY:
                new_stage = Stage.COMPLETED
                
            if new_stage:
                status.stage = new_stage
                if new_stage != Stage.COMPLETED:
                    current_question = self._get_next_question(status)
                    
        # Add user message to session
        await self.redis.add_message(session_id, {"role": "user", "content": user_message})
        
        # Update business data if the question maps to a field in the business model
        if current_question and current_question in self.field_mappings and self.business_crud and self.db:
            field_name = self.field_mappings[current_question]
            await self._update_business_field(field_name, user_message)
            
        # Mark question as answered and update chat data
        if current_question:
            status.questions_answered[current_question] = True
            
            # Aggregate chat data for the business
            if self.business_crud and self.db:
                business = self.business_crud.get(self.db, id=self.business_id)
                if business:
                    chat_data = business.chat_data or {}
                    # Store the answer under a key based on the question
                    question_key = current_question.replace("¿", "").replace("?", "").strip().lower()
                    question_key = '_'.join(question_key.split()[:5])  # Take first 5 words
                    chat_data[question_key] = user_message
                    
                    business.chat_data = chat_data
                    self.db.commit()
            
        # Generate AI response
        ai_response = await self._generate_ai_response(session_id, status, current_question)
        
        # Update progress
        await self._update_progress(status)
        
        # Get the next question
        next_question = self._get_next_question(status)
        status.current_question = next_question
        
        # Update session metadata
        await self.redis.update_session_metadata(session_id, {"status": status.model_dump()})
        
        return {
            "response": ai_response,
            "next_question": next_question,
            "status": status.model_dump()
        }
        
    async def _generate_ai_response(self, session_id: str, status: BusinessChatStatus, current_question: Optional[str]) -> str:
        """
        Generate an AI response based on the conversation history
        
        Args:
            session_id: Chat session ID
            status: Current business chat status
            current_question: The question being answered
            
        Returns:
            AI response text
        """
        # Get session messages
        session = await self.redis.get_session(session_id)
        messages = session.messages if session else []
        
        # Add a hint about the current stage and progress
        hint = ""
        if status.stage != Stage.COMPLETED:
            if current_question:
                # The question was just answered
                answered_count = sum(1 for q in self.questions[status.stage] if q in status.questions_answered and status.questions_answered[q])
                total_count = len(self.questions[status.stage])
                hint = f"\n\nEl usuario acaba de responder a la pregunta: '{current_question}'. "
                hint += f"Ha completado {answered_count} de {total_count} preguntas en la etapa '{status.stage}'."
                
                if status.stage == Stage.BUSINESS_UNDERSTANDING and answered_count == total_count:
                    hint += "\nDebe pasar a la siguiente etapa (COMMUNICATION_NEEDS) con un breve resumen de lo aprendido hasta ahora."
                elif status.stage == Stage.COMMUNICATION_NEEDS and answered_count == total_count:
                    hint += "\nDebe pasar a la siguiente etapa (COMMUNICATION_STRATEGY) con un breve resumen de lo aprendido hasta ahora."
                elif status.stage == Stage.COMMUNICATION_STRATEGY and answered_count == total_count:
                    hint += "\nDebe finalizar el proceso con un breve resumen general de toda la validación."
        else:
            hint = "\n\nEl proceso de validación ha sido completado. Proporcione un resumen final de la idea de negocio."
        
        # Add this hint to the system message
        if messages and messages[0]["role"] == "system":
            messages[0]["content"] += hint
        
        # Generate response
        if self.config.llm_provider in ["openai", "claude"]:
            completion = await self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=messages,
                temperature=0.7,
                top_p=0.9,
                max_tokens=500
            )
            
            response_text = completion.choices[0].message.content
        elif self.config.llm_provider == "deepseek":
            # DeepSeek API
            completion = await self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=messages,
                temperature=0.7,
                top_p=0.9,
                max_tokens=500
            )
            
            response_text = completion.choices[0].message.content
        else:
            response_text = "Lo siento, el proveedor de LLM no está configurado correctamente."
        
        # Add AI message to session
        await self.redis.add_message(session_id, {"role": "assistant", "content": response_text})
        
        return response_text
    
    async def _update_progress(self, status: BusinessChatStatus):
        """
        Update progress metrics in the status
        
        Args:
            status: Current BusinessChatStatus to update
        """
        # Calculate stage progress
        for stage in Stage:
            if stage == Stage.COMPLETED:
                continue
                
            stage_questions = self.questions.get(stage, [])
            if not stage_questions:
                status.stage_progress[stage] = 0.0
                continue
                
            answered_count = sum(1 for q in stage_questions if q in status.questions_answered and status.questions_answered[q])
            status.stage_progress[stage] = answered_count / len(stage_questions)
        
        # Calculate overall progress (weighted by stage)
        weights = {
            Stage.BUSINESS_UNDERSTANDING: 0.4,
            Stage.COMMUNICATION_NEEDS: 0.3,
            Stage.COMMUNICATION_STRATEGY: 0.3
        }
        
        total_progress = sum(status.stage_progress[stage] * weights[stage] for stage in weights)
        
        status.progress = total_progress
        
        # Update stage if complete
        if status.stage != Stage.COMPLETED:
            if status.stage_progress[status.stage] >= 1.0:
                # Move to next stage
                if status.stage == Stage.BUSINESS_UNDERSTANDING:
                    status.stage = Stage.COMMUNICATION_NEEDS
                elif status.stage == Stage.COMMUNICATION_NEEDS:
                    status.stage = Stage.COMMUNICATION_STRATEGY
                elif status.stage == Stage.COMMUNICATION_STRATEGY:
                    status.stage = Stage.COMPLETED
    
    async def _update_business_field(self, field_name: str, value: str):
        """
        Update a field in the BusinessIdea model
        
        Args:
            field_name: Field name to update
            value: New value for the field
        """
        if not self.business_crud or not self.db:
            return
            
        try:
            business = self.business_crud.get(self.db, id=self.business_id)
            if not business:
                return
                
            setattr(business, field_name, value)
            self.db.commit()
            logger.info(f"Updated business field {field_name} for business {self.business_id}")
        except Exception as e:
            logger.error(f"Error updating business field: {e}")
    
    async def generate_summary(self, session_id: str) -> Dict[str, Any]:
        """
        Generate a summary of the business validation chat
        
        Args:
            session_id: Chat session ID
            
        Returns:
            Dictionary with summary text and data
        """
        # Get session
        session = await self.redis.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
            
        # Get status
        status = BusinessChatStatus()
        if 'status' in session.metadata:
            try:
                status = BusinessChatStatus(**session.metadata['status'])
            except Exception as e:
                logger.error(f"Error parsing status: {e}")
        
        # Get all messages
        messages = session.messages if session else []
        
        # Extract user responses only
        user_responses = {}
        for question in self.all_questions_by_id.values():
            question_text = question["question"]
            stage = question["stage"]
            
            if question_text in status.questions_answered and status.questions_answered[question_text]:
                # Find the user response for this question
                for i, msg in enumerate(messages):
                    if msg["role"] == "assistant" and question_text in msg["content"]:
                        # User response should be the next message
                        if i+1 < len(messages) and messages[i+1]["role"] == "user":
                            user_responses[question_text] = {
                                "stage": stage,
                                "answer": messages[i+1]["content"]
                            }
                            break
        
        # Generate summary prompt
        summary_prompt = [
            {"role": "system", "content": """Eres un consultor de negocios experto. Necesito que generes un resumen ejecutivo 
            de la validación de una idea de negocio basándote en las respuestas proporcionadas por el usuario a las siguientes 
            preguntas organizadas por etapas. El resumen debe ser conciso, específico y útil para el emprendedor, destacando 
            puntos fuertes, oportunidades y posibles desafíos identificados durante la validación. Estructura tu resumen por 
            secciones correspondientes a las etapas del proceso."""},
            {"role": "user", "content": "A continuación están las respuestas del usuario organizadas por etapas:"}
        ]
        
        # Add user responses by stage
        for stage in Stage:
            if stage == Stage.COMPLETED:
                continue
                
            stage_prompt = f"\n\nETAPA: {stage}\n"
            has_responses = False
            
            for question, response in user_responses.items():
                if response["stage"] == stage:
                    stage_prompt += f"Pregunta: {question}\nRespuesta: {response['answer']}\n\n"
                    has_responses = True
            
            if has_responses:
                summary_prompt[-1]["content"] += stage_prompt
        
        summary_prompt[-1]["content"] += "\nPor favor, genera un resumen ejecutivo basado en estas respuestas, destacando los puntos clave de la validación del negocio y posibles recomendaciones."
        
        # Generate summary
        if self.config.llm_provider in ["openai", "claude"]:
            completion = await self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=summary_prompt,
                temperature=0.7,
                top_p=0.9,
                max_tokens=1000
            )
            
            summary_text = completion.choices[0].message.content
        elif self.config.llm_provider == "deepseek":
            # DeepSeek API
            completion = await self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=summary_prompt,
                temperature=0.7,
                top_p=0.9,
                max_tokens=1000
            )
            
            summary_text = completion.choices[0].message.content
        else:
            summary_text = "Lo siento, el proveedor de LLM no está configurado correctamente."
        
        # Update business with summary if possible
        if self.business_crud and self.db:
            try:
                business = self.business_crud.get(self.db, id=self.business_id)
                if business:
                    # Save the summary in chat_data
                    chat_data = business.chat_data or {}
                    chat_data["validation_summary"] = summary_text
                    business.chat_data = chat_data
                    
                    # Mark as validated
                    business.is_validated = True
                    
                    self.db.commit()
                    logger.info(f"Updated business with validation summary for business {self.business_id}")
            except Exception as e:
                logger.error(f"Error updating business with summary: {e}")
        
        # Update session metadata to mark as completed
        status.stage = Stage.COMPLETED
        status.progress = 1.0
        await self.redis.update_session_metadata(session_id, {"status": status.model_dump()})
        
        return {
            "summary": summary_text,
            "data": user_responses,
            "status": status.model_dump()
        } 