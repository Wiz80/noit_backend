import os
import sys
import pytest
import asyncio
from decimal import Decimal
from dotenv import load_dotenv

# Add the application root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

# Load environment variables from .env file
load_dotenv()

from app.services.scrape.competitor_pricing_scraper import CompetitorPricingScraper, extract_competitor_pricing

class TestCompetitorPricingScraper:
    """Test suite for CompetitorPricingScraper"""

    @pytest.fixture
    def scraper(self):
        """Create a scraper instance for testing"""
        return CompetitorPricingScraper(
            llm_provider="openai",
            llm_model="gpt-4o-mini",
            api_key=os.environ.get("OPENAI_API_KEY"),
            headless=True,
            verbose=False
        )

    @pytest.mark.asyncio
    async def test_udemy_pricing_extraction(self, scraper):
        """Test pricing extraction from Udemy"""
        print("\n🧪 Testing Udemy pricing extraction...")
        
        url = "https://www.udemy.com/"
        result = await scraper.extract_complete_pricing_info(url)
        
        # Print results for debugging
        print(f"📊 Udemy Results:")
        print(f"  - Website URL: {result['website_url']}")
        print(f"  - Pricing URLs found: {len(result['pricing_urls'])}")
        print(f"  - Product URLs found: {len(result['products_urls'])}")
        print(f"  - Total products: {result['total_products']}")
        
        if result['products']:
            print(f"  - Sample products:")
            for i, product in enumerate(result['products'][:3]):
                print(f"    {i+1}. {product.get('name', 'N/A')} - {product.get('price', 'N/A')}")
        
        # Assertions
        assert result is not None
        assert isinstance(result, dict)
        assert result['website_url'] == url
        assert isinstance(result['pricing_urls'], list)
        assert isinstance(result['products_urls'], list)
        assert isinstance(result['products'], list)
        assert result['total_products'] >= 0

    @pytest.mark.asyncio
    async def test_codecademy_pricing_extraction(self, scraper):
        """Test pricing extraction from Codecademy"""
        print("\n🧪 Testing Codecademy pricing extraction...")
        
        url = "https://www.codecademy.com/"
        result = await scraper.extract_complete_pricing_info(url)
        
        # Print results for debugging
        print(f"📊 Codecademy Results:")
        print(f"  - Website URL: {result['website_url']}")
        print(f"  - Pricing URLs found: {len(result['pricing_urls'])}")
        print(f"  - Product URLs found: {len(result['products_urls'])}")
        print(f"  - Total products: {result['total_products']}")
        
        if result['products']:
            print(f"  - Sample products:")
            for i, product in enumerate(result['products'][:3]):
                print(f"    {i+1}. {product.get('name', 'N/A')} - {product.get('price', 'N/A')}")
        
        # Assertions
        assert result is not None
        assert isinstance(result, dict)
        assert result['website_url'] == url
        assert isinstance(result['pricing_urls'], list)
        assert isinstance(result['products_urls'], list)
        assert isinstance(result['products'], list)
        assert result['total_products'] >= 0

    @pytest.mark.asyncio
    async def test_crehana_pricing_extraction(self, scraper):
        """Test pricing extraction from Crehana"""
        print("\n🧪 Testing Crehana pricing extraction...")
        
        url = "https://www.crehana.com/"
        result = await scraper.extract_complete_pricing_info(url)
        
        # Print results for debugging
        print(f"📊 Crehana Results:")
        print(f"  - Website URL: {result['website_url']}")
        print(f"  - Pricing URLs found: {len(result['pricing_urls'])}")
        print(f"  - Product URLs found: {len(result['products_urls'])}")
        print(f"  - Total products: {result['total_products']}")
        
        if result['products']:
            print(f"  - Sample products:")
            for i, product in enumerate(result['products'][:3]):
                print(f"    {i+1}. {product.get('name', 'N/A')} - {product.get('price', 'N/A')}")
        
        # Assertions
        assert result is not None
        assert isinstance(result, dict)
        assert result['website_url'] == url
        assert isinstance(result['pricing_urls'], list)
        assert isinstance(result['products_urls'], list)
        assert isinstance(result['products'], list)
        assert result['total_products'] >= 0

    @pytest.mark.asyncio
    async def test_sambanova_pricing_extraction(self, scraper):
        """Test pricing extraction from SambaNova"""
        print("\n🧪 Testing SambaNova pricing extraction...")
        
        url = "https://sambanova.ai/"
        result = await scraper.extract_complete_pricing_info(url)
        
        # Print results for debugging
        print(f"📊 SambaNova Results:")
        print(f"  - Website URL: {result['website_url']}")
        print(f"  - Pricing URLs found: {len(result['pricing_urls'])}")
        print(f"  - Product URLs found: {len(result['products_urls'])}")
        print(f"  - Total products: {result['total_products']}")
        
        if result['products']:
            print(f"  - Sample products:")
            for i, product in enumerate(result['products'][:3]):
                print(f"    {i+1}. {product.get('name', 'N/A')} - {product.get('price', 'N/A')}")
        
        # Assertions
        assert result is not None
        assert isinstance(result, dict)
        assert result['website_url'] == url
        assert isinstance(result['pricing_urls'], list)
        assert isinstance(result['products_urls'], list)
        assert isinstance(result['products'], list)
        assert result['total_products'] >= 0

    @pytest.mark.asyncio
    async def test_platzi_pricing_extraction(self, scraper):
        """Test pricing extraction from Platzi"""
        print("\n🧪 Testing Platzi pricing extraction...")
        
        url = "https://platzi.com/"
        result = await scraper.extract_complete_pricing_info(url)
        
        # Print results for debugging
        print(f"📊 Platzi Results:")
        print(f"  - Website URL: {result['website_url']}")
        print(f"  - Pricing URLs found: {len(result['pricing_urls'])}")
        print(f"  - Product URLs found: {len(result['products_urls'])}")
        print(f"  - Total products: {result['total_products']}")
        
        if result['products']:
            print(f"  - Sample products:")
            for i, product in enumerate(result['products'][:3]):
                print(f"    {i+1}. {product.get('name', 'N/A')} - {product.get('price', 'N/A')}")
        
        # Assertions
        assert result is not None
        assert isinstance(result, dict)
        assert result['website_url'] == url
        assert isinstance(result['pricing_urls'], list)
        assert isinstance(result['products_urls'], list)
        assert isinstance(result['products'], list)
        assert result['total_products'] >= 0

    @pytest.mark.asyncio
    async def test_find_pricing_urls(self, scraper):
        """Test finding pricing URLs functionality"""
        print("\n🧪 Testing pricing URL detection...")
        
        # Test with a known website
        url = "https://www.codecademy.com/"
        result = await scraper.find_pricing_urls(url)
        
        print(f"📊 URL Detection Results for {url}:")
        print(f"  - Pricing URLs: {result['pricing_urls']}")
        print(f"  - Product URLs: {result['products_urls']}")
        
        # Assertions
        assert result is not None
        assert isinstance(result, dict)
        assert 'pricing_urls' in result
        assert 'products_urls' in result
        assert isinstance(result['pricing_urls'], list)
        assert isinstance(result['products_urls'], list)

    @pytest.mark.asyncio
    async def test_batch_extraction(self, scraper):
        """Test batch extraction of pricing information from multiple websites"""
        print("\n🧪 Testing batch pricing extraction...")
        
        websites = [
            "https://www.udemy.com/",
            "https://www.codecademy.com/",
            "https://sambanova.ai/"
        ]
        
        results = {}
        for website in websites:
            try:
                print(f"  Processing: {website}")
                result = await scraper.extract_complete_pricing_info(website)
                results[website] = result
                print(f"  ✅ Success - Found {result['total_products']} products")
            except Exception as e:
                print(f"  ❌ Error: {str(e)}")
                results[website] = {"error": str(e)}
        
        # Print summary
        print(f"\n📊 Batch Results Summary:")
        for website, result in results.items():
            if 'error' not in result:
                print(f"  - {website}: {result['total_products']} products")
            else:
                print(f"  - {website}: Error - {result['error']}")
        
        # Assertions
        assert len(results) == len(websites)
        for website in websites:
            assert website in results

    def test_price_parsing(self, scraper):
        """Test price parsing functionality"""
        print("\n🧪 Testing price parsing...")
        
        test_cases = [
            ("$50.000", "COP"),  # Colombian format
            ("USD $100", "USD"),
            ("€25.99", "EUR"),
            ("$1.500.000", "COP"),  # Colombian millions
            ("$19.99 USD", "USD"),
            ("COP 50,000", "COP"),
            ("Free", None),
            ("", None)
        ]
        
        for price_text, expected_currency in test_cases:
            price, currency, is_range, min_price, max_price = scraper._parse_price(price_text)
            print(f"  Input: '{price_text}' -> Price: {price}, Currency: {currency}")
            
            if expected_currency:
                assert currency == expected_currency, f"Expected {expected_currency}, got {currency} for '{price_text}'"

    def test_url_normalization(self, scraper):
        """Test URL normalization functionality"""
        print("\n🧪 Testing URL normalization...")
        
        test_cases = [
            ("www.example.com", "https://www.example.com"),
            ("http://example.com", "http://example.com"),
            ("https://example.com", "https://example.com"),
            ("", ""),
            ("platzi.com", "https://platzi.com")
        ]
        
        for input_url, expected_output in test_cases:
            normalized = scraper._normalize_url(input_url)
            print(f"  Input: '{input_url}' -> Output: '{normalized}'")
            assert normalized == expected_output, f"Failed for {input_url}, got {normalized}"

    @pytest.mark.asyncio
    async def test_utility_function(self):
        """Test the standalone utility function"""
        print("\n🧪 Testing utility function...")
        
        result = await extract_competitor_pricing(
            website_url="https://www.codecademy.com/",
            llm_provider="openai",
            llm_model="gpt-4o-mini",
            api_key=os.environ.get("OPENAI_API_KEY")
        )
        
        print(f"📊 Utility Function Results:")
        print(f"  - Total products: {result['total_products']}")
        print(f"  - Pricing URLs: {len(result['pricing_urls'])}")
        
        # Assertions
        assert result is not None
        assert isinstance(result, dict)
        assert 'website_url' in result
        assert 'products' in result


# Direct execution functions for manual testing
async def run_full_test_suite():
    """Run all tests manually"""
    print("🚀 Starting Competitor Pricing Scraper Test Suite")
    print("=" * 60)
    
    scraper = CompetitorPricingScraper(
        llm_provider="openai",
        llm_model="gpt-4o-mini",
        api_key=os.environ.get("OPENAI_API_KEY"),
        headless=True,
        verbose=False
    )
    
    test_instance = TestCompetitorPricingScraper()
    
    # Run individual tests
    try:
        await test_instance.test_udemy_pricing_extraction(scraper)
        await test_instance.test_codecademy_pricing_extraction(scraper)
        await test_instance.test_crehana_pricing_extraction(scraper)
        await test_instance.test_sambanova_pricing_extraction(scraper)
        await test_instance.test_platzi_pricing_extraction(scraper)
        await test_instance.test_find_pricing_urls(scraper)
        await test_instance.test_batch_extraction(scraper)
        test_instance.test_price_parsing(scraper)
        test_instance.test_url_normalization(scraper)
        await test_instance.test_utility_function()
        
        print("\n✅ All tests completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {str(e)}")


if __name__ == "__main__":
    # Run the tests directly when script is executed
    asyncio.run(run_full_test_suite()) 