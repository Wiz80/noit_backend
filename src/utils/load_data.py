import json
from typing import Dict, List
import logging
import os

logger = logging.getLogger(__name__)

def load_latest_data(start_with_name: str) -> Dict:
     
    files = [f for f in os.listdir('.') if f.startswith(start_with_name)]
    if not files:
        raise FileNotFoundError(f"No files found starting with {start_with_name}")
    
    latest_file = max(files)  # Gets the most recent file
    logger.info(f"Processing file: {latest_file}")

    try:
        with open(latest_file, 'r') as f:
            data = json.load(f)
        return data
    except Exception as e:
        logger.error(f"Error loading data: {str(e)}")
        raise

def load_competitor_data() -> List[Dict]:
        """
        Load competitor data from JSON file
        
        Args:
            json_path: Path to competitor analysis JSON
            
        Returns:
            List of competitor data dictionaries
        """
        return load_latest_data('competitor_analysis_')

def load_competitor_questions() -> List[Dict]:
        """
        Load competitor questions from JSON file
        
        Args:
            json_path: Path to competitor questions JSON
            
        Returns:
            List of competitor questions
        """
        # Example competitor questions (replace with actual questions)
        return load_latest_data('competitor_questions_')