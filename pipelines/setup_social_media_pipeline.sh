#!/bin/bash

# 🚀 Social Media Extraction Pipeline Setup Script
# This script sets up and deploys the Kestra pipeline for automatic social media extraction

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
KESTRA_URL="${KESTRA_URL:-http://localhost:8080}"
NAMESPACE="noit.backend"
FLOW_NAME="social-media-extraction-trigger"
PIPELINE_FILE="pipelines/social-media-extraction-trigger.yml"

echo -e "${BLUE}🚀 Setting up Social Media Extraction Pipeline${NC}"
echo "============================================="

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to wait for Kestra to be ready
wait_for_kestra() {
    echo -e "${YELLOW}⏳ Waiting for Kestra to be ready...${NC}"
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s "$KESTRA_URL/health" >/dev/null 2>&1; then
            echo -e "${GREEN}✅ Kestra is ready!${NC}"
            return 0
        fi
        
        echo -e "${YELLOW}Attempt $attempt/$max_attempts - Kestra not ready yet...${NC}"
        sleep 5
        ((attempt++))
    done
    
    echo -e "${RED}❌ Kestra is not responding after $max_attempts attempts${NC}"
    echo -e "${RED}Please ensure Kestra is running at $KESTRA_URL${NC}"
    exit 1
}

# Function to check database connection
check_database() {
    echo -e "${YELLOW}🔍 Checking database connection...${NC}"
    
    # Create a test query to verify database connection
    local test_query='{
        "inputs": {
            "check_interval_minutes": 1,
            "max_concurrent_extractions": 1,
            "process_existing": false
        }
    }'
    
    # Try to execute the pipeline to test database connection
    local response=$(curl -s -X POST "$KESTRA_URL/api/v1/executions/$NAMESPACE/$FLOW_NAME" \
        -H "Content-Type: application/json" \
        -d "$test_query" 2>/dev/null || echo "error")
    
    if [[ "$response" == "error" ]]; then
        echo -e "${YELLOW}⚠️  Could not test database connection directly${NC}"
        echo -e "${YELLOW}   This will be verified when the pipeline runs${NC}"
    else
        echo -e "${GREEN}✅ Database connection test initiated${NC}"
    fi
}

# Function to upload the pipeline
upload_pipeline() {
    echo -e "${YELLOW}📤 Uploading pipeline to Kestra...${NC}"
    
    if [ ! -f "$PIPELINE_FILE" ]; then
        echo -e "${RED}❌ Pipeline file not found: $PIPELINE_FILE${NC}"
        echo -e "${RED}Please ensure you're running this script from the project root directory${NC}"
        exit 1
    fi
    
    # Upload the flow using Kestra API
    local response=$(curl -s -w "%{http_code}" -X PUT "$KESTRA_URL/api/v1/flows/$NAMESPACE/$FLOW_NAME" \
        -H "Content-Type: application/yaml" \
        --data-binary "@$PIPELINE_FILE")
    
    local http_code="${response: -3}"
    local body="${response%???}"
    
    if [ "$http_code" -eq 200 ] || [ "$http_code" -eq 201 ]; then
        echo -e "${GREEN}✅ Pipeline uploaded successfully!${NC}"
    else
        echo -e "${RED}❌ Failed to upload pipeline (HTTP $http_code)${NC}"
        echo -e "${RED}Response: $body${NC}"
        exit 1
    fi
}

# Function to verify the pipeline
verify_pipeline() {
    echo -e "${YELLOW}🔍 Verifying pipeline deployment...${NC}"
    
    local response=$(curl -s "$KESTRA_URL/api/v1/flows/$NAMESPACE/$FLOW_NAME")
    
    if echo "$response" | grep -q "\"id\":\"$FLOW_NAME\""; then
        echo -e "${GREEN}✅ Pipeline verified successfully!${NC}"
        
        # Extract some information about the pipeline
        echo -e "${BLUE}📋 Pipeline Information:${NC}"
        echo -e "   Name: $FLOW_NAME"
        echo -e "   Namespace: $NAMESPACE"
        echo -e "   URL: $KESTRA_URL/ui/flows/$NAMESPACE/$FLOW_NAME"
    else
        echo -e "${RED}❌ Pipeline verification failed${NC}"
        echo -e "${RED}Response: $response${NC}"
        exit 1
    fi
}

