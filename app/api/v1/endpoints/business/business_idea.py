from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from app.api import deps
from app.schemas.business.business_idea import BusinessIdeaCreate, BusinessIdeaInDBBase
from app.crud.crud_business_idea import CRUDBusinessIdea
from app.models.user import User
from app.models.business.business_idea import BusinessIdea
from typing import List, Dict, Any, Optional
from app.services.storage.minio_business_service import MinioBusinessService
from app.services.cache.redis_service import RedisChatService
from app.services.business.chat_business_understanding import BusinessChatService, BusinessChatConfig
from pydantic import BaseModel

router = APIRouter()

minio_service = MinioBusinessService()
crud_business_idea = CRUDBusinessIdea(BusinessIdea)

# Initialize Redis Chat Service
redis_chat_service = RedisChatService(
    host="redis",  # Docker service name
    port=6379,
    db=0
)

# Chat-related schemas
class ChatMessageRequest(BaseModel):
    """Request model for chat messages"""
    message: str

class ChatSessionResponse(BaseModel):
    """Response model for chat sessions"""
    session_id: str
    greeting: str
    next_question: Optional[str] = None
    status: Dict[str, Any]

class ChatMessageResponse(BaseModel):
    """Response model for chat messages"""
    response: str
    next_question: Optional[str] = None
    status: Dict[str, Any]

class ChatSummaryResponse(BaseModel):
    """Response model for chat summaries"""
    summary: str
    data: Dict[str, Any]
    status: Dict[str, Any]

@router.post("/", response_model=BusinessIdeaInDBBase)
async def create_business_idea(
    *,
    db: Session = Depends(deps.get_db),
    business_idea_in: BusinessIdeaCreate,
    current_user: User = Depends(deps.get_current_user)
):
    existing_idea = crud_business_idea.get_by_title_and_owner(
        db=db,
        title=business_idea_in.title,
        owner_id=current_user.id
    )
    
    if existing_idea:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have a business idea with this title"
        )
    try:
        # Crear el registro en la base de datos
        business_idea = crud_business_idea.create_with_owner(
            db=db,   
            obj_in=business_idea_in,
            owner_id=current_user.id
        )

        # Inicializar la estructura de carpetas en MinIO
        await minio_service.initialize_business_folders(business_idea.id)

        return business_idea
    except Exception as e:
        # Si hay error al crear las carpetas, eliminamos el registro
        if 'business_idea' in locals():
            db.delete(business_idea)
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating business idea: {str(e)}"
        )

@router.get("/", response_model=List[BusinessIdeaInDBBase])
async def get_business_ideas(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
    skip: int = 0,
    limit: int = 100
):
    business_ideas = crud_business_idea.get_multi_by_owner(
        db=db, owner_id=current_user.id, skip=skip, limit=limit
    )
    return business_ideas

@router.get("/{business_idea_id}", response_model=BusinessIdeaInDBBase)
async def get_business_idea(
    *,
    db: Session = Depends(deps.get_db),
    business_idea_id: int,
    current_user: User = Depends(deps.get_current_user)
):
    business_idea = crud_business_idea.get(db=db, id=business_idea_id)
    if not business_idea:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business idea not found"
        )
    if business_idea.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return business_idea

@router.get("/{business_idea_id}/folders", response_model=List[str])
async def get_business_idea_folders(
    *,
    db: Session = Depends(deps.get_db),
    business_idea_id: int,
    current_user: User = Depends(deps.get_current_user)
):
    """Lista todas las carpetas asociadas a una idea de negocio"""
    business_idea = crud_business_idea.get(db=db, id=business_idea_id)
    if not business_idea:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business idea not found"
        )
    if business_idea.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    try:
        folders = await minio_service.list_business_folders(business_idea_id)
        return folders
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing folders: {str(e)}"
        )

# New chat-based endpoints

@router.post("/{business_idea_id}/chat/start", response_model=ChatSessionResponse)
async def start_chat_session(
    *,
    db: Session = Depends(deps.get_db),
    business_idea_id: int,
    current_user: User = Depends(deps.get_current_user),
    llm_provider: str = "openai",
    llm_model: str = "gpt-4o",
    language: str = "es"
):
    """Inicia o continúa una sesión de chat para validación de idea de negocio"""
    # Verify business idea exists and belongs to user
    business_idea = crud_business_idea.get(db=db, id=business_idea_id)
    if not business_idea:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business idea not found"
        )
    if business_idea.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    try:
        # Configure the chat service
        chat_config = BusinessChatConfig(
            business_id=business_idea_id,
            user_id=current_user.id,
            language=language,
            llm_provider=llm_provider,
            llm_model=llm_model
        )
        
        # Initialize the chat service
        chat_service = BusinessChatService(
            config=chat_config,
            redis_service=redis_chat_service
        )
        
        # Start or continue the chat session
        chat_session = await chat_service.start_or_continue_chat()
        
        return ChatSessionResponse(
            session_id=chat_session["session_id"],
            greeting=chat_session["greeting"],
            next_question=chat_session["next_question"],
            status=chat_session["status"]
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error starting chat session: {str(e)}"
        )

@router.post("/{business_idea_id}/chat/{session_id}/message", response_model=ChatMessageResponse)
async def send_chat_message(
    *,
    db: Session = Depends(deps.get_db),
    business_idea_id: int,
    session_id: str,
    message_request: ChatMessageRequest,
    current_user: User = Depends(deps.get_current_user),
    llm_provider: str = "openai",
    llm_model: str = "gpt-4o",
    language: str = "es"
):
    """Envía un mensaje al chat y obtiene una respuesta"""
    # Verify business idea exists and belongs to user
    business_idea = crud_business_idea.get(db=db, id=business_idea_id)
    if not business_idea:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business idea not found"
        )
    if business_idea.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    try:
        # Configure the chat service
        chat_config = BusinessChatConfig(
            business_id=business_idea_id,
            user_id=current_user.id,
            language=language,
            llm_provider=llm_provider,
            llm_model=llm_model
        )
        
        # Initialize the chat service
        chat_service = BusinessChatService(
            config=chat_config,
            redis_service=redis_chat_service
        )
        
        # Process the message
        response = await chat_service.process_user_message(
            session_id=session_id,
            user_message=message_request.message
        )
        
        return ChatMessageResponse(
            response=response["response"],
            next_question=response.get("next_question"),
            status=response["status"]
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing message: {str(e)}"
        )

@router.post("/{business_idea_id}/chat/{session_id}/summary", response_model=ChatSummaryResponse)
async def generate_chat_summary(
    *,
    db: Session = Depends(deps.get_db),
    business_idea_id: int,
    session_id: str,
    current_user: User = Depends(deps.get_current_user),
    llm_provider: str = "openai",
    llm_model: str = "gpt-4o",
    language: str = "es"
):
    """Genera un resumen del chat de validación de negocio"""
    # Verify business idea exists and belongs to user
    business_idea = crud_business_idea.get(db=db, id=business_idea_id)
    if not business_idea:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business idea not found"
        )
    if business_idea.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    try:
        # Configure the chat service
        chat_config = BusinessChatConfig(
            business_id=business_idea_id,
            user_id=current_user.id,
            language=language,
            llm_provider=llm_provider,
            llm_model=llm_model
        )
        
        # Initialize the chat service
        chat_service = BusinessChatService(
            config=chat_config,
            redis_service=redis_chat_service
        )
        
        # Generate the summary
        summary = await chat_service.generate_summary(session_id)
        
        return ChatSummaryResponse(
            summary=summary["summary"],
            data=summary["data"],
            status=summary["status"]
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating summary: {str(e)}"
        )