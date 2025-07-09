import logging
from datetime import datetime
from typing import Dict, Any

from .broker import broker
from app.services.business.competitive_analysis.business_competitors_extraction import EnhancedBusinessAnalyzer, BusinessModel
from app.services.search.web_research_client import WebResearchClient, WebResearchConfig
from app.db.session import SessionLocal

# Configure logging
logger = logging.getLogger(__name__)

@broker.task
async def research_competitors_task(
    prompt_search: Dict[str, Any],
    business_id: str,
    request_id: str,
    business_model_dict: Dict[str, Any],
    lang: str = "en"
) -> Dict[str, Any]:
    """
    TaskIQ task for researching competitors asynchronously using the new web research system.
    
    Args:
        prompt_search: Prompt de búsqueda para la investigación de competidores
        business_id: ID del negocio
        request_id: ID de la solicitud de investigación
        business_model_dict: Diccionario con los datos del modelo de negocio
        lang: Idioma (predeterminado: "en")
        
    Returns:
        Dict with task result information
    """
    logger.info(f"🔍 Starting competitor research task for business {business_id}, request {request_id}")
    
    # Debug: Log the prompt_search contents
    logger.info(f"📋 prompt_search contents: {prompt_search}")
    logger.info(f"🔧 perplexity_model from prompt_search: {prompt_search.get('perplexity_model', 'NOT_FOUND')}")
    
    db = None
    try:
        # Crear sesión de base de datos
        db = SessionLocal()
        
        # Convertir el diccionario a BusinessModel
        business_model = BusinessModel(**business_model_dict)
        
        # Create web research client instead of using n8n
        research_config = WebResearchConfig(
            timeout=800,  # Increased from 120 to 300 seconds (5 minutes) for competitor research
            language=lang
        )
        web_research_client = WebResearchClient(research_config)
        
        # Prepare the payload for the research system according to ResearchCreateRequest schema
        research_payload = {
            "query": prompt_search.get("search_query"),
            "directory_path": f"{business_id}/competitor-analysis/{request_id}",
            "llm_provider": prompt_search.get("llm_provider", "openai"),
            "llm_model": prompt_search.get("llm_model", "gpt-4o-mini"),
            "perplexity_model": prompt_search.get("perplexity_model", "sonar-pro"),
            "max_planning_tasks": 8,
            "callback_enabled": True,
            "callback_url": prompt_search.get("callback_url"),
            "callback_data": {
                "business_id": business_id,
                "request_id": request_id,
                "research_type": "competitor_analysis"
            }
        }

        # Call the research client with the formatted payload
        await web_research_client.research(research_payload)
        
        logger.info(f"✅ Competitor research task for business {business_id}, request {request_id} sent to research system.")
        
        return {
            "status": "in_progress",
            "business_id": business_id,
            "request_id": request_id,
            "submitted_at": datetime.now().isoformat(),
            "task_type": "competitor_research",
            "research_system": "web_research_system"
        }
        
    except Exception as e:
        logger.error(f"❌ Error in competitor research task for business {business_id}: {str(e)}")
        
        # En caso de error, también intentamos actualizar el estado en la base de datos
        if db:
            try:
                from app.models.business.competitive_analysis.business_competitor import CompetitorResearch, CompetitorResearchStatus
                research = db.query(CompetitorResearch).filter(
                    CompetitorResearch.id == request_id
                ).first()
                if research:
                    research.status = CompetitorResearchStatus.FAILED
                    research.completed_at = datetime.now()
                    db.commit()
                    logger.info(f"Updated research status to FAILED for request {request_id}")
            except Exception as db_error:
                logger.error(f"Error updating research status: {str(db_error)}")
        
        raise Exception(f"Error in competitor research task: {str(e)}")
        
    finally:
        # Cerrar sesión de base de datos
        if db:
            db.close()
            logger.debug(f"Database session closed for task {request_id}") 