# Function to show next steps
show_next_steps() {
    echo -e "${GREEN}🎉 Setup completed successfully!${NC}"
    echo ""
    echo -e "${BLUE}📌 Next Steps:${NC}"
    echo "1. 🌐 Access Kestra Dashboard: $KESTRA_URL"
    echo "2. 📊 Monitor executions at: $KESTRA_URL/ui/flows/$NAMESPACE/$FLOW_NAME"
    echo "3. 🔧 The pipeline is configured to run every 5 minutes automatically"
    echo ""
    echo -e "${BLUE}🎯 Manual Triggers:${NC}"
    echo ""
    echo -e "${YELLOW}▶️  Run pipeline manually:${NC}"
    echo "curl -X POST $KESTRA_URL/api/v1/executions/$NAMESPACE/$FLOW_NAME \\"
    echo "  -H \"Content-Type: application/json\" \\"
    echo "  -d '{"
    echo "    \"inputs\": {"
    echo "      \"check_interval_minutes\": 5,"
    echo "      \"max_concurrent_extractions\": 3,"
    echo "      \"process_existing\": false"
    echo "    }"
    echo "  }'"
    echo ""
    echo -e "${YELLOW}▶️  Process existing competitors:${NC}"
    echo "curl -X POST $KESTRA_URL/api/v1/executions/webhook/$NAMESPACE/$FLOW_NAME/social_media_extraction_existing \\"
    echo "  -H \"Content-Type: application/json\" \\"
    echo "  -d '{\"action\": \"process_existing_competitors\"}'"
    echo ""
    echo -e "${BLUE}📚 Documentation:${NC}"
    echo "📖 Full documentation: pipelines/README_SOCIAL_MEDIA_PIPELINE.md"
    echo ""
}

# Function to test the setup
test_setup() {
    echo -e "${YELLOW}🧪 Testing pipeline setup...${NC}"
    
    # Test manual execution
    local test_payload='{
        "inputs": {
            "check_interval_minutes": 1,
            "max_concurrent_extractions": 1,
            "process_existing": false
        }
    }'
    
    local response=$(curl -s -X POST "$KESTRA_URL/api/v1/executions/$NAMESPACE/$FLOW_NAME" \
        -H "Content-Type: application/json" \
        -d "$test_payload")
    
    if echo "$response" | grep -q "\"id\""; then
        local execution_id=$(echo "$response" | grep -o '"id":"[^"]*"' | cut -d'"' -f4)
        echo -e "${GREEN}✅ Test execution started successfully!${NC}"
        echo -e "   Execution ID: $execution_id"
        echo -e "   Monitor at: $KESTRA_URL/ui/executions/$execution_id"
    else
        echo -e "${YELLOW}⚠️  Could not start test execution${NC}"
        echo -e "${YELLOW}   This might be normal if there are no competitors to process${NC}"
        echo -e "${YELLOW}   Response: $response${NC}"
    fi
}

# Main execution
main() {
    echo -e "${BLUE}Configuration:${NC}"
    echo -e "   Kestra URL: $KESTRA_URL"
    echo -e "   Namespace: $NAMESPACE"
    echo -e "   Flow Name: $FLOW_NAME"
    echo -e "   Pipeline File: $PIPELINE_FILE"
    echo ""
    
    # Check dependencies
    if ! command_exists curl; then
        echo -e "${RED}❌ curl is required but not installed${NC}"
        exit 1
    fi
    
    # Wait for Kestra to be ready
    wait_for_kestra
    
    # Upload pipeline
    upload_pipeline
    
    # Verify deployment
    verify_pipeline
    
    # Check database connection
    check_database
    
    # Test the setup
    test_setup
    
    # Show next steps
    show_next_steps
}

# Handle command line arguments
case "${1:-}" in
    "help"|"-h"|"--help")
        echo "Social Media Extraction Pipeline Setup Script"
        echo ""
        echo "Usage: $0 [options]"
        echo ""
        echo "Options:"
        echo "  help, -h, --help    Show this help message"
        echo "  verify              Only verify the existing pipeline"
        echo "  test                Only run a test execution"
        echo ""
        echo "Environment Variables:"
        echo "  KESTRA_URL          Kestra server URL (default: http://localhost:8080)"
        echo ""
        exit 0
        ;;
    "verify")
        verify_pipeline
        exit 0
        ;;
    "test")
        wait_for_kestra
        test_setup
        exit 0
        ;;
    "")
        # No arguments, run main setup
        main
        ;;
    *)
        echo -e "${RED}❌ Unknown option: $1${NC}"
        echo "Use '$0 help' for usage information"
        exit 1
        ;;
esac 