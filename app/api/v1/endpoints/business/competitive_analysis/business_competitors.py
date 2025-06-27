from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Request, Form
from app.api import deps
from typing import List, Optional, Dict, Any
import json
import logging
from fastapi.responses import JSONResponse
import uuid
from uuid import UUID
import datetime
import httpx
from pydantic import BaseModel

from app.services.storage.minio_service import MinioService
from app.services.business.competitive_analysis.business_competitors_extraction import EnhancedBusinessAnalyzer, CompetitorInfo, BusinessModel
from app.controllers.competitive_analysis.business_competitor_controller import BusinessCompetitorController
from app.controllers.competitive_analysis.website_extraction_controller import WebsiteExtractionController
from app.core.config import settings

from app.models.business.business_idea import BusinessIdea
from app.models.business.business_progress import BusinessProgress, StepStatus
from app.models.business.competitive_analysis.business_competitor import CompetitorResearch, CompetitorResearchStatus
from app.models.business.competitive_analysis.competitors import Competitor
from app.models.business.business_understanding.business_model import BusinessModel as BusinessModelDB
from app.models.user import User

from app.schemas.business.business_competitors import (
    CompetitorAnalysisRequest, 
    CompetitorAnalysisCallback,
    GetCompetitorsResponse,
    Competitor as CompetitorSchema
)
from sqlalchemy.orm import Session

from app.utils.decode_json import clean_json_encoding

# Import TaskIQ task
from app.tasks.competitor_analysis_tasks import research_competitors_task

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Simple cache to store task progress
# In production, you should use Redis or similar
analysis_progress = {}

router = APIRouter()

class InternalCompetitorAnalysisRequest(BaseModel):
    """Request model for internal competitor analysis (used by Kestra)"""
    business_id: str
    language: str = "es"
    validator_provider: str = "openai"
    validator_model: str = "gpt-4o-mini"
    research_model: str = "sonar-deep-research"
    search_prompt: str = "Análisis detallado de competidores"
    base_url: str = "http://app:8000"
    triggered_by: str = "internal_automation"

