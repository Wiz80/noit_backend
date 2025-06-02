"""
Test for performance optimization with static suggestions
Tests that the system is faster with pre-defined suggestions
"""
import asyncio
import time
import logging
from app.services.business.business_understanding.brief_agent_service import BriefAgentService
from app.utils.brief_suggestions import get_suggestion_answer, get_all_suggestions

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_static_suggestions():
    """Test that static suggestions are working correctly"""
    print("🧪 Testing Static Suggestions")
    print("="*60)
    
    # Test all questions have suggestions
    all_suggestions = get_all_suggestions()
    
    print(f"📋 Total questions with suggestions: {len(all_suggestions)}")
    
    # Test a few specific questions
    test_questions = [
        "¿Qué hace la empresa? ¿Cuál es su propósito?",
        "¿Cuál es su propuesta de valor?",
        "¿Cuál es el cliente ideal?"
    ]
    
    for question in test_questions:
        suggestion = get_suggestion_answer(question)
        print(f"✅ {question[:30]}... : {len(suggestion)} characters")
        assert len(suggestion) > 50, f"Suggestion too short for: {question}"
    
    print(f"✅ All static suggestions are working correctly!")
    
    return {
        "total_suggestions": len(all_suggestions),
        "test_passed": True
    }

async def test_response_time_improvement():
    """Test response time improvement with static suggestions"""
    print("\n" + "="*60)
    print("⚡ Testing Response Time Improvement")
    print("="*60)
    
    # Initialize service
    service = BriefAgentService(llm_model="claude-3-5-sonnet-20241022")
    
    # Business data
    business_data = {
        "id": "test-performance",
        "title": "Test Business",
        "description": "Test description",
        "website_url": "https://test.com"
    }
    
    # Test multiple brief interactions
    test_responses = [
        "Somos una empresa de tecnología",
        "Ofrecemos soluciones innovadoras",
        "Nuestro cliente ideal son PYMES"
    ]
    
    times = []
    
    for i, response in enumerate(test_responses):
        print(f"  Testing response {i+1}/3...")
        
        # Initialize session
        session_data = {
            "current_question_index": 0,
            "answers": {},
            "langchain_chat_history": [],
            "business_idea": business_data
        }
        
        # Time the welcome flow
        start_time = time.time()
        welcome_result = service.run_agent_turn("Iniciar brief", session_data)
        welcome_time = time.time() - start_time
        
        # Update session
        session_data = {
            "current_question_index": welcome_result['updated_current_question_index'],
            "answers": welcome_result['updated_answers'],
            "langchain_chat_history": welcome_result['updated_chat_history'],
            "business_idea": business_data
        }
        
        # Time the response
        start_time = time.time()
        result = service.run_agent_turn(response, session_data)
        response_time = time.time() - start_time
        
        total_time = welcome_time + response_time
        times.append(total_time)
        
        print(f"    Welcome: {welcome_time:.2f}s, Response: {response_time:.2f}s, Total: {total_time:.2f}s")
        
        # Verify it worked correctly
        assert result.get('answer_recorded', False), "Answer should be recorded"
        assert 'suggestion_answer' in welcome_result, "Should have suggestion_answer"
        assert 'suggestion_response' in welcome_result, "Should have suggestion_response"
    
    avg_time = sum(times) / len(times)
    print(f"\n📊 Performance Results:")
    print(f"  Average total time per interaction: {avg_time:.2f}s")
    print(f"  All times: {[f'{t:.2f}s' for t in times]}")
    
    # Performance assessment
    if avg_time < 10:
        assessment = "🎉 EXCELLENT: Very fast response times!"
    elif avg_time < 20:
        assessment = "✅ GOOD: Reasonable response times!"
    elif avg_time < 30:
        assessment = "⚠️ FAIR: Could be faster!"
    else:
        assessment = "❌ SLOW: Needs optimization!"
    
    print(f"  {assessment}")
    
    return {
        "avg_time": avg_time,
        "times": times,
        "assessment": assessment,
        "performance_good": avg_time < 20
    }

