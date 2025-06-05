from typing import List, Optional, Dict, Any
import os
from datetime import datetime
from urllib.parse import urlencode
from dotenv import load_dotenv
import aiohttp
import json
import logging
from sqlalchemy.orm import Session
from app.models.business.competitive_analysis.competitors import Competitor
from app.services.storage.minio_service import MinioService
from app.services.business.competitive_analysis.linkedin.linkedin_scraper_base import LinkedInScraperBase
from apify_client import ApifyClient

# Logger setup
logger = logging.getLogger(__name__)
 

class LinkedInAdsScraperService(LinkedInScraperBase):
    """Service for interacting with LinkedIn Ads Library through Apify actor."""
    
    BASE_URL = "https://www.linkedin.com/ad-library/search"
    
    # Available date options for LinkedIn Ad Library
    DATE_OPTIONS = {
        "last-30-days": "last-30-days",
        "this-month": "this-month",
        "this-year": "this-year",
        "last-year": "last-year",
        "custom": "custom"  # Requires start_date and end_date
    }
    
    def __init__(
        self, 
        apify_api_token: Optional[str] = None,
        max_results: int = 100,
        actor_id: str = "31BPULiLZ42ca1mvj",
        max_retries: int = 2,
        timeout_secs: int = 600
    ):
        """
        Initialize the Apify LinkedIn Ads Service.
        
        Args:
            apify_api_token: The Apify API token (will use env var if not provided)
            max_results: Default maximum number of results to fetch
            actor_id: The Apify actor ID for LinkedIn ads
            max_retries: Number of retries for ApifyClient
            timeout_secs: Timeout in seconds for actor run calls
        """
        super().__init__(
            apify_api_token=apify_api_token,
            max_retries=max_retries,
            timeout_secs=timeout_secs
        )
        self.actor_id = actor_id
        self.max_results = max_results
        
    async def scrape(
        self,
        competitor_name: Optional[str] = None,
        companies: Optional[List[str]] = None,
        date_range_type: str = "last-30-days",
        combine_companies_onesearch: bool = False,
        countries: Optional[List[str]] = None,
        date_type: str = "date_range_type",
        date_start: Optional[str] = None,
        date_end: Optional[str] = None,
        timeout_secs: Optional[int] = None,
        **kwargs
    ) -> Dict:
        """
        Fetch ads data from LinkedIn Ad Library using Apify actor.
        
        Args:
            competitor_name: The competitor name (will be used as accountOwner)
            companies: List of LinkedIn company URLs to search
            date_range_type: Time range for ads (last-30-days, this-month, this-year, last-year, custom)
            limit: Maximum number of results to return
            combine_companies_onesearch: Whether to combine multiple company searches
            countries: Optional list of country codes to filter by
            type_search: Search type ("search_word", "search_url", or "company")
            date_start: Start date for custom range (required if date_range_type is "custom")
            date_end: End date for custom range (required if date_range_type is "custom")
            timeout_secs: Override default timeout for this specific call
            **kwargs: Additional parameters to pass to the Apify actor
            
        Returns:
            Dict: The ads data from LinkedIn
        """
        
        # Transform competitor_name to lowercase for accountOwner if provided
        accountOwner = competitor_name.lower() if competitor_name else None
        
        # Prepare the Actor input based on script example
        if not date_type == "date_range_type":
            run_input = {
                "accountOwner": accountOwner,
                "combine_companies_onesearch": combine_companies_onesearch,
                "companies": companies or [],
                "date_range_type": date_range_type,
                "country": "ALL" if not countries else ",".join(countries),
                "proxyConfiguration": {
                    "useApifyProxy": True,
                    "apifyProxyGroups": []
                },
                "type_search": "search_word"
            }
        else:
            run_input = {
                "accountOwner": accountOwner,
                "combine_companies_onesearch": combine_companies_onesearch,
                "companies": companies or [],
                "date_start": date_start,
                "date_end": date_end,
                "country": "ALL" if not countries else ",".join(countries),
                "proxyConfiguration": {
                    "useApifyProxy": True,
                    "apifyProxyGroups": []
                },
                "type_search": "search_word"
            }
        
        # Update with any additional kwargs
        for key, value in kwargs.items():
            if key in run_input:
                run_input[key] = value
        
        logger.info(f"Running Apify actor for LinkedIn ads with input: {run_input}")
        
        try:
            # Use the provided timeout or the default one from the instance
            timeout = timeout_secs or self.timeout_secs
            logger.info(f"Using timeout of {timeout} seconds for Apify actor call")
            
            # Run the Actor and wait for it to finish with the specified timeout
            run = self.client.actor(self.actor_id).call(
                run_input=run_input,
                timeout_secs=timeout
            )
            
            # Fetch results from the dataset
            items = []
            for item in self.client.dataset(run["defaultDatasetId"]).iterate_items():
                items.append(item)
                
            return {
                "success": True,
                "count": len(items),
                "data": items,
                "run_id": run["id"],
                "dataset_id": run["defaultDatasetId"]
            }
            
        except Exception as e:
            logger.error(f"Error running Apify actor: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "data": []
            }

    async def save_to_minio(self, data: Dict[str, Any], business_id: str, competitor_name: str, file_name: str = "ads.json") -> Dict[str, Any]:
        """
        Save scraped ads data to MinIO
        
        Args:
            data: The scraped ads data
            business_id: The business ID
            competitor_name: The competitor name to use in the path
            file_name: The file name to save (default: ads.json)
            
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
            
            logger.info(f"Saved LinkedIn ads data to MinIO: {competitor_path}")
            return {
                "success": True,
                "path": competitor_path
            }
            
        except Exception as e:
            return self._handle_error(f"saving LinkedIn ads data to MinIO for {competitor_name}", e) 