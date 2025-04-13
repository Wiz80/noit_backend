# Instagram Research Pipeline Implementation

## Architecture Overview

We've implemented an asynchronous workflow system for Instagram competitor research using Mage.ai as an orchestration tool. Here's the overall architecture:

1. **FastAPI Application**: Handles API requests, initiates research, and processes callbacks
2. **N8N Workflow**: Performs web research to find Instagram URLs for competitors
3. **Mage.ai Pipeline**: Orchestrates data processing after research is complete
4. **Database (PostgreSQL)**: Stores competitor data, scraping jobs, and analysis results

## Flow Diagram

```
┌─────────────┐         ┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│             │ research │             │ callback │             │ trigger  │             │
│   FastAPI   ├────────►│     N8N     ├────────►│   FastAPI   ├────────►│   Mage.ai   │
│             │         │             │         │             │         │             │
└─────────────┘         └─────────────┘         └─────────────┘         └─────────────┘
                                                      │                        │
                                                      │                        │
                                                      ▼                        ▼
                                               ┌─────────────┐         ┌─────────────┐
                                               │             │ callback │             │
                                               │   FastAPI   │◄────────┤   Mage.ai   │
                                               │             │         │             │
                                               └─────────────┘         └─────────────┘
                                                      │
                                                      │
                                                      ▼
                                               ┌─────────────┐
                                               │ Instagram   │
                                               │ Scraping    │
                                               │             │
                                               └─────────────┘
```

## Components

### 1. Docker Compose Setup

The `docker-compose.yaml` file sets up the required services:
- PostgreSQL database
- Redis for caching
- MinIO for object storage
- Mage.ai for pipeline orchestration

### 2. Mage.ai Pipeline

The Instagram research pipeline in Mage.ai has three main steps:
1. **load_research_data**: Loads the research data from the trigger payload
2. **validate_research_data**: Validates the data for required fields
3. **process_instagram_research**: Processes the research and calls back to the FastAPI endpoint

### 3. N8N Integration

The existing N8N workflow is updated to:
1. Receive a research request with callback information
2. Perform web research to find social media URLs
3. Call back to our API with the research results

### 4. FastAPI Controller

The CompetitorAnalysisController handles:
1. Processing research results
2. Updating competitor records with social media URLs
3. Executing Instagram scraping logic

### 5. FastAPI Endpoints

Modified endpoints:
1. `/api/v1/business/{business_id}/competitor-analysis`: Initiates the analysis process
2. `/api/v1/business/{business_id}/competitor-analysis/research-callback`: Handles N8N callbacks and triggers Mage.ai

## Configuration

Environment variables needed:
- `API_BASE_URL`: Base URL for FastAPI
- `MAGE_API_URL`: URL for Mage.ai API
- `N8N_WEBHOOK_URL`: URL for N8N webhook
- `USE_DIRECT_PROCESSING`: Flag to use direct processing or Mage.ai

## Fallback Mechanism

The system includes fallback options:
1. If Mage.ai is unavailable, it falls back to direct processing
2. If N8N fails, the research is marked as failed but the process can continue

## Development and Testing

1. Start the docker-compose environment: `docker-compose up -d`
2. Access the Mage.ai UI at: http://localhost:6789
3. Configure the pipeline triggers in Mage.ai
4. Test the workflow end-to-end

## Scaling Considerations

This architecture can scale by:
1. Increasing Mage.ai workers
2. Adding more N8N nodes for parallel processing
3. Separating services into different containers
4. Implementing proper queue systems for high-load scenarios 