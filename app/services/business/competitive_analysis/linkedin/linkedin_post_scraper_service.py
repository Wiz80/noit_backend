from apify_client import ApifyClient
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import json
import logging
from typing import Dict, Any, Optional, List

from app.services.business.competitive_analysis.linkedin.linkedin_scraper_base import LinkedInScraperBase
from app.services.storage.minio_service import MinioService

# Intentar cargar variables de entorno desde diferentes ubicaciones
# Primero intentamos desde el directorio actual
load_dotenv()

# Si no se cargó, intentamos desde el directorio raíz del proyecto
root_dir = Path(__file__).resolve().parents[4]  # Subir 4 niveles para llegar a la raíz del proyecto
env_path = root_dir / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

# Verificar que el token está disponible
apify_token = os.getenv("APIFY_API_KEY")
if not apify_token:
    print("Error: No se encontró la variable de entorno APIFY_API_TOKEN")
    print(f"Asegúrate de que el archivo .env existe y contiene la variable APIFY_API_TOKEN")
    print(f"Ubicación actual: {os.getcwd()}")
    print(f"Ubicación de la raíz del proyecto (intentada): {root_dir}")
    sys.exit(1)

# Initialize the ApifyClient with your API token
client = ApifyClient(apify_token)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LinkedInPostScraperService(LinkedInScraperBase):
    """
    Service to scrape LinkedIn posts using Apify's LinkedIn Post Search Scraper
    Actor ID: curious_coder/linkedin-post-search-scraper
    """
    
    def __init__(self):
        super().__init__()
        self.actor_id = "curious_coder/linkedin-post-search-scraper"
        
    async def scrape(self, company_url: str, min_delay: int = 2, max_delay: int = 8, deep_scrape: bool = True, **kwargs) -> Dict[str, Any]:
        """
        Scrape LinkedIn posts for a specific company
        
        Args:
            company_url: The LinkedIn URL of the company
            min_delay: Minimum delay between requests (seconds)
            max_delay: Maximum delay between requests (seconds)
            deep_scrape: Whether to perform a deep scrape
            
        Returns:
            Dict containing scraped data or error information
        """
        try:
            # Prepare the Actor input with cookie data if available
            run_input = {
                "urls": [company_url],
                "deepScrape": deep_scrape,
                "rawData": False,
                "minDelay": min_delay,
                "maxDelay": max_delay,
            }
            
            # Add proxy configuration
            if kwargs.get("use_proxy", True):
                run_input["proxy"] = {
                    "useApifyProxy": True,
                    "apifyProxyCountry": kwargs.get("proxy_country", "US"),
                }
            
            # Add cookies if provided
            if kwargs.get("cookies"):
                run_input["cookie"] = kwargs.get("cookies")
            
            # Run the Actor and wait for it to finish
            logger.info(f"Starting LinkedIn post scrape for: {company_url}")
            run = self.client.actor(self.actor_id).call(run_input=run_input)
            
            # Fetch Actor results from the run's dataset
            results = []
            for item in self.client.dataset(run["defaultDatasetId"]).iterate_items():
                results.append(item)
                
            logger.info(f"Completed LinkedIn post scrape for: {company_url}, found {len(results)} posts")
            
            return {
                "success": True,
                "data": results,
                "count": len(results)
            }
            
        except Exception as e:
            return self._handle_error(f"LinkedIn post scrape for {company_url}", e)
    
    async def save_to_minio(self, data: Dict[str, Any], business_id: str, competitor_id: str, file_name: str = "post.json") -> Dict[str, Any]:
        """
        Save scraped post data to MinIO
        
        Args:
            data: The scraped post data
            business_id: The business ID
            competitor_id: The competitor ID
            file_name: The file name to save (default: post.json)
            
        Returns:
            Dict containing success status and path information
        """
        try:
            # Create path for individual competitor data
            competitor_path = f"{business_id}/competitor-analysis/linkedin/{competitor_id}/{file_name}"
            
            # Initialize MinIO service
            minio_service = MinioService(bucket_name="lattice-businesses")
            
            # Upload data to MinIO
            minio_service.upload_json(competitor_path, data)
            
            logger.info(f"Saved LinkedIn post data to MinIO: {competitor_path}")
            return {
                "success": True,
                "path": competitor_path
            }
            
        except Exception as e:
            return self._handle_error(f"saving LinkedIn post data to MinIO for {competitor_id}", e)

