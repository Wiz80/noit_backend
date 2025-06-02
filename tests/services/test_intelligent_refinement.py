"""
Test for intelligent refinement logic
Tests that refinement is only applied when truly necessary
"""
import asyncio
import json
import logging
from app.services.business.business_understanding.brief_agent_service import BriefAgentService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_intelligent_refinement():
    """Test that refinement is applied intelligently"""
    print("🧪 Testing Intelligent Refinement Logic")
    print("="*60)
    
    # Initialize service
    service = BriefAgentService(llm_model="claude-3-5-sonnet-20241022")
    
    # Business data
    business_data = {
        "id": "test-intelligent-refinement",
        "title": "Plataforma Educativa",
        "description": "Educación online de marketing digital",
        "website_url": "https://example.com"
    }
    
    # Test different types of responses
    test_cases = [
        {
            "name": "Respuesta Afirmativa",
            "response": "Estoy de acuerdo con el ejemplo de respuesta",
            "expected_source": "suggestion",
            "expected_refinement": False,
            "description": "Should use suggestion without refinement"
        },
        {
            "name": "Respuesta Buena",
            "response": "Somos una plataforma educativa online especializada en marketing digital para profesionales latinoamericanos. Ofrecemos cursos prácticos con casos reales de la región, mentores certificados y contenido actualizado mensualmente.",
            "expected_source": "original", 
            "expected_refinement": False,
            "description": "Should use original without refinement"
        },
        {
            "name": "Respuesta Básica",
            "response": "Educación online",
            "expected_source": "refined",
            "expected_refinement": True,
            "description": "Should refine basic response"
        },
        {
            "name": "Respuesta Corta pero Específica",
            "response": "Plataforma de cursos de marketing digital para LATAM",
            "expected_source": "original",
            "expected_refinement": False,
            "description": "Should use original as it's specific enough"
        }
    ]
    
    results = []
    
    for i, test_case in enumerate(test_cases):
        print(f"\n{i+1}️⃣ Testing: {test_case['name']}")
        print(f"   Response: '{test_case['response']}'")
        print(f"   Expected: {test_case['expected_source']} (refinement: {test_case['expected_refinement']})")
        
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
        
        # Test the response
        result = service.run_agent_turn(test_case['response'], session_data)
        
        # Analyze results
        actual_source = result.get('answer_source', 'unknown')
        actual_refinement = result.get('refinement_applied', False)
        response_quality = result.get('response_quality', 'unknown')
        was_affirmative = result.get('was_affirmative_to_suggestion', False)
        final_answer = result.get('final_answer', '')
        
        # Check if it matches expectations
        source_correct = actual_source == test_case['expected_source']
        refinement_correct = actual_refinement == test_case['expected_refinement']
        overall_success = source_correct and refinement_correct
        
        test_result = {
            "name": test_case['name'],
            "response": test_case['response'],
            "expected_source": test_case['expected_source'],
            "actual_source": actual_source,
            "expected_refinement": test_case['expected_refinement'],
            "actual_refinement": actual_refinement,
            "response_quality": response_quality,
            "was_affirmative": was_affirmative,
            "final_answer": final_answer[:60] + "..." if len(final_answer) > 60 else final_answer,
            "success": overall_success
        }
        
        results.append(test_result)
        
        print(f"   ✅ Source: {actual_source} ({'✅' if source_correct else '❌'})")
        print(f"   ✅ Refinement: {actual_refinement} ({'✅' if refinement_correct else '❌'})")
        print(f"   ✅ Quality: {response_quality}")
        print(f"   ✅ Affirmative: {was_affirmative}")
        print(f"   🎯 Success: {overall_success}")
        print(f"   📄 Final: '{test_result['final_answer']}'")
    
    # Overall assessment
    print(f"\n📊 OVERALL RESULTS")
    print("="*60)
    
    total_tests = len(results)
    successful_tests = sum(1 for r in results if r['success'])
    success_rate = (successful_tests / total_tests) * 100
    
    print(f"📈 Success Rate: {success_rate:.0f}% ({successful_tests}/{total_tests})")
    
    # Detailed breakdown
    print(f"\n📋 Detailed Results:")
    for result in results:
        status = "✅" if result['success'] else "❌"
        print(f"  {status} {result['name']}: {result['actual_source']} (refinement: {result['actual_refinement']})")
    
    # Assessment
    if success_rate >= 80:
        assessment = "🎉 EXCELLENT: Intelligent refinement is working perfectly!"
    elif success_rate >= 60:
        assessment = "✅ GOOD: Intelligent refinement is working well!"
    elif success_rate >= 40:
        assessment = "⚠️ FAIR: Intelligent refinement needs some improvement!"
    else:
        assessment = "❌ POOR: Intelligent refinement needs significant work!"
    
    print(f"\n🏆 ASSESSMENT: {assessment}")
    
    return {
        "success_rate": success_rate,
        "total_tests": total_tests,
        "successful_tests": successful_tests,
        "detailed_results": results,
        "assessment": assessment
    }

