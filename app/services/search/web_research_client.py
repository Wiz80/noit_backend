import os
import json
import logging
import uuid
import requests
import asyncio
from dataclasses import dataclass
from typing import Dict, Optional, List, Any, Union

from dotenv import load_dotenv
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class WebResearchConfig:
    """Configuration for the web research client"""
    web_research_base_url: Optional[str] = None
    timeout: int = 800  # Increased from 60 to 300 seconds (5 minutes) for complex research
    language: str = "en"

class WebResearchClient:
    """
    Client for conducting web research using the noit-web-research-system
    
    This client replaces the n8n-based research with the new CrewAI-based
    web research application.
    """
    
    def __init__(self, config: WebResearchConfig):
        self.config = config
        self.language = config.language
        
        # Get web research app base URL from environment
        # Use host.docker.internal by default for Docker connectivity
        self.web_research_base_url = os.getenv("WEB_RESEARCH_BASE_URL", "http://host.docker.internal:8001")
        self.timeout = config.timeout
        
        # Get callback API URL from environment
        # Use CALLBACK_BASE_URL for consistency with the endpoint
        # For web-research-system (host) to callback to backend (Docker): use localhost:8000
        self.api_callback_base_url = os.getenv("CALLBACK_BASE_URL", os.getenv("API_CALLBACK_BASE_URL", "http://localhost:8000"))
        
        logger.info(f"WebResearchClient initialized with base URL: {self.web_research_base_url}")
        logger.info(f"Callback API URL: {self.api_callback_base_url}")
        
        # Verify configuration
        if not self.web_research_base_url:
            logger.warning("WEB_RESEARCH_BASE_URL not configured, using default host.docker.internal")
            
    async def research(self, research_request: Dict[str, Any]) -> str:
        """
        Perform web research by sending a pre-formatted research request
        to the web research system.
        
        Args:
            research_request: The research request payload, expected to match
                              the ResearchCreateRequest schema of the target service.
            
        Returns:
            A string containing a confirmation message or an error.
        """
        try:
            logger.info(f"Prepared research request for web research system with model: {research_request.get('perplexity_model')}")
            
            # Make the HTTP call to the web research system
            result = await self._call_web_research_api(research_request)
            
            # Return the research ID or a status message
            return result.get("message", f"Research request submitted with ID: {result.get('id', 'unknown')}")
            
        except Exception as e:
            logger.error(f"Research error: {str(e)}")
            return f"Error starting research: {str(e)}"
    
    async def _call_web_research_api(self, research_request: dict) -> Dict[str, Any]:
        """
        Call the web research system API to perform the research
        
        Args:
            research_request: The research request payload
            
        Returns:
            Dict containing the API response
        """
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Prepare the API endpoint
        research_endpoint = f"{self.web_research_base_url}/api/v1/research"
        
        logger.info(f"Calling web research API at: {research_endpoint}")
        logger.info(f"Research request payload: {json.dumps(research_request, indent=2)}")
        
        try:
            # Use asyncio with requests in a thread pool for async compatibility
            loop = asyncio.get_event_loop()
            
            def make_request():
                response = requests.post(
                    research_endpoint,
                    headers=headers,
                    json=research_request,
                    timeout=self.timeout
                )
                return response
            
            # Execute the request in a thread pool
            response = await loop.run_in_executor(None, make_request)
            
            if response.status_code == 201:
                response_data = response.json()
                logger.info(f"✅ Web research request successful: {response.status_code}")
                logger.info(f"Response: {json.dumps(response_data, indent=2)}")
                return response_data
            else:
                logger.error(f"❌ Web research request failed: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return {
                    "error": f"API request failed with status {response.status_code}",
                    "message": f"Research request failed: {response.text}",
                    "status_code": response.status_code
                }
                
        except requests.exceptions.Timeout:
            logger.error(f"⏰ Web research API timeout")
            return {
                "error": "API timeout",
                "message": "Research request timed out"
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"🌐 Web research API request error: {str(e)}")
            return {
                "error": f"Request error: {str(e)}",
                "message": f"Research request failed: {str(e)}"
            }
        except Exception as e:
            logger.error(f"💥 Unexpected error calling web research API: {str(e)}")
            return {
                "error": f"Unexpected error: {str(e)}",
                "message": f"Research request failed: {str(e)}"
            } 