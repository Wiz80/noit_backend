import logging
import json
from typing import Dict, Any, List, Optional

from app.services.business.competitive_analysis.linkedin.linkedin_company_scraper_service import LinkedInCompanyScraperService
from app.services.business.competitive_analysis.linkedin.linkedin_post_scraper_service import LinkedInPostScraperService
from app.services.business.competitive_analysis.linkedin.linkedin_ads_scraper_service import LinkedInAdsScraperService
from app.services.storage.minio_service import MinioService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LinkedInService:
    """
    Comprehensive service for LinkedIn competitor analysis,
    combining company information, posts, and ads
    """
    
    def __init__(self):
        self.company_scraper = LinkedInCompanyScraperService()
        self.post_scraper = LinkedInPostScraperService()
        self.ads_scraper = LinkedInAdsScraperService()
        
    async def scrape_competitor_data(self, business_id: str, competitor_id: str, linkedin_url: str, 
                                    scrape_company: bool = True, scrape_posts: bool = True, 
                                    scrape_ads: bool = True, **kwargs) -> Dict[str, Any]:
        """
        Scrape all LinkedIn data for a competitor
        
        Args:
            business_id: The business ID
            competitor_id: The competitor ID
            linkedin_url: The LinkedIn URL of the competitor
            scrape_company: Whether to scrape company data
            scrape_posts: Whether to scrape posts
            scrape_ads: Whether to scrape ads
            **kwargs: Additional parameters for individual scrapers
            
        Returns:
            Dict containing status and results for each scraping operation
        """
        results = {
            "business_id": business_id,
            "competitor_id": competitor_id,
            "linkedin_url": linkedin_url,
            "company": {"scraped": False},
            "posts": {"scraped": False},
            "ads": {"scraped": False}
        }
        
        # Scrape company data if requested
        if scrape_company:
            company_result = await self.company_scraper.scrape(
                company_name=linkedin_url, 
                isUrl=True, 
                **kwargs
            )
            
            if company_result["success"] and company_result["count"] > 0:
                save_result = await self.company_scraper.save_to_minio(
                    data=company_result["data"],
                    business_id=business_id,
                    competitor_id=competitor_id
                )
                results["company"] = {
                    "scraped": True,
                    "count": company_result["count"],
                    "saved": save_result["success"],
                    "path": save_result.get("path", "")
                }
            else:
                results["company"] = {
                    "scraped": False,
                    "error": company_result.get("error", "No company data found")
                }
        
        # Scrape posts if requested
        if scrape_posts:
            post_result = await self.post_scraper.scrape(
                company_url=linkedin_url,
                **kwargs
            )
            
            if post_result["success"] and post_result["count"] > 0:
                save_result = await self.post_scraper.save_to_minio(
                    data=post_result["data"],
                    business_id=business_id,
                    competitor_id=competitor_id
                )
                results["posts"] = {
                    "scraped": True,
                    "count": post_result["count"],
                    "saved": save_result["success"],
                    "path": save_result.get("path", "")
                }
            else:
                results["posts"] = {
                    "scraped": False,
                    "error": post_result.get("error", "No posts found")
                }
        
        # Scrape ads if requested
        if scrape_ads:
            ads_result = await self.ads_scraper.scrape(
                company_url=linkedin_url,
                **kwargs
            )
            
            if ads_result["success"] and ads_result["count"] > 0:
                save_result = await self.ads_scraper.save_to_minio(
                    data=ads_result["data"],
                    business_id=business_id,
                    competitor_id=competitor_id
                )
                results["ads"] = {
                    "scraped": True,
                    "count": ads_result["count"],
                    "saved": save_result["success"],
                    "path": save_result.get("path", "")
                }
            else:
                results["ads"] = {
                    "scraped": False,
                    "error": ads_result.get("error", "No ads found")
                }
        
        return results
        
    async def generate_combined_data(self, business_id: str, competitor_ids: List[str]) -> Dict[str, Any]:
        """
        Generate combined data files from individual competitor data
        
        Args:
            business_id: The business ID
            competitor_ids: List of competitor IDs
            
        Returns:
            Dict containing status for each combined data operation
        """
        results = {
            "business_id": business_id,
            "company": {"combined": False},
            "posts": {"combined": False},
            "ads": {"combined": False}
        }
        
        minio_service = MinioService(bucket_name="lattice-businesses")
        
        # Combine company data
        try:
            company_data = []
            for competitor_id in competitor_ids:
                path = f"{business_id}/competitor-analysis/linkedin/{competitor_id}/company.json"
                if minio_service.object_exists(path):
                    data = minio_service.download_json(path)
                    if isinstance(data, dict) and "data" in data:
                        company_data.extend(data["data"])
                    else:
                        company_data.append(data)
            
            if company_data:
                combined_path = f"{business_id}/competitor-analysis/linkedin/company.json"
                minio_service.upload_json(combined_path, company_data)
                results["company"] = {
                    "combined": True,
                    "count": len(company_data),
                    "path": combined_path
                }
        except Exception as e:
            results["company"] = {
                "combined": False,
                "error": str(e)
            }
        
        # Combine posts data
        try:
            posts_data = []
            for competitor_id in competitor_ids:
                path = f"{business_id}/competitor-analysis/linkedin/{competitor_id}/post.json"
                if minio_service.object_exists(path):
                    data = minio_service.download_json(path)
                    if isinstance(data, dict) and "data" in data:
                        posts_data.extend(data["data"])
                    else:
                        posts_data.append(data)
            
            if posts_data:
                combined_path = f"{business_id}/competitor-analysis/linkedin/post.json"
                minio_service.upload_json(combined_path, posts_data)
                results["posts"] = {
                    "combined": True,
                    "count": len(posts_data),
                    "path": combined_path
                }
        except Exception as e:
            results["posts"] = {
                "combined": False,
                "error": str(e)
            }
        
        # Combine ads data
        try:
            ads_data = []
            for competitor_id in competitor_ids:
                path = f"{business_id}/competitor-analysis/linkedin/{competitor_id}/ads.json"
                if minio_service.object_exists(path):
                    data = minio_service.download_json(path)
                    if isinstance(data, dict) and "data" in data:
                        ads_data.extend(data["data"])
                    else:
                        ads_data.append(data)
            
            if ads_data:
                combined_path = f"{business_id}/competitor-analysis/linkedin/ads.json"
                minio_service.upload_json(combined_path, ads_data)
                results["ads"] = {
                    "combined": True,
                    "count": len(ads_data),
                    "path": combined_path
                }
        except Exception as e:
            results["ads"] = {
                "combined": False,
                "error": str(e)
            }
        
        return results 