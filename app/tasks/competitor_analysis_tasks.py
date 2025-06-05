import logging
from datetime import datetime
from typing import Dict, Any

from .broker import broker
from app.services.business.competitive_analysis.business_competitors_extraction import EnhancedBusinessAnalyzer, BusinessModel
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
    TaskIQ task for researching competitors asynchronously.
    
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
    
    db = None
    try:
        # Crear sesión de base de datos
        db = SessionLocal()
        
        # Convertir el diccionario a BusinessModel
        business_model = BusinessModel(**business_model_dict)
        
        # Crear instancia del analizador
        analyzer = EnhancedBusinessAnalyzer(
            business_model=business_model,
            lang=lang,
            max_depth=1,
            db=db
        )
        
        # Ejecutar la investigación de competidores
        await analyzer.research_competitors_async(
            prompt_search=prompt_search,
            business_id=business_id,
            request_id=request_id
        )
        
        logger.info(f"✅ Competitor research task completed for business {business_id}, request {request_id}")
        
        return {
            "status": "completed",
            "business_id": business_id,
            "request_id": request_id,
            "completed_at": datetime.now().isoformat(),
            "task_type": "competitor_research"
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