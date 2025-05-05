import asyncio
import json
from app.services.business.competitive_analysis.linkedin.linkedin_ads_scraper_service import LinkedInAdsService

async def test_linkedin_ads_service():
    """
    Test script to fetch NVIDIA ads data from Brazil in the last 30 days.
    """
    try:
        # Initialize the service
        service = LinkedInAdsService()
        print("LinkedIn Ads Service initialized successfully")
        
        # Build URL for NVIDIA ads in Brazil
        print("\nBuilding search URL for NVIDIA ads in Brazil...")
        url = service.build_search_url(
            account_owner="nvidia",
            countries=["BR"],
            date_option="last-30-days"
        )
        print(f"Search URL created: {url}")
        
        # Fetch ads data
        print("\nFetching ads data from LinkedIn...")
        result = await service.fetch_ads_data(
            search_url=url,
            max_results=22  # We saw 22 ads in the search results
        )
        
        if result["success"]:
            print("\nSuccessfully fetched ads data!")
            print("\nAds data retrieved:")
            print(json.dumps(result["data"], indent=2))
        else:
            print(f"\nError fetching ads data: {result['error']}")
            
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    # Run the async test function
    asyncio.run(test_linkedin_ads_service()) 