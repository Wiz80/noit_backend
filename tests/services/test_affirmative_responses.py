"""
Test for affirmative responses to suggestions
Tests that the system correctly handles when users agree with suggestions
"""
import asyncio
import json
import logging
from app.services.business.business_understanding.brief_agent_service import BriefAgentService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_affirmative_responses():
    """Test different types of affirmative responses to suggestions"""
    print("🧪 Testing Affirmative Responses to Suggestions")
    print("="*60)
    
    # Initialize service
    service = BriefAgentService(llm_model="claude-3-5-sonnet-20241022")
    
    # Business data
    business_data = {
        "id": "test-affirmative-001",
        "title": "Plataforma Educativa",
        "description": "Educación online de marketing digital",
        "website_url": "https://example.com"
    }
    
    # Test different affirmative responses
    affirmative_responses = [
        "Estoy de acuerdo con el ejemplo de respuesta",
        "Sí, ese ejemplo está perfecto",
        "Correcto, esa es nuestra propuesta de valor",
        "Exacto, me gusta esa respuesta",
        "De acuerdo",
        "Sí",
        "Correcto",
        "Perfecto",
        "Esa respuesta está bien",
        "Acepto esa sugerencia"
    ]
    
    test_results = []
    
    for i, affirmative_response in enumerate(affirmative_responses[:3]):  # Test first 3
        print(f"\n{i+1}️⃣ Testing: '{affirmative_response}'")
        
        # Initialize fresh session for each test
        session_data = {
            "current_question_index": 0,
            "answers": {},
            "langchain_chat_history": [],
            "business_idea": business_data
        }
        
        # Start welcome flow
        welcome_result = service.run_agent_turn("Iniciar brief", session_data)
        
        # Update session
        session_data = {
            "current_question_index": welcome_result['updated_current_question_index'],
            "answers": welcome_result['updated_answers'],
            "langchain_chat_history": welcome_result['updated_chat_history'],
            "business_idea": business_data
        }
        
        # Test the affirmative response
        result = service.run_agent_turn(affirmative_response, session_data)
        
        # Analyze results
        was_affirmative = result.get('was_affirmative_to_suggestion', False)
        used_suggestion = result.get('used_suggestion_as_base', False)
        answer_recorded = result.get('answer_recorded', False)
        flow_continued = result.get('updated_current_question_index', 0) > session_data['current_question_index']
        
        # Check if no clarification was requested
        clarification_keywords = ['no pude entender', 'podrías intentar', 'responder de nuevo']
        no_clarification = not any(keyword in result['reply'].lower() for keyword in clarification_keywords)
        
        test_result = {
            "response": affirmative_response,
            "was_affirmative": was_affirmative,
            "used_suggestion": used_suggestion,
            "answer_recorded": answer_recorded,
            "flow_continued": flow_continued,
            "no_clarification": no_clarification,
            "success": was_affirmative and answer_recorded and flow_continued and no_clarification
        }
        
        test_results.append(test_result)
        
        print(f"  ✅ Detected as affirmative: {was_affirmative}")
        print(f"  ✅ Used suggestion as base: {used_suggestion}")
        print(f"  ✅ Answer recorded: {answer_recorded}")
        print(f"  ✅ Flow continued: {flow_continued}")
        print(f"  ✅ No clarification requested: {no_clarification}")
        print(f"  🎯 Overall success: {test_result['success']}")
        
        # Show what was stored
        if answer_recorded:
            answers = result.get('updated_answers', {})
            if answers:
                for phase, phase_answers in answers.items():
                    for question, answer in phase_answers.items():
                        print(f"  📄 Stored: '{answer[:60]}...'")
    
    # Overall assessment
    print(f"\n📊 OVERALL RESULTS")
    print("="*60)
    
    total_tests = len(test_results)
    successful_tests = sum(1 for r in test_results if r['success'])
    success_rate = (successful_tests / total_tests) * 100
    
    print(f"📈 Success Rate: {success_rate:.0f}% ({successful_tests}/{total_tests})")
    
    # Detailed breakdown
    affirmative_detected = sum(1 for r in test_results if r['was_affirmative'])
    suggestions_used = sum(1 for r in test_results if r['used_suggestion'])
    answers_recorded = sum(1 for r in test_results if r['answer_recorded'])
    flows_continued = sum(1 for r in test_results if r['flow_continued'])
    no_clarifications = sum(1 for r in test_results if r['no_clarification'])
    
    print(f"✅ Affirmative detection: {affirmative_detected}/{total_tests}")
    print(f"✅ Suggestions used: {suggestions_used}/{total_tests}")
    print(f"✅ Answers recorded: {answers_recorded}/{total_tests}")
    print(f"✅ Flows continued: {flows_continued}/{total_tests}")
    print(f"✅ No clarifications: {no_clarifications}/{total_tests}")
    
    # Assessment
    if success_rate >= 80:
        assessment = "🎉 EXCELLENT: Affirmative response handling is working perfectly!"
    elif success_rate >= 60:
        assessment = "✅ GOOD: Affirmative response handling is working well!"
    elif success_rate >= 40:
        assessment = "⚠️ FAIR: Affirmative response handling needs some improvement!"
    else:
        assessment = "❌ POOR: Affirmative response handling needs significant work!"
    
    print(f"\n🏆 ASSESSMENT: {assessment}")
    
    return {
        "success_rate": success_rate,
        "total_tests": total_tests,
        "successful_tests": successful_tests,
        "detailed_results": test_results,
        "assessment": assessment
    }

