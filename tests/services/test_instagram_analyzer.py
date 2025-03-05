import os
import asyncio
from app.services.business.competitive_analysis.instagram.instagram_image_analyzer import InstagramImageAnalyzer
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.core.config import settings
import logging

# Set up logging for debugging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def main():
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
        
        print(f"📊 Processing images for Instagram user: {instagram_username}")
        # BREAKPOINT 2: Before processing images
        results = await analyzer.process_images_from_minio(instagram_username)
        
        if results:
            # BREAKPOINT 3: After image processing
            image_count = len(results['images_analyzed'])
            logger.debug(f"Successfully analyzed {image_count} images")
            
            print(f"✅ Analysis completed successfully!")
            print(f"📝 Analyzed {image_count} images")
            print(f"🔍 Analysis report saved to: {output_folder}/{instagram_username}/image_analysis_report.json")
            
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
        logger.exception(f"Unexpected error in main function: {str(e)}")
        print(f"❌ Unexpected error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main()) 