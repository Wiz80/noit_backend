"""
Main execution file for the research question processing system.
"""

import os
from dotenv import load_dotenv
from state_of_art.question_organizer import QuestionOrganizer
from state_of_art.answer_generator import AnswerGenerator

def main():
    """
    Main execution function for processing research questions.
    """
    # Load environment variables
    load_dotenv()
    
    # Get API keys
    openai_api_key = os.getenv("OPENAI_API_KEY")
    tavily_api_key = os.getenv("TAVILY_API_KEY")
    
    if not all([openai_api_key, tavily_api_key]):
        raise ValueError("Missing required API keys in .env file")
    
    # Example input (in production this would come from user input)
    user_input = """
    Estoy pensando en lanzar una app de ejercicio y nutrición
    enfocada en hombres de 25-40 años que viven en grandes ciudades.
    Por ahora solo tengo el concepto: una suscripción mensual que ofrece
    rutinas, recordatorios, dietas personalizadas y soporte de entrenadores en línea.
    Quiero saber cómo podría diferenciarme y qué necesito investigar.
    No tengo marca registrada ni inversores aún.
    """
    
    # Read questions from file
    with open('questions.md', 'r', encoding='utf-8') as f:
        questions = f.read()
    
    try:
        # Initialize components
        question_organizer = QuestionOrganizer(openai_api_key)
        answer_generator = AnswerGenerator(openai_api_key, tavily_api_key)
        
        # Organize questions
        print("Organizing questions...")
        organized_questions = question_organizer.organize_questions(user_input, questions)
        
        # Save organized questions
        question_organizer.save_organized_questions(
            organized_questions,
            "output/organized_questions.json"
        )
        
        # Process questions and generate answers
        print("Generating answers...")
        answer_generator.process_all_questions(
            organized_questions,
            user_input,
            "output/research_results.json"
        )
        
        print("Process completed successfully!")
        
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        raise

if __name__ == "__main__":
    main()