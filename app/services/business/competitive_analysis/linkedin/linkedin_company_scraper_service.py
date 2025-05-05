import json
import logging
from typing import Dict, Any, Optional, List

from app.services.business.competitive_analysis.linkedin.linkedin_scraper_base import LinkedInScraperBase
from app.services.storage.minio_service import MinioService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LinkedInCompanyScraperService(LinkedInScraperBase):
    """
    Service to scrape LinkedIn company data using Apify's LinkedIn Actor
    Actor ID: od6RadQV98FOARtrp (Apify recommended LinkedIn actor)
    """
    
    def __init__(self, apify_api_token: Optional[str] = None, max_retries: int = 2, timeout_secs: int = 300):
        super().__init__(
            apify_api_token=apify_api_token,
            max_retries=max_retries,
            timeout_secs=timeout_secs
        )
        self.actor_id = "od6RadQV98FOARtrp"  # Updated to recommended Apify actor
        
    async def scrape(self, 
                     company_name: str, 
                     competitor,
                     location: Optional[str] = None, 
                     isUrl: bool = False, 
                     use_proxy: bool = True,
                     timeout_secs: Optional[int] = None,
                     **kwargs) -> Dict[str, Any]:
        """
        Scrape LinkedIn company data
        
        Args:
            company_name: The name of the company or LinkedIn URL
            competitor: The competitor object
            location: Optional location to filter results
            isUrl: Whether the company_name is a URL
            use_proxy: Whether to use a proxy for scraping
            timeout_secs: Optional timeout override for this specific call
            **kwargs: Additional parameters
            
        Returns:
            Dict containing scraped data or error information
        """
        try:
            # Prepare the Actor input based on Apify's recommended configuration
            run_input = {
                "action": "get-companies",  # Use get-companies for company profiles
                "isName": not isUrl,
                "isUrl": isUrl,
                "keywords": [] if isUrl else [company_name.lower()],
                "limit": kwargs.get("limit", 5)  # Increased default limit to 20
            }
            
            # Add location if provided
            if location:
                run_input["location"] = [location]
                
            # Add proxy configuration
            if use_proxy:
                run_input["proxy"] = {
                    "useApifyProxy": True,
                    "apifyProxyCountry": kwargs.get("proxy_country", "US"),
                }
            
            # Get the timeout value (use parameter or fallback to instance default)
            timeout = timeout_secs or self.timeout_secs
            logger.info(f"Using timeout of {timeout} seconds for Apify actor call")
            
            # Run the Actor and wait for it to finish
            logger.info(f"Starting LinkedIn company scrape for: {company_name}")
            logger.info(f"Using run input: {json.dumps(run_input)}")
            run = self.client.actor(self.actor_id).call(
                run_input=run_input,
                timeout_secs=timeout
            )
            
            # Fetch Actor results from the run's dataset
            results = []
            for item in self.client.dataset(run["defaultDatasetId"]).iterate_items():
                if item.get('name').lower() == company_name.lower() or item.get('websiteUrl') == competitor.website or item.get('url') == competitor.linkedin_url:
                    results.append(item)
                
            logger.info(f"Completed LinkedIn company scrape for: {company_name}, found {len(results)} results")
            
            return {
                "success": True,
                "data": results,
                "count": len(results)
            }
            
        except Exception as e:
            return self._handle_error(f"LinkedIn company scrape for {company_name}", e)
    
    async def save_to_minio(self, data: Dict[str, Any], business_id: str, competitor_name: str, file_name: str = "company.json") -> Dict[str, Any]:
        """
        Save scraped company data to MinIO
        
        Args:
            data: The scraped company data
            business_id: The business ID
            competitor_name: The competitor name to use in the path
            file_name: The file name to save (default: company.json)
            
        Returns:
            Dict containing success status and path information
        """
        try:
            # Create path for individual competitor data
            competitor_path = f"{business_id}/competitor-analysis/linkedin/{competitor_name}/{file_name}"
            
            # Initialize MinIO service
            minio_service = MinioService(bucket_name="lattice-businesses")
            
            # Upload data to MinIO
            minio_service.upload_json(competitor_path, data)
            
            logger.info(f"Saved LinkedIn company data to MinIO: {competitor_path}")
            return {
                "success": True,
                "path": competitor_path
            }
            
        except Exception as e:
            return self._handle_error(f"saving LinkedIn company data to MinIO for {competitor_name}", e) 