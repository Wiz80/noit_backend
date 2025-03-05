from typing import Dict
import json
from openai import OpenAI
import aisuite as ai
from dataclasses import dataclass
import time
from dataclasses import dataclass
import os
from dotenv import load_dotenv  
import logging

logging.basicConfig(level=logging.INFO)

load_dotenv()

@dataclass
class ResearchConfig:
    """Configuration class for the research module"""
    perplexity_api_key: str
    validator_api_keys: Dict[str, str]
    validator_model: str
    language: str = "en"  # "en" for English, "es" for Spanish
    max_iterations: int = 3
    temperature: float = 0.7

class ResearchModule:
    """
    A module that combines Perplexity for web search and DeepSeek for validation
    and completion of research questions.
    """
    
    def __init__(self, config: ResearchConfig, model_validator: str = "openai"):
        """
        Initialize the research module with API clients and configuration.
        
        Args:
            config: ResearchConfig object containing API keys and settings
        """
        self.config = config
        self.perplexity_client = OpenAI(
            api_key=config.perplexity_api_key,
            base_url="https://api.perplexity.ai"
        )
        
        if model_validator == "openai" or model_validator == "claude":
            self.validator_client = ai.Client()
        elif model_validator == "deepseek":
            self.validator_client = OpenAI(api_key=config.validator_api_keys["deepseek"],
                                           base_url="https://api.deepseek.com")
        
    def get_system_prompt(self, is_validation: bool = False) -> str:
        """Get the appropriate system prompt based on language and purpose"""
        if self.config.language == "es":
            if is_validation:
                return ("Eres un asistente de investigación experto. Tu tarea es validar y "
                       "complementar respuestas de investigación, asegurando que sean completas "
                       "y precisas. Si falta información importante, debes identificarla.")
            return ("Eres un asistente de investigación experto. Proporciona respuestas "
                   "detalladas y precisas basadas en información actual de la web.")
        else:
            if is_validation:
                return ("You are an expert research assistant. Your task is to validate and "
                       "complement research answers, ensuring they are complete and accurate. "
                       "If important information is missing, you should identify it.")
            return ("You are an expert research assistant. Provide detailed and accurate "
                   "answers based on current web information.")

    async def search_with_perplexity(self, question: str) -> str:
        """
        Perform a web search using Perplexity API.
        
        Args:
            question: The research question to be answered
            
        Returns:
            str: The answer from Perplexity
        """
        try:
            response = self.perplexity_client.chat.completions.create(
                model="sonar-pro",
                messages=[
                    {"role": "system", "content": self.get_system_prompt()},
                    {"role": "user", "content": question}
                ],
                temperature=self.config.temperature
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"Error in Perplexity search: {str(e)}")

    async def validate_with_llm(
        self, 
        original_question: str, 
        current_answer: str
    ) -> Dict[str, any]:
        """
        Validate and potentially enhance the answer using DeepSeek, openai or claude.
        
        Args:
            original_question: The original research question
            current_answer: The current answer to validate
            
        Returns:
            Dict containing validation results and any follow-up questions
        """
        if self.config.language == "es":
            validation_prompt = (
                f"Pregunta original: {original_question}\n\n"
                f"Respuesta actual: {current_answer}\n\n"
                "1. ¿La respuesta es completa y precisa? (responde con 'yes' o 'no')\n"
                "2. ¿Qué información importante falta, si es que falta alguna?\n"
                "3. Si la respuesta necesita más información, proporciona una pregunta "
                "específica para obtener esa información.\n\n"
                "Responde en formato JSON con las siguientes claves: "
                "is_complete, missing_info, follow_up_question, enhanced_answer\n\n"
                "Ejemplo de respuesta:\n"
                "```json\n"
                "{\n"
                '  "is_complete": "no",\n'
                '  "missing_info": "Falta información sobre precios y disponibilidad",\n'
                '  "follow_up_question": "¿Cuáles son los precios y disponibilidad de estos productos?",\n'
                '  "enhanced_answer": "La respuesta mejorada con la información actual"\n'
                "}\n"
                "```\n"
                "Si la respuesta es completa, usa 'yes' para is_complete y deja follow_up_question vacío."
            )
        else:
            validation_prompt = (
                f"Original question: {original_question}\n\n"
                f"Current answer: {current_answer}\n\n"
                "1. Is the answer complete and accurate? (respond with 'yes' or 'no')\n"
                "2. What important information is missing, if any?\n"
                "3. If the answer needs more information, provide a specific question "
                "to get that information.\n\n"
                "Respond in JSON format with the following keys: "
                "is_complete, missing_info, follow_up_question, enhanced_answer\n\n"
                "Example response:\n"
                "```json\n"
                "{\n"
                '  "is_complete": "no",\n'
                '  "missing_info": "Missing information about pricing and availability",\n'
                '  "follow_up_question": "What are the prices and availability of these products?",\n'
                '  "enhanced_answer": "The enhanced answer with current information"\n'
                "}\n"
                "```\n"
                "If the answer is complete, use 'yes' for is_complete and leave follow_up_question empty."
            )

        try:        
            logging.info("Validating answer...")
            response = self.validator_client.chat.completions.create(
                model= self.config.validator_model, #"deepseek-reasoner",
                messages=[
                    {"role": "system", "content": self.get_system_prompt(is_validation=True)},
                    {"role": "user", "content": validation_prompt}
                ],
                temperature=0.3
            )
            
            # Clean the response from markdown code blocks before parsing JSON
            content = response.choices[0].message.content
            logging.info(f"Raw validation response: {content[:200]}...")
            
            # Extract JSON from the response
            json_content = self._extract_json_from_text(content)
            
            if not json_content:
                logging.warning("Could not extract valid JSON from validation response")
                # Return a default response to avoid breaking the flow
                return {
                    "is_complete": "no",
                    "missing_info": "Could not parse validation response",
                    "follow_up_question": "",
                    "enhanced_answer": current_answer
                }
            
            validation_result = json.loads(json_content)
            logging.info(f"Validation result: {validation_result}")
            return validation_result
        
        except json.JSONDecodeError as e:
            logging.error(f"JSON parsing error: {str(e)}")
            # Return a default response to avoid breaking the flow
            return {
                "is_complete": "no",
                "missing_info": f"Error parsing validation response: {str(e)}",
                "follow_up_question": "",
                "enhanced_answer": current_answer
            }
        except Exception as e:
            logging.error(f"Error in validation: {str(e)}")
            # Return a default response to avoid breaking the flow
            return {
                "is_complete": "no",
                "missing_info": f"Error during validation: {str(e)}",
                "follow_up_question": "",
                "enhanced_answer": current_answer
            }
            
    def _extract_json_from_text(self, text: str) -> str:
        """
        Extract JSON from text that might contain markdown or other content.
        
        Args:
            text: Text that might contain JSON
            
        Returns:
            str: Extracted JSON string or empty string if no JSON found
        """
        # Try to extract JSON from markdown code blocks
        if "```json" in text or "```" in text:
            parts = text.split("```")
            for i, part in enumerate(parts):
                if i % 2 == 1:  # This is inside a code block
                    # Remove 'json' from the start if present
                    if part.startswith("json"):
                        part = part[4:].strip()
                    # Try to parse this part as JSON
                    try:
                        json.loads(part)
                        return part
                    except:
                        continue
        
        # Try to find JSON between curly braces
        start_idx = text.find("{")
        end_idx = text.rfind("}")
        
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            potential_json = text[start_idx:end_idx+1]
            try:
                json.loads(potential_json)
                return potential_json
            except:
                pass
        
        # If we couldn't find valid JSON, return empty string
        return ""

    async def research(self, question: str) -> str:
        """
        Main research function that coordinates the research process.
        
        Args:
            question: The research question to be answered
            
        Returns:
            str: The final, validated answer
        """
        logging.info(f"Starting research for question: {question[:100]} ....")
        try:
            current_answer = await self.search_with_perplexity(question)
            iterations = 0
            
            while iterations < self.config.max_iterations:
                logging.info(f"Research iteration {iterations + 1}/{self.config.max_iterations}")
                
                try:
                    validation_result = await self.validate_with_llm(
                        question, 
                        current_answer
                    )
                    
                    # Ensure validation_result has the expected keys
                    if not isinstance(validation_result, dict):
                        logging.warning(f"Validation result is not a dictionary: {validation_result}")
                        break
                        
                    # Check if the answer is complete
                    is_complete = validation_result.get("is_complete", "").lower()
                    if is_complete == "yes":
                        logging.info("Answer is complete, ending research")
                        return current_answer
                        
                    # Check if we have a follow-up question
                    follow_up_question = validation_result.get("follow_up_question")
                    if not follow_up_question:
                        logging.info("No follow-up question, returning enhanced answer")
                        return validation_result.get("enhanced_answer", current_answer)
                    
                    logging.info(f"Follow-up question: {follow_up_question[:100]}...")
                    
                    # Get additional information
                    additional_info = await self.search_with_perplexity(follow_up_question)
                    
                    # Combine the answers
                    if self.config.language == "es":
                        current_answer = (f"{current_answer}\n\nInformación adicional: "
                                        f"{additional_info}")
                    else:
                        current_answer = (f"{current_answer}\n\nAdditional information: "
                                        f"{additional_info}")
                
                except Exception as e:
                    logging.error(f"Error in research iteration: {str(e)}")
                    # If there's an error, we'll still increment iterations to avoid infinite loop
                
                # Always increment iterations to prevent infinite loop
                iterations += 1
                logging.info(f"Completed iteration {iterations}/{self.config.max_iterations}")
            
            logging.info(f"Reached maximum iterations ({self.config.max_iterations}), returning best answer")
            return current_answer
            
        except Exception as e:
            logging.error(f"Critical error in research: {str(e)}")
            # Return a meaningful error message instead of empty string
            return f"Error during research: {str(e)}"

# Example usage
async def main():

    config = ResearchConfig(
        perplexity_api_key=os.getenv("PERPLEXITY_API_KEY"),
        validator_api_keys={"openai": os.getenv("OPENAI_API_KEY")},
        validator_model="openai:gpt-4o-mini",
        language="en",  # or "es" for Spanish
        max_iterations=3,
        temperature=0.7
    )
    
    research_module = ResearchModule(config, model_validator="openai")
    
    question = "What are the latest developments in quantum computing?"
    try:
        final_answer = await research_module.research(question)
        print(f"Final Answer:\n{final_answer}")
    except Exception as e:
        print(f"Error during research: {str(e)}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())