import os
import asyncio
import json
import logging
from app.services.business.competitive_analysis.instagram.comments.instagram_topic_modeling import InstagramTopicModeling
from app.services.business.competitive_analysis.instagram.comments.instagram_comment_categorizer import InstagramCommentCategorizer
from app.services.storage.minio_service import MinioService
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.core.config import settings
from app.models.business.competitive_analysis.instagram import (
    InstagramUserInfo, 
    InstagramPostInfo,
    InstagramLDATopic
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

async def test_instagram_topic_modeling():
    """
    Test the topic modeling analysis of Instagram comments for a competitor.
    
    This test:
    1. Fetches categorized comments data from Minio (output of InstagramCommentCategorizer)
    2. Initializes the InstagramTopicModeling with appropriate settings
    3. Runs the LDA topic modeling process
    4. Checks the results in Minio and the database
    5. Logs the results and statistics
    """
    try:
        # Initialize parameters
        business_id = "88025338-e86a-41ff-9b76-b8c1889ca4ac"
        output_folder = f"{business_id}/competitor-analysis/instagram"
        instagram_username = "bulldogskincare"
        num_topics = 5
        lang = "en"  # Language for topic modeling
        
        # Debug Parameters
        logger.debug(f"Debug Parameters - Username: {instagram_username}, Output folder: {output_folder}, Num topics: {num_topics}, Language: {lang}")
        
        print(f"🚀 Initializing Instagram Topic Modeling...")
        topic_modeling = InstagramTopicModeling(
            username=instagram_username,
            output_folder=output_folder,
            num_topics=num_topics,
            lang=lang
        )
        
        # Initialize MinioService to check for categorized comments
        minio_service = MinioService(bucket_name=settings.MINIO_BUCKET_NAME)
        
        # Define object paths
        categorized_comments_object_name = f"{output_folder}/dynamic_categorized_comments.json"
        
        print(f"📂 Checking for categorized Instagram comments from MinIO: {categorized_comments_object_name}")
        try:
            # Get categorized comments data from MinIO
            categorized_comments_data = minio_service.get_object_data(categorized_comments_object_name)
            if not categorized_comments_data:
                raise ValueError(f"❌ Could not retrieve categorized comments data from {categorized_comments_object_name}")
                
            # Parse categorized comments JSON data
            categorized_comments = json.loads(categorized_comments_data.decode('utf-8'))
            if not categorized_comments:
                raise ValueError(f"❌ Invalid categorized comments data format")
                
            # Extract the dynamic categories
            dynamic_categories = categorized_comments.get("categorized_comments", {})
            if not dynamic_categories:
                raise ValueError("❌ No categorized comments found in the data")
                
            # Print the structure of the categorized comments
            print_data_structure(dynamic_categories, "Dynamic Categories")
            
            logger.debug(f"Successfully verified categorized comments data exists in MinIO")
            print(f"📋 Found categorized Instagram comment data to analyze")
            
        except Exception as e:
            logger.error(f"❌ Error checking categorized comments data from MinIO: {str(e)}")
            print(f"❌ Error checking categorized comments data from MinIO: {str(e)}")
            return
        
        # Database connection check - ignore errors as this is just for verification
        try:
            session = SessionLocal()
            # Check if user already exists in database
            existing_user = session.query(InstagramUserInfo).filter_by(username=instagram_username).first()
            
            if existing_user:
                print(f"✅ Found existing Instagram user record for {instagram_username}")
                # Check if we have existing LDA topics for this user
                topic_count = session.query(InstagramLDATopic).filter_by(user_id=existing_user.id).count()
                if topic_count > 0:
                    print(f"📊 Found {topic_count} existing LDA topics for {instagram_username}")
            else:
                print(f"⚠️ Instagram user {instagram_username} not found in database.")
                
        except Exception as db_error:
            logger.error(f"❌ Database connection error: {str(db_error)}")
            print(f"❌ Database connection error: {str(db_error)}")
            print("⚠️ Continuing test without database operations...")
        finally:
            if 'session' in locals():
                session.close()
        
        # Run the LDA analysis
        print(f"🔍 Running LDA topic modeling analysis for Instagram user: {instagram_username}")
        
        try:
            # Run the main analysis function with dynamic categories
            await topic_modeling.run_lda_analysis(dynamic_categories)
            
            print(f"✅ LDA topic modeling analysis completed successfully!")
                
        except Exception as analysis_error:
            print(f"❌ Error during LDA topic modeling analysis: {analysis_error}")
            # Print the stack trace
            import traceback
            traceback.print_exc()
        
        # Check if LDA topics file was created in MinIO
        lda_topics_object_name = f"{output_folder}/lda_topics.json"
        wordcloud_object_name = f"{output_folder}/wordcloud.png"
        combined_analysis_object_name = f"{output_folder}/combined_analysis_report.json"
        
        lda_topics_data = minio_service.get_object_data(lda_topics_object_name)
        wordcloud_exists = minio_service.object_exists(wordcloud_object_name)
        
        # Try to get combined analysis but continue if not available
        try:
            combined_analysis_data = minio_service.get_object_data(combined_analysis_object_name)
        except Exception as e:
            print(f"⚠️ Combined analysis report not available: {str(e)}")
            combined_analysis_data = None
        
        if lda_topics_data:
            # Parse the results to show a summary
            lda_topics = json.loads(lda_topics_data.decode('utf-8'))
            
            # Print data structure to understand what was created
            print_data_structure(lda_topics, "LDA Topics Results")
            
            # Check for topics
            total_topics = len(lda_topics)
            
            print(f"📊 LDA Topic Modeling Statistics:")
            print(f"  - Total topics: {total_topics}")
            
            # Print the topics with their keywords
            if lda_topics:
                print("\n📝 LDA Topics with Keywords:")
                for topic_name, topic_data in lda_topics.items():
                    print(f"  Topic: {topic_name}")
                    print(f"  Comment count: {topic_data.get('cantidad_comentarios', 0)}")
                    
                    # Get the top words by weight
                    palabras_con_pesos = topic_data.get("palabras_con_pesos", {})
                    if palabras_con_pesos:
                        # Sort by weight and get top 5
                        top_words = sorted(palabras_con_pesos.items(), key=lambda x: x[1], reverse=True)[:5]
                        print(f"  Top words: {', '.join([f'{word} ({weight:.3f})' for word, weight in top_words])}")
                    
                    print("  " + "-" * 50)
            
            print(f"\n💾 LDA topics data saved to MinIO: {lda_topics_object_name}")
            
            if wordcloud_exists:
                print(f"🖼️ WordCloud image saved to MinIO: {wordcloud_object_name}")
            else:
                print("⚠️ WordCloud image was not generated or saved.")
                
            # Check if combined analysis report was created
            if combined_analysis_data:
                try:
                    combined_analysis = json.loads(combined_analysis_data.decode('utf-8'))
                    print_data_structure(combined_analysis, "Combined Analysis Report")
                    
                    print("\n📑 Combined Analysis Report:")
                    
                    # Print main areas if available
                    if "areas_principales" in combined_analysis:
                        areas = combined_analysis["areas_principales"]
                        print("  📌 Main Topic Areas:")
                        if isinstance(areas, list):
                            for i, area in enumerate(areas[:5]):
                                print(f"    {i+1}. {area}")
                        else:
                            print(f"    {areas}")
                    
                    # Print comparison if available
                    if "comparacion" in combined_analysis:
                        print("  🔄 Comparison between Categories and LDA Topics:")
                        comparison = combined_analysis["comparacion"]
                        if isinstance(comparison, str):
                            # Split long string into multiple lines for better readability
                            lines = [comparison[i:i+80] for i in range(0, len(comparison), 80)]
                            for line in lines[:3]:
                                print(f"    {line}")
                            if len(lines) > 3:
                                print("    ...")
                        elif isinstance(comparison, dict):
                            for key, value in list(comparison.items())[:3]:
                                print(f"    - {key}: {value}")
                        elif isinstance(comparison, list):
                            for i, item in enumerate(comparison[:3]):
                                print(f"    {i+1}. {item}")
                    
                    # Print insights if available
                    if "insights" in combined_analysis:
                        print("  💡 Key Insights:")
                        insights = combined_analysis["insights"]
                        if isinstance(insights, list):
                            for i, insight in enumerate(insights[:3]):
                                print(f"    {i+1}. {insight}")
                            if len(insights) > 3:
                                print(f"    ... and {len(insights)-3} more insights")
                        elif isinstance(insights, dict):
                            for key, value in list(insights.items())[:3]:
                                print(f"    - {key}: {value}")
                        elif isinstance(insights, str):
                            # Split long string into multiple lines for better readability
                            lines = [insights[i:i+80] for i in range(0, len(insights), 80)]
                            for line in lines[:3]:
                                print(f"    {line}")
                            if len(lines) > 3:
                                print("    ...")
                    
                    print(f"\n💾 Combined analysis report saved to MinIO: {combined_analysis_object_name}")
                except json.JSONDecodeError as e:
                    print(f"⚠️ Could not parse combined analysis report: {str(e)}")
            else:
                print("\n⚠️ Combined analysis report was not generated or could not be retrieved. This is optional and doesn't affect the main test.")
            
            # Check database for saved topics - ignore errors as this is just for verification
            try:
                session = SessionLocal()
                # Get the Instagram user from the database
                instagram_user = session.query(InstagramUserInfo).filter_by(username=instagram_username).first()
                if instagram_user:
                    # Count topics in the database
                    db_topics_count = session.query(InstagramLDATopic).filter_by(user_id=instagram_user.id).count()
                    
                    print(f"\n🗄️ Database Storage Check:")
                    print(f"  - LDA Topics stored in database: {db_topics_count}")
                    
                    if db_topics_count > 0:
                        print("\n📝 Sample of LDA Topics in Database:")
                        db_topics = session.query(InstagramLDATopic).filter_by(user_id=instagram_user.id).limit(3).all()
                        for i, topic in enumerate(db_topics):
                            print(f"  {i+1}. {topic.topic_name}")
                            # Try to extract a few top words
                            if hasattr(topic, 'topic_details') and topic.topic_details:
                                try:
                                    palabras = topic.topic_details.get('palabras_con_pesos', {})
                                    if palabras:
                                        top_words = sorted(palabras.items(), key=lambda x: x[1], reverse=True)[:3]
                                        print(f"     Top words: {', '.join([word for word, _ in top_words])}")
                                except:
                                    pass
                else:
                    print("\n⚠️ Instagram user not found in database, cannot check stored topics.")
                    
            except Exception as db_error:
                print(f"❌ Error checking database records: {db_error}")
                print("⚠️ Database operations could not be verified.")
            finally:
                if 'session' in locals():
                    session.close()
            
        else:
            print("⚠️ LDA topic modeling did not produce expected output file.")
    
    except Exception as e:
        logger.exception(f"Unexpected error in test_instagram_topic_modeling function: {str(e)}")
        print(f"❌ Unexpected error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_instagram_topic_modeling()) 