from typing import List, Optional
from apify_client import ApifyClient
from datetime import datetime
from urllib.parse import urlencode
import os
from dotenv import load_dotenv

load_dotenv()

def build_search_url(company_url: str, date_option: str = "last-30-days", country: str = "ALL") -> str:
    """
    Build a LinkedIn Ad Library search URL for a company.
    
    Args:
        company_url: LinkedIn company URL
        date_option: Date range option (last-30-days, this-month, etc.)
        country: Country filter (ALL or specific country code)
        
    Returns:
        Formatted search URL
    """
    # Extract company ID from URL
    company_url_parts = company_url.split('/')
    company_id = company_url_parts[-1] if company_url_parts[-1] else company_url_parts[-2]
    
    # Base URL for LinkedIn Ad Library
    base_url = "https://www.linkedin.com/ad-library/search"
    
    # Query parameters
    params = {
        "advertiser": company_id,
        "dateRange": date_option,
        "geo": country
    }
    
    # Build and return URL
    return f"{base_url}?{urlencode(params)}"

def run_linkedin_ad_scraper(company_url: str, account_owner: str = None, limit: int = 5):
    """
    Run the LinkedIn Ad Library scraper using Apify.
    
    Args:
        company_url: LinkedIn company URL
        account_owner: Company name for the search
        limit: Maximum number of ads to scrape
        
    Returns:
        Results from the Apify actor
    """
    # Initialize the ApifyClient with your API token
    client = ApifyClient(os.environ.get("APIFY_API_TOKEN"))
    
    # Prepare the Actor input
    run_input = {
        "accountOwner": account_owner,
        "combine_companies_onesearch": False,
        "companies": [company_url],
        "date_range_type": "last-30-days",
        "limit": limit,
        "proxyConfiguration": {
            "useApifyProxy": True,
            "apifyProxyGroups": []
        },
        "type_search": "search_word"
    }
    
    # Run the Actor and wait for it to finish
    run = client.actor("31BPULiLZ42ca1mvj").call(run_input=run_input)
    
    # Return dataset ID
    return run["defaultDatasetId"]

# This code will only run when the script is executed directly, not when imported
if __name__ == "__main__":
    # Example usage
    client = ApifyClient(os.environ.get("APIFY_API_TOKEN", "apify_api_7EtKZkACvq2NRLILXodtcagd2Sm3ep1nXqAt"))
    
    # Prepare example Actor input
    run_input = {
        "accountOwner": "udemy",
        "combine_companies_onesearch": False,
        "companies": [
            "https://www.linkedin.com/company/udemy/"
        ],
        "date_range_type": "last-30-days",
        "limit": 5,
        "proxyConfiguration": {
            "useApifyProxy": True,
            "apifyProxyGroups": []
        },
        "type_search": "search_word"
    }
    
    # Run the Actor and wait for it to finish
    run = client.actor("31BPULiLZ42ca1mvj").call(run_input=run_input)
    
    # Fetch and print Actor results from the run's dataset
    for item in client.dataset(run["defaultDatasetId"]).iterate_items():
        print(item)