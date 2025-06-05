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
    
    def __init__(self, apify_api_token: Optional[str] = None, timeout_secs: int = 6000):
        """
        Initialize the LinkedIn service with necessary scrapers
        
        Args:
            apify_api_token: The Apify API token to use for all scrapers
            timeout_secs: Timeout in seconds for Apify actor calls
        """
        self.apify_api_token = apify_api_token
        self.timeout_secs = timeout_secs
        self.company_scraper = LinkedInCompanyScraperService(
            apify_api_token=self.apify_api_token,
            timeout_secs=timeout_secs
        )
        self.post_scraper = LinkedInPostScraperService(
            apify_api_token=self.apify_api_token,
            timeout_secs=timeout_secs
        )
        self.ads_scraper = LinkedInAdsScraperService(
            apify_api_token=self.apify_api_token,
            timeout_secs=timeout_secs
        )
        
    async def scrape_competitor_data(self, 
                                     business_id: str, 
                                     competitor,
                                     scrape_company: bool = True, 
                                     scrape_posts: bool = True, 
                                     scrape_ads: bool = True,
                                     timeout_secs: Optional[int] = None,
                                     **kwargs) -> Dict[str, Any]:
        """
        Scrape all LinkedIn data for a competitor
        
        Args:
            business_id: The business ID
            competitor_id: The competitor ID
            linkedin_url: The LinkedIn URL of the competitor
            scrape_company: Whether to scrape company data
            scrape_posts: Whether to scrape posts
            scrape_ads: Whether to scrape ads
            timeout_secs: Optional timeout override for this specific call
            **kwargs: Additional parameters for individual scrapers
            
        Returns:
            Dict containing status and results for each scraping operation
        """

        competitor_name = competitor.competitor_name
        linkedin_url = competitor.linkedin_url
        competitor_id = competitor.id
        
        # Set the timeout for this operation (use parameter or fallback to instance default)
        timeout = timeout_secs or self.timeout_secs

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
                company_name=competitor_name, 
                competitor=competitor,
                isUrl=False, 
                limit=kwargs.get("limit", 5),
                use_proxy=False,
                proxy_country=kwargs.get("proxy_country", "US"),
                timeout_secs=timeout
            )
            
            if company_result["success"] and company_result["count"] > 0:
                save_result = await self.company_scraper.save_to_minio(
                    data=company_result["data"],
                    business_id=business_id,
                    competitor_name=competitor_name.lower()
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
                min_delay=kwargs.get("min_delay", 2),
                max_delay=kwargs.get("max_delay", 8),
                deep_scrape=kwargs.get("deep_scrape", True),
                limit_per_source=kwargs.get("limit", 5),
                use_proxy=kwargs.get("use_proxy", True),
                proxy_country=kwargs.get("proxy_country", "US"),
                timeout_secs=timeout
            )
            
            if post_result["success"] and post_result["count"] > 0:
                save_result = await self.post_scraper.save_to_minio(
                    data=post_result["data"],
                    business_id=business_id,
                    competitor_name=competitor_name.lower()
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
                competitor_name=competitor_name,
                companies=[linkedin_url],
                date_range_type="last-30-days",
                combine_companies_onesearch=False,
                countries=kwargs.get("countries", "ALL"),
                date_type="date_without_range",
                timeout_secs=timeout,
                **kwargs
            )
            
            if ads_result["success"] and ads_result["count"] > 0:
                save_result = await self.ads_scraper.save_to_minio(
                    data=ads_result["data"],
                    business_id=business_id,
                    competitor_name=competitor_name.lower()
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
        
    async def generate_combined_data(self, business_id: str, competitor_ids: List[str], competitor_names: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Generate combined data files from individual competitor data
        
        Args:
            business_id: The business ID
            competitor_ids: List of competitor IDs
            competitor_names: Optional list of competitor names corresponding to the IDs
            
        Returns:
            Dict containing status for each combined data operation
        """
        results = {
            "business_id": business_id,
            "company": {"combined": False},
            "posts": {"combined": False},
            "ads": {"combined": False}
        }
        
        minio_service = MinioService(bucket_name=settings.MINIO_BUCKET_NAME)
        
        # Create a mapping of competitor_id to competitor_name if provided
        competitor_name_map = {}
        if competitor_names and len(competitor_names) == len(competitor_ids):
            competitor_name_map = dict(zip(competitor_ids, competitor_names))
        
        # Combine company data
        try:
            company_data = []
            for competitor_id in competitor_ids:
                # Get competitor name from the map or fallback to helper method
                competitor_name = competitor_name_map.get(competitor_id)
                if not competitor_name:
                    competitor_name = await self._get_competitor_name(business_id, competitor_id)
                if not competitor_name:
                    continue
                    
                path = f"{business_id}/competitor-analysis/linkedin/{competitor_name.lower()}/company.json"
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
                # Get competitor name from the map or fallback to helper method
                competitor_name = competitor_name_map.get(competitor_id)
                if not competitor_name:
                    competitor_name = await self._get_competitor_name(business_id, competitor_id)
                if not competitor_name:
                    continue
                    
                path = f"{business_id}/competitor-analysis/linkedin/{competitor_name.lower()}/post.json"
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
                # Get competitor name from the map or fallback to helper method
                competitor_name = competitor_name_map.get(competitor_id)
                if not competitor_name:
                    competitor_name = await self._get_competitor_name(business_id, competitor_id)
                if not competitor_name:
                    continue
                    
                path = f"{business_id}/competitor-analysis/linkedin/{competitor_name.lower()}/ads.json"
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
        
    async def _get_competitor_name(self, business_id: str, competitor_id: str) -> Optional[str]:
        """
        Helper method to get competitor name from competitor ID.
        This is a fallback method for when competitor names aren't directly provided.
        
        Args:
            business_id: The business ID
            competitor_id: The competitor ID
            
        Returns:
            Competitor name if found, None otherwise
        """
        try:
            # In a real implementation, you would query your database to get the competitor name
            # This is a placeholder that would need to be replaced with actual database access
            # Example:
            # from app.models.business.competitive_analysis.competitors import Competitor
            # from app.api.deps import get_db
            # db = next(get_db())
            # competitor = db.query(Competitor).filter(
            #     Competitor.id == competitor_id,
            #     Competitor.business_id == business_id
            # ).first()
            # return competitor.competitor_name.lower() if competitor else None
            
            logger.warning(
                f"Using placeholder for competitor name with ID {competitor_id}. "
                f"In production, implement proper database lookup."
            )
            return f"competitor_{competitor_id}"
            
        except Exception as e:
            logger.error(f"Error getting competitor name for ID {competitor_id}: {str(e)}")
            # Return a sanitized fallback name that's safe for file paths
            return f"competitor_{competitor_id}" 