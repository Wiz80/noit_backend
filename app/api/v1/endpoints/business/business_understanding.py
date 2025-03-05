from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import Dict, Optional
from app.api import deps
import logging

from app.services.business.business_understanding.business_model_module import ValidatorConfig, BusinessValidator
from app.services.business.business_understanding.business_canvas_module import BusinessCanvasModule
from app.services.storage.minio_service import MinioService
from app.services.business.business_understanding.state_of_art import MarketStateOfArtService

from app.schemas.business.business_understanding import BusinessValidationResponse

from app.models.business.business_understanding.business_model import BusinessValidation, ValidationStatus
from app.models.business.business_understanding.business_canvas import BusinessCanvas
from app.models.business.business_idea import BusinessIdea
from app.models.business.business_understanding.state_of_art import MarketStateOfArt, StatusEnum    
from datetime import datetime, UTC
import os
import json

# Configurar logger
logger = logging.getLogger(__name__)

router = APIRouter()
minio_service = MinioService(bucket_name="lattice-businesses")

@router.post("/business-model/{business_id}")
async def business_model(
    business_id: str,
    update: Optional[bool] = Query(False, description="If True, a new validation will be executed"),
    db: Session = Depends(deps.get_db)
):
    """
    Validate a business idea
    if there is a previous successful validation and update=False, return that validation
    if update=True or there is no previous successful validation, execute a new validation
    """
    try:
        # Verify business idea exists
        business_idea = db.query(BusinessIdea).filter(BusinessIdea.id == business_id).first()
        if not business_idea:
            raise HTTPException(status_code=404, detail="Business idea not found")

        # Search for the most recent successful validation
        existing_validation = (
            db.query(BusinessValidation)
            .filter(
                BusinessValidation.business_id == business_id,
                BusinessValidation.status == ValidationStatus.COMPLETED
            )
            .order_by(BusinessValidation.created_at.desc())
            .first()
        )

        # If there is a successful validation and we don't want to update, return it
        if existing_validation and not update:
            return BusinessValidationResponse(
                success=True,
                business_id=business_id,
                report_url=existing_validation.report_url,
                data_url=existing_validation.data_url,
                results=json.loads(minio_service.get_object_data(existing_validation.data_url))
            )

        # Create a new validation record
        validation = BusinessValidation(
            business_id=business_id,
            status=ValidationStatus.PENDING
        )
        db.add(validation)
        db.commit()

        try:
            # Construct the business idea text
            business_idea_text = f"""
            {business_idea.title}:
            
            MISIÓN:
            {business_idea.mission}
            
            VISIÓN:
            {business_idea.vision}
            
            DESCRIPCIÓN:
            {business_idea.description}
            """

            # Configure the validator
            config = ValidatorConfig(
                business_idea=business_idea_text,
                perplexity_api_key=os.getenv("PERPLEXITY_API_KEY"),
                validator_api_keys={"openai": os.getenv("OPENAI_API_KEY")},
                validator_provider="openai",
                validator_model="openai:gpt-4o",
                language="es"
            )
            
            validator = BusinessValidator(config)
            # Execute the validation
            results = await validator.run()
            
            # Define paths for the validation report and structured data in MinIO
            business_folder = f"{business_id}/business-understanding"

            json_path = f"{business_folder}/business_model.json"
            
            # If we are updating, add a version suffix to the file names
            if update:
                minio_service.delete_object(f"{business_folder}/business_model.json")
            

            await minio_service.upload_content(
                object_name=json_path,
                data=json.dumps(results.json_output["es"], indent=2),
                content_type="application/json",
                metadata={
                    "business_id": business_id,
                    "validation_id": validation.id
                }
            )

            # Update the validation record
            validation.status = ValidationStatus.COMPLETED
            validation.data_url = json_path
            db.commit()

            return BusinessValidationResponse(
                success=True,
                business_id=business_id,
                data_url=json_path,
                results=results.json_output["es"]
            )

        except Exception as e:
            # In case of error, update the validation record
            validation.status = ValidationStatus.ERROR
            validation.error_message = str(e)
            db.commit()
            raise

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
from app.services.business.business_understanding.business_canvas_module import BusinessCanvasModule
from app.services.business.business_understanding.base_business_module import BaseValidatorConfig

