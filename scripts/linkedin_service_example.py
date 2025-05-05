import asyncio
import os
import sys
import json
from dotenv import load_dotenv

# Add the project root directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.business.competitive_analysis.linkedin.linkedin_ads_scraper_service import ApifyLinkedInAdsService

async def main():
    """Example of using the updated ApifyLinkedInAdsService."""
    load_dotenv()
    
    # Initialize the service (will use APIFY_API_TOKEN from .env file)
    service = ApifyLinkedInAdsService(max_results=5)
    
    print("Example 1: Search by company URL")
    results1 = await service.fetch_ads_data(
        competitor_name="Udemy",
        companies=["https://www.linkedin.com/company/udemy/"],
        date_range_type="last-30-days",
        limit=5,
        combine_companies_onesearch=False,
        type_search="company"
    )
    
    print(f"Found {results1['count']} ads")
    
    # Save results to a file for inspection
    with open("udemy_ads_results.json", "w") as f:
        json.dump(results1, f, indent=2)
    
    print("\nExample 2: Search by competitor name")
    results2 = await service.fetch_ads_data(
        competitor_name="udemy",
        date_range_type="last-30-days",
        limit=5,
        type_search="search_word"
    )
    
    print(f"Found {results2['count']} ads")
    
    # Show first ad details
    if results2["count"] > 0:
        first_ad = results2["data"][0]
        print("\nFirst ad details:")
        print(f"Type: {first_ad.get('ad_type')}")
        print(f"Headline: {first_ad.get('headline')}")
        print(f"Advertiser: {first_ad.get('advertiser_name')}")
        print(f"CTA: {first_ad.get('CTA_name')}")
    
    print("\nExample 3: Testing different date range")
    results3 = await service.fetch_ads_data(
        competitor_name="udemy",
        date_range_type="this-month",
        limit=3,
        type_search="search_word"
    )
    
    print(f"Found {results3['count']} ads")

if __name__ == "__main__":
    asyncio.run(main()) 