import os
import json
import logging
import uuid
import requests
import base64
from dataclasses import dataclass
from typing import Dict, Optional, List, Any, Union

from dotenv import load_dotenv
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ResearchConfig:
    """Configuration for the research module"""
    model: str  # Can be "sonar", "mistral", etc. for Perplexity models
    language: str = "en"
    max_iterations: int = 1

class ResearchModule:
    """
    Module for conducting web research using n8n webhook
    
    This module replaces the previous implementation that used direct API calls
    with a version that uses an n8n workflow via webhook.
    """
    
    def __init__(self, config: ResearchConfig):
        self.config = config
        self.language = config.language
        # Debug the environment variable value
        webhook_url_from_env = os.getenv("N8N_WEBHOOK_URL")
        logger.info(f"N8N_WEBHOOK_URL from environment: {webhook_url_from_env}")
        
        self.n8n_webhook_url = os.getenv("N8N_WEBHOOK_URL", "https://masterchief.app.n8n.cloud/webhook-test/b1cc2ce8-d4c9-44ff-b56f-0f0b86b62d04")
        self.n8n_auth_header = os.getenv("N8N_AUTH_HEADER", "auth_user")
        
        # Get timeout from environment or use default value
        self.webhook_timeout = int(os.getenv("N8N_WEBHOOK_TIMEOUT", "60"))
        logger.info(f"Using webhook timeout: {self.webhook_timeout} seconds")
        
        # Log the final URL being used
        logger.info(f"Using n8n webhook URL: {self.n8n_webhook_url}")
        
        # Verificar que las configuraciones clave estén presentes
        if not self.n8n_webhook_url:
            logger.warning("N8N_WEBHOOK_URL no está configurada, usando URL por defecto")
        
        if not self.n8n_auth_header:
            logger.warning("N8N_AUTH_HEADER no está configurada, usando valor por defecto")
            
    async def research(self, query: str) -> str:
        """
        Perform web research on the given query
        
        Args:
            query: The research query
            
        Returns:
            A string containing the research results
        """
        try:
            logger.info(f"Starting research on query: {query[:50]}...")
            
            # Instead of awaiting the result, just make the HTTP call to n8n
            # This doesn't need to be awaited since we're using requests directly
            # and we only care about initiating the request, not the final research result
            # n8n will call our callback URL when it's done
            result = self._call_n8n_webhook(query)
            
            # Just return the request ID or a status message
            return result.get("request_id", "Research request submitted")
            
        except Exception as e:
            logger.error(f"Research error: {str(e)}")
            return f"Error starting research: {str(e)}"
    
    async def search_and_answer(self, query: str) -> Dict[str, Any]:
        """
        Perform web research and return both the answer and sources
        
        Args:
            query: The research query
            
        Returns:
            Dict containing a message about the request and empty sources
        """
        try:
            response = self._call_n8n_webhook(query)
            return {
                "answer": response['text'],
                "sources": response.get('citations', []),
                "request_id": response.get('request_id')
            }
        except Exception as e:
            logger.error(f"search_and_answer failed: {str(e)}")
            return {
                "answer": f"Error during research: {str(e)}",
                "sources": []
            }
    
    def _call_n8n_webhook(self, research_query: str) -> Dict[str, Any]:
        """
        Call the n8n webhook to perform the research
        
        Args:
            research_query: The query to research (can contain callback URL as JSON)
            
        Returns:
            Dict containing the research results
        """
        # Debug: Log the webhook URL before making the request
        logger.info(f"Webhook URL before request: {self.n8n_webhook_url}")
        
        headers = {
            "Authorization": f"Basic {self.n8n_auth_header}",
            "Content-Type": "application/json"
        }
        
        # Check if research_query is a JSON string containing callback info
        try:
            query_data = json.loads(research_query)
            # Extract the actual search query and callback info
            search_query = query_data.get("search_query", research_query)
            callback_url = query_data.get("callback_url")
            request_id = query_data.get("request_id")
            business_id = query_data.get("business_id")
            
            # Prepare data payload with callback info if available
            data = {
                "id": request_id or str(uuid.uuid4()),
                "lang": self.language,
                "answer": "api",
                "research": search_query,
                "require_validation": "true",
                "model": self.config.model
            }
            
            # Include callback information if available
            if callback_url:
                data["callback_url"] = callback_url
                data["request_id"] = request_id
                data["business_id"] = business_id
                logger.info(f"Including callback URL in request: {callback_url}")
            
        except (json.JSONDecodeError, TypeError):
            # If not JSON, use the query directly
            data = {
                "id": str(uuid.uuid4()),
                "lang": self.language,
                "answer": "api",
                "research": research_query,
                "require_validation": "true",
                "model": self.config.model
            }
                
        logger.info(f"Calling n8n webhook with data: {json.dumps(data)[:200]}...")
        
        try:
            # Debug: Log the exact URL being used in the request
            request_url = self.n8n_webhook_url
            logger.info(f"Making request to URL: {request_url}")
            
            # Start a thread to make the request in the background
            # This way we don't block the main thread waiting for the response
            import threading
            
            def make_request():
                try:
                    response = requests.post(
                        request_url,
                        headers=headers,
                        json=data,
                        timeout=self.webhook_timeout
                    )
                    # Log response status
                    logger.info(f"Background request completed with status: {response.status_code}")
                    return response
                except Exception as req_error:
                    logger.error(f"Background request error: {str(req_error)}")
                    return None
            
            # Start the request in a background thread and continue immediately
            thread = threading.Thread(target=make_request)
            thread.daemon = True  # Make thread a daemon so it doesn't block program exit
            thread.start()
            
            logger.info(f"Request initiated in background thread for ID: {data['id']}")
            
            # Return immediately with just the request ID
            return {
                "text": f"Research request submitted with ID: {data['id']}. Processing asynchronously.",
                "citations": [],
                "request_id": data['id']
            }
            
        except Exception as e:
            logger.error(f"Error setting up n8n webhook call: {str(e)}")
            # Provide a meaningful error response
            return {
                "text": f"Error initiating research request: {str(e)}",
                "citations": [],
                "request_id": data.get('id', str(uuid.uuid4())),
                "error": str(e)
            } 