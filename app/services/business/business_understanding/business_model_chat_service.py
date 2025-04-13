"""
Chat-based Business Model Service
Enables interactive business model construction via chat sessions
"""
import logging
import json
import os
from typing import Dict, List, Optional, Any
from datetime import datetime
import asyncio
from sqlalchemy.orm import Session
import aisuite as ai

from app.services.storage.minio_service import MinioService
from app.models.business.business_understanding.business_model import BusinessModel as DBBusinessModel
from app.services.business.business_understanding.business_model_module import ValidatorConfig, BusinessValidator, MarketResearchModule

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BusinessModelChatService:
    """
    Service for interactive business model development through chat.
    Manages questions, answers, and state for creating a comprehensive business model.
    """
    
    def __init__(self):
        """Initialize the service with questions and language support"""
        # Questions organized by phase
        self.questions = {
            "ANÁLISIS DE MERCADO": {
                "¿Qué problema específico resuelve tu negocio?": "problem_definition",
                "¿En qué industria opera tu negocio? (Usa clasificación oficial)": "industry",
                "Describe tu cliente ideal (demografía, comportamientos, necesidades):": "customer_persona",
                "¿Cuál es tu propuesta de valor única? (¿Por qué deberían elegirte los clientes?)": "value_proposition",
                "¿Qué te diferencia de los competidores?": "competitive_advantage",
                "¿Cuáles son los recursos clave necesarios para entregar tu propuesta de valor?": "key_resources"
            }
        }
        
        # Flatten questions for easier sequential access
        self.flat_questions = []
        for phase, phase_questions in self.questions.items():
            for question, field in phase_questions.items():
                self.flat_questions.append((phase, question, field))
                
        # Initialize AI client
        self.ai_client = ai.Client()
        
    def get_total_questions(self) -> int:
        """Get the total number of questions in all phases"""
        return len(self.flat_questions)
    
    def get_question(self, index: int) -> str:
        """Get the question at the specified index"""
        if 0 <= index < len(self.flat_questions):
            phase, question, _ = self.flat_questions[index]
            return f"{phase}: {question}"
        return "No más preguntas disponibles."
    
    def get_field_name(self, index: int) -> str:
        """Get the database field name for a question"""
        if 0 <= index < len(self.flat_questions):
            _, _, field = self.flat_questions[index]
            return field
        return None
    
    async def generate_contextual_suggestion(
        self, 
        history: List[Dict[str, str]], 
        question: str, 
        business_data: Dict[str, Any]
    ) -> str:
        """
        Generate a contextual suggestion for a question based on business data
        
        Args:
            history: Chat history
            question: Current question
            business_data: Business context data
            
        Returns:
            str: Suggested answer with key aspects to consider
        """
        try:
            # Create a prompt that includes the business context
            context = "\n".join([f"{key}: {value}" for key, value in business_data.items() if value])
            
            # System prompt to generate structured suggestions with features
            system_prompt = f"""
            Eres un experto en desarrollo de modelos de negocio. Analiza esta información de negocio:
            
            ### INFORMACIÓN DEL NEGOCIO ###
            {context}
            
            Para la pregunta: {question}
            
            Devuelve JSON con:
            1. "aspectos_clave": 2-3 aspectos clave que el usuario debería considerar (preguntas guía para pensar)
            2. "sugerencia": una respuesta modelo completa basada en la información del negocio
            
            El JSON debe tener el formato: {{"aspectos_clave": [str], "sugerencia": str}}
            """
            
            response = self.ai_client.chat.completions.create(
                model="openai:gpt-4o-mini",
                temperature=0.7,
                messages=[{"role": "system", "content": system_prompt}],
                response_format={"type": "json_object"}
            )
            
            # Parse the JSON response
            try:
                result = json.loads(response.choices[0].message.content.strip())
                
                # Store the raw suggestion for later use
                suggestion_text = result.get("sugerencia", "")
                
                # Format the suggestion with the key aspects
                formatted_suggestion = "Considera estos aspectos clave:"
                
                # Add key aspects if available
                if "aspectos_clave" in result and result["aspectos_clave"]:
                    for aspect in result["aspectos_clave"]:
                        formatted_suggestion += f"\n- {aspect}"
                    
                # Add the suggested answer
                formatted_suggestion += f"\n\nSugerencia de respuesta:\n{suggestion_text}"
                
                # Add prompt for user to accept the suggestion
                formatted_suggestion += "\n\n¿Estás de acuerdo con esta sugerencia? (Responde 'sí', 'ok' o 'de acuerdo' para aceptarla, o proporciona tu propia respuesta)"
                
                # Store the raw suggestion in the response for later access
                formatted_suggestion += f"\n\n[SUGGESTION_DATA]{suggestion_text}[/SUGGESTION_DATA]"
                
                return formatted_suggestion
            except json.JSONDecodeError:
                # Fallback to using the raw response if JSON parsing fails
                return response.choices[0].message.content.strip() + "\n\n¿Estás de acuerdo con esta sugerencia? (Responde 'sí', 'ok' o 'de acuerdo' para aceptarla, o proporciona tu propia respuesta)"
            
        except Exception as e:
            logger.error(f"Error generando sugerencia: {str(e)}")
            return ""

    def _extract_suggestion_data(self, text: str) -> Optional[str]:
        """
        Extract the raw suggestion data from a formatted suggestion
        
        Args:
            text: Formatted suggestion text
            
        Returns:
            Optional[str]: Raw suggestion data if found, None otherwise
        """
        import re
        pattern = r"\[SUGGESTION_DATA\](.*?)\[/SUGGESTION_DATA\]"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return None
        
    def _is_agreement_response(self, message: str) -> bool:
        """
        Check if the message indicates agreement with a suggestion
        
        Args:
            message: User message
            
        Returns:
            bool: True if the message indicates agreement, False otherwise
        """
        agreement_phrases = [
            "sí", "si", "yes", "ok", "okay", "de acuerdo", "acepto", 
            "me parece bien", "estoy de acuerdo", "correcto", "exacto",
            "así es", "claro", "aceptar", "bien", "bueno", "está bien"
        ]
        
        # Clean and normalize message
        message = message.lower().strip()
        
        # Check if message is an agreement phrase
        for phrase in agreement_phrases:
            if message == phrase or message.startswith(phrase + " ") or message.endswith(" " + phrase):
                return True
                
        return False
        
    async def process_message_internal(
        self,
        message: str,
        current_index: int,
        mode: str,
        pending_correction: Optional[str],
        answers: Dict[str, Dict[str, str]],
        history: List[Dict[str, str]],
        business_idea: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process a message in the context of business model creation
        
        Args:
            message: User message
            current_index: Current question index
            mode: Current mode (normal, correction, etc.)
            pending_correction: Question pending correction
            answers: Current answers
            history: Chat history
            business_idea: Business idea data
            
        Returns:
            Dict containing updated state and response
        """
        # Check if we have reached the end of questions
        if current_index >= self.get_total_questions():
            return {
                "current_index": current_index,
                "mode": mode,
                "pending_correction": None,
                "answers": answers,
                "reply": "¡Felicidades! Has completado todas las preguntas para el modelo de negocio.",
                "session_finished": True
            }
            
        # Handle correction mode
        if mode == "correction" and pending_correction is not None:
            phase, question, field = self.flat_questions[pending_correction]
            
            # Check if the user is agreeing with the suggestion
            last_assistant_message = None
            for msg in reversed(history):
                if msg.get("role") == "assistant":
                    last_assistant_message = msg.get("content", "")
                    break
                    
            if last_assistant_message and self._is_agreement_response(message):
                # Extract suggestion from the last message
                suggestion = self._extract_suggestion_data(last_assistant_message)
                if suggestion:
                    message = suggestion
            
            # Update the answer
            if phase not in answers:
                answers[phase] = {}
            answers[phase][question] = message
            
            # Return to normal mode and go to next question
            current_index = int(pending_correction) + 1
            next_question = self.get_question(current_index) if current_index < self.get_total_questions() else None
            
            if next_question:
                # Get business data for suggestion
                next_phase, next_question_text, _ = self.flat_questions[current_index]
                suggestion = await self.generate_contextual_suggestion(history, next_question_text, business_idea)
                
                suggestion_text = ""
                if suggestion:
                    suggestion_text = f"\n\n{suggestion}"
                    
                return {
                    "current_index": current_index,
                    "mode": "normal",
                    "pending_correction": None,
                    "answers": answers,
                    "reply": f"Respuesta actualizada. Continuemos con la siguiente pregunta:\n\n{next_question}{suggestion_text}",
                    "session_finished": False
                }
            else:
                # No more questions
                return {
                    "current_index": current_index,
                    "mode": "normal",
                    "pending_correction": None,
                    "answers": answers,
                    "reply": "¡Felicidades! Has completado todas las preguntas para el modelo de negocio.",
                    "session_finished": True
                }
        
        # Handle skip command
        if message.lower() in ["omitir", "skip", "saltar"]:
            phase, question, _ = self.flat_questions[current_index]
            
            # Record as skipped
            if phase not in answers:
                answers[phase] = {}
            answers[phase][question] = "Omitida"
            
            # Move to next question
            current_index += 1
            next_question = self.get_question(current_index) if current_index < self.get_total_questions() else None
            
            if next_question:
                # Get business data for suggestion
                next_phase, next_question_text, _ = self.flat_questions[current_index]
                suggestion = await self.generate_contextual_suggestion(history, next_question_text, business_idea)
                
                suggestion_text = ""
                if suggestion:
                    suggestion_text = f"\n\n{suggestion}"
                    
                return {
                    "current_index": current_index,
                    "mode": "normal",
                    "pending_correction": None,
                    "answers": answers,
                    "reply": f"Pregunta omitida. Continuemos con la siguiente:\n\n{next_question}{suggestion_text}",
                    "session_finished": False
                }
            else:
                # No more questions
                return {
                    "current_index": current_index,
                    "mode": "normal",
                    "pending_correction": None,
                    "answers": answers,
                    "reply": "¡Felicidades! Has completado todas las preguntas para el modelo de negocio.",
                    "session_finished": True
                }
        
        # Handle correction command
        if message.lower().startswith(("corregir", "editar", "cambiar")):
            try:
                # If they specify a question number
                parts = message.split()
                if len(parts) > 1 and parts[1].isdigit():
                    question_index = int(parts[1]) - 1  # Convert to 0-based index
                    
                    if 0 <= question_index < current_index:
                        phase, question, _ = self.flat_questions[question_index]
                        current_answer = answers.get(phase, {}).get(question, "No respondida aún")
                        
                        # Generate a new suggestion for the question being corrected
                        question_text = question
                        suggestion = await self.generate_contextual_suggestion(history, question_text, business_idea)
                        
                        suggestion_text = ""
                        if suggestion:
                            suggestion_text = f"\n\n{suggestion}"
                        
                        return {
                            "current_index": current_index,
                            "mode": "correction",
                            "pending_correction": question_index,
                            "answers": answers,
                            "reply": f"Por favor, proporciona tu nueva respuesta para la pregunta:\n\n{phase}: {question}\n\nRespuesta actual: {current_answer}{suggestion_text}",
                            "session_finished": False
                        }
                    else:
                        return {
                            "current_index": current_index,
                            "mode": "normal",
                            "pending_correction": None,
                            "answers": answers,
                            "reply": f"No se encontró la pregunta {question_index + 1}. Por favor, continúa con la pregunta actual:\n\n{self.get_question(current_index)}",
                            "session_finished": False
                        }
                else:
                    # They want to correct the last question
                    last_index = current_index - 1
                    if last_index >= 0:
                        phase, question, _ = self.flat_questions[last_index]
                        current_answer = answers.get(phase, {}).get(question, "No respondida aún")
                        
                        # Generate a new suggestion for the question being corrected
                        question_text = question
                        suggestion = await self.generate_contextual_suggestion(history, question_text, business_idea)
                        
                        suggestion_text = ""
                        if suggestion:
                            suggestion_text = f"\n\n{suggestion}"
                        
                        return {
                            "current_index": current_index,
                            "mode": "correction",
                            "pending_correction": last_index,
                            "answers": answers,
                            "reply": f"Por favor, proporciona tu nueva respuesta para la pregunta anterior:\n\n{phase}: {question}\n\nRespuesta actual: {current_answer}{suggestion_text}",
                            "session_finished": False
                        }
                    else:
                        return {
                            "current_index": current_index,
                            "mode": "normal",
                            "pending_correction": None,
                            "answers": answers,
                            "reply": f"No hay preguntas anteriores para corregir. Por favor, responde a la pregunta actual:\n\n{self.get_question(current_index)}",
                            "session_finished": False
                        }
            except Exception as e:
                logger.error(f"Error procesando comando de corrección: {str(e)}")
                return {
                    "current_index": current_index,
                    "mode": "normal",
                    "pending_correction": None,
                    "answers": answers,
                    "reply": f"No se pudo procesar el comando de corrección. Por favor, responde a la pregunta actual:\n\n{self.get_question(current_index)}",
                    "session_finished": False
                }
        
        # Handle help command
        if message.lower() in ["ayuda", "help", "?"]:
            # Get current question and generate suggestion for it
            phase, question_text, _ = self.flat_questions[current_index]
            suggestion = await self.generate_contextual_suggestion(history, question_text, business_idea)
            
            suggestion_text = ""
            if suggestion:
                suggestion_text = f"\n\n{suggestion}"
                
            return {
                "current_index": current_index,
                "mode": "normal",
                "pending_correction": None,
                "answers": answers,
                "reply": f"""Comandos disponibles:
                - omitir/skip/saltar: Omite la pregunta actual.
                - corregir/editar/cambiar: Corrige la última pregunta.
                - corregir N: Corrige la pregunta número N.
                - ayuda/help/?: Muestra este mensaje de ayuda.
                - sí/ok/de acuerdo: Acepta la sugerencia proporcionada.
                
                Por favor, responde a la pregunta actual:
                
                {self.get_question(current_index)}{suggestion_text}""",
                "session_finished": False
            }
        
        # Check if the user is agreeing with the suggestion
        last_assistant_message = None
        for msg in reversed(history):
            if msg.get("role") == "assistant":
                last_assistant_message = msg.get("content", "")
                break
                
        if last_assistant_message and self._is_agreement_response(message):
            # Extract suggestion from the last message
            suggestion = self._extract_suggestion_data(last_assistant_message)
            if suggestion:
                message = suggestion
                logger.info(f"User agreed with suggestion. Using suggestion as response: {message[:50]}...")
        
        # Normal flow - save answer and move to next question
        phase, question, _ = self.flat_questions[current_index]
        
        # Save answer
        if phase not in answers:
            answers[phase] = {}
        answers[phase][question] = message
        
        # Move to next question
        current_index += 1
        next_question = self.get_question(current_index) if current_index < self.get_total_questions() else None
        
        if next_question:
            # Get business data for suggestion
            next_phase, next_question_text, _ = self.flat_questions[current_index]
            suggestion = await self.generate_contextual_suggestion(history, next_question_text, business_idea)
            
            suggestion_text = ""
            if suggestion:
                suggestion_text = f"\n\n{suggestion}"
                
            return {
                "current_index": current_index,
                "mode": "normal",
                "pending_correction": None,
                "answers": answers,
                "reply": f"Respuesta guardada. Continuemos con la siguiente pregunta:\n\n{next_question}{suggestion_text}",
                "session_finished": False
            }
        else:
            # No more questions
            return {
                "current_index": current_index,
                "mode": "normal",
                "pending_correction": None,
                "answers": answers,
                "reply": "¡Felicidades! Has completado todas las preguntas para el modelo de negocio.",
                "session_finished": True
            }
    
    async def save_business_model(
        self,
        answers: Dict[str, Dict[str, str]],
        business_id: str,
        session_id: str,
        db: Session,
        minio_client: MinioService
    ) -> Dict[str, Any]:
        """
        Save business model to MinIO and database
        
        Args:
            answers: Collected answers
            business_id: Business ID
            session_id: Session ID
            db: Database session
            minio_client: MinIO client
            
        Returns:
            Dict with status and results
        """
        try:
            # Log received data
            logger.info(f"Starting to save business model for business_id: {business_id}, session_id: {session_id}")
            logger.info(f"Answers received: {json.dumps(answers, ensure_ascii=False)[:200]}...")
            
            if not answers:
                logger.error(f"No answers provided for business_id: {business_id}")
                return {
                    "success": False,
                    "error": "No answers provided",
                    "business_id": business_id,
                    "session_id": session_id
                }
            
            # Prepare flattened answer dictionary
            flat_answers = {}
            for phase, phase_answers in answers.items():
                logger.info(f"Processing phase: {phase} with {len(phase_answers)} answers")
                for question, answer in phase_answers.items():
                    # Find the field name for this question
                    field_name = None
                    for idx, (q_phase, q_text, q_field) in enumerate(self.flat_questions):
                        if q_phase == phase and q_text == question:
                            field_name = q_field
                            break
                    
                    if field_name:
                        logger.info(f"Mapping question to field: '{question}' -> '{field_name}'")
                        flat_answers[field_name] = answer if answer != "Omitida" else None
                    else:
                        logger.warning(f"Could not find field mapping for question: '{question}' in phase '{phase}'")
            
            logger.info(f"Flattened answers: {json.dumps(flat_answers, ensure_ascii=False)[:200]}...")
            
            if not flat_answers:
                logger.error(f"Could not map any answers to database fields for business_id: {business_id}")
                return {
                    "success": False,
                    "error": "Could not map answers to database fields",
                    "business_id": business_id,
                    "session_id": session_id
                }
            
            # Create a new business model record or update existing one
            try:
                existing_model = db.query(DBBusinessModel).filter(
                    DBBusinessModel.business_id == business_id
                ).first()
                
                if existing_model:
                    logger.info(f"Updating existing business model (id: {existing_model.id}) for business_id: {business_id}")
                    # Update existing model
                    for field, value in flat_answers.items():
                        if hasattr(existing_model, field):
                            if value is not None:
                                logger.info(f"Setting field '{field}' to value (length: {len(str(value)) if value else 0})")
                                setattr(existing_model, field, value)
                        else:
                            logger.warning(f"Field '{field}' not found in business model")
                    
                    existing_model.updated_at = datetime.now()
                    db_model = existing_model
                else:
                    logger.info(f"Creating new business model for business_id: {business_id}")
                    # Create new model with only the fields that exist in the model
                    valid_fields = {}
                    model_fields = [column.key for column in DBBusinessModel.__table__.columns]
                    for k, v in flat_answers.items():
                        if k in model_fields and v is not None:
                            valid_fields[k] = v
                        elif k not in model_fields:
                            logger.warning(f"Field '{k}' not found in business model schema")
                    
                    # Add required business_id
                    valid_fields['business_id'] = business_id
                    
                    db_model = DBBusinessModel(**valid_fields)
                    db.add(db_model)
                
                # Save to database
                try:
                    db.commit()
                    db.refresh(db_model)
                    logger.info(f"Successfully saved business model to database, id: {db_model.id}")
                except Exception as db_error:
                    db.rollback()
                    logger.error(f"Database error saving business model: {str(db_error)}")
                    raise
            except Exception as model_error:
                logger.error(f"Error creating/updating business model record: {str(model_error)}")
                raise
            
            # Format data for MinIO
            minio_data = {
                "MarketResearchModule": flat_answers,
                "session_id": session_id,
                "created_at": datetime.now().isoformat(),
                "business_id": business_id
            }
            
            # Define MinIO path
            minio_path = f"{business_id}/business-understanding/business_model.json"
            
            # Upload to MinIO
            try:
                logger.info(f"Uploading business model data to MinIO path: {minio_path}")
                await minio_client.upload_content(
                    object_name=minio_path,
                    data=json.dumps(minio_data, indent=2, ensure_ascii=False),
                    content_type="application/json",
                    metadata={
                        "business_id": business_id,
                        "session_id": session_id
                    }
                )
                logger.info(f"Successfully uploaded business model data to MinIO")
                
                # Update the MinIO URL in the database model
                db_model.minio_url = minio_path
                db.commit()
                logger.info(f"Updated minio_url in database record")
            except Exception as minio_error:
                logger.error(f"Error uploading to MinIO: {str(minio_error)}")
                # Continue even if MinIO upload fails
            
            logger.info(f"Business model save completed successfully")
            return {
                "success": True,
                "business_id": business_id,
                "session_id": session_id,
                "model_id": db_model.id,
                "minio_path": minio_path
            }
            
        except Exception as e:
            logger.error(f"Error guardando modelo de negocio: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                "success": False,
                "error": str(e),
                "business_id": business_id,
                "session_id": session_id
            }
    
    def generate_markdown(self, answers: Dict[str, Dict[str, str]]) -> str:
        """
        Generate markdown report from answers
        
        Args:
            answers: Collected answers by phase and question
            
        Returns:
            str: Markdown formatted report
        """
        md_lines = ["# Modelo de Negocio\n"]
        
        for phase, phase_answers in answers.items():
            md_lines.append(f"## {phase}\n")
            
            for question, answer in phase_answers.items():
                if answer != "Omitida":
                    # Format question as field name
                    field_label = ""
                    for phase_name, q_text, field in self.flat_questions:
                        if q_text == question:
                            field_label = field.replace("_", " ").title()
                            break
                    
                    if not field_label:
                        field_label = question
                        
                    md_lines.append(f"### {field_label}\n")
                    md_lines.append(f"{answer}\n")
        
        return "\n".join(md_lines) 