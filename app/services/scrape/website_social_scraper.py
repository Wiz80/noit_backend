import os
import json
import logging
import concurrent.futures
import multiprocessing
from functools import partial
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse

# Import ScrapeGraphAI components
from scrapegraphai.graphs import SmartScraperGraph
from playwright.async_api import Error as PlaywrightError, async_playwright
import asyncio

# Logger setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebsiteSocialMediaScraper:
    """
    Service for extracting social media links from competitor websites using ScrapeGraphAI.
    This service uses AI-powered scraping to find social media links from company websites.
    """

    def __init__(
        self, 
        llm_provider: str = "openai", 
        llm_model: str = "gpt-4o-mini", 
        api_key: Optional[str] = None,
        headless: bool = True,
        verbose: bool = False
    ):
        """
        Initialize the WebsiteSocialMediaScraper.
        
        Args:
            llm_provider: The LLM provider to use ('openai', 'ollama', etc.)
            llm_model: The model to use for extraction
            api_key: API key for the LLM provider (if needed)
            headless: Whether to run browser in headless mode
            verbose: Whether to output detailed logs
        """
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        self.api_key = api_key or os.environ.get(f"{llm_provider.upper()}_API_KEY")
        self.headless = headless
        self.verbose = verbose

    def _get_graph_config(self) -> Dict[str, Any]:
        """
        Get the configuration for the ScrapeGraphAI graph.
        
        Returns:
            Dict with configuration settings for the ScrapeGraphAI graph
        """
        config = {
            "llm": {
                "model": f"{self.llm_provider}/{self.llm_model}" if self.llm_provider != "openai" else self.llm_model,
                "model_tokens": 8192
            },
            "verbose": self.verbose,
            "headless": self.headless
        }
        
        # Add API key if provided
        if self.api_key and self.llm_provider in ["openai", "anthropic", "mistral", "groq"]:
            config["llm"]["api_key"] = self.api_key
            
        return config

    def _create_extraction_prompt(self) -> str:
        """
        Create the prompt for social media extraction.
        
        Returns:
            String prompt that tells the AI what to extract
        """
        return """
        Extract all social media links and handles from this website. 
        Look specifically for:
        1. Instagram profile URL and username
        2. Facebook page URL and name
        3. Twitter/X profile URL and handle
        4. LinkedIn company URL and name
        5. YouTube channel URL and name
        6. TikTok profile URL and username
        
        For each social media platform, return both the full URL and the username/handle.
        If a platform is not found, indicate it as "not found".
        
        Format the results as a structured JSON object with the following fields:
        - instagram: {url, username}
        - facebook: {url, name}
        - twitter: {url, handle}
        - linkedin: {url, name}
        - youtube: {url, name}
        - tiktok: {url, username}
        """

    def _normalize_url(self, url: str) -> str:
        """
        Normalize a URL by ensuring it has a proper scheme.
        
        Args:
            url: The URL to normalize
            
        Returns:
            Normalized URL
        """
        if not url:
            return ""
            
        # Add https:// if no scheme is provided
        if not urlparse(url).scheme:
            return f"https://{url}"
        return url

    async def extract_social_media(self, website_url: str) -> Dict[str, Dict[str, str]]:
        """
        Extract social media information from a website.
        
        Args:
            website_url: The URL of the website to scrape
            
        Returns:
            Dictionary containing extracted social media information
        """
        try:
            # Normalize URL
            normalized_url = self._normalize_url(website_url)
            if not normalized_url:
                logger.error(f"Invalid website URL: {website_url}")
                return self._get_empty_result()
                
            logger.info(f"Extracting social media from: {normalized_url}")
            
            # Use a custom implementation instead of SmartScraperGraph
            try:
                # Use playwright directly with custom scraping approach
                social_media = await self._custom_extract_social_media(normalized_url)
                if social_media:
                    logger.info(f"Successfully extracted social media from {normalized_url}")
                    return social_media
                else:
                    # Fallback to SmartScraperGraph in case the direct approach fails
                    logger.info(f"Custom extraction failed, falling back to SmartScraperGraph for {normalized_url}")
                    
                    # Run SmartScraperGraph in a separate thread to avoid event loop conflicts
                    try:
                        # Create the executor for running in a separate thread
                        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                            # Run the extraction in a separate thread
                            result = await asyncio.get_event_loop().run_in_executor(
                                executor, 
                                self._run_smart_scraper_in_thread, 
                                normalized_url
                            )
                            
                            if result:
                                # Process and return the result
                                processed_result = self._process_result(result)
                                logger.info(f"Successfully extracted social media from {normalized_url} using fallback method")
                                return processed_result
                            else:
                                logger.error(f"SmartScraperGraph fallback failed for {normalized_url}")
                                return self._get_empty_result()
                    except Exception as e:
                        logger.error(f"Error in ThreadPoolExecutor for {normalized_url}: {str(e)}")
                        # If thread-based approach fails, try one more fallback with simplified extraction
                        return await self._simplified_extraction(normalized_url)
                
            except (PlaywrightError, Exception) as e:
                logger.error(f"Error scraping {normalized_url}: {str(e)}")
                return self._get_empty_result()
                
        except Exception as e:
            logger.error(f"Unexpected error in extract_social_media: {str(e)}")
            logger.exception(e)
            return self._get_empty_result()

    async def _custom_extract_social_media(self, url: str) -> Dict[str, Dict[str, str]]:
        """
        Custom implementation to extract social media links using Playwright directly.
        
        Args:
            url: Website URL to scrape
            
        Returns:
            Dictionary with social media information
        """
        result = self._get_empty_result()
        
        try:
            # Initialize playwright
            async with async_playwright() as p:
                # Launch browser
                browser = await p.chromium.launch(headless=self.headless)
                
                # Create a new page
                page = await browser.new_page()
                
                # Set a reasonable timeout
                page.set_default_timeout(60000)  # 60 seconds (increased from 30)
                
                # Navigate to the URL
                await page.goto(url, wait_until="domcontentloaded")
                
                # Wait for the page to load
                await page.wait_for_load_state("networkidle")
                
                # Extract social media links
                social_media_selectors = {
                    "instagram": ["a[href*='instagram.com']"],
                    "facebook": ["a[href*='facebook.com']", "a[href*='fb.com']"],
                    "twitter": ["a[href*='twitter.com']", "a[href*='x.com']"],
                    "linkedin": ["a[href*='linkedin.com']"],
                    "youtube": ["a[href*='youtube.com']", "a[href*='youtu.be']"],
                    "tiktok": ["a[href*='tiktok.com']"]
                }
                
                # Find links for each platform
                for platform, selectors in social_media_selectors.items():
                    for selector in selectors:
                        try:
                            links = await page.query_selector_all(selector)
                            
                            if links and len(links) > 0:
                                # Get href attribute
                                for link in links:
                                    href = await link.get_attribute("href")
                                    if href:
                                        # Store the URL
                                        result[platform]["url"] = href
                                        
                                        # Extract username from URL
                                        if platform == "instagram":
                                            parts = href.strip('/').split('/')
                                            if len(parts) > 2:
                                                result[platform]["username"] = parts[-1]
                                        elif platform == "twitter" or platform == "x":
                                            parts = href.strip('/').split('/')
                                            if len(parts) > 2:
                                                result[platform]["username"] = parts[-1]
                                        elif platform == "facebook":
                                            parts = href.strip('/').split('/')
                                            if len(parts) > 2:
                                                result[platform]["username"] = parts[-1]
                                        
                                        # Only store the first one found
                                        break
                        except Exception as e:
                            logger.error(f"Error extracting {platform} links: {str(e)}")
                
                # Close browser
                await browser.close()
                
                # Check if we found any social media
                found_any = any([result[platform]["url"] for platform in social_media_selectors.keys()])
                
                if found_any:
                    return result
                else:
                    return None
                    
        except Exception as e:
            logger.error(f"Error in custom social media extraction: {str(e)}")
            return None

    def _process_result(self, result: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
        """
        Process and normalize the extraction result.
        
        Args:
            result: Raw extraction result from ScrapeGraphAI
            
        Returns:
            Processed and normalized result
        """
        # Initialize empty result structure
        processed = self._get_empty_result()
        
        # If no result or not dict, return empty structure
        if not result or not isinstance(result, dict):
            return processed
            
        # Social media platforms to look for
        platforms = ["instagram", "facebook", "twitter", "linkedin", "youtube", "tiktok"]
        
        # Process each platform
        for platform in platforms:
            # Check if the platform is in the result
            if platform in result:
                platform_data = result[platform]
                
                # If platform data is a dictionary
                if isinstance(platform_data, dict):
                    # Extract URL and username/handle
                    url = platform_data.get("url", "")
                    username_key = "username" if platform in ["instagram", "tiktok"] else "handle" if platform == "twitter" else "name"
                    username = platform_data.get(username_key, "")
                    
                    # Add to processed result
                    processed[platform] = {
                        "url": url.strip() if url else "",
                        "username": username.strip() if username else ""
                    }
                # If platform data is a string (likely a URL)
                elif isinstance(platform_data, str) and platform_data.strip():
                    processed[platform]["url"] = platform_data.strip()
        
        return processed

    def _get_empty_result(self) -> Dict[str, Dict[str, str]]:
        """
        Get an empty result structure.
        
        Returns:
            Empty result dictionary
        """
        return {
            "instagram": {"url": "", "username": ""},
            "facebook": {"url": "", "username": ""},
            "twitter": {"url": "", "username": ""},
            "linkedin": {"url": "", "username": ""},
            "youtube": {"url": "", "username": ""},
            "tiktok": {"url": "", "username": ""}
        }

    async def batch_extract_social_media(self, website_urls: List[str]) -> Dict[str, Dict[str, Dict[str, str]]]:
        """
        Extract social media information from multiple websites.
        
        Args:
            website_urls: List of website URLs to scrape
            
        Returns:
            Dictionary mapping website URLs to their social media information
        """
        results = {}
        
        for url in website_urls:
            try:
                result = await self.extract_social_media(url)
                results[url] = result
            except Exception as e:
                logger.error(f"Error processing {url}: {str(e)}")
                results[url] = self._get_empty_result()
                
        return results

    def _run_smart_scraper_in_thread(self, url: str) -> Dict[str, Any]:
        """
        Run SmartScraperGraph in a separate thread to avoid event loop conflicts.
        
        Args:
            url: Website URL to scrape
            
        Returns:
            Raw extraction results from SmartScraperGraph
        """
        try:
            # Configure SmartScraperGraph with the browser config to use sync mode
            graph_config = self._get_graph_config()
            if "browser" not in graph_config:
                graph_config["browser"] = {}
            
            # Force synchronous mode
            graph_config["browser"]["sync"] = True
            
            # Create SmartScraperGraph instance
            smart_scraper = SmartScraperGraph(
                prompt=self._create_extraction_prompt(),
                source=url,
                config=graph_config
            )
            
            # Execute SmartScraperGraph
            try:
                return smart_scraper.run()
            except Exception as inner_e:
                logger.error(f"Error in SmartScraperGraph run: {str(inner_e)}")
                return None
                
        except Exception as e:
            logger.error(f"Error in _run_smart_scraper_in_thread: {str(e)}")
            return None

    async def _simplified_extraction(self, url: str) -> Dict[str, Dict[str, str]]:
        """
        Final fallback extraction method using simple text search.
        
        Args:
            url: Website URL to scrape
            
        Returns:
            Dictionary with social media information
        """
        try:
            # Initialize playwright
            async with async_playwright() as p:
                # Launch browser with shorter timeout
                browser = await p.chromium.launch(headless=self.headless)
                
                # Create a new page with shorter timeout
                page = await browser.new_page()
                page.set_default_timeout(15000)  # 15 seconds
                
                # Set request timeout
                try:
                    # Navigate to the URL with shorter timeout and less waiting
                    await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    
                    # Get page content
                    content = await page.content()
                    
                    # Close browser
                    await browser.close()
                    
                    # Use simple regex/string search to find social media links
                    result = self._get_empty_result()
                    
                    # Simple patterns to search for
                    patterns = {
                        "instagram": ["instagram.com", "www.instagram.com"],
                        "facebook": ["facebook.com", "www.facebook.com", "fb.com"],
                        "twitter": ["twitter.com", "www.twitter.com", "x.com"],
                        "linkedin": ["linkedin.com", "www.linkedin.com"],
                        "youtube": ["youtube.com", "www.youtube.com", "youtu.be"],
                        "tiktok": ["tiktok.com", "www.tiktok.com"]
                    }
                    
                    # Search for each platform
                    for platform, pattern_list in patterns.items():
                        for pattern in pattern_list:
                            if pattern in content:
                                # Very simple extraction - just note that it exists
                                result[platform]["url"] = f"https://{pattern}"
                                break
                    
                    logger.info(f"Simplified extraction completed for {url}")
                    return result
                    
                except Exception as e:
                    logger.error(f"Error in simplified extraction navigation: {str(e)}")
                    await browser.close()
                    # Final fallback - try through requests instead of browser
                    return await self._fully_sync_extraction(url)
                    
        except Exception as e:
            logger.error(f"Error in simplified extraction browser: {str(e)}")
            # Final fallback - try through requests instead of browser
            return await self._fully_sync_extraction(url)
            
    async def _fully_sync_extraction(self, url: str) -> Dict[str, Dict[str, str]]:
        """
        Completely synchronous fallback extraction using requests.
        This is the final fallback when all browser-based approaches fail.
        
        Args:
            url: Website URL to scrape
            
        Returns:
            Dictionary with social media information
        """
        try:
            # Run the sync code in a thread to not block the event loop
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                result = await asyncio.get_event_loop().run_in_executor(
                    executor,
                    self._sync_extract_with_requests,
                    url
                )
            return result
        except Exception as e:
            logger.error(f"Error in fully sync extraction: {str(e)}")
            return self._get_empty_result()
            
    def _sync_extract_with_requests(self, url: str) -> Dict[str, Dict[str, str]]:
        """
        Extract social media links using the requests library.
        This is a fully synchronous method for ultimate fallback.
        
        Args:
            url: Website URL to scrape
            
        Returns:
            Dictionary with social media information
        """
        import requests
        from requests.exceptions import RequestException
        
        result = self._get_empty_result()
        
        try:
            # Set a timeout for the request
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                # Simple patterns to search for
                patterns = {
                    "instagram": ["instagram.com", "www.instagram.com"],
                    "facebook": ["facebook.com", "www.facebook.com", "fb.com"],
                    "twitter": ["twitter.com", "www.twitter.com", "x.com"],
                    "linkedin": ["linkedin.com", "www.linkedin.com"],
                    "youtube": ["youtube.com", "www.youtube.com", "youtu.be"],
                    "tiktok": ["tiktok.com", "www.tiktok.com"]
                }
                
                content = response.text
                
                # Search for each platform
                for platform, pattern_list in patterns.items():
                    for pattern in pattern_list:
                        if pattern in content:
                            # Very simple extraction - just note that it exists
                            result[platform]["url"] = f"https://{pattern}"
                            break
                
                logger.info(f"Requests-based extraction completed for {url}")
                
            else:
                logger.error(f"Request failed with status code {response.status_code}")
                
        except RequestException as e:
            logger.error(f"RequestException in sync extraction: {str(e)}")
        except Exception as e:
            logger.error(f"General error in sync extraction: {str(e)}")
            
        return result

# Utility function for direct usage
async def extract_social_media_from_website(
    website_url: str,
    llm_provider: str = "openai",
    llm_model: str = "gpt-4o-mini",
    api_key: Optional[str] = None
) -> Dict[str, Dict[str, str]]:
    """
    Utility function to extract social media information from a website.
    
    Args:
        website_url: The URL of the website to scrape
        llm_provider: The LLM provider to use
        llm_model: The model to use for extraction
        api_key: API key for the LLM provider
        
    Returns:
        Dictionary containing extracted social media information
    """
    scraper = WebsiteSocialMediaScraper(
        llm_provider=llm_provider,
        llm_model=llm_model,
        api_key=api_key,
        headless=True
    )
    
    return await scraper.extract_social_media(website_url) 