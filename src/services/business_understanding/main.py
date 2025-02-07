from src.services.business_understanding.business_validator import ValidatorConfig, BusinessValidator
from dotenv import load_dotenv
import os

load_dotenv()

def main():
    # Configuration with language selection
    config = ValidatorConfig(
        perplexity_api_key=os.getenv("PERPLEXITY_API_KEY"),
        validator_api_keys={"openai": os.getenv("OPENAI_API_KEY")},
        validator_provider="openai",
        validator_model="openai:gpt-4o",
        language="es"
    )
    
    # Run validation pipeline
    validator = BusinessValidator(config)
    validator.run()

if __name__ == "__main__":
    main()