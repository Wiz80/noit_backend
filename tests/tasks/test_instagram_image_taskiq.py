#!/usr/bin/env python3
"""
Script de prueba para la tarea TaskIQ de análisis completo de imágenes de Instagram
"""

import asyncio
import uuid
from app.tasks.instagram_analysis_tasks import complete_instagram_image_analysis_task
from app.services.cache.task_progress_service import get_task_progress_service

async def test_image_analysis_task():
    """Probar la tarea de análisis completo de imágenes de Instagram"""
    print("🧪 Testing Instagram image analysis TaskIQ task...")
    
    # Mock data for testing
    business_id = "test-business-image-123"
    username = "test_instagram_user"
    task_id = str(uuid.uuid4())
    
    # Get progress service
    progress_service = get_task_progress_service()
    
    try:
        print(f"📤 Sending Instagram image analysis task...")
        print(f"   Business ID: {business_id}")
        print(f"   Username: {username}")
        print(f"   Task ID: {task_id}")
        
        # Send task to TaskIQ
        taskiq_task = await complete_instagram_image_analysis_task.kiq(
            business_id=business_id,
            username=username,
            task_id=task_id,
            posts_limit=5  # Reduce for testing
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
        
        # Wait for result (with longer timeout for image analysis)
        print("\n⏳ Waiting for task result...")
        result = await taskiq_task.wait_result(timeout=600)  # 10 minutes
        
        print(f"⏱️  Task execution took: {result.execution_time} seconds")
        
        if not result.is_err:
            print(f"✅ Image analysis completed!")
            print(f"📊 Result: {result.return_value}")
            
            # Check final progress
            print("\n📊 Checking final progress...")
            final_progress = progress_service.get_task_progress(task_id)
            if final_progress:
                print(f"   Status: {final_progress['status']}")
                print(f"   Progress: {final_progress['progress']}%")
                print(f"   Results: {final_progress.get('results', 'None')}")
            
        else:
            print(f"❌ Error in image analysis: {result.error}")
            
            # Check error progress
            error_progress = progress_service.get_task_progress(task_id)
            if error_progress:
                print(f"   Status: {error_progress['status']}")
                print(f"   Error: {error_progress.get('error', 'Unknown')}")
            
    except Exception as e:
        print(f"❌ Error testing image analysis: {str(e)}")

async def test_image_task_with_invalid_user():
    """Probar la tarea con usuario de Instagram que no existe"""
    print("\n🧪 Testing image analysis with invalid Instagram user...")
    
    # Mock data for testing - invalid user
    business_id = "test-business-invalid-image"
    username = "non_existent_user_images_123456"
    task_id = str(uuid.uuid4())
    
    # Get progress service
    progress_service = get_task_progress_service()
    
    try:
        print(f"📤 Sending image analysis task (invalid user)...")
        print(f"   Business ID: {business_id}")
        print(f"   Username: {username}")
        print(f"   Task ID: {task_id}")
        
        # Send task to TaskIQ
        taskiq_task = await complete_instagram_image_analysis_task.kiq(
            business_id=business_id,
            username=username,
            task_id=task_id,
            posts_limit=5
        )
        
        print(f"✅ Task queued with TaskIQ ID: {taskiq_task.task_id}")
        
        # Wait for result
        print("\n⏳ Waiting for task result...")
        result = await taskiq_task.wait_result(timeout=60)
        
        print(f"⏱️  Task execution took: {result.execution_time} seconds")
        
        if not result.is_err:
            print(f"✅ Image analysis completed (invalid user case)!")
            print(f"📊 Result: {result.return_value}")
            
            # Check final progress
            final_progress = progress_service.get_task_progress(task_id)
            if final_progress:
                print(f"   Status: {final_progress['status']}")
                print(f"   Results: {final_progress.get('results', 'None')}")
            
        else:
            print(f"❌ Error in image analysis (expected): {result.error}")
            
    except Exception as e:
        print(f"❌ Error testing image analysis (invalid user): {str(e)}")

async def test_progress_service_images():
    """Probar el servicio de progreso específicamente para análisis de imágenes"""
    print("\n🧪 Testing TaskProgressService for image analysis...")
    
    progress_service = get_task_progress_service()
    test_task_id = f"test-image-task-{uuid.uuid4()}"
    
    try:
        # Test setting image-specific progress
        print(f"📤 Setting initial image analysis progress for task {test_task_id}")
        success = progress_service.set_task_progress(
            task_id=test_task_id,
            progress=20,
            status="processing",
            results={
                "current_step": "fetching_posts",
                "username": "test_user",
                "analysis_type": "instagram_images"
            }
        )
        print(f"   Set progress: {'✅' if success else '❌'}")
        
        # Test updating with image-specific data
        print(f"🔄 Updating image analysis progress for task {test_task_id}")
        update_success = progress_service.update_task_progress(test_task_id, {
            "progress": 60,
            "status": "processing",
            "results": {
                "current_step": "processing_posts_images",
                "username": "test_user",
                "posts_count": 10,
                "posts_processed": 6
            }
        })
        print(f"   Update progress: {'✅' if update_success else '❌'}")
        
        # Test completing image analysis
        print(f"✅ Completing image analysis task {test_task_id}")
        complete_success = progress_service.set_task_completed(
            task_id=test_task_id,
            results={
                "username": "test_user",
                "analysis_results": {
                    "posts_images": {
                        "status": "completed",
                        "posts_processed": 10
                    },
                    "database_save": {
                        "status": "completed"
                    },
                    "feed_analysis": {
                        "status": "completed"
                    }
                },
                "posts_processed": 10
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
        print(f"❌ Error testing image progress service: {str(e)}")

async def test_image_analysis_steps():
    """Probar los pasos individuales del análisis de imágenes"""
    print("\n🧪 Testing individual steps of image analysis...")
    
    # Mock data for testing
    business_id = "test-business-image-steps"
    username = "test_steps_user"
    task_id = str(uuid.uuid4())
    
    # Get progress service
    progress_service = get_task_progress_service()
    
    try:
        print(f"📤 Testing step-by-step image analysis...")
        print(f"   Business ID: {business_id}")
        print(f"   Username: {username}")
        print(f"   Task ID: {task_id}")
        
        # Manually simulate the progress steps
        steps = [
            {"progress": 0, "status": "queued", "step": "initialized"},
            {"progress": 10, "status": "processing", "step": "starting_analysis"},
            {"progress": 20, "status": "processing", "step": "fetching_posts"},
            {"progress": 30, "status": "processing", "step": "processing_posts_images"},
            {"progress": 70, "status": "processing", "step": "saving_to_database"},
            {"progress": 85, "status": "processing", "step": "analyzing_feed"},
            {"progress": 100, "status": "completed", "step": "finished"}
        ]
        
        for i, step in enumerate(steps):
            print(f"   📊 Step {i+1}: {step['step']} ({step['progress']}%)")
            
            if step['status'] == 'completed':
                progress_service.set_task_completed(
                    task_id=task_id,
                    results={
                        "username": username,
                        "final_step": step['step'],
                        "posts_processed": 10
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

async def test_image_analysis_with_posts_limit():
    """Probar análisis de imágenes con límite de posts"""
    print("\n🧪 Testing image analysis with posts limit...")
    
    # Mock data for testing
    business_id = "test-business-limit"
    username = "test_limit_user"
    task_id = str(uuid.uuid4())
    posts_limit = 3
    
    # Get progress service
    progress_service = get_task_progress_service()
    
    try:
        print(f"📤 Testing image analysis with posts limit...")
        print(f"   Business ID: {business_id}")
        print(f"   Username: {username}")
        print(f"   Posts Limit: {posts_limit}")
        print(f"   Task ID: {task_id}")
        
        # Simulate setting progress for limited posts
        progress_service.set_task_progress(
            task_id=task_id,
            progress=30,
            status="processing",
            results={
                "current_step": "processing_posts_images",
                "username": username,
                "posts_count": posts_limit,
                "posts_limit_applied": True
            }
        )
        
        # Check progress
        current_progress = progress_service.get_task_progress(task_id)
        if current_progress:
            print(f"   ✅ Progress set with posts limit")
            print(f"      Posts count: {current_progress['results']['posts_count']}")
            print(f"      Limit applied: {current_progress['results']['posts_limit_applied']}")
        
        # Complete with limited results
        progress_service.set_task_completed(
            task_id=task_id,
            results={
                "username": username,
                "posts_processed": posts_limit,
                "limit_applied": True,
                "analysis_results": {
                    "posts_images": {"status": "completed", "posts_processed": posts_limit}
                }
            }
        )
        
        print("✅ Posts limit test completed!")
        
        # Clean up
        progress_service.delete_task_progress(task_id)
        
    except Exception as e:
        print(f"❌ Error testing posts limit: {str(e)}")

async def main():
    """Función principal para ejecutar las pruebas"""
    print("🚀 Starting TaskIQ Instagram Image Analysis tests...")
    print("=" * 70)
    
    # Test progress service first
    await test_progress_service_images()
    print()
    
    # Test step-by-step analysis
    await test_image_analysis_steps()
    print()
    
    # Test posts limit functionality
    await test_image_analysis_with_posts_limit()
    print()
    
    # Test with invalid user scenario
    await test_image_task_with_invalid_user()
    print()
    
    # Test the actual TaskIQ task (commented out as it requires real data)
    print("⚠️  Skipping actual TaskIQ task test (requires real Instagram user data and posts)")
    print("   To test with real data, uncomment the following line:")
    print("   # await test_image_analysis_task()")
    print()
    
    print("🏁 Instagram Image TaskIQ tests completed!")

if __name__ == "__main__":
    asyncio.run(main()) 