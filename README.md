# Noit

## Project Overview

Noit is an AI-powered platform designed to help entrepreneurs understand, structure, and execute their business ideas. The platform leverages AI agents to guide entrepreneurs through the process of developing their business ideas, creating strategies, and scaling their ventures.

## Problem Statement

Many entrepreneurs struggle with the practical aspects of executing a business idea, including:
- Structuring the business model
- Creating effective marketing strategies
- Building an audience
- Scaling the business
- Understanding market dynamics
- Validating business hypotheses
- Developing competitive strategies

Noit addresses these challenges by providing AI-driven guidance and tools that help entrepreneurs bring their ideas to life.

## Key Features

- **Business Idea Creation**: Define and structure your business idea with mission, vision, and description
- **Business Understanding**: Analyze and refine your business model with AI-powered insights
- **Business Canvas Generation**: Create a comprehensive business canvas based on specific objectives
- **Competitor Analysis**: Research and analyze competitors in your market
- **State of Art Analysis**: Understand the current market landscape and industry trends
- **Social Media Competitor Analysis**: Analyze competitors' Instagram profiles and content
- **Interactive Business Validation Chat**: Engage in a conversational process to validate your business idea through a structured methodology
- **Market Research**: Conduct in-depth market research using AI-powered tools
- **Strategy Development**: Create actionable business strategies based on validated insights
- **Progress Tracking**: Monitor and track the development of your business idea through different stages

## Architecture

Noit is built using FastAPI for the backend, with a modular architecture that separates concerns into:
- API endpoints
- Business logic services
- Data models
- Storage services (MinIO for object storage)
- Cache services (Redis for conversation management)
- Task queues (Celery for background processing)
- Event bus (Redis Pub/Sub for real-time updates)

## Installation

### Prerequisites

- Python 3.8+
- Docker and Docker Compose
- MinIO (for object storage)
- Redis (for chat cache)
- PostgreSQL

### Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/noit.git
cd noit
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration including:
# - Database credentials
# - MinIO credentials
# - Redis configuration
# - API keys for OpenAI and Perplexity
# - JWT secret key
# - Apify API key for Instagram scraping
```

5. Start the services using Docker Compose:
```bash
docker-compose up -d
```

6. Initialize the database:
```bash
python manage.py db_init
```

7. Start the application:
```bash
python manage.py runserver
```

## API Endpoints

### Authentication

#### Login
- **Endpoint**: `POST /api/v1/auth/login`
- **Description**: Authenticates a user and returns a JWT token

### Business Idea

#### Create Business Idea
- **Endpoint**: `POST /api/v1/business-idea/`
- **Description**: Creates a new business idea in the database
- **Required Fields**: title, mission, vision, description

#### Get Business Ideas
- **Endpoint**: `GET /api/v1/business-idea/`
- **Description**: Retrieves all business ideas for the current user

#### Get Business Idea
- **Endpoint**: `GET /api/v1/business-idea/{business_idea_id}`
- **Description**: Retrieves a specific business idea by ID

#### Get Business Idea Folders
- **Endpoint**: `GET /api/v1/business-idea/{business_idea_id}/folders`
- **Description**: Lists all folders associated with a business idea

### Business Understanding

#### Business Model Analysis
- **Endpoint**: `POST /api/v1/business-understanding/business-model/{business_id}`
- **Description**: Analyzes and validates a business idea, providing insights on:
  - Customer persona: The target customer for the business
  - Problem definition: The problem the business is trying to solve
  - Industry analysis: The industry context of the business
  - Value proposition: The unique value offered by the business
  - Competitive advantage: What makes this business model more profitable
  - Key resources: The resources needed for the business to be competitive
- **Parameters**:
  - `update` (optional): If true, forces a new validation

#### Business Canvas Generation
- **Endpoint**: `POST /api/v1/business-understanding/create-business-canvas/{business_id}`
- **Description**: Creates a business canvas based on specific objectives, including:
  - Customer segments: Who the business serves
  - Value propositions: What value the business delivers
  - Channels: How the business reaches customers
  - Customer relationships: How the business maintains customer relationships
  - Revenue streams: How the business generates revenue
  - Key resources: What assets are required
  - Key activities: What activities are necessary
  - Key partnerships: Who are the key partners
  - Cost structure: What are the main costs
  - Pricing strategy: How the business prices its offerings
- **Parameters**:
  - `update` (optional): If true, forces a new analysis

#### State of Art Analysis
- **Endpoint**: `POST /api/v1/business-understanding/business/{business_id}/state-of-art`
- **Description**: Generates state of art analysis for a business idea, including market research and current industry landscape
- **Parameters**:
  - `language` (optional): Language for the analysis (default: "es")
  - `test_mode` (optional): If true, only processes a limited number of questions for testing (default: false)
  - `test_questions_limit` (optional): Number of questions to process per category in test mode (default: 4)
- **Response**: Returns a JSON object with the analysis results and paths to the stored files in MinIO

### Competitor Analysis

#### Analyze Competitors
- **Endpoint**: `POST /api/v1/analyze-competitors/{business_id}`
- **Description**: Analyzes competitors based on the business model, extracting key questions and performing competitor research
- **Required Fields**: language, validator_provider, validator_model, search_prompt

#### Instagram Competitor Analysis
- **Endpoint**: `POST /api/v1/competitor-analysis/instagram/{business_id}`
- **Description**: Initiates Instagram competitor analysis for all competitors associated with a business idea
- **Response**: Returns a task ID for tracking progress

#### Get Instagram Analysis Progress
- **Endpoint**: `GET /api/v1/competitor-analysis/instagram/{business_id}/task/{task_id}`
- **Description**: Retrieves the progress of an Instagram competitor analysis task
- **Response**: Returns progress percentage, status, and results

### Business Chat

#### Start or Continue Chat Session
- **Endpoint**: `POST /api/v1/business-idea/{business_idea_id}/chat/start`
- **Description**: Starts a new chat session or continues an existing one for business idea validation
- **Parameters**:
  - `llm_provider` (optional): LLM provider to use (default: "openai")
  - `llm_model` (optional): LLM model to use (default: "gpt-4o")
  - `language` (optional): Language for the conversation (default: "es")
- **Response**: Returns session information with greeting and first question

#### Send Chat Message
- **Endpoint**: `POST /api/v1/business-idea/{business_idea_id}/chat/{session_id}/message`
- **Description**: Sends a message to the chat and receives an AI-generated response
- **Required Body**: `{"message": "Your message here"}`
- **Parameters**:
  - `llm_provider` (optional): LLM provider to use (default: "openai")
  - `llm_model` (optional): LLM model to use (default: "gpt-4o")
  - `language` (optional): Language for the conversation (default: "es")
- **Response**: Returns AI response, next question if applicable, and current status

#### Generate Chat Summary
- **Endpoint**: `POST /api/v1/business-idea/{business_idea_id}/chat/{session_id}/summary`
- **Description**: Generates a comprehensive summary of the business validation chat session
- **Parameters**:
  - `llm_provider` (optional): LLM provider to use (default: "openai")
  - `llm_model` (optional): LLM model to use (default: "gpt-4o")
  - `language` (optional): Language for the summary (default: "es")
- **Response**: Returns a structured summary of the business validation process

## Data Flow

1. User creates a business idea with title, mission, vision, and description
2. The system analyzes the business idea to understand its structure and market context
3. A business canvas is generated based on specific objectives
4. Competitor analysis is performed to understand the market landscape
5. Instagram competitor analysis extracts data from competitors' social media profiles
6. Results are stored in MinIO for future reference and retrieval
7. For interactive validation, users engage in a structured chat conversation with AI
8. Chat history is cached in Redis to maintain conversation context
9. The AI guides users through a 3-stage validation process:
   - Business Understanding
   - Communication Needs
   - Communication Strategy

## Business Validation Chat Flow

The Business Validation Chat provides a structured, conversational approach to validating business ideas through three stages:

### Stage 1: Business Understanding
- Purpose and mission of the business
- Value proposition
- Products/services and target audience
- Ideal customer profile
- Problem being solved
- Competitive differentiators
- Key challenges and opportunities

### Stage 2: Communication Needs
- Market context necessitating communication
- Concrete business opportunity
- Communication objectives (positioning, launch, awareness, conversion)

### Stage 3: Communication Strategy
- Core message
- Target audience and their characteristics
- Credibility factors and tone
- Success metrics and expected results
- Desired audience response
- Constraints and considerations

## Technologies Used

- **Backend Framework**: FastAPI
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Object Storage**: MinIO
- **Cache System**: Redis
- **AI Integration**: OpenAI, Claude, DeepSeek, n8n workflow for web research
- **Authentication**: JWT with Python-Jose
- **Containerization**: Docker and Docker Compose
- **CLI Management**: Click
- **Database Migrations**: Alembic
- **Social Media Scraping**: Apify API

## Development

### Project Structure

```
noit/
├── app/
│   ├── api/              # API endpoints
│   │   └── v1/
│   │       ├── endpoints/  # API endpoint implementations
│   │       └── api.py      # API router
│   ├── controllers/      # Business logic controllers
│   ├── core/             # Core configuration
│   │   ├── config.py     # Application settings
│   │   └── security.py   # Authentication and security
│   ├── crud/             # Database CRUD operations
│   ├── db/               # Database configuration
│   ├── models/           # Database models
│   ├── schemas/          # Pydantic schemas
│   ├── services/         # Business logic services
│   │   ├── business/     # Business-related services
│   │   ├── cache/        # Cache services (Redis)
│   │   ├── storage/      # Storage services (MinIO)
│   │   ├── queue/        # Task queue services (Celery)
│   │   └── events/       # Event handling services
│   └── utils/            # Utility functions
├── alembic/              # Database migrations
├── config/               # Configuration files
├── tests/                # Test cases
│   ├── unit/            # Unit tests
│   ├── integration/     # Integration tests
│   └── e2e/            # End-to-end tests
├── scripts/             # Utility scripts
├── manage.py            # Management script
├── docker-compose.yaml  # Docker Compose configuration
└── requirements.txt     # Python dependencies
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test categories
pytest tests/unit
pytest tests/integration
pytest tests/e2e

