import os
from typing import List, Optional, Dict, Any
from uuid import UUID
import uuid
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.api import deps
from app.api.deps import get_db
from app.models.business.business_idea import BusinessIdea
from app.models.business.competitive_analysis.instagram import InstagramUserInfo
from app.services.business.competitive_analysis.instagram.instagram_image_analyzer import InstagramImageAnalyzer
from app.models.user import User

# Import TaskIQ task
from app.tasks.instagram_analysis_tasks import complete_instagram_image_analysis_task
# Import task progress service
from app.services.cache.task_progress_service import get_task_progress_service

from app.core.config import settings

import logging
logger = logging.getLogger(__name__)

router = APIRouter()

# Models for request and response schemas
class PostsImageAnalysisRequest(BaseModel):
    instagram_username: str
    posts_limit: Optional[int] = None
    business_id: Optional[str] = None

class FeedAnalysisRequest(BaseModel):
    instagram_username: str
    posts_limit: Optional[int] = None
    business_id: Optional[str] = None

class AnalysisResponse(BaseModel):
    status: str
    message: str
    username: str
    analysis_type: str
    posts_analyzed: int
    output_path: str

class CompleteImageAnalysisRequest(BaseModel):
    instagram_username: str
    posts_limit: Optional[int] = None

# Endpoints
@router.post("/{business_id}/analyze-posts-images", response_model=AnalysisResponse)
async def analyze_posts_images(
    business_id: UUID,
    request: PostsImageAnalysisRequest,
    db: Session = Depends(get_db)
):
    """
    Analyze images from Instagram posts for a specific username.
    
    Args:
        business_id: UUID of the business idea
        request: PostsImageAnalysisRequest with instagram_username and posts_limit
        db: Database session
        
    Returns:
        AnalysisResponse: Analysis results with file path
    """
    try:
        # Verify if business_id exists
        if not db.query(BusinessIdea).filter(BusinessIdea.id == str(business_id)).first():
            raise HTTPException(status_code=404, detail="Business idea not found")
        
        # Check if username exists in the database
        instagram_user = db.query(InstagramUserInfo).filter_by(username=request.instagram_username).first()
        if not instagram_user:
            raise HTTPException(status_code=404, detail=f"Instagram user {request.instagram_username} not found. You may need to scrape this profile first.")
        
        # Initialize the Instagram image analyzer
        output_folder = f"{business_id}/competitor-analysis/instagram"
        analyzer = InstagramImageAnalyzer(output_folder=output_folder)
        
        # Get posts for the username
        from app.services.storage.minio_service import MinioService
        minio_service = MinioService(bucket_name=settings.MINIO_BUCKET_NAME)
        posts_object_name = f"{output_folder}/{request.instagram_username}/instagram_posts.json"
        
        try:
            # Get JSON data from MinIO
            posts_data = minio_service.get_object_data(posts_object_name)
            if not posts_data:
                raise ValueError(f"Could not retrieve posts data from {posts_object_name}")
                
            # Parse JSON data
            import json
            posts = json.loads(posts_data.decode('utf-8'))
            if not posts or not isinstance(posts, list):
                raise ValueError(f"Invalid posts data format. Expected a list, got {type(posts)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error fetching posts: {str(e)}")
        
        # Limit posts if requested
        if request.posts_limit and request.posts_limit > 0:
            posts = posts[:request.posts_limit]
        
        # Process posts images
        results = await analyzer.process_posts_images(request.instagram_username, posts)
        
        # Save analysis to database if business_id is provided
        if request.business_id:
            try:
                await analyzer.save_analysis_to_database(
                    db=db,
                    business_id=request.business_id,
                    instagram_username=request.instagram_username,
                    analysis_data=results
                )
            except Exception as e:
                # Log but don't fail the request if database save fails
                print(f"Error saving analysis to database: {str(e)}")
        
        # Return response
        posts_count = results.get('global_analysis', {}).get('posts_analyzed', 0)
        
        return AnalysisResponse(
            status="success",
            message=f"Successfully analyzed images from {posts_count} posts",
            username=request.instagram_username,
            analysis_type="posts_images",
            posts_analyzed=posts_count,
            output_path=f"{output_folder}/{request.instagram_username}/posts_image_analysis_report.json"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{business_id}/analyze-feed", response_model=AnalysisResponse)
async def analyze_instagram_feed(
    business_id: UUID,
    request: FeedAnalysisRequest,
    db: Session = Depends(get_db)
):
    """
    Analyze Instagram feed coherence for a specific username.
    
    Args:
        business_id: UUID of the business idea
        request: FeedAnalysisRequest with instagram_username and posts_limit
        db: Database session
        
    Returns:
        AnalysisResponse: Analysis results with file path
    """
    try:
        # Verify if business_id exists
        if not db.query(BusinessIdea).filter(BusinessIdea.id == str(business_id)).first():
            raise HTTPException(status_code=404, detail="Business idea not found")
        
        # Check if username exists in the database
        instagram_user = db.query(InstagramUserInfo).filter_by(username=request.instagram_username).first()
        if not instagram_user:
            raise HTTPException(status_code=404, detail=f"Instagram user {request.instagram_username} not found. You may need to scrape this profile first.")
        
        # Initialize the Instagram image analyzer
        output_folder = f"{business_id}/competitor-analysis/instagram"
        analyzer = InstagramImageAnalyzer(output_folder=output_folder)
        
        # Get posts for the username
        from app.services.storage.minio_service import MinioService
        minio_service = MinioService(bucket_name=settings.MINIO_BUCKET_NAME)
        posts_object_name = f"{output_folder}/{request.instagram_username}/instagram_posts.json"
        
        try:
            # Get JSON data from MinIO
            posts_data = minio_service.get_object_data(posts_object_name)
            if not posts_data:
                raise ValueError(f"Could not retrieve posts data from {posts_object_name}")
                
            # Parse JSON data
            import json
            posts = json.loads(posts_data.decode('utf-8'))
            if not posts or not isinstance(posts, list):
                raise ValueError(f"Invalid posts data format. Expected a list, got {type(posts)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error fetching posts: {str(e)}")
        
        # Limit posts if requested
        if request.posts_limit and request.posts_limit > 0:
            posts = posts[:request.posts_limit]
        
        # Analyze Instagram feed
        feed_results = await analyzer.analyze_instagram_feed(request.instagram_username, posts)
        
        # Return response
        total_posts = feed_results.get('global_analysis', {}).get('total_posts_analyzed', 0)
        total_batches = feed_results.get('global_analysis', {}).get('total_batches', 0)
        
        return AnalysisResponse(
            status="success",
            message=f"Successfully analyzed feed with {total_posts} posts in {total_batches} batches",
            username=request.instagram_username,
            analysis_type="feed_coherence",
            posts_analyzed=total_posts,
            output_path=f"{output_folder}/{request.instagram_username}/feed_analysis_report.json"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{business_id}/complete-image-analysis")
async def complete_image_analysis(
    business_id: UUID,
    request: CompleteImageAnalysisRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_superuser)
):
    """
    Run a complete image analysis on Instagram posts and feed for a specific username using TaskIQ.
    
    Args:
        business_id: UUID of the business idea
        request: CompleteImageAnalysisRequest with instagram_username and posts_limit
        db: Database session
        
    Returns:
        dict: Analysis initiation status with task_id for progress tracking
    """
    try:
        # Extract parameters from request
        username = request.instagram_username
        
        # Verify if business_id exists
        business = db.query(BusinessIdea).filter(BusinessIdea.id == str(business_id)).first()
        if not business:
            raise HTTPException(status_code=404, detail="Business idea not found")
        
        # Check if username exists in the database
        instagram_user = db.query(InstagramUserInfo).filter_by(username=username).first()
        if not instagram_user:
            raise HTTPException(status_code=404, detail=f"Instagram user {username} not found. You may need to scrape this profile first.")
        
        # Get progress service
        progress_service = get_task_progress_service()
        
        # --- Task Existence Check ---
        task_tracking_key = f"latest_task:instagram_image_analysis:{business_id}:{username}"
        latest_task_id = progress_service.redis.get(task_tracking_key)
        
        if latest_task_id:
            task_progress = progress_service.get_task_progress(latest_task_id)
            if task_progress:
                status = task_progress.get("status")
                if status in ["queued", "processing", "waiting_for_research"]:
                    logger.info(f"Image analysis task {latest_task_id} for {username} is already in progress (status: {status}).")
                    return {
                        "status": "already_running",
                        "message": f"An image analysis for {username} is already in progress.",
                        "task_id": latest_task_id,
                        "current_status": status
                    }
                elif status == "completed":
                    logger.info(f"Image analysis for {username} (task {latest_task_id}) has already completed successfully.")
                    return {
                        "status": "already_completed",
                        "message": f"A successful image analysis for {username} already exists.",
                        "task_id": latest_task_id,
                        "results": task_progress.get("results")
                    }
                
        # --- Generate and Queue New Task ---
        task_id = str(uuid.uuid4())
        
        progress_service.redis.set(task_tracking_key, task_id, ex=86400) # 24-hour TTL
        
        progress_service.set_task_progress(
            task_id=task_id,
            progress=0,
            status="queued"
        )

        try:
            taskiq_task = await complete_instagram_image_analysis_task.kiq(
                business_id=str(business_id),
                username=username,
                task_id=task_id,
                posts_limit=request.posts_limit
            )
            
            logger.info(f"📤 TaskIQ image analysis task queued with ID: {taskiq_task.task_id} for user {username}")
            
            progress_service.update_task_progress(task_id, {
                "status": "queued",
                "taskiq_task_id": taskiq_task.task_id
            })
            
            return {
                "status": "queued",
                "message": f"Complete image analysis for {username} queued successfully",
                "username": username,
                "business_id": str(business_id),
                "task_id": task_id
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to queue TaskIQ image analysis task: {str(e)}")
            progress_service.set_task_failed(task_id, f"Failed to queue task: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to queue image analysis task: {str(e)}")

    except Exception as e:
        task_id_local = locals().get('task_id')
        if task_id_local:
            progress_service = get_task_progress_service()
            progress_service.set_task_failed(task_id_local, str(e))
        
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{business_id}/posts-image-analysis/{instagram_username}")
async def get_posts_image_analysis(
    business_id: UUID,
    instagram_username: str,
    db: Session = Depends(get_db)
):
    """
    Get the posts image analysis results for a specific Instagram username.
    
    Args:
        business_id: UUID of the business idea
        instagram_username: Instagram username to get analysis for
        db: Database session
        
    Returns:
        dict: Posts image analysis data
    """
    try:
        # Verify if business_id exists
        business = db.query(BusinessIdea).filter(BusinessIdea.id == str(business_id)).first()
        if not business:
            raise HTTPException(status_code=404, detail="Business idea not found")
        
        # Check if username exists in the database
        instagram_user = db.query(InstagramUserInfo).filter_by(username=instagram_username).first()
        if not instagram_user:
            raise HTTPException(status_code=404, detail=f"Instagram user {instagram_username} not found")
        
        # Get data from MinIO
        from app.services.storage.minio_service import MinioService
        import json
        
        output_folder = f"{business_id}/competitor-analysis/instagram"
        minio_service = MinioService(bucket_name=settings.MINIO_BUCKET_NAME)
        analysis_object_name = f"{output_folder}/{instagram_username}/posts_image_analysis_report.json"
        
        try:
            # Get JSON data from MinIO
            analysis_data = minio_service.get_object_data(analysis_object_name)
            if not analysis_data:
                raise HTTPException(status_code=404, detail="Posts image analysis not found")
                
            # Parse JSON data
            analysis = json.loads(analysis_data.decode('utf-8'))
            return analysis
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error fetching posts image analysis: {str(e)}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{business_id}/feed-analysis/{instagram_username}")
async def get_feed_analysis(
    business_id: UUID,
    instagram_username: str,
    db: Session = Depends(get_db)
):
    """
    Get the feed analysis results for a specific Instagram username.
    
    Args:
        business_id: UUID of the business idea
        instagram_username: Instagram username to get analysis for
        db: Database session
        
    Returns:
        dict: Feed analysis data
    """
    try:
        # Verify if business_id exists
        business = db.query(BusinessIdea).filter(BusinessIdea.id == str(business_id)).first()
        if not business:
            raise HTTPException(status_code=404, detail="Business idea not found")
        
        # Check if username exists in the database
        instagram_user = db.query(InstagramUserInfo).filter_by(username=instagram_username).first()
        if not instagram_user:
            raise HTTPException(status_code=404, detail=f"Instagram user {instagram_username} not found")
        
        # Get data from MinIO
        from app.services.storage.minio_service import MinioService
        import json
        
        output_folder = f"{business_id}/competitor-analysis/instagram"
        minio_service = MinioService(bucket_name=settings.MINIO_BUCKET_NAME)
        analysis_object_name = f"{output_folder}/{instagram_username}/feed_analysis_report.json"
        
        try:
            # Get JSON data from MinIO
            analysis_data = minio_service.get_object_data(analysis_object_name)
            if not analysis_data:
                raise HTTPException(status_code=404, detail="Feed analysis not found")
                
            # Parse JSON data
            analysis = json.loads(analysis_data.decode('utf-8'))
            return analysis
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error fetching feed analysis: {str(e)}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{business_id}/complete-image-analysis/task/{task_id}")
async def get_image_analysis_progress(
    business_id: UUID,
    task_id: str,
    db: Session = Depends(get_db)
):
    """
    Get the progress of complete Instagram image analysis for a specific task.
    
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

# Optional: Endpoint to cancel an ongoing image analysis
@router.delete("/complete-image-analysis/task/{task_id}")
async def cancel_image_analysis(task_id: str, db: Session = Depends(get_db)):
    """
    Cancel an ongoing Instagram image analysis.
    
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
        
        return {"message": "Instagram image analysis cancelled successfully", "task_id": task_id}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{business_id}/images/{username}")
async def get_analyzed_images(
    business_id: UUID,
    username: str,
    db: Session = Depends(get_db)
):
    """
    Get the analyzed images for a specific Instagram username.
    
    Args:
        business_id: UUID of the business idea
        username: Instagram username to get analyzed images for
        db: Database session
        
    Returns:
        dict: Analyzed images data
    """
    try:
        # Verify if business_id exists
        business = db.query(BusinessIdea).filter(BusinessIdea.id == str(business_id)).first()
        if not business:
            raise HTTPException(status_code=404, detail="Business idea not found")
        
        # Check if username exists in the database
        instagram_user = db.query(InstagramUserInfo).filter_by(username=username).first()
        if not instagram_user:
            raise HTTPException(status_code=404, detail=f"Instagram user {username} not found")
        
        # Get data from MinIO
        from app.services.storage.minio_service import MinioService
        import json
        
        output_folder = f"{business_id}/competitor-analysis/instagram"
        minio_service = MinioService(bucket_name=settings.MINIO_BUCKET_NAME)
        analysis_object_name = f"{output_folder}/{username}/posts_image_analysis_report.json"
        
        try:
            # Get JSON data from MinIO
            analysis_data = minio_service.get_object_data(analysis_object_name)
            if not analysis_data:
                raise HTTPException(status_code=404, detail="Analyzed images not found")
                
            # Parse JSON data
            analysis = json.loads(analysis_data.decode('utf-8'))
            return analysis
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error fetching analyzed images: {str(e)}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 