from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api import deps
from app.schemas.business.business_idea import BusinessIdeaCreate, BusinessIdeaInDBBase
from app.api.v1.endpoints.crud.crud_business_idea import CRUDBusinessIdea
from app.models.user import User
from app.models.business.business_idea import BusinessIdea
from typing import List
from app.services.storage.minio_business_service import MinioBusinessService

router = APIRouter()

crud_business_idea = CRUDBusinessIdea(BusinessIdea)
minio_service = MinioBusinessService()

@router.post("", response_model=BusinessIdeaInDBBase)
async def create_business_idea(
    *,
    db: Session = Depends(deps.get_db),
    business_idea_in: BusinessIdeaCreate,
    current_user: User = Depends(deps.get_current_user)
):
    """
    Crea una nueva idea de negocio con título, descripción y URL del sitio web.
    
    Este es el primer paso del flujo. Después de crear la idea de negocio,
    el usuario debe iniciar un chat con el ID obtenido para comenzar el proceso de brief.
    """
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
        # Crear el registro en la base de datos con título, descripción y website_url
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
    business_idea_id: str,
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
    business_idea_id: str,
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