#!/usr/bin/env python3
"""
Simple test script to verify TaskIQ setup
"""
import asyncio
import os
import sys

# Add the app directory to Python path
sys.path.insert(0, '.')

# Set environment variables to ensure correct configuration
os.environ['REDIS_URL'] = 'redis://localhost:6379/0'

async def test_simple_task():
    """Test sending a simple task to TaskIQ"""
    try:
        from app.tasks.competitor_analysis_tasks import research_competitors_task
        
        print("📤 Testing TaskIQ task submission...")
        
        # Create a simple test task
        test_prompt = {
            "search_query": "Test search query",
            "callback_url": "http://localhost:8000/test",
            "request_id": "test-123",
            "business_id": "test-business-456",
            "base_url": "http://localhost:8000",
            "research_type": "test",
            "triggered_by": "manual_test"
        }
        
        test_business_model = {
            "business_idea": "Test business idea",
            "customer_persona": "Test customer",
            "industry": "Test industry",
            "problem_definition": "Test problem",
            "value_proposition": "Test value",
            "competitive_advantage": "Test advantage",
            "products_services": "Test products",
            "challenges_opportunities": "Test challenges"
        }
        
        # Send the task
        task = await research_competitors_task.kiq(
            prompt_search=test_prompt,
            business_id="test-business-456",
            request_id="test-123",
            business_model_dict=test_business_model,
            lang="en"
        )
        
        print(f"✅ Task sent successfully with ID: {task.task_id}")
        print("📊 Check TaskIQ Admin dashboard at http://localhost:3000")
        print("🔍 Check Redis queue with: redis-cli llen noit_backend_queue")
        
        return task.task_id
        
    except Exception as e:
        print(f"❌ Error testing TaskIQ: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    asyncio.run(test_simple_task()) 