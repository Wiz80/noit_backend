from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any, Union


class BriefMessageRequest(BaseModel):
    """
    Modelo para solicitudes de mensajes del brief
    """
    message: str = Field(..., description="Mensaje enviado por el usuario")
    session_id: Optional[str] = Field(None, description="ID de la sesión de chat. Si no se proporciona, se creará una nueva sesión")
    business_id: str = Field(..., description="ID del negocio al que pertenece esta sesión")


class BriefMessageResponse(BaseModel):
    """
    Modelo para respuestas de mensajes del brief
    """
    session_id: str = Field(..., description="ID de la sesión de chat")
    reply: str = Field(..., description="Respuesta del sistema al mensaje del usuario")
    current_question_index: int = Field(..., description="Índice de la pregunta actual en el brief")
    total_questions: int = Field(..., description="Número total de preguntas en el brief")
    session_finished: bool = Field(False, description="Indica si la sesión de brief ha finalizado")
    

class BriefSessionInfo(BaseModel):
    """
    Modelo para información de la sesión del brief
    """
    session_id: str = Field(..., description="ID de la sesión")
    business_id: str = Field(..., description="ID del negocio")
    user_id: str = Field(..., description="ID del usuario")
    current_question_index: int = Field(..., description="Índice de la pregunta actual")
    total_questions: int = Field(..., description="Total de preguntas en el brief")
    session_finished: bool = Field(False, description="Indica si la sesión ha finalizado")
    created_at: str = Field(..., description="Fecha de creación de la sesión")
    updated_at: str = Field(..., description="Fecha de última actualización de la sesión")


class BriefSessionListResponse(BaseModel):
    """
    Modelo para lista de sesiones de brief
    """
    sessions: List[BriefSessionInfo] = Field([], description="Lista de sesiones de brief")


class BriefReportResponse(BaseModel):
    """
    Modelo para informe final del brief
    """
    session_id: str = Field(..., description="ID de la sesión de chat")
    business_id: str = Field(..., description="ID del negocio")
    report_markdown: str = Field(..., description="Informe final del brief en formato Markdown")
    answers: Dict[str, Dict[str, str]] = Field(..., description="Respuestas organizadas por fase y pregunta") 