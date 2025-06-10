# routes/competitor_analysis.py

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from openai import OpenAI
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
import uuid
from uuid import UUID
from datetime import datetime
import requests
import json
import logging
import os
from dotenv import load_dotenv

from app.api.deps import get_db
from app.models.business.business_idea import BusinessIdea
from app.models.business.competitive_analysis.competitors import Competitor
from app.models.business.competitive_analysis.instagram import InstagramScrapingJob, InstagramUserInfo
from app.controllers.competitive_analysis.instagram_competitor_controller import InstagramCompetitorController
from app.services.business.competitive_analysis.instagram.comments.instagram_comment_categorizer import InstagramCommentCategorizer
from app.services.business.competitive_analysis.instagram.comments.instagram_topic_modeling import InstagramTopicModeling
from app.services.business.competitive_analysis.instagram.comments.instagram_sentiment_emotion_analyzer import InstagramSentimentEmotionAnalyzer
from app.services.business.competitive_analysis.instagram.instagram_scraper import InstagramScraper
from app.services.search.dynamic_research_ai import ResearchModule, ResearchConfig
from app.prompts.business.prompts_business_competitors import create_validation_competitor_prompt
from app.models.user import User

# Import TaskIQ task
from app.tasks.instagram_analysis_tasks import run_instagram_full_analysis_task
# Import task progress service
from app.services.cache.task_progress_service import get_task_progress_service

import logging
logger = logging.getLogger(__name__)

load_dotenv()

router = APIRouter()

# Pydantic schemas for response
class AnalysisResponse(BaseModel):
    task_id: str
    message: str
    status: str

class AnalysisProgressResponse(BaseModel):
    task_id: str
    progress: int
    status: str
    results: Optional[dict]

# Schema for competitor analysis request - simplified since we're targeting one competitor
class CompetitorAnalysisRequest(BaseModel):
    # Remove competitor_ids since we'll get the competitor_id from the URL
    pass

# Schema for comment analysis request
class CommentAnalysisRequest(BaseModel):
    username: str
    analysis_types: List[str] = ["categorization", "sentiment", "topics"]
    language: str = "es"
    num_topics: int = 5
    provider: str = "openai"
    model: str = "gpt-4o-mini"

# Schema for comment analysis response
class CommentAnalysisResponse(BaseModel):
    username: str
    analysis_types: List[str]
    status: str
    results: Optional[dict]

# Schema for research callback request
class ResearchCallbackRequest(BaseModel):
    request_id: str
    business_id: str
    competitor_id: str
    task_id: Optional[str] = None
    research_results: dict

