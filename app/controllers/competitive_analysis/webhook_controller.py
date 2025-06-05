from sqlalchemy.orm import Session
import logging
import json
from datetime import datetime
from typing import Dict, Any
from dotenv import load_dotenv

from app.api import deps
from app.models.business.competitive_analysis.business_competitor import CompetitorResearch, CompetitorResearchStatus
from app.models.business.business_idea import BusinessIdea
from app.models.business.business_understanding.business_model import BusinessModel as BusinessModelDB
from app.services.business.competitive_analysis.business_competitors_extraction import EnhancedBusinessAnalyzer, BusinessModel
from app.services.storage.minio_service import MinioService
import app.prompts.business.prompts_business_competitors as prompts
from app.utils.decode_json import clean_json_encoding

# Import settings
from app.core.config import settings

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
                            validator_provider="anthropic",  # Valores predeterminados
                            validator_model="claude-3-5-sonnet-20241022",
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
                            
                            # Usar el mismo flujo que en research_competitors
                            try:
                                # Parse response with LLM to structured JSON
                                logger.info("Parseando respuesta de investigación con LLM...")
                                prompt_parsing = prompts.create_parsing_prompt_competitors(
                                    lang=research.language or "es",
                                    raw_response=raw_response
                                )
                                
                                # Parsear con LLM a JSON estructurado final
                                competitors_parsed = await analyzer._parse_response_with_llm(prompt=prompt_parsing)
                                logger.info(f"Datos parseados de competidores: {competitors_parsed}")
                                
                                competitors_structured = competitors_parsed.get('competitors', [])
                                logger.info(f"Extraídos {len(competitors_structured)} competidores de datos raw")
                            except Exception as e:
                                logger.error(f"Error parseando competidores: {str(e)}")
                                competitors_structured = []
                        else:
                            # Si ya recibimos datos estructurados
                            competitors_structured = competitors_data
                            logger.info(f"Recibidos {len(competitors_structured)} competidores pre-estructurados")
                        
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