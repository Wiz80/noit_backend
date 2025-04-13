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
    perplexity_api_key: Optional[str] = None
    validator_api_keys: Optional[Dict[str, str]] = None
    validator_model: str = "openai:gpt-4o-mini"
    language: str = "en"
    max_iterations: int = 1
    temperature: float = 0.7
    require_validation: str = "false"
    validate_existance: str = "false"
    model: str = "llama3"  # Default model to use for perplexity

class ResearchModule:
    """
    Module for conducting web research using n8n webhook
    
    This module replaces the previous implementation that used direct API calls
    with a version that uses an n8n workflow via webhook.
    """
    
    def __init__(self, config: ResearchConfig, model_validator: str = "openai"):
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
        
        # Get callback API URL from environment
        self.api_callback_base_url = os.getenv("API_CALLBACK_BASE_URL", "http://localhost:8000")
        
        # Verificar que las configuraciones clave estén presentes
        if not self.n8n_webhook_url:
            logger.warning("N8N_WEBHOOK_URL no está configurada, usando URL por defecto")
        
        if not self.n8n_auth_header:
            logger.warning("N8N_AUTH_HEADER no está configurada, usando valor por defecto")
            
    async def research(self, 
                       query: Union[dict, str], 
                       business_id: Optional[str] = None, 
                       competitor_id: Optional[str] = None, 
                       task_id: Optional[str] = None) -> str:
        """
        Perform web research on the given query
        
        Args:
            query: The research query (can be a string or a dict with search_query key)
            business_id: ID of the business idea (optional)
            competitor_id: ID of the competitor (optional)
            task_id: ID of the task (optional)
            
        Returns:
            A string containing the research results
        """
        try:
            # Prepare the query data based on input type
            if isinstance(query, dict):
                search_query = query.get("search_query", "")
                callback_data = query
                research_type = query.get("research_type", "general")
                logger.info(f"Starting research on query from dict: {search_query[:50]}...")
            else:
                # If query is a string, create a query dict
                search_query = query
                callback_data = {"search_query": query}
                research_type = "general"
                logger.info(f"Starting research on string query: {search_query[:50]}...")
            
            # Generate a request ID if not provided
            request_id = str(uuid.uuid4())
            callback_data["request_id"] = request_id
            
            # Generate callback URL based on research type
            callback_url = None
            
            # If we have a specific callback URL in the query dict, use that
            if "callback_url" in callback_data:
                callback_url = callback_data["callback_url"]
                logger.info(f"Using provided callback URL: {callback_url}")
            else:
                # Otherwise generate based on the type
                if research_type == "market_research" or research_type == "state_of_art":
                    if business_id and task_id:
                        callback_url = f"{self.api_callback_base_url}/api/v1/business/{business_id}/research-callback/{task_id}"
                        logger.info(f"Generated business understanding callback URL: {callback_url}")
                elif business_id and competitor_id:
                    callback_url = f"{self.api_callback_base_url}/api/v1/business/{business_id}/competitor-analysis/research-callback"
                    logger.info(f"Generated competitor analysis callback URL: {callback_url}")
                else:
                    # Default callback for general research
                    callback_url = f"{self.api_callback_base_url}/api/v1/research-callback"
                    logger.info(f"Generated default callback URL: {callback_url}")
            
            # Set the callback URL in the data
            if callback_url:
                callback_data["callback_url"] = callback_url
            
            # Add business_id if provided
            if business_id:
                callback_data["business_id"] = business_id
                
            # Add competitor_id if provided
            if competitor_id:
                callback_data["competitor_id"] = competitor_id
                
            # Add task_id if provided
            if task_id:
                callback_data["task_id"] = task_id
            
            # Add research_type if available
            if research_type:
                callback_data["research_type"] = research_type
            
            # Make the HTTP call to n8n
            result = self._call_n8n_webhook(callback_data)
            
            # Return the request ID or a status message
            return result.get("text", "Research request submitted")
            
        except Exception as e:
            logger.error(f"Research error: {str(e)}")
            return f"Error starting research: {str(e)}"
    
    async def search_and_answer(self, 
                                query: dict, 
                                business_id: Optional[str] = None, 
                                competitor_id: Optional[str] = None, 
                                task_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Perform web research and return both the answer and sources
        
        Args:
            query: The research query
            business_id: ID of the business idea (optional)
            competitor_id: ID of the competitor (optional)
            task_id: ID of the task (optional)
            
        Returns:
            Dict containing a message about the request and empty sources
        """
        try:

            callback_url = f"{self.api_callback_base_url}/api/v1/business/{business_id}/competitor-analysis/research-callback"
            query["callback_url"] = callback_url
            
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
    
    def _call_n8n_webhook(self, research_query: Union[dict, str]) -> Dict[str, Any]:
        """
        Call the n8n webhook to perform the research
        
        Args:
            research_query: The query to research (dict or JSON string)
            
        Returns:
            Dict containing the research results
        """
        # Debug: Log the webhook URL before making the request
        logger.info(f"Webhook URL before request: {self.n8n_webhook_url}")
        
        headers = {
            "Authorization": f"Basic {self.n8n_auth_header}",
            "Content-Type": "application/json"
        }
        
        # Process the research query
        try:
            # If research_query is a string, try to parse it as JSON
            if isinstance(research_query, str):
                try:
                    query_data = json.loads(research_query)
                except json.JSONDecodeError:
                    # If not valid JSON, use it directly as the search query
                    query_data = {
                        "id": str(uuid.uuid4()),
                        "lang": self.language,
                        "answer": "api",
                        "research": research_query,
                        "require_validation": self.config.require_validation,
                        "model": self.config.model,
                        "depth": self.config.max_iterations,
                        "validate_existance": self.config.validate_existance
                    }
            else:
                # Research query is already a dictionary
                query_data = research_query
            
            # Extract the actual search query and callback info
            search_query = query_data.get("search_query", "")
            if not search_query and "research" in query_data:
                search_query = query_data.get("research", "")
            
            callback_url = query_data.get("callback_url")
            request_id = query_data.get("request_id", str(uuid.uuid4()))
            business_id = query_data.get("business_id")
            competitor_id = query_data.get("competitor_id")
            task_id = query_data.get("task_id")
            
            # Prepare data payload
            data = {
                "id": request_id,
                "lang": self.language,
                "answer": "api",
                "require_validation": self.config.require_validation,
                "model": self.config.model,
                "depth": self.config.max_iterations,
                "validate_existance": self.config.validate_existance,
                "research": search_query,
                "base_url": self.api_callback_base_url
            }
            
            # Include callback information if available
            if callback_url:
                data["callback_url"] = callback_url
            
            # Include additional metadata for the callback
            if business_id:
                data["business_id"] = business_id
            if competitor_id:
                data["competitor_id"] = competitor_id
            if task_id:
                data["task_id"] = task_id
                
            if callback_url:
                logger.info(f"Including callback URL in request: {callback_url}")
            
        except Exception as e:
            logger.error(f"Error processing research query: {str(e)}")
            data = {
                "id": str(uuid.uuid4()),
                "lang": self.language,
                "answer": "api",
                "research": str(research_query),
                "require_validation": self.config.require_validation,
                "model": self.config.model,
                "depth": self.config.max_iterations,
                "validate_existance": self.config.validate_existance
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