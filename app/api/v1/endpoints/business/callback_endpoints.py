from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.api import deps
import json
import logging
import datetime
from typing import Dict, Any
import httpx
from app.core.config import settings
from fastapi import BackgroundTasks

from app.models.business.business_idea import BusinessIdea
from app.models.business.competitive_analysis.business_competitor import CompetitorResearch, CompetitorResearchStatus
from app.services.storage.minio_service import MinioService
from app.services.business.competitive_analysis.business_competitors_extraction import EnhancedBusinessAnalyzer, BusinessModel
from app.utils.decode_json import clean_json_encoding
from app.prompts.business import prompts_business_competitors as prompts

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/receive-webhook")
async def receive_webhook(
    request: Request
) -> JSONResponse:
    """
    Simple endpoint to receive any webhook data
    """
    logger.info("WEBHOOK ENDPOINT WAS CALLED")
    
    try:
        # Get request body
        body = await request.body()
        body_str = body.decode('utf-8')
        logger.info(f"Webhook received body: {body_str}")
        
        # Try to parse JSON
        try:
            body_json = json.loads(body_str)
            data = body_json
        except:
            data = {"raw": body_str}
        
        # Return success with content
        return JSONResponse(
            status_code=200,
            content={
                "message": "Webhook received successfully",
                "timestamp": datetime.datetime.now().isoformat(),
                "data": data
            }
        )
    except Exception as e:
        logger.error(f"Error in webhook: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "message": f"Error processing webhook: {str(e)}"
            }
        )

@router.post("/competitor-research")
async def competitor_research_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(deps.get_db)
) -> JSONResponse:
    """
    Webhook endpoint for competitor research results
    """
    logger.info("COMPETITOR RESEARCH WEBHOOK CALLED")
    
    try:
        # Get request body
        body = await request.body()
        body_str = body.decode('utf-8')
        logger.info(f"Webhook received body: {body_str}")
        
        # Parse JSON
        body_json = json.loads(body_str)
        
        # Extract key fields
        request_id = body_json.get("request_id", "missing")
        business_id = body_json.get("business_id", "missing")
        status = body_json.get("status", "missing")
        
        logger.info(f"Received webhook - request_id: {request_id}, business_id: {business_id}, status: {status}")
        
        # Start processing in the background and return immediately
        background_tasks.add_task(
            process_competitor_data,
            body_json=body_json,
            db=db
        )
        
        # Return success immediately
        return JSONResponse(
            status_code=200,
            content={
                "message": "Webhook received successfully, processing in background",
                "request_id": request_id,
                "business_id": business_id,
                "status": "processing"
            }
        )
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return JSONResponse(
            status_code=200,  # Return 200 even on error to prevent n8n retries
            content={
                "message": f"Error receiving webhook: {str(e)}",
                "status": "error_receiving"
            }
        )

