import asyncio
import os
import sys
from dotenv import load_dotenv
from uuid import uuid4

# Add the project root to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.controllers.competitor_analysis_controller import CompetitorAnalysisController

load_dotenv()

async def test_instagram_scraper():
    """
    Test function for the Instagram scraper.
    This function tests the CompetitorAnalysisController's ability to analyze Instagram competitors.
    """
    # Generate a test business ID
    test_business_id = str(uuid4())
    print(f"Testing with business ID: {test_business_id}")
    
    # Initialize the controller
    controller = CompetitorAnalysisController(test_business_id)
    
    # Test usernames - replace with actual Instagram usernames for testing
    test_usernames = ["nike", "adidas"]
    
    print(f"Starting analysis for usernames: {test_usernames}")
    
    # Test analyzing a single competitor
    for username in test_usernames:
        print(f"\nAnalyzing competitor: {username}")
        result = await controller.analyze_instagram_competitor(
            username=username,
            results_limit=3,  # Limit to 3 posts for testing
            max_comments=2    # Limit to 2 comments per post for testing
        )
        
        print(f"Analysis result: {result}")
    
    # Test analyzing multiple competitors
    print("\nAnalyzing multiple competitors")
    results = await controller.analyze_multiple_instagram_competitors(
        usernames=test_usernames,
        results_limit=2,
        max_comments=1
    )
    
    print(f"Multiple analysis results: {results}")
    
    print("\nTest completed successfully!")

if __name__ == "__main__":
    # Run the test
    asyncio.run(test_instagram_scraper()) 