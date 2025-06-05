#!/usr/bin/env python3
"""
Script de prueba para la tarea TaskIQ de análisis de Instagram
"""

import asyncio
import uuid
from app.tasks.instagram_analysis_tasks import run_instagram_full_analysis_task
from app.services.cache.task_progress_service import get_task_progress_service

async def test_instagram_analysis_task():
    """Probar la tarea de análisis de Instagram"""
    print("🧪 Testing Instagram analysis TaskIQ task...")
    
    # Mock data for testing
    business_id = "test-business-456"
    competitor_ids = ["competitor-1", "competitor-2"]
    task_id = str(uuid.uuid4())
    
    # Get progress service
    progress_service = get_task_progress_service()
    
    try:
        print(f"📤 Sending Instagram analysis task...")
        print(f"   Business ID: {business_id}")
        print(f"   Competitor IDs: {competitor_ids}")
        print(f"   Task ID: {task_id}")
        
        # Send task to TaskIQ
        taskiq_task = await run_instagram_full_analysis_task.kiq(
            business_id=business_id,
            task_id=task_id,
            competitor_ids=competitor_ids,
            results_limit=5,  # Reduce for testing
            max_comments=3   # Reduce for testing
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
        result = await taskiq_task.wait_result(timeout=180)  # 3 minutes
        
        print(f"⏱️  Task execution took: {result.execution_time} seconds")
        
        if not result.is_err:
            print(f"✅ Instagram analysis completed!")
            print(f"📊 Result: {result.return_value}")
            
            # Check final progress
            print("\n📊 Checking final progress...")
            final_progress = progress_service.get_task_progress(task_id)
            if final_progress:
                print(f"   Status: {final_progress['status']}")
                print(f"   Progress: {final_progress['progress']}%")
                print(f"   Results: {final_progress.get('results', 'None')}")
            
        else:
            print(f"❌ Error in Instagram analysis: {result.error}")
            
            # Check error progress
            error_progress = progress_service.get_task_progress(task_id)
            if error_progress:
                print(f"   Status: {error_progress['status']}")
                print(f"   Error: {error_progress.get('error', 'Unknown')}")
            
    except Exception as e:
        print(f"❌ Error testing Instagram analysis: {str(e)}")

async def test_instagram_task_without_competitors():
    """Probar la tarea con business ID que no tiene competidores"""
    print("\n🧪 Testing Instagram analysis with no competitors...")
    
    # Mock data for testing - business without competitors
    business_id = "test-business-no-competitors"
    task_id = str(uuid.uuid4())
    
    # Get progress service
    progress_service = get_task_progress_service()
    
    try:
        print(f"📤 Sending Instagram analysis task (no competitors)...")
        print(f"   Business ID: {business_id}")
        print(f"   Task ID: {task_id}")
        
        # Send task to TaskIQ
        taskiq_task = await run_instagram_full_analysis_task.kiq(
            business_id=business_id,
            task_id=task_id,
            competitor_ids=None,
            results_limit=5,
            max_comments=3
        )
        
        print(f"✅ Task queued with TaskIQ ID: {taskiq_task.task_id}")
        
        # Wait for result
        print("\n⏳ Waiting for task result...")
        result = await taskiq_task.wait_result(timeout=60)
        
        print(f"⏱️  Task execution took: {result.execution_time} seconds")
        
        if not result.is_err:
            print(f"✅ Instagram analysis completed (no competitors case)!")
            print(f"📊 Result: {result.return_value}")
            
            # Check final progress
            final_progress = progress_service.get_task_progress(task_id)
            if final_progress:
                print(f"   Status: {final_progress['status']}")
                print(f"   Results: {final_progress.get('results', 'None')}")
            
        else:
            print(f"❌ Error in Instagram analysis: {result.error}")
            
    except Exception as e:
        print(f"❌ Error testing Instagram analysis (no competitors): {str(e)}")

async def test_progress_service_instagram():
    """Probar el servicio de progreso específicamente para Instagram"""
    print("\n🧪 Testing TaskProgressService for Instagram...")
    
    progress_service = get_task_progress_service()
    test_task_id = f"test-instagram-task-{uuid.uuid4()}"
    
    try:
        # Test setting Instagram-specific progress
        print(f"📤 Setting initial Instagram analysis progress for task {test_task_id}")
        success = progress_service.set_task_progress(
            task_id=test_task_id,
            progress=15,
            status="processing",
            results={
                "competitor_1": {
                    "status": "processing",
                    "instagram_username": "test_user_1"
                }
            }
        )
        print(f"   Set progress: {'✅' if success else '❌'}")
        
        # Test updating with Instagram-specific data
        print(f"🔄 Updating Instagram analysis progress for task {test_task_id}")
        update_success = progress_service.update_task_progress(test_task_id, {
            "progress": 50,
            "status": "processing",
            "results": {
                "competitor_1": {
                    "status": "completed",
                    "instagram_username": "test_user_1",
                    "posts_scraped": 10,
                    "comments_analyzed": 45
                },
                "competitor_2": {
                    "status": "processing", 
                    "instagram_username": "test_user_2"
                }
            }
        })
        print(f"   Update progress: {'✅' if update_success else '❌'}")
        
        # Test completing Instagram analysis
        print(f"✅ Completing Instagram analysis task {test_task_id}")
        complete_success = progress_service.set_task_completed(
            task_id=test_task_id,
            results={
                "competitor_1": {
                    "status": "completed",
                    "instagram_username": "test_user_1",
                    "posts_scraped": 10,
                    "comments_analyzed": 45
                },
                "competitor_2": {
                    "status": "completed",
                    "instagram_username": "test_user_2", 
                    "posts_scraped": 8,
                    "comments_analyzed": 32
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
        print(f"❌ Error testing Instagram progress service: {str(e)}")

async def main():
    """Función principal para ejecutar las pruebas"""
    print("🚀 Starting TaskIQ Instagram Analysis tests...")
    print("=" * 60)
    
    # Test progress service first
    await test_progress_service_instagram()
    print()
    
    # Test the actual TaskIQ task with competitors
    await test_instagram_analysis_task()
    print()
    
    # Test with no competitors scenario
    await test_instagram_task_without_competitors()
    print()
    
    print("🏁 Instagram TaskIQ tests completed!")

if __name__ == "__main__":
    asyncio.run(main()) 