"""
Module for generating answers to research questions using OpenAI and Tavily.
"""

from typing import Dict, List
import json
from openai import OpenAI
from tavily import TavilyClient

class AnswerGenerator:
    """Class to generate answers for research questions using AI and search."""
    
    def __init__(self, openai_api_key: str, tavily_api_key: str):
        """
        Initialize the AnswerGenerator.
        
        Args:
            openai_api_key (str): OpenAI API key
            tavily_api_key (str): Tavily API key
        """
        self.openai_client = OpenAI(api_key=openai_api_key)
        self.tavily_client = TavilyClient(api_key=tavily_api_key)

    def enhance_search_query(self, question: str, business_context: Dict) -> str:
        """Generate an enhanced search query using the business context."""
        prompt = f"""
        Given a research question and business context, create a detailed search query 
        that will help find relevant information.

        Business Context:
        Description: {business_context["description"]}
        Differentiation Goals: {business_context["differentiation"]}
        Current Status: {business_context["currentStatus"]}

        Research Question: {question}

        Create a detailed search query that combines the question with relevant business context.
        Focus on finding specific, actionable information. Return only the search query.
        """

        response = self.openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        return response.choices[0].message.content.strip()
        
    def search_info(self, question: str, business_context: Dict) -> List[Dict]:
        """Search for information using enhanced query."""
        enhanced_query = self.enhance_search_query(question, business_context)
        try:
            search_result = self.tavily_client.search(query=enhanced_query, search_depth="advanced")
            return search_result.get('results', [])
        except Exception as e:
            print(f"Error in search: {str(e)}")
            return []

            
    def generate_answer(self, question: str, business_context: Dict, search_results: List[Dict]) -> str:
        """
        Generate an answer using OpenAI with context and search results.
        
        Args:
            question (str): Question to answer
            context (str): Business idea context
            search_results (List[Dict]): Search results from Tavily
            
        Returns:
            str: Generated answer
        """
        # Prepare search results for the prompt
        search_content = "\n".join([
            f"Source {i+1}: {result.get('content', '')}"
            for i, result in enumerate(search_results[:3])
        ])
        
        prompt = f"""
            Business Context:
            Description: {business_context["description"]}
            Differentiation Goals: {business_context["differentiation"]}
            Current Status: {business_context["currentStatus"]}

            Research Question: {question}

            Available Research:
            {search_content}

            Provide a comprehensive answer that:
            1. Addresses the question with specific insights for this business case
            2. Uses evidence from the research
            3. Gives actionable recommendations
            4. Considers the business's current status and goals
            """
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"Error generating answer: {str(e)}")
            raise
            
    def process_all_questions(self, 
                            organized_questions: Dict, 
                            business_context: str,
                            output_path: str) -> None:
        """
        Process all questions and save answers to a file.
        
        Args:
            organized_questions (Dict): Organized questions in JSON format
            business_context (str): Original business idea description
            output_path (str): Path to save the results
        """
        results = {
            "business_context": organized_questions["businessIdea"],
            "categories": {}
        }
        
        try:
            business_context = organized_questions["businessIdea"]
            for category, questions in organized_questions["researchQuestions"].items():
                results["categories"][category] = []
                for question_data in questions:
                    search_results = self.search_info(
                        question_data["question"],
                        business_context
                    )
                    
                    answer = self.generate_answer(
                        question_data["question"],
                        business_context,
                        search_results
                    )
                    
                    results["categories"][category].append({
                        "question_id": question_data["id"],
                        "question": question_data["question"],
                        "answer": answer
                    })
                    print(f"Processed question {question_data['id']}")
                    
            # Save results
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=4, ensure_ascii=False)
                
        except Exception as e:
            print(f"Error processing questions: {str(e)}")
            raise