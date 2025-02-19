from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import Dict, Optional
from app.api import deps
from app.services.business.business_understanding.business_validator_module import ValidatorConfig, BusinessValidator
from app.services.business.business_understanding.business_canvas_module import BusinessCanvasModule
from app.services.storage.minio_service import MinioService
from app.schemas.business.business_understanding import BusinessValidationResponse
from app.models.business.business_understanding.business_validation import BusinessValidation, ValidationStatus
from app.models.business.business_understanding.business_canvas import BusinessCanvas
from app.models.business.business_idea import BusinessIdea
from datetime import datetime, UTC
import os
import json

router = APIRouter()
minio_service = MinioService(bucket_name="lattice-businesses")

@router.post("/validate-business/{business_id}")
async def validate_business_idea(
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
                results=json.loads(await minio_service.get_file(existing_validation.data_url))
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
            business_folder = f"{business_id}/business-understanding/validate-business/"
            version_suffix = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            
            # If we are updating, add a version suffix to the file names
            if update:
                markdown_path = f"{business_folder}validation_report_v{version_suffix}.md"
                json_path = f"{business_folder}structured_data_v{version_suffix}.json"
            else:
                markdown_path = f"{business_folder}validation_report.md"
                json_path = f"{business_folder}structured_data.json"

            # Store the validation report and structured data in MinIO
            await minio_service.upload_content(
                object_name=markdown_path,
                data=results.full_doc["es"],
                content_type="text/markdown",
                metadata={
                    "business_id": business_id,
                    "validation_id": validation.id
                }
            )

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
            validation.report_url = markdown_path
            validation.data_url = json_path
            db.commit()

            return BusinessValidationResponse(
                success=True,
                business_id=business_id,
                report_url=markdown_path,
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
        existing_canvas = await db.execute(
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