from typing import List, Optional, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.api.deps import get_db
from app.models.business.business_idea import BusinessIdea
from app.models.business.competitive_analysis.instagram import InstagramUserInfo
from app.services.business.competitive_analysis.instagram.instagram_image_analyzer import InstagramImageAnalyzer

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
        minio_service = MinioService(bucket_name="lattice-businesses")
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
        minio_service = MinioService(bucket_name="lattice-businesses")
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
    instagram_username: str,
    posts_limit: Optional[int] = None,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """
    Run a complete image analysis on Instagram posts and feed for a specific username.
    
    Args:
        business_id: UUID of the business idea
        instagram_username: Instagram username to analyze
        posts_limit: Maximum number of posts to analyze
        background_tasks: Background tasks runner
        db: Database session
        
    Returns:
        dict: Analysis initiation status
    """
    try:
        # Verify if business_id exists
        business = db.query(BusinessIdea).filter(BusinessIdea.id == str(business_id)).first()
        if not business:
            raise HTTPException(status_code=404, detail="Business idea not found")
        
        # Check if username exists in the database
        instagram_user = db.query(InstagramUserInfo).filter_by(username=instagram_username).first()
        if not instagram_user:
            raise HTTPException(status_code=404, detail=f"Instagram user {instagram_username} not found. You may need to scrape this profile first.")
        
        # Define the analysis function to run in the background
        async def run_complete_analysis():
            output_folder = f"{business_id}/competitor-analysis/instagram"
            analyzer = InstagramImageAnalyzer(output_folder=output_folder)
            
            try:
                # Get posts for the username
                from app.services.storage.minio_service import MinioService
                import json
                
                minio_service = MinioService(bucket_name="lattice-businesses")
                posts_object_name = f"{output_folder}/{instagram_username}/instagram_posts.json"
                
                # Get JSON data from MinIO
                posts_data = minio_service.get_object_data(posts_object_name)
                if not posts_data:
                    raise ValueError(f"Could not retrieve posts data from {posts_object_name}")
                    
                # Parse JSON data
                posts = json.loads(posts_data.decode('utf-8'))
                if not posts or not isinstance(posts, list):
                    raise ValueError(f"Invalid posts data format. Expected a list, got {type(posts)}")
                
                # Limit posts if requested
                if posts_limit and posts_limit > 0:
                    posts = posts[:posts_limit]
                
                # 1. Process posts images
                posts_results = await analyzer.process_posts_images(instagram_username, posts)
                
                # Save analysis to database
                await analyzer.save_analysis_to_database(
                    db=db,
                    business_id=str(business_id),
                    instagram_username=instagram_username,
                    analysis_data=posts_results
                )
                
                # 2. Analyze Instagram feed
                feed_results = await analyzer.analyze_instagram_feed(instagram_username, posts)
                
                # Update status in database
                # This would typically update a job status table
                
            except Exception as e:
                # Log the error and update status in database
                print(f"Error in complete image analysis for {instagram_username}: {str(e)}")
        
        # Add analysis to background tasks if available, otherwise run synchronously
        if background_tasks:
            background_tasks.add_task(run_complete_analysis)
            return {
                "status": "processing",
                "message": f"Complete image analysis for {instagram_username} started in background",
                "username": instagram_username,
                "business_id": str(business_id)
            }
        else:
            # Run synchronously
            await run_complete_analysis()
            return {
                "status": "completed",
                "message": f"Complete image analysis for {instagram_username} completed",
                "username": instagram_username,
                "business_id": str(business_id)
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 