#!/usr/bin/env python3
"""
Script de prueba para TaskIQ - Análisis de Competidores
"""

import asyncio
from app.tasks.competitor_analysis_tasks import research_competitors_task
from app.tasks.example_tasks import add_numbers, process_data

async def test_simple_task():
    """Probar una tarea simple"""
    print("🧪 Testing simple add_numbers task...")
    
    # Enviar tarea
    task = await add_numbers.kiq(5, 3)
    print(f"📤 Task sent with ID: {task.task_id}")
    
    # Esperar resultado
    result = await task.wait_result(timeout=10)
    print(f"⏱️  Task execution took: {result.execution_time} seconds")
    
    if not result.is_err:
        print(f"✅ Result: {result.return_value}")
    else:
        print(f"❌ Error: {result.error}")

async def test_competitor_analysis_task():
    """Probar la tarea de análisis de competidores"""
    print("🔍 Testing competitor analysis task...")
    
    # Datos de prueba
    prompt_search = {
        "search_query": "Competitors in fintech industry",
        "callback_url": "http://localhost:8000/api/callback",
        "request_id": "test-request-123",
        "business_id": "test-business-456",
        "base_url": "http://localhost:8000",
        "research_type": "competitor_analysis",
        "triggered_by": "test_script"
    }
    
    business_model_dict = {
        "business_idea": "Fintech app for personal finance management",
        "customer_persona": "Young professionals aged 25-35",
        "industry": "Financial Technology",
        "problem_definition": "People struggle to manage their personal finances",
        "value_proposition": "Simple, automated personal finance management",
        "competitive_advantage": "AI-powered insights and recommendations",
        "products_services": "Mobile app with budget tracking and investment advice",
        "challenges_opportunities": "Regulatory compliance and user trust"
    }
    
    try:
        # Enviar tarea
        task = await research_competitors_task.kiq(
            prompt_search=prompt_search,
            business_id="test-business-456",
            request_id="test-request-123",
            business_model_dict=business_model_dict,
            lang="en"
        )
        print(f"📤 Competitor analysis task sent with ID: {task.task_id}")
        
        # Esperar resultado (aumentamos el timeout porque es una tarea más compleja)
        print("⏳ Waiting for result (this may take a while)...")
        result = await task.wait_result(timeout=60)
        print(f"⏱️  Task execution took: {result.execution_time} seconds")
        
        if not result.is_err:
            print(f"✅ Competitor analysis completed!")
            print(f"📊 Result: {result.return_value}")
        else:
            print(f"❌ Error in competitor analysis: {result.error}")
            
    except Exception as e:
        print(f"❌ Error testing competitor analysis: {str(e)}")

async def main():
    """Función principal para ejecutar las pruebas"""
    print("🚀 Starting TaskIQ tests...")
    print("=" * 50)
    
    # Probar tarea simple primero
    await test_simple_task()
    print()
    
    # Probar tarea de análisis de competidores
    await test_competitor_analysis_task()
    print()
    
    print("🏁 Tests completed!")

if __name__ == "__main__":
    asyncio.run(main()) 