async def test_refinement_efficiency():
    """Test that refinement is not overused"""
    print("\n" + "="*60)
    print("🎯 Testing Refinement Efficiency")
    print("="*60)
    
    service = BriefAgentService(llm_model="claude-3-5-sonnet-20241022")
    
    business_data = {
        "id": "test-efficiency",
        "title": "Test Business",
        "description": "Test description",
        "website_url": "https://test.com"
    }
    
    # Responses that should NOT be refined
    good_responses = [
        "Estoy de acuerdo",
        "Somos una empresa de tecnología que desarrolla software personalizado para PYMES",
        "Nuestro valor único es la rapidez en implementación y soporte 24/7",
        "Sí, correcto",
        "Ofrecemos consultoría especializada en transformación digital"
    ]
    
    refinement_count = 0
    total_responses = len(good_responses)
    
    for i, response in enumerate(good_responses):
        # Fresh session for each test
        session_data = {
            "current_question_index": 0,
            "answers": {},
            "langchain_chat_history": [],
            "business_idea": business_data
        }
        
        # Start and test
        welcome_result = service.run_agent_turn("Iniciar brief", session_data)
        session_data.update({
            "current_question_index": welcome_result['updated_current_question_index'],
            "answers": welcome_result['updated_answers'],
            "langchain_chat_history": welcome_result['updated_chat_history']
        })
        
        result = service.run_agent_turn(response, session_data)
        
        if result.get('refinement_applied', False):
            refinement_count += 1
            print(f"  ⚠️ Unnecessarily refined: '{response}'")
        else:
            print(f"  ✅ Correctly not refined: '{response}'")
    
    efficiency_rate = ((total_responses - refinement_count) / total_responses) * 100
    
    print(f"\n📊 Efficiency Results:")
    print(f"  Total responses: {total_responses}")
    print(f"  Unnecessary refinements: {refinement_count}")
    print(f"  Efficiency rate: {efficiency_rate:.0f}%")
    
    if efficiency_rate >= 80:
        efficiency_assessment = "🎉 EXCELLENT: High efficiency, minimal unnecessary refinement!"
    elif efficiency_rate >= 60:
        efficiency_assessment = "✅ GOOD: Good efficiency!"
    else:
        efficiency_assessment = "⚠️ POOR: Too much unnecessary refinement!"
    
    print(f"  Assessment: {efficiency_assessment}")
    
    return {
        "efficiency_rate": efficiency_rate,
        "unnecessary_refinements": refinement_count,
        "total_responses": total_responses,
        "assessment": efficiency_assessment
    }

async def main():
    """Main function to run all tests"""
    # Test intelligent refinement
    refinement_results = await test_intelligent_refinement()
    
    # Test efficiency
    efficiency_results = await test_refinement_efficiency()
    
    print(f"\n🎯 FINAL SUMMARY")
    print("="*60)
    print(f"Intelligent refinement: {refinement_results['success_rate']:.0f}% success")
    print(f"Refinement efficiency: {efficiency_results['efficiency_rate']:.0f}%")
    
    overall_success = refinement_results['success_rate'] >= 75 and efficiency_results['efficiency_rate'] >= 75
    
    if overall_success:
        final_assessment = "🎉 SUCCESS: Intelligent refinement is working optimally!"
    else:
        final_assessment = "⚠️ NEEDS WORK: Intelligent refinement needs improvements!"
    
    print(f"\n🏆 FINAL ASSESSMENT: {final_assessment}")
    
    return {
        "refinement_results": refinement_results,
        "efficiency_results": efficiency_results,
        "overall_success": overall_success
    }

if __name__ == "__main__":
    result = asyncio.run(main())
    print(f"\n📊 Test completed: Overall success = {result['overall_success']}") 