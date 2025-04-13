from fastapi import APIRouter, HTTPException, Depends, Path
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
import logging
from datetime import datetime

from app.api import deps
from app.models.user import User
from app.models.business.business_progress import BusinessProgress, StepStatus
from app.services.business.chat_orchestrator import ChatOrchestrator
from app.services.cache.redis_service import RedisChatService

# Importar esquemas
from pydantic import BaseModel, Field

class ChatMessageRequest(BaseModel):
    """Modelo para solicitudes de mensajes de chat"""
    message: str = Field(..., description="Mensaje enviado por el usuario")
    business_id: str = Field(..., description="ID del negocio")
    session_id: Optional[str] = Field(None, description="ID de sesión de chat existente (opcional)")
    business_data: Optional[Dict[str, Any]] = Field(None, description="Datos del negocio para sugerencias en brief")

class ChatMessageResponse(BaseModel):
    """Modelo para respuestas de mensajes de chat"""
    session_id: str = Field(..., description="ID de la sesión de chat")
    reply: str = Field(..., description="Respuesta del sistema")
    intent: Optional[str] = Field(None, description="Intención detectada en el mensaje")
    confidence: Optional[float] = Field(None, description="Confianza en la clasificación de intención")
    next_step: Optional[str] = Field(None, description="Próximo paso recomendado")
    completed_steps: List[str] = Field(default=[], description="Pasos completados")
    mode: str = Field(..., description="Modo actual de la conversación")
    active_module: Optional[str] = Field(None, description="Módulo actualmente activo (si aplica)")

class ProgressUpdateRequest(BaseModel):
    """Modelo para actualizar el progreso de un negocio"""
    step_name: str = Field(..., description="Nombre del paso a actualizar ('brief', 'business_canvas', 'competitive_analysis')")
    status: str = Field(..., description="Nuevo estado del paso ('not_started', 'in_progress', 'completed', 'failed')")
    resource_id: Optional[str] = Field(None, description="ID del recurso asociado a este paso (session_id, canvas_id, etc.)")

# Configurar logger
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/", response_model=ChatMessageResponse)
async def process_chat_message(
    request: ChatMessageRequest,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
    redis_service: RedisChatService = Depends(deps.get_redis_service)
):
    """
    Procesa un mensaje de chat y coordina la respuesta utilizando el orchestrator.
    Funciona como punto de entrada central para toda la comunicación del usuario,
    dirigiendo el flujo según la intención y el progreso del negocio.
    
    Si el negocio es nuevo (sin pasos completados), automáticamente inicia el proceso de brief.
    Puede recibir datos del business_idea para ofrecer sugerencias en el brief.
    """
    try:
        # Crear orchestrador
        orchestrator = ChatOrchestrator(db=db, redis_service=redis_service)
        
        # Verificar si es un negocio nuevo (sin pasos completados)
        from app.models.business.business_progress import BusinessProgress
        
        progress = db.query(BusinessProgress).filter(
            BusinessProgress.business_id == request.business_id
        ).first()
        
        # Si no hay registro de progreso o no hay pasos completados, y es la primera interacción (sin session_id)
        is_new_business = (not progress or not progress.get_completed_steps()) and not request.session_id
        
        # Si es un negocio nuevo, automáticamente establecer un mensaje que inicie el brief
        actual_message = request.message
        if is_new_business:
            logger.info(f"Negocio nuevo detectado, redirigiendo automáticamente al brief: {request.business_id}")
            # Usar un mensaje que probablemente activará el brief en el orchestrator
            actual_message = "Quiero comenzar con el brief"
        
        # Procesar mensaje
        result = await orchestrator.process_message(
            message=actual_message,
            business_id=request.business_id,
            user_id=current_user.id,
            session_id=request.session_id,
            business_data=request.business_data  # Pasar los datos del negocio
        )
        
        # Verificar si hubo error
        if result.get("error", False):
            status_code = result.get("status_code", 500)
            detail = result.get("detail", "Unknown error")
            raise HTTPException(status_code=status_code, detail=detail)
        
        # Si era un negocio nuevo pero el usuario envió un mensaje diferente,
        # agregar una nota al inicio de la respuesta para informar el redirección
        if is_new_business and actual_message != request.message:
            result["reply"] = f"Vamos a comenzar con el proceso de Brief para definir tu negocio.\n\n{result['reply']}"
        
        # Retornar respuesta exitosa
        return ChatMessageResponse(
            session_id=result["session_id"],
            reply=result["reply"],
            intent=result.get("intent"),
            confidence=result.get("confidence"),
            next_step=result.get("next_step"),
            completed_steps=result.get("completed_steps", []),
            mode=result.get("mode", "general"),
            active_module=result.get("active_module")
        )
        
    except HTTPException:
        # Re-lanzar excepciones HTTP para mantener su status code
        raise
    except Exception as e:
        logger.error(f"Error procesando mensaje de chat: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error procesando mensaje: {str(e)}")

