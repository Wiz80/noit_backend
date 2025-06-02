"""
Simple test for response refinement functionality
Tests the exact scenario described by the user
"""
import asyncio
import json
import logging
from app.services.business.business_understanding.brief_agent_service import BriefAgentService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_user_scenario():
    """Test the exact scenario described by the user"""
    print("🧪 Testing User Scenario: Education Platform Brief")
    print("="*60)
    
    # Initialize service
    service = BriefAgentService(llm_model="claude-3-5-sonnet-20241022")
    
    # Business data similar to user's case
    business_data = {
        "id": "test-education-001",
        "title": "Plataforma de Educación Digital",
        "description": "Educación de marketing digital para Latinoamérica",
        "website_url": "https://educacion-digital.com"
    }
    
    # Initialize session
    session_data = {
        "current_question_index": 0,
        "answers": {},
        "langchain_chat_history": [],
        "business_idea": business_data
    }
    
    print("📝 Starting brief conversation...")
    
    # Step 1: Welcome flow
    print("\n1️⃣ Welcome Flow")
    welcome_result = service.run_agent_turn("Iniciar brief", session_data)
    print(f"✅ Welcome message length: {len(welcome_result['reply'])} chars")
    print(f"✅ Question index: {welcome_result['updated_current_question_index']}")
    
    # Update session
    session_data = {
        "current_question_index": welcome_result['updated_current_question_index'],
        "answers": welcome_result['updated_answers'],
        "langchain_chat_history": welcome_result['updated_chat_history'],
        "business_idea": business_data
    }
    
    # Step 2: Test first problematic response from user
    print("\n2️⃣ Testing User's First Response")
    user_response_1 = "La mejor educación online de latinoamerica"
    print(f"User says: '{user_response_1}'")
    
    result_1 = service.run_agent_turn(user_response_1, session_data)
    
    print(f"✅ Answer recorded: {result_1.get('answer_recorded', False)}")
    print(f"✅ Response refined: {result_1.get('response_was_refined', False)}")
    print(f"✅ Flow continued: {result_1.get('updated_current_question_index', 0) > session_data['current_question_index']}")
    
    if result_1.get('refined_answer'):
        print(f"📄 Refined answer: '{result_1['refined_answer'][:100]}...'")
    
    # Update session
    session_data = {
        "current_question_index": result_1['updated_current_question_index'],
        "answers": result_1['updated_answers'],
        "langchain_chat_history": result_1['updated_chat_history'],
        "business_idea": business_data
    }
    
    # Step 3: Test second response from user
    print("\n3️⃣ Testing User's Second Response")
    user_response_2 = "Educación de marketing digital, la audiencia es el publico latinoamericano, ofrecemos cursos desde nivel básico a avanzado, el proposito es generar un impacto en latinoamerica, ayudando a las personas a mejorar su conocimiento y por lo tanto sus ingresos"
    print(f"User says: '{user_response_2[:80]}...'")
    
    result_2 = service.run_agent_turn(user_response_2, session_data)
    
    print(f"✅ Answer recorded: {result_2.get('answer_recorded', False)}")
    print(f"✅ Response refined: {result_2.get('response_was_refined', False)}")
    print(f"✅ Flow continued: {result_2.get('updated_current_question_index', 0) > session_data['current_question_index']}")
    
    if result_2.get('refined_answer'):
        print(f"📄 Refined answer: '{result_2['refined_answer'][:100]}...'")
    
    # Step 4: Check no clarification requests
    print("\n4️⃣ Checking for Clarification Requests")
    clarification_keywords = ['más detalles', 'proporcione', 'específicos', 'información adicional', 'cualificaciones']
    
    reply_1_has_clarification = any(keyword in result_1['reply'].lower() for keyword in clarification_keywords)
    reply_2_has_clarification = any(keyword in result_2['reply'].lower() for keyword in clarification_keywords)
    
    print(f"✅ No clarification in response 1: {not reply_1_has_clarification}")
    print(f"✅ No clarification in response 2: {not reply_2_has_clarification}")
    
    # Step 5: Show stored answers
    print("\n5️⃣ Final Stored Answers")
    answers = result_2.get('updated_answers', {})
    for phase, phase_answers in answers.items():
        print(f"\n📁 {phase}:")
        for question, answer in phase_answers.items():
            print(f"  Q: {question[:50]}...")
            print(f"  A: {answer[:80]}...")
    
    # Step 6: Overall assessment
    print("\n6️⃣ Overall Assessment")
    success_criteria = [
        result_1.get('answer_recorded', False),
        result_2.get('answer_recorded', False),
        not reply_1_has_clarification,
        not reply_2_has_clarification,
        len(answers) > 0
    ]
    
    success_rate = sum(success_criteria) / len(success_criteria) * 100
    
    print(f"✅ Success Rate: {success_rate:.0f}%")
    
    if success_rate >= 80:
        print("🎉 EXCELLENT: Refinement is working perfectly!")
    elif success_rate >= 60:
        print("✅ GOOD: Refinement is working well!")
    else:
        print("⚠️ NEEDS IMPROVEMENT: Refinement needs optimization!")
    
    return {
        "success_rate": success_rate,
        "answers_stored": len(answers),
        "no_clarification_requests": not (reply_1_has_clarification or reply_2_has_clarification),
        "flow_progression": result_2.get('updated_current_question_index', 0) > 0
    }

if __name__ == "__main__":
    result = asyncio.run(test_user_scenario())
    print(f"\n📊 Final Result: {result}") 