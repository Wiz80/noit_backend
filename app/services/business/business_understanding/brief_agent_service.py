"""
CrewAI-powered Business Brief Service
Intelligent chat system for conducting business brief interviews using multiple AI agents
"""
import json
import logging
import os
import httpx
import asyncio
from typing import Dict, List, Optional, Any, Tuple, Union
from datetime import datetime

from crewai import Agent, Crew, Task, Process
from crewai.memory import LongTermMemory
from pydantic import BaseModel, Field

# LLM imports for different providers
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI

# Import brief suggestions utilities
from app.utils.brief_suggestions import get_suggestion_answer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# LLM Configuration Manager
class LLMConfig:
    """Configuration manager for different LLM providers"""
    
    PROVIDER_CONFIGS = {
        # OpenAI models
        "gpt-4o": {"provider": "openai", "model": "gpt-4o"},
        "gpt-4o-mini": {"provider": "openai", "model": "gpt-4o-mini"},
        "gpt-4-turbo": {"provider": "openai", "model": "gpt-4-turbo"},
        "gpt-3.5-turbo": {"provider": "openai", "model": "gpt-3.5-turbo"},
        
        # Anthropic models
        "claude-3-5-sonnet-20241022": {"provider": "anthropic", "model": "claude-3-5-sonnet-20241022"},
        "claude-3-5-haiku-20241022": {"provider": "anthropic", "model": "claude-3-5-haiku-20241022"},
        "claude-3-opus-20240229": {"provider": "anthropic", "model": "claude-3-opus-20240229"},
        "claude-3-sonnet-20240229": {"provider": "anthropic", "model": "claude-3-sonnet-20240229"},
        
        # DeepSeek models (using OpenAI-compatible API)
        "deepseek-chat": {"provider": "deepseek", "model": "deepseek-chat"},
        "deepseek-coder": {"provider": "deepseek", "model": "deepseek-coder"},
        
        # Google models
        "gemini-1.5-pro": {"provider": "google", "model": "gemini-1.5-pro"},
        "gemini-1.5-flash": {"provider": "google", "model": "gemini-1.5-flash"},
        "gemini-pro": {"provider": "google", "model": "gemini-pro"},
    }
    
    @classmethod
    def create_llm(cls, model_name: str = "claude-3-5-sonnet-20241022", **kwargs):
        """
        Create an LLM instance based on the model name
        
        Args:
            model_name: Name of the model to use
            **kwargs: Additional parameters for the LLM
            
        Returns:
            LLM instance
        """
        if model_name not in cls.PROVIDER_CONFIGS:
            logger.warning(f"Model {model_name} not found in configurations. Using default claude-3-5-sonnet-20241022")
            model_name = "claude-3-5-sonnet-20241022"
        
        config = cls.PROVIDER_CONFIGS[model_name]
        provider = config["provider"]
        model = config["model"]
        
        # Default parameters
        default_params = {
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 4000),
        }
        
        try:
            if provider == "openai":
                return ChatOpenAI(
                    model=model,
                    api_key=os.getenv("OPENAI_API_KEY"),
                    **default_params
                )
            
            elif provider == "anthropic":
                return ChatAnthropic(
                    model=model,
                    api_key=os.getenv("ANTHROPIC_API_KEY"),
                    **default_params
                )
            
            elif provider == "deepseek":
                return ChatOpenAI(
                    model=model,
                    api_key=os.getenv("DEEPSEEK_API_KEY"),
                    base_url="https://api.deepseek.com/v1",
                    **default_params
                )
            
            elif provider == "google":
                return ChatGoogleGenerativeAI(
                    model=model,
                    google_api_key=os.getenv("GOOGLE_API_KEY"),
                    temperature=default_params["temperature"],
                    max_output_tokens=default_params["max_tokens"]
                )
            
            else:
                raise ValueError(f"Unknown provider: {provider}")
                
        except Exception as e:
            logger.error(f"Error creating LLM for {model_name}: {str(e)}")
            logger.info("Falling back to default OpenAI model")
            return ChatOpenAI(
                model="gpt-4o-mini",
                api_key=os.getenv("OPENAI_API_KEY"),
                **default_params
            )
    
    @classmethod
    def get_available_models(cls) -> Dict[str, str]:
        """Get list of available models grouped by provider"""
        models_by_provider = {}
        for model, config in cls.PROVIDER_CONFIGS.items():
            provider = config["provider"]
            if provider not in models_by_provider:
                models_by_provider[provider] = []
            models_by_provider[provider].append(model)
        return models_by_provider

