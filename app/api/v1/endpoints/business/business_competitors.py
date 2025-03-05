from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from app.api import deps
from typing import List, Optional
import json
import logging
from fastapi.responses import JSONResponse

from app.services.storage.minio_service import MinioService
from app.services.business.competitive_analysis.business_competitors_extraction import EnhancedBusinessAnalyzer, CompetitorInfo, BusinessModel

from app.models.business.business_idea import BusinessIdea

from app.schemas.business.business_competitors import CompetitorAnalysisRequest
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

        # Execute analysis in background
        analyzer = EnhancedBusinessAnalyzer(
            business_model=business_model,
            lang=request.language,
            validator_provider=request.validator_provider,
            validator_model=request.validator_model,
            max_depth=1,
            db=db
        )

        # Generate competitor analysis questions
        questions = analyzer.generate_competitor_questions()

        # Research competitors
        competitors = await analyzer.research_competitors(
            prompt_search=request.search_prompt,
            business_id=business_id
        )

        results = {
            "competitors": competitors,
            "analysis_questions": questions
        }

        # Save results to MinIO (optional, can remove if not needed)
        results_filename = f"{business_id}/competitor-analysis/competitors.json"
        await minio_service.upload_content(
            results_filename, 
            json.dumps(results), 
            content_type='application/json'
        )


        return JSONResponse(
            status_code=202,
            content={
                "message": "Competitor analysis finished",
                "business_model_id": business_id,
                "status": "completed",
                "results": results
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