#!/usr/bin/env python3
"""
Test script to verify LangChain migration is working correctly
"""

import asyncio
import os
from dotenv import load_dotenv

# Import our new LangChain factory
from app.services.llm import create_llm_client

load_dotenv()

async def test_llm_providers():
    """Test different LLM providers with LangChain"""
    
    test_prompt = "¿Cuál es la capital de España? Responde en una sola palabra."
    
    # Test Anthropic (Claude) - our new default
    print("🧪 Testing Anthropic Claude (default)...")
    try:
        claude_client = create_llm_client(
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            temperature=0.1
        )
        
        from langchain_core.messages import HumanMessage
        response = claude_client.invoke([HumanMessage(content=test_prompt)])
        print(f"✅ Claude response: {response.content}")
        
    except Exception as e:
        print(f"❌ Claude test failed: {str(e)}")
    
    # Test OpenAI (fallback)
    print("\n🧪 Testing OpenAI (fallback)...")
    try:
        openai_client = create_llm_client(
            provider="openai",
            model="gpt-4o-mini",
            temperature=0.1
        )
        
        response = openai_client.invoke([HumanMessage(content=test_prompt)])
        print(f"✅ OpenAI response: {response.content}")
        
    except Exception as e:
        print(f"❌ OpenAI test failed: {str(e)}")
    
    # Test DeepSeek (if available)
    print("\n🧪 Testing DeepSeek...")
    try:
        deepseek_client = create_llm_client(
            provider="deepseek",
            model="deepseek-chat",
            temperature=0.1
        )
        
        response = deepseek_client.invoke([HumanMessage(content=test_prompt)])
        print(f"✅ DeepSeek response: {response.content}")
        
    except Exception as e:
        print(f"❌ DeepSeek test failed: {str(e)}")

def test_environment_variables():
    """Check if required environment variables are set"""
    print("🔍 Checking environment variables...")
    
    required_vars = {
        "ANTHROPIC_API_KEY": "Claude",
        "OPENAI_API_KEY": "OpenAI", 
        "DEEPSEEK_API_KEY": "DeepSeek"
    }
    
    for var_name, provider in required_vars.items():
        if os.getenv(var_name):
            print(f"✅ {provider} API key found")
        else:
            print(f"⚠️ {provider} API key not found ({var_name})")

def main():
    """Main test function"""
    print("🚀 Starting LangChain migration test...\n")
    
    # Test environment
    test_environment_variables()
    print()
    
    # Test LLM providers
    asyncio.run(test_llm_providers())
    
    print("\n🎉 Migration test completed!")

if __name__ == "__main__":
    main() 