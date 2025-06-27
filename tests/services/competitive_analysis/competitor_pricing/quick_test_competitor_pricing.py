#!/usr/bin/env python3
"""
Quick test script for CompetitorPricingScraper
Run this script to quickly test the pricing scraper with various websites.
"""

import os
import sys
import asyncio
import json
from datetime import datetime
from dotenv import load_dotenv

# Add the application root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

# Load environment variables
load_dotenv()

from app.services.scrape.competitor_pricing_scraper import CompetitorPricingScraper

# Test URLs provided by the user
TEST_URLS = [
    "https://www.udemy.com/",
    "https://www.codecademy.com/", 
    "https://www.crehana.com/",
    "https://sambanova.ai/", 
    "https://platzi.com/"
]

async def test_single_website(scraper, url: str, detailed: bool = False):
    """Test pricing extraction for a single website"""
    print(f"\n{'='*60}")
    print(f"🔍 TESTING: {url}")
    print(f"{'='*60}")
    
    try:
        start_time = datetime.now()
        
        # Extract complete pricing info
        result = await scraper.extract_complete_pricing_info(url)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Print results
        print(f"⏱️  Execution time: {duration:.2f} seconds")
        print(f"🌐 Website URL: {result['website_url']}")
        print(f"📄 Pricing URLs found: {len(result['pricing_urls'])}")
        print(f"🛍️  Product URLs found: {len(result['products_urls'])}")
        print(f"📦 Total products extracted: {result['total_products']}")
        
        if detailed and result['pricing_urls']:
            print(f"\n📄 Pricing URLs:")
            for i, purl in enumerate(result['pricing_urls'][:5], 1):
                print(f"  {i}. {purl}")
            if len(result['pricing_urls']) > 5:
                print(f"  ... and {len(result['pricing_urls']) - 5} more")
        
        if detailed and result['products_urls']:
            print(f"\n🛍️  Product URLs:")
            for i, purl in enumerate(result['products_urls'][:5], 1):
                print(f"  {i}. {purl}")
            if len(result['products_urls']) > 5:
                print(f"  ... and {len(result['products_urls']) - 5} more")
        
        if result['products']:
            print(f"\n📦 Sample Products:")
            for i, product in enumerate(result['products'][:5], 1):
                name = product.get('name', 'N/A')[:50]
                price = product.get('price', 'N/A')
                currency = product.get('currency', '')
                source = product.get('source_url', '')
                
                print(f"  {i}. {name}")
                if price and price != 'N/A':
                    print(f"     💰 Price: {price} ({currency})")
                if detailed and source:
                    print(f"     🔗 Source: {source}")
                print()
        else:
            print("❌ No products found")
        
        if 'error' in result:
            print(f"⚠️  Error occurred: {result['error']}")
        
        return result
        
    except Exception as e:
        print(f"❌ Error testing {url}: {str(e)}")
        return None

async def test_url_finding_only(scraper, url: str):
    """Test only the URL finding functionality"""
    print(f"\n🔍 Testing URL finding for: {url}")
    
    try:
        result = await scraper.find_pricing_urls(url)
        
        print(f"📄 Found {len(result['pricing_urls'])} pricing URLs:")
        for purl in result['pricing_urls'][:3]:
            print(f"  - {purl}")
        
        print(f"🛍️  Found {len(result['products_urls'])} product URLs:")
        for purl in result['products_urls'][:3]:
            print(f"  - {purl}")
            
        return result
        
    except Exception as e:
        print(f"❌ Error finding URLs for {url}: {str(e)}")
        return None

async def interactive_test():
    """Interactive test mode"""
    print("🎯 Interactive Testing Mode")
    print("Enter a URL to test (or 'quit' to exit):")
    
    scraper = CompetitorPricingScraper(
        llm_provider="openai",
        llm_model="gpt-4o-mini",
        api_key=os.environ.get("OPENAI_API_KEY"),
        headless=True,
        verbose=False
    )
    
    while True:
        url = input("\nURL to test: ").strip()
        
        if url.lower() in ['quit', 'exit', 'q']:
            break
            
        if not url:
            continue
            
        if not url.startswith(('http://', 'https://')):
            url = f"https://{url}"
        
        choice = input("Full test (f) or URL finding only (u)? [f/u]: ").strip().lower()
        
        if choice == 'u':
            await test_url_finding_only(scraper, url)
        else:
            await test_single_website(scraper, url, detailed=True)

async def run_predefined_tests():
    """Run tests on predefined URLs"""
    print("🚀 Starting Competitor Pricing Scraper Tests")
    print("=" * 80)
    
    # Initialize scraper
    scraper = CompetitorPricingScraper(
        llm_provider="openai",
        llm_model="gpt-4o-mini",
        api_key=os.environ.get("OPENAI_API_KEY"),
        headless=True,
        verbose=False
    )
    
    results = {}
    
    # Test each URL
    for url in TEST_URLS:
        result = await test_single_website(scraper, url, detailed=False)
        results[url] = result
        
        # Small delay between requests
        await asyncio.sleep(2)
    
    # Summary
    print(f"\n{'='*80}")
    print("📊 SUMMARY RESULTS")
    print(f"{'='*80}")
    
    total_products = 0
    successful_sites = 0
    
    for url, result in results.items():
        if result and 'error' not in result:
            successful_sites += 1
            products_count = result['total_products']
            total_products += products_count
            status = f"✅ {products_count} products"
        else:
            status = "❌ Failed"
        
        site_name = url.replace('https://', '').replace('www.', '').split('/')[0]
        print(f"{site_name:20} | {status}")
    
    print(f"\n📈 Overall Statistics:")
    print(f"  - Successful sites: {successful_sites}/{len(TEST_URLS)}")
    print(f"  - Total products found: {total_products}")
    print(f"  - Average products per site: {total_products/successful_sites if successful_sites > 0 else 0:.1f}")

def save_results_to_file(results, filename="competitor_pricing_test_results.json"):
    """Save test results to a JSON file"""
    try:
        # Make results JSON serializable
        clean_results = {}
        for url, result in results.items():
            if result:
                clean_results[url] = {
                    'website_url': result.get('website_url', ''),
                    'pricing_urls_count': len(result.get('pricing_urls', [])),
                    'products_urls_count': len(result.get('products_urls', [])),
                    'total_products': result.get('total_products', 0),
                    'has_error': 'error' in result,
                    'timestamp': datetime.now().isoformat()
                }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(clean_results, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Results saved to {filename}")
        
    except Exception as e:
        print(f"❌ Error saving results: {str(e)}")

async def main():
    """Main function"""
    print("🎯 Competitor Pricing Scraper Test Suite")
    print("Choose testing mode:")
    print("1. Run predefined tests (recommended)")
    print("2. Interactive testing")
    print("3. Quick URL finding test")
    
    choice = input("\nEnter your choice [1/2/3]: ").strip()
    
    if choice == "2":
        await interactive_test()
    elif choice == "3":
        scraper = CompetitorPricingScraper(
            llm_provider="openai",
            llm_model="gpt-4o-mini",
            api_key=os.environ.get("OPENAI_API_KEY"),
            headless=True
        )
        for url in TEST_URLS[:3]:  # Test first 3 URLs only
            await test_url_finding_only(scraper, url)
    else:
        await run_predefined_tests()

if __name__ == "__main__":
    # Check if OpenAI API key is available
    if not os.environ.get("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY not found in environment variables.")
        print("Please set your OpenAI API key in your .env file or environment.")
        sys.exit(1)
    
    # Run the main function
    asyncio.run(main()) 