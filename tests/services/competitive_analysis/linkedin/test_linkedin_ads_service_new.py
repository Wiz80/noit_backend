import os
import json
import pytest

# pytest-asyncio is required for async tests
pytestmark = pytest.mark.asyncio

from app.services.business.competitive_analysis.linkedin.linkedin_ads_service import LinkedInAdsService


@pytest.mark.skipif(
    os.getenv("SKIP_LINKEDIN_SCRAPER_TEST") == "1",  # Allow skipping via env var
    reason="LinkedIn Ads scraper integration test skipped via environment variable."
)
async def test_linkedin_ads_service_with_selector_detection():
    """Integration test for LinkedInAdsService using automatic selector detection.

    The test builds a LinkedIn Ad Library search URL for NVIDIA ads in Brazil in
    the last 30 days, detects optimal CSS selectors, and tries to fetch a small
    sample of ads.  We assert that the extraction succeeded and returned at
    least one ad.

    NOTE: This test performs live scraping and therefore requires:
        1. A stable internet connection.
        2. Playwright browsers installed (run `playwright install chromium`).
        3. A valid `OPENAI_API_KEY` in the environment (.env file) for the
           ScrapeGraphAI fallback.

    You can skip this test by setting the environment variable
    `SKIP_LINKEDIN_SCRAPER_TEST=1`.
    """

    # Initialize the service with verbose logging and reduced retries for speed
    service = LinkedInAdsService(
        verbose=True,
        headless=True,  # Use headless mode for automated testing
        max_retries=1,  # Keep retries low to reduce test time
    )

    # Build a search URL for NVIDIA ads in Brazil (last 30 days)
    search_url = service.build_search_url(
        account_owner="nvidia",
        countries=["BR"],
        date_option="last-30-days",
    )

    # Fetch a small sample of ads with automatic selector detection enabled
    result = await service.fetch_ads_data(
        search_url=search_url,
        max_results=5,
        detect_selectors=True,
    )

    # Basic assertions – ensure the scraper reports success and returns data
    assert result["success"] is True, f"Scraper did not succeed: {result.get('error')}"
    assert isinstance(result["data"], list), "Expected 'data' field to be a list"
    assert len(result["data"]) > 0, "No ads were extracted from the search page"

    # Optionally, print the first ad for debugging (comment out in CI)
    print("First ad extracted:\n", json.dumps(result["data"][0], indent=2, ensure_ascii=False)) 