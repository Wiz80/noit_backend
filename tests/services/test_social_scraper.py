import asyncio
import json
from app.services.scrape.website_social_scraper import extract_social_media_from_website

async def main():
    """
    Main function to test the social media extraction.
    """
    website_urls = ["www.amd.com", "intel.com", "www.linkedin.com", "www.udemy.com"]
    for website_url in website_urls:
        print(f"Attempting to extract social media links from: {website_url}")

        # Call the asynchronous function
        try:
            social_media_info = await extract_social_media_from_website(website_url)

            # Print the result in a readable format
            print("\n--- Extraction Result ---")
            print(json.dumps(social_media_info, indent=4))
            print("-----------------------\n")

        except Exception as e:
            print(f"An error occurred during extraction for {website_url}: {e}")

if __name__ == "__main__":
    # In Python 3.7+ you can use asyncio.run()
    asyncio.run(main()) 