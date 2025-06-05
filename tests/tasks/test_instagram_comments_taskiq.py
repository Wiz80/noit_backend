#!/usr/bin/env python3
"""
Script de prueba para la tarea TaskIQ de análisis completo de comentarios de Instagram
"""

import asyncio
import uuid
from app.tasks.instagram_analysis_tasks import complete_instagram_comments_analysis_task
from app.services.cache.task_progress_service import get_task_progress_service

async def test_comments_analysis_task():
    """Probar la tarea de análisis completo de comentarios de Instagram"""
    print("🧪 Testing Instagram comments analysis TaskIQ task...")
    
    # Mock data for testing
    business_id = "test-business-789"
    username = "test_instagram_user"
    task_id = str(uuid.uuid4())
    
    # Get progress service
    progress_service = get_task_progress_service()
    
    try:
        print(f"📤 Sending Instagram comments analysis task...")
        print(f"   Business ID: {business_id}")
        print(f"   Username: {username}")
        print(f"   Task ID: {task_id}")
        
        # Send task to TaskIQ
        taskiq_task = await complete_instagram_comments_analysis_task.kiq(
            business_id=business_id,
            username=username,
            task_id=task_id,
            num_topics=3,  # Reduce for testing
            max_comments=20,  # Reduce for testing
            provider="openai",
            model="gpt-4o-mini",
            lang="es"
        )
        
        print(f"✅ Task queued with TaskIQ ID: {taskiq_task.task_id}")
        
        # Check initial progress
        print("\n📊 Checking initial progress...")
        progress = progress_service.get_task_progress(task_id)
        if progress:
            print(f"   Status: {progress['status']}")
            print(f"   Progress: {progress['progress']}%")
        else:
            print("   No progress data found yet")
        
        # Wait for result (with longer timeout for complex task)
        print("\n⏳ Waiting for task result...")
        result = await taskiq_task.wait_result(timeout=300)  # 5 minutes
        
        print(f"⏱️  Task execution took: {result.execution_time} seconds")
        
        if not result.is_err:
            print(f"✅ Comments analysis completed!")
            print(f"📊 Result: {result.return_value}")
            
            # Check final progress
            print("\n📊 Checking final progress...")
            final_progress = progress_service.get_task_progress(task_id)
            if final_progress:
                print(f"   Status: {final_progress['status']}")
                print(f"   Progress: {final_progress['progress']}%")
                print(f"   Results: {final_progress.get('results', 'None')}")
            
        else:
            print(f"❌ Error in comments analysis: {result.error}")
            
            # Check error progress
            error_progress = progress_service.get_task_progress(task_id)
            if error_progress:
                print(f"   Status: {error_progress['status']}")
                print(f"   Error: {error_progress.get('error', 'Unknown')}")
            
    except Exception as e:
        print(f"❌ Error testing comments analysis: {str(e)}")

async def test_comments_task_with_invalid_user():
    """Probar la tarea con usuario de Instagram que no existe"""
    print("\n🧪 Testing comments analysis with invalid Instagram user...")
    
    # Mock data for testing - invalid user
    business_id = "test-business-invalid"
    username = "non_existent_user_123456"
    task_id = str(uuid.uuid4())
    
    # Get progress service
    progress_service = get_task_progress_service()
    
    try:
        print(f"📤 Sending comments analysis task (invalid user)...")
        print(f"   Business ID: {business_id}")
        print(f"   Username: {username}")
        print(f"   Task ID: {task_id}")
        
        # Send task to TaskIQ
        taskiq_task = await complete_instagram_comments_analysis_task.kiq(
            business_id=business_id,
            username=username,
            task_id=task_id,
            num_topics=3,
            max_comments=20,
            provider="openai",
            model="gpt-4o-mini",
            lang="es"
        )
        
        print(f"✅ Task queued with TaskIQ ID: {taskiq_task.task_id}")
        
        # Wait for result
        print("\n⏳ Waiting for task result...")
        result = await taskiq_task.wait_result(timeout=60)
        
        print(f"⏱️  Task execution took: {result.execution_time} seconds")
        
        if not result.is_err:
            print(f"✅ Comments analysis completed (invalid user case)!")
            print(f"📊 Result: {result.return_value}")
            
            # Check final progress
            final_progress = progress_service.get_task_progress(task_id)
            if final_progress:
                print(f"   Status: {final_progress['status']}")
                print(f"   Results: {final_progress.get('results', 'None')}")
            
        else:
            print(f"❌ Error in comments analysis (expected): {result.error}")
            
    except Exception as e:
        print(f"❌ Error testing comments analysis (invalid user): {str(e)}")