@router.post("/{business_id}/competitor/{competitor_id}", response_model=AnalysisResponse)
async def start_instagram_competitor_analysis(
    business_id: UUID,
    competitor_id: str,
    request: CompetitorAnalysisRequest,
    background_tasks: BackgroundTasks,
    results_limit: int = 10,
    max_comments: int = 5,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_superuser)
):
    """
    Start Instagram competitor analysis for a specific competitor using TaskIQ.
    
    Args:
        business_id: UUID of the business idea
        competitor_id: ID of the specific competitor to analyze
        request: Request body (currently empty but kept for potential future parameters)
        background_tasks: FastAPI background tasks (not used with TaskIQ)
        results_limit: Maximum number of posts to extract per Instagram account (default: 10)
        max_comments: Maximum number of comments to extract per post (default: 5)
        db: Database session
        
    Returns:
        AnalysisResponse: Task information
    """
    try:
        # Verify if business_id exists
        business = db.query(BusinessIdea).filter(BusinessIdea.id == str(business_id)).first()
        if not business:
            raise HTTPException(status_code=404, detail="Business idea not found")

        # Get the specific competitor and verify it belongs to this business
        competitor = db.query(Competitor).filter(
            Competitor.id == competitor_id,
            Competitor.business_idea_id == str(business_id)
        ).first()
        
        if not competitor:
            raise HTTPException(
                status_code=404, 
                detail=f"Competitor with ID {competitor_id} not found for business {business_id}"
            )
            
        # Verify that the competitor has an Instagram URL
        if not competitor.instagram_url:
            raise HTTPException(
                status_code=400, 
                detail=f"Competitor '{competitor.competitor_name}' does not have an Instagram URL"
            )
        
        # Verify if a task is already running or finished for this competitor
        progress_service = get_task_progress_service()
        
        # First check if there's any existing task using competitor_id as key
        existing_task_progress = progress_service.get_task_progress(competitor_id)
        
        if existing_task_progress:
            task_status = existing_task_progress.get("status")
            existing_task_id = existing_task_progress.get("task_id")
            
            logger.info(f"🔍 Found existing task for competitor {competitor.competitor_name}: {existing_task_id} with status: {task_status}")
            
            # Handle different existing task statuses
            # Get the actual task_id from metadata if available
            actual_task_id = existing_task_progress.get("actual_task_id", existing_task_id)
            
            if task_status == "processing":
                logger.info(f"⏳ Task {actual_task_id} is still processing for competitor '{competitor.competitor_name}'")
                return AnalysisResponse(
                    task_id=actual_task_id,
                    message=f"Task is already in progress for competitor '{competitor.competitor_name}'. Task ID: {actual_task_id}",
                    status="processing"
                )
            
            elif task_status == "completed":
                logger.info(f"✅ Task {actual_task_id} already completed for competitor '{competitor.competitor_name}'")
                return AnalysisResponse(
                    task_id=actual_task_id,
                    message=f"Analysis already completed for competitor '{competitor.competitor_name}'. Task ID: {actual_task_id}",
                    status="completed"
                )
            
            elif task_status == "queued":
                logger.info(f"🕒 Task {actual_task_id} is queued for competitor '{competitor.competitor_name}'")
                return AnalysisResponse(
                    task_id=actual_task_id,
                    message=f"Task is already queued for competitor '{competitor.competitor_name}'. Task ID: {actual_task_id}",
                    status="queued"
                )
            
            elif task_status in ["failed", "cancelled", "error"]:
                logger.warning(f"❌ Previous task {actual_task_id} failed/cancelled for competitor '{competitor.competitor_name}'. Creating new task...")
                # Clean up the failed task progress and continue to create a new one
                progress_service.delete_task_progress(competitor_id)
            
            else:
                logger.warning(f"⚠️ Unknown task status '{task_status}' for competitor '{competitor.competitor_name}'. Creating new task...")
                # Clean up unknown status and continue
                progress_service.delete_task_progress(competitor_id)

        # Generate a unique task ID for new task
        task_id = str(uuid.uuid4())
        
        logger.info(f"🆕 Creating new task {task_id} for competitor '{competitor.competitor_name}'")
        
        # Initialize progress in Redis using competitor_id as key for consistency
        progress_service.set_task_progress(
            task_id=competitor_id,  # Use competitor_id as key for easier lookup
            progress=0,
            status="queued"
        )
        
        # Add additional metadata using update_task_progress
        progress_service.update_task_progress(competitor_id, {
            "actual_task_id": task_id,
            "competitor_id": competitor_id,
            "competitor_name": competitor.competitor_name,
            "business_id": str(business_id),
            "instagram_url": competitor.instagram_url
        })

        # Send task to TaskIQ queue for the specific competitor
        try:
            taskiq_task = await run_instagram_full_analysis_task.kiq(
                business_id=str(business_id),
                task_id=task_id,
                competitor_ids=[competitor_id],  # Pass only this competitor
                results_limit=results_limit,
                max_comments=max_comments
            )
            
            logger.info(f"📤 TaskIQ task queued with ID: {taskiq_task.task_id} for Instagram analysis of competitor {competitor.competitor_name}")
            
            # Update progress to indicate task was queued and store TaskIQ task ID
            progress_service.update_task_progress(competitor_id, {
                "status": "queued",
                "taskiq_task_id": taskiq_task.task_id,
                "actual_task_id": task_id,
                "competitor_id": competitor_id,
                "competitor_name": competitor.competitor_name,
                "instagram_url": competitor.instagram_url,
                "business_id": str(business_id)
            })
            
        except Exception as e:
            logger.error(f"❌ Failed to queue TaskIQ task: {str(e)}")
            progress_service.set_task_failed(competitor_id, f"Failed to queue task: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to queue Instagram analysis task: {str(e)}")

        return AnalysisResponse(
            task_id=task_id,  # Return the actual task_id (UUID), not competitor_id
            message=f"Instagram analysis queued successfully for competitor '{competitor.competitor_name}'",
            status="queued"
        )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # If there was a task_id created, update its status
        if 'task_id' in locals() and 'competitor_id' in locals():
            progress_service = get_task_progress_service()
            progress_service.set_task_failed(competitor_id, str(e))
        
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{business_id}/task/{task_id}", response_model=AnalysisProgressResponse)
async def get_instagram_analysis_progress(
    business_id: UUID,
    task_id: str,
    db: Session = Depends(get_db)
):
    """
    Get the progress of Instagram competitor analysis for a specific task.
    
    Args:
        business_id: UUID of the business idea
        task_id: Task identifier
        db: Database session
        
    Returns:
        AnalysisProgressResponse: Task progress information
    """
    # Get progress service
    progress_service = get_task_progress_service()
    
    # Get progress data from Redis
    progress_data = progress_service.get_task_progress(task_id)
    
    if progress_data is None:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return AnalysisProgressResponse(
        task_id=task_id,
        progress=progress_data["progress"],
        status=progress_data["status"],
        results=progress_data.get("results")
    )

# Optional: Endpoint to cancel an ongoing analysis
@router.delete("/task/{task_id}")
async def cancel_instagram_analysis(task_id: str, db: Session = Depends(get_db)):
    """
    Cancel an ongoing Instagram analysis.
    
    Args:
        task_id: Task identifier
        db: Database session
        
    Returns:
        dict: Cancellation confirmation message
    """
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
    
    # Update any in-progress scraping jobs
    scraping_jobs = db.query(InstagramScrapingJob).filter(
        InstagramScrapingJob.job_metadata.contains({"task_id": task_id}),
        InstagramScrapingJob.status == "processing"
    ).all()
    
    for job in scraping_jobs:
        job.status = "cancelled"
        db.commit()

    return {"message": "Instagram analysis cancelled successfully"}