@router.get("/business/{business_id}/chat/sessions")
async def list_chat_sessions(
    business_id: str = Path(..., description="ID del negocio"),
    current_user: User = Depends(deps.get_current_user),
    redis_service: RedisChatService = Depends(deps.get_redis_service)
):
    """
    Lista todas las sesiones de chat para un negocio específico.
    """
    try:
        # Obtener las sesiones que coinciden con el business_id y user_id
        user_sessions = await redis_service.get_user_sessions(current_user.id)
        business_sessions = await redis_service.get_business_sessions(business_id)
        
        # Intersección de los conjuntos
        session_ids = list(set(user_sessions) & set(business_sessions))
        
        sessions_data = []
        for session_id in session_ids:
            session = await redis_service.get_session(session_id)
            if session:
                # Solo incluir información básica
                sessions_data.append({
                    "session_id": session.id,
                    "created_at": session.created_at.isoformat() if hasattr(session.created_at, "isoformat") else session.created_at,
                    "updated_at": session.updated_at.isoformat() if hasattr(session.updated_at, "isoformat") else session.updated_at,
                    "message_count": len(session.messages),
                    "active_module": session.metadata.get("orchestrator_state", {}).get("active_module")
                })
        
        return {"sessions": sessions_data}
        
    except Exception as e:
        logger.error(f"Error al listar sesiones de chat: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al listar sesiones: {str(e)}")