async def test_progress_service_comments():
    """Probar el servicio de progreso específicamente para análisis de comentarios"""
    print("\n🧪 Testing TaskProgressService for comments analysis...")
    
    progress_service = get_task_progress_service()
    test_task_id = f"test-comments-task-{uuid.uuid4()}"
    
    try:
        # Test setting comments-specific progress
        print(f"📤 Setting initial comments analysis progress for task {test_task_id}")
        success = progress_service.set_task_progress(
            task_id=test_task_id,
            progress=15,
            status="processing",
            results={
                "current_step": "categorization",
                "username": "test_user",
                "analysis_type": "instagram_comments"
            }
        )
        print(f"   Set progress: {'✅' if success else '❌'}")
        
        # Test updating with comments-specific data
        print(f"🔄 Updating comments analysis progress for task {test_task_id}")
        update_success = progress_service.update_task_progress(test_task_id, {
            "progress": 50,
            "status": "processing",
            "results": {
                "current_step": "sentiment_analysis",
                "username": "test_user",
                "categorization": {
                    "status": "completed",
                    "categories_found": 8
                }
            }
        })
        print(f"   Update progress: {'✅' if update_success else '❌'}")
        
        # Test completing comments analysis
        print(f"✅ Completing comments analysis task {test_task_id}")
        complete_success = progress_service.set_task_completed(
            task_id=test_task_id,
            results={
                "username": "test_user",
                "analysis_results": {
                    "categorization": {
                        "status": "completed",
                        "categories_found": 8
                    },
                    "sentiment_emotion": {
                        "status": "completed",
                        "sentiment_path": "/path/to/sentiment.json"
                    },
                    "topic_modeling": {
                        "status": "completed",
                        "topics_count": 5
                    }
                }
            }
        )
        print(f"   Complete task: {'✅' if complete_success else '❌'}")
        
        # Check final state
        final_progress = progress_service.get_task_progress(test_task_id)
        if final_progress:
            print(f"   Final state: {final_progress}")
        
        # Clean up
        print(f"🗑️  Cleaning up test task {test_task_id}")
        delete_success = progress_service.delete_task_progress(test_task_id)
        print(f"   Delete task: {'✅' if delete_success else '❌'}")
        
    except Exception as e:
        print(f"❌ Error testing comments progress service: {str(e)}")

async def test_comments_analysis_steps():
    """Probar los pasos individuales del análisis de comentarios"""
    print("\n🧪 Testing individual steps of comments analysis...")
    
    # Mock data for testing
    business_id = "test-business-steps"
    username = "test_steps_user"
    task_id = str(uuid.uuid4())
    
    # Get progress service
    progress_service = get_task_progress_service()
    
    try:
        print(f"📤 Testing step-by-step comments analysis...")
        print(f"   Business ID: {business_id}")
        print(f"   Username: {username}")
        print(f"   Task ID: {task_id}")
        
        # Manually simulate the progress steps
        steps = [
            {"progress": 0, "status": "queued", "step": "initialized"},
            {"progress": 10, "status": "processing", "step": "starting_analysis"},
            {"progress": 15, "status": "processing", "step": "categorization"},
            {"progress": 40, "status": "processing", "step": "sentiment_analysis"},
            {"progress": 70, "status": "processing", "step": "topic_modeling"},
            {"progress": 100, "status": "completed", "step": "finished"}
        ]
        
        for i, step in enumerate(steps):
            print(f"   📊 Step {i+1}: {step['step']} ({step['progress']}%)")
            
            if step['status'] == 'completed':
                progress_service.set_task_completed(
                    task_id=task_id,
                    results={
                        "username": username,
                        "final_step": step['step']
                    }
                )
            else:
                progress_service.set_task_progress(
                    task_id=task_id,
                    progress=step['progress'],
                    status=step['status'],
                    results={
                        "current_step": step['step'],
                        "username": username
                    }
                )
            
            # Small delay to simulate processing
            await asyncio.sleep(0.5)
            
            # Check progress
            current_progress = progress_service.get_task_progress(task_id)
            if current_progress:
                print(f"      Current status: {current_progress['status']}")
                print(f"      Current progress: {current_progress['progress']}%")
        
        print("✅ Step-by-step test completed!")
        
        # Clean up
        progress_service.delete_task_progress(task_id)
        
    except Exception as e:
        print(f"❌ Error testing step-by-step analysis: {str(e)}")

async def main():
    """Función principal para ejecutar las pruebas"""
    print("🚀 Starting TaskIQ Instagram Comments Analysis tests...")
    print("=" * 70)
    
    # Test progress service first
    await test_progress_service_comments()
    print()
    
    # Test step-by-step analysis
    await test_comments_analysis_steps()
    print()
    
    # Test with invalid user scenario
    await test_comments_task_with_invalid_user()
    print()
    
    # Test the actual TaskIQ task (commented out as it requires real data)
    print("⚠️  Skipping actual TaskIQ task test (requires real Instagram user data)")
    print("   To test with real data, uncomment the following line:")
    print("   # await test_comments_analysis_task()")
    print()
    
    print("🏁 Instagram Comments TaskIQ tests completed!")

if __name__ == "__main__":
    asyncio.run(main()) 