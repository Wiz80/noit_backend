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

A FastAPI backend application for Infinity Lab.

## Docker Setup

This project is containerized with Docker and uses Docker Compose for orchestration.

### Prerequisites

- Docker and Docker Compose installed on your system
- Git (for cloning the repository)

### Configuration

1. Clone the repository:
   ```bash
   git clone <repository_url>
   cd noit_backend
   ```

2. Set up environment variables (optional):
   The docker-compose.yaml file includes default environment variables. For production, you should customize these in an `.env` file.

### Build and Run

To build and run the application:

```bash
docker-compose up --build
```

This will:
- Build the FastAPI application container
- Start PostgreSQL, Redis, and MinIO services
- Start the Nginx proxy server

To run in detached mode:

```bash
docker-compose up -d
```

### Services

The application includes the following services:

- **FastAPI App**: The main backend application (http://localhost:8000)
- **Nginx**: Proxy server that forwards requests from port 80 to the FastAPI app
- **PostgreSQL**: Database running on port 5435
- **Redis**: In-memory cache on port 6379
- **MinIO**: Object storage compatible with S3 API (http://localhost:9003)
- **Mage**: Data pipeline tool (http://localhost:6789)

### Testing the API

1. Using the browser:
   - Open http://localhost:80 to access the API through Nginx
   - Open http://localhost:8000 to access the API directly

2. Using the test HTML page:
   - Open `tests/api_test.html` in your browser
   - Select the endpoint, method, and port
   - Click "Send Request" to test the API

## Development

### Directory Structure

```
noit_backend/
├── app/                    # Main application code
│   ├── api/                # API endpoints
│   ├── core/               # Core application modules
│   ├── crud/               # CRUD operations
│   ├── db/                 # Database models and connections
│   ├── models/             # Pydantic models
│   ├── schemas/            # Schema definitions
│   ├── services/           # Business logic services
│   └── main.py             # FastAPI application entry point
├── nginx/                  # Nginx configuration
│   └── nginx.conf
├── tests/                  # Tests
├── Dockerfile              # Docker configuration for FastAPI app
└── docker-compose.yaml     # Docker Compose configuration
```

### Customization

The Nginx configuration (`nginx/nginx.conf`) can be modified to adjust the proxy settings as needed. 

The FastAPI application is configured with CORS to allow all origins (`"*"`) for development purposes. For production, you should restrict this to specific domains.

## Troubleshooting

### CORS Issues

If you encounter CORS issues when testing from a web browser:
1. Check that the FastAPI CORS middleware is configured correctly in `app/main.py`
2. Verify that Nginx is properly forwarding CORS headers in `nginx/nginx.conf`
3. Ensure your test page is making requests to the correct port (80 for Nginx or 8000 for direct access)

### Container Connectivity

If containers cannot communicate with each other:
1. Check Docker networks: `docker network ls`
2. Inspect the container network: `docker network inspect noit_backend_default` 

## Configuración con Poetry

Este proyecto utiliza Poetry para la gestión de dependencias y entornos virtuales.

### Requisitos previos

- Python 3.12
- Poetry

### Instalación de Poetry

```bash
# En macOS/Linux/WSL:
curl -sSL https://install.python-poetry.org | python3 -

# En Windows (PowerShell):
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -
```

### Configuración del proyecto

1. Clonar el repositorio:
```bash
git clone <url-del-repositorio>
cd noit-backend
```

2. Instalar dependencias con Poetry:
```bash
poetry install
```

3. Activar el entorno virtual:
```bash
poetry shell
```

4. Descargar modelo de lenguaje para español:
```bash
python -m spacy download es_core_news_sm
```

### Ejecutar la aplicación

```bash
poetry run uvicorn app.main:app --reload
```

### Ejecución con Docker

Construir la imagen:
```bash
docker build -t noit-backend .
```

Ejecutar el contenedor:
```bash
docker run -p 8000:8000 noit-backend
```

## Variables de entorno

Crear un archivo `.env` en la raíz del proyecto con las siguientes variables:

```
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
SECRET_KEY=your_secret_key
# Otras variables necesarias para tu aplicación
``` 