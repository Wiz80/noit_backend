import json
import logging
from typing import Dict, Any, Optional, List

from app.services.business.competitive_analysis.linkedin.linkedin_scraper_base import LinkedInScraperBase
from app.services.storage.minio_service import MinioService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LinkedInAdsScraperService(LinkedInScraperBase):
    """
    Service to scrape LinkedIn ads library using Apify's LinkedIn Ads Library Scraper
    Actor ID: saswave/linkedin-ads-library-scraper
    """
    
    def __init__(self):
        super().__init__()
        self.actor_id = "saswave/linkedin-ads-library-scraper"
        self.date_options = [
            "last-24-hours", 
            "last-7-days", 
            "last-30-days", 
            "last-90-days",
            "current-month", 
            "last-month", 
            "custom"
        ]
        
    async def scrape(self, company_url: str, word_search: Optional[str] = None, 
                    date_option: str = "last-30-days", date_start: Optional[str] = None, 
                    date_end: Optional[str] = None, country: str = "ALL", limit: int = 50, **kwargs) -> Dict[str, Any]:
        """
        Scrape LinkedIn ads for a specific company
        
        Args:
            company_url: The LinkedIn URL of the company
            word_search: Optional keyword to search for in ads
            date_option: One of the date options (last-24-hours, last-7-days, etc.)
            date_start: Start date for custom range (YYYY-MM-DD)
            date_end: End date for custom range (YYYY-MM-DD)
            country: Country code to filter ads by
            limit: Maximum number of ads to scrape
            
        Returns:
            Dict containing scraped data or error information
        """
        try:
            # Validate date option
            if date_option not in self.date_options:
                return {"success": False, "error": f"Invalid date option. Must be one of {self.date_options}"}
                
            # For custom date range, validate dates
            if date_option == "custom" and not (date_start and date_end):
                return {"success": False, "error": "date_start and date_end are required for custom date range"}
                
            # Prepare the Actor input
            run_input = {
                "proxyConfiguration": {
                    "useApifyProxy": True,
                    "apifyProxyGroups": [],
                },
                "limit": limit,
                "companies": [company_url],
                "company_word_search": word_search,
                "company_date_range_type": date_option,
                "company_date_start": date_start,
                "company_date_end": date_end,
                "company_country": country
            }
            
            # Run the Actor and wait for it to finish
            logger.info(f"Starting LinkedIn ads scrape for: {company_url}")
            run = self.client.actor(self.actor_id).call(run_input=run_input)
            
            # Fetch Actor results from the run's dataset
            results = []
            for item in self.client.dataset(run["defaultDatasetId"]).iterate_items():
                results.append(item)
                
            logger.info(f"Completed LinkedIn ads scrape for: {company_url}, found {len(results)} ads")
            
            return {
                "success": True,
                "data": results,
                "count": len(results)
            }
            
        except Exception as e:
            return self._handle_error(f"LinkedIn ads scrape for {company_url}", e)
    
    async def save_to_minio(self, data: Dict[str, Any], business_id: str, competitor_id: str, file_name: str = "ads.json") -> Dict[str, Any]:
        """
        Save scraped ads data to MinIO
        
        Args:
            data: The scraped ads data
            business_id: The business ID
            competitor_id: The competitor ID
            file_name: The file name to save (default: ads.json)
            
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
            
            logger.info(f"Saved LinkedIn ads data to MinIO: {competitor_path}")
            return {
                "success": True,
                "path": competitor_path
            }
            
        except Exception as e:
            return self._handle_error(f"saving LinkedIn ads data to MinIO for {competitor_id}", e) 