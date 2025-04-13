import os
import json
import logging
import random
import tiktoken
from typing import Optional, List, Dict, Any
from openai import OpenAI
from datetime import datetime
import uuid
from app.services.storage.minio_service import MinioService

# Configuración básica y de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Configuración del cliente y tokenización
# -----------------------------------------------------------------------------
MAX_TOKENS_GPT4O = 8192  # Ajusta según el límite del modelo

def get_encoder():
    """
    Retorna un codificador apropiado para el modelo.
    Se intenta con "gpt-4" y se usa "gpt-3.5-turbo" como fallback.
    """
    try:
        return tiktoken.encoding_for_model("gpt-4")
    except KeyError:
        return tiktoken.encoding_for_model("gpt-3.5-turbo")

ENCODER = get_encoder()

def count_tokens(messages: List[dict]) -> int:
    """
    Calcula la cantidad aproximada de tokens usados por la lista de mensajes.
    Cada mensaje debe tener 'role' y 'content'.
    """
    total_tokens = 0
    for msg in messages:
        total_tokens += len(ENCODER.encode(msg.get("content", "")))
    return total_tokens

# -----------------------------------------------------------------------------
# Definición de fases y preguntas (estructura del brief)
# -----------------------------------------------------------------------------
phases = {
    "ETAPA 1: ENTENDIMIENTO DEL NEGOCIO": [
        "¿Qué hace la empresa? ¿Cuál es su propósito?",
        "¿Cuál es su propuesta de valor?",
        "¿Qué productos/servicios ofrece y a quiénes?",
        "¿Cuál es el cliente ideal?",
        "¿Qué problema resuelve?",
        "¿Qué los hace diferentes frente a la competencia?",
        "¿Qué desafíos u oportunidades clave enfrentan hoy?"
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

# -----------------------------------------------------------------------------
# Ejemplos canónicos para cada pregunta
# -----------------------------------------------------------------------------
QUESTION_EXAMPLES = {
    "¿Qué hace la empresa? ¿Cuál es su propósito?": [
        "Somos una startup de software que desarrolla soluciones de automatización para pymes. Nuestro propósito es simplificar procesos y permitir que las empresas se enfoquen en lo que mejor hacen.",
        "Somos una empresa de moda sostenible comprometida con la creación de prendas ecológicas y éticas, generando un impacto positivo en el medio ambiente."
    ],
    "¿Cuál es su propuesta de valor?": [
        "Ofrecemos asesoría integral y soporte 24/7 para garantizar soluciones a la medida, con atención personalizada.",
        "Proporcionamos productos de alta calidad a un precio competitivo, con innovación y excelente experiencia de cliente."
    ],
    # Agrega más ejemplos según sea necesario
}

def generate_markdown(answers: dict) -> str:
    """Genera un reporte en Markdown a partir de las respuestas del brief, agrupando la información por fase."""
    md = ""
    for phase in phases.keys():
        md += f"## {phase}\n"
        phase_answers = answers.get(phase, {})
        for question in phases[phase]:
            answer = phase_answers.get(question, "Sin respuesta")
            md += f"- *{question}*: {answer}\n"
        md += "\n"
    return md

# -----------------------------------------------------------------------------
# Clase para manejar la lógica del brief
# -----------------------------------------------------------------------------
class BriefService:
    def __init__(self, api_key: str = None):
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.phases = phases
        self.flat_questions = []
        self.build_flat_questions()
        self.question_mapping = {i + 1: self.flat_questions[i] for i in range(len(self.flat_questions))}
        
    def build_flat_questions(self):
        for phase, questions in self.phases.items():
            for q in questions:
                self.flat_questions.append((phase, q))
    
    def get_question(self, index: int) -> Optional[str]:
        if index < len(self.flat_questions):
            phase, question = self.flat_questions[index]
            return f"[{index + 1}] {phase} - {question}"
        else:
            return None
    
    def get_local_example(self, question: str) -> str:
        """Obtiene un ejemplo local para la pregunta actual."""
        examples_list = QUESTION_EXAMPLES.get(question, [])
        if not examples_list:
            return ""
        return random.choice(examples_list)
    
    def get_suggestion_from_business_idea(self, business_idea: dict, phase: str, question: str) -> Optional[str]:
        """
        Obtiene una sugerencia basada en la información existente de la idea de negocio.
        NOTA: Esta función ahora solo extrae datos relacionados pero NO genera la sugerencia final.
        Usarla para verificar si hay información relevante, pero siempre pasar por LLM para generar la sugerencia.
        """
        if phase != "ETAPA 1: ENTENDIMIENTO DEL NEGOCIO" or not business_idea:
            return None
            
        field_mapping = {
            "¿Qué hace la empresa? ¿Cuál es su propósito?": "description",
            "¿Cuál es su propuesta de valor?": "value_proposal",
            "¿Qué productos/servicios ofrece y a quiénes?": "products_services",
            "¿Cuál es el cliente ideal?": "ideal_customer",
            "¿Qué problema resuelve?": "problem_solved",
            "¿Qué los hace diferentes frente a la competencia?": "differentiators",
            "¿Qué desafíos u oportunidades clave enfrentan hoy?": "challenges_opportunities"
        }
        
        field = field_mapping.get(question)
        if field and field in business_idea and business_idea[field]:
            # Solo devolvemos información si es realmente relevante (más de 10 caracteres)
            if len(business_idea[field].strip()) > 10:
                return business_idea[field]
        return None
        
    def process_answer(self, phase: str, question: str, answer: str, answers: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, str]]:
        """Procesa y almacena una respuesta en el diccionario de respuestas."""
        if phase not in answers:
            answers[phase] = {}
        answers[phase][question] = answer
        return answers
    
    def get_total_questions(self) -> int:
        """Retorna el número total de preguntas en el brief."""
        return len(self.flat_questions)
            
    # -----------------------------------------------------------------------------
    # Funciones LLM
    # -----------------------------------------------------------------------------
    async def generate_llm_explanation(self, question: str, local_example: str, history: List[dict]) -> str:
        """
        Proporciona una aclaración profesional para la pregunta integrando el ejemplo local.
        Responde en un único párrafo, de forma natural y amigable.
        """
        if not local_example.strip():
            local_example = "No se dispone de un ejemplo local. Por favor, genera uno basado en buenas prácticas."

        system_msg = {
            "role": "system",
            "content": (
                "Eres un consultor senior en marketing y comunicación. Tu tarea es explicar de forma clara y profesional "
                "la siguiente pregunta, integrando el ejemplo local. Utiliza un tono natural y cercano, y sé conciso."
            )
        }
        user_msg = {
            "role": "user",
            "content": f"Pregunta: '{question}'\nEjemplo local: '{local_example}'"
        }
        messages = history + [system_msg, user_msg]

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0.5,
                max_tokens=200
            )
            explanation = response.choices[0].message.content.strip()
            return explanation
        except Exception as e:
            logger.error(f"Error al generar explicación: {e}")
            return "No se pudo generar la aclaración en este momento."

    async def rewrite_text(self, text: str, history: List[dict]) -> str:
        """
        Corrige y mejora la redacción del texto de forma natural y profesional.
        """
        system_msg = {
            "role": "system",
            "content": "Corrige y mejora la redacción del siguiente texto, manteniendo su significado original. Sé natural y profesional."
        }
        user_msg = {"role": "user", "content": f"Texto original: '{text}'"}
        messages = history + [system_msg, user_msg]

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0.3,
                max_tokens=150
            )
            rewritten = response.choices[0].message.content.strip()
            return rewritten
        except Exception as e:
            logger.error(f"Error en reescritura: {e}")
            return text

    async def generate_llm_suggestion(self, history: List[dict], user_text: str, question: str, business_idea: Optional[dict] = None) -> str:
        """
        Ofrece una recomendación o intuición breve en caso de respuesta incompleta.
        Utiliza un tono natural y amigable, y orienta al usuario basándose en el contexto previo
        y en la información disponible del modelo de negocio.
        
        Args:
            history: Historial de la conversación
            user_text: Texto del usuario
            question: La pregunta actual del brief
            business_idea: Datos del modelo de negocio (opcional)
        """
        # Preparar contexto del negocio si está disponible
        business_context = ""
        if business_idea:
            business_context = "Información del negocio:\n"
            if business_idea.get("title"):
                business_context += f"- Nombre/Título: {business_idea.get('title')}\n"
            if business_idea.get("description"):
                business_context += f"- Descripción: {business_idea.get('description')}\n"
            if business_idea.get("value_proposal"):
                business_context += f"- Propuesta de valor: {business_idea.get('value_proposal')}\n"
            if business_idea.get("products_services"):
                business_context += f"- Productos/Servicios: {business_idea.get('products_services')}\n"
            if business_idea.get("ideal_customer"):
                business_context += f"- Cliente ideal: {business_idea.get('ideal_customer')}\n"
            if business_idea.get("problem_solved"):
                business_context += f"- Problema que resuelve: {business_idea.get('problem_solved')}\n"
            if business_idea.get("differentiators"):
                business_context += f"- Diferenciadores: {business_idea.get('differentiators')}\n"
            if business_idea.get("challenges_opportunities"):
                business_context += f"- Desafíos/Oportunidades: {business_idea.get('challenges_opportunities')}\n"

        system_msg = {
            "role": "system",
            "content": (
                "Eres un asesor creativo y empático especializado en desarrollo de negocios. "
                "Tu tarea es ayudar al usuario a responder una pregunta específica de un brief de negocio. "
                "Ofrece una sugerencia de respuesta completa y profesional basada en la información disponible "
                "del negocio. Utiliza un tono natural y cercano."
            )
        }
        user_msg = {
            "role": "user",
            "content": (
                f"Pregunta del brief: '{question}'\n\n"
                f"{business_context}\n"
                f"El usuario dice: '{user_text}'\n\n"
                f"Por favor, genera una sugerencia de respuesta para esta pregunta del brief, "
                f"utilizando toda la información disponible del negocio."
            )
        }
        messages = history + [system_msg, user_msg]

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0.7,
                max_tokens=200
            )
            suggestion = response.choices[0].message.content.strip()
            return suggestion
        except Exception as e:
            logger.error(f"Error al generar la sugerencia: {e}")
            return "No se pudo generar una sugerencia en este momento."

    async def classify_intent(self, message: str, history: List[dict]) -> str:
        """
        Clasifica la intención del mensaje en una de estas etiquetas EXACTAS:
          - respuesta_valida
          - nonsense
          - pedir_aclaracion
          - corregir_respuesta
          - omitir
          - respuesta_incompleta
        Usa 'respuesta_incompleta' si el usuario indica no tener claro su respuesta.
        """
        system_msg = {
            "role": "system",
            "content": (
                "Eres un experto clasificador de intenciones para un agente de brief. Analiza cuidadosamente el mensaje actual en el contexto completo y responde SOLO con una de estas etiquetas EXACTAS (en minúsculas):\n"
                "- respuesta_valida\n- nonsense\n- pedir_aclaracion\n- corregir_respuesta\n- omitir\n- respuesta_incompleta\n\n"
                "Utiliza 'respuesta_incompleta' si el usuario expresa que no tiene claro su respuesta sin pedir que se omita o aclare."
            )
        }
        user_msg = {"role": "user", "content": f"Mensaje actual: '{message}'"}
        messages = history + [system_msg, user_msg]

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0.0,
                max_tokens=10
            )
            intent = response.choices[0].message.content.strip().lower()
            logger.info(f"Intención clasificada: {intent}")
            return intent
        except Exception as e:
            logger.error(f"Error en clasificación de intención: {e}")
            lower_msg = message.lower()
            
            # Mejorar la detección de intenciones con mensajes específicos
            # Frases relacionadas con continuar o empezar el brief
            if any(x in lower_msg for x in ["continua", "continuar", "seguir", "adelante", "empezar", "comenzar", "brief", "listo", "iniciar"]):
                return "respuesta_valida"
            
            # Confirmaciones simples
            if any(x in lower_msg for x in ["si", "sí", "ok", "estoy de acuerdo", "correcto", "exacto", "así es"]):
                return "respuesta_valida"
                
            # Respuestas incompletas
            elif any(x in lower_msg for x in ["no estoy seguro", "no lo sé", "no lo tengo claro", "no tengo idea", "aún no sé", "aun no sé"]):
                return "respuesta_incompleta"
            elif "aclara" in lower_msg or "ejemplo" in lower_msg:
                return "pedir_aclaracion"
            elif "correg" in lower_msg:
                return "corregir_respuesta"
            elif "omitir" in lower_msg:
                return "omitir"
            elif len(message.strip()) < 3:
                return "nonsense"
            else:
                return "respuesta_valida"

    async def generate_contextual_suggestion(self, history: List[dict], question: str, business_idea: dict) -> str:
        """
        Genera una sugerencia de respuesta basada en la información del negocio 
        y la pregunta específica del brief.
        
        Args:
            history: Historial de la conversación
            question: La pregunta actual del brief
            business_idea: Datos del modelo de negocio
        
        Returns:
            Sugerencia generada por el LLM
        """
        # Preparar contexto del negocio
        business_context = "Información del negocio:\n"
        if business_idea.get("title"):
            business_context += f"- Nombre/Título: {business_idea.get('title')}\n"
        if business_idea.get("description"):
            business_context += f"- Descripción: {business_idea.get('description')}\n"
        if business_idea.get("value_proposal"):
            business_context += f"- Propuesta de valor: {business_idea.get('value_proposal')}\n"
        if business_idea.get("products_services"):
            business_context += f"- Productos/Servicios: {business_idea.get('products_services')}\n"
        if business_idea.get("ideal_customer"):
            business_context += f"- Cliente ideal: {business_idea.get('ideal_customer')}\n"
        if business_idea.get("problem_solved"):
            business_context += f"- Problema que resuelve: {business_idea.get('problem_solved')}\n"
        if business_idea.get("differentiators"):
            business_context += f"- Diferenciadores: {business_idea.get('differentiators')}\n"
        if business_idea.get("challenges_opportunities"):
            business_context += f"- Desafíos/Oportunidades: {business_idea.get('challenges_opportunities')}\n"

        system_msg = {
            "role": "system",
            "content": (
                "Eres un consultor experto en negocios y marketing. "
                "Tu tarea es generar una sugerencia de respuesta para una pregunta específica "
                "de un brief de negocio, basándote en la información disponible del negocio. "
                "Ofrece una respuesta completa, profesional y directa que el usuario pueda utilizar "
                "o adaptar fácilmente. La respuesta debe ser concisa pero informativa."
            )
        }
        
        user_msg = {
            "role": "user",
            "content": (
                f"Pregunta del brief: '{question}'\n\n"
                f"{business_context}\n\n"
                f"Por favor, genera una respuesta sugerida para esta pregunta del brief, "
                f"utilizando la información disponible. La respuesta debe ser completa y profesional, "
                f"como si fuera la respuesta final que daría el usuario."
            )
        }
        
        messages = history + [system_msg, user_msg]

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0.5,
                max_tokens=250
            )
            suggestion = response.choices[0].message.content.strip()
            return suggestion
        except Exception as e:
            logger.error(f"Error al generar la sugerencia contextual: {e}")
            return "No se pudo generar una sugerencia en este momento."

    # Métodos para manejar la lógica principal del chat de brief
    async def process_message(self, message: str, business_id: str, session_id: Optional[str] = None, business_idea: Optional[dict] = None) -> Dict[str, Any]:
        """
        Método para integración con ChatOrchestrator.
        Maneja y mantiene el estado de la sesión de brief.
        
        Args:
            message: Mensaje del usuario
            business_id: ID del negocio
            session_id: ID de sesión existente (opcional)
            business_idea: Información del business_idea (opcional)
            
        Returns:
            Dict con respuesta y metadatos
        """
        try:
            # Inicializar o recuperar estado de la sesión
            if not session_id:
                # Nueva sesión
                session_id = str(uuid.uuid4())
                current_index = 0
                mode = "normal"
                pending_correction = None
                answers = {}
                history = []
            else:
                # TODO: En el futuro, recuperar estado desde Redis o BD
                # Por ahora, simplemente inicializamos con valores por defecto
                current_index = 0
                mode = "normal"
                pending_correction = None
                answers = {}
                history = []
            
            # Procesar el mensaje con el método existente
            result = await self.process_message_internal(
                message=message,
                current_index=current_index,
                mode=mode,
                pending_correction=pending_correction,
                answers=answers,
                history=history,
                business_idea=business_idea
            )
            
            # Construir respuesta
            response = {
                "session_id": session_id,
                "reply": result["reply"],
                "status": "completed" if result.get("session_finished", False) else "in_progress"
            }
            
            # TODO: Guardar estado actualizado en Redis o BD
            
            return response
            
        except Exception as e:
            logger.error(f"Error procesando mensaje en BriefService: {str(e)}")
            return {
                "session_id": session_id or str(uuid.uuid4()),
                "reply": "Hubo un error procesando tu mensaje. Por favor, intenta nuevamente.",
                "status": "error"
            }
    
    # Renombramos el método original para evitar conflictos
    async def process_message_internal(self, message: str, current_index: int, mode: str, 
                         pending_correction: Optional[tuple], 
                         answers: Dict[str, Dict[str, str]], 
                         history: List[Dict[str, str]],
                         business_idea: Optional[dict] = None) -> Dict[str, Any]:
        """
        Procesa un mensaje del usuario y devuelve una respuesta junto con la información actualizada del estado.
        Utiliza information preexistente del business_idea para sugerir respuestas.
        """
        # Permitir palabras de confirmación cortas como "si" o "ok"
        lower_msg = message.lower().strip()
        short_confirmations = ["si", "sí", "ok", "yes", "ya"]
        
        if len(message.strip()) < 3 and not any(conf == lower_msg for conf in short_confirmations):
            return {
                "reply": "Tu mensaje es muy corto. Por favor, proporciona más detalles.",
                "current_index": current_index,
                "mode": mode,
                "pending_correction": pending_correction,
                "answers": answers,
                "session_finished": False
            }

        # Modo corrección
        if mode == "correction":
            if pending_correction is None:
                try:
                    q_num = int(message.strip())
                    if q_num in self.question_mapping:
                        phase, question = self.question_mapping[q_num]
                        return {
                            "reply": f"Modo corrección activado para la pregunta [{q_num}]: {phase} - {question}. Ingresa la nueva respuesta.",
                            "current_index": current_index,
                            "mode": mode,
                            "pending_correction": (phase, question),
                            "answers": answers,
                            "session_finished": False
                        }
                    else:
                        return {
                            "reply": "Número de pregunta inválido. Inténtalo de nuevo.",
                            "current_index": current_index,
                            "mode": mode,
                            "pending_correction": None,
                            "answers": answers,
                            "session_finished": False
                        }
                except ValueError:
                    return {
                        "reply": "Debes ingresar un número válido para identificar la pregunta a corregir.",
                        "current_index": current_index,
                        "mode": mode,
                        "pending_correction": None,
                        "answers": answers,
                        "session_finished": False
                    }
            else:
                phase, question = pending_correction
                new_answer = await self.rewrite_text(message, history)
                answers = self.process_answer(phase, question, new_answer, answers)
                next_question = self.get_question(current_index)
                reply = f"Respuesta corregida para la pregunta: {question}\n\nContinuemos. {next_question or ''}"
                return {
                    "reply": reply,
                    "current_index": current_index,
                    "mode": "normal",
                    "pending_correction": None,
                    "answers": answers,
                    "session_finished": False
                }

        # Modo normal: clasificar intención
        intent = await self.classify_intent(message, history)

        # Procesar afirmación a una sugerencia
        if intent == "respuesta_valida" and business_idea:
            # Verificar si el mensaje es una afirmación simple a una sugerencia previa
            lower_msg = message.lower().strip()
            is_confirmation = any(word in lower_msg for word in [
                "sí", "si", "correcto", "exacto", "así es", "estoy de acuerdo", 
                "me parece bien", "es correcto", "es adecuado", "ok", "okay", "ya",
                "de acuerdo", "continuar", "seguir", "bueno", "perfecto", "bien"
            ])
            
            # También verificar si el mensaje es muy corto, lo que podría indicar que es una confirmación
            if len(message.strip()) <= 5:
                is_confirmation = True
            
            # Verificar si en el historial reciente hay una sugerencia
            has_recent_suggestion = False
            if history and len(history) > 1:
                last_assistant_messages = [msg for msg in history[-3:] if msg.get("role") == "assistant"]
                for msg in last_assistant_messages:
                    content = msg.get("content", "").lower()
                    if "sugerencia" in content and "¿estás de acuerdo" in content:
                        has_recent_suggestion = True
                        break
            
            if (is_confirmation or has_recent_suggestion) and current_index < len(self.flat_questions):
                phase, question = self.flat_questions[current_index]
                
                # Obtenemos primero la información relevante del business_idea si existe
                existing_info = self.get_suggestion_from_business_idea(business_idea, phase, question)
                
                # Pero siempre generamos una sugerencia enriquecida mediante el LLM
                suggestion = await self.generate_contextual_suggestion(history, question, business_idea)
                
                if suggestion:
                    # Si es una confirmación y hay una sugerencia disponible, usamos la sugerencia como respuesta
                    answers = self.process_answer(phase, question, suggestion, answers)
                    new_index = current_index + 1
                    session_finished = new_index >= len(self.flat_questions)
                    
                    reply = f"Perfecto, he registrado la respuesta sugerida: \"{suggestion}\"."
                    
                    if session_finished:
                        md = generate_markdown(answers)
                        reply += "\n\nBrief completado. Resumen final:\n" + md
                    else:
                        next_question = self.get_question(new_index)
                        next_phase, next_question_text = self.flat_questions[new_index]
                        next_suggestion = None
                        
                        if business_idea:
                            # Siempre generamos sugerencia con LLM usando el contexto de negocio
                            next_suggestion = await self.generate_contextual_suggestion(history, next_question_text, business_idea)
                        
                        reply += "\n\nSiguiente pregunta: " + next_question
                        
                        if next_suggestion:
                            reply += f"\n\nSugerencia basada en la información proporcionada:\n{next_suggestion}\n\n¿Estás de acuerdo con esta sugerencia o quieres modificarla?"
                        
                    return {
                        "reply": reply,
                        "current_index": new_index,
                        "mode": "normal",
                        "pending_correction": None,
                        "answers": answers,
                        "session_finished": session_finished
                    }
            
            # Si no es una confirmación pero hay un business_idea, generamos una sugerencia contextual
            if current_index < len(self.flat_questions) and business_idea:
                phase, question_text = self.flat_questions[current_index]
                
                # Siempre generamos sugerencia con LLM usando el contexto de negocio
                suggestion = await self.generate_contextual_suggestion(history, question_text, business_idea)
                    
                if suggestion:
                    reply = f"Para la pregunta: \"{question_text}\"\n\nSugerencia basada en la información de tu negocio:\n{suggestion}\n\n¿Estás de acuerdo con esta sugerencia o prefieres dar tu propia respuesta?"
                    return {
                        "reply": reply,
                        "current_index": current_index,
                        "mode": "normal",
                        "pending_correction": None,
                        "answers": answers,
                        "session_finished": False
                    }

        if intent == "respuesta_valida":
            corrected_answer = await self.rewrite_text(message, history)
            phase, question = self.flat_questions[current_index]
            answers = self.process_answer(phase, question, corrected_answer, answers)
            new_index = current_index + 1
            session_finished = new_index >= len(self.flat_questions)
            
            reply = f"Respuesta registrada (reescrita): \"{corrected_answer}\"."
            if session_finished:
                md = generate_markdown(answers)
                reply += "\n\nBrief completado. Resumen final:\n" + md
            else:
                next_question = self.get_question(new_index)
                next_phase, next_question_text = self.flat_questions[new_index]
                next_suggestion = None
                
                if business_idea:
                    # Siempre generamos sugerencia con LLM usando el contexto de negocio
                    next_suggestion = await self.generate_contextual_suggestion(history, next_question_text, business_idea)
                
                reply += "\n\nSiguiente pregunta: " + next_question
                
                if next_suggestion:
                    reply += f"\n\nSugerencia basada en la información proporcionada:\n{next_suggestion}\n\n¿Estás de acuerdo con esta sugerencia o quieres modificarla?"
                
            return {
                "reply": reply,
                "current_index": new_index,
                "mode": "normal",
                "pending_correction": None,
                "answers": answers,
                "session_finished": session_finished
            }

        elif intent == "nonsense":
            return {
                "reply": "Tu respuesta no tiene sentido. Por favor, reescríbela de forma más clara o escribe 'omitir'.",
                "current_index": current_index,
                "mode": mode,
                "pending_correction": pending_correction,
                "answers": answers,
                "session_finished": False
            }

        elif intent == "pedir_aclaracion":
            phase, question_text = self.flat_questions[current_index]
            local_example = self.get_local_example(question_text)
            explanation = await self.generate_llm_explanation(question_text, local_example, history)
            current_question = self.get_question(current_index)
            
            suggestion = None
            if business_idea:
                # Siempre generamos sugerencia con LLM usando el contexto de negocio
                suggestion = await self.generate_contextual_suggestion(history, question_text, business_idea)
            
            reply = (
                f"Aquí tienes una aclaración/ejemplo para la pregunta:\n{current_question}\n\n"
                f"{explanation}\n\n"
            )
            
            if suggestion:
                reply += f"Sugerencia basada en la información proporcionada:\n{suggestion}\n\n¿Estás de acuerdo con esta sugerencia o quieres modificarla?"
            else:
                reply += "Por favor, ingresa tu respuesta cuando estés listo."
            
            return {
                "reply": reply,
                "current_index": current_index,
                "mode": mode,
                "pending_correction": pending_correction,
                "answers": answers,
                "session_finished": False
            }

        elif intent == "corregir_respuesta":
            return {
                "reply": "Modo corrección activado. Por favor, ingresa el número de la pregunta que deseas corregir, y luego la nueva respuesta en el siguiente mensaje.",
                "current_index": current_index,
                "mode": "correction",
                "pending_correction": None,
                "answers": answers,
                "session_finished": False
            }

        elif intent == "omitir":
            phase, question = self.flat_questions[current_index]
            answers = self.process_answer(phase, question, "Omitida", answers)
            new_index = current_index + 1
            session_finished = new_index >= len(self.flat_questions)
            
            reply = "Pregunta omitida."
            if session_finished:
                md = generate_markdown(answers)
                reply += "\n\nBrief completado. Resumen final:\n" + md
            else:
                next_question = self.get_question(new_index)
                next_phase, next_question_text = self.flat_questions[new_index]
                next_suggestion = None
                
                if business_idea:
                    # Siempre generamos sugerencia con LLM usando el contexto de negocio
                    next_suggestion = await self.generate_contextual_suggestion(history, next_question_text, business_idea)
                
                reply += "\n\nSiguiente pregunta: " + next_question
                
                if next_suggestion:
                    reply += f"\n\nSugerencia basada en la información proporcionada:\n{next_suggestion}\n\n¿Estás de acuerdo con esta sugerencia o quieres modificarla?"
                
            return {
                "reply": reply,
                "current_index": new_index,
                "mode": "normal",
                "pending_correction": None,
                "answers": answers,
                "session_finished": session_finished
            }

        elif intent == "respuesta_incompleta":
            corrected_user_text = await self.rewrite_text(message, history)
            phase, question = self.flat_questions[current_index]
            suggestion = await self.generate_llm_suggestion(history, corrected_user_text, question, business_idea)
            
            final_answer = (
                f"No tiene claro su respuesta, pero no omite.\n"
                f"*Respuesta del usuario*: \"{corrected_user_text}\"\n"
                f"*Sugerencia/Intuición*: {suggestion}"
            )
            
            answers = self.process_answer(phase, question, final_answer, answers)
            new_index = current_index + 1
            session_finished = new_index >= len(self.flat_questions)
            
            reply = "He registrado tu respuesta como 'incompleta' junto con una sugerencia.\n"
            if session_finished:
                md = generate_markdown(answers)
                reply += "\nBrief completado. Resumen final:\n" + md
            else:
                next_question = self.get_question(new_index)
                next_phase, next_question_text = self.flat_questions[new_index]
                next_suggestion = None
                
                if business_idea:
                    # Siempre generamos sugerencia con LLM usando el contexto de negocio
                    next_suggestion = await self.generate_contextual_suggestion(history, next_question_text, business_idea)
                
                reply += "\nSiguiente pregunta: " + next_question
                
                if next_suggestion:
                    reply += f"\n\nSugerencia basada en la información proporcionada:\n{next_suggestion}\n\n¿Estás de acuerdo con esta sugerencia o quieres modificarla?"
                
            return {
                "reply": reply,
                "current_index": new_index,
                "mode": "normal",
                "pending_correction": None,
                "answers": answers,
                "session_finished": session_finished
            }

        else:
            return {
                "reply": "No se pudo determinar la intención. Por favor, reescríbelo de forma clara.",
                "current_index": current_index,
                "mode": mode,
                "pending_correction": pending_correction,
                "answers": answers,
                "session_finished": False
            } 

    async def save_brief_to_minio(self, answers: dict, business_id: str, session_id: str = None) -> bool:
        """
        Guarda el brief completado en MinIO storage.
        
        Args:
            answers: Diccionario con las respuestas del brief por etapa y pregunta
            business_id: ID del negocio
            session_id: ID opcional de la sesión de brief
            
        Returns:
            True si la operación fue exitosa, False en caso contrario
        """
        try:
            # Construir la estructura del brief según las fases
            brief_data = {
                "business_id": business_id,
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
                "brief": answers  # Ya está organizado por fases y preguntas
            }
            
            # Construir la ruta donde se guardará el brief
            object_path = f"{business_id}/business-understanding/brief.json"
            
            logger.info(f"Guardando brief en MinIO: {object_path}")
            
            # Inicializar el servicio de MinIO con el bucket correcto
            # Asumiendo que tienes un bucket "business-data" o similar
            minio_service = MinioService(bucket_name="business-data")
            
            # Guardar el archivo en MinIO
            await minio_service.upload_json(object_path, brief_data)
            
            logger.info(f"Brief guardado exitosamente en MinIO: {object_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error al guardar el brief en MinIO: {str(e)}")
            return False 