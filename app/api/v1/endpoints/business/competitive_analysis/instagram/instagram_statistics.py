import uuid
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
from app.core.config import settings

# Import TaskIQ task
from app.tasks.instagram_analysis_tasks import complete_instagram_statistics_analysis_task
# Import task progress service
from app.services.cache.task_progress_service import get_task_progress_service

import logging
logger = logging.getLogger(__name__)

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

class CompleteStatisticsAnalysisRequest(BaseModel):
    username: str
    post_limit: int = 50
    image_limit: int = 10
    run_in_background: bool = False

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
        minio_service = MinioService(bucket_name=settings.MINIO_BUCKET_NAME)
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

@router.post("/{business_id}/complete-statistics-analysis")
async def complete_statistics_analysis(
    business_id: UUID,
    request: CompleteStatisticsAnalysisRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Run a complete statistics analysis on Instagram posts for a specific username using TaskIQ.
    
    Args:
        business_id: UUID of the business idea
        request: CompleteStatisticsAnalysisRequest with username, post_limit, image_limit, and run_in_background
        background_tasks: Background tasks runner (deprecated, using TaskIQ)
        db: Database session
        
    Returns:
        dict: Analysis initiation status with task_id for progress tracking
    """
    try:
        # Extract parameters from request
        username = request.username
        post_limit = request.post_limit
        image_limit = request.image_limit
        run_in_background = request.run_in_background
        
        # Verify if business_id exists
        business = db.query(BusinessIdea).filter(BusinessIdea.id == str(business_id)).first()
        if not business:
            raise HTTPException(status_code=404, detail="Business idea not found")
        
        # Check if username exists in the database
        instagram_user = db.query(InstagramUserInfo).filter_by(username=username).first()
        if not instagram_user:
            raise HTTPException(status_code=404, detail=f"Instagram user {username} not found. You may need to scrape this profile first.")
        
        # Generate a unique task ID
        task_id = str(uuid.uuid4())
        
        # Get progress service
        progress_service = get_task_progress_service()
        
        # Initialize progress in Redis
        progress_service.set_task_progress(
            task_id=task_id,
            progress=0,
            status="queued"
        )

        # Check if we should run in background (TaskIQ) or synchronously
        if run_in_background:
            # Send task to TaskIQ queue
            try:
                taskiq_task = await complete_instagram_statistics_analysis_task.kiq(
                    business_id=str(business_id),
                    username=username,
                    task_id=task_id,
                    post_limit=post_limit,
                    image_limit=image_limit
                )
                
                logger.info(f"📤 TaskIQ statistics analysis task queued with ID: {taskiq_task.task_id} for user {username}")
                
                # Update progress to indicate task was queued and store TaskIQ task ID
                progress_service.update_task_progress(task_id, {
                    "status": "queued",
                    "taskiq_task_id": taskiq_task.task_id
                })
                
                return {
                    "status": "queued",
                    "message": f"Complete statistics analysis for {username} queued successfully",
                    "username": username,
                    "business_id": str(business_id),
                    "task_id": task_id
                }
                
            except Exception as e:
                logger.error(f"❌ Failed to queue TaskIQ statistics analysis task: {str(e)}")
                progress_service.set_task_failed(task_id, f"Failed to queue task: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Failed to queue statistics analysis task: {str(e)}")
        else:
            # Run task synchronously through TaskIQ (wait for result)
            try:
                taskiq_task = await complete_instagram_statistics_analysis_task.kiq(
                    business_id=str(business_id),
                    username=username,
                    task_id=task_id,
                    post_limit=post_limit,
                    image_limit=image_limit
                )
                
                # Wait for result (with timeout)
                result = await taskiq_task.wait_result(timeout=300)  # 5 minutes timeout for statistics analysis
                
                if result.is_err:
                    raise HTTPException(status_code=500, detail=f"Statistics analysis failed: {result.error}")
                
                return {
                    "status": "completed",
                    "message": f"Complete statistics analysis for {username} completed successfully",
                    "username": username,
                    "business_id": str(business_id),
                    "task_id": task_id,
                    "results": result.return_value.get("results", {})
                }
                
            except Exception as e:
                logger.error(f"❌ Failed to execute TaskIQ statistics analysis task: {str(e)}")
                progress_service.set_task_failed(task_id, str(e))
                raise HTTPException(status_code=500, detail=f"Statistics analysis failed: {str(e)}")

    except Exception as e:
        # If there was a task_id created, update its status
        if 'task_id' in locals():
            progress_service = get_task_progress_service()
            progress_service.set_task_failed(task_id, str(e))
        
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
        minio_service = MinioService(bucket_name=settings.MINIO_BUCKET_NAME)
        statistics_path = f"{business_id}/competitor-analysis/instagram/{username}/statistics.json"
        
        statistics_data = minio_service.get_object_data(statistics_path)
        if not statistics_data:
            raise HTTPException(status_code=404, detail=f"Statistics not found for username {username}")
        
        import json
        stats = json.loads(statistics_data.decode('utf-8'))
        
        return stats

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{business_id}/complete-statistics-analysis/task/{task_id}")
async def get_statistics_analysis_progress(
    business_id: UUID,
    task_id: str,
    db: Session = Depends(get_db)
):
    """
    Get the progress of complete Instagram statistics analysis for a specific task.
    
    Args:
        business_id: UUID of the business idea
        task_id: Task identifier
        db: Database session
        
    Returns:
        dict: Task progress information
    """
    try:
        # Verify if business_id exists
        if not db.query(BusinessIdea).filter(BusinessIdea.id == str(business_id)).first():
            raise HTTPException(status_code=404, detail="Business idea not found")
        
        # Get progress service
        progress_service = get_task_progress_service()
        
        # Get progress data from Redis
        progress_data = progress_service.get_task_progress(task_id)
        
        if progress_data is None:
            raise HTTPException(status_code=404, detail="Task not found")
        
        return {
            "task_id": task_id,
            "progress": progress_data["progress"],
            "status": progress_data["status"],
            "results": progress_data.get("results"),
            "error": progress_data.get("error"),
            "business_id": str(business_id)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Optional: Endpoint to cancel an ongoing statistics analysis
@router.delete("/complete-statistics-analysis/task/{task_id}")
async def cancel_statistics_analysis(task_id: str, db: Session = Depends(get_db)):
    """
    Cancel an ongoing Instagram statistics analysis.
    
    Args:
        task_id: Task identifier
        db: Database session
        
    Returns:
        dict: Cancellation confirmation message
    """
    try:
        # Get progress service
        progress_service = get_task_progress_service()
        
        # Check if task exists
        progress_data = progress_service.get_task_progress(task_id)
        if progress_data is None:
            raise HTTPException(status_code=404, detail="Task not found")

        # Update task status to cancelled
        progress_service.update_task_progress(task_id, {
            "status": "cancelled"
        })
        
        return {"message": "Instagram statistics analysis cancelled successfully", "task_id": task_id}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))