# Run tests with coverage report
pytest --cov=app tests/

# Run tests in parallel
pytest -n auto
```

### Development Guidelines

1. **Code Style**
   - Follow PEP 8 guidelines
   - Use type hints
   - Write comprehensive docstrings
   - Keep functions focused and small

2. **Testing**
   - Write unit tests for all new features
   - Maintain test coverage above 80%
   - Include integration tests for API endpoints
   - Add end-to-end tests for critical flows

3. **Documentation**
   - Update README.md for new features
   - Document all API endpoints
   - Include example requests and responses
   - Keep architecture diagrams up to date

4. **Version Control**
   - Use feature branches
   - Write meaningful commit messages
   - Follow conventional commits format
   - Review code before merging

5. **Performance**
   - Profile code for bottlenecks
   - Optimize database queries
   - Use caching appropriately
   - Monitor resource usage

## Environment Variables

The application requires the following environment variables:

```
# JWT
SECRET_KEY=your-secret-key
ALGORITHM=HS256

# Database
POSTGRES_SERVER=localhost
POSTGRES_USER=postgres
POSTGRES_PORT=5432
POSTGRES_PASSWORD=password
POSTGRES_DB=noit

# MinIO
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin
MINIO_ENDPOINT=localhost:9000
MINIO_REGION=us-east-1

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0

# API Keys
OPENAI_API_KEY=your-openai-api-key
PERPLEXITY_API_KEY=your-perplexity-api-key
APIFY_API_KEY=your-apify-api-key
DEEPSEEK_API_KEY=your-deepseek-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key

# Celery
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# Application
DEBUG=True
ENVIRONMENT=development
LOG_LEVEL=INFO
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

We welcome contributions! Please follow these steps:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Write or update tests
5. Update documentation
6. Submit a pull request

For major changes, please open an issue first to discuss what you would like to change.

# Noit Backend

Backend services for the Noit platform.

## LinkedIn Ads Scraper

The LinkedIn Ads Scraper is a custom solution for extracting ad data from the LinkedIn Ad Library. It uses ScrapeGraphAI with the SmartScraperGraph component to intelligently extract ad information.

### Features

- Extract ad data from LinkedIn Ad Library using AI-powered scraping
- Support for various search filters (company, date range, countries, etc.)
- Automatic detection of CSS selectors to handle LinkedIn page structure changes
- Robust error handling with automatic retries
- Detection of login walls and other potential issues
- Two-tiered approach: direct Playwright extraction with SmartScraperGraph fallback
- Extracts comprehensive ad information including:
  - Ad ID
  - Advertiser logo
  - Ad text
  - Call-to-action (CTAs)
  - Advertiser name and URL
  - Ad format
  - Paid by information
  - Media URLs (images/videos)
  - Source URL

