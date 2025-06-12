import os
import logging
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# LangChain imports
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel

# Load environment variables
load_dotenv()
logger = logging.getLogger(__name__)

class LangChainLLMFactory:
    """
    Factory class for creating LangChain LLM instances
    """
    
    DEFAULT_MODELS = {
        "anthropic": "claude-3-5-sonnet-20241022",
        "openai": "gpt-4o",
        "deepseek": "deepseek-chat"
    }
    
    @staticmethod
    def create_llm(
        provider: str = "openai",
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> BaseChatModel:
        """
        Create a LangChain LLM instance
        
        Args:
            provider: LLM provider (anthropic, openai, deepseek)
            model: Model name (optional, uses default if not provided)
            temperature: Temperature for generation
            max_tokens: Maximum tokens for response
            **kwargs: Additional model-specific parameters
            
        Returns:
            LangChain chat model instance
        """
        
        # Use default model if not specified
        if not model:
            model = LangChainLLMFactory.DEFAULT_MODELS.get(provider, "claude-3-5-sonnet-20241022")
        
        logger.info(f"Creating LLM with provider: {provider}, model: {model}")
        
        if provider == "anthropic":
            return LangChainLLMFactory._create_anthropic_llm(model, temperature, max_tokens, **kwargs)
        elif provider == "openai":
            return LangChainLLMFactory._create_openai_llm(model, temperature, max_tokens, **kwargs)
        elif provider == "deepseek":
            return LangChainLLMFactory._create_deepseek_llm(model, temperature, max_tokens, **kwargs)
        else:
            raise ValueError(f"Unsupported provider: {provider}")
    
    @staticmethod
    def _create_anthropic_llm(
        model: str,
        temperature: float,
        max_tokens: Optional[int],
        **kwargs
    ) -> ChatAnthropic:
        """Create Anthropic Claude LLM"""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment variables")
        
        params = {
            "model": model,
            "temperature": temperature,
            "anthropic_api_key": api_key,
            **kwargs
        }
        
        if max_tokens:
            params["max_tokens"] = max_tokens
            
        return ChatAnthropic(**params)
    
    @staticmethod
    def _create_openai_llm(
        model: str = "gpt-4o-mini",
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> ChatOpenAI:
        """Create OpenAI LLM"""
        logger.info("Attempting to create OpenAI LLM client.")
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("OPENAI_API_KEY not found in environment variables.")
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        logger.debug(f"Found OPENAI_API_KEY with length: {len(api_key)}")

        params = {
            "model": model,
            "temperature": temperature,
            "openai_api_key": api_key,
            **kwargs
        }
        
        if max_tokens:
            params["max_tokens"] = max_tokens
        
        try:
            logger.info(f"Initializing ChatOpenAI with model: {model}")
            llm = ChatOpenAI(**params)
            logger.info("Successfully created OpenAI LLM client.")
            return llm
        except Exception as e:
            logger.error(f"Failed to create OpenAI LLM client: {str(e)}", exc_info=True)
            raise
    
    @staticmethod
    def _create_deepseek_llm(
        model: str,
        temperature: float,
        max_tokens: Optional[int],
        **kwargs
    ) -> ChatOpenAI:
        """Create DeepSeek LLM using OpenAI-compatible interface"""
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY not found in environment variables")
        
        params = {
            "model": model,
            "temperature": temperature,
            "openai_api_key": api_key,
            "base_url": "https://api.deepseek.com",
            **kwargs
        }
        
        if max_tokens:
            params["max_tokens"] = max_tokens
            
        return ChatOpenAI(**params)

def read_api_key_from_env_file(key_name: str) -> Optional[str]:
    """
    Helper function to read API key from .env file
    (Mantener compatibilidad con función existente)
    """
    return os.getenv(key_name)

# Helper function for backward compatibility
def create_llm_client(
    provider: str = "anthropic",
    model: Optional[str] = None,
    **kwargs
) -> BaseChatModel:
    """
    Convenience function to create LLM client
    """
    return LangChainLLMFactory.create_llm(provider=provider, model=model, **kwargs) 