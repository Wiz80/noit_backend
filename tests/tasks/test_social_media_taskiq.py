#!/usr/bin/env python3
"""
Script de prueba para la tarea TaskIQ de extracción de social media
"""

import asyncio
import uuid
from app.tasks.social_media_extraction_tasks import extract_social_media_from_websites_task
from app.services.cache.task_progress_service import get_task_progress_service

async def test_social_media_extraction_task():
    """Probar la tarea de extracción de social media"""
    print("🧪 Testing social media extraction TaskIQ task...")
    
    # Mock data for testing
    business_id = "test-business-123"
    competitor_ids = ["competitor-1", "competitor-2"]
    task_id = str(uuid.uuid4())
    
    # Get progress service
    progress_service = get_task_progress_service()
    
    try:
        print(f"📤 Sending social media extraction task...")
        print(f"   Business ID: {business_id}")
        print(f"   Competitor IDs: {competitor_ids}")
        print(f"   Task ID: {task_id}")
        
        # Send task to TaskIQ
        taskiq_task = await extract_social_media_from_websites_task.kiq(
            business_id=business_id,
            competitor_ids=competitor_ids,
            task_id=task_id,
            update_db=False  # Don't update DB in test
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
        result = await taskiq_task.wait_result(timeout=120)
        
        print(f"⏱️  Task execution took: {result.execution_time} seconds")
        
        if not result.is_err:
            print(f"✅ Social media extraction completed!")
            print(f"📊 Result: {result.return_value}")
            
            # Check final progress
            print("\n📊 Checking final progress...")
            final_progress = progress_service.get_task_progress(task_id)
            if final_progress:
                print(f"   Status: {final_progress['status']}")
                print(f"   Progress: {final_progress['progress']}%")
                print(f"   Results: {final_progress.get('results', 'None')}")
            
        else:
            print(f"❌ Error in social media extraction: {result.error}")
            
            # Check error progress
            error_progress = progress_service.get_task_progress(task_id)
            if error_progress:
                print(f"   Status: {error_progress['status']}")
                print(f"   Error: {error_progress.get('error', 'Unknown')}")
            
    except Exception as e:
        print(f"❌ Error testing social media extraction: {str(e)}")

async def test_progress_service():
    """Probar el servicio de progreso directamente"""
    print("\n🧪 Testing TaskProgressService...")
    
    progress_service = get_task_progress_service()
    test_task_id = f"test-task-{uuid.uuid4()}"
    
    try:
        # Test setting progress
        print(f"📤 Setting initial progress for task {test_task_id}")
        success = progress_service.set_task_progress(
            task_id=test_task_id,
            progress=25,
            status="processing",
            results={"test": "data"}
        )
        print(f"   Set progress: {'✅' if success else '❌'}")
        
        # Test getting progress
        print(f"📥 Getting progress for task {test_task_id}")
        progress = progress_service.get_task_progress(test_task_id)
        if progress:
            print(f"   ✅ Got progress: {progress}")
        else:
            print(f"   ❌ Failed to get progress")
        
        # Test updating progress
        print(f"🔄 Updating progress for task {test_task_id}")
        update_success = progress_service.update_task_progress(test_task_id, {
            "progress": 75,
            "status": "almost_done"
        })
        print(f"   Update progress: {'✅' if update_success else '❌'}")
        
        # Test completing task
        print(f"✅ Completing task {test_task_id}")
        complete_success = progress_service.set_task_completed(
            task_id=test_task_id,
            results={"final": "result", "items_processed": 10}
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
        print(f"❌ Error testing progress service: {str(e)}")

async def main():
    """Función principal para ejecutar las pruebas"""
    print("🚀 Starting TaskIQ Social Media Extraction tests...")
    print("=" * 60)
    
    # Test progress service first
    await test_progress_service()
    print()
    
    # Test the actual TaskIQ task
    await test_social_media_extraction_task()
    print()
    
    print("🏁 Tests completed!")

if __name__ == "__main__":
    asyncio.run(main()) 