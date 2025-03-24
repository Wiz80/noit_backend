import os
import asyncio
import json
from app.services.business.competitive_analysis.instagram.instagram_image_analyzer import InstagramImageAnalyzer
from app.services.storage.minio_service import MinioService
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.core.config import settings
import logging

# Set up logging for debugging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def test_process_posts_images():
    try:
        # Get the OpenAI API key from environment variables
        api_key = os.getenv("OPENAI_API_KEY")
        
        if not api_key:
            logger.error("❌ OPENAI_API_KEY environment variable is not set.")
            return
        
        # Initialize the analyzer with the specified output folder
        output_folder = "88025338-e86a-41ff-9b76-b8c1889ca4ac/competitor-analysis/instagram"
        instagram_username = "bulldogskincare"
        business_id = "88025338-e86a-41ff-9b76-b8c1889ca4ac"  # Use your actual business ID if available
        
        # BREAKPOINT 1: Check initial parameters
        logger.debug(f"Debug Parameters - Username: {instagram_username}, Output folder: {output_folder}")
        
        print(f"🚀 Initializing Instagram Image Analyzer...")
        analyzer = InstagramImageAnalyzer(api_key=api_key, output_folder=output_folder)
        
        # Initialize MinioService to fetch Instagram posts
        minio_service = MinioService(bucket_name="lattice-businesses")
        posts_object_name = f"{output_folder}/{instagram_username}/instagram_posts.json"
        
        print(f"📂 Fetching Instagram posts from MinIO: {posts_object_name}")
        try:
            # Get JSON data from MinIO
            posts_data = minio_service.get_object_data(posts_object_name)
            if not posts_data:
                raise ValueError(f"❌ Could not retrieve posts data from {posts_object_name}")
                
            # Parse JSON data
            posts = json.loads(posts_data.decode('utf-8'))
            if not posts or not isinstance(posts, list):
                raise ValueError(f"❌ Invalid posts data format. Expected a list, got {type(posts)}")
                
            logger.debug(f"Successfully fetched {len(posts)} posts from MinIO")
            print(f"📋 Found {len(posts)} Instagram posts to analyze")
        except Exception as e:
            logger.error(f"❌ Error fetching posts from MinIO: {str(e)}")
            print(f"❌ Error fetching posts from MinIO: {str(e)}")
            return
        
        print(f"📊 Processing posts images for Instagram user: {instagram_username}")
        # BREAKPOINT 2: Before processing images
        results = await analyzer.process_posts_images(instagram_username, posts)
        
        if results:
            # BREAKPOINT 3: After image processing
            posts_count = results.get('global_analysis', {}).get('posts_analyzed', 0)
            logger.debug(f"Successfully analyzed images from {posts_count} posts")
            
            print(f"✅ Analysis completed successfully!")
            print(f"📝 Analyzed images from {posts_count} posts")
            print(f"🔍 Analysis report saved to: {output_folder}/{instagram_username}/posts_image_analysis_report.json")
            
            # Save analysis data to database
            print(f"💾 Now saving analysis data to database...")
            db = SessionLocal()
            try:
                # BREAKPOINT 4: Before database saving
                logger.debug("Starting database save operation")
                
                await analyzer.save_analysis_to_database(
                    db=db,
                    business_id=business_id,
                    instagram_username=instagram_username,
                    analysis_data=results
                )
                
                # BREAKPOINT 5: After database saving
                logger.debug("Database save operation completed")
            except Exception as e:
                logger.error(f"❌ Error saving to database: {str(e)}")
                print(f"❌ Error saving to database: {str(e)}")
            finally:
                db.close()
        else:
            print("⚠️ Analysis did not produce any results.")
    except Exception as e:
        logger.exception(f"Unexpected error in test_process_posts_images function: {str(e)}")
        print(f"❌ Unexpected error: {str(e)}")

async def test_analyze_instagram_feed():
    try:
        # Get the OpenAI API key from environment variables
        api_key = os.getenv("OPENAI_API_KEY")
        
        if not api_key:
            logger.error("❌ OPENAI_API_KEY environment variable is not set.")
            return
        
        # Initialize the analyzer with the specified output folder
        output_folder = "88025338-e86a-41ff-9b76-b8c1889ca4ac/competitor-analysis/instagram"
        instagram_username = "bulldogskincare"
        business_id = "88025338-e86a-41ff-9b76-b8c1889ca4ac"
        
        logger.debug(f"Debug Parameters - Username: {instagram_username}, Output folder: {output_folder}")
        
        print(f"🚀 Initializing Instagram Image Analyzer for feed analysis...")
        analyzer = InstagramImageAnalyzer(api_key=api_key, output_folder=output_folder)
        
        # Initialize MinioService to fetch Instagram posts
        minio_service = MinioService(bucket_name="lattice-businesses")
        posts_object_name = f"{output_folder}/{instagram_username}/instagram_posts.json"
        
        print(f"📂 Fetching Instagram posts from MinIO: {posts_object_name}")
        try:
            # Get JSON data from MinIO
            posts_data = minio_service.get_object_data(posts_object_name)
            if not posts_data:
                raise ValueError(f"❌ Could not retrieve posts data from {posts_object_name}")
                
            # Parse JSON data
            posts = json.loads(posts_data.decode('utf-8'))
            if not posts or not isinstance(posts, list):
                raise ValueError(f"❌ Invalid posts data format. Expected a list, got {type(posts)}")
                
            logger.debug(f"Successfully fetched {len(posts)} posts from MinIO")
            print(f"📋 Found {len(posts)} Instagram posts to analyze for feed coherence")
        except Exception as e:
            logger.error(f"❌ Error fetching posts from MinIO: {str(e)}")
            print(f"❌ Error fetching posts from MinIO: {str(e)}")
            return
        
        print(f"🖼️ Analyzing Instagram feed coherence for user: {instagram_username}")
        feed_results = await analyzer.analyze_instagram_feed(instagram_username, posts)
        
        if feed_results:
            total_posts = feed_results.get('global_analysis', {}).get('total_posts_analyzed', 0)
            total_batches = feed_results.get('global_analysis', {}).get('total_batches', 0)
            
            logger.debug(f"Successfully analyzed feed with {total_posts} posts in {total_batches} batches")
            
            print(f"✅ Feed analysis completed successfully!")
            print(f"📝 Analyzed {total_posts} posts in {total_batches} batches")
            print(f"🔍 Feed analysis report saved to: {output_folder}/{instagram_username}/feed_analysis_report.json")
        else:
            print("⚠️ Feed analysis did not produce any results.")
    except Exception as e:
        logger.exception(f"Unexpected error in test_analyze_instagram_feed function: {str(e)}")
        print(f"❌ Unexpected error: {str(e)}")

async def main():
    # First test the process_posts_images method
    print("=== Testing process_posts_images ===")
    await test_process_posts_images()
    
    # Then test the analyze_instagram_feed method
    print("\n=== Testing analyze_instagram_feed ===")
    await test_analyze_instagram_feed()

if __name__ == "__main__":
    asyncio.run(main()) 