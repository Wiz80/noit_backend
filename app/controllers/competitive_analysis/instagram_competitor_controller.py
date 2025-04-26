from sqlalchemy.orm import Session
import logging
import os
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv

from app.models.business.competitive_analysis.instagram import InstagramScrapingJob
from app.services.business.competitive_analysis.instagram.instagram_scraper import InstagramScraper
from app.db.session import SessionLocal

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class InstagramCompetitorController:
    """
    Controller para el análisis de competidores en Instagram.
    Maneja la extracción y procesamiento de datos de Instagram.
    """
    
    def __init__(self, business_id: str):
        """
        Inicializa el controlador con el ID del negocio.
        
        Args:
            business_id (str): ID del negocio
        """
        self.business_id = business_id
        
        # Inicializar el scraper de Instagram con almacenamiento en MinIO
        self.instagram_scraper = InstagramScraper(
            api_key=os.getenv("APIFY_API_KEY"),
            output_folder=f"{business_id}/competitor-analysis/instagram",
            bucket_name="lattice-businesses"
        )
    
    async def analyze_instagram_competitor(self, username, competitor_id=None, results_limit=10, max_comments=5):
        """
        Analiza un competidor en Instagram.
        
        Args:
            username (str): Nombre de usuario de Instagram del competidor
            competitor_id (str, opcional): ID del competidor en la base de datos
            results_limit (int): Número máximo de posts a extraer
            max_comments (int): Número máximo de comentarios por post
            
        Returns:
            dict: Resultados del análisis
        """
        try:
            # Obtener o crear job de scraping
            db = SessionLocal()
            scraping_job = None
            
            if competitor_id:
                # Verificar si ya existe un job de scraping
                scraping_job = db.query(InstagramScrapingJob).filter(
                    InstagramScrapingJob.competitor_id == competitor_id,
                    InstagramScrapingJob.username == username
                ).first()
                
                if not scraping_job:
                    # Crear un nuevo job de scraping
                    scraping_job = InstagramScrapingJob(
                        business_id=self.business_id,
                        competitor_id=competitor_id,
                        username=username,
                        status="pending",
                        results_limit=results_limit,
                        max_comments=max_comments
                    )
                    db.add(scraping_job)
                    db.commit()
                    db.refresh(scraping_job)
            
            # Ejecutar el scraper de Instagram
            result = await self.instagram_scraper.run_full_instagram_scraper(
                usernames=[username],
                results_limit=results_limit,
                max_comments=max_comments,
                scraping_job=scraping_job,
                db_session=db
            )
            
            if db:
                db.close()
                
            return {
                "username": username,
                "status": result.get("status", "completed"),
                "message": result.get("message", f"Instagram analysis completed for {username}")
            }
        except Exception as e:
            if db:
                db.close()
                
            return {
                "username": username,
                "status": "failed",
                "error": str(e)
            }
    
    @staticmethod
    def extract_instagram_username(instagram_url):
        """
        Extrae el nombre de usuario de una URL de Instagram.
        
        Args:
            instagram_url (str): URL del perfil de Instagram
            
        Returns:
            str: Nombre de usuario de Instagram o None si es inválido
        """
        if not instagram_url:
            return None
        
        # Eliminar la barra final si existe
        if instagram_url.endswith('/'):
            instagram_url = instagram_url[:-1]
        
        # Extraer el último segmento de la URL
        parts = instagram_url.split('/')
        username = parts[-1]
        
        # Eliminar parámetros de consulta si existen
        if '?' in username:
            username = username.split('?')[0]
        
        return username 