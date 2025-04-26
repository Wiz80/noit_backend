import json
import os
import re
import logging
from typing import Dict, List, Optional
from pathlib import Path
import aisuite as ai
from openai import OpenAI
from dotenv import load_dotenv
from src.utils.load_data import load_competitor_data, load_competitor_questions
from src.core.minio_manager import MinioManager

# Configure environment and logging
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CompetitorAnalyzer:
    """
    Analyzes scraped competitor data to answer business questions using LLMs.
    
    Attributes:
        questions (List[str]): List of business questions to answer
        llm_provider (Dict): Configuration for different LLM providers
        results_dir (Path): Directory to store analysis results
        deepseek_client: DeepSeek API client
    """
    
    def __init__(self, questions: List[str], results_dir: str = "analysis_results", llm_provider: str = "deepseek", llm_model:str = "openai:gpt-4o"):
        self.questions = questions
        self.results_dir = Path(results_dir)
        if llm_provider == "openai" or llm_provider == "claude":
            self.llm = ai.Client()
        elif llm_provider == "deepseek":
            self.llm = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"),
                              base_url="https://api.deepseek.com")
            
        self.llm_model = llm_model
        # Create results directory if needed
        self.minio_manager = MinioManager(bucket_name="web-scraper-cache")

    def _get_competitor_files_from_minio(self, competitor_name: str) -> List[str]:
        """Lista todos los archivos .txt de un competidor en Minio"""
        prefix = f"scraped_data/competitor_analysis/{competitor_name}/"
        try:
            objects = self.minio_manager.list_objects(prefix=prefix)
            return [obj for obj in objects if obj.endswith('.txt')]
        except Exception as e:
            logger.error(f"Error listing objects for {competitor_name}: {str(e)}")
            return []

    def _read_file_from_minio(self, object_name: str) -> str:
        """Obtiene el contenido de un archivo desde Minio"""
        try:
            data = self.minio_manager.get_object_data(object_name)
            return data.decode('utf-8')
        except Exception as e:
            logger.error(f"Error reading {object_name}: {str(e)}")
            return ""

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
                model=self.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            raw_content = response.choices[0].message.content
            cleaned_content = re.sub(r'^\s*```json\s*|\s*```\s*$', '', raw_content, flags=re.DOTALL)
            try:
                parsed_data = json.loads(cleaned_content)
                return parsed_data
            except json.JSONDecodeError as e:
                print(f"Error de parseo: {e}")
                print(f"Contenido problemático: {cleaned_content}")
                cleaned = re.sub(r'[^\x00-\x7F]', '', cleaned_content)
                cleaned = re.sub(r'\s+', ' ', cleaned)
                return json.loads(cleaned)

                
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
        
        # Cargar resultados existentes
        if output_file.exists():
            with open(output_file, 'r') as f:
                results = json.load(f)

        # Obtener archivos desde Minio
        object_names = self._get_competitor_files_from_minio(competitor_name)
        
        for object_name in object_names:
            try:
                content = self._read_file_from_minio(object_name)
                
                prompt = self._create_analysis_prompt(content, self.questions)
                response = self._call_llm(provider, prompt)
                
                if response:
                    results = self._merge_responses(results, response)
                    
                    # Guardar resultados incrementales
                    with open(output_file, 'w') as f:
                        json.dump(results, f, indent=2)
                        
                    logger.info(f"Updated analysis from {object_name.split('/')[-1]}")
                    
            except Exception as e:
                logger.error(f"Error processing {object_name}: {str(e)}")
                continue
                
        return results

    def batch_analyze(
        self,
        competitors: List[str],
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
            logger.info(f"Analyzing {competitor['full_name']}")
            folder_name = competitor['full_name'].lower().replace(" ", "_") 
            results = self.analyze_competitor(folder_name, provider=provider)
            all_results[folder_name] = results
            
        return all_results
    
# Example usage
if __name__ == "__main__":
    
    questions = load_competitor_questions()
    competitors = load_competitor_data()

    provider = 'openai'
    llm_model = 'openai:gpt-4o-mini'
    # Initialize analyzer
    analyzer = CompetitorAnalyzer(questions, llm_provider=provider)
    
    # Run analysis using DeepSeek as default
    results = analyzer.batch_analyze(competitors, provider=provider)
    
    # Save final results
    with open("final_analysis.json", "w") as f:
        json.dump(results, f, indent=2)