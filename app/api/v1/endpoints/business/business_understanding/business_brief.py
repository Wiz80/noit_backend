from fastapi import APIRouter, Depends, HTTPException, Query, Path
from typing import Dict, List, Optional
import logging
import json
import os
from datetime import datetime
from sqlalchemy.orm import Session

from app.api import deps
from app.services.business.business_understanding.brief_service import BriefService
from app.services.cache.redis_service import RedisChatService
from app.schemas.business.business_brief import (
    BriefMessageRequest, 
    BriefMessageResponse, 
    BriefSessionInfo,
    BriefSessionListResponse,
    BriefReportResponse
)
from app.models.user import User
from app.models.business.business_idea import BusinessIdea

# Configurar logger
logger = logging.getLogger(__name__)

router = APIRouter()

# -----------------------------------------------------------------------------
# Endpoint para procesar mensajes del brief
# -----------------------------------------------------------------------------
@router.post("/business/{business_id}/brief/chat", response_model=BriefMessageResponse)
async def process_brief_message(
    business_id: str = Path(..., description="ID del negocio"),
    request: BriefMessageRequest = None,
    redis_service: RedisChatService = Depends(deps.get_redis_service),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Procesa un mensaje en una sesión de brief.
    Si no se proporciona session_id, se crea una nueva sesión.
    Si se proporciona un session_id que viene de chat.py, se verifica si está marcado para brief.
    Requiere autenticación y verifica que el business_id exista y pertenezca al usuario.
    """
    try:
        # Verificar si el business_id existe y pertenece al usuario actual
        business = db.query(BusinessIdea).filter(
            BusinessIdea.id == business_id,
            BusinessIdea.user_id == current_user.id
        ).first()
        
        if not business:
            raise HTTPException(
                status_code=404, 
                detail="Business idea not found or you don't have access to it"
            )
        
        # Inicializar el servicio de brief
        brief_service = BriefService()
        total_questions = brief_service.get_total_questions()
        
        # Obtener el user_id del usuario autenticado
        user_id = current_user.id
        
        # Convertir el objeto business a un diccionario para usar en sugerencias
        business_data = {
            "id": business.id,
            "title": business.title,
            "description": business.description,
            "value_proposal": getattr(business, 'value_proposal', None),
            "products_services": getattr(business, 'products_services', None),
            "ideal_customer": getattr(business, 'ideal_customer', None),
            "problem_solved": getattr(business, 'problem_solved', None),
            "differentiators": getattr(business, 'differentiators', None),
            "challenges_opportunities": getattr(business, 'challenges_opportunities', None)
        }
        
        # Verificar si se proporciona un session_id existente
        if request.session_id:
            # Obtener la sesión existente
            session = await redis_service.get_session(request.session_id)
            
            if not session:
                raise HTTPException(status_code=404, detail="Sesión no encontrada")
            
            # Verificar que la sesión pertenece al usuario y negocio correctos
            if session.user_id != user_id or session.business_id != business_id:
                raise HTTPException(status_code=403, detail="No tienes acceso a esta sesión")
            
            # Verificar si la sesión viene del endpoint de chat y está marcada para brief
            orchestrator_state = session.metadata.get("orchestrator_state", {})
            is_redirect_from_chat = orchestrator_state.get("mode") in ["redirect_to_brief", "brief_started"]
            
            if is_redirect_from_chat:
                # Es una sesión que viene redirigida del chat
                logger.info(f"Sesión redirigida desde chat: {request.session_id}")
                
                # Actualizar los metadatos para indicar que ahora está en el flujo de brief
                brief_state = {
                    "current_index": 0,
                    "mode": "normal",
                    "pending_correction": None,
                    "answers": {},
                    "session_finished": False
                }
                
                # Preservar los datos de business_idea si existen
                business_data_from_chat = orchestrator_state.get("business_data", {})
                if business_data_from_chat:
                    for key, value in business_data_from_chat.items():
                        if value and key in business_data:
                            business_data[key] = value
                
                # Actualizar los metadatos
                session = await redis_service.update_session_metadata(
                    session_id=session.id,
                    metadata={"brief_state": brief_state, "came_from_chat": True}
                )
                
                # Obtener la primera pregunta del brief
                first_question = brief_service.get_question(0)
                
                # Check if we have data for the first question
                first_phase, first_question_text = brief_service.flat_questions[0]
                
                # Generate suggestion with LLM using business context
                # We need to create a minimal history for the first message
                initial_history = [{"role": "system", "content": "Inicio de sesión de brief."}]
                first_suggestion = await brief_service.generate_contextual_suggestion(
                    initial_history, 
                    first_question_text, 
                    business_data
                )
                
                # Prepare welcome message with suggestion if available
                welcome_content = f"Comencemos con el proceso de brief. Tu primera pregunta es:\n\n{first_question}"
                
                if first_suggestion:
                    welcome_content += f"\n\nSugerencia basada en la información proporcionada:\n{first_suggestion}\n\n¿Estás de acuerdo con esta sugerencia o quieres modificarla?"
                
                # Añadir mensaje del sistema con la primera pregunta
                welcome_message = {
                    "role": "assistant",
                    "content": welcome_content,
                    "timestamp": datetime.now().isoformat()
                }
                
                # Añadir mensaje a la sesión
                session = await redis_service.add_message(session.id, welcome_message)
                
                # Añadir mensaje del usuario si envió uno
                if request.message:
                    user_message = {
                        "role": "user",
                        "content": request.message,
                        "timestamp": datetime.now().isoformat()
                    }
                    session = await redis_service.add_message(session.id, user_message)
                
                # Retornar respuesta con la primera pregunta
                return BriefMessageResponse(
                    session_id=session.id,
                    reply=welcome_content,
                    current_question_index=0,
                    total_questions=total_questions,
                    session_finished=False
                )
        
        # CASO 1: No se proporciona session_id - crear nueva sesión de brief
        if not request.session_id:
            # Inicializar una nueva sesión
            metadata = {
                "brief_state": {
                    "current_index": 0,
                    "mode": "normal",
                    "pending_correction": None,
                    "answers": {},
                    "session_finished": False
                }
            }
            
            # Mensaje inicial del sistema
            initial_messages = [{
                "role": "system",
                "content": "Inicio de sesión de brief. El sistema guiará al usuario a través de una serie de preguntas para crear un brief de comunicación.",
                "timestamp": datetime.now().isoformat()
            }]
            
            # Obtener la primera pregunta del brief
            first_question = brief_service.get_question(0)
            
            # Check if we have data for the first question
            first_phase, first_question_text = brief_service.flat_questions[0]
            
            # Generate suggestion with LLM using business context
            # We need to create a minimal history for the first message
            initial_history = [{"role": "system", "content": "Inicio de sesión de brief."}]
            first_suggestion = await brief_service.generate_contextual_suggestion(
                initial_history, 
                first_question_text, 
                business_data
            )
            
            # Prepare welcome message with suggestion if available
            welcome_content = f"¡Bienvenido al proceso de brief! Comenzaremos con la siguiente pregunta:\n\n{first_question}"
            
            if first_suggestion:
                welcome_content += f"\n\nSugerencia basada en la información proporcionada:\n{first_suggestion}\n\n¿Estás de acuerdo con esta sugerencia o quieres modificarla?"
            
            # Añadir mensaje del sistema con la primera pregunta
            welcome_message = {
                "role": "assistant",
                "content": welcome_content,
                "timestamp": datetime.now().isoformat()
            }
            
            # Crear sesión en Redis
            session = await redis_service.create_session(
                user_id=user_id,
                business_id=business_id,
                metadata=metadata,
                initial_messages=initial_messages
            )
            
            # Añadir mensaje del sistema con la primera pregunta
            session = await redis_service.add_message(session.id, welcome_message)
            
            # Retornar respuesta con la primera pregunta
            return BriefMessageResponse(
                session_id=session.id,
                reply=welcome_message["content"],
                current_question_index=0,
                total_questions=total_questions,
                session_finished=False
            )
        
        # CASO 2: Ya existe la sesión y ya tiene estado de brief - Procesar el mensaje
        
        # Obtener el estado actual del brief desde los metadatos
        brief_state = session.metadata.get("brief_state", {
            "current_index": 0,
            "mode": "normal",
            "pending_correction": None,
            "answers": {},
            "session_finished": False
        })
        
        # Añadir el mensaje del usuario a la sesión
        user_message = {
            "role": "user",
            "content": request.message,
            "timestamp": datetime.now().isoformat()
        }
        session = await redis_service.add_message(session.id, user_message)
        
        # Extraer el historial de mensajes para el procesamiento por LLM
        # Solo necesitamos el contenido y rol para el LLM
        conversation_history = [
            {"role": msg["role"], "content": msg["content"]} 
            for msg in session.messages
        ]
        
        # Procesar el mensaje a través del servicio de brief
        # Utilizamos directamente process_message_internal en lugar de process_message
        # para tener mayor control sobre los parámetros y utilizar la información del business_idea
        result = await brief_service.process_message_internal(
            message=request.message,
            current_index=brief_state["current_index"],
            mode=brief_state["mode"],
            pending_correction=brief_state["pending_correction"],
            answers=brief_state["answers"],
            history=conversation_history,
            business_idea=business_data
        )
        
        # Actualizar el estado del brief en los metadatos de la sesión
        brief_state.update({
            "current_index": result["current_index"],
            "mode": result["mode"],
            "pending_correction": result["pending_correction"],
            "answers": result["answers"],
            "session_finished": result["session_finished"]
        })
        session = await redis_service.update_session_metadata(
            session_id=session.id,
            metadata={"brief_state": brief_state}
        )
        
        # Si el brief ha terminado, guardarlo en MinIO
        if result["session_finished"]:
            try:
                logger.info(f"Brief completado. Guardando en MinIO para business_id: {business_id}")
                save_result = await brief_service.save_brief_to_minio(
                    answers=result["answers"],
                    business_id=business_id,
                    session_id=session.id
                )
                if save_result:
                    logger.info(f"Brief guardado exitosamente en MinIO para business_id: {business_id}")
                else:
                    logger.warning(f"No se pudo guardar el brief en MinIO para business_id: {business_id}")
            except Exception as e:
                # Capturar cualquier error durante el guardado pero continuar con la respuesta
                logger.error(f"Error al guardar brief en MinIO: {str(e)}")
        
        # Añadir respuesta del sistema a la sesión
        assistant_message = {
            "role": "assistant",
            "content": result["reply"],
            "timestamp": datetime.now().isoformat()
        }
        session = await redis_service.add_message(session.id, assistant_message)
        
        # Actualizar el BusinessIdea basado en las respuestas a las preguntas de la Etapa 1
        # Sólo actualizamos si estamos en modo normal y la respuesta es válida
        if result["mode"] == "normal" and result["current_index"] > brief_state["current_index"]:
            # Verificar qué pregunta fue respondida
            phase, question = brief_service.flat_questions[brief_state["current_index"]]
            
            # Solo procesamos las preguntas de la primera etapa (ETAPA 1: ENTENDIMIENTO DEL NEGOCIO)
            if phase == "ETAPA 1: ENTENDIMIENTO DEL NEGOCIO":
                answer = None
                for phase_key, phase_answers in result["answers"].items():
                    if phase_key == phase and question in phase_answers:
                        answer = phase_answers[question]
                        break
                
                if answer and answer != "Omitida":
                    # Determinamos qué campo actualizar basado en la pregunta
                    if question == "¿Qué hace la empresa? ¿Cuál es su propósito?":
                        business.description = answer
                    elif question == "¿Cuál es su propuesta de valor?":
                        if hasattr(business, 'value_proposal'):
                            business.value_proposal = answer
                    elif question == "¿Qué productos/servicios ofrece y a quiénes?":
                        if hasattr(business, 'products_services'):
                            business.products_services = answer
                    elif question == "¿Cuál es el cliente ideal?":
                        if hasattr(business, 'ideal_customer'):
                            business.ideal_customer = answer
                    elif question == "¿Qué problema resuelve?":
                        if hasattr(business, 'problem_solved'):
                            business.problem_solved = answer
                    elif question == "¿Qué los hace diferentes frente a la competencia?":
                        if hasattr(business, 'differentiators'):
                            business.differentiators = answer
                    elif question == "¿Qué desafíos u oportunidades clave enfrentan hoy?":
                        if hasattr(business, 'challenges_opportunities'):
                            business.challenges_opportunities = answer
                    
                    # Guardar cambios en la base de datos
                    db.commit()
        
        # Construir y retornar la respuesta
        return BriefMessageResponse(
            session_id=session.id,
            reply=result["reply"],
            current_question_index=result["current_index"],
            total_questions=total_questions,
            session_finished=result["session_finished"]
        )
        
    except Exception as e:
        logger.error(f"Error en procesamiento de brief: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------------------------------------------------------------
# Endpoint para listar sesiones de brief
# -----------------------------------------------------------------------------
@router.get("/business/{business_id}/brief/sessions", response_model=BriefSessionListResponse)
async def list_brief_sessions(
    business_id: str = Path(..., description="ID del negocio"),
    redis_service: RedisChatService = Depends(deps.get_redis_service),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Lista todas las sesiones de brief para un negocio.
    Requiere autenticación y verifica que el business_id exista y pertenezca al usuario.
    """
    try:
        # Verificar si el business_id existe y pertenece al usuario actual
        business = db.query(BusinessIdea).filter(
            BusinessIdea.id == business_id,
            BusinessIdea.user_id == current_user.id
        ).first()
        
        if not business:
            raise HTTPException(
                status_code=404, 
                detail="Business idea not found or you don't have access to it"
            )
        
        # Obtener el user_id del usuario autenticado
        user_id = current_user.id
        
        # Obtener sesiones que pertenezcan al usuario y al negocio
        user_sessions = await redis_service.get_user_sessions(user_id)
        business_sessions = await redis_service.get_business_sessions(business_id)
        
        # Intersección de ambos conjuntos
        session_ids = list(set(user_sessions).intersection(set(business_sessions)))
            
        # Lista para almacenar la información de las sesiones
        sessions_info = []
        
        # Obtener detalles de cada sesión
        for session_id in session_ids:
            session = await redis_service.get_session(session_id)
            
            # Verificar si es una sesión de brief (debe tener el brief_state en metadata)
            if session and "brief_state" in session.metadata:
                brief_state = session.metadata["brief_state"]
                
                # Crear objeto de información de la sesión
                session_info = BriefSessionInfo(
                    session_id=session.id,
                    business_id=session.business_id,
                    user_id=session.user_id,
                    current_question_index=brief_state.get("current_index", 0),
                    total_questions=BriefService().get_total_questions(),
                    session_finished=brief_state.get("session_finished", False),
                    created_at=session.created_at.isoformat() if isinstance(session.created_at, datetime) else session.created_at,
                    updated_at=session.updated_at.isoformat() if isinstance(session.updated_at, datetime) else session.updated_at
                )
                sessions_info.append(session_info)
        
        return BriefSessionListResponse(sessions=sessions_info)
        
    except Exception as e:
        logger.error(f"Error al listar sesiones de brief: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------------------------------------------------------------
# Endpoint para obtener el informe del brief
# -----------------------------------------------------------------------------
@router.get("/business/{business_id}/brief/report/{session_id}", response_model=BriefReportResponse)
async def get_brief_report(
    business_id: str = Path(..., description="ID del negocio"),
    session_id: str = Path(..., description="ID de la sesión"),
    redis_service: RedisChatService = Depends(deps.get_redis_service),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Obtiene el informe final de un brief a partir de una sesión completa.
    Requiere autenticación y verifica que el business_id exista y pertenezca al usuario.
    """
    try:
        # Verificar si el business_id existe y pertenece al usuario actual
        business = db.query(BusinessIdea).filter(
            BusinessIdea.id == business_id,
            BusinessIdea.user_id == current_user.id
        ).first()
        
        if not business:
            raise HTTPException(
                status_code=404, 
                detail="Business idea not found or you don't have access to it"
            )
        
        # Obtener la sesión
        session = await redis_service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Sesión no encontrada")
            
        # Verificar que la sesión pertenece al usuario y negocio correctos
        if session.user_id != current_user.id or session.business_id != business_id:
            raise HTTPException(status_code=403, detail="No tienes acceso a esta sesión")
            
        # Obtener el estado del brief
        brief_state = session.metadata.get("brief_state", {})
        
        # Verificar si se ha completado el brief
        if not brief_state.get("session_finished", False):
            raise HTTPException(status_code=400, detail="La sesión de brief no ha finalizado aún")
            
        # Obtener las respuestas del brief
        answers = brief_state.get("answers", {})
        
        # Inicializar el servicio de brief
        brief_service = BriefService()
        
        # Generar el informe en Markdown
        from app.services.business.business_understanding.brief_service import generate_markdown
        report_markdown = generate_markdown(answers)
        
        # Guardar el brief en MinIO si ha finalizado
        try:
            logger.info(f"Guardando brief completado en MinIO desde endpoint de reporte, business_id: {business_id}")
            save_result = await brief_service.save_brief_to_minio(
                answers=answers,
                business_id=business_id,
                session_id=session_id
            )
            if save_result:
                logger.info(f"Brief guardado exitosamente en MinIO desde endpoint de reporte para business_id: {business_id}")
            else:
                logger.warning(f"No se pudo guardar el brief en MinIO desde endpoint de reporte para business_id: {business_id}")
        except Exception as e:
            # Capturar cualquier error pero continuar para retornar el reporte
            logger.error(f"Error al guardar brief en MinIO desde endpoint de reporte: {str(e)}")
        
        # Asegurarse de que todas las respuestas de la Etapa 1 estén guardadas en el modelo
        if "ETAPA 1: ENTENDIMIENTO DEL NEGOCIO" in answers:
            etapa1_answers = answers["ETAPA 1: ENTENDIMIENTO DEL NEGOCIO"]
            
            # Actualizar cada campo si tiene respuesta y no es "Omitida"
            if "¿Qué hace la empresa? ¿Cuál es su propósito?" in etapa1_answers:
                answer = etapa1_answers["¿Qué hace la empresa? ¿Cuál es su propósito?"]
                if answer and answer != "Omitida":
                    business.description = answer
                    
            if "¿Cuál es su propuesta de valor?" in etapa1_answers:
                answer = etapa1_answers["¿Cuál es su propuesta de valor?"]
                if answer and answer != "Omitida" and hasattr(business, 'value_proposal'):
                    business.value_proposal = answer
                    
            if "¿Qué productos/servicios ofrece y a quiénes?" in etapa1_answers:
                answer = etapa1_answers["¿Qué productos/servicios ofrece y a quiénes?"]
                if answer and answer != "Omitida" and hasattr(business, 'products_services'):
                    business.products_services = answer
                    
            if "¿Cuál es el cliente ideal?" in etapa1_answers:
                answer = etapa1_answers["¿Cuál es el cliente ideal?"]
                if answer and answer != "Omitida" and hasattr(business, 'ideal_customer'):
                    business.ideal_customer = answer
                    
            if "¿Qué problema resuelve?" in etapa1_answers:
                answer = etapa1_answers["¿Qué problema resuelve?"]
                if answer and answer != "Omitida" and hasattr(business, 'problem_solved'):
                    business.problem_solved = answer
                    
            if "¿Qué los hace diferentes frente a la competencia?" in etapa1_answers:
                answer = etapa1_answers["¿Qué los hace diferentes frente a la competencia?"]
                if answer and answer != "Omitida" and hasattr(business, 'differentiators'):
                    business.differentiators = answer
                    
            if "¿Qué desafíos u oportunidades clave enfrentan hoy?" in etapa1_answers:
                answer = etapa1_answers["¿Qué desafíos u oportunidades clave enfrentan hoy?"]
                if answer and answer != "Omitida" and hasattr(business, 'challenges_opportunities'):
                    business.challenges_opportunities = answer
            
            # Guardar todos los cambios
            db.commit()
        
        return BriefReportResponse(
            session_id=session_id,
            business_id=business_id,
            report_markdown=report_markdown,
            answers=answers
        )
        
    except Exception as e:
        logger.error(f"Error al obtener informe de brief: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------------------------------------------------------------
# Endpoint para eliminar una sesión de brief
# -----------------------------------------------------------------------------
@router.delete("/business/{business_id}/brief/session/{session_id}")
async def delete_brief_session(
    business_id: str = Path(..., description="ID del negocio"),
    session_id: str = Path(..., description="ID de la sesión"),
    redis_service: RedisChatService = Depends(deps.get_redis_service),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Elimina una sesión de brief.
    Requiere autenticación y verifica que el business_id exista y pertenezca al usuario.
    """
    try:
        # Verificar si el business_id existe y pertenece al usuario actual
        business = db.query(BusinessIdea).filter(
            BusinessIdea.id == business_id,
            BusinessIdea.user_id == current_user.id
        ).first()
        
        if not business:
            raise HTTPException(
                status_code=404, 
                detail="Business idea not found or you don't have access to it"
            )
        
        # Verificar que la sesión existe
        session = await redis_service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Sesión no encontrada")
            
        # Verificar que la sesión pertenece al usuario y negocio correctos
        if session.user_id != current_user.id or session.business_id != business_id:
            raise HTTPException(status_code=403, detail="No tienes acceso a esta sesión")
            
        # Eliminar la sesión
        deleted = await redis_service.delete_session(session_id)
        
        if deleted:
            return {"message": "Sesión eliminada correctamente"}
        else:
            raise HTTPException(status_code=500, detail="No se pudo eliminar la sesión")
            
    except Exception as e:
        logger.error(f"Error al eliminar sesión de brief: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 