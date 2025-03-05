#!/usr/bin/env python
"""
Script to test the state-of-art endpoint with test mode enabled.
This script sends a request to the endpoint and prints the response.

Usage:
    python scripts/test_state_of_art.py <business_id>
"""

import sys
import os
import json
import requests
import time
from datetime import datetime

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_state_of_art(business_id, test_mode=True, test_questions_limit=2, force_update=True):
    """
    Test the state-of-art endpoint with test mode enabled.
    
    Args:
        business_id (str): The ID of the business idea to analyze
        test_mode (bool): Whether to run in test mode
        test_questions_limit (int): The number of questions to process per category in test mode
        force_update (bool): Whether to force a new analysis even if one already exists
    
    Returns:
        dict: The response from the endpoint
    """
    # Get the API base URL from environment or use default
    api_base_url = os.getenv('API_BASE_URL', 'http://localhost:8000')
    
    # Construct the endpoint URL
    endpoint = f"{api_base_url}/api/v1/business-understanding/business/{business_id}/state-of-art"
    
    # Set up the parameters
    params = {
        'test_mode': test_mode,
        'test_questions_limit': test_questions_limit,
        'force_update': force_update,
        'language': 'es'  # Use Spanish for testing
    }
    
    print(f"Testing state-of-art endpoint for business ID: {business_id}")
    print(f"Parameters: {params}")
    print(f"Endpoint: {endpoint}")
    print("Sending request...")
    
    # Record start time
    start_time = time.time()
    
    # Send the request
    response = requests.post(endpoint, params=params)
    
    # Record end time
    end_time = time.time()
    elapsed_time = end_time - start_time
    
    # Print the response status code
    print(f"Response status code: {response.status_code}")
    print(f"Request took {elapsed_time:.2f} seconds")
    
    # If the response is successful, print the response data
    if response.status_code == 200:
        data = response.json()
        print("Response data:")
        print(json.dumps(data, indent=2))
        
        # If the response contains a state_of_art_path, try to download the file
        if 'state_of_art_path' in data:
            print(f"State of art path: {data['state_of_art_path']}")
            
            # Create a directory to save the file
            os.makedirs('test_results', exist_ok=True)
            
            # Save the results to a file
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"test_results/state_of_art_{business_id}_{timestamp}.json"
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
            
            print(f"Results saved to {filename}")
        
        return data
    else:
        print("Error response:")
        print(response.text)
        return None

if __name__ == '__main__':
    # Check if a business ID was provided
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_state_of_art.py <business_id>")
        sys.exit(1)
    
    # Get the business ID from the command line
    business_id = sys.argv[1]
    
    # Get optional parameters
    test_mode = True
    test_questions_limit = 2
    force_update = True
    
    if len(sys.argv) > 2:
        test_mode = sys.argv[2].lower() == 'true'
    
    if len(sys.argv) > 3:
        test_questions_limit = int(sys.argv[3])
        
    if len(sys.argv) > 4:
        force_update = sys.argv[4].lower() == 'true'
    
    # Run the test
    test_state_of_art(business_id, test_mode, test_questions_limit, force_update) 