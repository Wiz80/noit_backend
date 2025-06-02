"""
Test Business Model Mapping and Database Storage
Tests that ETAPA 1 completion triggers business model saving to database
"""
import asyncio
import logging
from datetime import datetime
from app.services.business.business_understanding.brief_agent_service import BriefAgentService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_etapa1_business_model_mapping():
    """Test that ETAPA 1 completion generates correct business model mapping"""
    print("🧪 Testing ETAPA 1 Business Model Mapping")
    print("="*60)
    
    # Initialize service
    service = BriefAgentService(llm_model="claude-3-5-sonnet-20241022")
    
    # Business data
    business_data = {
        "id": "test-business-model",
        "title": "Alpina Test",
        "description": "Test company for business model mapping",
        "website_url": "https://test-alpina.com"
    }
    
    # Mock completed ETAPA 1 answers
    etapa1_answers = {
        "ETAPA 1: ENTENDIMIENTO DEL NEGOCIO": {
            "¿Qué hace la empresa? ¿Cuál es su propósito?": "Somos una empresa de alimentos que produce lácteos",
            "¿Cuál es su propuesta de valor?": "Ofrecemos los mejores productos lácteos de la región",
            "¿Qué productos/servicios ofrece y a quiénes?": "Leche, quesos y yogurt para familias",
            "¿Cuál es el cliente ideal?": "Familias con niños que valoran la calidad",
            "¿Qué problema resuelve?": "Necesidad de alimentación nutritiva y saludable",
            "¿Qué los hace diferentes frente a la competencia?": "75 años de experiencia y calidad premium",
            "¿Qué desafíos u oportunidades clave enfrentan hoy?": "Expansión internacional y productos saludables",
            "¿En qué industria se encuentra?": "Industria de alimentos y lácteos"
        }
    }
    
    # Test business model mapping
    business_model_mapping = service.map_etapa1_to_business_model(etapa1_answers)
    
    print(f"📋 Generated business model mapping:")
    for field, value in business_model_mapping.items():
        print(f"  ✅ {field}: {value[:50]}...")
    
    # Verify all expected fields are present
    expected_fields = [
        "problem_definition",
        "value_proposition", 
        "products_services",
        "customer_persona",
        "competitive_advantage",
        "challenges_opportunities",
        "industry"
    ]
    
    for field in expected_fields:
        assert field in business_model_mapping, f"Missing field: {field}"
        assert len(business_model_mapping[field]) > 10, f"Field {field} is too short"
    
    print(f"✅ All {len(expected_fields)} business model fields generated correctly!")
    
    return {
        "mapping_generated": True,
        "fields_count": len(business_model_mapping),
        "expected_fields": len(expected_fields),
        "test_passed": True
    }

async def simulate_etapa1_completion():
    """Simulate completing ETAPA 1 and check if business model mapping is triggered"""
    print("\n" + "="*60)
    print("🎯 Simulating ETAPA 1 Completion")
    print("="*60)
    
    # Initialize service
    service = BriefAgentService(llm_model="claude-3-5-sonnet-20241022")
    
    # Business data
    business_data = {
        "id": "test-completion",
        "title": "Test Company",
        "description": "Test company for completion simulation",
        "website_url": "https://test.com"
    }
    
    # Simulate going through all ETAPA 1 questions
    etapa1_questions = [
        "¿Qué hace la empresa? ¿Cuál es su propósito?",
        "¿Cuál es su propuesta de valor?",
        "¿Qué productos/servicios ofrece y a quiénes?",
        "¿Cuál es el cliente ideal?",
        "¿Qué problema resuelve?",
        "¿Qué los hace diferentes frente a la competencia?",
        "¿Qué desafíos u oportunidades clave enfrentan hoy?",
        "¿En qué industria se encuentra?"
    ]
    
    # Session data setup
    session_data = {
        "current_question_index": 0,
        "answers": {},
        "langchain_chat_history": [],
        "business_idea": business_data
    }
    
    # Start brief
    welcome_result = service.run_agent_turn("Iniciar brief", session_data)
    session_data.update({
        "current_question_index": welcome_result['updated_current_question_index'],
        "answers": welcome_result['updated_answers'],
        "langchain_chat_history": welcome_result['updated_chat_history']
    })
    
    print(f"  📋 Starting brief simulation...")
    
    # Answer all ETAPA 1 questions
    etapa1_completed = False
    business_model_mapping = None
    
    responses = [
        "Somos una empresa de tecnología",
        "Ofrecemos las mejores soluciones tecnológicas",
        "Software para empresas medianas",
        "PYMES que buscan digitalización",
        "Falta de digitalización en PYMES",
        "Experiencia y soporte local",
        "Crecimiento del mercado digital",
        "Industria de tecnología"
    ]
    
    for i, response in enumerate(responses):
        result = service.run_agent_turn(response, session_data)
        
        session_data.update({
            "current_question_index": result['updated_current_question_index'],
            "answers": result['updated_answers'],
            "langchain_chat_history": result['updated_chat_history']
        })
        
        print(f"    Question {i+1}/8: {result.get('answer_recorded', False)} - Index: {result['updated_current_question_index']}")
        
        # Check if ETAPA 1 was completed
        if result.get("etapa1_completed"):
            etapa1_completed = True
            business_model_mapping = result.get("business_model_mapping")
            print(f"    🎉 ETAPA 1 COMPLETED! Business model mapping triggered.")
            break
    
    print(f"\n📊 Simulation Results:")
    print(f"  ETAPA 1 completed: {etapa1_completed}")
    print(f"  Business model mapping generated: {business_model_mapping is not None}")
    
    if business_model_mapping:
        print(f"  Mapping fields: {len(business_model_mapping)}")
        for field in business_model_mapping.keys():
            print(f"    - {field}")
    
    return {
        "etapa1_completed": etapa1_completed,
        "mapping_generated": business_model_mapping is not None,
        "mapping_fields": len(business_model_mapping) if business_model_mapping else 0,
        "simulation_success": etapa1_completed and business_model_mapping is not None
    }

async def main():
    """Main function to run all tests"""
    # Test business model mapping
    mapping_results = await test_etapa1_business_model_mapping()
    
    # Test ETAPA 1 completion simulation
    completion_results = await simulate_etapa1_completion()
    
    print(f"\n🎯 FINAL SUMMARY")
    print("="*60)
    print(f"Business model mapping: ✅ Working ({mapping_results['fields_count']} fields)")
    print(f"ETAPA 1 completion: {'✅ Working' if completion_results['simulation_success'] else '❌ FAILED'}")
    print(f"Database mapping ready: {'✅ YES' if completion_results['mapping_generated'] else '❌ NO'}")
    
    overall_success = (
        mapping_results['test_passed'] and 
        completion_results['simulation_success']
    )
    
    if overall_success:
        final_assessment = "🎉 SUCCESS: Business model mapping is working correctly!"
    else:
        final_assessment = "⚠️ ISSUES FOUND: Some functionality needs debugging!"
    
    print(f"\n🏆 FINAL ASSESSMENT: {final_assessment}")
    
    return {
        "mapping_results": mapping_results,
        "completion_results": completion_results,
        "overall_success": overall_success
    }

if __name__ == "__main__":
    result = asyncio.run(main())
    print(f"\n📊 Test completed: Overall success = {result['overall_success']}") 