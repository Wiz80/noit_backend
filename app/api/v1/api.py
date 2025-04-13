from fastapi import APIRouter
from app.api.v1.endpoints import auth
from app.api.v1.endpoints.business.business_understanding import business_idea, business_brief
from app.api.v1.endpoints.business import chat
from app.api.v1.endpoints.business.competitive_analysis import business_competitors, instagram
from app.api.v1.endpoints.business.webhooks import callback_endpoints
from app.api.v1.endpoints.business.business_understanding.business_model import router as business_model_router

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(
    business_idea.router, 
    prefix="/business-idea", 
    tags=["business-idea"]
)
# api_router.include_router(
#     business_understanding_legacy.router, 
#     prefix="/business-understanding", 
#     tags=["business-understanding"]
# )
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
api_router.include_router(
    business_brief.router,
    prefix="/business-brief",
    tags=["business-brief"]
)
api_router.include_router(
    chat.router,
    prefix="/chat",
    tags=["chat"]
) 

api_router.include_router(
    business_model_router, 
    prefix="/business-model", 
    tags=["business_model"]
    )