# Load phases from the phases.txt structure
phases = {
    "ETAPA 1: ENTENDIMIENTO DEL NEGOCIO": [
        "¿Qué hace la empresa? ¿Cuál es su propósito?",
        "¿Cuál es su propuesta de valor?",
        "¿Qué productos/servicios ofrece y a quiénes?",
        "¿Cuál es el cliente ideal?",
        "¿Qué problema resuelve?",
        "¿Qué los hace diferentes frente a la competencia?",
        "¿Qué desafíos u oportunidades clave enfrentan hoy?",
        "¿En qué industria se encuentra?"
    ],
    "ETAPA 2: NECESIDAD / OPORTUNIDAD DE COMUNICACIÓN": [
        "¿Qué está ocurriendo alrededor del negocio o mercado que hace necesaria esta comunicación?",
        "¿Cuál es la oportunidad de negocio concreta?",
        "¿Qué objetivo tiene esta comunicación (posicionamiento, lanzamiento, awareness, conversión, etc.)?"
    ],
    "ETAPA 3: ESTRATEGIA DE COMUNICACIÓN": [
        "¿Cuál es la idea o mensaje clave a comunicar?",
        "¿A quién va dirigida esta comunicación?",
        "¿Qué valores o características tiene esta audiencia que deberíamos considerar?",
        "¿Por qué nos creerían?",
        "¿Qué hace nuestra promesa creíble?",
        "¿Cómo vamos a sonar (tono, voz, estilo)?",
        "¿Cuál es el indicador de éxito más importante?",
        "¿Qué cifras o resultados esperamos?",
        "¿Qué queremos que la audiencia piense, sienta o haga después de recibir esta comunicación?",
        "¿Hay limitaciones legales, presupuestarias o de formatos?",
        "¿Canales obligatorios o a evitar?",
        "¿Fechas clave?"
    ]
}

class BriefSessionState(BaseModel):
    """State model for brief session management"""
    current_question_index: int = 0
    current_phase: str = ""
    current_question: str = ""
    answers: Dict[str, Dict[str, str]] = Field(default_factory=dict)
    session_finished: bool = False
    last_suggestion_answer: Optional[str] = None
    last_suggestion_response: Optional[str] = None
    pending_validation: bool = False

