import os
import sys
import pytest
import asyncio
from dotenv import load_dotenv

# Add the application root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Load environment variables from .env file
load_dotenv()

from app.services.business.competitive_analysis.website_social_scraper import WebsiteSocialMediaScraper

@pytest.mark.asyncio
async def test_extract_social_media():
    """Test extracting social media from a website with known social media links."""
    
    # Initialize scraper
    # Use a shorter-context model to save tokens during testing
    scraper = WebsiteSocialMediaScraper(
        llm_provider="openai",
        llm_model="gpt-3.5-turbo",
        api_key=os.environ.get("OPENAI_API_KEY"),
        headless=True
    )
    
    # Test extraction with a website that has multiple social media links
    # Using HubSpot as an example since they have many social links
    result = await scraper.extract_social_media("https://www.hubspot.com")
    
    # Print result for debugging
    print("Extracted social media data:")
    print(result)
    
    # Basic assertions
    assert result is not None
    assert isinstance(result, dict)
    
    # Check that we found at least some social platforms
    found_platforms = sum(1 for platform in result.values() if platform['url'])
    assert found_platforms > 0, "No social media platforms were found"
    
    # Test with a website that might have fewer social links
    result2 = await scraper.extract_social_media("https://www.example.com")
    
    # Print result for debugging
    print("\nExtracted social media data from example.com:")
    print(result2)
    
    # Ensure the function handles websites without social media gracefully
    assert result2 is not None
    assert isinstance(result2, dict)

@pytest.mark.asyncio
async def test_batch_extraction():
    """Test batch extraction of social media from multiple websites."""
    
    # Initialize scraper
    scraper = WebsiteSocialMediaScraper(
        llm_provider="openai",
        llm_model="gpt-3.5-turbo",
        api_key=os.environ.get("OPENAI_API_KEY"),
        headless=True
    )
    
    # Test batch extraction with multiple websites
    websites = [
        "https://www.hubspot.com",
        "https://www.github.com",
        "https://www.example.com"  # Likely has no social media
    ]
    
    results = await scraper.batch_extract_social_media(websites)
    
    # Print results for debugging
    print("\nBatch extraction results:")
    for website, result in results.items():
        print(f"\n{website}:")
        print(result)
    
    # Basic assertions
    assert results is not None
    assert isinstance(results, dict)
    assert len(results) == len(websites)
    
    # Check that all websites are in the results
    for website in websites:
        assert website in results

@pytest.mark.asyncio
async def test_normalize_url():
    """Test URL normalization functionality."""
    
    # Initialize scraper
    scraper = WebsiteSocialMediaScraper()
    
    # Test cases
    test_cases = [
        ("www.example.com", "https://www.example.com"),
        ("http://example.com", "http://example.com"),
        ("https://example.com", "https://example.com"),
        ("", ""),
        (None, "")
    ]
    
    for input_url, expected_output in test_cases:
        normalized = scraper._normalize_url(input_url)
        assert normalized == expected_output, f"Failed for {input_url}, got {normalized}"

if __name__ == "__main__":
    # Run the tests directly when script is executed
    asyncio.run(test_extract_social_media())
    print("\n" + "="*50 + "\n")
    asyncio.run(test_batch_extraction())
    print("\n" + "="*50 + "\n")
    asyncio.run(test_normalize_url()) 