async def process_competitor_data(
    body_json: dict,
    db: Session
):
    """
    Process competitor data in the background
    """
    logger.info("Starting background processing of competitor data")
    
    try:
        # Extract key fields
        request_id = body_json.get("request_id", "missing")
        business_id = body_json.get("business_id", "missing")
        status = body_json.get("status", "missing")
        competitors_data = body_json.get("competitors", None)
        
        logger.info(f"Processing data - request_id: {request_id}, business_id: {business_id}, status: {status}")
        
        # Use a new db session since we're in a background task
        db_session = next(deps.get_db())
        
        try:
            # Verify business exists
            business = db_session.query(BusinessIdea).filter(BusinessIdea.id == business_id).first()
            if not business:
                logger.error(f"Business with ID {business_id} not found")
                return
            
            # Verify research exists
            research = db_session.query(CompetitorResearch).filter(
                CompetitorResearch.id == request_id
            ).first()
            
            if not research:
                logger.error(f"Research with ID {request_id} not found")
                # Check for a pending research for this business
                research = db_session.query(CompetitorResearch).filter(
                    CompetitorResearch.business_id == business_id,
                    CompetitorResearch.status == CompetitorResearchStatus.PENDING
                ).first()
                
                if not research:
                    logger.error(f"No pending research found for business_id: {business_id}")
                    return
                logger.info(f"Found research by business_id instead: {research.id}")
            
            # Update research status
            if status == "completed":
                # Aquí agregamos la lógica para procesar los datos de competidores recibidos
                
                # Primero, obtenemos el business model para inicializar el analyzer
                minio_service = MinioService(bucket_name="lattice-businesses")
                business_model_object_path = f"{business_id}/business-understanding/business_model.json"
                
                # Verificamos si el business model existe
                if not minio_service.object_exists(business_model_object_path):
                    logger.error(f"Business model {business_model_object_path} not found")
                    research.status = CompetitorResearchStatus.ERROR
                    research.error_message = f"Business model not found: {business_model_object_path}"
                    db_session.commit()
                    return
                
                try:
                    # Obtener los datos del modelo de negocio
                    business_model_data = clean_json_encoding(minio_service.download_json(business_model_object_path))
                    business_model_data = business_model_data.get('MarketResearchModule', {})
                    
                    # Crear texto descriptivo del business idea
                    business_idea_text = f"""
                    {business.title}:
                    
                    MISIÓN:
                    {business.mission}
                    
                    VISIÓN:
                    {business.vision}
                    
                    DESCRIPCIÓN:
                    {business.description}
                    """
                    
                    # Crear objeto BusinessModel
                    business_model = BusinessModel(
                        business_idea = business_idea_text,
                        customer_persona = business_model_data.get('customer_persona', ''),
                        industry = business_model_data.get('industry', '')
                    )
                    
                    # Crear el analizador
                    analyzer = EnhancedBusinessAnalyzer(
                        business_model=business_model,
                        lang=research.language or "es",
                        validator_provider="deepseek",  # Valores predeterminados
                        validator_model="deepseek-reasoner",
                        max_depth=1,
                        research_model=research.model or "sonar-deep-research",
                        db=db_session
                    )
                    
                    # Verificar que tenemos datos de competidores válidos
                    if not competitors_data:
                        logger.warning("No competitor data received in webhook payload")
                        competitors_structured = []
                    elif isinstance(competitors_data, str):
                        # Si los datos llegan como string, lo tratamos como raw_response
                        logger.info("Processing raw competitor data...")
                        raw_response = competitors_data
                        
                        # Usar el mismo flujo que en research_competitors
                        try:
                            # Parse response with LLM to structured JSON
                            logger.info("Parsing research response with LLM...")
                            prompt_parsing = prompts.create_parsing_prompt_competitors(
                                lang=research.language or "es",
                                raw_response=raw_response
                            )
                            
                            # Parsear con LLM a JSON estructurado final
                            competitors_parsed = await analyzer._parse_response_with_llm(prompt=prompt_parsing)
                            logger.info(f"Parsed competitors data: {competitors_parsed}")
                            
                            competitors_structured = competitors_parsed.get('competitors', [])
                            logger.info(f"Extracted {len(competitors_structured)} competitors from raw data")
                        except Exception as e:
                            logger.error(f"Error parsing competitors: {str(e)}")
                            competitors_structured = []
                    else:
                        # Si ya recibimos datos estructurados
                        competitors_structured = competitors_data
                        logger.info(f"Received {len(competitors_structured)} pre-structured competitors")
                    
                    # Guardar competidores en la base de datos
                    logger.info("Saving competitors to database...")
                    analyzer.save_competitors(
                        competitors_data={"competitors": competitors_structured},
                        business_idea_id=business_id
                    )
                    
                    # Actualizar estado de la investigación
                    research.status = CompetitorResearchStatus.COMPLETED
                    research.completed_at = datetime.datetime.now()
                    db_session.commit()
                    
                    # Guardar resultados estructurados en MinIO
                    results_filename = f"{business_id}/competitor-analysis/competitors_{research.id}.json"
                    final_results = {
                        "request_id": research.id,
                        "business_id": business_id,
                        "status": "completed",
                        "competitors": competitors_structured,
                        "timestamp": datetime.datetime.now().isoformat()
                    }
                    
                    await minio_service.upload_content(
                        results_filename,
                        json.dumps(final_results),
                        content_type='application/json'
                    )
                    logger.info(f"Stored parsed competitors in MinIO: {results_filename}")
                    
                except Exception as e:
                    logger.error(f"Error processing competitors data: {str(e)}")
                    research.status = CompetitorResearchStatus.ERROR
                    research.error_message = f"Error processing competitors: {str(e)}"
                    db_session.commit()
                    
            elif status == "error":
                research.status = CompetitorResearchStatus.ERROR
                research.error_message = body_json.get("error_message", "Unknown error")
                db_session.commit()
                
                # Almacenar el estado de error en MinIO
                try:
                    minio_service = MinioService(bucket_name="lattice-businesses")
                    results_filename = f"{business_id}/competitor-analysis/competitors_{research.id}.json"
                    
                    error_results = {
                        "request_id": research.id,
                        "business_id": business_id,
                        "status": "error",
                        "error_message": research.error_message,
                        "timestamp": datetime.datetime.now().isoformat()
                    }
                    
                    await minio_service.upload_content(
                        results_filename,
                        json.dumps(error_results),
                        content_type='application/json'
                    )
                    logger.info(f"Stored error results in MinIO: {results_filename}")
                except Exception as e:
                    logger.error(f"Error storing error results in MinIO: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Error in background processing: {str(e)}")
        finally:
            db_session.close()
            
    except Exception as e:
        logger.error(f"Fatal error in background processing: {str(e)}")