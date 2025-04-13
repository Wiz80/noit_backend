from mage_ai.data_preparation.decorators import data_loader, data_exporter
from mage_ai.data_preparation.shared.secrets import get_secret_value
import requests
import json
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@data_loader
def load_research_data(*args, **kwargs):
    """
    Load research data from the trigger payload
    This function will be called when the pipeline is triggered
    
    Returns:
        dict: Research data
    """
    # Get data from the trigger or kwargs
    data = kwargs.get('data', {})
    
    if not data:
        logger.warning("No data provided in trigger")
        return {}
    
    logger.info(f"Received research data: {data.keys()}")
    return data

@data_loader
def validate_research_data(data, *args, **kwargs):
    """
    Validate the research data
    
    Args:
        data (dict): Research data from previous step
        
    Returns:
        dict: Validated data
    """
    # Check required fields
    required_fields = ['request_id', 'business_id', 'competitor_id']
    missing_fields = [field for field in required_fields if field not in data]
    
    if missing_fields:
        error_message = f"Missing required fields: {', '.join(missing_fields)}"
        logger.error(error_message)
        return {
            'status': 'error',
            'message': error_message
        }
    
    logger.info(f"Validated research data for request_id: {data.get('request_id')}")
    return data

@data_exporter
def process_instagram_research(data, *args, **kwargs):
    """
    Process Instagram research data
    This function will call the FastAPI callback endpoint
    
    Args:
        data (dict): Research data from previous steps
        
    Returns:
        dict: Processing result
    """
    if data.get('status') == 'error':
        logger.error(f"Cannot process research data: {data.get('message')}")
        return data
    
    try:
        # Get API base URL from environment or config
        api_base_url = os.getenv('API_BASE_URL', 'http://localhost:8000')
        business_id = data.get('business_id')
        
        # Prepare callback data
        callback_data = {
            'request_id': data.get('request_id'),
            'business_id': data.get('business_id'),
            'competitor_id': data.get('competitor_id'),
            'task_id': data.get('task_id'),
            'research_results': data.get('research_results', {})
        }
        
        # Call the FastAPI callback endpoint
        callback_url = f"{api_base_url}/api/v1/business/{business_id}/competitor-analysis/research-callback"
        logger.info(f"Calling callback URL: {callback_url}")
        
        response = requests.post(
            url=callback_url,
            json=callback_data,
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code != 200:
            logger.error(f"Error calling callback URL: {response.status_code} - {response.text}")
            return {
                'status': 'error',
                'message': f"Error calling callback: {response.status_code}",
                'response': response.text
            }
        
        # Parse and return the response
        result = response.json()
        logger.info(f"Callback successful: {result}")
        return {
            'status': 'success',
            'message': 'Research data processed successfully',
            'callback_result': result
        }
        
    except Exception as e:
        logger.exception(f"Error processing research data: {str(e)}")
        return {
            'status': 'error',
            'message': f"Exception: {str(e)}"
        } 
    

# openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                    

#                         # We need the information in json format parsed as expected
#                         response = openai_client.chat.completions.create(
#                             model="gpt-4o-mini",
#                             messages=[
#                                 {"role": "system", "content": """You are a helpful assistant that parses information from a web ai research. You need to parse the information from the research and return it in a json format.
#                                  The json should be like this:
#                                  {
#                                      "full_name": "string", # Competitor's Full Name
#                                      "key_feature": "string", # Competitor's Key Feature (Value Proposition)
#                                      "website": "url", # Competitor's Website URL
#                                      "instagram_url": "handle", # Instagram handle (if available)
#                                      "facebook_url": "handle", # Facebook handle (if available)
#                                      "linkedin_url": "handle", # LinkedIn URL (if available)
#                                      "x_url": "handle", # Twitter/X handle (if available)
#                                      "youtube_url": "handle", # YouTube channel (if available)
#                                      "tiktok_url": "handle", # TikTok handle (if available)
#                                      "similarity_score": 1-100 # Similarity score with the business idea
#                                   }
#                                  """
#                                 },
#                                 {"role": "user", "content": research_results}
#                             ],
#                             response_format={
#                                 "type": "json_object"
#                             }
#                         )

#                         #Get the json from the response
#                         research_results = response.choices[0].message.content

#                         # Parse the json
#                         research_results = json.loads(research_results)