"""
Test for ETAPA 1 automatic mapping to BusinessModel
Tests that the system correctly maps ETAPA 1 answers to BusinessModel fields
"""
import asyncio
import json
import logging
from app.services.business.business_understanding.brief_agent_service import BriefAgentService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_etapa1_mapping():
    """Test the automatic mapping of ETAPA 1 to BusinessModel fields"""
    print("🧪 Testing ETAPA 1 Automatic Mapping to BusinessModel")
    print("="*60)
    
    # Initialize service
    service = BriefAgentService(llm_model="claude-3-5-sonnet-20241022")
    
    # Business data
    business_data = {
        "id": "test-etapa1-mapping",
        "title": "Plataforma Educativa Digital",
        "description": "Educación online de marketing digital",
        "website_url": "https://example.com"
    }
    
    # Simulate complete ETAPA 1 responses
    etapa1_responses = [
        "Somos una plataforma educativa online que se dedica a enseñar marketing digital a profesionales latinoamericanos",
        "Ofrecemos la mejor educación online de marketing digital en Latinoamérica, con contenido actualizado y mentores expertos",
        "Ofrecemos cursos de marketing digital desde nivel básico hasta avanzado, dirigidos a profesionales y emprendedores",
        "Nuestro cliente ideal son profesionales de 25-45 años que buscan mejorar sus ingresos a través del marketing digital",
        "Resolvemos la falta de educación práctica y actualizada en marketing digital en el mercado latinoamericano",
        "Nos diferenciamos por tener contenido 100% en español, casos reales de la región y mentores con experiencia comprobada",
        "Enfrentamos el desafío de la competencia internacional pero tenemos la oportunidad de ser líderes en Latinoamérica",
        "Operamos en la industria de educación online y capacitación profesional"
    ]
    
    # Initialize session
    session_data = {
        "current_question_index": 0,
        "answers": {},
        "langchain_chat_history": [],
        "business_idea": business_data
    }
    
    # Start with welcome flow
    welcome_result = service.run_agent_turn("Iniciar brief", session_data)
    session_data = {
        "current_question_index": welcome_result['updated_current_question_index'],
        "answers": welcome_result['updated_answers'],
        "langchain_chat_history": welcome_result['updated_chat_history'],
        "business_idea": business_data
    }
    
    print("🔄 Answering all ETAPA 1 questions...")
    
    # Answer all ETAPA 1 questions
    mapping_triggered = False
    business_model_mapping = None
    
    for i, response in enumerate(etapa1_responses):
        print(f"  Question {i+1}/8: Answering...")
        
        result = service.run_agent_turn(response, session_data)
        
        # Update session
        session_data = {
            "current_question_index": result['updated_current_question_index'],
            "answers": result['updated_answers'],
            "langchain_chat_history": result['updated_chat_history'],
            "business_idea": business_data
        }
        
        # Check if ETAPA 1 was completed
        if result.get('etapa1_completed', False):
            mapping_triggered = True
            business_model_mapping = result.get('business_model_mapping', {})
            mapping_success = result.get('mapping_success', False)
            
            print(f"  🎉 ETAPA 1 completed! Mapping triggered: {mapping_triggered}")
            print(f"  📊 Mapping success: {mapping_success}")
            print(f"  📋 Mapped fields: {len(business_model_mapping) if business_model_mapping else 0}")
            break
    
    print(f"\n📊 RESULTS")
    print("="*60)
    
    print(f"✅ ETAPA 1 mapping triggered: {mapping_triggered}")
    
    if business_model_mapping:
        print(f"✅ Business model fields mapped: {len(business_model_mapping)}")
        print(f"\n📋 Mapped Fields:")
        for field, value in business_model_mapping.items():
            print(f"  • {field}: {value[:80]}...")
        
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
        
        missing_fields = [field for field in expected_fields if field not in business_model_mapping]
        present_fields = [field for field in expected_fields if field in business_model_mapping]
        
        print(f"\n✅ Present fields ({len(present_fields)}/{len(expected_fields)}): {', '.join(present_fields)}")
        if missing_fields:
            print(f"❌ Missing fields: {', '.join(missing_fields)}")
        
        success_rate = (len(present_fields) / len(expected_fields)) * 100
        print(f"\n🎯 Mapping completeness: {success_rate:.0f}%")
        
        if success_rate >= 85:
            assessment = "🎉 EXCELLENT: Business model mapping is working perfectly!"
        elif success_rate >= 70:
            assessment = "✅ GOOD: Business model mapping is working well!"
        elif success_rate >= 50:
            assessment = "⚠️ FAIR: Business model mapping needs some improvement!"
        else:
            assessment = "❌ POOR: Business model mapping needs significant work!"
            
        print(f"\n🏆 ASSESSMENT: {assessment}")
        
        return {
            "mapping_triggered": mapping_triggered,
            "mapping_success": True,
            "mapped_fields_count": len(business_model_mapping),
            "expected_fields_count": len(expected_fields),
            "success_rate": success_rate,
            "missing_fields": missing_fields,
            "business_model_mapping": business_model_mapping,
            "assessment": assessment
        }
    else:
        print("❌ No business model mapping generated")
        return {
            "mapping_triggered": mapping_triggered,
            "mapping_success": False,
            "error": "No mapping generated"
        }

async def test_phase_boundaries():
    """Test that phase boundaries are correctly calculated"""
    print("\n" + "="*60)
    print("🧪 Testing Phase Boundaries Calculation")
    print("="*60)
    
    service = BriefAgentService(llm_model="claude-3-5-sonnet-20241022")
    
    boundaries = service.get_phase_boundaries()
    
    print("📋 Phase Boundaries:")
    for phase, (start, end) in boundaries.items():
        print(f"  • {phase}: Questions {start} to {end} (total: {end-start+1})")
    
    # Test completion detection
    print(f"\n🔍 Testing completion detection:")
    
    # Test various indices
    test_indices = [0, 7, 8, 10, 11, 22, 23]
    
    for index in test_indices:
        etapa1_completed = service.is_phase_completed(index, "ETAPA 1: ENTENDIMIENTO DEL NEGOCIO")
        etapa2_completed = service.is_phase_completed(index, "ETAPA 2: NECESIDAD / OPORTUNIDAD DE COMUNICACIÓN")
        print(f"  Index {index}: ETAPA 1 completed: {etapa1_completed}, ETAPA 2 completed: {etapa2_completed}")
    
    return boundaries

async def main():
    """Main function to run all tests"""
    # Test phase boundaries
    boundaries = await test_phase_boundaries()
    
    # Test ETAPA 1 mapping
    mapping_results = await test_etapa1_mapping()
    
    print(f"\n🎯 FINAL SUMMARY")
    print("="*60)
    print(f"Phase boundaries: {len(boundaries)} phases detected")
    if mapping_results.get('mapping_success'):
        print(f"ETAPA 1 mapping: ✅ SUCCESS ({mapping_results['success_rate']:.0f}% completeness)")
    else:
        print(f"ETAPA 1 mapping: ❌ FAILED")
    
    return {
        "boundaries": boundaries,
        "mapping_results": mapping_results
    }

if __name__ == "__main__":
    result = asyncio.run(main())
    print(f"\n📊 Test completed: Mapping success = {result['mapping_results'].get('mapping_success', False)}") 