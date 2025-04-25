import os
import asyncio
import json
import logging
from app.services.business.competitive_analysis.instagram.instagram_statistics import InstagramStatistics
from app.services.storage.minio_service import MinioService
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.core.config import settings
from app.models.business.competitive_analysis.instagram import (
    InstagramUserInfo, 
    InstagramPostInfo
)

# Set up logging for debugging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Helper function to check and print data structure
def print_data_structure(data, name="Data"):
    """Print information about the data structure to help debugging"""
    print(f"\n🔍 DEBUG: {name} Structure Analysis:")
    print(f"  Type: {type(data)}")
    
    if isinstance(data, str):
        print(f"  Length: {len(data)} characters")
        print(f"  First 100 chars: {data[:100]}...")
        print("  This appears to be a string, not parsed JSON")
    elif isinstance(data, dict):
        print(f"  Keys count: {len(data.keys())}")
        print(f"  Keys sample: {list(data.keys())[:5]}")
        if len(data) > 0:
            first_key = next(iter(data))
            first_value = data[first_key]
            print(f"  First key: {first_key}")
            print(f"  First value type: {type(first_value)}")
            if isinstance(first_value, dict):
                print(f"  First value keys: {list(first_value.keys())}")
    elif isinstance(data, list):
        print(f"  Items count: {len(data)}")
        if len(data) > 0:
            print(f"  First item type: {type(data[0])}")
            if isinstance(data[0], dict):
                print(f"  First item keys: {list(data[0].keys())}")

async def load_posts_into_db(session, instagram_username, posts, user_id):
    """
    Load Instagram posts from JSON data into the database
    
    :param session: Database session
    :param instagram_username: Username of the Instagram account
    :param posts: List of posts data from JSON
    :param user_id: ID of the Instagram user in the database
    :return: Number of posts loaded
    """
    count = 0
    
    try:
        # First check how many posts already exist for this user
        existing_count = session.query(InstagramPostInfo).filter_by(instagram_user_id=user_id).count()
        
        if existing_count > 0:
            print(f"📊 Found {existing_count} existing posts for {instagram_username} in database")
            return existing_count
        
        print(f"🔄 Loading posts data into database for {instagram_username}...")
        
        for post in posts:
            # Check if we already have this post
            existing_post = session.query(InstagramPostInfo).filter_by(
                id_post=post.get("id"),
                instagram_user_id=user_id
            ).first()
            
            if not existing_post:
                # Create new post record
                new_post = InstagramPostInfo(
                    instagram_user_id=user_id,
                    id_post=post.get("id"),
                    type_post=post.get("type"),
                    caption=post.get("caption", ""),
                    likes_count=post.get("likesCount", 0),
                    comments_count=post.get("commentsCount", 0),
                    post_timestamp=post.get("timestamp"),
                    url_post=post.get("url", "")
                )
                session.add(new_post)
                count += 1
                
        session.commit()
        print(f"✅ Successfully loaded {count} posts into database")
        return count
        
    except Exception as e:
        session.rollback()
        print(f"❌ Error loading posts into database: {e}")
        return 0

