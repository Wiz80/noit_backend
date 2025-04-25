import os
import asyncio
import json
import logging
from app.services.business.competitive_analysis.instagram.comments.instagram_comment_categorizer import InstagramCommentCategorizer
from app.services.storage.minio_service import MinioService
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.core.config import settings
from app.models.business.competitive_analysis.instagram import (
    InstagramUserInfo, 
    InstagramPostInfo,
    InstagramComment,
    InstagramCommentCategory
)
from sqlalchemy import update

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

async def test_categorize_instagram_comments():
    """
    Test the categorization of Instagram comments for a competitor.
    
    This test:
    1. Fetches processed comments data from Minio
    2. Initializes the InstagramCommentCategorizer with appropriate LLM settings
    3. Runs the comment categorization process
    4. Checks the results in Minio and the database
    5. Logs the results and statistics
    """
    try:
        # Initialize parameters
        business_id = "88025338-e86a-41ff-9b76-b8c1889ca4ac"
        output_folder = f"{business_id}/competitor-analysis/instagram"
        instagram_username = "bulldogskincare"
        provider = "openai"  # Options: "openai", "claude", "deepseek"
        model = "openai:gpt-4o-mini"  # Fixed format: "provider:model"
        
        # Debug Parameters
        logger.debug(f"Debug Parameters - Username: {instagram_username}, Output folder: {output_folder}, Provider: {provider}, Model: {model}")
        
        print(f"🚀 Initializing Instagram Comment Categorizer...")
        comment_categorizer = InstagramCommentCategorizer(
            username=instagram_username,
            output_folder=output_folder,
            provider=provider,
            model=model
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
            
            logger.debug(f"Successfully verified processed comments data exists in MinIO")
            print(f"📋 Found processed Instagram comment data to analyze")
            
        except Exception as e:
            logger.error(f"❌ Error checking processed comments data from MinIO: {str(e)}")
            print(f"❌ Error checking processed comments data from MinIO: {str(e)}")
            return
        
        # Database connection check - ignore errors as this is just for verification
        try:
            session = SessionLocal()
            # Check if user already exists in database
            existing_user = session.query(InstagramUserInfo).filter_by(username=instagram_username).first()
            
            if existing_user:
                print(f"✅ Found existing Instagram user record for {instagram_username}")
                # Check if we have post records
                post_count = session.query(InstagramPostInfo).filter_by(instagram_user_id=existing_user.id).count()
                print(f"📊 Found {post_count} post records for {instagram_username}")
            else:
                print(f"⚠️ Instagram user {instagram_username} not found in database.")
                
        except Exception as db_error:
            logger.error(f"❌ Database connection error: {str(db_error)}")
            print(f"❌ Database connection error: {str(db_error)}")
            print("⚠️ Continuing test without database operations...")
        finally:
            if 'session' in locals():
                session.close()
        
        # Run the analysis using the original methods
        print(f"🔍 Running comment categorization analysis for Instagram user: {instagram_username}")
        
        try:
            # Run the main analysis function
            total_categories = await comment_categorizer.run_analysis()
            
            if total_categories:
                print(f"✅ Comment categorization analysis completed successfully!")
                print(f"📊 Total categories generated: {total_categories}")
            else:
                print("⚠️ Comment categorization did not produce any categories.")
                
        except Exception as analysis_error:
            print(f"❌ Error during comment categorization analysis: {analysis_error}")
            # Print the stack trace
            import traceback
            traceback.print_exc()
        
        # Check if categorized comments file was created in MinIO
        categorized_comments_object_name = f"{output_folder}/dynamic_categorized_comments.json"
        
        categorized_data = minio_service.get_object_data(categorized_comments_object_name)
        
        if categorized_data:
            # Parse the results to show a summary
            categorized_results = json.loads(categorized_data.decode('utf-8'))
            
            # Print data structure to understand what was created
            print_data_structure(categorized_results, "Categorized Comments Results")
            
            # Check for category counts
            category_counts = categorized_results.get("category_counts", {})
            total_categories = len(category_counts)
            total_comments = sum(category_counts.values())
            
            print(f"📊 Categorization Statistics:")
            print(f"  - Total categories: {total_categories}")
            print(f"  - Total categorized comments: {total_comments}")
            
            # Print the top categories by comment count
            if category_counts:
                print("\n📝 Top Categories by Comment Count:")
                sorted_categories = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)
                for i, (category, count) in enumerate(sorted_categories[:5]):  # Show top 5 categories
                    print(f"  {i+1}. {category}: {count} comments")
            
            # Print a sample of the categorized comments
            if "categorized_comments" in categorized_results:
                print("\n📝 Sample of Categorized Comments:")
                for i, (category, comments) in enumerate(list(categorized_results["categorized_comments"].items())[:3]):  # Show up to 3 categories
                    print(f"  Category: {category} ({len(comments)} comments)")
                    for j, comment in enumerate(comments[:2]):  # Show up to 2 comments per category
                        if isinstance(comment, dict):
                            comment_text = comment.get("contenido", comment.get("content", ""))
                            owner = comment.get("ownerUsername", comment.get("owner", ""))
                            print(f"    - @{owner}: {comment_text[:50]}{'...' if len(comment_text) > 50 else ''}")
                        else:
                            print(f"    - {comment[:50]}{'...' if len(comment) > 50 else ''}")
                    
                    if len(comments) > 2:
                        print(f"    - ... and {len(comments) - 2} more comments")
            
            print(f"\n💾 Categorized comments data saved to MinIO: {categorized_comments_object_name}")
            
            # Check database for saved categories - ignore errors as this is just for verification
            try:
                session = SessionLocal()
                # Get the Instagram user from the database
                instagram_user = session.query(InstagramUserInfo).filter_by(username=instagram_username).first()
                if instagram_user:
                    # Count categories in the database
                    db_categories_count = session.query(InstagramCommentCategory).filter_by(user_id=instagram_user.id).count()
                    # Count comments in the database
                    db_comments_count = session.query(InstagramComment).filter_by(user_id=instagram_user.id).count()
                    
                    print(f"\n🗄️ Database Storage Check:")
                    print(f"  - Categories stored in database: {db_categories_count}")
                    print(f"  - Comments stored in database: {db_comments_count}")
                    
                    if db_categories_count > 0:
                        print("\n📝 Sample of Categories in Database:")
                        db_categories = session.query(InstagramCommentCategory).filter_by(user_id=instagram_user.id).limit(3).all()
                        for i, category in enumerate(db_categories):
                            print(f"  {i+1}. {category.category_type}: {category.category_count} comments")
                else:
                    print("\n⚠️ Instagram user not found in database, cannot check stored categories.")
                    
            except Exception as db_error:
                print(f"❌ Error checking database records: {db_error}")
                print("⚠️ Database operations could not be verified.")
            finally:
                if 'session' in locals():
                    session.close()
            
        else:
            print("⚠️ Comment categorization did not produce expected output file.")
    
    except Exception as e:
        logger.exception(f"Unexpected error in test_categorize_instagram_comments function: {str(e)}")
        print(f"❌ Unexpected error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_categorize_instagram_comments()) 