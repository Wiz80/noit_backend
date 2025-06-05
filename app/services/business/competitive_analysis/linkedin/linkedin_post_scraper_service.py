import os
import logging
from typing import Dict, Any, Optional, List

from app.services.business.competitive_analysis.linkedin.linkedin_scraper_base import LinkedInScraperBase
from app.services.storage.minio_service import MinioService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LinkedInPostScraperService(LinkedInScraperBase):
    """
    Service to scrape LinkedIn posts using Apify's LinkedIn Post Search Scraper
    Actor ID: kfiWbq3boy3dWKbiL (LinkedIn company search scraper)
    """
    
    def __init__(self, apify_api_token: Optional[str] = None, max_retries: int = 2, timeout_secs: int = 300):
        super().__init__(
            apify_api_token=apify_api_token,
            max_retries=max_retries,
            timeout_secs=timeout_secs
        )
        self.actor_id = "kfiWbq3boy3dWKbiL"  # Actualizado al actor correcto
        
    def _get_default_linkedin_cookies(self) -> List[Dict[str, Any]]:
        """
        Returns a list of default LinkedIn cookies that pueden ser usadas para autenticación
        
        Returns:
            List[Dict[str, Any]]: Lista de cookies predefinidas para LinkedIn
        """
        return [
            {
                "domain": ".linkedin.com",
                "expirationDate": 1746143676.122925,
                "hostOnly": False,
                "httpOnly": True,
                "name": "__cf_bm",
                "path": "/",
                "sameSite": "no_restriction",
                "secure": True,
                "session": False,
                "storeId": "0",
                "value": "Fko_XMjsDHZhlCOygcBWWHVspHSAawzwMhHB_bJYMTk-1746141876-1.0.1.1-vH7resNg4qIMPFjJXMOtUkvyJjnFsYYePbLuF_UVdlpv5UeBxme_POO5V5nAesrEa2_S8UItODVlDQtwFr.3.AsagOLuJiXsFE0iNYLH9l8",
                "id": 1
            },
            {
                "domain": ".linkedin.com",
                "expirationDate": 1752884072,
                "hostOnly": False,
                "httpOnly": False,
                "name": "_gcl_au",
                "path": "/",
                "sameSite": "unspecified",
                "secure": False,
                "session": False,
                "storeId": "0",
                "value": "1.1.1322076727.1745108072.837929275.1745374342.1745374341",
                "id": 2
            },
            {
                "domain": ".linkedin.com",
                "hostOnly": False,
                "httpOnly": False,
                "name": "lang",
                "path": "/",
                "sameSite": "no_restriction",
                "secure": True,
                "session": True,
                "storeId": "0",
                "value": "v=2&lang=en-us",
                "id": 13
            },
            {
                "domain": ".www.linkedin.com",
                "expirationDate": 1777677876.122627,
                "hostOnly": False,
                "httpOnly": True,
                "name": "li_at",
                "path": "/",
                "sameSite": "no_restriction",
                "secure": True,
                "session": False,
                "storeId": "0",
                "value": "AQEDAS25u-oDk4ExAAABllCM8eMAAAGWsjcTLE0AB4K8QrFlnTTQ_ftu3TfNvu78r_F7SeuxnBg795gjzXS6cLR8fwKZv0tRML1m_O119SwrerFoIMlvNv1wOxl8FQXi7KWMFrqlCUucDdltQSr9kHQB",
                "id": 26
            },
            {
                "domain": ".www.linkedin.com",
                "expirationDate": 1777677876.122738,
                "hostOnly": False,
                "httpOnly": False,
                "name": "JSESSIONID",
                "path": "/",
                "sameSite": "no_restriction",
                "secure": True,
                "session": False,
                "storeId": "0",
                "value": "\"ajax:4802930318244996953\"",
                "id": 25
            },
        ]
        
    async def scrape(self, company_url: str, min_delay: int = 2, max_delay: int = 8, deep_scrape: bool = True, limit_per_source: int = 10, timeout_secs: Optional[int] = None, **kwargs) -> Dict[str, Any]:
        """
        Scrape LinkedIn posts for a specific company
        
        Args:
            company_url: The LinkedIn URL of the company
            min_delay: Minimum delay between requests (seconds)
            max_delay: Maximum delay between requests (seconds)
            deep_scrape: Whether to perform a deep scrape
            limit_per_source: Maximum number of posts to scrape per source
            timeout_secs: Optional timeout override for this specific call
            **kwargs: Additional parameters
            
        Returns:
            Dict containing scraped data or error information
        """
        try:
            # Prepare the Actor input with the correct configuration
            run_input = {
                "urls": [company_url],
                "deepScrape": deep_scrape,
                "limitPerSource": limit_per_source,
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
            
            # Add cookies - usar cookies proporcionadas o las predeterminadas
            if kwargs.get("cookies"):
                run_input["cookie"] = kwargs.get("cookies")
            else:
                # Si no se proporcionan cookies, usar las predeterminadas
                run_input["cookie"] = self._get_default_linkedin_cookies()
            
            # Get the timeout value (use parameter or fallback to instance default)
            timeout = timeout_secs or self.timeout_secs
            logger.info(f"Using timeout of {timeout} seconds for Apify actor call")
            
            # Run the Actor and wait for it to finish
            logger.info(f"Starting LinkedIn post scrape for: {company_url}")
            run = self.client.actor(self.actor_id).call(
                run_input=run_input,
                timeout_secs=timeout
            )
            
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
    
    async def save_to_minio(self, data: Dict[str, Any], business_id: str, competitor_name: str, file_name: str = "post.json") -> Dict[str, Any]:
        """
        Save scraped post data to MinIO
        
        Args:
            data: The scraped post data
            business_id: The business ID
            competitor_name: The competitor name to use in the path
            file_name: The file name to save (default: post.json)
            
        Returns:
            Dict containing success status and path information
        """
        try:
            # Create path for individual competitor data
            competitor_path = f"{business_id}/competitor-analysis/linkedin/{competitor_name}/{file_name}"
            
            # Initialize MinIO service
            minio_service = MinioService(bucket_name=settings.MINIO_BUCKET_NAME)
            
            # Upload data to MinIO
            minio_service.upload_json(competitor_path, data)
            
            logger.info(f"Saved LinkedIn post data to MinIO: {competitor_path}")
            return {
                "success": True,
                "path": competitor_path
            }
            
        except Exception as e:
            return self._handle_error(f"saving LinkedIn post data to MinIO for {competitor_name}", e)

