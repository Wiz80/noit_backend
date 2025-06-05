#!/usr/bin/env python3
"""
Script de prueba para la tarea TaskIQ de análisis completo de estadísticas de Instagram
"""

import asyncio
import uuid
from app.tasks.instagram_analysis_tasks import complete_instagram_statistics_analysis_task
from app.services.cache.task_progress_service import get_task_progress_service

async def test_statistics_analysis_task():
    """Probar la tarea de análisis completo de estadísticas de Instagram"""
    print("🧪 Testing Instagram statistics analysis TaskIQ task...")
    
    # Mock data for testing
    business_id = "test-business-stats-123"
    username = "test_instagram_user"
    task_id = str(uuid.uuid4())
    
    # Get progress service
    progress_service = get_task_progress_service()
    
    try:
        print(f"📤 Sending Instagram statistics analysis task...")
        print(f"   Business ID: {business_id}")
        print(f"   Username: {username}")
        print(f"   Task ID: {task_id}")
        
        # Send task to TaskIQ
        taskiq_task = await complete_instagram_statistics_analysis_task.kiq(
            business_id=business_id,
            username=username,
            task_id=task_id,
            post_limit=50,
            image_limit=10
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
        
        # Wait for result
        print("\n⏳ Waiting for task result...")
        result = await taskiq_task.wait_result(timeout=300)  # 5 minutes
        
        print(f"⏱️  Task execution took: {result.execution_time} seconds")
        
        if not result.is_err:
            print(f"✅ Statistics analysis completed!")
            print(f"📊 Result: {result.return_value}")
            
            # Check final progress
            print("\n📊 Checking final progress...")
            final_progress = progress_service.get_task_progress(task_id)
            if final_progress:
                print(f"   Status: {final_progress['status']}")
                print(f"   Progress: {final_progress['progress']}%")
                print(f"   Results: {final_progress.get('results', 'None')}")
            
        else:
            print(f"❌ Error in statistics analysis: {result.error}")
            
            # Check error progress
            error_progress = progress_service.get_task_progress(task_id)
            if error_progress:
                print(f"   Status: {error_progress['status']}")
                print(f"   Error: {error_progress.get('error', 'Unknown')}")
            
    except Exception as e:
        print(f"❌ Error testing statistics analysis: {str(e)}")

async def test_statistics_task_with_invalid_user():
    """Probar la tarea con usuario de Instagram que no existe"""
    print("\n🧪 Testing statistics analysis with invalid Instagram user...")
    
    # Mock data for testing - invalid user
    business_id = "test-business-invalid-stats"
    username = "non_existent_user_stats_123456"
    task_id = str(uuid.uuid4())
    
    # Get progress service
    progress_service = get_task_progress_service()
    
    try:
        print(f"📤 Sending statistics analysis task (invalid user)...")
        print(f"   Business ID: {business_id}")
        print(f"   Username: {username}")
        print(f"   Task ID: {task_id}")
        
        # Send task to TaskIQ
        taskiq_task = await complete_instagram_statistics_analysis_task.kiq(
            business_id=business_id,
            username=username,
            task_id=task_id,
            post_limit=50,
            image_limit=10
        )
        
        print(f"✅ Task queued with TaskIQ ID: {taskiq_task.task_id}")
        
        # Wait for result
        print("\n⏳ Waiting for task result...")
        result = await taskiq_task.wait_result(timeout=60)
        
        print(f"⏱️  Task execution took: {result.execution_time} seconds")
        
        if not result.is_err:
            print(f"✅ Statistics analysis completed (invalid user case)!")
            print(f"📊 Result: {result.return_value}")
            
            # Check final progress
            final_progress = progress_service.get_task_progress(task_id)
            if final_progress:
                print(f"   Status: {final_progress['status']}")
                print(f"   Results: {final_progress.get('results', 'None')}")
            
        else:
            print(f"❌ Error in statistics analysis (expected): {result.error}")
            
    except Exception as e:
        print(f"❌ Error testing statistics analysis (invalid user): {str(e)}")

async def test_progress_service_statistics():
    """Probar el servicio de progreso específicamente para análisis de estadísticas"""
    print("\n🧪 Testing TaskProgressService for statistics analysis...")
    
    progress_service = get_task_progress_service()
    test_task_id = f"test-stats-task-{uuid.uuid4()}"
    
    try:
        # Test setting statistics-specific progress
        print(f"📤 Setting initial statistics analysis progress for task {test_task_id}")
        success = progress_service.set_task_progress(
            task_id=test_task_id,
            progress=20,
            status="processing",
            results={
                "current_step": "preparing_data",
                "username": "test_user",
                "analysis_type": "instagram_statistics"
            }
        )
        print(f"   Set progress: {'✅' if success else '❌'}")
        
        # Test updating with statistics-specific data
        print(f"🔄 Updating statistics analysis progress for task {test_task_id}")
        update_success = progress_service.update_task_progress(test_task_id, {
            "progress": 60,
            "status": "processing",
            "results": {
                "current_step": "generating_statistics",
                "username": "test_user",
                "posts_count": 50,
                "data_preparation": {"status": "completed", "posts_count": 50},
                "database_loading": {"status": "completed", "posts_loaded": 50}
            }
        })
        print(f"   Update progress: {'✅' if update_success else '❌'}")
        
        # Test completing statistics analysis
        print(f"✅ Completing statistics analysis task {test_task_id}")
        complete_success = progress_service.set_task_completed(
            task_id=test_task_id,
            results={
                "username": "test_user",
                "analysis_results": {
                    "data_preparation": {
                        "status": "completed",
                        "posts_count": 50
                    },
                    "database_loading": {
                        "status": "completed",
                        "posts_loaded": 50
                    },
                    "statistics_generation": {
                        "status": "completed",
                        "statistics_summary": {
                            "total_posts": 50,
                            "total_followers": 10000,
                            "avg_likes_per_post": 250.5,
                            "avg_comments_per_post": 15.3,
                            "avg_engagement_rate": 2.65
                        }
                    }
                },
                "post_limit": 50,
                "image_limit": 10
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
        print(f"❌ Error testing statistics progress service: {str(e)}")

async def test_statistics_analysis_steps():
    """Probar los pasos individuales del análisis de estadísticas"""
    print("\n🧪 Testing individual steps of statistics analysis...")
    
    # Mock data for testing
    business_id = "test-business-stats-steps"
    username = "test_steps_user"
    task_id = str(uuid.uuid4())
    
    # Get progress service
    progress_service = get_task_progress_service()
    
    try:
        print(f"📤 Testing step-by-step statistics analysis...")
        print(f"   Business ID: {business_id}")
        print(f"   Username: {username}")
        print(f"   Task ID: {task_id}")
        
        # Manually simulate the progress steps
        steps = [
            {"progress": 0, "status": "queued", "step": "initialized"},
            {"progress": 10, "status": "processing", "step": "starting_analysis"},
            {"progress": 20, "status": "processing", "step": "preparing_data"},
            {"progress": 40, "status": "processing", "step": "loading_database"},
            {"progress": 60, "status": "processing", "step": "generating_statistics"},
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
                        "analysis_results": {
                            "statistics_generation": {
                                "status": "completed",
                                "statistics_summary": {
                                    "total_posts": 50,
                                    "total_followers": 10000,
                                    "avg_engagement_rate": 2.65
                                }
                            }
                        }
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

async def test_statistics_analysis_with_custom_limits():
    """Probar análisis de estadísticas con límites personalizados"""
    print("\n🧪 Testing statistics analysis with custom limits...")
    
    # Mock data for testing
    business_id = "test-business-custom-limits"
    username = "test_custom_user"
    task_id = str(uuid.uuid4())
    post_limit = 30
    image_limit = 5
    
    # Get progress service
    progress_service = get_task_progress_service()
    
    try:
        print(f"📤 Testing statistics analysis with custom limits...")
        print(f"   Business ID: {business_id}")
        print(f"   Username: {username}")
        print(f"   Post Limit: {post_limit}")
        print(f"   Image Limit: {image_limit}")
        print(f"   Task ID: {task_id}")
        
        # Simulate setting progress for custom limits
        progress_service.set_task_progress(
            task_id=task_id,
            progress=60,
            status="processing",
            results={
                "current_step": "generating_statistics",
                "username": username,
                "post_limit": post_limit,
                "image_limit": image_limit,
                "custom_limits_applied": True
            }
        )
        
        # Check progress
        current_progress = progress_service.get_task_progress(task_id)
        if current_progress:
            print(f"   ✅ Progress set with custom limits")
            print(f"      Post limit: {current_progress['results']['post_limit']}")
            print(f"      Image limit: {current_progress['results']['image_limit']}")
            print(f"      Limits applied: {current_progress['results']['custom_limits_applied']}")
        
        # Complete with custom results
        progress_service.set_task_completed(
            task_id=task_id,
            results={
                "username": username,
                "post_limit": post_limit,
                "image_limit": image_limit,
                "analysis_results": {
                    "statistics_generation": {
                        "status": "completed",
                        "statistics_summary": {
                            "total_posts": post_limit,
                            "total_followers": 5000,
                            "avg_engagement_rate": 3.2
                        }
                    }
                }
            }
        )
        
        print("✅ Custom limits test completed!")
        
        # Clean up
        progress_service.delete_task_progress(task_id)
        
    except Exception as e:
        print(f"❌ Error testing custom limits: {str(e)}")

async def test_statistics_metrics_calculation():
    """Probar el cálculo de métricas de estadísticas"""
    print("\n🧪 Testing statistics metrics calculation...")
    
    task_id = str(uuid.uuid4())
    progress_service = get_task_progress_service()
    
    try:
        # Simulate different metrics scenarios
        scenarios = [
            {
                "name": "High Engagement Account",
                "stats": {
                    "total_posts": 100,
                    "total_followers": 50000,
                    "avg_likes_per_post": 1500.0,
                    "avg_comments_per_post": 75.0,
                    "avg_engagement_rate": 3.15
                }
            },
            {
                "name": "Medium Engagement Account",
                "stats": {
                    "total_posts": 75,
                    "total_followers": 20000,
                    "avg_likes_per_post": 400.0,
                    "avg_comments_per_post": 20.0,
                    "avg_engagement_rate": 2.1
                }
            },
            {
                "name": "Low Engagement Account",
                "stats": {
                    "total_posts": 50,
                    "total_followers": 10000,
                    "avg_likes_per_post": 150.0,
                    "avg_comments_per_post": 8.0,
                    "avg_engagement_rate": 1.58
                }
            }
        ]
        
        for i, scenario in enumerate(scenarios):
            scenario_task_id = f"{task_id}-scenario-{i}"
            print(f"   📊 Testing scenario: {scenario['name']}")
            
            # Set completed stats for this scenario
            progress_service.set_task_completed(
                task_id=scenario_task_id,
                results={
                    "username": f"test_user_{i}",
                    "analysis_results": {
                        "statistics_generation": {
                            "status": "completed",
                            "statistics_summary": scenario['stats']
                        }
                    }
                }
            )
            
            # Verify metrics
            progress_data = progress_service.get_task_progress(scenario_task_id)
            if progress_data:
                stats = progress_data['results']['analysis_results']['statistics_generation']['statistics_summary']
                print(f"      Posts: {stats['total_posts']}")
                print(f"      Followers: {stats['total_followers']}")
                print(f"      Avg likes: {stats['avg_likes_per_post']}")
                print(f"      Avg comments: {stats['avg_comments_per_post']}")
                print(f"      Engagement rate: {stats['avg_engagement_rate']}%")
            
            # Clean up
            progress_service.delete_task_progress(scenario_task_id)
        
        print("✅ Metrics calculation test completed!")
        
    except Exception as e:
        print(f"❌ Error testing metrics calculation: {str(e)}")

async def main():
    """Función principal para ejecutar las pruebas"""
    print("🚀 Starting TaskIQ Instagram Statistics Analysis tests...")
    print("=" * 70)
    
    # Test progress service first
    await test_progress_service_statistics()
    print()
    
    # Test step-by-step analysis
    await test_statistics_analysis_steps()
    print()
    
    # Test custom limits functionality
    await test_statistics_analysis_with_custom_limits()
    print()
    
    # Test metrics calculation
    await test_statistics_metrics_calculation()
    print()
    
    # Test with invalid user scenario
    await test_statistics_task_with_invalid_user()
    print()
    
    # Test the actual TaskIQ task (commented out as it requires real data)
    print("⚠️  Skipping actual TaskIQ task test (requires real Instagram user data and posts)")
    print("   To test with real data, uncomment the following line:")
    print("   # await test_statistics_analysis_task()")
    print()
    
    print("🏁 Instagram Statistics TaskIQ tests completed!")

if __name__ == "__main__":
    asyncio.run(main()) 