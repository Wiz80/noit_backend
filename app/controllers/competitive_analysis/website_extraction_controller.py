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
            # Obtener el registro del competidor
            competitor = db.query(Competitor).filter(
                Competitor.id == competitor_id,
                Competitor.business_idea_id == self.business_id
            ).first()
            
            if not competitor:
                return {"status": "failed", "error": f"Competidor con ID {competitor_id} no encontrado"}
            
            # Verificar si el competidor tiene un sitio web
            if not competitor.website:
                return {"status": "skipped", "reason": "No hay URL de sitio web disponible"}
            
            # Extraer la URL base para el sitio web
            original_website = competitor.website
            base_website_url = self.extract_base_url(competitor.website)
            logger.info(f"URL simplificada para extracción: {base_website_url} (original: {original_website})")
            
            # Extraer información de redes sociales de la URL base del sitio web
            social_media = await self.extract_social_media_from_website(base_website_url)
            
            # Actualizar registro del competidor con URLs de redes sociales extraídas
            if social_media["instagram"]["url"]:
                competitor.instagram_url = social_media["instagram"]["url"]
                
            if social_media["facebook"]["url"]:
                competitor.facebook_url = social_media["facebook"]["url"]
                
            if social_media["twitter"]["url"]:
                competitor.x_url = social_media["twitter"]["url"]
                
            if social_media["linkedin"]["url"]:
                competitor.linkedin_url = social_media["linkedin"]["url"]
                
            if social_media["youtube"]["url"]:
                competitor.youtube_url = social_media["youtube"]["url"]
                
            if social_media["tiktok"]["url"]:
                competitor.tiktok_url = social_media["tiktok"]["url"]
                
            # Guardar cambios en la base de datos
            db.commit()
            
            return {
                "status": "success",
                "competitor_id": competitor_id,
                "original_website": original_website,
                "scraped_website": base_website_url,
                "social_media": social_media
            }
            
        except Exception as e:
            logger.error(f"Error actualizando redes sociales del competidor: {str(e)}")
            return {
                "status": "failed",
                "error": str(e)
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
            
    async def _correct_website_url_with_llm(self, website_url: str) -> str:
        """
        Corrige una URL de sitio web mal formada utilizando un LLM.
        Si la corrección falla, devuelve la URL original.
        """
        if not website_url or not isinstance(website_url, str):
            return ""
        
        try:
            logger.info(f"Intentando corregir URL con LLM: {website_url}")
            llm = LangChainLLMFactory.create_llm(
                provider="openai",
                model="gpt-4o-mini",
                temperature=0.0,
                max_tokens=150
            )

            prompt_template = ChatPromptTemplate.from_messages([
                ("system", "You are an expert at cleaning and correcting website URLs. Your task is to take a potentially malformed URL and return ONLY the corrected, clean, and functional URL. Remove any extra spaces, fix typos, and ensure it's a valid web address. Do not include 'http://' or 'https://' unless it's necessary to fix the URL. Do not add any explanation, preamble, or markdown. Only output the corrected URL string. For example, if the input is 'https: //www.ibm.com/ai', the output should be 'www.ibm.com/ai'."),
                ("human", "Please correct the following URL: '{url}'")
            ])
            
            chain = prompt_template | llm
            response = await chain.ainvoke({"url": website_url})
            
            corrected_url = response.content.strip().replace(" ", "")
            
            if not corrected_url or "." not in corrected_url:
                logger.warning(f"LLM produjo una URL sospechosa '{corrected_url}' desde '{website_url}'. Se usará la original.")
                return website_url

            logger.info(f"LLM corrigió la URL: '{website_url}' -> '{corrected_url}'")
            return corrected_url
        except Exception as e:
            logger.error(f"Error corrigiendo URL con LLM: {e}. Se usará la URL original.")
            return website_url
        
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
                    
                    # Corregir la URL del sitio web usando LLM
                    original_website = competitor.website
                    corrected_website_url = await self._correct_website_url_with_llm(original_website)

                    # Actualizar la web del competidor en la BD si se corrigió y update_db es true
                    if update_db and original_website != corrected_website_url:
                        competitor.website = corrected_website_url
                        db.commit()
                        logger.info(f"Sitio web del competidor {competitor.id} actualizado de '{original_website}' a '{corrected_website_url}'")

                    # Extraer redes sociales
                    if update_db:
                        # Usar el método existente que ahora extrae la URL base.
                        # Este método usará el valor actualizado de la BD si se modificó.
                        result = await self.update_competitor_social_media(competitor_id, db)
                    else:
                        # Extraer la URL base para el sitio web
                        base_website_url = self.extract_base_url(corrected_website_url)
                        logger.info(f"URL simplificada para extracción: {base_website_url} (original: {original_website}, corregida: {corrected_website_url})")
                        
                        try:
                            # Extraer redes sociales sin actualizar la base de datos
                            social_media = await self.extract_social_media_from_website(base_website_url)
                            result = {
                                "status": "success",
                                "competitor_id": competitor_id,
                                "original_website": original_website,
                                "scraped_website": base_website_url,
                                "corrected_website": corrected_website_url,
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
                                "corrected_website": corrected_website_url,
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