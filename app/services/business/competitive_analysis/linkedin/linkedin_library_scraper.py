from typing import List, Optional
from apify_client import ApifyClient
from datetime import datetime
from urllib.parse import urlencode
import os
from dotenv import load_dotenv

load_dotenv()

def build_search_url(
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
    # Validate date option
    DATE_OPTIONS = ["last-30-days", "this-month", "this-year", "last-year", "custom"]
    if date_option not in DATE_OPTIONS:
        raise ValueError(f"Invalid date_option. Must be one of {DATE_OPTIONS}")
        
    # For custom date range, validate dates
    if date_option == "custom":
        if not (start_date and end_date):
            raise ValueError("start_date and end_date are required for custom date range")
        try:
            datetime.strptime(start_date, "%Y-%m-%d")
            datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Dates must be in YYYY-MM-DD format")
    
    # Build query parameters
    params = {}
    
    if account_owner:
        params["accountOwner"] = account_owner
        
    if countries:
        params["countries"] = ",".join(countries)
        
    params["dateOption"] = date_option
    
    if date_option == "custom":
        params["startDate"] = start_date
        params["endDate"] = end_date
        
    if keyword:
        params["keyword"] = keyword
    
    # Build the final URL
    BASE_URL = "https://www.linkedin.com/ad-library/search"
    url = f"{BASE_URL}?{urlencode(params)}"
    return url

def fetch_linkedin_ads_example(account_owner: str = "nvidia", country: str = "BR"):
    """
    Example function to fetch LinkedIn ads data using Apify.
    Only runs when explicitly called, not on module import.
    
    Args:
        account_owner: The LinkedIn company/account owner to search for
        country: The country code to filter by
        
    Returns:
        The scraped data items
    """
    # Initialize the ApifyClient with your API token
    client = ApifyClient(os.getenv("APIFY_API_KEY"))

    # Prepare the Actor input
    run_input = {
        "proxyConfiguration": {
            "useApifyProxy": True,
            "apifyProxyGroups": [],
        },
        "limit": 5,
        "type_search": "search_url",
        "search_url": f"https://www.linkedin.com/ad-library/search?accountOwner={account_owner}&countries={country}&dateOption=last-30-days",
        "accountOwner": account_owner,  # Ensure this is a string, not None
        "word_search": None,
        "date_range_type": "last-30-days",
        "date_start": None,
        "date_end": None,
        "country": "ALL",
        "combine_companies_onesearch": False,
        "companies": [f"https://www.linkedin.com/company/{account_owner}"],
        "company_word_search": None,
        "company_date_range_type": "last-30-days",
        "company_date_start": None,
        "company_date_end": None,
        "company_country": "ALL",
    }

    # Run the Actor and wait for it to finish
    run = client.actor("31BPULiLZ42ca1mvj").call(run_input=run_input)

    # Fetch and return Actor results from the run's dataset
    items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    return items

# Este código ahora solo se ejecutará si llamas explícitamente a la función fetch_linkedin_ads_example
