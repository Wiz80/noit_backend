#!/usr/bin/env python3
"""
Test script for Kestra webhook integration
Tests the business model completion webhook
"""

import requests
import json
from datetime import datetime

def test_kestra_webhook():
    """Test the Kestra webhook with sample data"""
    
    # Kestra webhook URL
    webhook_url = "http://localhost:8080/api/v1/executions/webhook/noit.backend/start-competitor-analysis/competitor_analysis_trigger"
    
    # Sample payload
    payload = {
        "event": "business_model_completed",
        "business_id": "test-business-123",
        "business_title": "Mi App de Delivery",
        "industry": "Tecnología - Delivery de comida",
        "triggered_by": "manual_test",
        "timestamp": datetime.now().isoformat(),
        "business_model_data": {
            "problem_definition": "Facilitar el acceso a comida rápida en zonas residenciales",
            "value_proposition": "Entrega rápida de comida en menos de 30 minutos",
            "products_services": "Plataforma de delivery con app móvil",
            "customer_persona": "Jóvenes profesionales de 25-40 años que viven en apartamentos",
            "competitive_advantage": "Algoritmo de optimización de rutas único",
            "challenges_opportunities": "Competencia con Uber Eats y Rappi",
            "industry": "Tecnología - Delivery de comida"
        }
    }
    
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Test-Script/1.0"
    }
    
    try:
        print("🔔 Testing Kestra webhook...")
        print(f"URL: {webhook_url}")
        print(f"Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        
        response = requests.post(
            webhook_url,
            json=payload,
            headers=headers,
            timeout=30
        )
        
        print(f"\n📋 Response Status: {response.status_code}")
        print(f"📋 Response Headers: {dict(response.headers)}")
        print(f"📋 Response Body: {response.text}")
        
        if response.status_code in [200, 201, 202]:
            print("✅ Webhook test successful!")
            
            # Try to parse response
            try:
                response_data = response.json()
                if "id" in response_data:
                    print(f"🆔 Execution ID: {response_data['id']}")
            except:
                pass
                
        else:
            print(f"❌ Webhook test failed with status {response.status_code}")
            
    except requests.exceptions.Timeout:
        print("❌ Webhook request timed out")
    except requests.exceptions.RequestException as e:
        print(f"❌ Request error: {str(e)}")
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")

def test_manual_trigger():
    """Test the manual trigger webhook without conditions"""
    
    webhook_url = "http://localhost:8080/api/v1/executions/webhook/noit.backend/start-competitor-analysis/competitor_analysis_trigger"
    
    payload = {
        "business_id": "test-business-456",
        "business_title": "Tienda Online de Ropa",
        "industry": "E-commerce",
        "triggered_by": "manual_webhook_test"
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        print("\n🔧 Testing manual trigger webhook...")
        print(f"URL: {webhook_url}")
        
        response = requests.post(
            webhook_url,
            json=payload,
            headers=headers,
            timeout=30
        )
        
        print(f"📋 Manual Trigger Response: {response.status_code}")
        print(f"📋 Response: {response.text}")
        
        if response.status_code in [200, 201, 202]:
            print("✅ Manual trigger test successful!")
        else:
            print(f"❌ Manual trigger test failed")
            
    except Exception as e:
        print(f"❌ Manual trigger error: {str(e)}")

if __name__ == "__main__":
    print("🧪 Testing Kestra Webhook Integration")
    print("="*50)
    
    # Test the main webhook with event condition
    test_kestra_webhook()
    
    # Test the manual trigger webhook
    test_manual_trigger()
    
    print("\n🎯 Test completed!") 