### Usage

To use the LinkedIn Ads Scraper in your application:

```python
from app.services.business.competitive_analysis.linkedin.linkedin_ads_service import LinkedInAdsService

# Initialize the service
ads_service = LinkedInAdsService(
    llm_provider="openai",
    llm_model="gpt-3.5-turbo"
)

# Extract ads for competitors
result = await ads_service.extract_competitor_ads_data(
    business_idea_id="your-business-idea-id",
    db=db_session,
    date_option="last-30-days",
    max_results_per_competitor=50,
    detect_selectors=True  # Enable automatic CSS selector detection
)
```

For direct ad extraction without database integration:

```python
from app.services.scrape.linkedin_ads_scraper import extract_ads_from_linkedin

# Create search URL for a specific company
search_url = "https://www.linkedin.com/ad-library/search?accountOwner=Microsoft&dateOption=last-30-days"

# Extract ads data with automatic selector detection
ads_data = await extract_ads_from_linkedin(
    search_url=search_url,
    max_results=50,
    detect_selectors=True
)

# Check for warnings or issues
if "warnings" in ads_data:
    for warning in ads_data["warnings"]:
        print(f"Warning: {warning}")
```

### Advanced Usage

For more control over the scraping process, you can use the `LinkedInAdsScraper` class directly:

```python
from app.services.scrape.linkedin_ads_scraper import LinkedInAdsScraper

# Create a scraper with custom settings
scraper = LinkedInAdsScraper(
    llm_provider="openai",
    llm_model="gpt-3.5-turbo",
    headless=True,
    verbose=True,
    max_retries=3,
    retry_delay=5,
    custom_selectors={
        "ad_container": ".custom-ad-selector"  # Override default selectors
    }
)

# Detect optimal selectors for current LinkedIn structure
updated_selectors = await scraper.detect_optimal_selectors(search_url)
scraper.selectors = updated_selectors

# Extract ads
ads_data = await scraper.extract_ads_data(search_url, max_results=100)
```

### Testing

A test script is provided to verify the scraper's functionality:

```bash
python app/services/scrape/examples/test_linkedin_ads_scraper.py
```

This will detect optimal selectors, extract sample ads from a predefined company, and save the results to the `output` directory.

### Setup

To install the required dependencies:

```bash
python app/services/scrape/setup_scraper.py
```

This script will install the necessary packages and set up the environment.

## Requirements

- Python 3.8+
- OpenAI API key (set as environment variable `OPENAI_API_KEY`)
- Required packages:
  - scrapegraphai
  - playwright
  - aiohttp
  - python-dotenv
  - sqlalchemy
  - minio

## LinkedIn Ads Analysis

The application provides two services for analyzing LinkedIn ads:

### 1. LinkedInAdsService

Custom implementation that uses a scraper to extract ads data from LinkedIn's Ad Library.

### 2. ApifyLinkedInAdsService

Integration with Apify's LinkedIn Ad scraper actor (ID: 31BPULiLZ42ca1mvj) for more robust ad extraction.

#### Setup

1. Set your Apify API token in the environment:
   ```
   APIFY_API_TOKEN=your_apify_token
   ```

2. Usage example:
   ```python
   from app.services.business.competitive_analysis.linkedin.linkedin_ads_service import ApifyLinkedInAdsService
   
   # Initialize the service
   service = ApifyLinkedInAdsService()
   
   # Search for ads by URL
   search_url = service.build_search_url(
       account_owner="company_name",
       countries=["US"],
       date_option="last-30-days",
       keyword="product"
   )
   ads_data = await service.fetch_ads_data(search_url)
   
   # Or extract ads for all competitors of a business idea
   results = await service.extract_competitor_ads_data(
       business_idea_id="your_business_idea_id",
       db=db_session,
       date_option="last-30-days"
   )
   ```

#### Parameters

The service supports all parameters provided by the Apify actor, including:
- `type_search`: "search_url" or "company"
- `limit`: Maximum number of ads to retrieve
- `countries`: Filter by country codes
- `date_option`: Time range for ads (last-30-days, this-month, etc.)
- `keyword`: Keyword to search for in ads 