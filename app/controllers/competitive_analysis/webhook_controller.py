from sqlalchemy.orm import Session
import logging
import json
from datetime import datetime
from typing import Dict, Any
from dotenv import load_dotenv
import httpx
import os

from app.api import deps
from app.models.business.competitive_analysis.business_competitor import CompetitorResearch, CompetitorResearchStatus
from app.models.business.business_idea import BusinessIdea
from app.models.business.business_understanding.business_model import BusinessModel as BusinessModelDB
from app.services.business.competitive_analysis.business_competitors_extraction import EnhancedBusinessAnalyzer, BusinessModel
from app.services.storage.minio_service import MinioService
import app.prompts.business.prompts_business_competitors as prompts
from app.utils.decode_json import clean_json_encoding, extract_and_parse_json, save_problematic_content

# Import settings
from app.core.config import settings

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuración temporal para debugging detallado
logging.getLogger('app.utils.decode_json').setLevel(logging.DEBUG)

def get_social_media_extraction_webhook_url():
    """Constructs the Kestra webhook URL for social media extraction."""
    kestra_base_url = os.getenv("KESTRA_BASE_URL", "http://kestra:8080")
    namespace = "noit.backend"
    flow_id = "social-media-extraction-trigger"
    webhook_key = os.getenv("KESTRA_SOCIAL_MEDIA_KEY", "ks_wht_zXcVbNmLk8jH5fD2")
    return f"{kestra_base_url}/api/v1/executions/webhook/{namespace}/{flow_id}/{webhook_key}"

async def trigger_social_media_extraction_webhook(business_id: str):
    """Triggers a Kestra webhook to start social media extraction for all competitors."""
    webhook_url = get_social_media_extraction_webhook_url()
    payload = {
        "business_id": business_id,
        "update_db": True
    }
    
    try:
        async with httpx.AsyncClient() as client:
            logger.info(f"Triggering Kestra webhook for social media extraction: {webhook_url}")
            response = await client.post(webhook_url, json=payload, timeout=30.0)
            
            if response.status_code >= 400:
                logger.error(
                    f"Error triggering Kestra social media extraction webhook for business {business_id}. "
                    f"Status: {response.status_code}, Response: {response.text}"
                )
            else:
                logger.info(
                    f"Kestra social media extraction webhook for business {business_id} triggered successfully. "
                    f"Execution ID: {response.json().get('executionId')}"
                )
    except httpx.RequestError as e:
        logger.error(f"RequestError while triggering Kestra social media extraction webhook for business {business_id}: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error while triggering Kestra social media extraction webhook for business {business_id}: {str(e)}")