async def test_instagram_statistics():
    """
    Test the statistics analysis of Instagram posts for a competitor.
    
    This test:
    1. Fetches posts data from Minio
    2. Loads posts data into the database if needed
    3. Initializes the InstagramStatistics with appropriate settings
    4. Runs the statistics generation process
    5. Checks the results in Minio
    6. Logs the results and statistics
    """
    try:
        # Initialize parameters
        business_id = "88025338-e86a-41ff-9b76-b8c1889ca4ac"
        output_folder = f"{business_id}/competitor-analysis/instagram"
        instagram_username = "bulldogskincare"
        post_limit = 50
        image_limit = 10
        
        # Debug Parameters
        logger.debug(f"Debug Parameters - Username: {instagram_username}, Output folder: {output_folder}, Post limit: {post_limit}, Image limit: {image_limit}")
        
        print(f"🚀 Initializing Instagram Statistics Analysis...")
        
        # Initialize MinioService to check for posts data
        minio_service = MinioService(bucket_name="lattice-businesses")
        
        # Define object paths - Update to correct path for bulldogskincare
        posts_object_name = f"{output_folder}/{instagram_username}/instagram_posts.json"
        
        print(f"📂 Checking for Instagram posts data from MinIO: {posts_object_name}")
        try:
            # Get posts data from MinIO
            posts_data = minio_service.get_object_data(posts_object_name)
            if not posts_data:
                raise ValueError(f"❌ Could not retrieve posts data from {posts_object_name}")
                
            # Parse posts JSON data
            posts = json.loads(posts_data.decode('utf-8'))
            if not posts:
                raise ValueError(f"❌ Invalid posts data format")
                
            # Print the structure of the posts data
            print_data_structure(posts, "Posts Data")
            
            logger.debug(f"Successfully verified posts data exists in MinIO")
            print(f"📋 Found Instagram posts data to analyze: {len(posts)} posts")
            
            # Load data into database
            user_id = None
            try:
                session = SessionLocal()
                # Check if user already exists in database
                existing_user = session.query(InstagramUserInfo).filter_by(username=instagram_username).first()
                
                if existing_user:
                    print(f"✅ Found existing Instagram user record for {instagram_username}")
                    print(f"👥 Followers count: {existing_user.followers_count}")
                    user_id = existing_user.id
                    
                    # Load posts into database
                    posts_loaded = await load_posts_into_db(session, instagram_username, posts, user_id)
                    
                    # After loading, verify again
                    post_count = session.query(InstagramPostInfo).filter_by(instagram_user_id=user_id).count()
                    if post_count > 0:
                        print(f"📊 Verified {post_count} posts in database for {instagram_username}")
                else:
                    print(f"⚠️ Instagram user {instagram_username} not found in database.")
                    print("⚠️ Cannot load posts without a user record. Creating user record first...")
                    
                    # Create user record with basic info
                    new_user = InstagramUserInfo(
                        username=instagram_username,
                        full_name=instagram_username,  # Default to username if full name not available
                        followers_count=1000,  # Default value
                        follows_count=0,       # Default value
                        total_posts=len(posts)
                    )
                    session.add(new_user)
                    session.commit()
                    
                    user_id = new_user.id
                    print(f"✅ Created new Instagram user record for {instagram_username} with ID {user_id}")
                    
                    # Now load posts
                    posts_loaded = await load_posts_into_db(session, instagram_username, posts, user_id)
                    
            except Exception as db_error:
                logger.error(f"❌ Database connection error: {str(db_error)}")
                print(f"❌ Database connection error: {str(db_error)}")
                print("⚠️ Continuing test without database operations...")
            finally:
                if 'session' in locals():
                    session.close()
            
        except Exception as e:
            logger.error(f"❌ Error checking posts data from MinIO: {str(e)}")
            print(f"❌ Error checking posts data from MinIO: {str(e)}")
            return
        
        # Now initialize the statistics analyzer
        statistics = InstagramStatistics(
            username=instagram_username,
            post_limit=post_limit,
            image_limit=image_limit,
            output_folder=output_folder
        )
        
        # Update the img_posts.json file to match the structure expected by the generate_statistics method
        # Copy the posts data to the expected location
        try:
            print(f"🔄 Copying posts data to expected location for statistics generation...")
            await minio_service.upload_content(
                object_name=f"{output_folder}/img_posts.json",
                data=posts_data,
                content_type="application/json"
            )
            print(f"✅ Posts data copied successfully")
        except Exception as copy_error:
            print(f"❌ Error copying posts data: {copy_error}")
            
        # Run the statistics generation
        print(f"📊 Generating statistics for Instagram user: {instagram_username}")
        
        try:
            # Run the main statistics function
            stats_file_path = await statistics.generate_statistics()
            
            if stats_file_path:
                print(f"✅ Statistics generation completed successfully!")
                print(f"📂 Statistics saved to: {stats_file_path}")
            else:
                print("❌ Failed to generate statistics.")
                
        except Exception as analysis_error:
            print(f"❌ Error during statistics generation: {analysis_error}")
            # Print the stack trace
            import traceback
            traceback.print_exc()
        
        # Check if statistics file was created in MinIO
        statistics_object_name = f"{output_folder}/statistics.json"
        
        statistics_data = minio_service.get_object_data(statistics_object_name)
        
        if statistics_data:
            # Parse the results to show a summary
            stats = json.loads(statistics_data.decode('utf-8'))
            
            # Print data structure to understand what was created
            print_data_structure(stats, "Instagram Statistics Results")
            
            print(f"\n📊 Instagram Statistics Summary:")
            print(f"  - Total followers: {stats.get('total_followers', 'N/A')}")
            print(f"  - Total posts analyzed: {stats.get('total_posts', 'N/A')}")
            print(f"  - Total likes: {stats.get('total_likes', 'N/A')}")
            print(f"  - Total comments: {stats.get('total_comments', 'N/A')}")
            print(f"  - Average likes per post: {stats.get('avg_likes_per_post', 'N/A'):.2f}")
            print(f"  - Average comments per post: {stats.get('avg_comments_per_post', 'N/A'):.2f}")
            print(f"  - Average engagement rate: {stats.get('avg_engagement_rate', 'N/A'):.2f}%")
            
            # Print post type distribution
            post_types = stats.get('post_type_distribution', {})
            if post_types:
                print("\n📸 Post Type Distribution:")
                for post_type, count in post_types.items():
                    print(f"  - {post_type}: {count} posts")
            
            # Print engagement by day of week
            engagement_by_day = stats.get('engagement_by_day_of_week', {})
            if engagement_by_day:
                print("\n📅 Engagement by Day of Week:")
                for day, rate in engagement_by_day.items():
                    print(f"  - {day}: {rate:.2f}%")
            
            # Print top posts
            top_posts = stats.get('top_posts', [])
            if top_posts:
                print("\n🔝 Top 3 Posts by Engagement:")
                for i, post in enumerate(top_posts[:3]):
                    print(f"  {i+1}. Post ID: {post.get('id', 'N/A')}")
                    print(f"     Type: {post.get('type', 'N/A')}")
                    print(f"     Likes: {post.get('likesCount', 'N/A')}")
                    print(f"     Comments: {post.get('commentsCount', 'N/A')}")
                    print(f"     Engagement rate: {post.get('engagement_rate', 'N/A'):.2f}%")
                    
                    # Print a snippet of the caption if available
                    caption = post.get('caption', '')
                    if caption:
                        # Truncate long captions
                        caption = caption[:100] + '...' if len(caption) > 100 else caption
                        print(f"     Caption: {caption}")
                    
                    print("     " + "-" * 40)
            
            print(f"\n💾 Statistics data saved to MinIO: {statistics_object_name}")
        else:
            print("⚠️ Statistics generation did not produce expected output file.")
    
    except Exception as e:
        logger.exception(f"Unexpected error in test_instagram_statistics function: {str(e)}")
        print(f"❌ Unexpected error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_instagram_statistics()) 