class BriefAgentService:
    """
    CrewAI-powered service for conducting intelligent business brief interviews.
    Uses multiple specialized agents to manage the conversation flow.
    """
    
    def __init__(
        self, 
        llm_model: str = "claude-3-5-sonnet-20241022",
        llm_temperature: float = 0.7,
        llm_max_tokens: int = 4000,
        custom_llm: Optional[Any] = None
    ):
        """
        Initialize the Brief Agent Service with configurable LLM
        
        Args:
            llm_model: Model name to use (default: claude-3-5-sonnet-20241022)
            llm_temperature: Temperature for LLM responses (0.0-1.0)
            llm_max_tokens: Maximum tokens for LLM responses
            custom_llm: Custom LLM instance (overrides other LLM settings)
        """
        self.phases = phases
        self.flat_questions = self._flatten_questions()
        self.total_questions = len(self.flat_questions)
        
        # Configure LLM
        if custom_llm:
            self.llm = custom_llm
            self.llm_model = "custom"
        else:
            self.llm = LLMConfig.create_llm(
                model_name=llm_model,
                temperature=llm_temperature,
                max_tokens=llm_max_tokens
            )
            self.llm_model = llm_model
        
        logger.info(f"BriefAgentService initialized with LLM: {self.llm_model}")
        
        # Initialize CrewAI agents
        self._initialize_agents()
        
    def _flatten_questions(self) -> List[Tuple[str, str, str]]:
        """Flatten the phases dictionary into a list of (phase, question, field_mapping) tuples"""
        flat = []
        field_mappings = {
            # ETAPA 1 mappings to business_model fields
            "¿Qué hace la empresa? ¿Cuál es su propósito?": "problem_definition",
            "¿Cuál es su propuesta de valor?": "value_proposition", 
            "¿Qué productos/servicios ofrece y a quiénes?": "products_services",
            "¿Cuál es el cliente ideal?": "customer_persona",
            "¿Qué problema resuelve?": "problem_definition",
            "¿Qué los hace diferentes frente a la competencia?": "competitive_advantage",
            "¿Qué desafíos u oportunidades clave enfrentan hoy?": "challenges_opportunities",
            "¿En qué industria se encuentra?": "industry",
            # ETAPA 2 and 3 don't map to business_model fields directly
        }
        
        for phase, questions in self.phases.items():
            for question in questions:
                field_mapping = field_mappings.get(question, None)
                flat.append((phase, question, field_mapping))
        
        return flat
    
    def _initialize_agents(self):
        """Initialize the CrewAI agents for the brief process"""
        
        # Suggestions Agent - generates contextual suggestions
        self.suggestions_agent = Agent(
            role="Business Brief Suggestions Expert",
            goal="Provide intelligent suggestions and example responses for business brief questions based on available business information",
            backstory="""You are an expert business consultant with extensive experience in helping entrepreneurs 
            define their business models and communication strategies. You excel at asking the right questions 
            and providing contextual suggestions that help business owners think deeply about their ventures.""",
            verbose=True,
            allow_delegation=False,
            llm=self.llm
        )
        
        # Validation Agent - validates user responses
        self.validation_agent = Agent(
            role="Response Validation and Refinement Specialist", 
            goal="Validate user responses and intelligently refine them to be more complete and professional while maintaining the original intent",
            backstory="""You are a skilled business analyst and communication expert who specializes in improving 
            business responses. You understand when responses need enhancement and can intelligently expand on 
            user input to make it more comprehensive without changing the core meaning. You excel at maintaining 
            the user's voice while adding professional context and completeness.""",
            verbose=True,
            allow_delegation=False,
            llm=self.llm
        )
        
        # Flow Control Agent - manages the conversation flow
        self.flow_agent = Agent(
            role="Conversation Flow Manager",
            goal="Manage the overall flow of the brief conversation, ensuring smooth progression through questions",
            backstory="""You are an experienced facilitator who manages structured business conversations. 
            You ensure that each question is properly addressed before moving to the next one, and you 
            maintain the overall coherence of the brief process.""",
            verbose=True,
            allow_delegation=False,
            llm=self.llm
        )
    
    def get_llm_info(self) -> Dict[str, Any]:
        """Get information about the current LLM configuration"""
        return {
            "model": self.llm_model,
            "provider": LLMConfig.PROVIDER_CONFIGS.get(self.llm_model, {}).get("provider", "unknown"),
            "available_models": LLMConfig.get_available_models()
        }
    
    def change_llm(self, new_model: str, temperature: float = 0.7, max_tokens: int = 4000):
        """
        Change the LLM model and reinitialize agents
        
        Args:
            new_model: New model name to use
            temperature: Temperature for the new LLM
            max_tokens: Max tokens for the new LLM
        """
        try:
            self.llm = LLMConfig.create_llm(
                model_name=new_model,
                temperature=temperature,
                max_tokens=max_tokens
            )
            self.llm_model = new_model
            
            # Reinitialize agents with new LLM
            self._initialize_agents()
            
            logger.info(f"Successfully changed LLM to: {new_model}")
        except Exception as e:
            logger.error(f"Error changing LLM to {new_model}: {str(e)}")
            raise
        
    def get_total_questions(self) -> int:
        """Get the total number of questions in the brief"""
        return self.total_questions
        
    def get_current_question(self, index: int) -> Optional[Tuple[str, str]]:
        """Get the current question by index"""
        if 0 <= index < len(self.flat_questions):
            phase, question, _ = self.flat_questions[index]
            return phase, question
        return None
        
    async def run_agent_turn(self, message: str, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main method to process a turn in the brief conversation using CrewAI flow
        
        Args:
            message: User's message
            session_data: Current session state data
            
        Returns:
            Dict containing the response and updated session state
        """
        try:
            # Parse session data
            current_index = session_data.get("current_question_index", 0)
            answers = session_data.get("answers", {})
            business_data = session_data.get("business_idea", {})
            chat_history = session_data.get("langchain_chat_history", [])
            
            # Check if we're starting or continuing
            is_start = current_index == 0 and len(chat_history) == 0
            
            if is_start:
                return self._handle_welcome_flow(current_index, business_data, answers, chat_history)
            else:
                return await self._handle_conversation_flow(message, current_index, business_data, answers, chat_history)
                
        except Exception as e:
            logger.error(f"Error in run_agent_turn: {str(e)}")
            return {
                "reply": "Lo siento, ocurrió un error. Por favor, intenta de nuevo.",
                "updated_current_question_index": session_data.get("current_question_index", 0),
                "updated_answers": session_data.get("answers", {}),
                "updated_chat_history": session_data.get("langchain_chat_history", []),
                "session_finished": False
            }
    
    def _handle_welcome_flow(self, current_index: int, business_data: Dict, answers: Dict, chat_history: List) -> Dict[str, Any]:
        """Handle the welcome message and first question"""
        
        # Get first question
        phase, question = self.get_current_question(current_index)
        
        # Get static suggestion for how to answer
        suggestion_answer = get_suggestion_answer(question)
        
        # Create task only for dynamic suggestion response
        suggestion_response_task = Task(
            description=f"""
            Basándote en la información del negocio: {json.dumps(business_data, indent=2)}
            
            Genera una respuesta de ejemplo para la pregunta: "{question}"
            
            La respuesta debe ser contextual y específica al negocio descrito.
            Si no hay suficiente información del negocio, proporciona una respuesta genérica pero útil.
            """,
            expected_output="Una respuesta de ejemplo clara y contextual a la pregunta",
            agent=self.suggestions_agent
        )
        
        # Create crew and execute only for suggestion_response
        crew = Crew(
            agents=[self.suggestions_agent],
            tasks=[suggestion_response_task],
            process=Process.sequential,
            verbose=False
        )
        
        try:
            result = crew.kickoff()
            
            # Parse result from crew execution
            suggestion_response = suggestion_response_task.output.raw if hasattr(suggestion_response_task.output, 'raw') else str(suggestion_response_task.output)
            
        except Exception as e:
            logger.error(f"Error in CrewAI execution: {str(e)}")
            suggestion_response = "Excelente, continuemos con la siguiente pregunta."
        
        # Create welcome message
        welcome_msg = f"""¡Hola! Bienvenido al proceso de Brief para definir tu negocio y estrategia de comunicación.

Te haré {self.total_questions} preguntas organizadas en 3 etapas:
1. Entendimiento del Negocio
2. Necesidad/Oportunidad de Comunicación  
3. Estrategia de Comunicación

Comenzemos con la primera pregunta:

**{phase}**
**Pregunta:** {question}"""
        
        # Update chat history
        updated_history = chat_history + [
            {"role": "assistant", "content": welcome_msg}
        ]
        
        return {
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
    
    async def _handle_conversation_flow(self, message: str, current_index: int, business_data: Dict, answers: Dict, chat_history: List) -> Dict[str, Any]:
        """Handle ongoing conversation flow with intelligent response refinement"""
        
        # Get current question details
        if current_index >= len(self.flat_questions):
            return self._handle_completion(answers, chat_history)
            
        phase, question, field_mapping = self.flat_questions[current_index]
        
        # Get suggestions for current question to use in validation
        current_suggestion_answer = get_suggestion_answer(question)
        current_suggestion_tasks = [self._create_suggestion_response_task(question, business_data)]
        
        suggestion_crew = Crew(
            agents=[self.suggestions_agent],
            tasks=current_suggestion_tasks,
            process=Process.sequential,
            verbose=False
        )
        
        try:
            suggestion_crew.kickoff()
            current_suggestion_response = current_suggestion_tasks[0].output.raw if hasattr(current_suggestion_tasks[0].output, 'raw') else ""
        except Exception as e:
            logger.error(f"Error generating current suggestions: {str(e)}")
            current_suggestion_response = ""
        
        # Create validation and refinement tasks
        validation_task = Task(
            description=f"""
            Analiza esta respuesta del usuario a la pregunta del brief:
            
            Pregunta: "{question}"
            Respuesta del usuario: "{message}"
            Sugerencia de respuesta disponible: "{current_suggestion_response}"
            
            Tu trabajo es evaluar la respuesta del usuario según estos criterios:
            
            1. RESPUESTA AFIRMATIVA: ¿El usuario está de acuerdo con la sugerencia?
               - Frases como "estoy de acuerdo", "sí", "correcto", "ese ejemplo está bien", "de acuerdo", "exacto", etc.
               - Si es afirmativa, marca usar_sugerencia_como_base = true y necesita_refinamiento = false
            
            2. CALIDAD DE LA RESPUESTA: ¿La respuesta es suficientemente completa?
               - Respuesta BUENA: Tiene detalles específicos, contexto claro, información útil
               - Respuesta BÁSICA: Muy corta, genérica, falta contexto o detalles importantes
               - Respuesta INVÁLIDA: Sin sentido, completamente irrelevante
            
            3. DECISIÓN DE REFINAMIENTO:
               - NO refinar si: es afirmativa a sugerencia O es una respuesta buena/completa
               - SÍ refinar si: es básica/incompleta pero válida
               - Pedir aclaración si: es completamente inválida
            
            IMPORTANTE: 
            - Si la respuesta tiene información específica y relevante, aunque sea breve, NO la refines
            - Solo refina respuestas que son demasiado genéricas o muy pobres en información
            - Las respuestas afirmativas siempre usan la sugerencia sin refinamiento
            
            Responde con JSON en este formato:
            {{
                "es_valida": true/false,
                "calidad_respuesta": "buena"/"basica"/"invalida",
                "es_afirmativa_a_sugerencia": true/false,
                "razon": "explicación breve de la evaluación",
                "necesita_refinamiento": true/false,
                "usar_sugerencia_como_base": true/false
            }}
            """,
            expected_output="JSON con la evaluación inteligente de la respuesta del usuario",
            agent=self.validation_agent
        )
        
        refinement_task = Task(
            description=f"""
            Basándote en la pregunta del brief y la respuesta del usuario:
            
            Pregunta: "{question}"
            Respuesta original del usuario: "{message}"
            Contexto del negocio: {json.dumps(business_data, indent=2)}
            Sugerencia de respuesta disponible: "{current_suggestion_response}"
            
            Tu tarea es refinar y mejorar la respuesta del usuario manteniendo su esencia pero agregando detalles útiles 
            para hacer la respuesta más completa y profesional.
            
            Instrucciones:
            1. Si el usuario está de acuerdo con la sugerencia ("estoy de acuerdo", "sí", "correcto", etc.), 
               usa la sugerencia como base principal y personalízala con el contexto del negocio.
            2. Si la respuesta es original del usuario, mantén esa información como base
            3. Completa los aspectos que puedan estar incompletos usando contexto lógico
            4. Mejora la estructura y claridad de la respuesta
            5. Si la información es muy limitada, expándela de manera razonable
            6. Mantén el tono profesional pero conserva la intención original
            
            La respuesta refinada debe ser lo que realmente se guardará en el brief.
            """,
            expected_output="Una versión refinada y completa de la respuesta del usuario",
            agent=self.validation_agent
        )
        
        # Create crew for validation and refinement
        validation_crew = Crew(
            agents=[self.validation_agent],
            tasks=[validation_task, refinement_task],
            process=Process.sequential,
            verbose=False
        )
        
        try:
            validation_crew.kickoff()
            
            # Get validation result
            validation_output = validation_task.output.raw if hasattr(validation_task.output, 'raw') else str(validation_task.output)
            
            # Get refined response
            refined_response = refinement_task.output.raw if hasattr(refinement_task.output, 'raw') else message
            
            # Try to parse JSON response for validation
            try:
                validation_data = json.loads(validation_output)
            except:
                # Fallback if JSON parsing fails - assume valid and needs refinement
                validation_data = {
                    "es_valida": True, 
                    "calidad_respuesta": "basica",
                    "es_afirmativa_a_sugerencia": False,
                    "razon": "Respuesta procesada", 
                    "necesita_refinamiento": True,
                    "usar_sugerencia_como_base": False
                }
                
        except Exception as e:
            logger.error(f"Error in validation/refinement: {str(e)}")
            # Fallback: use original response and mark as valid
            validation_data = {
                "es_valida": True, 
                "calidad_respuesta": "basica",
                "es_afirmativa_a_sugerencia": False,
                "razon": "Error en procesamiento", 
                "necesita_refinamiento": False,
                "usar_sugerencia_como_base": False
            }
            refined_response = message
        
        # Handle completely invalid responses (only for truly nonsensical responses)
        if not validation_data.get("es_valida", True):
            clarification_msg = f"""No pude entender tu respuesta para la pregunta: "{question}". 

¿Podrías intentar responder de nuevo? Por ejemplo, puedes describir los aspectos básicos relacionados con la pregunta."""
            
            updated_history = chat_history + [
                {"role": "user", "content": message},
                {"role": "assistant", "content": clarification_msg}
            ]
            
            return {
                "reply": clarification_msg,
                "updated_current_question_index": current_index,
                "updated_answers": answers,
                "updated_chat_history": updated_history,
                "session_finished": False,
                "total_questions": self.total_questions,
                "current_question_index": current_index,
                "answer_recorded": False
            }
        
        # Determine final answer based on validation results
        if validation_data.get("es_afirmativa_a_sugerencia", False):
            # User agreed with suggestion - use suggestion directly
            final_answer = current_suggestion_response
            answer_source = "suggestion"
            logger.info("Using suggestion as user agreed with it")
            
        elif validation_data.get("calidad_respuesta") == "buena":
            # Good quality response - use as is without refinement
            final_answer = message
            answer_source = "original"
            logger.info("Using original response as it's good quality")
            
        elif validation_data.get("calidad_respuesta") == "basica" and validation_data.get("necesita_refinamiento", False):
            # Basic response that needs refinement
            final_answer = refined_response
            answer_source = "refined"
            logger.info("Using refined response as original was too basic")
            
        else:
            # Fallback - use original response
            final_answer = message
            answer_source = "original"
            logger.info("Using original response as fallback")
        
        # Valid response - save the final answer
        if phase not in answers:
            answers[phase] = {}
        
        answers[phase][question] = final_answer
        
        # Move to next question
        next_index = current_index + 1
        
        # Check if we just completed ETAPA 1 and trigger business model mapping
        etapa1_completed = False
        business_model_mapping = None
        
        if self.is_phase_completed(next_index, "ETAPA 1: ENTENDIMIENTO DEL NEGOCIO") and not self.is_phase_completed(current_index, "ETAPA 1: ENTENDIMIENTO DEL NEGOCIO"):
            # We just finished ETAPA 1 - execute business model mapping
            logger.info("ETAPA 1 completed - executing business model mapping")
            etapa1_completed = True
            
            try:
                # Create and execute business model mapping task
                mapping_task = self.create_business_model_mapping_task(answers, business_data)
                
                mapping_crew = Crew(
                    agents=[self.validation_agent],
                    tasks=[mapping_task],
                    process=Process.sequential,
                    verbose=False
                )
                
                mapping_crew.kickoff()
                mapping_output = mapping_task.output.raw if hasattr(mapping_task.output, 'raw') else str(mapping_task.output)
                
                # Try to parse the JSON output
                try:
                    business_model_mapping = json.loads(mapping_output)
                    logger.info(f"Successfully generated business model mapping with {len(business_model_mapping)} fields")
                except json.JSONDecodeError:
                    logger.warning("Failed to parse business model mapping JSON, using fallback method")
                    business_model_mapping = self.map_etapa1_to_business_model(answers)
                    
            except Exception as e:
                logger.error(f"Error in business model mapping: {str(e)}")
                # Fallback to simple mapping
                business_model_mapping = self.map_etapa1_to_business_model(answers)
        
        if next_index >= len(self.flat_questions):
            completion_result = self._handle_completion(answers, chat_history + [{"role": "user", "content": message}])
            if business_model_mapping:
                completion_result["business_model_mapping"] = business_model_mapping
                completion_result["etapa1_completed"] = True
            return completion_result
        
        # Get next question
        next_phase, next_question, _ = self.flat_questions[next_index]
        
        # Get static suggestion for next question
        suggestion_answer = get_suggestion_answer(next_question)
        
        # Generate only dynamic suggestion response for next question
        next_suggestion_task = self._create_suggestion_response_task(next_question, business_data)
        
        next_suggestion_crew = Crew(
            agents=[self.suggestions_agent],
            tasks=[next_suggestion_task],
            process=Process.sequential,
            verbose=False
        )
        
        try:
            next_suggestion_crew.kickoff()
            suggestion_response = next_suggestion_task.output.raw if hasattr(next_suggestion_task.output, 'raw') else str(next_suggestion_task.output)
        except Exception as e:
            logger.error(f"Error generating suggestions: {str(e)}")
            suggestion_response = "Perfecto, continuemos con la siguiente pregunta."
        
        # Create response with acknowledgment based on what actually happened
        if answer_source == "suggestion":
            base_msg = "Perfecto, he registrado tu conformidad con la respuesta sugerida."
        elif answer_source == "refined":
            base_msg = f"""Perfecto, he registrado y mejorado tu respuesta: "{final_answer[:100]}..."""
        else:
            base_msg = "Perfecto, he registrado tu respuesta."
        
        # Add special message if ETAPA 1 was just completed
        if etapa1_completed:
            base_msg += f"""

🎉 ¡Excelente! Has completado la **ETAPA 1: ENTENDIMIENTO DEL NEGOCIO**.

He procesado y estructurado toda la información de tu modelo de negocio. Esta información se ha guardado automáticamente y estará disponible para análisis posteriores.

Ahora continuaremos con la siguiente fase:"""
            
            # Make webhook call to Kestra to trigger competitor analysis
            try:
                await self._trigger_kestra_webhook(business_data, business_model_mapping)
                logger.info(f"Successfully triggered Kestra webhook for business {business_data.get('id')}")
            except Exception as e:
                logger.error(f"Failed to trigger Kestra webhook: {str(e)}")
                # Don't fail the conversation, just log the error
        
        response_msg = f"""{base_msg}

**{next_phase}**
**Pregunta:** {next_question}"""
        
        updated_history = chat_history + [
            {"role": "user", "content": message},
            {"role": "assistant", "content": response_msg}
        ]
        
        result = {
            "reply": response_msg,
            "suggestion_answer": suggestion_answer,
            "suggestion_response": suggestion_response,
            "updated_current_question_index": next_index,
            "updated_answers": answers,
            "updated_chat_history": updated_history,
            "session_finished": False,
            "total_questions": self.total_questions,
            "current_question_index": next_index,
            "answer_recorded": True,
            "previous_action_confirmation": f"He guardado tu respuesta para: {question}",
            "answer_source": answer_source,
            "response_quality": validation_data.get("calidad_respuesta", "unknown"),
            "was_affirmative_to_suggestion": validation_data.get("es_afirmativa_a_sugerencia", False),
            "refinement_applied": answer_source == "refined",
            "final_answer": final_answer,
            "original_response": message
        }
        
        # Add business model mapping information if ETAPA 1 was completed
        if etapa1_completed and business_model_mapping:
            result["business_model_mapping"] = business_model_mapping
            result["etapa1_completed"] = True
            result["mapping_success"] = True
        
        return result
    
    def _create_suggestion_response_task(self, question: str, business_data: Dict) -> Task:
        """Create suggestion response task for a given question"""
        
        suggestion_response_task = Task(
            description=f"""
            Basándote en la información del negocio: {json.dumps(business_data, indent=2)}
            
            Genera una respuesta de ejemplo para la pregunta: "{question}"
            
            La respuesta debe ser contextual y específica al negocio descrito.
            Si no hay suficiente información del negocio, proporciona una respuesta genérica pero útil.
            """,
            expected_output="Una respuesta de ejemplo clara y contextual a la pregunta",
            agent=self.suggestions_agent
        )
        
        return suggestion_response_task
    
    def _handle_completion(self, answers: Dict, chat_history: List) -> Dict[str, Any]:
        """Handle brief completion"""
        
        completion_msg = """🎉 ¡Felicitaciones! Has completado todo el proceso de Brief.

He recopilado toda la información sobre tu negocio y estrategia de comunicación. Ahora puedes acceder al reporte final que resume todas tus respuestas organizadas por etapas.

El brief está completo y guardado en tu sesión."""
        
        updated_history = chat_history + [
            {"role": "assistant", "content": completion_msg}
        ]
        
        return {
            "reply": completion_msg,
            "updated_current_question_index": len(self.flat_questions),
            "updated_answers": answers,
            "updated_chat_history": updated_history,
            "session_finished": True,
            "total_questions": self.total_questions,
            "current_question_index": len(self.flat_questions)
        }

    def get_phase_boundaries(self) -> Dict[str, Tuple[int, int]]:
        """Get the start and end indices for each phase"""
        boundaries = {}
        current_index = 0
        
        for phase, questions in self.phases.items():
            start_index = current_index
            end_index = current_index + len(questions) - 1
            boundaries[phase] = (start_index, end_index)
            current_index += len(questions)
        
        return boundaries
    
    def is_phase_completed(self, current_index: int, phase_name: str) -> bool:
        """Check if a specific phase has been completed"""
        boundaries = self.get_phase_boundaries()
        if phase_name not in boundaries:
            return False
        
        start_index, end_index = boundaries[phase_name]
        return current_index > end_index
    
    def map_etapa1_to_business_model(self, answers: Dict[str, Dict[str, str]]) -> Dict[str, str]:
        """
        Map ETAPA 1 answers to BusinessModel fields
        
        Args:
            answers: Dictionary containing all answers organized by phases
            
        Returns:
            Dict with BusinessModel field mappings
        """
        etapa1_phase = "ETAPA 1: ENTENDIMIENTO DEL NEGOCIO"
        if etapa1_phase not in answers:
            return {}
        
        etapa1_answers = answers[etapa1_phase]
        business_model_data = {}
        
        # Field mappings from questions to BusinessModel fields
        field_mappings = {
            "¿Qué hace la empresa? ¿Cuál es su propósito?": "problem_definition",
            "¿Cuál es su propuesta de valor?": "value_proposition", 
            "¿Qué productos/servicios ofrece y a quiénes?": "products_services",
            "¿Cuál es el cliente ideal?": "customer_persona",
            "¿Qué problema resuelve?": "problem_definition",
            "¿Qué los hace diferentes frente a la competencia?": "competitive_advantage",
            "¿Qué desafíos u oportunidades clave enfrentan hoy?": "challenges_opportunities",
            "¿En qué industria se encuentra?": "industry",
        }
        
        # Map each answer to its corresponding BusinessModel field
        for question, answer in etapa1_answers.items():
            if question in field_mappings:
                field_name = field_mappings[question]
                
                # If the field already has content, append the new answer
                if field_name in business_model_data:
                    business_model_data[field_name] += f"\n\n{answer}"
                else:
                    business_model_data[field_name] = answer
        
        logger.info(f"Mapped ETAPA 1 answers to {len(business_model_data)} BusinessModel fields")
        return business_model_data
    
    def create_business_model_mapping_task(self, answers: Dict[str, Dict[str, str]], business_data: Dict) -> Task:
        """
        Create a CrewAI task to generate a comprehensive business model mapping
        """
        etapa1_answers = answers.get("ETAPA 1: ENTENDIMIENTO DEL NEGOCIO", {})
        
        task = Task(
            description=f"""
            Analiza las respuestas de la ETAPA 1 del brief de negocio y crea un mapeo estructurado para el modelo de negocio.
            
            Contexto del negocio: {json.dumps(business_data, indent=2)}
            
            Respuestas de ETAPA 1:
            {json.dumps(etapa1_answers, indent=2, ensure_ascii=False)}
            
            Tu tarea es estructurar y optimizar estas respuestas para los siguientes campos del modelo de negocio:
            
            1. problem_definition: Definición clara del problema que resuelve y propósito de la empresa
            2. value_proposition: Propuesta de valor única y diferenciadora
            3. products_services: Productos y servicios específicos que ofrece
            4. customer_persona: Descripción detallada del cliente ideal
            5. competitive_advantage: Ventajas competitivas y diferenciadores clave
            6. challenges_opportunities: Desafíos y oportunidades identificados
            7. industry: Industria y sector en el que opera
            
            Instrucciones:
            - Sintetiza y organiza la información de manera coherente
            - Elimina redundancias pero mantén información valiosa
            - Usa un lenguaje profesional y estructurado
            - Asegúrate de que cada campo sea completo y útil para análisis posterior
            
            Responde con JSON en este formato:
            {{
                "problem_definition": "texto optimizado",
                "value_proposition": "texto optimizado", 
                "products_services": "texto optimizado",
                "customer_persona": "texto optimizado",
                "competitive_advantage": "texto optimizado",
                "challenges_opportunities": "texto optimizado",
                "industry": "texto optimizado"
            }}
            """,
            expected_output="JSON estructurado con el mapeo optimizado del modelo de negocio",
            agent=self.validation_agent
        )
        
        return task

    async def _trigger_kestra_webhook(self, business_data: Dict, business_model_mapping: Dict):
        """
        Trigger Kestra webhook to start competitor analysis after ETAPA 1 completion
        
        Args:
            business_data: Business information from the session
            business_model_mapping: Mapped business model data from ETAPA 1
        """
        try:
            kestra_host = os.getenv("KESTRA_HOST", "http://localhost:8080")
            # Get webhook configuration from environment
            kestra_webhook_url = f"{kestra_host}/api/v1/executions/webhook/noit.backend/start-competitor-analysis/competitor_analysis_trigger"
            
            # Prepare webhook payload
            webhook_payload = {
                "event": "business_model_completed",
                "business_id": business_data.get("id"),
                "business_title": business_data.get("title", "Unknown"),
                "industry": business_model_mapping.get("industry", "Unknown"),
                "triggered_by": "brief_etapa1_completion",
                "timestamp": datetime.now().isoformat(),
                "business_model_data": business_model_mapping
            }
            
            # Make async HTTP request to Kestra webhook
            timeout = httpx.Timeout(30.0)  # 30 seconds timeout
            
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    kestra_webhook_url,
                    json=webhook_payload,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "Brief-Agent-Service/1.0"
                    }
                )
                
                if response.status_code in [200, 201, 202]:
                    logger.info(f"Successfully triggered Kestra webhook for business {business_data.get('id')}")
                    logger.info(f"Kestra response: {response.status_code} - {response.text[:200]}")
                else:
                    logger.warning(f"Kestra webhook returned status {response.status_code}: {response.text[:200]}")
                    
        except httpx.TimeoutException:
            logger.error(f"Timeout calling Kestra webhook for business {business_data.get('id')}")
        except httpx.RequestError as e:
            logger.error(f"Request error calling Kestra webhook: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error calling Kestra webhook: {str(e)}")
            # Don't raise the error to avoid breaking the conversation flow


