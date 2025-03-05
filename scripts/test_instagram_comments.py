#!/usr/bin/env python3
"""
Script to test the scrape_instagram_comments method of InstagramScraper.
This script uses the username "bulldogskincare" to find Instagram posts and
tests the scrape_instagram_comments functionality.
"""

import asyncio
import os
import sys
from dotenv import load_dotenv
from sqlalchemy import select
from uuid import uuid4
import re

# Add the project root to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.business.competitive_analysis.instagram.instagram_scraper import InstagramScraper
from app.models.business.competitive_analysis.instagram import InstagramUserInfo, InstagramPostInfo
from app.db.session import SessionLocal

# Load environment variables
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

async def main():
    """
    Main function to test the Instagram comments scraper.
    """
    print("=" * 50)
    print("INSTAGRAM COMMENTS SCRAPER TEST")
    print("=" * 50)
    print("Target username: bulldogskincare")
    print("-" * 50)
    
    try:
        # Initialize the Instagram scraper
        instagram_scraper = InstagramScraper(
            api_key=os.getenv("APIFY_API_KEY"),
            output_folder=f"88025338-e86a-41ff-9b76-b8c1889ca4ac/competitor-analysis/instagram"
        )
        
        # Create a database session
        db = SessionLocal()
        
        # Find the user ID for "bulldogskincare"
        print("Looking up user info for username: bulldogskincare")
        user_info = db.execute(
            select(InstagramUserInfo).where(InstagramUserInfo.username == "bulldogskincare")
        ).scalar_one_or_none()
        
        if not user_info:
            print("⚠️ User 'bulldogskincare' not found in the database.")
            
            # Ask if we should search for other users
            print("\nOptions:")
            print("1. Search for other Instagram users in the database")
            print("2. Exit the script")
            
            choice = input("Choose an option (1 or 2): ")
            
            if choice.strip() == "1":
                # Get a list of available users
                users = db.execute(select(InstagramUserInfo).limit(10)).scalars().all()
                
                if not users:
                    print("No Instagram users found in the database.")
                    return
                
                print("\nAvailable Instagram users:")
                for i, user in enumerate(users, 1):
                    print(f"{i}. {user.username} (Followers: {user.followers_count})")
                
                user_choice = input(f"Choose a user (1-{len(users)}): ")
                try:
                    user_index = int(user_choice) - 1
                    if 0 <= user_index < len(users):
                        user_info = users[user_index]
                    else:
                        print("Invalid selection. Exiting.")
                        return
                except ValueError:
                    print("Invalid input. Exiting.")
                    return
            else:
                print("Exiting the script.")
                return
        
        print(f"✅ Using user: {user_info.username} (Followers: {user_info.followers_count})")
        
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
        
        # Debug point #3 - After extracting post URLs
        # Set a breakpoint here to inspect the available post URLs
        
        if not post_urls:
            print("⚠️ No post URLs found for this user. Cannot proceed with the test.")
            return
        
        # Allow the user to select how many posts to use
        print(f"\nFound {len(post_urls)} posts with URLs.")
        max_posts = min(len(post_urls), 5)  # Default to 5 posts max
        
        posts_to_use = input(f"How many posts would you like to use for testing? (1-{len(post_urls)}, default: {max_posts}): ")
        if posts_to_use.strip() and posts_to_use.isdigit():
            max_posts = min(int(posts_to_use), len(post_urls))
        
        selected_urls = post_urls[:max_posts]
        
        print(f"\nSelected {len(selected_urls)} post URLs for testing:")
        for i, url in enumerate(selected_urls, 1):
            print(f"  {i}. {url}")
        
        # Ask for the maximum number of comments per post
        max_comments = 5  # Default
        comments_input = input(f"Maximum comments per post to retrieve (default: {max_comments}): ")
        if comments_input.strip() and comments_input.isdigit():
            max_comments = int(comments_input)
        
        print(f"\nRetrieving up to {max_comments} comments per post...")
        
        # Call the scrape_instagram_comments method
        results = await instagram_scraper.run_instagram_comments_scraper(
            usernames=["bulldogskincare"],
            result_limit=max_comments,
            max_comments=max_comments
        )
        
        # Display the results
        if results:
            print(f"\n✅ Successfully retrieved comments data for {len(results)} posts")
            
            # Summary of comments retrieved
            total_comments = sum(len(result.get("comments", [])) for result in results)
            print(f"Total comments retrieved: {total_comments}")
            
            # Detailed breakdown by post
            print("\nBreakdown by post:")
            for i, result in enumerate(results, 1):
                post_url = result.get("postUrl", "Unknown URL")
                comments = result.get("comments", [])
                comments_count = len(comments)
                
                print(f"\nPost {i}: {post_url}")
                print(f"Comments retrieved: {comments_count}")
                
                # Display sample comments
                if comments_count > 0:
                    print("\nSample comments:")
                    sample_size = min(3, comments_count)  # Show up to 3 comments as a sample
                    for j, comment in enumerate(comments[:sample_size], 1):
                        text = comment.get("text", "No text")
                        username = comment.get("ownerUsername", "Unknown user")
                        likes = comment.get("likesCount", 0)
                        timestamp = comment.get("timestamp", "Unknown time")
                        
                        print(f"  {j}. @{username} (Likes: {likes})")
                        print(f"     {text[:100]}{'...' if len(text) > 100 else ''}")
                        print(f"     Posted: {timestamp}")
            
            # Check if data was saved to MinIO
            print(f"\nData was saved to MinIO at: {instagram_scraper.output_folder}/comments_data.json")
        else:
            print("\n❌ Failed to retrieve comments. See error messages above for details.")
        
        # Close the database session
        db.close()
        
    except Exception as e:
        print(f"\n❌ Error during execution: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Run the main function
    asyncio.run(main()) 