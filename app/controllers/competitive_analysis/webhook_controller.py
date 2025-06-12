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
from app.services.llm.langchain_factory import LangChainLLMFactory
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
    kestra_base_url = settings.KESTRA_URL.rstrip('/')
    namespace = "noit.backend"
    flow_id = "social-media-extraction-trigger"
    webhook_key = settings.KESTRA_SOCIAL_MEDIA_SCRAPER_KEY
    # Directly using the correct key
    logger.info(f"Using Kestra webhook key for social media scraper: {webhook_key}")
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
                logger.warning(
                    f"Kestra social media extraction webhook returned error for business {business_id}. "
                    f"Status: {response.status_code}, Response: {response.text}"
                )
                if response.status_code == 404:
                    logger.warning("Webhook endpoint not found in Kestra - this might indicate the workflow is not deployed yet")
                raise Exception(f"Webhook returned {response.status_code}: {response.text}")
            
            # Handle successful responses
            elif response.status_code == 204:
                logger.info(
                    f"Kestra social media extraction webhook for business {business_id} triggered successfully (status 204 No Content)."
                )
            else: # Handle other success codes that might have a body
                logger.info(
                    f"Kestra social media extraction webhook for business {business_id} triggered successfully. "
                    f"Execution ID: {response.json().get('executionId')}"
                )
    except httpx.RequestError as e:
        logger.warning(f"Network error while triggering Kestra social media extraction webhook for business {business_id}: {str(e)}")
        raise Exception(f"Network error: {str(e)}")
    except Exception as e:
        logger.warning(f"Error while triggering Kestra social media extraction webhook for business {business_id}: {str(e)}")
        raise

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
        body_json: Dict[str, Any],
        db: Session
    ):
        """
        Procesa datos de competidores recibidos desde un webhook, los guarda en la base de datos
        y dispara el siguiente paso del pipeline (extracción de redes sociales).
        """
        request_id = body_json.get("request_id", "missing")
        business_id = body_json.get("business_id", "missing")
        logger.info(f"Iniciando procesamiento de competidores para request_id: {request_id}, business_id: {business_id}")

        db_session = next(deps.get_db())
        try:
            research = db_session.query(CompetitorResearch).filter(
                (CompetitorResearch.id == request_id) | 
                ((CompetitorResearch.business_id == business_id) & (CompetitorResearch.status == CompetitorResearchStatus.PENDING))
            ).order_by(CompetitorResearch.created_at.desc()).first()

            if not research:
                logger.error(f"No se encontró investigación para request_id '{request_id}' o una pendiente para business_id '{business_id}'")
                return

            logger.info(f"Procesando investigación: {research.id} para negocio: {research.business_id}")
            actual_business_id = research.business_id

            status = body_json.get("status", "completed").lower()
            if status in ["error", "failed"]:
                error_message = body_json.get("error_message", "Error desconocido desde el webhook.")
                logger.error(f"La investigación falló: {error_message}")
                research.status = CompetitorResearchStatus.ERROR
                research.error_message = error_message
                db_session.commit()
                return

            # --- Lógica de extracción y parsing de competidores ---
            competitors_data_source = body_json.get("competitors") or body_json.get("text") or body_json
            competitors_structured = await self._extract_and_parse_competitors(competitors_data_source, research, db_session)
            
            if not competitors_structured:
                logger.error("No se pudieron extraer competidores estructurados. Marcando investigación como fallida.")
                research.status = CompetitorResearchStatus.ERROR
                research.error_message = "No se pudieron extraer datos de competidores estructurados del payload del webhook."
                db_session.commit()
                return

            # --- Guardado en Base de Datos y MinIO ---
            analyzer = self._get_analyzer(research, actual_business_id, db_session)
            analyzer.save_competitors(
                competitors_data={"competitors": competitors_structured},
                business_idea_id=actual_business_id
            )

            research.status = CompetitorResearchStatus.COMPLETED
            research.completed_at = datetime.now()
            
            logger.info(f"Guardando {len(competitors_structured)} competidores en la base de datos.")
            db_session.commit()
            
            await self._save_results_to_minio(actual_business_id, research.id, competitors_structured)

            # --- Disparar siguiente pipeline ---
            if competitors_structured:
                logger.info(f"Triggering social media extraction for business_id: {actual_business_id}")
                try:
                    await trigger_social_media_extraction_webhook(business_id=actual_business_id)
                    logger.info(f"Successfully triggered social media extraction webhook for business: {actual_business_id}")
                except Exception as webhook_error:
                    logger.warning(f"Failed to trigger social media extraction webhook (non-critical): {str(webhook_error)}")
            else:
                logger.info(f"Skipping social media extraction for {actual_business_id}: no competitors found.")

        except Exception as e:
            logger.error(f"Error fatal durante el procesamiento de datos de competidores: {str(e)}", exc_info=True)
            db_session.rollback()
        finally:
            db_session.close()

    def _get_analyzer(self, research: CompetitorResearch, business_id: str, db_session: Session) -> EnhancedBusinessAnalyzer:
        """Crea una instancia del EnhancedBusinessAnalyzer."""
        business_model_db = db_session.query(BusinessModelDB).filter(BusinessModelDB.business_id == business_id).first()
        business_idea = db_session.query(BusinessIdea).filter(BusinessIdea.id == business_id).first()
        
        if not business_model_db or not business_idea:
            raise ValueError(f"No se pudo encontrar el modelo de negocio o la idea de negocio para business_id: {business_id}")

        business_idea_text = f"{business_idea.title}:\n\nDESCRIPCIÓN:\n{business_idea.description}"
        
        business_model = BusinessModel(
            business_idea=business_idea_text,
            customer_persona=business_model_db.customer_persona or '',
            industry=business_model_db.industry or '',
            problem_definition=business_model_db.problem_definition,
            value_proposition=business_model_db.value_proposition,
            competitive_advantage=business_model_db.competitive_advantage,
            products_services=business_model_db.products_services,
            challenges_opportunities=business_model_db.challenges_opportunities
        )

        return EnhancedBusinessAnalyzer(
            business_model=business_model,
            lang=research.language or "es",
            research_model=research.model or "sonar-deep-research",
            db=db_session
        )

    async def _extract_and_parse_competitors(self, data_source: Any, research: CompetitorResearch, db_session: Session) -> list:
        """Extrae y parsea los datos de competidores desde diferentes formatos."""
        if not data_source:
            logger.warning("Fuente de datos de competidores está vacía.")
            return []

        if isinstance(data_source, list):
            logger.info(f"Datos de competidores recibidos como lista pre-estructurada de {len(data_source)} elementos.")
            return data_source
        
        parsed_dict = None
        if isinstance(data_source, str):
            logger.info("Fuente de datos es un string. Intentando parsear.")
            try:
                # Use the improved _extract_json method
                analyzer_instance = EnhancedBusinessAnalyzer(business_model=BusinessModel(business_idea="", customer_persona="", industry=""), db=db_session)
                clean_str = analyzer_instance._extract_json(data_source)
                parsed_dict = json.loads(clean_str)
                logger.info("String parseado como JSON exitosamente.")
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Parsing directo de JSON falló ({e}). Usando LLM como fallback.")
                llm = LangChainLLMFactory.create_llm(
                    provider="openai",
                    model="gpt-4o-mini",
                    temperature=0.3,
                    max_tokens=16384
                )
                prompt = prompts.create_parsing_prompt_competitors(lang=research.language or "es", raw_response=data_source)
                response = llm.invoke(prompt)
                try:
                    logger.debug(f"Raw LLM content for parsing: {response.content}")
                    
                    # Parsear con LLM a JSON estructurado final
                    competitors_parsed, _ = extract_and_parse_json(response.content)

                    # Verificar que la respuesta del LLM sea válida y no None
                    if competitors_parsed is None:
                        logger.error("LLM parsing returned None or failed.")
                        save_problematic_content(response.content, "llm_parsing_failed")
                        return []
                        
                    logger.info(f"Datos parseados de competidores con LLM: {competitors_parsed}")
                    
                    # Verificar que la respuesta del LLM sea válida
                    if not isinstance(competitors_parsed, dict):
                        logger.error("LLM devolvió respuesta inválida (no es un diccionario)")
                        competitors_structured = []
                    else:
                        # Find the list of competitors, regardless of the key name
                        competitors_structured = []
                        for key, value in competitors_parsed.items():
                            if isinstance(value, list) and value:
                                # Assume the first non-empty list is the list of competitors
                                competitors_structured = value
                                logger.info(f"Found competitor list under key '{key}'")
                                break
                        
                        if not competitors_structured:
                            logger.warning("Could not find a list of competitors in the parsed JSON from LLM.")
                        
                        logger.info(f"Extraídos {len(competitors_structured)} competidores de datos raw con LLM")
                        
                        # Validar que la estructura es correcta y retornar
                        if not isinstance(competitors_structured, list):
                            logger.error(f"Estructura incorrecta encontrada en la respuesta del LLM: {type(competitors_structured)}")
                            return []
                        
                        return competitors_structured
                except Exception as llm_e:
                    logger.error(f"LLM parsing también falló: {llm_e}", exc_info=True)
                    save_problematic_content(data_source, "llm_parsing_failed")
                    return []
        
        elif isinstance(data_source, dict):
            parsed_dict = data_source

        if isinstance(parsed_dict, dict):
            # Find a key whose value is a list of dicts
            for key, value in parsed_dict.items():
                if isinstance(value, list) and all(isinstance(i, dict) for i in value):
                    logger.info(f"Lista de competidores encontrada en la clave '{key}' del diccionario.")
                    return value
            logger.warning("El diccionario parseado no contenía una lista de competidores válida.")

        logger.error(f"No se pudo extraer una lista de competidores de la fuente de datos (tipo: {type(data_source)}).")
        return []

    async def _save_results_to_minio(self, business_id: str, request_id: str, competitors_structured: list):
        """Guarda los resultados finales en MinIO."""
        try:
            minio_service = MinioService(bucket_name=settings.MINIO_BUCKET_NAME)
            results_filename = f"{business_id}/competitor-analysis/competitors.json"
            final_results = {
                "request_id": request_id,
                "business_id": business_id,
                "status": "completed",
                "competitors": competitors_structured,
                "timestamp": datetime.now().isoformat()
            }
            await minio_service.upload_content(
                results_filename,
                json.dumps(final_results, indent=2),
                content_type='application/json'
            )
            logger.info(f"Resultados de competidores guardados en MinIO: {results_filename}")
        except Exception as e:
            logger.error(f"Error guardando resultados en MinIO: {e}") 