@router.post("/{business_id}")
async def analyze_competitors(
    business_id: str,
    request: Optional[InternalCompetitorAnalysisRequest] = None,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_superuser)
) -> JSONResponse:
    """
    Internal endpoint to analyze competitors based on a business model.
    This endpoint is designed for internal use (Kestra automation) and doesn't require authentication.
    
    Args:
        business_id: ID of the business idea
        request: Optional InternalCompetitorAnalysisRequest with analysis parameters
        db: Database session
    
    Returns:
        JSONResponse with analysis results or error details
    """
    try:
        # Set default values if no request provided
        if not request:
            request = InternalCompetitorAnalysisRequest(business_id=business_id)
        
        # Verify business idea exists
        business_idea = db.query(BusinessIdea).filter(BusinessIdea.id == business_id).first()
        if not business_idea:
            logger.error(f"Business idea not found: {business_id}")
            raise HTTPException(status_code=404, detail="Business idea not found")

        # Get business model from database (primary source)
        business_model_db = db.query(BusinessModelDB).filter(
            BusinessModelDB.business_id == business_id
        ).first()
        
        if not business_model_db:
            logger.info(f"Business model not found in database for {business_id}, trying MinIO fallback")
            return JSONResponse(
                status_code=404,
                content={
                    "message": "Business model not found in database",
                    "business_id": business_id
                }
            )


        business_idea_text = f"""
        {business_idea.title}:

        DESCRIPCIÓN:
        {business_idea.description}
        """

        # Create comprehensive BusinessModel object with all fields
        business_model = BusinessModel(
            business_idea=business_idea_text,
            customer_persona=business_model_db.customer_persona or "",
            industry=business_model_db.industry or "",
            problem_definition=business_model_db.problem_definition,
            value_proposition=business_model_db.value_proposition,
            competitive_advantage=business_model_db.competitive_advantage,
            products_services=business_model_db.products_services,
            challenges_opportunities=business_model_db.challenges_opportunities
        )

        # Check if there's already a pending research for this business_id
        existing_research = db.query(CompetitorResearch).filter(
            CompetitorResearch.business_id == business_id,
            CompetitorResearch.status == CompetitorResearchStatus.PENDING
        ).first()
        
        if existing_research:
            # If there's already a pending research, reuse it
            logger.info(f"Found existing pending research for business {business_id}, reusing it: {existing_research.id}")
            request_id = existing_research.id
            
            return JSONResponse(
                status_code=200,
                content={
                    "message": f"Competitor analysis already in progress (triggered by {request.triggered_by})",
                    "business_id": business_id,
                    "request_id": request_id,
                    "status": "pending",
                    "triggered_by": request.triggered_by
                }
            )
        else:
            # Create a new research record
            request_id = str(uuid.uuid4())
            
            research_record = CompetitorResearch(
                id=request_id,
                business_id=business_id,
                status=CompetitorResearchStatus.PENDING,
                language=request.language,
                model=request.research_model
            )
            db.add(research_record)
            
            # Update business progress to indicate competitive analysis started
            business_progress = db.query(BusinessProgress).filter(
                BusinessProgress.business_id == business_id
            ).first()
            
            if not business_progress:
                # Create new progress record
                business_progress = BusinessProgress(
                    business_id=business_id,
                    competitive_analysis_status=StepStatus.IN_PROGRESS,
                    competitive_analysis_id=request_id
                )
                db.add(business_progress)
                logger.info(f"Created new business progress record for {business_id}")
            else:
                # Update existing progress
                business_progress.competitive_analysis_status = StepStatus.IN_PROGRESS
                business_progress.competitive_analysis_id = request_id
                logger.info(f"Updated existing business progress for {business_id}")
            
            db.commit()
            logger.info(f"Created new research record with ID {request_id} for business {business_id} (triggered by {request.triggered_by})")
        
        # Create callback URL for research completion
        callback_url = f"{request.base_url}/api/v1/webhooks/competitor-analysis-callback/{request_id}"
        
        # Initialize MinIO service for questions storage
        minio_service = MinioService(bucket_name=settings.MINIO_BUCKET_NAME)
        
        # Check if competitor questions already exist in MinIO
        questions_filename = f"{business_id}/competitor-analysis/competitor_questions_{request.language}.json"
        
        # Try to get existing questions first
        questions = None
        if minio_service.object_exists(questions_filename):
            try:
                logger.info(f"Found existing competitor questions for business {business_id}")
                questions_data = minio_service.download_json(questions_filename)
                questions = questions_data.get("questions", [])
            except Exception as e:
                logger.warning(f"Error loading existing questions, will regenerate: {str(e)}")
                questions = None
        
        # Initialize the competitor analysis controller
        controller = BusinessCompetitorController(business_id=business_id)
                
        # If we don't have questions, generate them and save to MinIO
        if not questions:
            logger.info(f"Generating new competitor questions for business {business_id}")
            questions = await controller.generate_competitor_questions(
                business_model=business_model,
                lang=request.language
            )
            
            # Save questions to MinIO for future use
            questions_data = {
                "business_id": business_id,
                "language": request.language,
                "questions": questions,
                "generated_at": datetime.datetime.now().isoformat(),
                "industry": business_model.industry,
                "triggered_by": request.triggered_by
            }
            
            try:
                await minio_service.upload_content(
                    questions_filename,
                    json.dumps(questions_data),
                    content_type="application/json"
                )
                logger.info(f"Saved competitor questions to MinIO: {questions_filename}")
            except Exception as e:
                logger.error(f"Error saving questions to MinIO: {str(e)}")
        
        # Save initial data to MinIO before starting the research
        initial_data = {
            "request_id": request_id,
            "business_id": business_id,
            "status": "pending",
            "questions": questions,
            "timestamp": datetime.datetime.now().isoformat(),
            "triggered_by": request.triggered_by
        }
        
        results_filename = f"{business_id}/competitor-analysis/competitors.json"
        await minio_service.upload_content(
            results_filename, 
            json.dumps(initial_data), 
            content_type='application/json'
        )
        
        # Import the create_research_query function
        from app.prompts.business.prompts_business_competitors import create_research_query
        
        # Combine the search prompt with the formatted research query using comprehensive business details
        combined_prompt = create_research_query(
            lang=request.language,
            business_details=business_model.get_comprehensive_description(),
            prompt_search=request.search_prompt
        )
        
        # Create the modified prompt with the combined search query
        modified_prompt = {
            "search_query": combined_prompt,
            "callback_url": callback_url,
            "request_id": request_id,
            "business_id": business_id,
            "base_url": request.base_url,
            "research_type": "competitor_analysis",
            "triggered_by": request.triggered_by
        }
        
        # Start the analysis using TaskIQ instead of FastAPI background tasks
        try:
            # Convert BusinessModel to dictionary for serialization
            business_model_dict = {
                "business_idea": business_model.business_idea,
                "customer_persona": business_model.customer_persona,
                "industry": business_model.industry,
                "problem_definition": business_model.problem_definition,
                "value_proposition": business_model.value_proposition,
                "competitive_advantage": business_model.competitive_advantage,
                "products_services": business_model.products_services,
                "challenges_opportunities": business_model.challenges_opportunities
            }
            
            # Send task to TaskIQ queue
            task = await research_competitors_task.kiq(
                prompt_search=modified_prompt,
                business_id=business_id,
                request_id=request_id,
                business_model_dict=business_model_dict,
                lang=request.language
            )
            
            logger.info(f"TaskIQ task queued with ID: {task.task_id} for business {business_id}, request_id: {request_id} (triggered by {request.triggered_by})")
            
        except Exception as task_error:
            logger.error(f"Error queueing TaskIQ task: {str(task_error)}")
            # Fallback to direct execution for testing
            try:
                # Convert BusinessModel to dictionary for serialization
                business_model_dict = {
                    "business_idea": business_model.business_idea,
                    "customer_persona": business_model.customer_persona,
                    "industry": business_model.industry,
                    "problem_definition": business_model.problem_definition,
                    "value_proposition": business_model.value_proposition,
                    "competitive_advantage": business_model.competitive_advantage,
                    "products_services": business_model.products_services,
                    "challenges_opportunities": business_model.challenges_opportunities
                }
                
                await research_competitors_task(
                    modified_prompt,
                    business_id,
                    request_id,
                    business_model_dict,
                    request.language
                )
            except Exception as fallback_error:
                logger.error(f"Fallback execution also failed: {str(fallback_error)}")
                # Update research status to failed
                research_record.status = CompetitorResearchStatus.FAILED
                db.commit()
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to start competitor analysis: {str(fallback_error)}"
                )
        
        logger.info(f"Competitor analysis started for business {business_id}, request_id: {request_id} (triggered by {request.triggered_by})")

        return JSONResponse(
            status_code=202,
            content={
                "message": f"Competitor analysis started (triggered by {request.triggered_by})",
                "business_id": business_id,
                "request_id": request_id,
                "status": "pending",
                "questions": questions,
                "triggered_by": request.triggered_by
            }
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Unexpected error in competitor analysis: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Server error: {str(e)}"
        )



