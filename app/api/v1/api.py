from fastapi import APIRouter
from app.api.v1.endpoints import auth
from app.api.v1.endpoints.business import business_idea, business_understanding

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(
    business_idea.router, 
    prefix="/business-idea", 
    tags=["business-idea"]
)
api_router.include_router(
    business_understanding.router, 
    prefix="/business-understanding", 
    tags=["business-understanding"]
)