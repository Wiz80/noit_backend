import json
import logging
import os
from typing import Dict, List, Any, Optional, Union
from pydantic import BaseModel, Field
from enum import Enum
import aisuite as ai
from openai import OpenAI
from app.services.cache.redis_service import RedisChatService, ChatSession

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
    business_id: int
    user_id: int
    language: str = "es"
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o"
    
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
        redis_service: RedisChatService
    ):
        self.config = config
        self.redis = redis_service
        self.business_id = config.business_id
        self.user_id = config.user_id
        self.llm_client = config.llm_client
        self.llm_model = config.llm_model
        self.language = config.language
        
        # Define all questions by stage
        self.questions = {
            Stage.BUSINESS_UNDERSTANDING: [
                "¿Qué hace la empresa? ¿Cuál es su propósito?",
                "¿Cuál es su propuesta de valor?",
                "¿Qué productos/servicios ofrece y a quiénes?",
                "¿Cuál es el cliente ideal?",
                "¿Qué problema resuelve?",
                "¿Qué los hace diferentes frente a la competencia?",
                "¿Qué desafíos u oportunidades clave enfrentan hoy?"
            ],
            Stage.COMMUNICATION_NEEDS: [
                "¿Qué está ocurriendo alrededor del negocio o mercado que hace necesaria esta comunicación?",
                "¿Cuál es la oportunidad de negocio concreta?",
                "¿Qué objetivo tiene esta comunicación (posicionamiento, lanzamiento, awareness, conversión, etc.)?"
            ],
            Stage.COMMUNICATION_STRATEGY: [
                "¿Cuál es la idea o mensaje clave a comunicar?",
                "¿A quién va dirigida esta comunicación?",
                "¿Qué valores o características tiene esta audiencia que deberíamos considerar?",
                "¿Por qué nos creerían? ¿Qué hace nuestra promesa creíble?",
                "¿Cómo vamos a sonar (tono, voz, estilo)?",
                "¿Cuál es el indicador de éxito más importante? ¿Qué cifras o resultados esperamos?",
                "¿Qué queremos que la audiencia piense, sienta o haga después de recibir esta comunicación?",
                "¿Hay limitaciones legales, presupuestarias o de formatos? ¿Canales obligatorios o a evitar? ¿Fechas clave?"
            ]
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
                "content": "¡Hola! Soy tu asistente para la validación de ideas de negocio. Vamos a trabajar juntos para entender y validar tu idea a través de un proceso de 3 etapas: Entendimiento del negocio, Necesidad de comunicación y Estrategia de comunicación.\n\nComencemos con la primera etapa: Entendimiento del negocio."
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

ETAPA 1: ENTENDIMIENTO DEL NEGOCIO (Brief de diagnóstico)
- ¿Qué hace la empresa? ¿Cuál es su propósito?
- ¿Cuál es su propuesta de valor?
- ¿Qué productos/servicios ofrece y a quiénes?
- ¿Cuál es el cliente ideal?
- ¿Qué problema resuelve?
- ¿Qué los hace diferentes frente a la competencia?
- ¿Qué desafíos u oportunidades clave enfrentan hoy?

ETAPA 2: NECESIDAD / OPORTUNIDAD DE COMUNICACIÓN
- ¿Qué está ocurriendo alrededor del negocio o mercado que hace necesaria esta comunicación?
- ¿Cuál es la oportunidad de negocio concreta?
- ¿Qué objetivo tiene esta comunicación (posicionamiento, lanzamiento, awareness, conversión, etc.)?

ETAPA 3: ESTRATEGIA DE COMUNICACIÓN
- El mensaje central: ¿Cuál es la idea o mensaje clave a comunicar?
- Audiencia: ¿A quién va dirigida esta comunicación? ¿Qué valores o características tiene esta audiencia?
- Credibilidad y tono: ¿Por qué nos creerían? ¿Qué hace nuestra promesa creíble? ¿Cómo vamos a sonar?
- Objetivos y éxito: ¿Cuál es el indicador de éxito? ¿Qué resultados esperamos?
- Efecto deseado: ¿Qué queremos que la audiencia piense, sienta o haga?
- Consideraciones: ¿Hay limitaciones legales, presupuestarias o de formatos? ¿Canales? ¿Fechas clave?

Instrucciones importantes:
1. Haz una pregunta a la vez, no bombardees al usuario con muchas preguntas a la vez.
2. Mantén un tono conversacional, amigable y profesional.
3. Si el usuario ya ha proporcionado información relevante a una pregunta, considera esa pregunta respondida.
4. No sigas un guión rígido - adapta las preguntas según lo que el usuario ya haya compartido.
5. Cuando una etapa esté completa, resume lo aprendido antes de pasar a la siguiente etapa.
6. Profundiza cuando sea necesario para obtener respuestas de calidad.
7. Si el usuario se desvía del tema, guíalo de vuelta amablemente."""
    
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
        all_questions_answered_in_stage = True
        for q_id, q_info in self.all_questions_by_id.items():
            if q_info["stage"] == current_stage and not q_info["answered"]:
                all_questions_answered_in_stage = False
                next_question_id = q_id
                break
        
        # Move to next stage if all questions in current stage are answered
        if all_questions_answered_in_stage:
            if current_stage == Stage.BUSINESS_UNDERSTANDING:
                status.stage = Stage.COMMUNICATION_NEEDS
                return "Excelente, hemos completado la primera etapa de entendimiento del negocio. Ahora, vamos a la segunda etapa para entender la necesidad u oportunidad de comunicación.\n\n¿Qué está ocurriendo alrededor del negocio o mercado que hace necesaria esta comunicación?"
            
            elif current_stage == Stage.COMMUNICATION_NEEDS:
                status.stage = Stage.COMMUNICATION_STRATEGY
                return "Perfecto, hemos completado la segunda etapa. Ahora, vamos a la tercera etapa para definir la estrategia de comunicación.\n\n¿Cuál es la idea o mensaje clave a comunicar?"
            
            elif current_stage == Stage.COMMUNICATION_STRATEGY:
                status.stage = Stage.COMPLETED
                return "¡Felicitaciones! Hemos completado todas las etapas de validación. Ahora tengo suficiente información para generar un reporte completo sobre tu idea de negocio. ¿Te gustaría ver un resumen de todo lo que hemos discutido?"
            
            else:  # COMPLETED
                return None
        
        # Get next unanswered question in current stage
        for q_id, q_info in self.all_questions_by_id.items():
            if q_info["stage"] == current_stage and not q_info["answered"]:
                status.current_question = q_id
                return q_info["question"]
        
        return None
    
    async def process_user_message(
        self, 
        session_id: str, 
        user_message: str
    ) -> Dict[str, Any]:
        """
        Process a user message and generate a response
        
        Args:
            session_id: ID of the chat session
            user_message: User's message
            
        Returns:
            Dictionary with assistant response and updated status
        """
        # Get current session
        session = await self.redis.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        # Add user message to the conversation
        await self.redis.add_message(session_id, "user", user_message)
        
        # Get current status
        status = BusinessChatStatus()
        if 'status' in session.metadata:
            try:
                status = BusinessChatStatus(**session.metadata['status'])
            except Exception as e:
                logger.error(f"Error parsing status: {e}")
        
        # Update status based on user message
        if status.current_question:
            q_info = self.all_questions_by_id.get(status.current_question)
            if q_info:
                q_info["answered"] = True
                q_info["answer"] = user_message
                status.questions_answered[status.current_question] = True
                
                # Calculate progress
                self._update_progress(status)
                
                # Store answer in results
                if status.stage not in status.results:
                    status.results[status.stage] = {}
                
                status.results[status.stage][q_info["question"]] = user_message
        
        # Generate AI response
        history = await self.redis.get_conversation_history(session_id)
        response = await self._generate_ai_response(history, status)
        
        # Add AI response to the conversation
        await self.redis.add_message(session_id, "assistant", response)
        
        # Update next question
        next_question = self._get_next_question(status)
        if next_question:
            status.current_question = next_question
        
        # Update session metadata with new status
        await self.redis.update_session_metadata(
            session_id, 
            {"status": status.model_dump()}
        )
        
        return {
            "response": response,
            "status": status.model_dump(),
            "next_question": next_question
        }
    
    def _update_progress(self, status: BusinessChatStatus) -> None:
        """
        Update progress percentages based on answered questions
        
        Args:
            status: Current BusinessChatStatus to update
        """
        # Count questions by stage
        stage_questions = {}
        for stage in Stage:
            if stage == Stage.COMPLETED:
                continue
            stage_questions[stage] = 0
        
        # Count answered questions by stage
        stage_answered = {}
        for stage in Stage:
            if stage == Stage.COMPLETED:
                continue
            stage_answered[stage] = 0
        
        # Count total questions and answered questions
        total_questions = 0
        total_answered = 0
        
        for q_id, q_info in self.all_questions_by_id.items():
            stage = q_info["stage"]
            if stage == Stage.COMPLETED:
                continue
                
            stage_questions[stage] += 1
            total_questions += 1
            
            if q_info["answered"]:
                stage_answered[stage] += 1
                total_answered += 1
        
        # Calculate progress percentages
        for stage in Stage:
            if stage == Stage.COMPLETED:
                continue
                
            if stage_questions[stage] > 0:
                status.stage_progress[stage] = stage_answered[stage] / stage_questions[stage]
        
        # Overall progress
        if total_questions > 0:
            status.progress = total_answered / total_questions
    
    async def _generate_ai_response(
        self, 
        conversation_history: List[Dict[str, str]],
        status: BusinessChatStatus
    ) -> str:
        """
        Generate an AI response based on the conversation history
        
        Args:
            conversation_history: List of conversation messages
            status: Current BusinessChatStatus
            
        Returns:
            AI response text
        """
        # Prepare messages for LLM
        messages = []
        
        # Add system prompt
        messages.append({
            "role": "system",
            "content": self._get_system_prompt()
        })
        
        # Add conversation history (excluding system messages)
        for msg in conversation_history:
            if msg["role"] != "system":
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
        
        # Add status information to help guide the response
        messages.append({
            "role": "system",
            "content": f"""
            Current status:
            - Stage: {status.stage}
            - Current question: {self.all_questions_by_id.get(status.current_question, {}).get('question') if status.current_question else 'None'}
            - Progress: {status.progress * 100:.1f}%
            
            Please respond to the user's last message. If appropriate, guide them to the next question:
            {self._get_next_question(status) or 'No more questions, summarize findings.'}
            """
        })
        
        try:
            # Call the LLM
            if self.config.llm_provider in ["openai", "claude"]:
                response = self.llm_client.chat.completions.create(
                    model=self.llm_model,
                    messages=messages,
                    temperature=0.7
                )
                return response.choices[0].message.content
            elif self.config.llm_provider == "deepseek":
                response = self.llm_client.chat.completions.create(
                    model=self.llm_model,
                    messages=messages,
                    temperature=0.7
                )
                return response.choices[0].message.content
            else:
                raise ValueError(f"Unsupported LLM provider: {self.config.llm_provider}")
        except Exception as e:
            logger.error(f"Error generating AI response: {e}")
            return "Lo siento, tuve un problema al generar una respuesta. ¿Podrías reformular tu pregunta?"
    
    async def generate_summary(self, session_id: str) -> Dict[str, Any]:
        """
        Generate a summary of the business understanding process
        
        Args:
            session_id: ID of the chat session
            
        Returns:
            Dictionary with summary data
        """
        # Get current session
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
        
        # Prepare the data for the summary
        summary_data = {
            "business_understanding": status.results.get(Stage.BUSINESS_UNDERSTANDING, {}),
            "communication_needs": status.results.get(Stage.COMMUNICATION_NEEDS, {}),
            "communication_strategy": status.results.get(Stage.COMMUNICATION_STRATEGY, {})
        }
        
        # Generate a conversational summary using the LLM
        summary_prompt = f"""
        Basado en la información recopilada en nuestra conversación sobre este negocio, 
        por favor genera un resumen estructurado que abarque las tres etapas del proceso:
        
        1. ENTENDIMIENTO DEL NEGOCIO
        {json.dumps(summary_data['business_understanding'], indent=2, ensure_ascii=False)}
        
        2. NECESIDAD / OPORTUNIDAD DE COMUNICACIÓN
        {json.dumps(summary_data['communication_needs'], indent=2, ensure_ascii=False)}
        
        3. ESTRATEGIA DE COMUNICACIÓN
        {json.dumps(summary_data['communication_strategy'], indent=2, ensure_ascii=False)}
        
        Genera un resumen conversacional que destaque los puntos más importantes de cada etapa,
        las fortalezas del negocio, las oportunidades clave y recomendaciones estratégicas.
        Utiliza un tono profesional pero amigable, y estructura la información de manera clara.
        """
        
        try:
            # Call the LLM
            if self.config.llm_provider in ["openai", "claude"]:
                response = self.llm_client.chat.completions.create(
                    model=self.llm_model,
                    messages=[
                        {"role": "system", "content": "Eres un consultor de negocios experto que genera resúmenes claros y profesionales."},
                        {"role": "user", "content": summary_prompt}
                    ],
                    temperature=0.7
                )
                conversational_summary = response.choices[0].message.content
            elif self.config.llm_provider == "deepseek":
                response = self.llm_client.chat.completions.create(
                    model=self.llm_model,
                    messages=[
                        {"role": "system", "content": "Eres un consultor de negocios experto que genera resúmenes claros y profesionales."},
                        {"role": "user", "content": summary_prompt}
                    ],
                    temperature=0.7
                )
                conversational_summary = response.choices[0].message.content
            else:
                raise ValueError(f"Unsupported LLM provider: {self.config.llm_provider}")
            
            # Add to conversation
            await self.redis.add_message(session_id, "assistant", conversational_summary)
            
            # Update status to indicate completion
            status.stage = Stage.COMPLETED
            await self.redis.update_session_metadata(
                session_id, 
                {"status": status.model_dump(), "summary": conversational_summary}
            )
            
            return {
                "summary": conversational_summary,
                "data": summary_data,
                "status": status.model_dump()
            }
            
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return {
                "summary": "Lo siento, tuve un problema al generar el resumen.",
                "data": summary_data,
                "status": status.model_dump()
            } 