from fastapi import APIRouter
from app.api.v1.endpoints import auth
from app.api.v1.endpoints.business.business_understanding import business_idea, business_brief, business_brief_websocket, state_of_art
from app.api.v1.endpoints.business.competitive_analysis import (
    business_competitors, 
    social_media,
    competitor_pricing
)
from app.api.v1.endpoints.business.competitive_analysis.instagram import (
    instagram,
    instagram_comments,
    instagram_image_analyzer,
    instagram_statistics
)
from app.api.v1.endpoints.business.competitive_analysis.linkedin import linkedin
from app.api.v1.endpoints.business.webhooks import research_callback
from app.api.v1.endpoints.health import kestra_health

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
    instagram_image_analyzer.router,
    prefix="/analyze-competitors/instagram-image-analyzer",
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
    business_brief_websocket.router,
    prefix="/ws",
    tags=["business-brief-websocket"]
)

api_router.include_router(
    state_of_art.router,
    prefix="/state-of-art",
    tags=["state-of-art"]
)

api_router.include_router(
    social_media.router,
    prefix="/analyze-competitors/extract-social-media",
    tags=["extract-social-media"]
)

api_router.include_router(
    competitor_pricing.router,
    prefix="/analyze-competitors/pricing",
    tags=["competitor-pricing"]
)

api_router.include_router(
    kestra_health.router,
    prefix="/health",
    tags=["kestra-health"]
)