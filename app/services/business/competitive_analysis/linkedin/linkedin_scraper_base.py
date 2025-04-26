from abc import ABC, abstractmethod
import os
import logging
from apify_client import ApifyClient
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LinkedInScraperBase(ABC):
    """Base class for LinkedIn scrapers using Apify services"""
    
    def __init__(self):
        # Load environment variables
        load_dotenv()
        
        # Initialize the ApifyClient with API token
        self.apify_token = os.getenv("APIFY_API_KEY")
        if not self.apify_token:
            raise ValueError("APIFY_API_KEY environment variable is not set")
        
        self.client = ApifyClient(self.apify_token)
        
    @abstractmethod
    async def scrape(self, **kwargs):
        """
        Abstract method that should be implemented by subclasses
        to perform the specific scraping operation
        """
        pass
        
    @abstractmethod
    async def save_to_minio(self, data, business_id, competitor_id, file_name):
        """
        Abstract method that should be implemented by subclasses
        to save scraped data to MinIO
        """
        pass
        
    def _handle_error(self, operation, error):
        """Helper method to handle errors consistently"""
        error_msg = f"Error during {operation}: {str(error)}"
        logger.error(error_msg)
        return {"success": False, "error": error_msg} 