@router.get("/business/{business_id}/chat/session/{session_id}")
async def get_chat_session(
    business_id: str = Path(..., description="ID del negocio"),
    session_id: str = Path(..., description="ID de la sesión"),
    current_user: User = Depends(deps.get_current_user),
    redis_service: RedisChatService = Depends(deps.get_redis_service)
):
    """
    Obtiene el historial de mensajes de una sesión de chat.
    """
    try:
        # Recuperar la sesión
        session = await redis_service.get_session(session_id)
        
        if not session:
            raise HTTPException(status_code=404, detail="Sesión no encontrada")
        
        # Verificar que la sesión pertenece al usuario y negocio
        if session.user_id != current_user.id or session.business_id != business_id:
            raise HTTPException(status_code=403, detail="Acceso denegado a esta sesión")
        
        # Preparar respuesta con mensajes filtrados (excluir mensajes del sistema)
        messages = [
            {
                "role": msg["role"],
                "content": msg["content"],
                "timestamp": msg["timestamp"]
            }
            for msg in session.messages if msg["role"] != "system"
        ]
        
        return {
            "session_id": session.id,
            "business_id": session.business_id,
            "created_at": session.created_at.isoformat() if hasattr(session.created_at, "isoformat") else session.created_at,
            "updated_at": session.updated_at.isoformat() if hasattr(session.updated_at, "isoformat") else session.updated_at,
            "messages": messages,
            "orchestrator_state": session.metadata.get("orchestrator_state", {})
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al obtener sesión de chat: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al obtener sesión: {str(e)}")

@router.delete("/business/{business_id}/chat/session/{session_id}")
async def delete_chat_session(
    business_id: str = Path(..., description="ID del negocio"),
    session_id: str = Path(..., description="ID de la sesión"),
    current_user: User = Depends(deps.get_current_user),
    redis_service: RedisChatService = Depends(deps.get_redis_service)
):
    """
    Elimina una sesión de chat.
    """
    try:
        # Recuperar la sesión
        session = await redis_service.get_session(session_id)
        
        if not session:
            raise HTTPException(status_code=404, detail="Sesión no encontrada")
        
        # Verificar que la sesión pertenece al usuario y negocio
        if session.user_id != current_user.id or session.business_id != business_id:
            raise HTTPException(status_code=403, detail="Acceso denegado a esta sesión")
        
        # Eliminar la sesión
        deleted = await redis_service.delete_session(session_id)
        
        if deleted:
            return {"message": "Sesión eliminada correctamente"}
        else:
            raise HTTPException(status_code=500, detail="No se pudo eliminar la sesión")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al eliminar sesión de chat: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al eliminar sesión: {str(e)}")

@router.post("/business/{business_id}/progress")
async def update_business_progress(
    business_id: str = Path(..., description="ID del negocio"),
    request: ProgressUpdateRequest = None,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """
    Actualiza el progreso de un negocio.
    Este endpoint es llamado por los distintos módulos cuando completan un paso
    para mantener actualizado el estado global del progreso.
    """
    try:
        # Verificar que el negocio existe y pertenece al usuario
        from app.models.business.business_idea import BusinessIdea
        business = db.query(BusinessIdea).filter(
            BusinessIdea.id == business_id,
            BusinessIdea.user_id == current_user.id
        ).first()
        
        if not business:
            raise HTTPException(status_code=404, detail="Negocio no encontrado o acceso denegado")
        
        # Obtener o crear progreso
        progress = db.query(BusinessProgress).filter(
            BusinessProgress.business_id == business_id
        ).first()
        
        if not progress:
            progress = BusinessProgress(business_id=business_id)
            db.add(progress)
        
        # Validar el step_name
        valid_steps = ["brief", "business_canvas", "competitive_analysis"]
        if request.step_name not in valid_steps:
            raise HTTPException(status_code=400, detail=f"Paso inválido. Debe ser uno de: {', '.join(valid_steps)}")
        
        # Validar el status
        valid_statuses = [s.value for s in StepStatus.__members__.values()]
        if request.status not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Estado inválido. Debe ser uno de: {', '.join(valid_statuses)}")
        
        # Actualizar el estado
        status_attr = f"{request.step_name}_status"
        setattr(progress, status_attr, request.status)
        
        # Si se proporciona resource_id, actualizarlo
        if request.resource_id:
            resource_attr = f"{request.step_name}_session_id" if request.step_name == "brief" else f"{request.step_name}_id"
            setattr(progress, resource_attr, request.resource_id)
        
        # Si el estado es "completed", actualizar fecha de completado
        if request.status == StepStatus.COMPLETED:
            completion_attr = f"{request.step_name}_completed_at"
            setattr(progress, completion_attr, datetime.now())
        
        # Guardar cambios
        db.commit()
        db.refresh(progress)
        
        # Retornar los pasos completados actualizados
        return {
            "business_id": business_id,
            "completed_steps": progress.get_completed_steps(),
            "next_step": progress.get_next_step()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al actualizar progreso: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al actualizar progreso: {str(e)}")

@router.get("/business/{business_id}/progress")
async def get_business_progress(
    business_id: str = Path(..., description="ID del negocio"),
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """
    Obtiene el progreso actual de un negocio.
    """
    try:
        # Verificar que el negocio existe y pertenece al usuario
        from app.models.business.business_idea import BusinessIdea
        business = db.query(BusinessIdea).filter(
            BusinessIdea.id == business_id,
            BusinessIdea.user_id == current_user.id
        ).first()
        
        if not business:
            raise HTTPException(status_code=404, detail="Negocio no encontrado o acceso denegado")
        
        # Obtener progreso
        progress = db.query(BusinessProgress).filter(
            BusinessProgress.business_id == business_id
        ).first()
        
        if not progress:
            # Si no hay progreso, devolver valores por defecto
            return {
                "business_id": business_id,
                "completed_steps": [],
                "next_step": "brief",
                "steps": {
                    "brief": {
                        "status": StepStatus.NOT_STARTED,
                        "resource_id": None,
                        "completed_at": None
                    },
                    "business_canvas": {
                        "status": StepStatus.NOT_STARTED,
                        "resource_id": None,
                        "completed_at": None
                    },
                    "competitive_analysis": {
                        "status": StepStatus.NOT_STARTED,
                        "resource_id": None,
                        "completed_at": None
                    }
                }
            }
        
        # Construir respuesta detallada
        steps_info = {
            "brief": {
                "status": progress.brief_status,
                "resource_id": progress.brief_session_id,
                "completed_at": progress.brief_completed_at.isoformat() if progress.brief_completed_at else None
            },
            "business_canvas": {
                "status": progress.business_canvas_status,
                "resource_id": progress.business_canvas_id,
                "completed_at": progress.business_canvas_completed_at.isoformat() if progress.business_canvas_completed_at else None
            },
            "competitive_analysis": {
                "status": progress.competitive_analysis_status,
                "resource_id": progress.competitive_analysis_id,
                "completed_at": progress.competitive_analysis_completed_at.isoformat() if progress.competitive_analysis_completed_at else None
            }
        }
        
        return {
            "business_id": business_id,
            "completed_steps": progress.get_completed_steps(),
            "next_step": progress.get_next_step(),
            "steps": steps_info
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al obtener progreso: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al obtener progreso: {str(e)}") 