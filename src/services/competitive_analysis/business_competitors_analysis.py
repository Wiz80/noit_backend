"""
Module: competitor_analyzer.py

Responsible for analyzing scraped competitor data to answer business questions using multiple LLMs.
Uses aisuite for OpenAI/Claude and DeepSeek's API directly based on provided documentation.
"""

import json
import os
import logging
from typing import Dict, List, Optional
from pathlib import Path
import aisuite as ai
from openai import OpenAI
from dotenv import load_dotenv
from src.utils.load_data import load_competitor_data, load_competitor_questions

# Configure environment and logging
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CompetitorAnalyzer:
    """
    Analyzes scraped competitor data to answer business questions using LLMs.
    
    Attributes:
        questions (List[str]): List of business questions to answer
        llm_providers (Dict): Configuration for different LLM providers
        results_dir (Path): Directory to store analysis results
        deepseek_client: DeepSeek API client
    """
    
    def __init__(self, questions: List[str], results_dir: str = "analysis_results", llm_provider: str = "deepseek"):
        self.questions = questions
        self.results_dir = Path(results_dir)
        if llm_provider == "openai" or llm_provider == "claude":
            self.llm = ai.Client()
        elif llm_provider == "deepseek":
            self.llm = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"),
                              base_url="https://api.deepseek.com")
        # Create results directory if needed
        self.results_dir.mkdir(exist_ok=True)


    def _create_analysis_prompt(self, content: str, questions: List[str]) -> str:
        """
        Create prompt for analyzing competitor content.
        
        Args:
            content: Scraped website content
            questions: List of questions to answer
            
        Returns:
            Formatted analysis prompt
        """
        return f"""
        Analyze this competitor website content and answer the following questions.
        Rules:
        1. Only use information from the provided content
        2. Be concise and factual
        3. Skip questions without sufficient information
        4. Use Markdown formatting for answers

        Content:
        {content[:15000]} 

        Questions:
        {chr(10).join(f"{i+1}. {q}" for i, q in enumerate(questions))}

        Format response as JSON with:
        {{
            "answers": {{
                "question1": "answer1",
                "question2": "answer2"
            }},
            "unanswered": ["question3", "question4"]
        }}
        """

    def _call_llm(self, provider: str, prompt: str) -> Optional[Dict]:
        """
        Execute LLM call with proper error handling.
        
        Args:
            provider: LLM provider (openai|claude|deepseek)
            prompt: Analysis prompt
            
        Returns:
            Parsed JSON response or None
        """
        try:
            response = self.llm.chat.completions.create(
                model=self.validator_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            return json.loads(response.choices[0].message.content)
                
        except Exception as e:
            logger.error(f"{provider} analysis failed: {str(e)}")
            return None

    def _merge_responses(self, existing: Dict, new: Dict) -> Dict:
        """
        Merge analysis results from multiple scrapes.
        
        Args:
            existing: Current analysis state
            new: New analysis results
            
        Returns:
            Merged analysis dictionary
        """
        merged = existing.copy()
        
        # Merge answers
        for q, a in new.get('answers', {}).items():
            if q not in merged['answers']:
                merged['answers'][q] = a
            else:
                merged['answers'][q] += f"\n\nAdditional info: {a}"
                
        # Update unanswered questions
        merged['unanswered'] = [
            q for q in merged['unanswered']
            if q not in new.get('answers', {})
        ]
        
        return merged

    def analyze_competitor(
        self,
        competitor_name: str,
        scraped_files: List[str],
        provider: str = 'deepseek'
    ) -> Dict:
        """
        Analyze all scraped files for a competitor.
        
        Args:
            competitor_name: Name of competitor being analyzed
            scraped_files: List of paths to scraped files
            provider: LLM provider to use
            
        Returns:
            Complete analysis results
        """
        results = {'answers': {}, 'unanswered': self.questions.copy()}
        output_file = self.results_dir / f"{competitor_name}_analysis.json"
        
        # Load existing results if available
        if output_file.exists():
            with open(output_file, 'r') as f:
                results = json.load(f)

        for file_path in scraped_files:
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                    
                prompt = self._create_analysis_prompt(content, self.questions)
                response = self._call_llm(provider, prompt)
                
                if response:
                    results = self._merge_responses(results, response)
                    
                    # Save incremental results
                    with open(output_file, 'w') as f:
                        json.dump(results, f, indent=2)
                        
                    logger.info(f"Updated analysis from {Path(file_path).name}")
                    
            except Exception as e:
                logger.error(f"Error processing {file_path}: {str(e)}")
                continue
                
        return results

    def batch_analyze(
        self,
        competitors: List[Dict],
        provider: str = 'deepseek'
    ) -> Dict[str, Dict]:
        """
        Analyze multiple competitors.
        
        Args:
            competitors: List of competitor dicts with name and scraped_files
            provider: LLM provider to use
            
        Returns:
            Dictionary of analysis results per competitor
        """
        all_results = {}
        
        for competitor in competitors:
            logger.info(f"Analyzing {competitor['name']}")
            results = self.analyze_competitor(
                competitor['name'],
                competitor['scraped_files'],
                provider
            )
            all_results[competitor['name']] = results
            
        return all_results

# Example usage
if __name__ == "__main__":
    
    questions = load_competitor_questions()
    competitors = load_competitor_data()
    # Initialize analyzer
    analyzer = CompetitorAnalyzer(questions)

    
    competitors = [{
        "name": "competitor_A",
        "scraped_files": [
            "scraped_data/competitor_A_page1.txt",
            "scraped_data/competitor_A_page2.txt"
        ]
    }]
    
    # Run analysis using DeepSeek as default
    results = analyzer.batch_analyze(competitors)
    
    # Save final results
    with open("final_analysis.json", "w") as f:
        json.dump(results, f, indent=2)