from typing import List, Optional, Dict
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
from app.services.scrape.linkedin_ads_scraper import LinkedInAdsScraper
from apify_client import ApifyClient

# Logger setup
logger = logging.getLogger(__name__)

class LinkedInAdsService:
    """Service for interacting with LinkedIn Ads Library through custom scraping."""
    
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
        llm_provider: str = "openai", 
        llm_model: str = "gpt-3.5-turbo",
        max_retries: int = 3,
        retry_delay: int = 5,
        headless: bool = True,
        verbose: bool = False,
        custom_selectors: Optional[Dict[str, str]] = None
    ):
        """
        Initialize the LinkedIn Ads Service.
        
        Args:
            llm_provider: The LLM provider to use
            llm_model: The model to use for extraction
            max_retries: Maximum number of retries for failed extractions
            retry_delay: Delay between retries in seconds
            headless: Whether to run the browser in headless mode
            verbose: Whether to output detailed logs
            custom_selectors: Custom CSS selectors to override defaults
        """
        load_dotenv()
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        self.openai_api_key = os.environ.get("OPENAI_API_KEY")
        
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        
        # Initialize the custom LinkedIn Ads scraper
        self.scraper = LinkedInAdsScraper(
            llm_provider=llm_provider,
            llm_model=llm_model,
            api_key=self.openai_api_key,
            headless=headless,
            verbose=verbose,
            max_retries=max_retries,
            retry_delay=retry_delay,
            custom_selectors=custom_selectors
        )
    
    def build_search_url(
        self,
        account_owner: Optional[str] = None,
        countries: Optional[List[str]] = None,
        date_option: str = "last-30-days",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        keyword: Optional[str] = None
    ) -> str:
        """
        Build the LinkedIn Ad Library search URL with the specified filters.
        
        Args:
            account_owner (str, optional): The company/account owner to search for
            countries (List[str], optional): List of country codes to filter by
            date_option (str): One of the DATE_OPTIONS values
            start_date (str, optional): Start date for custom range (YYYY-MM-DD)
            end_date (str, optional): End date for custom range (YYYY-MM-DD)
            keyword (str, optional): Keyword to search for in ads
            
        Returns:
            str: The complete search URL
        """
        return self.scraper.build_search_url(
            account_owner=account_owner,
            countries=countries,
            date_option=date_option,
            start_date=start_date,
            end_date=end_date,
            keyword=keyword
        )
        
    async def fetch_ads_data(
        self,
        search_url: str,
        max_results: Optional[int] = None,
        detect_selectors: bool = False
    ) -> Dict:
        """
        Fetch ads data from LinkedIn Ad Library using custom scraper.
        
        Args:
            search_url (str): The LinkedIn Ad Library search URL
            max_results (int, optional): Maximum number of results to return
            detect_selectors (bool): Whether to automatically detect optimal selectors
            
        Returns:
            Dict: The ads data from LinkedIn
        """
        if detect_selectors:
            try:
                logger.info("Detecting optimal selectors for LinkedIn Ad Library")
                updated_selectors = await self.scraper.detect_optimal_selectors(search_url)
                if updated_selectors:
                    logger.info(f"Updated selectors for LinkedIn Ad Library: {updated_selectors}")
                    self.scraper.selectors = updated_selectors
            except Exception as e:
                logger.error(f"Error detecting selectors: {str(e)}")
        
        return await self.scraper.extract_ads_data(search_url, max_results)
    
    async def extract_competitor_ads_data(
        self,
        business_idea_id: str,
        db: Session,
        date_option: str = "last-30-days",
        max_results_per_competitor: int = 100,
        countries: Optional[List[str]] = None,
        detect_selectors: bool = True
    ) -> Dict:
        """
        Extract LinkedIn Ads data for all competitors of a business idea and save to MinIO.
        
        Args:
            business_idea_id: ID of the business idea
            db: Database session
            date_option: Time range for ads (last-30-days, this-month, etc.)
            max_results_per_competitor: Maximum number of ad results per competitor
            countries: Optional list of country codes to filter by
            detect_selectors: Whether to automatically detect optimal selectors
            
        Returns:
            Dict: Summary of the extraction process
        """
        return await self.scraper.extract_competitor_ads_data(
            business_idea_id=business_idea_id,
            db=db,
            date_option=date_option,
            max_results_per_competitor=max_results_per_competitor,
            countries=countries,
            detect_selectors=detect_selectors
        )

