from fastapi import APIRouter
from app.api.v1.endpoints import auth
from app.api.v1.endpoints.business.business_understanding import business_idea, business_brief, state_of_art
from app.api.v1.endpoints.business import chat
from app.api.v1.endpoints.business.competitive_analysis import (
    business_competitors, 
    instagram, 
    social_media, 
    instagram_comments, 
    instagram_analyzer, 
    instagram_statistics,
    linkedin
)
from app.api.v1.endpoints.business.webhooks import research_callback
from app.api.v1.endpoints.business.business_understanding.business_model import router as business_model_router

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(
    business_idea.router, 
    prefix="/business-idea", 
    tags=["business-idea"]
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
    instagram_comments.router,
    prefix="/analyze-competitors/instagram-comments",
    tags=["instagram-comments-analysis"]
)
api_router.include_router(
    instagram_analyzer.router,
    prefix="/analyze-competitors/instagram-analyzer",
    tags=["instagram-image-analysis"]
)
api_router.include_router(
    instagram_statistics.router,
    prefix="/analyze-competitors/instagram-statistics",
    tags=["instagram-statistics-analysis"]
)
api_router.include_router(
    linkedin.router,
    prefix="/analyze-competitors/linkedin",
    tags=["linkedin-competitor-analysis"]
)
api_router.include_router(
    research_callback.router,
    prefix="/webhooks",
    tags=["research-callbacks"]
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

api_router.include_router(
    state_of_art.router,
    prefix="/state-of-art",
    tags=["state-of-art"]
)

api_router.include_router(
    social_media.router,
    prefix="/extract-social-media",
    tags=["extract-social-media"]
)