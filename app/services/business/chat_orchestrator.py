import os
import logging
import json
from typing import Dict, List, Optional, Any, Tuple
from sqlalchemy.orm import Session
from datetime import datetime

from app.services.business.chat_intent_classifier import ChatIntentClassifier
from app.services.cache.redis_service import RedisChatService
from app.models.business.business_idea import BusinessIdea
from app.models.business.business_progress import BusinessProgress, StepStatus
from app.services.business.business_understanding.brief_service import BriefService

from openai import OpenAI

logger = logging.getLogger(__name__)

class ChatOrchestrator:
    """
    Servicio para gestionar y orquestar la conversación general con el usuario,
    redirigiendo a los módulos específicos según la intención y el progreso.
    """
    
    def __init__(
        self,
        db: Session,
        redis_service: RedisChatService,
        api_key: Optional[str] = None
    ):
        """
        Inicializa el orquestador de chat.
        
        Args:
            db: Sesión de base de datos
            redis_service: Servicio de caché para gestionar sesiones de chat
            api_key: API key para OpenAI (opcional)
        """
        self.db = db
        self.redis_service = redis_service
        self.intent_classifier = ChatIntentClassifier(api_key=api_key)
        self.openai_client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        
        # Servicios específicos
        self.brief_service = BriefService(api_key=api_key)
    
    async def process_message(
        self,
        message: str,
        business_id: str,
        user_id: str,
        session_id: Optional[str] = None,
        business_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Procesa un mensaje del usuario y coordina la respuesta apropiada.
        
        Args:
            message: Mensaje del usuario
            business_id: ID del negocio
            user_id: ID del usuario
            session_id: ID de la sesión de chat (opcional)
            business_data: Datos completos del business_idea para sugerencias
            
        Returns:
            Diccionario con la información de la respuesta
        """
        try:
            # Verificar que el negocio existe y pertenece al usuario
            business = self.db.query(BusinessIdea).filter(
                BusinessIdea.id == business_id,
                BusinessIdea.user_id == user_id
            ).first()
            
            if not business:
                return {
                    "error": True,
                    "detail": "Business not found or access denied",
                    "status_code": 404
                }
            
            # Obtener o crear el registro de progreso
            progress = self._get_or_create_progress(business_id)
            completed_steps = progress.get_completed_steps()
            next_step = progress.get_next_step()
            
            # Gestionar sesión
            if session_id:
                # Verificar que la sesión existe
                session = await self.redis_service.get_session(session_id)
                if not session:
                    return {
                        "error": True,
                        "detail": "Session not found",
                        "status_code": 404
                    }
                
                # Verificar que la sesión pertenece al usuario y negocio
                if session.user_id != user_id or session.business_id != business_id:
                    return {
                        "error": True,
                        "detail": "Access denied for this session",
                        "status_code": 403
                    }
            else:
                # Crear nueva sesión
                session = await self.redis_service.create_session(
                    user_id=user_id,
                    business_id=business_id,
                    metadata={
                        "orchestrator_state": {
                            "current_mode": "general",
                            "active_module": None
                        }
                    },
                    initial_messages=[{
                        "role": "system",
                        "content": self._get_system_prompt(completed_steps, next_step),
                        "timestamp": datetime.now().isoformat()
                    }]
                )
                
                # Guardar welcome message
                welcome_message = await self._generate_welcome_message(business, completed_steps, next_step)
                await self.redis_service.add_message(
                    session.id,
                    {
                        "role": "assistant",
                        "content": welcome_message,
                        "timestamp": datetime.now().isoformat()
                    }
                )
            
            # Añadir mensaje del usuario a la sesión
            await self.redis_service.add_message(
                session.id,
                {
                    "role": "user",
                    "content": message,
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            # Obtener historial de mensajes para clasificación
            chat_history = [
                {"role": msg["role"], "content": msg["content"]}
                for msg in session.messages if msg["role"] in ["user", "assistant"]
            ]
            
            # Clasificar intención
            intent_result = await self.intent_classifier.classify_intent(
                message=message,
                conversation_history=chat_history,
                completed_steps=completed_steps,
                next_step=next_step
            )
            
            # Obtener el estado actual del orquestador
            orchestrator_state = session.metadata.get("orchestrator_state", {
                "current_mode": "general",
                "active_module": None
            })
            
            # Decidir acción basada en la intención y estado actual
            response, new_state = await self._handle_intent(
                intent_result=intent_result,
                current_state=orchestrator_state,
                message=message,
                business_id=business_id,
                user_id=user_id,
                session=session,
                progress=progress,
                business_data=business_data
            )
            
            # Actualizar estado del orquestador
            await self.redis_service.update_session_metadata(
                session_id=session.id,
                metadata={"orchestrator_state": new_state}
            )
            
            # Añadir respuesta al historial
            await self.redis_service.add_message(
                session.id,
                {
                    "role": "assistant", 
                    "content": response,
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            return {
                "session_id": session.id,
                "reply": response,
                "intent": intent_result.get("intent"),
                "confidence": intent_result.get("confidence"),
                "next_step": next_step,
                "completed_steps": completed_steps,
                "mode": new_state["current_mode"],
                "active_module": new_state["active_module"]
            }
            
        except Exception as e:
            logger.error(f"Error en el orquestador de chat: {str(e)}")
            return {
                "error": True,
                "detail": f"Error processing message: {str(e)}",
                "status_code": 500
            }
    
    async def _handle_intent(
        self,
        intent_result: Dict[str, Any],
        current_state: Dict[str, Any],
        message: str,
        business_id: str,
        user_id: str,
        session: Any,
        progress: BusinessProgress,
        business_data: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Maneja la intención detectada y determina la acción a tomar.
        
        Returns:
            Tupla con (respuesta, nuevo_estado)
        """
        intent = intent_result.get("intent", "none")
        current_mode = current_state.get("current_mode", "general")
        active_module = current_state.get("active_module")
        
        # Preparar contexto para respuestas
        completed_steps = progress.get_completed_steps()
        next_step = progress.get_next_step()
        
        # Verificar si el modo actual indica que estamos en transición al brief
        if current_mode == "redirect_to_brief" or active_module == "brief":
            # En lugar de procesar aquí, debemos indicar al cliente que debe usar el endpoint de brief
            # Este caso será manejado directamente en el endpoint de chat
            return "Para continuar con el proceso de brief, por favor utiliza el endpoint dedicado para brief.", {
                "current_mode": "redirect_to_brief",
                "active_module": "brief",
                "business_data": business_data
            }
        
        # Para usuarios nuevos, dirigir automáticamente al brief en su primera interacción
        is_new_user = not completed_steps and next_step == "brief"
        first_message = len(session.messages) <= 3  # Sistema + bienvenida + mensaje usuario
        
        if is_new_user and first_message and current_mode == "general":
            # En lugar de gestionar el brief aquí, indicamos que debe redirigirse al endpoint específico
            return "Vamos a comenzar con el Brief para definir tu negocio. Te haré una serie de preguntas para entender mejor tu idea. Por favor, utiliza el endpoint dedicado para brief.", {
                "current_mode": "redirect_to_brief",
                "active_module": "brief",
                "business_data": business_data
            }
            
        # Buscar module_switch en la intención para cambiar de modo/módulo
        if intent.startswith("module_switch_"):
            target_module = intent.split("_")[-1]
            
            # Verificar si el módulo solicitado está disponible según el progreso
            if target_module == "brief":
                # Redirigir al endpoint de brief
                return "Para acceder al módulo de brief, por favor utiliza el endpoint dedicado para brief.", {
                    "current_mode": "redirect_to_brief", 
                    "active_module": "brief",
                    "business_data": business_data
                }
            elif target_module == "canvas" and "brief" not in completed_steps:
                return "Primero es necesario completar el Brief antes de trabajar en el Business Canvas.", current_state
            elif target_module == "competitive" and "brief" not in completed_steps:
                return "Primero es necesario completar el Brief antes de realizar un análisis competitivo.", current_state
            else:
                # Cambiar al módulo solicitado
                return f"Cambiando al módulo de {target_module}.", {
                    "current_mode": "module",
                    "active_module": target_module
                }
                
        # Si no hay un manejo específico para la intención, usar respuesta general
        response = await self._generate_general_response(
            intent=intent,
            message=message,
            session=session,
            completed_steps=completed_steps,
            next_step=next_step
        )
        
        return response, current_state
    
    def _get_or_create_progress(self, business_id: str) -> BusinessProgress:
        """Obtiene o crea un registro de progreso para el negocio"""
        progress = self.db.query(BusinessProgress).filter(
            BusinessProgress.business_id == business_id
        ).first()
        
        if not progress:
            progress = BusinessProgress(business_id=business_id)
            self.db.add(progress)
            self.db.commit()
            self.db.refresh(progress)
            
        return progress
    
    def _get_system_prompt(self, completed_steps: List[str], next_step: str) -> str:
        """Genera el prompt del sistema para la conversación general"""
        
        steps_context = ""
        if completed_steps:
            steps_context += f"El usuario ya ha completado: {', '.join(completed_steps)}.\n"
        
        if next_step != "all_completed":
            steps_context += f"El siguiente paso recomendado es: {next_step}.\n"
        else:
            steps_context += "El usuario ha completado todos los pasos principales del proceso.\n"
        
        return f"""Eres Lattice, un asistente de negocios profesional que ayuda a los emprendedores a desarrollar y mejorar sus ideas de negocio.
Tu objetivo es guiar al usuario a través de un proceso estructurado para definir y validar su negocio:

1. Brief: Define el propósito y la propuesta de valor del negocio
2. Business Canvas: Estructura el modelo de negocio completo
3. Análisis Competitivo: Evalúa el mercado y los competidores

Contexto del usuario:
{steps_context}

Guía al usuario de manera amigable pero profesional. Cuando detectes que quiere trabajar en uno de los módulos principales (brief, canvas o análisis competitivo), recomienda seguir la secuencia lógica, pero sé flexible.

Prioriza ayudarle a completar el siguiente paso recomendado, pero responde cualquier consulta general sobre su negocio. Sé empático y constructivo en todo momento.
"""
    
    async def _generate_welcome_message(self, business: BusinessIdea, completed_steps: List[str], next_step: str) -> str:
        """Genera un mensaje de bienvenida personalizado"""
        
        # Para usuarios nuevos que solo tienen el nombre del negocio
        is_new_user = not completed_steps and next_step == "brief" and (not hasattr(business, 'progress') or business.progress is None)
        
        if is_new_user:
            welcome_template = f"""¡Bienvenido a Lattice! 👋

Soy tu asistente inteligente especializado en ayudarte a desarrollar y estructurar tu idea de negocio "{business.title}".

Lattice es una plataforma que te guiará a través de un proceso paso a paso para convertir tu idea en un plan de negocio sólido:

1️⃣ **Brief**: Vamos a definir el propósito y la propuesta de valor
2️⃣ **Business Canvas**: Estructuraremos tu modelo de negocio 
3️⃣ **Análisis Competitivo**: Evaluaremos el mercado y la competencia

Comenzaremos ahora con el Brief, que es el primer paso fundamental para definir la esencia de tu negocio. Los demás módulos se habilitarán una vez que hayas completado el Brief.

Empecemos con la primera pregunta: ¿Cuál es el problema principal que tu negocio "{business.title}" busca resolver?"""
            return welcome_template
        
        # Mensaje estándar para usuarios que ya tienen algún progreso
        welcome_template = f"""¡Hola! Soy Lattice, tu asistente para desarrollar y mejorar tu idea de negocio "{business.title}".

Estoy aquí para ayudarte a través de un proceso estructurado:
1. Brief: Define el propósito y la propuesta de valor
2. Business Canvas: Estructura tu modelo de negocio
3. Análisis Competitivo: Evalúa el mercado y la competencia

"""
        
        if not completed_steps:
            welcome_template += f"Aún no has completado ninguno de los pasos. Te recomiendo comenzar con el Brief. ¿Te gustaría empezar ahora?"
        elif next_step == "all_completed":
            welcome_template += f"¡Felicidades! Has completado todos los pasos principales. ¿En qué más puedo ayudarte hoy?"
        else:
            completed = ", ".join(completed_steps)
            welcome_template += f"Has completado: {completed}. Tu próximo paso recomendado es el {next_step}. ¿Te gustaría trabajar en eso ahora?"
            
        return welcome_template
    
    def _build_feedback_prompt(self, business_id: str, completed_steps: List[str], next_step: str) -> str:
        """Construye un prompt para generar feedback sobre el progreso"""
        
        steps_context = ""
        if completed_steps:
            steps_context += f"El usuario ha completado: {', '.join(completed_steps)}.\n"
        else:
            steps_context += "El usuario aún no ha completado ningún paso.\n"
        
        if next_step != "all_completed":
            steps_context += f"El siguiente paso recomendado es: {next_step}.\n"
        else:
            steps_context += "El usuario ha completado todos los pasos principales del proceso.\n"
        
        return f"""Eres Lattice, un asistente de negocios que proporciona feedback constructivo sobre el progreso del usuario.

Contexto del progreso:
{steps_context}

El usuario está pidiendo feedback sobre su avance. Proporciona una evaluación positiva pero honesta de su progreso, destacando:
1. Lo que ha logrado hasta ahora (si ha completado pasos)
2. Por qué el siguiente paso es importante para su negocio
3. Beneficios específicos que obtendrá al completar el proceso completo

Sé motivador y enfatiza el valor de cada etapa. Ofrece consejos prácticos relevantes a su etapa actual.
Limita tu respuesta a un máximo de 3-4 párrafos cortos.
"""
    
    def _build_general_response_prompt(self, business_id: str, completed_steps: List[str], next_step: str) -> str:
        """Construye un prompt para responder a preguntas generales"""
        
        steps_context = ""
        if completed_steps:
            steps_context += f"El usuario ha completado: {', '.join(completed_steps)}.\n"
        else:
            steps_context += "El usuario aún no ha completado ningún paso.\n"
        
        if next_step != "all_completed":
            steps_context += f"El siguiente paso recomendado es: {next_step}.\n"
        else:
            steps_context += "El usuario ha completado todos los pasos principales del proceso.\n"
        
        return f"""Eres Lattice, un asistente de negocios profesional y conciso.

Contexto del progreso:
{steps_context}

Responde a la pregunta del usuario de manera clara y breve. Si su consulta está relacionada con aspectos del negocio que aún no ha definido (en pasos que no ha completado), menciona sutilmente que completar esos pasos le ayudará a obtener una respuesta más precisa.

Mantén tus respuestas enfocadas y prácticas. Si no puedes responder con certeza, sé honesto y sugiere qué información adicional sería útil.

Limita tu respuesta a 1-2 párrafos cortos y evita explicaciones extensas a menos que sean absolutamente necesarias.
"""
    
    async def _generate_general_response(
        self,
        intent: str,
        message: str,
        session: Any,
        completed_steps: List[str],
        next_step: str
    ) -> str:
        """
        Genera una respuesta general basada en la intención y el contexto.
        
        Args:
            intent: Intención detectada
            message: Mensaje del usuario
            session: Sesión actual
            completed_steps: Pasos completados
            next_step: Próximo paso recomendado
            
        Returns:
            Respuesta generada
        """
        if intent == "brief":
            # Verificar si ya tienen un brief completado
            if "brief" in completed_steps:
                return "Ya has completado el brief. Para revisarlo o modificarlo, utiliza el endpoint dedicado para brief."
            else:
                # Iniciar proceso de brief
                return "Para comenzar con el brief, que es el primer paso para definir tu negocio, utiliza el endpoint dedicado para brief."
                
        elif intent == "business_canvas":
            # Verificar si ya han completado el paso previo
            if "brief" not in completed_steps:
                return "Antes de trabajar en el Business Canvas, deberíamos completar el Brief. ¿Te gustaría hacer eso primero utilizando el endpoint dedicado?"
            elif "business_canvas" in completed_steps:
                return "Ya has creado tu Business Canvas. ¿Quieres revisarlo o modificarlo?"
            else:
                return "Vamos a trabajar en tu Business Canvas. Esto te ayudará a definir tu modelo de negocio de manera estructurada."
                
        elif intent == "competitive_analysis":
            # Verificar si ya han completado los pasos previos
            if "business_canvas" not in completed_steps:
                return "Para hacer un análisis competitivo efectivo, primero necesitamos completar el Business Canvas. ¿Quieres trabajar en eso primero?"
            elif "competitive_analysis" in completed_steps:
                return "Ya hemos analizado tu competencia. ¿Quieres revisar los resultados o actualizar el análisis?"
            else:
                return "Vamos a analizar tu competencia. Esto te ayudará a entender tu posición en el mercado y a identificar oportunidades."
                
        elif intent == "next_steps":
            if next_step == "brief":
                return "Tu próximo paso es completar el Brief, que es fundamental para definir la esencia de tu negocio. Para comenzar, utiliza el endpoint dedicado para brief."
            elif next_step == "business_canvas":
                return "Tu próximo paso es crear el Business Canvas, que te ayudará a estructurar tu modelo de negocio. ¿Quieres empezar?"
            elif next_step == "competitive_analysis":
                return "Tu próximo paso es realizar un Análisis Competitivo, que te permitirá entender tu posición en el mercado. ¿Comenzamos?"
            else:
                return "¡Felicidades! Has completado todos los pasos principales. Ahora podríamos profundizar en aspectos específicos de tu negocio. ¿Qué te interesa explorar?"
                
        elif intent == "feedback":
            # Generar feedback basado en el progreso
            feedback_prompt = self._build_feedback_prompt(session.business_id, completed_steps, next_step)
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": feedback_prompt},
                    {"role": "user", "content": message}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            return response.choices[0].message.content
            
        else:  # general_question o none
            # Responder con información general o aclarar
            general_prompt = self._build_general_response_prompt(session.business_id, completed_steps, next_step)
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": general_prompt},
                    {"role": "user", "content": message}
                ],
                temperature=0.7,
                max_tokens=300
            )
            
            return response.choices[0].message.content 