@router.get("/status/{request_id}")
async def get_research_status(
    request_id: str,
    db: Session = Depends(deps.get_db)
) -> JSONResponse:
    """
    Get the status of a competitor research request
    
    Args:
        request_id: ID of the research request
        db: Database session
    
    Returns:
        JSONResponse with the current status of the research
        The response includes the generated questions which are cached in MinIO
        for future use to avoid regeneration if the process fails.
    """
    try:
        # Get the research record from the database
        research = db.query(CompetitorResearch).filter(
            CompetitorResearch.id == request_id
        ).first()
        
        if not research:
            raise HTTPException(
                status_code=404,
                detail=f"Research with ID {request_id} not found"
            )
        
        # Check if results exist in MinIO
        minio_service = MinioService(bucket_name=settings.MINIO_BUCKET_NAME)
        results_filename = f"{research.business_id}/competitor-analysis/competitors.json"
        
        if minio_service.object_exists(results_filename):
            results = minio_service.download_json(results_filename)
            
            return JSONResponse(
                content={
                    "request_id": request_id,
                    "business_id": research.business_id,
                    "status": research.status,
                    "created_at": research.created_at.isoformat(),
                    "completed_at": research.completed_at.isoformat() if research.completed_at else None,
                    "results": results
                }
            )
        else:
            return JSONResponse(
                content={
                    "request_id": request_id,
                    "business_id": research.business_id,
                    "status": research.status,
                    "created_at": research.created_at.isoformat(),
                    "completed_at": research.completed_at.isoformat() if research.completed_at else None,
                    "message": "Results not found in storage"
                }
            )
            
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error retrieving research status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving research status: {str(e)}"
        )

