import asyncio
import os
import sys
from dotenv import load_dotenv
from sqlalchemy import select
from uuid import uuid4
import re

# Add the project root to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.business.competitive_analysis.instagram.instagram_scraper import InstagramScraper
from app.models.business.competitive_analysis.instagram import InstagramUserInfo, InstagramPostInfo
from app.db.session import SessionLocal

load_dotenv()

def clean_instagram_url(url):
    """
    Clean Instagram URL to ensure it's in the proper format without trailing slashes
    or other problematic characters.
    
    Args:
        url (str): The Instagram post URL to clean
        
    Returns:
        str: Properly formatted Instagram URL
    """
    if not url:
        return None
    
    # Remove trailing slashes
    url = url.rstrip('/')
    
    # Ensure URL is a valid Instagram post URL
    if not (url.startswith('http://') or url.startswith('https://')):
        url = f'https://{url}'
    
    # Some basic validation - Instagram URLs typically have this format
    if not ('instagram.com/p/' in url or 'instagram.com/reel/' in url):
        print(f"Warning: URL does not seem to be a valid Instagram post URL: {url}")
    
    return url

async def test_scrape_instagram_comments():
    """
    Test function for the scrape_instagram_comments method of the InstagramScraper.
    This test retrieves post URLs from the InstagramPostInfo model for the username "bulldogskincare"
    and tests the scrape_instagram_comments method using these URLs.
    """
    try:
        print("Starting test for scrape_instagram_comments method...")
        
        # Initialize the Instagram scraper with the API key from environment variables
        # For debugging purposes - use a consistent output folder
        business_id = "88025338-e86a-41ff-9b76-b8c1889ca4ac"  # Debug ID
        instagram_scraper = InstagramScraper(
            api_key=os.getenv("APIFY_API_KEY"),
            output_folder=f"{business_id}/competitor-analysis/instagram"
        )
        
        # Breakpoint opportunity #1 - After initializing scraper
        # You can set a breakpoint here to inspect the scraper object
        
        # Create a database session
        db = SessionLocal()
        
        # Find the user ID for "bulldogskincare"
        print(f"Looking up user info for username: bulldogskincare")
        user_info = db.execute(
            select(InstagramUserInfo).where(InstagramUserInfo.username == "bulldogskincare")
        ).scalar_one_or_none()
        
        # Breakpoint opportunity #2 - After fetching user info
        # You can set a breakpoint here to inspect user_info
        
        if not user_info:
            print("⚠️ User 'bulldogskincare' not found in the database.")
            print("Attempting to proceed with a general test...")
            
            # Fetch any available Instagram posts if the specific user is not found
            posts = db.execute(select(InstagramPostInfo).limit(5)).scalars().all()
        else:
            print(f"✅ Found user: {user_info.username} (ID: {user_info.id})")
            
            # Get the post URLs for this user
            posts = db.execute(
                select(InstagramPostInfo).where(InstagramPostInfo.instagram_user_id == user_info.id)
            ).scalars().all()
        
        # Extract and clean post URLs
        post_urls = []
        for post in posts:
            if post.url_post:
                clean_url = clean_instagram_url(post.url_post)
                if clean_url:
                    post_urls.append(clean_url)
        
        # Breakpoint opportunity #3 - After extracting post URLs
        # You can set a breakpoint here to inspect the post_urls
        
        if not post_urls:
            print("⚠️ No post URLs found. Cannot proceed with the test.")
            return
        
        print(f"Found {len(post_urls)} post URLs for testing:")
        for i, url in enumerate(post_urls, 1):
            print(f"  {i}. {url}")
        
        # Call the scrape_instagram_comments method
        print("\nCalling scrape_instagram_comments method...")
        
        # Breakpoint opportunity #4 - Before calling the scraper
        # You can set a breakpoint here to examine the parameters
        
        results = await instagram_scraper.scrape_instagram_comments(
            post_urls=post_urls,
            max_comments=5  # Limit to 5 comments per post for testing
        )
        
        # Breakpoint opportunity #5 - After getting results
        # You can set a breakpoint here to inspect the results
        
        # Display the results
        if results:
            print(f"\n✅ Successfully retrieved comments for {len(results)} posts")
            for i, result in enumerate(results, 1):
                post_url = result.get("postUrl", "Unknown URL")
                comments_count = len(result.get("comments", []))
                print(f"  Post {i}: {post_url}")
                print(f"    - Comments retrieved: {comments_count}")
                
                # Display a sample of comments if available
                if comments_count > 0:
                    print("    - Sample comments:")
                    for j, comment in enumerate(result.get("comments", [])[:2], 1):
                        text = comment.get("text", "No text")
                        username = comment.get("ownerUsername", "Unknown user")
                        print(f"      {j}. @{username}: {text[:50]}{'...' if len(text) > 50 else ''}")
        else:
            print("❌ Failed to retrieve comments.")
        
        # Close the database session
        db.close()
        
        print("\nTest completed!")
        
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    # Run the test
    asyncio.run(test_scrape_instagram_comments()) 