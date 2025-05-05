from typing import List, Optional, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.api.deps import get_db
from app.models.business.business_idea import BusinessIdea
from app.models.business.competitive_analysis.instagram import (
    InstagramUserInfo,
    InstagramPostInfo
)
from app.services.business.competitive_analysis.instagram.instagram_statistics import InstagramStatistics
from app.services.storage.minio_service import MinioService

router = APIRouter()

# Models for request and response schemas
class StatisticsRequest(BaseModel):
    username: str
    post_limit: int = 50
    image_limit: int = 10

class StatisticsResponse(BaseModel):
    status: str
    username: str
    total_posts: int
    total_followers: Optional[int] = None
    avg_likes_per_post: Optional[float] = None
    avg_comments_per_post: Optional[float] = None
    avg_engagement_rate: Optional[float] = None
    output_path: str

# Endpoints
@router.post("/{business_id}/generate-statistics", response_model=StatisticsResponse)
async def generate_statistics(
    business_id: UUID,
    request: StatisticsRequest,
    db: Session = Depends(get_db)
):
    """
    Generate statistics from Instagram posts for a specific username.
    
    Args:
        business_id: UUID of the business idea
        request: StatisticsRequest with username, post_limit, and image_limit
        db: Database session
        
    Returns:
        StatisticsResponse: Statistics results with file path
    """
    try:
        # Verify if business_id exists
        if not db.query(BusinessIdea).filter(BusinessIdea.id == str(business_id)).first():
            raise HTTPException(status_code=404, detail="Business idea not found")
        
        # Check if username exists in the database
        instagram_user = db.query(InstagramUserInfo).filter_by(username=request.username).first()
        if not instagram_user:
            raise HTTPException(status_code=404, detail=f"Instagram user {request.username} not found. You may need to scrape this profile first.")
        
        # Initialize the Instagram statistics analyzer
        base_folder = f"{business_id}/competitor-analysis/instagram"
        output_folder = f"{base_folder}/{request.username}"
        statistics = InstagramStatistics(
            username=request.username,
            post_limit=request.post_limit,
            image_limit=request.image_limit,
            output_folder=output_folder
        )
        
        # Get posts data from MinIO
        minio_service = MinioService(bucket_name="lattice-businesses")
        posts_object_name = f"{base_folder}/{request.username}/instagram_posts.json"
        
        try:
            # Get JSON data from MinIO
            posts_data = minio_service.get_object_data(posts_object_name)
            if not posts_data:
                raise ValueError(f"Could not retrieve posts data from {posts_object_name}")
            
            # Copy the data to the expected location for the statistics generator
            await minio_service.upload_content(
                object_name=f"{output_folder}/img_posts.json",
                data=posts_data,
                content_type="application/json"
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error preparing posts data: {str(e)}")
        
        # Ensure posts exist in the database if needed for statistics generation
        post_count = db.query(InstagramPostInfo).filter_by(instagram_user_id=instagram_user.id).count()
        if post_count == 0:
            # Load posts into the database from the JSON data
            import json
            posts = json.loads(posts_data.decode('utf-8'))
            
            for post in posts:
                # Check if we already have this post
                existing_post = db.query(InstagramPostInfo).filter_by(
                    id_post=post.get("id"),
                    instagram_user_id=instagram_user.id
                ).first()
                
                if not existing_post:
                    # Create new post record
                    new_post = InstagramPostInfo(
                        instagram_user_id=instagram_user.id,
                        id_post=post.get("id"),
                        type_post=post.get("type"),
                        caption=post.get("caption", ""),
                        likes_count=post.get("likesCount", 0),
                        comments_count=post.get("commentsCount", 0),
                        post_timestamp=post.get("timestamp"),
                        url_post=post.get("url", "")
                    )
                    db.add(new_post)
            
            db.commit()
        
        # Generate statistics
        stats_file_path = await statistics.generate_statistics()
        
        # Read the generated statistics
        statistics_path = f"{output_folder}/statistics.json"
        statistics_data = minio_service.get_object_data(statistics_path)
        stats = {}
        
        if statistics_data:
            import json
            stats = json.loads(statistics_data.decode('utf-8'))
        
        return StatisticsResponse(
            status="success",
            username=request.username,
            total_posts=stats.get('total_posts', 0),
            total_followers=stats.get('total_followers', 0),
            avg_likes_per_post=stats.get('avg_likes_per_post', 0.0),
            avg_comments_per_post=stats.get('avg_comments_per_post', 0.0),
            avg_engagement_rate=stats.get('avg_engagement_rate', 0.0),
            output_path=statistics_path
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{business_id}/statistics/{username}")
async def get_statistics(
    business_id: UUID,
    username: str,
    db: Session = Depends(get_db)
):
    """
    Get Instagram statistics for a specific username.
    
    Args:
        business_id: UUID of the business idea
        username: Instagram username
        db: Database session
        
    Returns:
        Dict: Statistics data from the generated JSON
    """
    try:
        # Verify if business_id exists
        if not db.query(BusinessIdea).filter(BusinessIdea.id == str(business_id)).first():
            raise HTTPException(status_code=404, detail="Business idea not found")
        
        # Check if username exists in the database
        instagram_user = db.query(InstagramUserInfo).filter_by(username=username).first()
        if not instagram_user:
            raise HTTPException(status_code=404, detail=f"Instagram user {username} not found.")
        
        # Get statistics data from MinIO
        minio_service = MinioService(bucket_name="lattice-businesses")
        statistics_path = f"{business_id}/competitor-analysis/instagram/{username}/statistics.json"
        
        statistics_data = minio_service.get_object_data(statistics_path)
        if not statistics_data:
            raise HTTPException(status_code=404, detail=f"Statistics not found for username {username}")
        
        import json
        stats = json.loads(statistics_data.decode('utf-8'))
        
        return stats

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))