async def test_user_specific_case():
    """Test the specific case mentioned by the user"""
    print("\n" + "="*60)
    print("🎯 Testing User's Specific Case")
    print("="*60)
    
    service = BriefAgentService(llm_model="claude-3-5-sonnet-20241022")
    
    business_data = {
        "id": "test-user-case",
        "title": "Plataforma Educativa",
        "description": "Educación online de marketing digital",
        "website_url": "https://example.com"
    }
    
    # Initialize session
    session_data = {
        "current_question_index": 0,
        "answers": {},
        "langchain_chat_history": [],
        "business_idea": business_data
    }
    
    # Start flow
    welcome_result = service.run_agent_turn("Iniciar brief", session_data)
    
    # Move to next question (simulate answering first question)
    session_data = {
        "current_question_index": welcome_result['updated_current_question_index'],
        "answers": welcome_result['updated_answers'],
        "langchain_chat_history": welcome_result['updated_chat_history'],
        "business_idea": business_data
    }
    
    # Answer first question to get to second
    first_answer = service.run_agent_turn("Somos una plataforma educativa", session_data)
    
    session_data = {
        "current_question_index": first_answer['updated_current_question_index'],
        "answers": first_answer['updated_answers'],
        "langchain_chat_history": first_answer['updated_chat_history'],
        "business_idea": business_data
    }
    
    # Now test the user's exact response
    user_response = "Estoy de acuerdo con el ejemplo de respuesta"
    print(f"Testing user's exact response: '{user_response}'")
    
    result = service.run_agent_turn(user_response, session_data)
    
    # Check results
    was_affirmative = result.get('was_affirmative_to_suggestion', False)
    answer_recorded = result.get('answer_recorded', False)
    clarification_requested = 'no pude entender' in result['reply'].lower()
    
    print(f"✅ Detected as affirmative: {was_affirmative}")
    print(f"✅ Answer recorded: {answer_recorded}")
    print(f"✅ No clarification requested: {not clarification_requested}")
    print(f"📄 Reply: '{result['reply'][:100]}...'")
    
    if was_affirmative and answer_recorded and not clarification_requested:
        print("🎉 SUCCESS: User's case is now handled correctly!")
        return True
    else:
        print("❌ FAILED: User's case still needs work!")
        return False

async def main():
    """Main function to run all tests"""
    # Test general affirmative responses
    general_results = await test_affirmative_responses()
    
    # Test user's specific case
    user_case_success = await test_user_specific_case()
    
    print(f"\n🎯 FINAL SUMMARY")
    print("="*60)
    print(f"General affirmative responses: {general_results['success_rate']:.0f}% success")
    print(f"User's specific case: {'✅ FIXED' if user_case_success else '❌ STILL FAILING'}")
    
    return {
        "general_results": general_results,
        "user_case_success": user_case_success
    }

if __name__ == "__main__":
    result = asyncio.run(main())
    print(f"\n📊 Test completed: {result}") 