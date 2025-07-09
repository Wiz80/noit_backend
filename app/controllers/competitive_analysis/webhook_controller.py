from sqlalchemy.orm import Session
import logging
import json
import re
from datetime import datetime
from typing import Dict, Any, List
from dotenv import load_dotenv
import httpx
import os
import time
import asyncio

from app.api import deps
from app.models.business.competitive_analysis.business_competitor import CompetitorResearch, CompetitorResearchStatus
from app.models.business.business_idea import BusinessIdea
from app.models.business.business_understanding.business_model import BusinessModel as BusinessModelDB
from app.services.business.competitive_analysis.business_competitors_extraction import EnhancedBusinessAnalyzer, BusinessModel
from app.services.storage.minio_service import MinioService
from app.services.llm.langchain_factory import LangChainLLMFactory
import app.prompts.business.prompts_business_competitors as prompts
from app.utils.decode_json import clean_json_encoding, extract_and_parse_json, save_problematic_content
from minio.error import S3Error

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
            # Check if this is a callback from web research system
            if "callback_source" in body_json and body_json["callback_source"] == "web_research_system":
                logger.info("Processing callback from web research system")
                if "tasks" in body_json:
                    logger.info(f"Found {len(body_json['tasks'])} tasks in web research callback")
                    competitors_structured = await self._extract_competitors_from_tasks(body_json["tasks"], research, db_session)
                else:
                    competitors_data_source = body_json.get("competitors") or body_json.get("text") or body_json
                    competitors_structured = await self._extract_and_parse_competitors(competitors_data_source, research, db_session)
            else:
                # Standard flow
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
            
            # Check if this is a list of tasks instead of competitors
            if data_source and isinstance(data_source[0], dict) and 'minio_file_path' in data_source[0]:
                logger.info("Detected tasks with MinIO file paths instead of direct competitor data")
                return await self._extract_competitors_from_tasks(data_source, research, db_session)
            
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
            # Debug logging
            logger.info(f"Processing dict with keys: {list(parsed_dict.keys())}")
            if 'tasks' in parsed_dict:
                logger.info(f"Found 'tasks' key with {len(parsed_dict['tasks'])} items")
                if parsed_dict['tasks']:
                    logger.info(f"First task item: {parsed_dict['tasks'][0]}")
            # Check if this is a callback from web research system with tasks
            if 'tasks' in parsed_dict and isinstance(parsed_dict['tasks'], list):
                tasks = parsed_dict['tasks']
                logger.info(f"Checking tasks list with {len(tasks)} items")
                if tasks and isinstance(tasks[0], dict):
                    logger.info(f"First task is dict with keys: {list(tasks[0].keys())}")
                    if 'minio_file_path' in tasks[0]:
                        logger.info("✅ DETECTED: Web research system callback with MinIO file paths!")
                        logger.info("Calling _extract_competitors_from_tasks...")
                        result = await self._extract_competitors_from_tasks(tasks, research, db_session)
                        logger.info(f"Extraction result: {len(result)} competitors found")
                        return result
            
            # Find a key whose value is a list of dicts
            for key, value in parsed_dict.items():
                if isinstance(value, list) and value and all(isinstance(i, dict) for i in value):
                    # Log the first item for debugging
                    logger.info(f"Checking key '{key}' with {len(value)} items. First item keys: {list(value[0].keys()) if value else 'empty'}")
                    
                    # Additional check to ensure these are competitors and not tasks
                    if isinstance(value[0], dict) and 'minio_file_path' in value[0]:
                        logger.info(f"Found tasks in key '{key}', extracting competitors from MinIO files")
                        return await self._extract_competitors_from_tasks(value, research, db_session)
                    
                    # Check if this looks like task data even without minio_file_path
                    if isinstance(value[0], dict) and any(k in value[0] for k in ['task_query', 'task_order', 'id', 'status']):
                        logger.info(f"Found task-like structure in key '{key}', not competitor data. Keys: {list(value[0].keys())}")
                        # If we detect task structure, try to find minio files or skip
                        if 'minio_file_path' in value[0]:
                            return await self._extract_competitors_from_tasks(value, research, db_session)
                        else:
                            logger.warning(f"Tasks found but no minio_file_path available. Cannot extract competitors.")
                            continue
                    
                    # Only treat as competitors if it has competitor-like fields
                    if isinstance(value[0], dict) and any(k in value[0] for k in ['competitor_name', 'website', 'key_feature']):
                        logger.info(f"Lista de competidores encontrada en la clave '{key}' del diccionario.")
                        return value
                    
                    logger.warning(f"List in key '{key}' does not look like competitor data. First item: {value[0] if value else 'empty'}")
            
            logger.warning("El diccionario parseado no contenía una lista de competidores válida.")

        logger.error(f"No se pudo extraer una lista de competidores de la fuente de datos (tipo: {type(data_source)}).")
        return []
    
    async def _extract_competitors_from_tasks(self, tasks: List[Dict[str, Any]], research: CompetitorResearch, db_session: Session) -> List[Dict[str, Any]]:
        """
        Extract competitors from MinIO files referenced in tasks.
        This handles the case where the web research system returns tasks with file paths
        instead of directly returning competitor data.
        """
        logger.info(f"=== STARTING COMPETITOR EXTRACTION FROM TASKS ===")
        logger.info(f"Extracting competitors from {len(tasks)} task files")
        logger.info(f"First task details: {tasks[0] if tasks else 'No tasks'}")
        
        try:
            minio_service = deps.get_minio_research_client()
            
            all_competitors = []
            
            # Collect all content that needs LLM processing
            llm_content = []
            content_for_llm = {}  # Store content by task index
            
            for i, task in enumerate(tasks):
                if 'minio_file_path' in task:
                    file_path = task['minio_file_path']
                    content_bytes = None
                    max_retries = 5
                    base_delay = 1
                    
                    for attempt in range(max_retries):
                        try:
                            logger.info(f"Reading MinIO file (Attempt {attempt + 1}/{max_retries}): {file_path}")
                            content_bytes = minio_service.get_object_data(file_path)
                            if content_bytes:
                                logger.info(f"Successfully read file {file_path}")
                                break
                        except S3Error as e:
                            if e.code == 'NoSuchKey':
                                if attempt < max_retries - 1:
                                    delay = base_delay * (2 ** attempt)
                                    logger.warning(f"File not found (NoSuchKey). Retrying in {delay}s...")
                                    await asyncio.sleep(delay)
                                else:
                                    logger.error(f"File not found after {max_retries} attempts: {file_path}")
                                    continue  # Skip this file and continue with next
                            else:
                                logger.error(f"S3Error on attempt {attempt + 1}: {e}")
                                break
                        except Exception as e:
                            logger.error(f"Unexpected error on attempt {attempt + 1}: {e}")
                            break
                    
                    if content_bytes:
                        content = content_bytes.decode('utf-8')
                        
                        # Try to extract JSON directly from markdown first
                        competitors = self._extract_json_from_markdown(content)
                        if competitors:
                            logger.info(f"Successfully extracted {len(competitors)} competitors from markdown JSON in file: {file_path}")
                            all_competitors.extend(competitors)
                        else:
                            logger.warning(f"Could not extract JSON from markdown in file: {file_path}")
                            # Store content for later LLM processing
                            logger.info(f"Adding content to LLM processing queue for file: {file_path}")
                            content_for_llm[i] = content
            
            # If we successfully extracted competitors from JSON, return them
            if all_competitors:
                logger.info(f"Successfully extracted {len(all_competitors)} competitors from direct JSON parsing")
                return all_competitors
            
            # Fallback: Use LLM processing for content that couldn't be parsed directly
            logger.info("Falling back to LLM processing for content extraction")
            
            # Collect all content that needs LLM processing
            llm_content = list(content_for_llm.values())
            
            if not llm_content:
                logger.error("No content available for LLM processing")
                return []
            
            combined_content = "\n\n---\n\n".join(llm_content)
            logger.info(f"Combined content from {len(llm_content)} files for LLM processing, total length: {len(combined_content)} chars")
            
            # Use LLM to extract competitors
            competitors = await self._extract_competitors_with_llm(combined_content)
            if competitors:
                logger.info(f"Successfully extracted {len(competitors)} competitors using LLM")
                return competitors
            else:
                logger.error("LLM processing failed to extract competitors")
                return []
                
        except Exception as e:
            logger.error(f"Error extracting competitors from tasks: {str(e)}", exc_info=True)
            return []

    def _extract_json_from_markdown(self, content: str) -> List[Dict[str, Any]]:
        """
        Extract JSON data directly from markdown content.
        Returns list of competitors if successful, empty list if failed.
        """
        try:
            # Try to extract JSON from markdown code blocks
            
            # Pattern to match JSON blocks in markdown
            json_patterns = [
                r'```json\s*\n(.*?)\n```',
                r'```\s*\n(\{.*?\})\s*\n```',
                r'```json\s*(\{.*?\})\s*```',
                r'```\s*(\{.*?\})\s*```'
            ]
            
            for pattern in json_patterns:
                matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
                for match in matches:
                    try:
                        # Parse the JSON
                        json_data = json.loads(match.strip())
                        
                        # Extract competitors from various possible structures
                        competitors = []
                        
                        if isinstance(json_data, dict):
                            # Check for competitors key
                            if 'competitors' in json_data and isinstance(json_data['competitors'], list):
                                competitors = json_data['competitors']
                            elif isinstance(json_data, dict) and any(key in json_data for key in ['competitor_name', 'name', 'website']):
                                # Single competitor object
                                competitors = [json_data]
                        elif isinstance(json_data, list):
                            # Direct list of competitors
                            competitors = json_data
                        
                        if competitors:
                            # Validate that these look like competitor objects
                            valid_competitors = []
                            for comp in competitors:
                                if isinstance(comp, dict) and ('competitor_name' in comp or 'name' in comp):
                                    # Normalize similarity_score to decimal if it's an integer > 1
                                    if 'similarity_score' in comp and isinstance(comp['similarity_score'], (int, float)):
                                        if comp['similarity_score'] > 1:
                                            comp['similarity_score'] = comp['similarity_score'] / 100.0
                                    valid_competitors.append(comp)
                            
                            if valid_competitors:
                                logger.info(f"Successfully extracted {len(valid_competitors)} competitors from JSON")
                                return valid_competitors
                    
                    except json.JSONDecodeError as e:
                        logger.debug(f"Failed to parse JSON match: {e}")
                        continue
                    except Exception as e:
                        logger.debug(f"Error processing JSON match: {e}")
                        continue
            
            logger.debug("No valid JSON competitors found in markdown")
            return []
            
        except Exception as e:
            logger.error(f"Error extracting JSON from markdown: {str(e)}")
            return []

    async def _extract_competitors_with_llm(self, combined_content: str) -> List[Dict[str, Any]]:
        """
        Extract competitors using LLM processing.
        This is a fallback method when direct JSON extraction fails.
        """
        try:
            llm = LangChainLLMFactory.create_llm(
                provider="openai", model="gpt-4o-mini", temperature=0.3, max_tokens=16384
            )
            
            extraction_prompt = f"""
Analiza el siguiente contenido de investigación y extrae ÚNICAMENTE la información de competidores.

CONTENIDO DE INVESTIGACIÓN:
{combined_content[:12000]}  # Increased limit for better context

INSTRUCCIONES:
1. Identifica todos los competidores mencionados en el contenido
2. Para cada competidor, extrae:
   - Nombre del competidor
   - Sitio web (si está disponible)
   - Características principales
   - URLs de redes sociales (si están disponibles)
   - Puntuación de similitud (0-1) basada en qué tan similar es al negocio principal

FORMATO DE SALIDA REQUERIDO (JSON):
{{
  "competitors": [
    {{
      "competitor_name": "Nombre del Competidor",
      "website": "https://ejemplo.com",
      "key_feature": "Descripción breve de características principales",
      "instagram_url": "https://instagram.com/ejemplo",
      "facebook_url": "https://facebook.com/ejemplo",
      "linkedin_url": "https://linkedin.com/company/ejemplo",
      "x_url": "https://x.com/ejemplo",
      "youtube_url": "https://youtube.com/ejemplo",
      "tiktok_url": "https://tiktok.com/@ejemplo",
      "similarity_score": 0.85
    }}
  ]
}}

IMPORTANTE: 
- Devuelve SOLO el JSON, sin texto adicional
- Si no hay URL de redes sociales, usa una cadena vacía ""
- La similarity_score debe ser un número decimal entre 0 y 1
- Si el contenido ya contiene JSON bien formateado, úsalo directamente
"""
            
            response = llm.invoke(extraction_prompt)
            
            try:
                competitors_data, _ = extract_and_parse_json(response.content)
                if competitors_data and isinstance(competitors_data, dict) and 'competitors' in competitors_data:
                    competitors = competitors_data['competitors']
                    
                    # Normalize similarity scores
                    for comp in competitors:
                        if 'similarity_score' in comp and isinstance(comp['similarity_score'], (int, float)):
                            if comp['similarity_score'] > 1:
                                comp['similarity_score'] = comp['similarity_score'] / 100.0
                    
                    logger.info(f"Successfully extracted {len(competitors)} competitors using LLM")
                    return competitors
                else:
                    logger.error("LLM response did not contain valid competitor data")
                    return []
            except Exception as parse_error:
                logger.error(f"Failed to parse LLM response: {str(parse_error)}")
                save_problematic_content(response.content, "competitor_extraction_llm_failed")
                return []
                
        except Exception as e:
            logger.error(f"Error using LLM for competitor extraction: {str(e)}", exc_info=True)
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