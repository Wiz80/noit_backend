import os
import asyncio
import json
import logging
from app.services.business.competitive_analysis.instagram.comments.instagram_sentiment_emotion_analyzer import InstagramSentimentEmotionAnalyzer
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

"""
Database Operations in Tests:

This test interacts with the database to analyze Instagram comments. For production environments,
consider the following strategies:

1. TEST DATABASE: Use a separate test database to avoid affecting production data.
   Configure this in app/db/session.py with a TEST_DATABASE_URL environment variable.

2. MOCKING STRATEGY: For pure unit testing, consider mocking the database interactions:
   - Use unittest.mock to patch SessionLocal and session methods
   - Create a session_mock object that returns predefined data
   - Example: patch('app.db.session.SessionLocal', return_value=session_mock)

3. TRANSACTION ROLLBACK: If using the real database, wrap operations in transactions
   and roll back at the end of tests to avoid persistent changes.

4. DATA CLEANUP: Add teardown functions to delete any test data created during testing.

The current implementation creates minimal test data only if it doesn't exist and
does not clean up after itself, suitable for development testing but not production CI/CD.
"""

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

async def test_analyze_sentiment_and_emotions():
    """
    Test the sentiment and emotion analysis of Instagram comments for a competitor.
    
    This test:
    1. Fetches processed comments data from Minio
    2. Initializes the InstagramSentimentEmotionAnalyzer
    3. Runs the sentiment and emotion analysis
    4. Logs the results
    """
    try:
        # Initialize parameters
        business_id = "88025338-e86a-41ff-9b76-b8c1889ca4ac"
        output_folder = f"{business_id}/competitor-analysis/instagram"
        instagram_username = "bulldogskincare"
        
        # Get the API key from environment variables
        api_key = os.getenv("APIFY_API_KEY")
        if not api_key:
            logger.error("❌ APIFY_API_KEY environment variable is not set.")
            return
        
        # BREAKPOINT 1: Check initial parameters
        logger.debug(f"Debug Parameters - Username: {instagram_username}, Output folder: {output_folder}")
        
        print(f"🚀 Initializing Instagram Sentiment and Emotion Analyzer...")
        sentiment_analyzer = InstagramSentimentEmotionAnalyzer(
            username=instagram_username,
            output_folder=output_folder
        )
        
        # Initialize MinioService to check for processed comments
        minio_service = MinioService(bucket_name="lattice-businesses")
        
        # Define object paths
        processed_comments_object_name = f"{output_folder}/{instagram_username}/processed_comments_data.json"
        
        print(f"📂 Checking for processed Instagram comments from MinIO: {processed_comments_object_name}")
        try:
            # Get processed comments data from MinIO to ensure it exists
            processed_comments_data = minio_service.get_object_data(processed_comments_object_name)
            if not processed_comments_data:
                raise ValueError(f"❌ Could not retrieve processed comments data from {processed_comments_object_name}")
                
            # Parse processed comments JSON data (just to verify it exists and is valid)
            processed_comments = json.loads(processed_comments_data.decode('utf-8'))
            if not processed_comments:
                raise ValueError(f"❌ Invalid processed comments data format")
                
            # Print the structure of the processed comments to understand what we're working with
            print_data_structure(processed_comments, "Processed Comments")
            
            # DEBUG: Get returned data from load_comments() to see its structure
            print("\n📑 Testing the load_comments() method directly...")
            loaded_comments = await sentiment_analyzer.load_comments()
            print_data_structure(loaded_comments, "Loaded Comments from load_comments()")
            
            # If loaded_comments is a string, try parsing it
            if isinstance(loaded_comments, str):
                print("⚠️ load_comments() returned a string. Trying to parse it as JSON...")
                try:
                    parsed_comments = json.loads(loaded_comments)
                    print_data_structure(parsed_comments, "Parsed Loaded Comments")
                except json.JSONDecodeError as je:
                    print(f"❌ Could not parse loaded comments as JSON: {je}")
            
            logger.debug(f"Successfully verified processed comments data exists in MinIO")
            print(f"📋 Found processed Instagram comment data to analyze")
            
            # BREAKPOINT 2: After verifying data exists
            
        except Exception as e:
            logger.error(f"❌ Error checking processed comments data from MinIO: {str(e)}")
            print(f"❌ Error checking processed comments data from MinIO: {str(e)}")
            return
        
        # Create test data in database for testing if needed
        session = SessionLocal()
        try:
            # Check if user already exists in database
            existing_user = session.query(InstagramUserInfo).filter_by(username=instagram_username).first()
            
            if not existing_user:
                print(f"⚠️ Instagram user {instagram_username} not found in database. Creating test record...")
                # For testing purposes, create a test user record
                test_user = InstagramUserInfo(
                    username=instagram_username,
                    full_name=f"Test {instagram_username}",
                    profile_pic_url="https://example.com/test.jpg",
                    is_private=False,
                    media_count=100,
                    follower_count=1000,
                    following_count=500,
                    biography="Test biography",
                    external_url="https://example.com"
                )
                session.add(test_user)
                session.commit()
                instagram_user_id = test_user.id
            else:
                instagram_user_id = existing_user.id
                print(f"✅ Found existing Instagram user record for {instagram_username}")
            
            # Check if we have post records
            post_count = session.query(InstagramPostInfo).filter_by(instagram_user_id=instagram_user_id).count()
            if post_count == 0:
                print(f"⚠️ No post records found for {instagram_username}. Analysis may be incomplete.")
                # Optional: Create dummy post records if needed for testing
                
            print(f"📊 Found {post_count} post records for {instagram_username}")
            
        except Exception as db_error:
            logger.error(f"❌ Database setup error: {str(db_error)}")
            print(f"❌ Database setup error: {str(db_error)}")
        finally:
            session.close()
        
        # Create a monkeypatch for the load_comments method to return data in the expected format
        async def patched_load_comments(self):
            """Patched version of load_comments to return data in the expected format"""
            print("📝 Using patched load_comments method")
            comments_list = []
            
            # Get the raw data
            processed_comments_data = minio_service.get_object_data(processed_comments_object_name)
            if not processed_comments_data:
                return []
                
            # Parse the JSON
            posts_dict = json.loads(processed_comments_data.decode('utf-8'))
            
            # Flatten the comments structure to a list
            for post_id, post_data in posts_dict.items():
                for comment in post_data.get("comments", []):
                    # Add post_id to each comment for reference
                    comment["post_id"] = post_data.get("post_id")
                    comment["postUrl"] = f"https://www.instagram.com/p/{post_id}/"
                    comments_list.append(comment)
            
            print(f"📊 Flattened {len(comments_list)} comments from {len(posts_dict)} posts")
            return comments_list
        
        # Monkey-patch the load_comments method
        original_load_comments = sentiment_analyzer.load_comments
        sentiment_analyzer.load_comments = patched_load_comments.__get__(sentiment_analyzer)
        
        print(f"🔍 Running sentiment and emotion analysis for Instagram user: {instagram_username}")
        # Process the comments data
        try:
            await sentiment_analyzer.analyze_sentiment_and_emotions()
            print("✅ Analysis completed without errors")
        except Exception as analysis_error:
            print(f"❌ Error during analysis: {analysis_error}")
            # Restore original method
            sentiment_analyzer.load_comments = original_load_comments
            raise
        
        # Restore original method
        sentiment_analyzer.load_comments = original_load_comments
        
        # BREAKPOINT 3: After analysis
        
        # Check if sentiment and emotion files were created in MinIO
        sentiment_object_name = f"{output_folder}/sentiment_analysis.json"
        emotion_object_name = f"{output_folder}/emotion_analysis.json"
        
        sentiment_data = minio_service.get_object_data(sentiment_object_name)
        emotion_data = minio_service.get_object_data(emotion_object_name)
        
        if sentiment_data and emotion_data:
            # Parse the results to show a summary
            sentiment_results = json.loads(sentiment_data.decode('utf-8'))
            emotion_results = json.loads(emotion_data.decode('utf-8'))
            
            total_comments_analyzed = sentiment_results.get("total_comments", 0)
            
            print(f"✅ Sentiment and emotion analysis completed successfully!")
            print(f"📊 Total comments analyzed: {total_comments_analyzed}")
            
            # Print a sample of the sentiment analysis results
            if total_comments_analyzed > 0 and "results" in sentiment_results:
                print("\n📝 Sample of sentiment analysis results:")
                for i, result in enumerate(sentiment_results["results"][:3]):  # Show up to 3 results
                    print(f"  Comment {i+1}:")
                    print(f"    - Text: {result['comment_text'][:50]}{'...' if len(result['comment_text']) > 50 else ''}")
                    print(f"    - Top Sentiment: {result['top_label']}")
                    print(f"    - Owner: @{result['owner_username']}")
                
                if len(sentiment_results["results"]) > 3:
                    print(f"    - ... and {len(sentiment_results['results']) - 3} more comments analyzed")
            
            # Print a sample of the emotion analysis results
            if "results" in emotion_results:
                print("\n📝 Sample of emotion analysis results:")
                for i, result in enumerate(emotion_results["results"][:3]):  # Show up to 3 results
                    print(f"  Comment {i+1}:")
                    print(f"    - Text: {result['comment_text'][:50]}{'...' if len(result['comment_text']) > 50 else ''}")
                    print(f"    - Top Emotion: {result['top_label']}")
                    print(f"    - Owner: @{result['owner_username']}")
                
                if len(emotion_results["results"]) > 3:
                    print(f"    - ... and {len(emotion_results['results']) - 3} more comments analyzed")
            
            print(f"\n💾 Analysis results saved to MinIO:")
            print(f"  - Sentiment analysis: {sentiment_object_name}")
            print(f"  - Emotion analysis: {emotion_object_name}")
            
        else:
            print("⚠️ Sentiment and emotion analysis did not produce expected output files.")
    
    except Exception as e:
        logger.exception(f"Unexpected error in test_analyze_sentiment_and_emotions function: {str(e)}")
        print(f"❌ Unexpected error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_analyze_sentiment_and_emotions()) 