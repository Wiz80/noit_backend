import os
import sys
import asyncio
import logging
from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.business.competitive_analysis.instagram.instagram_scraper import InstagramScraper

# Set up logging for debugging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

async def main():
    try:
        # Get the Apify API key from environment variables
        api_key = os.getenv("APIFY_API_KEY")
        
        if not api_key:
            logger.error("❌ APIFY_API_KEY environment variable is not set.")
            return
        
        # Initialize parameters
        output_folder = "88025338-e86a-41ff-9b76-b8c1889ca4ac/competitor-analysis/instagram"
        instagram_username = "bulldogskincare"  # Use a real Instagram username
        results_limit = 15  # Limit number of posts to scrape
        
        # BREAKPOINT 1: Check initial parameters
        logger.debug(f"Debug Parameters - Username: {instagram_username}, Output folder: {output_folder}")
        
        print(f"🚀 Initializing Instagram Scraper...")
        instagram_scraper = InstagramScraper(
            api_key=api_key,
            output_folder=output_folder
        )
        
        # Step 1: Scrape the Instagram profile
        print(f"👤 Scraping profile for Instagram user: {instagram_username}")
        # BREAKPOINT 2: Before scraping profile
        profile_data = await instagram_scraper.scrape_instagram_profile([instagram_username])
        
        if profile_data:
            # BREAKPOINT 3: After profile scraping
            logger.debug(f"Successfully scraped profile for {instagram_username}")
            print(f"✅ Profile scraped successfully!")
            print(f"📊 Followers: {profile_data.get('followersCount', 'N/A')}")
            print(f"📝 Posts: {profile_data.get('postsCount', 'N/A')}")
            
            # Step 2: Scrape Instagram posts
            print(f"📱 Scraping posts for Instagram user: {instagram_username}")
            # BREAKPOINT 4: Before scraping posts
            dataset_ids, posts_data = await instagram_scraper.scrape_instagram_posts(
                [instagram_username], 
                results_limit
            )
            
            if posts_data:
                # BREAKPOINT 5: After posts scraping
                post_count = len(posts_data)
                logger.debug(f"Successfully scraped {post_count} posts for {instagram_username}")
                print(f"✅ Posts scraped successfully!")
                print(f"📊 Number of posts: {post_count}")
                
                # Step 3: Download images from the dataset
                if dataset_ids and instagram_username in dataset_ids:
                    dataset_id = dataset_ids[instagram_username]
                    print(f"📷 Downloading images for dataset ID: {dataset_id}")
                    # BREAKPOINT 6: Before downloading images
                    await instagram_scraper.download_images_from_dataset(
                        [instagram_username], 
                        dataset_id
                    )
                    # BREAKPOINT 7: After downloading images
                    print(f"✅ Images downloaded successfully!")
                else:
                    print(f"⚠️ No dataset ID found for {instagram_username}")
            else:
                print(f"⚠️ No posts data found for {instagram_username}")
        else:
            print(f"⚠️ Failed to scrape profile for {instagram_username}")
        
        print("🎉 Instagram scraping sequence completed!")
        
    except Exception as e:
        logger.exception(f"❌ Unexpected error in main function: {str(e)}")
        print(f"❌ Unexpected error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main()) 