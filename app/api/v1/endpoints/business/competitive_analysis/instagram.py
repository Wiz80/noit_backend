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

# Schema for competitor analysis request
class CompetitorAnalysisRequest(BaseModel):
    competitors_ids: Optional[List[str]] = None
    
    def get_competitor_ids(self):
        """Return the competitor IDs, using competitors_ids as fallback if competitor_ids is None"""
        return self.competitors_ids or None

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

# Simple cache to store task progress
# In production, you should use Redis or similar
analysis_progress = {}

@router.post("/{business_id}", response_model=AnalysisResponse)
async def start_instagram_competitor_analysis(
    business_id: UUID,
    request: CompetitorAnalysisRequest,
    background_tasks: BackgroundTasks,
    results_limit: int = 10,
    max_comments: int = 5,
    db: Session = Depends(get_db)
):
    """
    Start Instagram competitor analysis for a specific business_id.
    Allows filtering specific competitors by providing their IDs in the request body.
    
    Args:
        business_id: UUID of the business idea
        request: Request body containing:
            - competitor_ids: Optional list of competitor IDs to analyze. If not provided or empty,
              all competitors for the business will be analyzed.
        background_tasks: FastAPI background tasks (not used currently)
        results_limit: Maximum number of posts to extract per Instagram account (default: 10)
        max_comments: Maximum number of comments to extract per post (default: 5)
        db: Database session
        
    Returns:
        AnalysisResponse: Task information and results
    """
    try:
        # Verify if business_id exists
        if not db.query(BusinessIdea).filter(BusinessIdea.id == str(business_id)).first():
            raise HTTPException(status_code=404, detail="Business idea not found")

        # Check if there are competitors with Instagram URLs
        competitors_query = db.query(Competitor).filter(
            Competitor.business_idea_id == str(business_id)
        )
        
        # Filter by competitor_ids if provided
        if request.competitors_ids:
            competitors_query = competitors_query.filter(
                Competitor.id.in_(request.competitors_ids)
            )
            
        competitors = competitors_query.all()

        if not competitors:
            raise HTTPException(status_code=404, detail="No competitors found with the specified criteria")
            
        # Verify that the competitors have Instagram URLs
        valid_competitors = [c for c in competitors if c.instagram_url]
        if not valid_competitors:
            raise HTTPException(status_code=404, detail="None of the selected competitors have Instagram URLs")
            
        # If only some competitors have Instagram URLs, log a warning
        if len(valid_competitors) < len(competitors):
            logging.warning(f"{len(competitors) - len(valid_competitors)} competitors without Instagram URLs will be skipped")
            competitors = valid_competitors

        # Generate a unique task ID
        task_id = str(uuid.uuid4())
        
        # Initialize progress
        analysis_progress[task_id] = {
            "progress": 0,
            "status": "started",
            "results": {},
            "error": None
        }

        # Run analysis synchronously for debugging
        await run_instagram_full_analysis(
            business_id=str(business_id),
            task_id=task_id,
            db=db,
            competitor_ids=request.competitors_ids,
            competitors=valid_competitors,
            results_limit=results_limit,
            max_comments=max_comments
        )

        # Get the final results from the progress cache
        final_result = analysis_progress.get(task_id, {})
        
        # Add details about skipped competitors if any were filtered out
        skipped_message = ""
        if len(valid_competitors) < len(competitors):
            skipped_count = len(competitors) - len(valid_competitors)
            skipped_message = f" ({skipped_count} competitors were skipped due to missing Instagram URLs)"

        return AnalysisResponse(
            task_id=task_id,
            message=f"Instagram competitor analysis completed with status: {final_result.get('status', 'unknown')}{skipped_message}",
            status=final_result.get("status", "unknown")
        )

    except Exception as e:
        # If there was a task_id created, update its status
        if 'task_id' in locals():
            analysis_progress[task_id] = {
                "status": "failed",
                "error": str(e),
                "progress": 0
            }
        
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
    if task_id not in analysis_progress:
        raise HTTPException(status_code=404, detail="Task not found")

    progress_data = analysis_progress[task_id]
    
    return AnalysisProgressResponse(
        task_id=task_id,
        progress=progress_data["progress"],
        status=progress_data["status"],
        results=progress_data.get("results")
    )

async def run_instagram_full_analysis(business_id: str, task_id: str, db: Session, competitor_ids: Optional[List[str]] = None, competitors: Optional[List[Competitor]] = None, results_limit: int = 10, max_comments: int = 5):
    """
    Function that executes full Instagram analysis in the background using InstagramScraper.
    Now uses the InstagramCompetitorController for better separation of concerns.
    
    Args:
        business_id: Business idea ID
        task_id: Task identifier
        db: Database session
        competitor_ids: Optional list of competitor IDs to analyze
        competitors: Optional pre-filtered list of competitors to analyze
        results_limit: Maximum number of posts to extract per Instagram account
        max_comments: Maximum number of comments to extract per post
    """
    try:
        # If competitors are already provided, use them
        if not competitors:
            # Get competitors for this business idea
            competitors_query = db.query(Competitor).filter(
                Competitor.business_idea_id == business_id
            )
            
            # Filter by competitor_ids if provided
            if competitor_ids:
                competitors_query = competitors_query.filter(
                    Competitor.id.in_(competitor_ids)
                )
                
            competitors = competitors_query.all()
            
            # Filter out competitors without Instagram URLs
            competitors = [c for c in competitors if c.instagram_url]

        total_competitors = len(competitors)
        completed = 0
        results = {}
        
        # Initialize the controller
        controller = InstagramCompetitorController(business_id=business_id)
        
        for competitor in competitors:
            try:
                instagram_url = competitor.instagram_url

                username = controller.extract_instagram_username(instagram_url)
                
                if username:
                    # Use the controller to analyze this competitor
                    result = await controller.analyze_instagram_competitor(
                        username=username,
                        competitor_id=competitor.id,
                        results_limit=results_limit,
                        max_comments=max_comments
                    )
                    
                    results[competitor.competitor_name] = {
                        "instagram_username": username,
                        "competitor_id": competitor.id,
                        "status": result.get("status", "completed"),
                        "message": result.get("message", "")
                    }
                    completed += 1
                else:
                    results[competitor.competitor_name] = {
                        "instagram_username": None,
                        "competitor_id": competitor.id,
                        "status": "skipped",
                        "reason": "Invalid Instagram URL"
                    }
                    completed += 1
            
            except Exception as e:
                results[competitor.competitor_name] = {
                    "instagram_username": username if 'username' in locals() else None,
                    "competitor_id": competitor.id,
                    "status": "failed",
                    "error": str(e)
                }
                completed += 1
            
            # Update progress
            progress = int((completed / total_competitors) * 100)
            analysis_progress[task_id].update({
                "progress": progress,
                "results": results,
                "status": "processing"
            })

        # Check if all competitors are completed or in research_in_progress state
        all_completed = all(
            result.get("status") != "research_in_progress" 
            for result in results.values()
        )
        
        # If all are completed, mark the task as completed
        if all_completed:
            analysis_progress[task_id].update({
                "progress": 100,
                "status": "completed",
                "results": results
            })
        else:
            # Otherwise, mark it as waiting for research callbacks
            analysis_progress[task_id].update({
                "status": "waiting_for_research",
                "results": results
            })

    except Exception as e:
        analysis_progress[task_id].update({
            "status": "failed",
            "error": str(e)
        })
        raise

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
    if task_id not in analysis_progress:
        raise HTTPException(status_code=404, detail="Task not found")

    analysis_progress[task_id].update({
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