@router.get("/business-models/{business_model_id}/analysis-results")
async def get_analysis_results(
    business_model_id: str,
    db: Session = Depends(deps.get_db)
):
    """
    Get the results of a previously executed competitor analysis
    
    Args:
        business_model_id: ID of the business model used for analysis
        
    Returns:
        Analysis results if available
    """
    try:
        minio_service = MinioService(bucket_name=settings.MINIO_BUCKET_NAME)
        results_filename = f"analysis_results_{business_model_id}.json"

        if not minio_service.object_exists(results_filename):
            return JSONResponse(
                status_code=404,
                content={
                    "message": "Analysis results not found or still processing",
                    "business_model_id": business_model_id
                }
            )

        results = minio_service.download_json(results_filename)
        return JSONResponse(content=results)

    except Exception as e:
        logger.error(f"Error retrieving analysis results: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving analysis results: {str(e)}"
        )

@router.get("/list-researches/{business_id}")
async def list_researches(
    business_id: str,
    db: Session = Depends(deps.get_db)
) -> JSONResponse:
    """
    List all research records for a business
    
    Args:
        business_id: ID of the business
        db: Database session
    
    Returns:
        JSONResponse with research records
    """
    try:
        # Buscar investigaciones asociadas a este business_id
        researches = db.query(CompetitorResearch).filter(
            CompetitorResearch.business_id == business_id
        ).all()
        
        research_data = []
        for research in researches:
            research_data.append({
                "id": research.id,
                "status": research.status,
                "created_at": research.created_at.isoformat() if research.created_at else None,
                "completed_at": research.completed_at.isoformat() if research.completed_at else None
            })
        
        return JSONResponse(
            status_code=200,
            content={
                "business_id": business_id,
                "research_count": len(research_data),
                "researches": research_data
            }
        )
    except Exception as e:
        logger.error(f"Error listing researches: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "message": f"Error listing researches: {str(e)}"
            }
        )
    
@router.get("/{business_id}/competitors", response_model=GetCompetitorsResponse)
async def get_competitors(
    business_id: str,
    db: Session = Depends(deps.get_db)
) -> Any:
    """
    Get the competitors for a business.
    
    This endpoint retrieves all competitors associated with a specific business idea
    and returns them in a structured list.
    """
    try:
        competitors = db.query(Competitor).filter(Competitor.business_idea_id == business_id).all()
        
        return {
            "business_id": business_id,
            "competitors": competitors
        }
    except Exception as e:
        logger.error(f"Error getting competitors for business_id {business_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred while fetching competitors."
        )