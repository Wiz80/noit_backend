from sqlalchemy.orm import Session
import logging
import os
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse
from dotenv import load_dotenv
from pydantic import BaseModel

from app.models.business.competitive_analysis.competitors import Competitor
from app.services.scrape.website_social_scraper import WebsiteSocialMediaScraper
from app.schemas.business.business_competitors import WebsiteSocialMediaScrapingRequest, WebsiteSocialMediaScrapingResponse

from app.services.llm.langchain_factory import LangChainLLMFactory
from langchain_core.prompts import ChatPromptTemplate
from app.utils.decode_json import clean_json_encoding
from app.models.user import User

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebsiteExtractionController:
    """
    Controller para la extracción de datos de sitios web de competidores.
    Maneja la extracción de redes sociales y otra información de sitios web.
    """
    
    def __init__(self, business_id: str):
        """
        Inicializa el controlador con el ID del negocio.
        
        Args:
            business_id (str): ID del negocio
        """
        self.business_id = business_id
        
        # Inicializar Website Social Media Scraper
        self.scraper = WebsiteSocialMediaScraper(
            llm_provider="openai",
            llm_model="gpt-4o-mini",
            api_key=os.getenv("OPENAI_API_KEY"),
            headless=True,
            verbose=True
        )
    
    async def extract_social_media_from_website(self, website_url: str) -> Dict[str, Dict[str, str]]:
        """
        Extrae información de redes sociales del sitio web de un competidor mediante scraping potenciado por IA.
        
        Args:
            website_url (str): La URL del sitio web del competidor
            
        Returns:
            Dict: Enlaces de redes sociales y nombres de usuario
        """
        try:
            logger.info(f"Extrayendo redes sociales del sitio web: {website_url}")
            
            # Utilizar el WebsiteSocialMediaScraper para extraer información de redes sociales
            social_media_info = await self.scraper.extract_social_media(website_url)
            
            logger.info(f"Extracción exitosa de redes sociales del sitio web: {website_url}")
            return social_media_info
            
        except Exception as e:
            error_message = str(e).lower()
            
            # Check for critical errors that should be propagated
            critical_errors = [
                "executable doesn't exist",
                "browsertype.launch",
                "playwright",
                "chromium",
                "connection refused",
                "network is unreachable"
            ]
            
            # If it's a critical error, propagate it
            if any(critical_error in error_message for critical_error in critical_errors):
                logger.error(f"❌ Critical error extracting social media from {website_url}: {str(e)}")
                raise Exception(f"Critical scraping error: {str(e)}")
            
            # For non-critical errors, log and return empty result
            logger.warning(f"⚠️ Non-critical error extracting social media from {website_url}: {str(e)}")
            return self.scraper._get_empty_result()
    
    @staticmethod
    def extract_base_url(url: str) -> str:
        """
        Extrae solo el dominio base de una URL.
        
        Args:
            url (str): La URL completa
            
        Returns:
            str: La URL base (esquema + dominio)
        """
        if not url:
            return ""
            
        # Asegurar que la URL tiene un esquema
        if not url.startswith('http://') and not url.startswith('https://'):
            url = f"https://{url}"
            
        # Analizar la URL
        parsed_url = urlparse(url)
        
        # Reconstruir solo con esquema y netloc (dominio)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        return base_url
        
    async def update_competitor_social_media(self, competitor_id: str, db: Session) -> Dict[str, Any]:
        """
        Actualiza la información de redes sociales de un competidor mediante scraping de su sitio web.
        
        Args:
            competitor_id (str): ID del competidor en la base de datos
            db (Session): Sesión de base de datos
            
        Returns:
            Dict: Información actualizada de redes sociales y estado
        """
        try:
            logger.info(f"🔍 Iniciando actualización de redes sociales para competidor {competitor_id}")
            
            # Obtener el registro del competidor
            competitor = db.query(Competitor).filter(
                Competitor.id == competitor_id,
                Competitor.business_idea_id == self.business_id
            ).first()
            
            if not competitor:
                logger.warning(f"❌ Competidor con ID {competitor_id} no encontrado en business {self.business_id}")
                return {"status": "failed", "error": f"Competidor con ID {competitor_id} no encontrado"}
            
            logger.info(f"✅ Competidor encontrado: {competitor.competitor_name} (ID: {competitor_id})")
            
            # Verificar si el competidor tiene un sitio web
            if not competitor.website:
                logger.info(f"⏭️ Competidor {competitor_id} no tiene URL de sitio web disponible")
                return {"status": "skipped", "reason": "No hay URL de sitio web disponible"}
            
            # Extraer la URL base para el sitio web
            original_website = competitor.website
            base_website_url = self.extract_base_url(competitor.website)
            logger.info(f"🌐 URL simplificada para extracción: {base_website_url} (original: {original_website})")
            
            # Extraer información de redes sociales de la URL base del sitio web
            logger.info(f"🔍 Iniciando extracción de redes sociales para {base_website_url}")
            social_media = await self.extract_social_media_from_website(base_website_url)
            logger.info(f"📊 Resultados de extracción: {social_media}")
            
            # Actualizar registro del competidor con URLs de redes sociales extraídas
            updated_fields = []
            
            if social_media["instagram"]["url"]:
                old_instagram = competitor.instagram_url
                competitor.instagram_url = social_media["instagram"]["url"]
                updated_fields.append(f"instagram: '{old_instagram}' -> '{competitor.instagram_url}'")
                
            if social_media["facebook"]["url"]:
                old_facebook = competitor.facebook_url
                competitor.facebook_url = social_media["facebook"]["url"]
                updated_fields.append(f"facebook: '{old_facebook}' -> '{competitor.facebook_url}'")
                
            if social_media["twitter"]["url"]:
                old_x = competitor.x_url
                competitor.x_url = social_media["twitter"]["url"]
                updated_fields.append(f"x/twitter: '{old_x}' -> '{competitor.x_url}'")
                
            if social_media["linkedin"]["url"]:
                old_linkedin = competitor.linkedin_url
                competitor.linkedin_url = social_media["linkedin"]["url"]
                updated_fields.append(f"linkedin: '{old_linkedin}' -> '{competitor.linkedin_url}'")
                
            if social_media["youtube"]["url"]:
                old_youtube = competitor.youtube_url
                competitor.youtube_url = social_media["youtube"]["url"]
                updated_fields.append(f"youtube: '{old_youtube}' -> '{competitor.youtube_url}'")
                
            if social_media["tiktok"]["url"]:
                old_tiktok = competitor.tiktok_url
                competitor.tiktok_url = social_media["tiktok"]["url"]
                updated_fields.append(f"tiktok: '{old_tiktok}' -> '{competitor.tiktok_url}'")
            
            # Log the fields that will be updated
            if updated_fields:
                logger.info(f"📝 Actualizando campos para competidor {competitor_id}: {', '.join(updated_fields)}")
            else:
                logger.info(f"ℹ️ No se encontraron nuevas URLs de redes sociales para competidor {competitor_id}")
            
            # Guardar cambios en la base de datos
            logger.info(f"💾 Guardando cambios en la base de datos para competidor {competitor_id}")
            db.commit()
            logger.info(f"✅ Cambios guardados exitosamente para competidor {competitor_id}")
            
            return {
                "status": "success",
                "competitor_id": competitor_id,
                "original_website": original_website,
                "scraped_website": base_website_url,
                "social_media": social_media,
                "updated_fields": updated_fields
            }
            
        except Exception as e:
            logger.error(f"❌ Error actualizando redes sociales del competidor {competitor_id}: {str(e)}")
            
            # Rollback explícito en caso de error
            try:
                db.rollback()
                logger.info(f"🔄 Rollback ejecutado para competidor {competitor_id}")
            except Exception as rollback_error:
                logger.error(f"❌ Error ejecutando rollback para competidor {competitor_id}: {str(rollback_error)}")
            
            return {
                "status": "failed",
                "error": str(e),
                "competitor_id": competitor_id
            }
            
    async def batch_update_competitors_social_media(self, competitor_ids: List[str], db: Session) -> Dict[str, Dict[str, Any]]:
        """
        Actualiza la información de redes sociales para múltiples competidores.
        
        Args:
            competitor_ids (List[str]): Lista de IDs de competidores
            db (Session): Sesión de base de datos
            
        Returns:
            Dict: Resultados para cada competidor
        """
        results = {}
        
        for competitor_id in competitor_ids:
            result = await self.update_competitor_social_media(competitor_id, db)
            results[competitor_id] = result
            
        return results
            
    async def run_website_social_media_extraction(
        self,
        competitor_ids: List[str],
        task_id: str,
        update_db: bool,
        db: Session,
        progress_callback=None
    ) -> Dict[str, Any]:
        """
        Ejecuta el proceso de extracción de redes sociales de sitios web para múltiples competidores.
        
        Args:
            competitor_ids: Lista de IDs de competidores a procesar
            task_id: Identificador de tarea para seguimiento del progreso
            update_db: Si se debe actualizar la base de datos con los resultados
            db: Sesión de base de datos
            progress_callback: Función de callback opcional para reportar actualizaciones de progreso
            
        Returns:
            Dict: Resultados del proceso de extracción
        """
        try:
            results = {}
            total_competitors = len(competitor_ids)
            completed = 0
            
            # Procesar cada competidor
            for competitor_id in competitor_ids:
                try:
                    # Obtener competidor de la base de datos
                    competitor = db.query(Competitor).filter(
                        Competitor.id == competitor_id,
                        Competitor.business_idea_id == self.business_id
                    ).first()
                    
                    if not competitor or not competitor.website:
                        results[competitor_id] = {
                            "status": "skipped",
                            "reason": "Competidor no encontrado o sin sitio web disponible"
                        }
                        completed += 1
                        continue
                    
                    # Extraer redes sociales directamente sin corrección de URL
                    if update_db:
                        # Usar el método existente que actualiza la base de datos
                        result = await self.update_competitor_social_media(competitor_id, db)
                    else:
                        # Extraer la URL base para el sitio web
                        original_website = competitor.website
                        base_website_url = self.extract_base_url(original_website)
                        logger.info(f"URL simplificada para extracción: {base_website_url} (original: {original_website})")
                        
                        try:
                            # Extraer redes sociales sin actualizar la base de datos
                            social_media = await self.extract_social_media_from_website(base_website_url)
                            result = {
                                "status": "success",
                                "competitor_id": competitor_id,
                                "original_website": original_website,
                                "scraped_website": base_website_url,
                                "social_media": social_media
                            }
                        except Exception as e:
                            logger.error(f"Error extrayendo redes sociales para el competidor {competitor_id}: {str(e)}")
                            result = {
                                "status": "failed", 
                                "error": str(e),
                                "competitor_id": competitor_id,
                                "original_website": original_website,
                                "scraped_website": base_website_url,
                            }
                    
                    results[competitor_id] = result
                    completed += 1
                    
                except Exception as e:
                    logger.error(f"Error procesando competidor {competitor_id}: {str(e)}")
                    results[competitor_id] = {
                        "status": "failed",
                        "error": str(e)
                    }
                    completed += 1
                
                # Reportar progreso
                progress = int((completed / total_competitors) * 100)
                
                # Si se proporcionó un callback de progreso, usarlo
                if progress_callback:
                    progress_callback(
                        task_id=task_id,
                        progress=progress,
                        status="processing",
                        results=results
                    )
            
            # Resultado final
            return {
                "status": "completed",
                "results": results,
                "progress": 100
            }
            
        except Exception as e:
            logger.error(f"Error en run_website_social_media_extraction: {str(e)}")
            return {
                "status": "failed",
                "error": str(e),
                "progress": 0
            } 