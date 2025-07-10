# routes/competitor_analysis.py

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from openai import OpenAI
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import uuid
from uuid import UUID
from datetime import datetime
import requests
import json
import logging
import os
from dotenv import load_dotenv

from app.api import deps
from app.api.deps import get_db
from app.models.business.business_idea import BusinessIdea
from app.models.business.competitive_analysis.competitors import Competitor
from app.models.business.competitive_analysis.instagram import InstagramScrapingJob, InstagramUserInfo
from app.controllers.competitive_analysis.instagram_competitor_controller import InstagramCompetitorController
from app.services.search.dynamic_research_ai import ResearchModule, ResearchConfig
from app.prompts.business.prompts_business_competitors import create_validation_competitor_prompt
from app.models.user import User

# Import TaskIQ task
from app.tasks.instagram_analysis_tasks import run_instagram_full_analysis_task
# Import task progress service
from app.services.cache.task_progress_service import get_task_progress_service

# Import for Instagram URL correction
from app.schemas.business.business_competitors import (
    InstagramCorrectionRequest,
    InstagramCorrectionResponse,
    CorrectedInstagramUrl
)
from app.services.llm.langchain_factory import LangChainLLMFactory
from langchain_core.messages import HumanMessage
import re

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

@router.get("/instagram-posts/{competitor_id}")
async def get_instagram_posts(
    competitor_id: str,
    db: Session = Depends(get_db)
):
    """
    Get the Instagram posts data for a specific competitor.
    
    Args:
        competitor_id: ID of the competitor to get posts for
        db: Database session
        
    Returns:
        dict: Instagram posts data
    """
    try:
        # Verify if competitor_id exists
        competitor = db.query(Competitor).filter(Competitor.id == competitor_id).first()
        if not competitor:
            raise HTTPException(status_code=404, detail="Competitor not found")
        
        # get the username from the competitor
        # example: https://www.instagram.com/intel
        username = competitor.instagram_url.rstrip("/").split("/")[-1]
        
        # Get data from MinIO
        from app.services.storage.minio_service import MinioService
        import json
        
        output_folder = f"{competitor.business_idea_id}/competitor-analysis/instagram"
        minio_service = MinioService(bucket_name=settings.MINIO_BUCKET_NAME)
        posts_object_name = f"{output_folder}/{username}/instagram_posts.json"
        
        try:
            # Get JSON data from MinIO
            posts_data = minio_service.get_object_data(posts_object_name)
            if not posts_data:
                raise HTTPException(status_code=404, detail="Instagram posts data not found")
                
            # Parse JSON data
            posts = json.loads(posts_data.decode('utf-8'))
            return posts
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error fetching Instagram posts: {str(e)}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/instagram-profile/{competitor_id}")
async def get_instagram_profile(
    competitor_id: str,
    db: Session = Depends(get_db)
):
    """
    Get the Instagram profile data for a specific competitor.
    
    Args:
        competitor_id: ID of the competitor to get profile for
        db: Database session
        
    Returns:
        dict: Instagram profile data
    """
    try:
        # Verify if competitor_id exists
        competitor = db.query(Competitor).filter(Competitor.id == competitor_id).first()
        if not competitor:
            raise HTTPException(status_code=404, detail="Competitor not found")
        
        # get the username from the competitor
        # example: https://www.instagram.com/intel
        username = competitor.instagram_url.rstrip("/").split("/")[-1]
        
        # Get data from MinIO
        from app.services.storage.minio_service import MinioService
        import json
        
        output_folder = f"{competitor.business_idea_id}/competitor-analysis/instagram"
        minio_service = MinioService(bucket_name=settings.MINIO_BUCKET_NAME)
        profile_object_name = f"{output_folder}/{username}/instagram_profile.json"
        
        try:
            # Get JSON data from MinIO
            profile_data = minio_service.get_object_data(profile_object_name)
            if not profile_data:
                raise HTTPException(status_code=404, detail="Instagram profile data not found")
                
            # Parse JSON data
            profile = json.loads(profile_data.decode('utf-8'))
            return profile
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error fetching Instagram profile: {str(e)}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/{business_id}/correct-instagram-urls", response_model=InstagramCorrectionResponse)
async def correct_competitor_instagram_urls(
    business_id: UUID,
    request: InstagramCorrectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_superuser)
):
    """
    Correct or find Instagram URLs for competitors using OpenAI LLM.
    
    IMPORTANT: If competitor_ids is not provided or empty, this endpoint will process 
    ALL competitors for the given business_id. This is the default behavior.
    
    The LLM will use the competitor's name and website to find the correct Instagram URL.
    
    Args:
        business_id: UUID of the business idea
        request: InstagramCorrectionRequest with:
            - competitor_ids (optional): List of specific competitor IDs to correct.
              If empty/null, ALL competitors for this business will be processed.
            - force_update (optional): Whether to force update already existing Instagram URLs
        db: Database session
        current_user: Current active superuser
        
    Returns:
        InstagramCorrectionResponse: Correction results with detailed scope information
    """
    try:
        logger.info(f"🔧 Starting Instagram URL correction for business {business_id}")
        logger.info(f"🎯 Request: competitor_ids={request.competitor_ids}, force_update={request.force_update}")
        
        # Verify if business_id exists
        business_idea = db.query(BusinessIdea).filter(BusinessIdea.id == str(business_id)).first()
        if not business_idea:
            raise HTTPException(status_code=404, detail="Business idea not found")

        # Determine scope: specific competitors or all competitors for this business
        if request.competitor_ids and len(request.competitor_ids) > 0:
            # Process only specific competitor IDs provided
            logger.info(f"🎯 Processing specific competitors: {len(request.competitor_ids)} IDs provided")
            query = db.query(Competitor).filter(
                Competitor.business_idea_id == str(business_id),
                Competitor.id.in_(request.competitor_ids)
            )
            scope_message = f"specific {len(request.competitor_ids)} competitors"
        else:
            # Process ALL competitors for this business (default behavior)
            logger.info(f"🌍 Processing ALL competitors for business {business_id} (no specific IDs provided)")
            query = db.query(Competitor).filter(
                Competitor.business_idea_id == str(business_id)
            )
            scope_message = "all competitors for this business"
            
        competitors = query.all()

        if not competitors:
            error_msg = f"No competitors found for {scope_message}"
            logger.warning(f"⚠️ {error_msg}")
            raise HTTPException(status_code=404, detail=error_msg)

        # Filter competitors that need Instagram URL correction
        competitors_to_correct = []
        competitors_already_have_instagram = 0
        competitors_without_data = 0
        
        for comp in competitors:
            # Check if competitor has enough data (name at least)
            if not comp.competitor_name:
                competitors_without_data += 1
                continue
                
            # Skip if already has Instagram URL and force_update is False
            if comp.instagram_url and not request.force_update:
                competitors_already_have_instagram += 1
                continue
                
            competitors_to_correct.append(comp)

        logger.info(f"📊 Analysis results for {scope_message}:")
        logger.info(f"   - Total competitors: {len(competitors)}")
        logger.info(f"   - Need Instagram URL: {len(competitors_to_correct)}")
        logger.info(f"   - Already have Instagram: {competitors_already_have_instagram}")
        logger.info(f"   - Without sufficient data: {competitors_without_data}")

        if not competitors_to_correct:
            success_message = f"All competitors already have Instagram URLs for {scope_message}"
            logger.info(f"✅ {success_message}")
            return InstagramCorrectionResponse(
                business_id=str(business_id),
                total_competitors=len(competitors),
                corrected_count=0,
                skipped_count=len(competitors),
                corrected_instagram_urls=[],
                success=True,
                message=success_message
            )

        # Prepare data for LLM correction
        competitors_data = []
        for comp in competitors_to_correct:
            competitors_data.append({
                "competitor_id": comp.id,
                "competitor_name": comp.competitor_name,
                "website": comp.website,
                "current_instagram_url": comp.instagram_url
            })

        # Call LLM to find Instagram URLs
        corrected_data = await _find_instagram_urls_with_llm(competitors_data)
        
        # Process results and update database
        corrected_instagram_urls = []
        corrected_count = 0
        
        for correction in corrected_data.get("corrected_instagram_urls", []):
            competitor_id = correction.get("competitor_id")
            new_instagram_url = correction.get("instagram_url")
            confidence = correction.get("confidence_score", 0.7)
            reasoning = correction.get("reasoning", "")
            
            # Find the competitor in the database
            competitor = db.query(Competitor).filter(Competitor.id == competitor_id).first()
            if competitor:
                original_instagram_url = competitor.instagram_url
                was_corrected = original_instagram_url != new_instagram_url
                
                # Update Instagram URL in database if it was found/corrected
                if was_corrected and new_instagram_url:
                    competitor.instagram_url = new_instagram_url
                    corrected_count += 1
                
                corrected_instagram_urls.append(CorrectedInstagramUrl(
                    competitor_id=competitor_id,
                    competitor_name=competitor.competitor_name,
                    competitor_website=competitor.website,
                    original_instagram_url=original_instagram_url,
                    corrected_instagram_url=new_instagram_url,
                    was_corrected=was_corrected,
                    confidence_score=confidence,
                    reasoning=reasoning
                ))

        # Commit database changes
        db.commit()
        
        final_message = f"Successfully found/corrected {corrected_count} Instagram URLs for {scope_message}"
        logger.info(f"✅ {final_message}")

        return InstagramCorrectionResponse(
            business_id=str(business_id),
            total_competitors=len(competitors),
            corrected_count=corrected_count,
            skipped_count=len(competitors) - len(competitors_to_correct),
            corrected_instagram_urls=corrected_instagram_urls,
            success=True,
            message=final_message
        )

    except Exception as e:
        logger.error(f"❌ Error correcting Instagram URLs for business {business_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


async def _find_instagram_urls_with_llm(competitors_data: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Find Instagram URLs for competitors using OpenAI LLM.
    
    Args:
        competitors_data: List of dictionaries with competitor information
        
    Returns:
        Dictionary with Instagram URLs data
    """
    try:
        # Initialize OpenAI LLM
        max_tokens = min(4000, len(competitors_data) * 300 + 500)  # Dynamic token calculation
        llm = LangChainLLMFactory.create_llm(
            provider="openai",
            model="gpt-4o-mini",
            temperature=0.1,
            max_tokens=max_tokens
        )
        
        logger.info(f"🤖 LLM initialized with {max_tokens} max_tokens for {len(competitors_data)} competitors")
        
        # Prepare the input data for the prompt
        competitors_input = []
        for item in competitors_data:
            competitors_input.append({
                "competitor_id": item["competitor_id"],
                "competitor_name": item["competitor_name"],
                "website": item["website"],
                "current_instagram_url": item.get("current_instagram_url")
            })
        
        # Create the Instagram URL finding prompt
        prompt_template = """You are an expert at finding social media accounts for businesses and brands. I will provide you with a list of competitors and you need to find their Instagram URLs.

IMPORTANT INSTRUCTIONS:
1. Use the competitor name and website to determine the most likely Instagram account
2. Instagram URLs should be in format: https://instagram.com/username or https://www.instagram.com/username
3. If you're confident about the Instagram account, provide it
4. If you cannot confidently determine the Instagram account, set instagram_url to null
5. Assign a confidence_score between 0.0 and 1.0 based on how confident you are
6. Provide reasoning for your decision
7. Consider common patterns: company names, brand names, website domains without extensions
8. Look for verified or business accounts when possible

INPUT DATA:
{competitors_input}

OUTPUT FORMAT (JSON only, no additional text):
{{
  "corrected_instagram_urls": [
    {{
      "competitor_id": "competitor_id_here",
      "competitor_name": "Company Name",
      "website": "https://website.com",
      "instagram_url": "https://instagram.com/username_or_null",
      "confidence_score": 0.85,
      "reasoning": "Based on company name and website domain, this is likely their Instagram account"
    }}
  ]
}}

EXAMPLES OF GOOD REASONING:
- "Company name matches Instagram handle exactly"
- "Website domain matches Instagram username pattern"  
- "Well-known brand with verified Instagram account"
- "Common business naming pattern suggests this handle"
- "Could not confidently identify - multiple possibilities exist"
- "No clear Instagram presence found for this competitor"

Remember: Output ONLY the JSON, no explanations or markdown."""

        formatted_prompt = prompt_template.format(competitors_input=json.dumps(competitors_input, indent=2))
        
        # Make the LLM call
        response = llm.invoke([HumanMessage(content=formatted_prompt)])
        response_content = response.content.strip()
        
        # Clean and parse the JSON response
        if response_content.startswith("```json"):
            response_content = response_content[7:]
        if response_content.endswith("```"):
            response_content = response_content[:-3]
        
        response_content = response_content.strip()
        
        try:
            corrected_data = json.loads(response_content)
            logger.info(f"✅ LLM successfully found Instagram URLs for {len(corrected_data.get('corrected_instagram_urls', []))} competitors")
            return corrected_data
        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse LLM JSON response: {e}")
            logger.error(f"Response content length: {len(response_content)} chars")
            logger.error(f"Response content preview: {response_content[:500]}...")
            raise ValueError(f"Invalid JSON response from LLM: {e}")
            
    except Exception as e:
        logger.error(f"❌ Error in LLM Instagram URL finding: {str(e)}")
        raise ValueError(f"LLM Instagram URL finding failed: {str(e)}")