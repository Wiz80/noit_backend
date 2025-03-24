# Lattice

## Project Overview

Lattice is an AI-powered platform designed to help entrepreneurs understand, structure, and execute their business ideas. The platform leverages AI agents to guide entrepreneurs through the process of developing their business ideas, creating strategies, and scaling their ventures.

## Problem Statement

Many entrepreneurs struggle with the practical aspects of executing a business idea, including:
- Structuring the business model
- Creating effective marketing strategies
- Building an audience
- Scaling the business

Lattice addresses these challenges by providing AI-driven guidance and tools that help entrepreneurs bring their ideas to life.

## Key Features

- **Business Idea Creation**: Define and structure your business idea with mission, vision, and description
- **Business Understanding**: Analyze and refine your business model with AI-powered insights
- **Business Canvas Generation**: Create a comprehensive business canvas based on specific objectives
- **Competitor Analysis**: Research and analyze competitors in your market
- **State of Art Analysis**: Understand the current market landscape (in development)
- **Social Media Competitor Analysis**: Analyze competitors' Instagram profiles and content
- **Interactive Business Validation Chat**: Engage in a conversational process to validate your business idea through a structured methodology

## Architecture

Lattice is built using FastAPI for the backend, with a modular architecture that separates concerns into:
- API endpoints
- Business logic services
- Data models
- Storage services (MinIO for object storage)
- Cache services (Redis for conversation management)

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
git clone https://github.com/yourusername/lattice.git
cd lattice
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
lattice/
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
│   │   └── storage/      # Storage services (MinIO)
│   └── utils/            # Utility functions
├── alembic/              # Database migrations
├── config/               # Configuration files
├── tests/                # Test cases
├── manage.py             # Management script
├── docker-compose.yaml   # Docker Compose configuration
└── requirements.txt      # Python dependencies
```

### Management Commands

The application includes a CLI management script (`manage.py`) with the following commands:

- `python manage.py runserver`: Run the FastAPI development server
- `python manage.py db_init`: Initialize the database
- `python manage.py db_migrate "message"`: Create a new database migration
- `python manage.py db_upgrade`: Upgrade database to the latest version
- `python manage.py db_downgrade`: Downgrade database to a specific revision

### Testing

#### Running Tests

```bash
pytest
```

#### Testing State of Art Analysis

The state-of-art analysis endpoint can be computationally intensive due to the number of questions it processes. For testing purposes, you can use the `test_mode` parameter to limit the number of questions processed:

```bash
# Run the test script with a specific business ID
python scripts/test_state_of_art.py <business_id>

# Specify test_mode and test_questions_limit
python scripts/test_state_of_art.py <business_id> true 2
```

This will process only the first 2 questions from each category, allowing you to verify that the process is working correctly without the full computational load.

### Instagram Scraper Tests

To test the Instagram comment scraping functionality, we've provided a dedicated script:

```bash
# Run the Instagram comments scraper test
./scripts/test_instagram_comments.py
```

This script:
- Searches for Instagram posts from a specific username ("bulldogskincare" by default)
- Provides an interactive interface to select posts and configure parameters
- Tests the `scrape_instagram_comments` method using real data from the database
- Displays detailed results of the scraping process

#### Requirements

To run this test script, you need:
- Properly configured `.env` file with a valid APIFY_API_KEY
- Database connection with Instagram user and post data
- A working internet connection

### Business Chat Test

To test the business chat functionality, you can use the following script:

```bash
# Test the business chat with a specific business idea ID
python scripts/test_business_chat.py <business_id>
```

This script:
- Initializes a chat session for the specified business idea
- Simulates a conversation with predefined responses
- Tests the progression through all stages of the validation process
- Generates and displays a summary of the validation

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
POSTGRES_DB=lattice

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
```

## License

This project is licensed under the terms of the license included in the LICENSE file.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. 