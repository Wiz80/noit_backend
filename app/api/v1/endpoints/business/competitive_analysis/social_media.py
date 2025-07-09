from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Request, Form
from fastapi.responses import JSONResponse
from app.api import deps
from typing import List, Optional, Dict, Any
import uuid
from uuid import UUID
import logging
from app.controllers.competitive_analysis.website_extraction_controller import WebsiteExtractionController

from app.models.business.business_idea import BusinessIdea
from app.models.business.competitive_analysis.competitors import Competitor
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.schemas.business.business_competitors import (
    WebsiteSocialMediaScrapingRequest, 
    WebsiteSocialMediaScrapingResponse,
    WebsiteCorrectionRequest,
    WebsiteCorrectionResponse,
    CorrectedWebsite
)

from app.utils.decode_json import clean_json_encoding
from app.models.user import User

# Import TaskIQ tasks
from app.tasks.social_media_extraction_tasks import extract_social_media_from_websites_task, extract_social_media_from_single_competitor_task
# Import task progress service
from app.services.cache.task_progress_service import get_task_progress_service

# Import Langchain factory for LLM correction
from app.services.llm.langchain_factory import LangChainLLMFactory
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
import json
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/{business_id}", response_model=WebsiteSocialMediaScrapingResponse)
async def extract_social_media_from_websites(
    business_id: UUID,
    request: WebsiteSocialMediaScrapingRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_superuser)
):
    """
    Extract social media information from competitor websites using AI-powered scraping.
    This endpoint creates separate TaskIQ tasks for each competitor for distributed processing.
    
    Args:
        business_id: UUID of the business idea
        request: WebsiteSocialMediaScrapingRequest with optional competitor_ids list and update_db flag
        background_tasks: FastAPI background tasks (not used with TaskIQ)
        db: Database session
        current_user: Current active superuser
        
    Returns:
        WebsiteSocialMediaScrapingResponse: Task information
    """
    try:
        # Verify if business_id exists
        if not db.query(BusinessIdea).filter(BusinessIdea.id == str(business_id)).first():
            raise HTTPException(status_code=404, detail="Business idea not found")

        # Get competitors based on request.competitor_ids (if provided) or all competitors
        query = db.query(Competitor).filter(
            Competitor.business_idea_id == str(business_id)
        )
        
        # Filter by specific competitor IDs if provided
        if request.competitor_ids:
            query = query.filter(Competitor.id.in_(request.competitor_ids))
            logger.info(f"🎯 Processing specific competitors: {len(request.competitor_ids)} IDs provided")
        else:
            logger.info(f"🌍 Processing ALL competitors for business {business_id} (no specific IDs provided)")
            
        competitors = query.all()

        if not competitors:
            error_msg = "No competitors found"
            if request.competitor_ids:
                error_msg += " with provided competitor_ids"
            else:
                error_msg += " for this business"
            raise HTTPException(status_code=404, detail=error_msg)

        # Check that competitors have websites
        competitors_with_websites = [comp for comp in competitors if comp.website]
        if not competitors_with_websites:
            error_msg = "None of the competitors have website URLs"
            if request.competitor_ids:
                error_msg = "None of the requested competitors have website URLs"
            raise HTTPException(status_code=404, detail=error_msg)

        logger.info(f"📊 Analysis results:")
        logger.info(f"   - Total competitors found: {len(competitors)}")
        logger.info(f"   - Competitors with websites: {len(competitors_with_websites)}")
        logger.info(f"   - Will process: {len(competitors_with_websites)} competitors")

        # Generate a main task ID for tracking all sub-tasks
        main_task_id = str(uuid.uuid4())
        
        # Get progress service
        progress_service = get_task_progress_service()
        
        # Initialize main task progress in Redis
        progress_service.set_task_progress(
            task_id=main_task_id,
            progress=0,
            status="queued",
            results={
                "total_competitors": len(competitors_with_websites),
                "completed_competitors": 0,
                "sub_tasks": {}
            }
        )

        # Create separate tasks for each competitor (removed the idx < 2 limit)
        sub_task_ids = []
        failed_tasks = []
        
        for idx, competitor in enumerate(competitors_with_websites):
            try:
                # Generate unique task ID for this competitor
                sub_task_id = str(uuid.uuid4())
                sub_task_ids.append({
                    "competitor_id": competitor.id,
                    "competitor_name": competitor.competitor_name,
                    "task_id": sub_task_id
                })
                
                # Initialize sub-task progress
                progress_service.set_task_progress(
                    task_id=sub_task_id,
                    progress=0,
                    status="queued"
                )
                
                # Queue individual TaskIQ task for this competitor
                taskiq_task = await extract_social_media_from_single_competitor_task.kiq(
                    business_id=str(business_id),
                    competitor_id=competitor.id,
                    task_id=sub_task_id,
                    update_db=request.update_db
                )
                
                logger.info(f"📤 TaskIQ task queued with ID: {taskiq_task.task_id} for competitor {competitor.competitor_name} ({idx + 1}/{len(competitors_with_websites)})")
                
                # Update sub-task progress to indicate it was queued
                progress_service.update_task_progress(sub_task_id, {
                    "status": "queued",
                    "taskiq_task_id": taskiq_task.task_id,
                    "competitor_name": competitor.competitor_name
                })
                
            except Exception as e:
                logger.error(f"❌ Failed to queue TaskIQ task for competitor {competitor.competitor_name}: {str(e)}")
                failed_tasks.append({
                    "competitor_id": competitor.id,
                    "competitor_name": competitor.competitor_name,
                    "error": str(e)
                })
                progress_service.set_task_failed(sub_task_id, f"Failed to queue task: {str(e)}")

        # Update main task with sub-task information
        main_task_results = {
            "total_competitors": len(competitors_with_websites),
            "completed_competitors": 0,
            "queued_tasks": len(sub_task_ids),
            "failed_to_queue": len(failed_tasks),
            "sub_tasks": {task["task_id"]: task for task in sub_task_ids},
            "failed_tasks": failed_tasks
        }
        
        if failed_tasks and len(failed_tasks) == len(competitors_with_websites):
            # All tasks failed to queue
            progress_service.set_task_failed(
                main_task_id, 
                "Failed to queue any tasks",
                results=main_task_results
            )
            raise HTTPException(status_code=500, detail="Failed to queue extraction tasks for any competitor")
        else:
            # At least some tasks were queued successfully
            status = "partially_queued" if failed_tasks else "queued"
            progress_service.update_task_progress(main_task_id, {
                "status": status,
                "results": main_task_results
            })

        logger.info(f"✅ Successfully queued {len(sub_task_ids)} tasks for social media extraction")

        return WebsiteSocialMediaScrapingResponse(
            task_id=main_task_id,
            status=status,
            results=main_task_results
        )

    except Exception as e:
        # If there was a main_task_id created, update its status
        if 'main_task_id' in locals():
            progress_service = get_task_progress_service()
            progress_service.set_task_failed(main_task_id, str(e))
        
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{business_id}/task/{task_id}", response_model=WebsiteSocialMediaScrapingResponse)
async def get_social_media_extraction_progress(
    business_id: UUID,
    task_id: str,
    db: Session = Depends(deps.get_db)
):
    """
    Get the progress of social media extraction for a specific task.
    
    Args:
        business_id: UUID of the business idea
        task_id: Task identifier
        db: Database session
        
    Returns:
        WebsiteSocialMediaScrapingResponse: Task progress information
    """
    # Get progress service
    progress_service = get_task_progress_service()
    
    # Get progress data from Redis
    progress_data = progress_service.get_task_progress(task_id)
    
    if progress_data is None:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return WebsiteSocialMediaScrapingResponse(
        task_id=task_id,
        status=progress_data["status"],
        results=progress_data.get("results")
    )

