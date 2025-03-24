from fastapi import APIRouter
from app.api.v1.endpoints import auth
from app.api.v1.endpoints.business import business_idea, business_understanding
from app.api.v1.endpoints.business.competitive_analysis import business_competitors, instagram
from app.api.v1.endpoints.business import callback_endpoints

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
api_router.include_router(
    business_competitors.router,
    prefix="/analyze-competitors",
    tags=["analyze-competitors"]
) 
api_router.include_router(
    instagram.router,
    prefix="/analyze-competitors/instagram",
    tags=["instagram-competitor-analysis"]
) 
api_router.include_router(
    callback_endpoints.router,
    prefix="/webhooks",
    tags=["webhooks"]
) 
