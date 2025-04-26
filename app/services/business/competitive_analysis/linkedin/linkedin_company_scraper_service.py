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
    
    def __init__(self):
        super().__init__()
        self.actor_id = "od6RadQV98FOARtrp"  # Updated to recommended Apify actor
        
    async def scrape(self, company_name: str, location: Optional[str] = None, isUrl: bool = False, **kwargs) -> Dict[str, Any]:
        """
        Scrape LinkedIn company data
        
        Args:
            company_name: The name of the company or LinkedIn URL
            location: Optional location to filter results
            isUrl: Whether the company_name is a URL
            
        Returns:
            Dict containing scraped data or error information
        """
        try:
            # Prepare the Actor input based on Apify's recommended configuration
            run_input = {
                "action": "get-companies",  # Use get-companies for company profiles
                "isName": not isUrl,
                "isUrl": isUrl,
                "keywords": [] if isUrl else [company_name],
                "urls": [company_name] if isUrl else [],
                "limit": kwargs.get("limit", 20)  # Increased default limit to 20
            }
            
            # Add location if provided
            if location:
                run_input["location"] = [location]
                
            # Add proxy configuration
            run_input["proxy"] = {
                "useApifyProxy": True,
                "apifyProxyCountry": kwargs.get("proxy_country", "US"),
            }
            
            # Run the Actor and wait for it to finish
            logger.info(f"Starting LinkedIn company scrape for: {company_name}")
            logger.info(f"Using run input: {json.dumps(run_input)}")
            run = self.client.actor(self.actor_id).call(run_input=run_input)
            
            # Fetch Actor results from the run's dataset
            results = []
            for item in self.client.dataset(run["defaultDatasetId"]).iterate_items():
                results.append(item)
                
            logger.info(f"Completed LinkedIn company scrape for: {company_name}, found {len(results)} results")
            
            return {
                "success": True,
                "data": results,
                "count": len(results)
            }
            
        except Exception as e:
            return self._handle_error(f"LinkedIn company scrape for {company_name}", e)
    
    async def save_to_minio(self, data: Dict[str, Any], business_id: str, competitor_id: str, file_name: str = "company.json") -> Dict[str, Any]:
        """
        Save scraped company data to MinIO
        
        Args:
            data: The scraped company data
            business_id: The business ID
            competitor_id: The competitor ID
            file_name: The file name to save (default: company.json)
            
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
            
            logger.info(f"Saved LinkedIn company data to MinIO: {competitor_path}")
            return {
                "success": True,
                "path": competitor_path
            }
            
        except Exception as e:
            return self._handle_error(f"saving LinkedIn company data to MinIO for {competitor_id}", e) 