class WebhookController:
    """
    Controller para el procesamiento de webhooks.
    Maneja la recepción y procesamiento de datos de webhooks.
    """
    
    def __init__(self):
        """
        Inicializa el controlador de webhooks.
        """
        pass
    
    async def process_competitor_data(
        self,
        body_json: dict,
        db: Session
    ):
        """
        Procesa datos de competidores recibidos desde un webhook
        
        Args:
            body_json (dict): Datos JSON de la solicitud webhook
            db (Session): Sesión de base de datos
        """
        logger.info("Iniciando procesamiento de datos de competidores")
        
        try:
            # Extraer campos clave
            request_id = body_json.get("request_id", "missing")
            business_id = body_json.get("business_id", "missing")
            status = body_json.get("status", "missing")
            competitors_data = body_json.get("competitors", None)
            
            logger.info(f"Procesando datos - request_id: {request_id}, business_id: {business_id}, status: {status}")
            
            # Usar una nueva sesión de base de datos ya que estamos en una tarea en segundo plano
            db_session = next(deps.get_db())
            
            try:
                # Verificar que existe el negocio
                business = db_session.query(BusinessIdea).filter(BusinessIdea.id == business_id).first()
                if not business:
                    logger.error(f"Negocio con ID {business_id} no encontrado")
                    return
                
                # Verificar que existe la investigación
                research = db_session.query(CompetitorResearch).filter(
                    CompetitorResearch.id == request_id
                ).first()
                
                if not research:
                    logger.error(f"Investigación con ID {request_id} no encontrada")
                    # Buscar una investigación pendiente para este negocio
                    research = db_session.query(CompetitorResearch).filter(
                        CompetitorResearch.business_id == business_id,
                        CompetitorResearch.status == CompetitorResearchStatus.PENDING
                    ).first()
                    
                    if not research:
                        logger.error(f"No se encontró investigación pendiente para business_id: {business_id}")
                        return
                    logger.info(f"Investigación encontrada por business_id: {research.id}")
                
                # Actualizar estado de la investigación
                if status == "completed":
                    # Aquí agregamos la lógica para procesar los datos de competidores recibidos
                    
                    # Obtener el business model desde la base de datos
                    business_model_db = db_session.query(BusinessModelDB).filter(
                        BusinessModelDB.business_id == business_id
                    ).first()
                    
                    if not business_model_db:
                        logger.error(f"Business model no encontrado para business_id: {business_id}")
                        research.status = CompetitorResearchStatus.ERROR
                        research.error_message = f"Business model not found for business_id: {business_id}"
                        db_session.commit()
                        return
                    
                    try:
                        # Crear texto descriptivo del business idea
                        business_idea_text = f"""
                        {business.title}:
                        
                        DESCRIPCIÓN:
                        {business.description}
                        """
                        
                        # Crear objeto BusinessModel para el analyzer usando todos los campos de la base de datos
                        business_model = BusinessModel(
                            business_idea=business_idea_text,
                            customer_persona=business_model_db.customer_persona or '',
                            industry=business_model_db.industry or '',
                            problem_definition=business_model_db.problem_definition or None,
                            value_proposition=business_model_db.value_proposition or None,
                            competitive_advantage=business_model_db.competitive_advantage or None,
                            products_services=business_model_db.products_services or None,
                            challenges_opportunities=business_model_db.challenges_opportunities or None
                        )
                        
                        # Crear el analizador
                        analyzer = EnhancedBusinessAnalyzer(
                            business_model=business_model,
                            lang=research.language or "es",
                            validator_provider="openai",  # Valores predeterminados
                            validator_model="gpt-4o-mini",
                            max_depth=1,
                            research_model=research.model or "sonar-deep-research",
                            db=db_session
                        )
                        
                        # Verificar que tenemos datos de competidores válidos
                        if not competitors_data:
                            logger.warning("No se recibieron datos de competidores en el payload del webhook")
                            competitors_structured = []
                        elif isinstance(competitors_data, str):
                            # Si los datos llegan como string, lo tratamos como raw_response
                            logger.info("Procesando datos raw de competidores...")
                            raw_response = competitors_data
                            
                            # Fallback al parsing con LLM si la extracción automática falló
                            #logger.info("Extracción automática falló, usando parsing con LLM...")
                            try:
                                # Parse response with LLM to structured JSON
                                logger.info("Parseando respuesta de investigación con LLM...")
                                prompt_parsing = prompts.create_parsing_prompt_competitors(
                                    lang=research.language or "es",
                                    raw_response=raw_response
                                )
                                
                                # Parsear con LLM a JSON estructurado final
                                competitors_parsed = await analyzer._parse_response_with_llm(prompt=prompt_parsing)
                                logger.info(f"Datos parseados de competidores con LLM: {competitors_parsed}")
                                
                                # Verificar que la respuesta del LLM sea válida
                                if not competitors_parsed or not isinstance(competitors_parsed, dict):
                                    logger.error("LLM devolvió respuesta vacía o inválida")
                                    competitors_structured = []
                                else:
                                    competitors_structured = competitors_parsed.get('competitors', [])
                                    logger.info(f"Extraídos {len(competitors_structured)} competidores de datos raw con LLM")
                                    
                                    # Validar que la estructura es correcta
                                    if not isinstance(competitors_structured, list):
                                        logger.error("LLM devolvió estructura no válida para 'competitors'")
                                        competitors_structured = []
                                    elif len(competitors_structured) == 0:
                                        logger.warning("LLM devolvió lista vacía de competidores")
                                        
                                        # FALLBACK FINAL: Intentar una vez más el parsing automático con limpieza agresiva
                                        logger.info("Intentando fallback final con limpieza agresiva...")
                                        try:
                                            # Usar solo la parte central del texto que parece ser JSON
                                            json_start = raw_response.find('{')
                                            json_end = raw_response.rfind('}') + 1
                                            if json_start >= 0 and json_end > json_start:
                                                json_only = raw_response[json_start:json_end]
                                                parsed_fallback, _ = extract_and_parse_json(json_only)
                                                if parsed_fallback:
                                                    fallback_competitors = parsed_fallback.get('competitors', [])
                                                    if len(fallback_competitors) > 0:
                                                        logger.info(f"Fallback exitoso: {len(fallback_competitors)} competidores")
                                                        competitors_structured = fallback_competitors
                                        except Exception as fallback_e:
                                            logger.error(f"Fallback final también falló: {fallback_e}")
                                    
                            except Exception as e:
                                logger.error(f"Error parseando competidores con LLM: {str(e)}")
                                logger.error(f"Raw response que causó el error (primeros 1000 chars): {raw_response[:1000]}")
                                
                                # Guardar contenido problemático para análisis
                                save_problematic_content(raw_response, "llm_parsing_failed")
                                
                                # FALLBACK DE EMERGENCIA: Intentar parsing automático directo
                                logger.info("Intentando fallback de emergencia con parsing directo...")
                                try:
                                    # Buscar solo la parte que parece JSON válido
                                    json_start = raw_response.find('{')
                                    json_end = raw_response.rfind('}') + 1
                                    if json_start >= 0 and json_end > json_start:
                                        json_part = raw_response[json_start:json_end]
                                        emergency_parsed, emergency_needs_llm = extract_and_parse_json(json_part)
                                        if not emergency_needs_llm and emergency_parsed:
                                            emergency_competitors = emergency_parsed.get('competitors', [])
                                            if len(emergency_competitors) > 0:
                                                logger.info(f"Fallback de emergencia exitoso: {len(emergency_competitors)} competidores")
                                                competitors_structured = emergency_competitors
                                            else:
                                                competitors_structured = []
                                        else:
                                            competitors_structured = []
                                    else:
                                        competitors_structured = []
                                except Exception as emergency_e:
                                    logger.error(f"Fallback de emergencia también falló: {emergency_e}")
                                    competitors_structured = []
                        else:
                            # Si ya recibimos datos estructurados (list o dict)
                            if isinstance(competitors_data, list):
                                competitors_structured = competitors_data
                                logger.info(f"Recibidos {len(competitors_structured)} competidores como lista pre-estructurada")
                            elif isinstance(competitors_data, dict):
                                # Si es un diccionario, extraer la lista de competidores
                                competitors_structured = competitors_data.get('competitors', [])
                                logger.info(f"Extraídos {len(competitors_structured)} competidores de diccionario pre-estructurado")
                            else:
                                logger.error(f"Tipo de datos de competidores no soportado: {type(competitors_data)}")
                                competitors_structured = []
                        
                        # Guardar competidores en la base de datos
                        logger.info("Guardando competidores en la base de datos...")
                        analyzer.save_competitors(
                            competitors_data={"competitors": competitors_structured},
                            business_idea_id=business_id
                        )
                        
                        # Actualizar estado de la investigación
                        research.status = CompetitorResearchStatus.COMPLETED
                        research.completed_at = datetime.now()
                        db_session.commit()
                        
                        # Guardar resultados estructurados en MinIO
                        minio_service = MinioService(bucket_name=settings.MINIO_BUCKET_NAME)
                        results_filename = f"{business_id}/competitor-analysis/competitors.json"
                        final_results = {
                            "request_id": research.id,
                            "business_id": business_id,
                            "status": "completed",
                            "competitors": competitors_structured,
                            "timestamp": datetime.now().isoformat()
                        }
                        
                        await minio_service.upload_content(
                            results_filename,
                            json.dumps(final_results),
                            content_type='application/json'
                        )
                        logger.info(f"Competidores parseados almacenados en MinIO: {results_filename}")
                        
                        # Trigger the next step in the workflow: Social Media Extraction
                        if competitors_structured:
                             logger.info(f"Triggering social media extraction for business_id: {business_id}")
                             await trigger_social_media_extraction_webhook(business_id=business_id)
                        else:
                             logger.info(f"Skipping social media extraction for {business_id}: no competitors found.")
                        
                    except Exception as e:
                        logger.error(f"Error procesando datos de competidores: {str(e)}")
                        research.status = CompetitorResearchStatus.ERROR
                        research.error_message = f"Error procesando competidores: {str(e)}"
                        db_session.commit()
                
                elif status == "error":
                    research.status = CompetitorResearchStatus.ERROR
                    research.error_message = body_json.get("error_message", "Error desconocido")
                    db_session.commit()
                    
                    # Almacenar el estado de error en MinIO
                    try:
                        minio_service = MinioService(bucket_name=settings.MINIO_BUCKET_NAME)
                        results_filename = f"{business_id}/competitor-analysis/competitors.json"
                        
                        error_results = {
                            "request_id": research.id,
                            "business_id": business_id,
                            "status": "error",
                            "error_message": research.error_message,
                            "timestamp": datetime.now().isoformat()
                        }
                        
                        await minio_service.upload_content(
                            results_filename,
                            json.dumps(error_results),
                            content_type='application/json'
                        )
                        logger.info(f"Resultados de error almacenados en MinIO: {results_filename}")
                    except Exception as e:
                        logger.error(f"Error almacenando resultados de error en MinIO: {str(e)}")
            
            except Exception as e:
                logger.error(f"Error en procesamiento de datos de competidores: {str(e)}")
            finally:
                db_session.close()
                
        except Exception as e:
            logger.error(f"Error fatal en procesamiento de datos de competidores: {str(e)}") 