@router.post("/create-business-canvas/{business_id}")
async def create_business_canvas(
    business_id: str,
    update: Optional[bool] = Query(False, description="If True, forces a new analysis"),
    db: Session = Depends(deps.get_db)
):
    """
    Analyze and document the business model for a given business idea.
    Generates value proposition, business canvas, and monetization strategy.
    """
    try:
        # Verify business idea exists
        business_idea = db.query(BusinessIdea).filter(BusinessIdea.id == business_id).first()
        if not business_idea:
            raise HTTPException(status_code=404, detail="Business idea not found")
        
        # Check if business canvas already exists
        existing_canvas = db.execute(
            select(BusinessCanvas).filter(BusinessCanvas.business_idea_id == business_id)
        )
        existing_canvas = existing_canvas.scalar_one_or_none()

        # If canvas exists and update is False, return existing canvas
        if existing_canvas and not update:
            return {
                "message": "Business canvas already exists",
                "canvas": existing_canvas
            }

        # Format business idea text
        business_idea_text = f"""
            {business_idea.title}:
            
            MISIÓN:
            {business_idea.mission}
            
            VISIÓN:
            {business_idea.vision}
            
            DESCRIPCIÓN:
            {business_idea.description}
            """
        
        # Configure and run the business model analysis
        config = BaseValidatorConfig(
            business_idea=business_idea_text,
            perplexity_api_key=os.getenv("PERPLEXITY_API_KEY"),
            validator_api_keys={"openai": os.getenv("OPENAI_API_KEY")},
            validator_provider="openai",
            validator_model="openai:gpt-4o",
            language="es"
        )
        
        analyzer = BusinessCanvasModule(config, 
                                        db=db, 
                                        business_id=business_id,
                                        update_mode=update,
                                        existing_canvas=existing_canvas if update else None) 
        results = await analyzer.run()
        
        return {
            "success": True,
            "business_id": business_id,
            "documents": {
                "business_canvas": f"business-ideas/{business_id}/business-understanding/business_canvas.json"
            },
            "results": results
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@router.post("/business/{business_idea_id}/state-of-art", response_model=Dict)
async def create_state_of_art(
    business_idea_id: str,
    language: str = "es",
    test_mode: bool = Query(False, description="If True, only a limited number of questions will be processed for testing"),
    test_questions_limit: int = Query(4, description="Number of questions to process per category in test mode"),
    force_update: bool = Query(False, description="If True, forces a new analysis even if one already exists"),
    db: Session = Depends(deps.get_db),
    minio_client: MinioService = Depends(deps.get_minio_client)
):
    """
    Generate state of art analysis for a business idea.
    Creates a market research structure, generates questions, and saves results in MinIO.
    
    When test_mode is True, only a limited number of questions will be processed to speed up testing.
    """
    logger.info(f"Starting state-of-art analysis for business idea: {business_idea_id}")
    logger.info(f"Test mode: {test_mode}, Test questions limit: {test_questions_limit}, Force update: {force_update}")
    
    try:
        # If force_update is True, reset the state in the database
        if force_update:
            logger.info("Force update requested, resetting state in the database")
            business_understanding = db.query(MarketStateOfArt).filter(
                MarketStateOfArt.business_idea_id == business_idea_id
            ).first()
            
            if business_understanding:
                logger.info("Found existing state of art record, resetting status")
                business_understanding.market_research_status = StatusEnum.PENDING
                business_understanding.state_of_art_status = StatusEnum.PENDING
                business_understanding.error_message = None
                db.commit()
                logger.info("Reset status in database")
            else:
                logger.info("No existing state of art record found, will create a new one")
        
        # Initialize the service with the database session and MinIO client
        logger.info("Initializing MarketStateOfArtService")
        service = MarketStateOfArtService(
            db_session=db, 
            minio_client=minio_client,
            language=language,
            test_mode=test_mode,
            test_questions_limit=test_questions_limit
        )
        
        # Process the business understanding asynchronously
        logger.info("Starting process_business_understanding")
        result = await service.process_business_understanding(
            business_idea_id=business_idea_id,
            force_update=force_update
        )
        logger.info("Completed process_business_understanding")
        
        # Return the result with additional information
        output = {
            "business_idea_id": business_idea_id,
            "status": "success",
        }
        
        if "market_research" in result and "path" in result["market_research"]:
            output["market_research_path"] = result["market_research"]["path"]
        
        if "state_of_art" in result and "path" in result["state_of_art"]:
            output["state_of_art_path"] = result["state_of_art"]["path"]
            
        return output
    
    except Exception as e:
        logger.error(f"Error in state-of-art analysis: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"Error in state-of-art analysis: {str(e)}"
        )