class ApifyLinkedInAdsService:
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
        actor_id: str = "31BPULiLZ42ca1mvj"
    ):
        """
        Initialize the Apify LinkedIn Ads Service.
        
        Args:
            apify_api_token: The Apify API token (will use env var if not provided)
            max_results: Default maximum number of results to fetch
            actor_id: The Apify actor ID for LinkedIn ads
        """
        load_dotenv()
        self.apify_api_token = apify_api_token or os.environ.get("APIFY_API_TOKEN")
        
        if not self.apify_api_token:
            raise ValueError("APIFY_API_TOKEN environment variable is not set and no token provided")
        
        self.client = ApifyClient(self.apify_api_token)
        self.actor_id = actor_id
        self.max_results = max_results
    
    def build_search_url(
        self,
        account_owner: Optional[str] = None,
        countries: Optional[List[str]] = None,
        date_option: str = "last-30-days",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        keyword: Optional[str] = None
    ) -> str:
        """
        Build the LinkedIn Ad Library search URL with the specified filters.
        
        Args:
            account_owner (str, optional): The company/account owner to search for
            countries (List[str], optional): List of country codes to filter by
            date_option (str): One of the DATE_OPTIONS values
            start_date (str, optional): Start date for custom range (YYYY-MM-DD)
            end_date (str, optional): End date for custom range (YYYY-MM-DD)
            keyword (str, optional): Keyword to search for in ads
            
        Returns:
            str: The complete search URL
        """
        query_params = {}
        
        if account_owner:
            query_params["accountOwner"] = account_owner
            
        if keyword:
            query_params["keyword"] = keyword
            
        if countries:
            query_params["countries"] = ",".join(countries)
            
        query_params["dateOption"] = date_option
        
        if date_option == "custom" and start_date and end_date:
            query_params["startDate"] = start_date
            query_params["endDate"] = end_date
            
        url = f"{self.BASE_URL}?{urlencode(query_params)}"
        return url
        
    async def fetch_ads_data(
        self,
        search_url: str,
        max_results: Optional[int] = None,
        **kwargs
    ) -> Dict:
        """
        Fetch ads data from LinkedIn Ad Library using Apify actor.
        
        Args:
            search_url (str): The LinkedIn Ad Library search URL
            max_results (int, optional): Maximum number of results to return
            **kwargs: Additional parameters to pass to the Apify actor
            
        Returns:
            Dict: The ads data from LinkedIn
        """
        limit = max_results or self.max_results
        
        # Prepare the Actor input
        run_input = {
            "proxyConfiguration": {
                "useApifyProxy": True,
                "apifyProxyGroups": [],
            },
            "limit": limit,
            "type_search": "search_url",
            "search_url": search_url,
            # Default values for other parameters
            "accountOwner": None,
            "word_search": None,
            "date_range_type": "last-30-days",
            "date_start": None,
            "date_end": None,
            "country": "ALL",
            "combine_companies_onesearch": False,
            "companies": [],
            "company_word_search": None,
            "company_date_range_type": "last-30-days",
            "company_date_start": None,
            "company_date_end": None,
            "company_country": "ALL",
        }
        
        # Update with any additional kwargs
        for key, value in kwargs.items():
            if key in run_input:
                run_input[key] = value
        
        logger.info(f"Running Apify actor for LinkedIn ads with URL: {search_url}")
        
        try:
            # Run the Actor and wait for it to finish
            run = self.client.actor(self.actor_id).call(run_input=run_input)
            
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
    
    async def extract_competitor_ads_data(
        self,
        business_idea_id: str,
        db: Session,
        date_option: str = "last-30-days",
        max_results_per_competitor: int = 100,
        countries: Optional[List[str]] = None,
        **kwargs
    ) -> Dict:
        """
        Extract LinkedIn Ads data for all competitors of a business idea and save to MinIO.
        
        Args:
            business_idea_id: ID of the business idea
            db: Database session
            date_option: Time range for ads (last-30-days, this-month, etc.)
            max_results_per_competitor: Maximum number of ad results per competitor
            countries: Optional list of country codes to filter by
            **kwargs: Additional parameters to pass to the Apify actor
            
        Returns:
            Dict: Summary of the extraction process
        """
        # Get competitors from database
        competitors = db.query(Competitor).filter(
            Competitor.business_idea_id == business_idea_id
        ).all()
        
        if not competitors:
            logger.warning(f"No competitors found for business idea ID: {business_idea_id}")
            return {
                "success": False,
                "error": "No competitors found",
                "data": []
            }
        
        results = []
        
        # Initialize MinIO service for storing results
        minio_service = MinioService()
        bucket_name = "linkedin-ads"
        
        for competitor in competitors:
            logger.info(f"Fetching LinkedIn ads for competitor: {competitor.name}")
            
            # Get company LinkedIn URL or build search term
            if competitor.linkedin_url:
                company_url = competitor.linkedin_url
                # Run with company URL
                run_input = {
                    "combine_companies_onesearch": False,
                    "companies": [company_url],
                    "company_date_range_type": date_option,
                    "company_country": "ALL" if not countries else ",".join(countries),
                }
                
                if date_option == "custom" and "company_date_start" in kwargs and "company_date_end" in kwargs:
                    run_input["company_date_start"] = kwargs.get("company_date_start")
                    run_input["company_date_end"] = kwargs.get("company_date_end")
                
                ads_data = await self.fetch_ads_data(
                    search_url="",  # Not used in this mode
                    max_results=max_results_per_competitor,
                    type_search="company",
                    **run_input,
                    **kwargs
                )
            else:
                # Use the competitor name as account owner
                search_url = self.build_search_url(
                    account_owner=competitor.name,
                    countries=countries,
                    date_option=date_option,
                    start_date=kwargs.get("date_start"),
                    end_date=kwargs.get("date_end")
                )
                
                ads_data = await self.fetch_ads_data(
                    search_url=search_url,
                    max_results=max_results_per_competitor,
                    **kwargs
                )
            
            if ads_data["success"] and ads_data["count"] > 0:
                # Save to MinIO
                file_key = f"{business_idea_id}/{competitor.id}/{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
                
                minio_service.put_object(
                    bucket_name=bucket_name,
                    object_name=file_key,
                    data=json.dumps(ads_data).encode('utf-8'),
                    content_type="application/json"
                )
                
                ads_data["minio_path"] = f"{bucket_name}/{file_key}"
            
            results.append({
                "competitor_id": competitor.id,
                "competitor_name": competitor.name,
                "result": ads_data
            })
        
        return {
            "success": True,
            "count": len(results),
            "data": results
        } 