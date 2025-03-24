from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Request, Form
from app.api import deps
from typing import List, Optional, Dict, Any
import json
import logging
from fastapi.responses import JSONResponse
import uuid
import datetime
import httpx

from app.services.storage.minio_service import MinioService
from app.services.business.competitive_analysis.business_competitors_extraction import EnhancedBusinessAnalyzer, CompetitorInfo, BusinessModel
from app.core.config import settings

from app.models.business.business_idea import BusinessIdea
from app.models.business.competitive_analysis.business_competitor import CompetitorResearch, CompetitorResearchStatus

from app.schemas.business.business_competitors import CompetitorAnalysisRequest, CompetitorAnalysisCallback
from sqlalchemy.orm import Session

from app.utils.decode_json import clean_json_encoding

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()


async def run_competitor_analysis(
    minio_service: MinioService,
    business_model_data: dict,
    business_model_id: str,
    request: CompetitorAnalysisRequest
) -> dict:
    """Execute competitor analysis using the business model data"""
    try:
        # Create business analyzer instance
        analyzer = EnhancedBusinessAnalyzer(
            business_model=BusinessModel(**business_model_data),
            lang=request.language,
            validator_provider=request.validator_provider,
            validator_model=request.validator_model
        )

        # Generate competitor analysis questions
        questions = analyzer.generate_competitor_questions()

        # Research competitors
        competitors = await analyzer.research_competitors(
            prompt_search=request.search_prompt
        )

        # Store results in MinIO
        results = {
            "competitors": competitors,
            "analysis_questions": questions,
            "business_model_summary": business_model_data
        }

        # Save results to MinIO
        results_filename = f"analysis_results_{business_model_id}.json"
        await minio_service.upload_json(results_filename, results)

        return results

    except Exception as e:
        logger.error(f"Error in competitor analysis: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error executing competitor analysis: {str(e)}"
        )

@router.post("/{business_id}")
async def analyze_competitors(
    business_id: str,
    request: CompetitorAnalysisRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(deps.get_db)
) -> JSONResponse:
    """
    Endpoint to analyze competitors based on a business model
    
    Args:
        business_model_id: ID of the business model in MinIO
        request: CompetitorAnalysisRequest containing analysis parameters
        background_tasks: FastAPI background tasks handler
    
    Returns:
        JSONResponse with analysis results or error details
    """
    try:
        # Verify business idea exists
        business_idea = db.query(BusinessIdea).filter(BusinessIdea.id == business_id).first()
        if not business_idea:
            raise HTTPException(status_code=404, detail="Business idea not found")

        # Initialize MinIO service
        minio_service = MinioService(bucket_name="lattice-businesses")

        business_model_object_path = f"{business_id}/business-understanding/business_model.json"

        # Check if business model exists
        if not minio_service.object_exists(business_model_object_path):
            raise HTTPException(
                status_code=404,
                detail=f"Business model {business_model_object_path} not found"
            )

        # Get business model data
        business_model_data = clean_json_encoding(minio_service.download_json(business_model_object_path))
        business_model_data = business_model_data['MarketResearchModule']

        business_idea_text = f"""
        {business_idea.title}:
        
        MISIÓN:
        {business_idea.mission}
        
        VISIÓN:
        {business_idea.vision}
        
        DESCRIPCIÓN:
        {business_idea.description}
        """
    
        # Validate business model structure
        try:
            business_model = BusinessModel(
                business_idea = business_idea_text,
                customer_persona= business_model_data['customer_persona'],
                industry = business_model_data['industry']
            )
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid business model structure: {str(e)}"
            )

        # CAMBIO IMPORTANTE: Verificar si ya existe una investigación pendiente para este business_id
        existing_research = db.query(CompetitorResearch).filter(
            CompetitorResearch.business_id == business_id,
            CompetitorResearch.status == CompetitorResearchStatus.PENDING
        ).first()
        
        if existing_research:
            # Si ya existe una investigación pendiente, usamos su ID en lugar de crear una nueva
            logger.info(f"Found existing pending research for business {business_id}, reusing it: {existing_research.id}")
            request_id = existing_research.id
        else:
            # Si no existe, creamos una nueva investigación
            request_id = str(uuid.uuid4())
            
            # Create a research record in the database
            research_record = CompetitorResearch(
                id=request_id,
                business_id=business_id,
                status=CompetitorResearchStatus.PENDING,
                language=request.language,
                model=request.research_model
            )
            db.add(research_record)
            db.commit()
            logger.info(f"Created new research record with ID {request_id} for business {business_id}")
        
        # CHANGE: Use the new webhook URL instead of the callback
        # This is the URL n8n will call when the research is complete
        callback_url = f"{request.base_url}/api/v1/webhooks/competitor-research"
        
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
                
        # Execute analysis in background
        analyzer = EnhancedBusinessAnalyzer(
            business_model=business_model,
            lang=request.language,
            validator_provider=request.validator_provider,
            validator_model=request.validator_model,
            max_depth=1,
            research_model=request.research_model,
            db=db
        )

        # If we don't have questions, generate them and save to MinIO
        if not questions:
            logger.info(f"Generating new competitor questions for business {business_id}")
            # Generate competitor analysis questions
            questions = analyzer.generate_competitor_questions()
            
            # Save questions to MinIO for future use
            questions_data = {
                "business_id": business_id,
                "language": request.language,
                "questions": questions,
                "generated_at": datetime.datetime.now().isoformat(),
                "industry": business_model_data['industry']
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
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        results_filename = f"{business_id}/competitor-analysis/competitors_{request_id}.json"
        await minio_service.upload_content(
            results_filename, 
            json.dumps(initial_data), 
            content_type='application/json'
        )
        
        # Import the create_research_query function
        from app.prompts.business.prompts_business_competitors import create_research_query
        
        # Combine the search prompt with the formatted research query
        combined_prompt = create_research_query(
            lang=request.language,
            business_details=business_idea_text,
            prompt_search=request.search_prompt
        )
        
        # Create the modified prompt with the combined search query
        modified_prompt = {
            "search_query": combined_prompt,
            "callback_url": callback_url,
            "request_id": request_id,
            "business_id": business_id,
            "base_url": request.base_url
        }
        
        # Add the research task to background_tasks to run after responding to the client
        # This way we don't block the response while the research is being started
        background_tasks.add_task(
            analyzer.research_competitors_async,
            prompt_search=json.dumps(modified_prompt),
            business_id=business_id,
            request_id=request_id
        )
        
        logger.info(f"Competitor analysis started as background task, request_id: {request_id}")

        return JSONResponse(
            status_code=202,
            content={
                "message": "Competitor analysis started",
                "business_id": business_id,
                "request_id": request_id,
                "status": "pending",
                "questions": questions
            }
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
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
        minio_service = MinioService(bucket_name="lattice-businesses")
        results_filename = f"{research.business_id}/competitor-analysis/competitors_{request_id}.json"
        
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
async def get_analysis_results(business_model_id: str):
    """
    Get the results of a previously executed competitor analysis
    
    Args:
        business_model_id: ID of the business model used for analysis
        
    Returns:
        Analysis results if available
    """
    try:
        minio_service = MinioService(bucket_name="business-models")
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