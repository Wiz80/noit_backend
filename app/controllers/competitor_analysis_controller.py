from app.services.business.competitive_analysis.instagram.instagram_scraper import InstagramScraper
from app.models.business.competitive_analysis.instagram import InstagramScrapingJob
from app.db.session import SessionLocal
import os
from dotenv import load_dotenv

load_dotenv()

class CompetitorAnalysisController:
    """
    Controller for competitor analysis.
    Manages the extraction and processing of competitor data from different platforms.
    """
    
    def __init__(self, business_id):
        """
        Initialize the controller with the business idea ID.
        
        Args:
            business_id (str): Business idea ID
        """
        self.business_id = business_id
        self.instagram_scraper = InstagramScraper(
            api_key=os.getenv("APIFY_API_KEY"),
            output_folder=f"{business_id}/competitor-analysis/instagram"
        )
    
    async def analyze_instagram_competitor(self, username, competitor_id=None, results_limit=10, max_comments=5):
        """
        Analyze a competitor on Instagram.
        
        Args:
            username (str): Instagram username of the competitor
            competitor_id (str, optional): ID of the competitor in the database
            results_limit (int): Maximum number of posts to extract
            max_comments (int): Maximum number of comments per post
            
        Returns:
            dict: Analysis results
        """
        try:
            # Get or create scraping job
            db = SessionLocal()
            scraping_job = None
            
            if competitor_id:
                # Check if there's an existing scraping job
                scraping_job = db.query(InstagramScrapingJob).filter(
                    InstagramScrapingJob.competitor_id == competitor_id,
                    InstagramScrapingJob.username == username
                ).first()
                
                if not scraping_job:
                    # Create a new scraping job
                    scraping_job = InstagramScrapingJob(
                        business_id=self.business_id,
                        competitor_id=competitor_id,
                        username=username,
                        status="pending",
                        results_limit=results_limit,
                        max_comments=max_comments
                    )
                    db.add(scraping_job)
                    db.commit()
                    db.refresh(scraping_job)
            
            # Execute the Instagram scraper
            result = await self.instagram_scraper.run_full_instagram_scraper(
                usernames=[username],
                results_limit=results_limit,
                max_comments=max_comments,
                scraping_job=scraping_job,
                db_session=db
            )
            
            if db:
                db.close()
                
            return {
                "username": username,
                "status": result.get("status", "completed"),
                "message": result.get("message", f"Instagram analysis completed for {username}")
            }
        except Exception as e:
            if db:
                db.close()
                
            return {
                "username": username,
                "status": "failed",
                "error": str(e)
            }
    
    async def analyze_multiple_instagram_competitors(self, usernames, competitor_ids=None, results_limit=10, max_comments=5):
        """
        Analyze multiple competitors on Instagram.
        
        Args:
            usernames (list): List of Instagram usernames
            competitor_ids (list, optional): List of competitor IDs in the database
            results_limit (int): Maximum number of posts to extract
            max_comments (int): Maximum number of comments per post
            
        Returns:
            dict: Analysis results for each competitor
        """
        results = {}
        
        for i, username in enumerate(usernames):
            competitor_id = competitor_ids[i] if competitor_ids and i < len(competitor_ids) else None
            
            result = await self.analyze_instagram_competitor(
                username=username,
                competitor_id=competitor_id,
                results_limit=results_limit,
                max_comments=max_comments
            )
            results[username] = result
        
        return results 