# Helper functions for backwards compatibility
def generate_suggestion_answer(
    question: str, 
    business_data: Dict, 
    llm_model: str = "claude-3-5-sonnet-20241022"
) -> str:
    """
    Get a static suggestion answer for a question (no longer generates dynamically for performance)
    
    Args:
        question: The question to get suggestion for
        business_data: Business context data (kept for compatibility but not used)
        llm_model: LLM model (kept for compatibility but not used)
    """
    return get_suggestion_answer(question)

def generate_suggestion_response(
    question: str, 
    business_data: Dict, 
    llm_model: str = "claude-3-5-sonnet-20241022"
) -> str:
    """
    Generate a dynamic suggestion response for a question
    
    Args:
        question: The question to generate suggestion for
        business_data: Business context data
        llm_model: LLM model to use (default: claude-3-5-sonnet-20241022)
    """
    service = BriefAgentService(llm_model=llm_model)
    task = service._create_suggestion_response_task(question, business_data)
    
    try:
        crew = Crew(
            agents=[service.suggestions_agent],
            tasks=[task],
            process=Process.sequential,
            verbose=False
        )
        result = crew.kickoff()
        return task.output.raw if hasattr(task.output, 'raw') else str(task.output)
    except Exception as e:
        logger.error(f"Error generating suggestion response: {str(e)}")
        return "Excelente respuesta. Continuemos con la siguiente pregunta."

# LLM Configuration Functions
def get_available_llm_models() -> Dict[str, List[str]]:
    """Get all available LLM models grouped by provider"""
    return LLMConfig.get_available_models()

def validate_llm_model(model_name: str) -> bool:
    """Validate if a model name is supported"""
    return model_name in LLMConfig.PROVIDER_CONFIGS

def create_brief_service_with_custom_llm(
    llm_model: str = "claude-3-5-sonnet-20241022",
    temperature: float = 0.7,
    max_tokens: int = 4000
) -> BriefAgentService:
    """
    Factory function to create BriefAgentService with specific LLM configuration
    
    Args:
        llm_model: Model name to use
        temperature: LLM temperature (0.0-1.0)
        max_tokens: Maximum tokens for responses
        
    Returns:
        Configured BriefAgentService instance
    """
    return BriefAgentService(
        llm_model=llm_model,
        llm_temperature=temperature,
        llm_max_tokens=max_tokens
    ) 