@router.post("/{business_id}/correct-websites", response_model=WebsiteCorrectionResponse)
async def correct_competitor_websites(
    business_id: UUID,
    request: WebsiteCorrectionRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_superuser)
):
    """
    Correct malformed competitor website URLs using OpenAI LLM.
    
    IMPORTANT: If competitor_ids is not provided or empty, this endpoint will process 
    ALL competitors for the given business_id. This is the default behavior.
    
    This endpoint processes competitors in a single LLM call for efficiency and 
    updates the database with corrected URLs.
    
    Args:
        business_id: UUID of the business idea
        request: WebsiteCorrectionRequest with:
            - competitor_ids (optional): List of specific competitor IDs to correct.
              If empty/null, ALL competitors for this business will be processed.
            - force_update (optional): Whether to force update already correct URLs
        db: Database session
        current_user: Current active superuser
        
    Returns:
        WebsiteCorrectionResponse: Correction results with detailed scope information
    """
    try:
        logger.info(f"🔧 Starting website correction for business {business_id}")
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

        # Filter competitors that need correction
        competitors_to_correct = []
        competitors_without_websites = 0
        competitors_already_correct = 0
        
        for comp in competitors:
            if comp.website:
                # Skip if already looks correct and force_update is False
                if not request.force_update and _is_website_well_formatted(comp.website):
                    competitors_already_correct += 1
                    continue
                competitors_to_correct.append(comp)
            else:
                competitors_without_websites += 1

        logger.info(f"📊 Analysis results for {scope_message}:")
        logger.info(f"   - Total competitors: {len(competitors)}")
        logger.info(f"   - Need correction: {len(competitors_to_correct)}")
        logger.info(f"   - Already correct: {competitors_already_correct}")
        logger.info(f"   - Without websites: {competitors_without_websites}")

        if not competitors_to_correct:
            success_message = f"All websites are already well formatted for {scope_message}"
            logger.info(f"✅ {success_message}")
            return WebsiteCorrectionResponse(
                business_id=str(business_id),
                total_competitors=len(competitors),
                corrected_count=0,
                skipped_count=len(competitors),
                corrected_websites=[],
                success=True,
                message=success_message
            )

        # Prepare data for LLM correction
        websites_to_correct = []
        for comp in competitors_to_correct:
            websites_to_correct.append({
                "competitor_id": comp.id,
                "competitor_name": comp.competitor_name,
                "website": comp.website
            })

        # Call LLM to correct websites (process in batches if too many)
        corrected_data = await _correct_websites_with_llm_batched(websites_to_correct)
        
        # Process results and update database
        corrected_websites = []
        corrected_count = 0
        
        for correction in corrected_data.get("corrected_websites", []):
            competitor_id = correction.get("competitor_id")
            corrected_url = correction.get("corrected_website")
            confidence = correction.get("confidence_score", 0.8)
            
            # Find the competitor in the database
            competitor = db.query(Competitor).filter(Competitor.id == competitor_id).first()
            if competitor:
                original_website = competitor.website
                was_corrected = original_website != corrected_url
                
                # Update website in database if it was corrected
                if was_corrected and corrected_url:
                    competitor.website = corrected_url
                    corrected_count += 1
                
                corrected_websites.append(CorrectedWebsite(
                    competitor_id=competitor_id,
                    competitor_name=competitor.competitor_name,
                    original_website=original_website,
                    corrected_website=corrected_url,
                    was_corrected=was_corrected,
                    confidence_score=confidence
                ))

        # Commit database changes
        db.commit()
        
        final_message = f"Successfully corrected {corrected_count} websites for {scope_message}"
        logger.info(f"✅ {final_message}")

        return WebsiteCorrectionResponse(
            business_id=str(business_id),
            total_competitors=len(competitors),
            corrected_count=corrected_count,
            skipped_count=len(competitors) - len(competitors_to_correct),
            corrected_websites=corrected_websites,
            success=True,
            message=final_message
        )

    except Exception as e:
        logger.error(f"❌ Error correcting websites for business {business_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


def _is_website_well_formatted(website: str) -> bool:
    """
    Check if a website URL is well formatted.
    Returns True if the URL looks correct, False if it needs correction.
    """
    if not website or not isinstance(website, str):
        return False
    
    website = website.strip()
    
    # Check for common malformation patterns
    malformation_patterns = [
        r'\s',  # Contains spaces
        r'https?\s*:',  # Broken protocol
        r'www\s+\.',  # Space in www.
        r'\.\s+[a-z]',  # Space after dot
        r'[,;]',  # Contains commas or semicolons
    ]
    
    for pattern in malformation_patterns:
        if re.search(pattern, website):
            return False
    
    # Check if it has at least a domain structure
    if not re.search(r'\w+\.\w+', website):
        return False
        
    return True


async def _correct_websites_with_llm_batched(websites_data: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Correct websites using LLM, processing in batches if necessary.
    
    Args:
        websites_data: List of dictionaries with competitor data
        
    Returns:
        Combined results from all batches
    """
    # Define batch size based on number of websites (max ~15 per batch to stay under token limits)
    batch_size = 15
    
    if len(websites_data) <= batch_size:
        # Process all at once if small enough
        logger.info(f"🔄 Processing {len(websites_data)} websites in single batch")
        return await _correct_websites_with_llm(websites_data)
    
    # Process in batches
    logger.info(f"🔄 Processing {len(websites_data)} websites in batches of {batch_size}")
    all_corrected_websites = []
    
    for i in range(0, len(websites_data), batch_size):
        batch = websites_data[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (len(websites_data) + batch_size - 1) // batch_size
        
        logger.info(f"📦 Processing batch {batch_num}/{total_batches} ({len(batch)} websites)")
        
        try:
            batch_result = await _correct_websites_with_llm(batch)
            batch_websites = batch_result.get("corrected_websites", [])
            all_corrected_websites.extend(batch_websites)
            logger.info(f"✅ Batch {batch_num} completed with {len(batch_websites)} corrections")
        except Exception as e:
            logger.error(f"❌ Batch {batch_num} failed: {e}")
            # Continue with remaining batches, but log the failure
            continue
    
    return {"corrected_websites": all_corrected_websites}


async def _correct_websites_with_llm(websites_data: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Correct malformed websites using OpenAI LLM in a single call.
    
    Args:
        websites_data: List of dictionaries with competitor_id, competitor_name, and website
        
    Returns:
        Dictionary with corrected websites data
    """
    try:
        # Initialize OpenAI LLM with sufficient tokens for many competitors
        max_tokens = min(4000, len(websites_data) * 200 + 500)  # Dynamic token calculation
        llm = LangChainLLMFactory.create_llm(
            provider="openai",
            model="gpt-4o-mini",
            temperature=0.1,
            max_tokens=max_tokens
        )
        
        logger.info(f"🤖 LLM initialized with {max_tokens} max_tokens for {len(websites_data)} websites")
        
        # Prepare the input data for the prompt
        websites_input = []
        for item in websites_data:
            websites_input.append({
                "competitor_id": item["competitor_id"],
                "competitor_name": item["competitor_name"],
                "website": item["website"]
            })
        
        # Create the correction prompt
        prompt_template = """You are an expert at cleaning and correcting website URLs. I will provide you with a list of competitor websites that may be malformed, and you need to correct them.

IMPORTANT INSTRUCTIONS:
1. Fix common issues like: extra spaces, broken protocols (https:// -> https://), malformed domains
2. Remove any trailing punctuation that's not part of the URL
3. Ensure the URL is functional and properly formatted
4. If a URL is already correct, keep it as is
5. If a URL cannot be corrected or is meaningless, set corrected_website to null
6. Assign a confidence_score between 0.0 and 1.0 based on how confident you are in the correction

INPUT DATA:
{websites_input}

OUTPUT FORMAT (JSON only, no additional text):
{{
  "corrected_websites": [
    {{
      "competitor_id": "competitor_id_here",
      "original_website": "original_url_here",
      "corrected_website": "corrected_url_here_or_null",
      "confidence_score": 0.95,
      "correction_applied": "description of what was fixed"
    }}
  ]
}}

Remember: Output ONLY the JSON, no explanations or markdown."""

        formatted_prompt = prompt_template.format(websites_input=json.dumps(websites_input, indent=2))
        
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
            logger.info(f"✅ LLM successfully corrected {len(corrected_data.get('corrected_websites', []))} websites")
            return corrected_data
        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse LLM JSON response: {e}")
            logger.error(f"Response content length: {len(response_content)} chars")
            logger.error(f"Response content preview: {response_content[:500]}...")
            
            # Try to fix truncated JSON by attempting to close incomplete structures
            try:
                # If the JSON seems to be cut off, try to complete it
                fixed_content = _attempt_json_repair(response_content)
                if fixed_content:
                    corrected_data = json.loads(fixed_content)
                    logger.warning(f"⚠️ Recovered partial JSON with {len(corrected_data.get('corrected_websites', []))} websites")
                    return corrected_data
                else:
                    raise ValueError(f"Could not repair truncated JSON: {e}")
            except Exception as repair_error:
                logger.error(f"❌ JSON repair also failed: {repair_error}")
                raise ValueError(f"Invalid JSON response from LLM and repair failed: {e}")
            
    except Exception as e:
        logger.error(f"❌ Error in LLM website correction: {str(e)}")
        raise ValueError(f"LLM correction failed: {str(e)}")


def _attempt_json_repair(truncated_json: str) -> Optional[str]:
    """
    Attempt to repair truncated JSON by completing incomplete structures.
    
    Args:
        truncated_json: The potentially truncated JSON string
        
    Returns:
        Fixed JSON string or None if repair fails
    """
    try:
        # Count open braces and brackets to determine what's missing
        open_braces = truncated_json.count('{') - truncated_json.count('}')
        open_brackets = truncated_json.count('[') - truncated_json.count(']')
        open_quotes = truncated_json.count('"') % 2
        
        fixed_json = truncated_json.strip()
        
        # If there's an incomplete string (odd number of quotes), try to close it
        if open_quotes == 1:
            if not fixed_json.endswith('"'):
                fixed_json += '"'
        
        # Remove any incomplete trailing content that might be causing issues
        if fixed_json.endswith(','):
            fixed_json = fixed_json[:-1]
        
        # If there's an incomplete object/array, try to close it
        if fixed_json.endswith(',') or fixed_json.endswith('":'):
            # Find the last complete entry and truncate there
            last_complete = fixed_json.rfind('},')
            if last_complete > 0:
                fixed_json = fixed_json[:last_complete + 1]
        
        # Close any remaining open structures
        for _ in range(open_brackets):
            fixed_json += ']'
        for _ in range(open_braces):
            fixed_json += '}'
        
        # Test if the repair worked
        json.loads(fixed_json)
        return fixed_json
        
    except Exception as e:
        logger.debug(f"JSON repair attempt failed: {e}")
        return None