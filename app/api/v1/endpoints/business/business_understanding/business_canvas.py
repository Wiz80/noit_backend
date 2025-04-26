from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import Dict, List, Optional
import logging
import json
import os
from datetime import datetime
from sqlalchemy.orm import Session

from app.api import deps
from app.services.business.business_understanding.business_canvas_module import BusinessCanvasModule
from app.services.business.business_understanding.base_business_module import BaseValidatorConfig

from app.models.business.business_understanding.business_canvas import BusinessCanvas
from app.models.business.business_idea import BusinessIdea
from datetime import datetime, UTC
import os
import json

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# Note: Business model endpoints have been moved to business_model.py

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
    
