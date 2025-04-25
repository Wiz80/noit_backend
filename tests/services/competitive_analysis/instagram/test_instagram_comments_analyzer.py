import os
import asyncio
import json
import logging
from app.services.business.competitive_analysis.instagram.comments.instagram_comments import InstagramComments
from app.services.storage.minio_service import MinioService
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.core.config import settings

# Set up logging for debugging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def test_transform_instagram_comments():
    """
    Test the transformation of Instagram comments data for a competitor.
    
    This test:
    1. Fetches comments data from Minio
    2. Fetches posts data from Minio
    3. Uses the InstagramComments class to transform the data
    4. Logs the results
    """
    try:
        # Initialize parameters
        business_id = "88025338-e86a-41ff-9b76-b8c1889ca4ac"
        output_folder = f"{business_id}/competitor-analysis/instagram"
        instagram_username = "bulldogskincare"
        post_limit = 15
        image_limit = 5  # Not used for comments analysis but required for class initialization
        
        # Get the API key from environment variables
        api_key = os.getenv("APIFY_API_KEY")
        if not api_key:
            logger.error("❌ APIFY_API_KEY environment variable is not set.")
            return
        
        # BREAKPOINT 1: Check initial parameters
        logger.debug(f"Debug Parameters - Username: {instagram_username}, Output folder: {output_folder}")
        
        print(f"🚀 Initializing Instagram Comments Analyzer...")
        comments_analyzer = InstagramComments(
            username=instagram_username,
            post_limit=post_limit,
            image_limit=image_limit,
            output_folder=output_folder
        )
        
        # Initialize MinioService to fetch data
        minio_service = MinioService(bucket_name="lattice-businesses")
        
        # Define object paths
        comments_object_name = f"{output_folder}/{instagram_username}/comments_data.json"
        posts_object_name = f"{output_folder}/{instagram_username}/instagram_posts.json"
        
        print(f"📂 Fetching Instagram comments from MinIO: {comments_object_name}")
        try:
            # Get comments data from MinIO
            comments_data = minio_service.get_object_data(comments_object_name)
            if not comments_data:
                raise ValueError(f"❌ Could not retrieve comments data from {comments_object_name}")
                
            # Parse comments JSON data
            comments = json.loads(comments_data.decode('utf-8'))
            if not comments or not isinstance(comments, list):
                raise ValueError(f"❌ Invalid comments data format. Expected a list, got {type(comments)}")
                
            logger.debug(f"Successfully fetched comments data with {len(comments)} entries from MinIO")
            print(f"📋 Found {len(comments)} Instagram comment entries to analyze")
            
            # Get posts data from MinIO
            print(f"📂 Fetching Instagram posts from MinIO: {posts_object_name}")
            posts_data = minio_service.get_object_data(posts_object_name)
            if not posts_data:
                raise ValueError(f"❌ Could not retrieve posts data from {posts_object_name}")
                
            # Parse posts JSON data
            posts = json.loads(posts_data.decode('utf-8'))
            if not posts or not isinstance(posts, list):
                raise ValueError(f"❌ Invalid posts data format. Expected a list, got {type(posts)}")
                
            logger.debug(f"Successfully fetched posts data with {len(posts)} entries from MinIO")
            print(f"📋 Found {len(posts)} Instagram post entries to analyze")
            
            # BREAKPOINT 2: After fetching data
            
        except Exception as e:
            logger.error(f"❌ Error fetching data from MinIO: {str(e)}")
            print(f"❌ Error fetching data from MinIO: {str(e)}")
            return
        
        print(f"🔍 Transforming Instagram comments for user: {instagram_username}")
        # Process the comments data with posts data
        transformed_comments = await comments_analyzer.transform_instagram_comments(comments, posts)
        
        # BREAKPOINT 3: After transforming comments
        
        if transformed_comments:
            post_count = len(transformed_comments)
            total_comments = sum(len(post_data.get("comments", [])) for post_data in transformed_comments.values())
            
            logger.debug(f"Successfully transformed comments for {post_count} posts with {total_comments} total comments")
            
            print(f"✅ Comments transformation completed successfully!")
            print(f"📊 Transformed comments for {post_count} posts")
            print(f"💬 Total comments processed: {total_comments}")
            
            # Print a sample of the transformed data (first 2 posts only)
            print("\n📝 Sample of transformed comments:")
            for i, (post_id, post_data) in enumerate(list(transformed_comments.items())[:2]):
                print(f"  Post {i+1} (ID: {post_id}):")
                for j, comment in enumerate(post_data.get("comments", [])[:3]):  # Show up to 3 comments per post
                    print(f"    - Comment {j+1}: @{comment['ownerusername']}: {comment['contenido'][:50]}{'...' if len(comment['contenido']) > 50 else ''}")
                if len(post_data.get("comments", [])) > 3:
                    print(f"    - ... and {len(post_data.get('comments', [])) - 3} more comments")
            
            # Save transformed data to Minio
            transformed_object_name = f"{output_folder}/{instagram_username}/processed_comments_data.json"
            
            await minio_service.upload_content(
                object_name=transformed_object_name,
                data=json.dumps(transformed_comments, indent=4),
                content_type="application/json",
                metadata={"username": instagram_username}
            )
            
            print(f"💾 Transformed comments data saved to MinIO: {transformed_object_name}")
            
        else:
            print("⚠️ Comments transformation did not produce any results.")
    except Exception as e:
        logger.exception(f"Unexpected error in test_transform_instagram_comments function: {str(e)}")
        print(f"❌ Unexpected error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_transform_instagram_comments()) 