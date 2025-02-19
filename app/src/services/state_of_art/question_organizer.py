"""
Module for organizing research questions into a structured format.
"""

from typing import Dict, List
import json
from openai import OpenAI

class QuestionOrganizer:
    """Class to organize research questions into a structured format."""
    
    def __init__(self, api_key: str):
        """
        Initialize the QuestionOrganizer.
        
        Args:
            api_key (str): OpenAI API key
        """
        self.client = OpenAI(api_key=api_key)
        
    def organize_questions(self, user_input: str, questions: str) -> Dict:
        """
        Organize questions into a structured format using OpenAI.
        
        Args:
            user_input (str): Original business idea description
            questions (str): Raw questions text
            
        Returns:
            Dict: Organized questions in JSON format
        """
        prompt_1 = r"""
        Given a business idea and a set of research questions, organize them into a structured JSON format.
        create a structured JSON with exactly this format:
        {
            "businessIdea": {
                "description": "<clear business description>",
                "differentiation": "<differentiation goals/needs>",
                "currentStatus": "<current business status>"
            },
            "researchQuestions": {
                "literatureReview": [{"id": "LR<number>", "question": "<question>"}],
                "empiricalStudies": [{"id": "ES<number>", "question": "<question>"}],
                "consumerTrends": [{"id": "CT<number>", "question": "<question>"}],
                "researchMethodologies": [{"id": "RM<number>", "question": "<question>"}],
                "gapAnalysis": [{"id": "GA<number>", "question": "<question>"}],
                "strategicRecommendations": [{"id": "SR<number>", "question": "<question>"}]
            }
        }
        """
        prompt_2 = f"""
        
        Business Idea:
        {user_input}
        
        Questions:
        {questions}
        
        Create a JSON structure where:
        1. Questions are grouped by their main categories (e.g., "Literature Review", "Market Analysis", etc.)
        2. Each question has a unique identifier
        3. Each question maintains its context and relevance to the business idea
        
        Return only the JSON structure without any additional text.
        """

        prompt = prompt_1 + prompt_2
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0
            )
            
            # Clean and parse the response into JSON
            content = response.choices[0].message.content
            # Remove markdown code block indicators if present
            content = content.replace('```json', '').replace('```', '').strip()

            # Parse the response into JSON
            organized_questions = json.loads(content)
            return organized_questions
            
        except Exception as e:
            print(f"Error organizing questions: {str(e)}")
            raise
            
    def save_organized_questions(self, organized_questions: Dict, output_path: str) -> None:
        """
        Save organized questions to a JSON file.
        
        Args:
            organized_questions (Dict): Organized questions in JSON format
            output_path (str): Path to save the JSON file
        """
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(organized_questions, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving organized questions: {str(e)}")
            raise