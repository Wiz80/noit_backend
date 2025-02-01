import json
import os
import requests
from typing import List, Dict
import logging
from datetime import datetime
import time
from uuid import uuid4
import os
from dotenv import load_dotenv  
from utils.load_data import load_competitor_data

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KestraScrapeRequester:
    """
    Handles sending scraping requests to Kestra webhook for competitor websites
    """
    
    def __init__(self, kestra_host: str = "http://localhost:8084"):
        """
        Initialize the requester
        
        Args:
            kestra_host: Base URL for Kestra instance
        """
        self.kestra_host = kestra_host
        self.webhook_key = os.getenv("KESTRA_WEBHOOK_KEY")  # From your Kestra flow
        self.namespace = "infinity_lab"
        self.flow_id = "web_scraper"

    def _format_webhook_request(self, website_url: str, company_name: str) -> Dict:
        """
        Format the request payload for Kestra webhook
        
        Args:
            website_url: URL to scrape
            company_name: Name of the company (for storage config)
            
        Returns:
            Dictionary with formatted request payload
        """
        # Format storage config for competitor data
        storage_config = {
            "competitor_analysis": company_name.lower().replace(" ", "_")
        }

        return {
            "inputs": {
                "base_url": website_url,
                "search_url": website_url,
                "extract_type": "/",  # Root extraction
                "minio_location_storage_config": json.dumps(storage_config),
                "pagination": "False",
                "provided_urls": [],
                "chatbot_id": None,
                "conversation_id": None
            }
        }

    def _send_webhook_request(self, payload: Dict, company_name: str) -> bool:
        """
        Send webhook request to Kestra
        
        Args:
            payload: Formatted request payload
            company_name: Company name for logging
            
        Returns:
            Boolean indicating success
        """
        webhook_url = f"{self.kestra_host}/api/v1/executions/webhook/{self.namespace}/{self.flow_id}/{self.webhook_key}"
        
        payload = {
            "id": str(uuid4()),
            "namespace": "infinity_lab",
            "flowId": "web_scraper",
            "inputs": {**payload['inputs']},
        }
        try:
            response = requests.post(webhook_url, json=payload)
            
            if response.status_code in [200, 201]:
                logger.info(f"Successfully triggered scraping for {company_name}")
                return True
            else:
                logger.error(f"Error triggering scraping for {company_name}. Status: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Exception sending webhook for {company_name}: {str(e)}")
            return False

    def process_competitors(self, delay_seconds: int = 5):
        """
        Process all competitors and send scraping requests
        
        Args:
            json_path: Path to competitor analysis JSON
            delay_seconds: Delay between requests to avoid overwhelming the server
        """
        competitors = load_competitor_data()
        logger.info(f"Found {len(competitors)} competitors to process")
        
        for competitor in competitors:
            if not competitor.get('website'):
                logger.warning(f"No website found for competitor: {competitor.get('full_name', 'Unknown')}")
                continue
                
            # Format and send request
            payload = self._format_webhook_request(
                competitor['website'], 
                competitor['full_name']
            )
            
            success = self._send_webhook_request(payload, competitor['full_name'])
            
            if success:
                logger.info(f"Waiting {delay_seconds} seconds before next request...")
                time.sleep(delay_seconds)

def main():
    
    # Initialize and run the requester
    requester = KestraScrapeRequester()
    requester.process_competitors()

if __name__ == "__main__":
    main()