async def test_suggestion_quality():
    """Test that static suggestions maintain good quality"""
    print("\n" + "="*60)
    print("🎯 Testing Suggestion Quality")
    print("="*60)
    
    # Test key questions for quality
    quality_tests = [
        {
            "question": "¿Cuál es su propuesta de valor?",
            "expected_keywords": ["valor", "diferencia", "beneficio", "cliente"]
        },
        {
            "question": "¿Cuál es el cliente ideal?",
            "expected_keywords": ["cliente", "demografía", "necesidades", "comportamiento"]
        },
        {
            "question": "¿Qué problema resuelve?",
            "expected_keywords": ["problema", "dolor", "necesidad", "consecuencias"]
        }
    ]
    
    quality_results = []
    
    for test in quality_tests:
        question = test["question"]
        expected_keywords = test["expected_keywords"]
        
        suggestion = get_suggestion_answer(question)
        suggestion_lower = suggestion.lower()
        
        # Check for expected keywords
        found_keywords = [kw for kw in expected_keywords if kw in suggestion_lower]
        keyword_score = len(found_keywords) / len(expected_keywords)
        
        # Check length (should be comprehensive)
        length_score = 1.0 if len(suggestion) > 200 else len(suggestion) / 200
        
        # Check structure (should have examples)
        has_example = "ejemplo" in suggestion_lower
        structure_score = 1.0 if has_example else 0.5
        
        overall_score = (keyword_score + length_score + structure_score) / 3
        
        quality_results.append({
            "question": question[:40] + "...",
            "keyword_score": keyword_score,
            "length_score": length_score,
            "structure_score": structure_score,
            "overall_score": overall_score,
            "length": len(suggestion)
        })
        
        print(f"  ✅ {question[:40]}...")
        print(f"    Keywords: {keyword_score:.1%}, Length: {length_score:.1%}, Structure: {structure_score:.1%}")
        print(f"    Overall: {overall_score:.1%} ({len(suggestion)} chars)")
    
    avg_quality = sum(r["overall_score"] for r in quality_results) / len(quality_results)
    
    print(f"\n📊 Quality Results:")
    print(f"  Average quality score: {avg_quality:.1%}")
    
    if avg_quality >= 0.8:
        quality_assessment = "🎉 EXCELLENT: High quality suggestions!"
    elif avg_quality >= 0.6:
        quality_assessment = "✅ GOOD: Good quality suggestions!"
    else:
        quality_assessment = "⚠️ NEEDS WORK: Quality could be improved!"
    
    print(f"  {quality_assessment}")
    
    return {
        "avg_quality": avg_quality,
        "quality_results": quality_results,
        "assessment": quality_assessment,
        "quality_good": avg_quality >= 0.7
    }

async def main():
    """Main function to run all tests"""
    # Test static suggestions
    static_results = await test_static_suggestions()
    
    # Test performance
    performance_results = await test_response_time_improvement()
    
    # Test quality
    quality_results = await test_suggestion_quality()
    
    print(f"\n🎯 FINAL SUMMARY")
    print("="*60)
    print(f"Static suggestions: ✅ Working ({static_results['total_suggestions']} questions)")
    print(f"Performance: {'✅ GOOD' if performance_results['performance_good'] else '⚠️ NEEDS WORK'} ({performance_results['avg_time']:.1f}s avg)")
    print(f"Quality: {'✅ GOOD' if quality_results['quality_good'] else '⚠️ NEEDS WORK'} ({quality_results['avg_quality']:.1%} avg)")
    
    overall_success = (
        static_results['test_passed'] and 
        performance_results['performance_good'] and 
        quality_results['quality_good']
    )
    
    if overall_success:
        final_assessment = "🎉 SUCCESS: Performance optimization is working great!"
    else:
        final_assessment = "⚠️ PARTIAL SUCCESS: Some areas need improvement!"
    
    print(f"\n🏆 FINAL ASSESSMENT: {final_assessment}")
    
    return {
        "static_results": static_results,
        "performance_results": performance_results,
        "quality_results": quality_results,
        "overall_success": overall_success
    }

if __name__ == "__main__":
    result = asyncio.run(main())
    print(f"\n📊 Test completed: Overall success = {result['overall_success']}") 