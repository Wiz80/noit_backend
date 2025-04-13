# Mage.ai Integration for Instagram Research

This directory contains the mage.ai pipelines for orchestrating asynchronous Instagram research workflows.

## Overview

The system flow:

1. FastAPI endpoint starts the Instagram competitor analysis process
2. For competitors without Instagram URLs, it triggers a web research request via n8n webhook
3. n8n processes the research request asynchronously
4. When n8n completes, it calls back to our API with the research results
5. The FastAPI endpoint triggers a mage.ai pipeline to process the research results
6. The mage.ai pipeline calls back to our API to continue the Instagram scraping process

## Pipeline Structure

### instagram_research_pipeline

This pipeline handles the processing of research results and triggers the Instagram scraping:

1. `load_research_data`: Loads the research data from the trigger payload
2. `validate_research_data`: Validates the research data and ensures all required fields are present
3. `process_instagram_research`: Processes the research data and calls the FastAPI callback endpoint

## Configuration

### Environment Variables

- `API_BASE_URL`: Base URL of the FastAPI application (default: http://localhost:8000)
- `MAGE_DATABASE_CONNECTION_URL`: Connection URL for the mage.ai database

## Triggering the Pipeline

The pipeline can be triggered through:

1. API call to mage.ai trigger endpoint
2. n8n workflow directly calling mage.ai
3. FastAPI endpoint calling mage.ai

## Development

To develop and test the pipeline:

1. Start the docker-compose environment: `docker-compose up -d`
2. Access the mage.ai UI at: http://localhost:6789
3. Configure the pipeline triggers and settings
4. Test the workflow end-to-end 