@router.post("/{business_id}/analyze-comments", response_model=CommentAnalysisResponse)
async def analyze_instagram_comments(
    business_id: UUID,
    request: CommentAnalysisRequest,
    db: Session = Depends(get_db)
):
    """
    Perform detailed analysis of Instagram comments for a specific username.
    
    Args:
        business_id: UUID of the business idea
        request: Analysis request parameters including username and analysis types
        db: Database session
        
    Returns:
        CommentAnalysisResponse: Analysis results and status
    """
    try:
        # Verify if business_id exists
        if not db.query(BusinessIdea).filter(BusinessIdea.id == str(business_id)).first():
            raise HTTPException(status_code=404, detail="Business idea not found")
        
        # Check if username exists in the database
        instagram_user = db.query(InstagramUserInfo).filter_by(username=request.username).first()
        if not instagram_user:
            raise HTTPException(status_code=404, detail=f"Instagram user {request.username} not found. You may need to scrape this profile first.")
        
        output_folder = f"businesses/{business_id}/instagram/{request.username}"
        results = {}
        
        # Perform requested analyses
        for analysis_type in request.analysis_types:
            try:
                if analysis_type == "categorization":
                    # Run comment categorization
                    comment_categorizer = InstagramCommentCategorizer(
                        username=request.username,
                        output_folder=output_folder,
                        provider=request.provider,
                        model=request.model
                    )
                    categories = await comment_categorizer.run_analysis()
                    results["categorization"] = {
                        "status": "completed",
                        "categories_count": categories if categories else 0
                    }
                
                elif analysis_type == "topics":
                    # Run topic modeling
                    topic_modeling = InstagramTopicModeling(
                        username=request.username,
                        output_folder=output_folder,
                        num_topics=request.num_topics,
                        lang=request.language
                    )
                    await topic_modeling.run_lda_analysis()
                    results["topics"] = {
                        "status": "completed",
                        "topics_count": request.num_topics,
                        "wordcloud_path": f"{output_folder}/wordcloud.png",
                        "topics_json_path": f"{output_folder}/lda_topics.json"
                    }
                
                elif analysis_type == "sentiment":
                    # Run sentiment and emotion analysis
                    sentiment_analyzer = InstagramSentimentEmotionAnalyzer(
                        username=request.username,
                        output_folder=output_folder
                    )
                    await sentiment_analyzer.analyze_sentiment_and_emotions()
                    results["sentiment"] = {
                        "status": "completed",
                        "sentiment_path": f"{output_folder}/sentiment_analysis.json",
                        "emotion_path": f"{output_folder}/emotion_analysis.json"
                    }
                
            except Exception as e:
                results[analysis_type] = {
                    "status": "failed",
                    "error": str(e)
                }
        
        # Create or update analysis job record in database if needed
        # (You could track analysis jobs similar to scraping jobs)
        
        return CommentAnalysisResponse(
            username=request.username,
            analysis_types=request.analysis_types,
            status="completed" if all(result.get("status") == "completed" for result in results.values()) else "partial",
            results=results
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Also add an endpoint to analyze comments for multiple Instagram accounts at once
@router.post("/{business_id}/analyze-multiple-accounts", response_model=List[CommentAnalysisResponse])
async def analyze_multiple_instagram_accounts(
    business_id: UUID,
    usernames: List[str],
    analysis_types: List[str] = ["categorization", "sentiment", "topics"],
    language: str = "es",
    num_topics: int = 5,
    provider: str = "openai",
    model: str = "gpt-4-0125-preview",
    db: Session = Depends(get_db)
):
    """
    Perform detailed analysis of Instagram comments for multiple usernames.
    
    Args:
        business_id: UUID of the business idea
        usernames: List of Instagram usernames to analyze
        analysis_types: Types of analysis to perform
        language: Language of the comments
        num_topics: Number of topics for LDA analysis
        provider: LLM provider for categorization
        model: LLM model for categorization
        db: Database session
        
    Returns:
        List[CommentAnalysisResponse]: Analysis results and status for each username
    """
    try:
        # Verify if business_id exists
        if not db.query(BusinessIdea).filter(BusinessIdea.id == str(business_id)).first():
            raise HTTPException(status_code=404, detail="Business idea not found")
        
        results = []
        
        for username in usernames:
            # Process each username
            try:
                request = CommentAnalysisRequest(
                    username=username,
                    analysis_types=analysis_types,
                    language=language,
                    num_topics=num_topics,
                    provider=provider,
                    model=model
                )
                
                response = await analyze_instagram_comments(business_id, request, db)
                results.append(response)
                
            except HTTPException as http_exc:
                # If a specific username fails, add error to results but continue with others
                results.append(CommentAnalysisResponse(
                    username=username,
                    analysis_types=analysis_types,
                    status="failed",
                    results={"error": http_exc.detail}
                ))
            except Exception as e:
                results.append(CommentAnalysisResponse(
                    username=username,
                    analysis_types=analysis_types,
                    status="failed",
                    results={"error": str(e)}
                ))
        
        return results
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))