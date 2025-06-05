#!/bin/bash

# 🚀 Complete Pipelines Setup Script
# This script sets up both the social media extraction and Instagram analysis pipelines

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Configuration
KESTRA_URL="${KESTRA_URL:-http://localhost:8080}"
NAMESPACE="noit.backend"

# Pipeline configurations
SOCIAL_MEDIA_FLOW="social-media-extraction-trigger"
SOCIAL_MEDIA_FILE="pipelines/social-media-extraction-trigger.yml"

INSTAGRAM_FLOW="instagram-analysis-complete-trigger"
INSTAGRAM_FILE="pipelines/instagram-analysis-complete-trigger.yml"

echo -e "${BLUE}🚀 Setting up Complete Competitor Analysis Pipelines${NC}"
echo "===================================================="
echo -e "${PURPLE}This will install two integrated pipelines:${NC}"
echo -e "  1. 📱 Social Media Extraction Pipeline"
echo -e "  2. 📸 Instagram Analysis Complete Pipeline"
echo ""

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

# Function to upload a pipeline
upload_pipeline() {
    local flow_name="$1"
    local file_path="$2"
    local description="$3"
    
    echo -e "${YELLOW}📤 Uploading $description...${NC}"
    
    if [ ! -f "$file_path" ]; then
        echo -e "${RED}❌ Pipeline file not found: $file_path${NC}"
        return 1
    fi
    
    # Upload the flow using Kestra API
    local response=$(curl -s -w "%{http_code}" -X PUT "$KESTRA_URL/api/v1/flows/$NAMESPACE/$flow_name" \
        -H "Content-Type: application/yaml" \
        --data-binary "@$file_path")
    
    local http_code="${response: -3}"
    local body="${response%???}"
    
    if [ "$http_code" -eq 200 ] || [ "$http_code" -eq 201 ]; then
        echo -e "${GREEN}✅ $description uploaded successfully!${NC}"
        return 0
    else
        echo -e "${RED}❌ Failed to upload $description (HTTP $http_code)${NC}"
        echo -e "${RED}Response: $body${NC}"
        return 1
    fi
}

# Function to verify a pipeline
verify_pipeline() {
    local flow_name="$1"
    local description="$2"
    
    echo -e "${YELLOW}🔍 Verifying $description...${NC}"
    
    local response=$(curl -s "$KESTRA_URL/api/v1/flows/$NAMESPACE/$flow_name")
    
    if echo "$response" | grep -q "\"id\":\"$flow_name\""; then
        echo -e "${GREEN}✅ $description verified successfully!${NC}"
        return 0
    else
        echo -e "${RED}❌ $description verification failed${NC}"
        return 1
    fi
}

# Function to test pipeline triggers
test_triggers() {
    local flow_name="$1"
    local description="$2"
    
    echo -e "${YELLOW}🔍 Testing triggers for $description...${NC}"
    
    local response=$(curl -s "$KESTRA_URL/api/v1/flows/$NAMESPACE/$flow_name/triggers")
    
    if echo "$response" | grep -q "triggers"; then
        local trigger_count=$(echo "$response" | grep -o '"type"' | wc -l)
        echo -e "${GREEN}✅ $description has $trigger_count trigger(s) configured${NC}"
    else
        echo -e "${YELLOW}⚠️ Could not verify triggers for $description${NC}"
    fi
}

# Function to run integration test
run_integration_test() {
    echo -e "${YELLOW}🧪 Running integration test...${NC}"
    
    # Test social media pipeline webhook trigger with business_id
    echo -e "${BLUE}Testing Social Media Pipeline with business_id...${NC}"
    local social_response=$(curl -s -X POST "$KESTRA_URL/api/v1/executions/webhook/$NAMESPACE/$SOCIAL_MEDIA_FLOW/social_media_extraction_by_business" \
        -H "Content-Type: application/json" \
        -d '{
            "business_id": "test-business-id-12345",
            "process_all_competitors": false,
            "max_concurrent_extractions": 1
        }')
    
    if echo "$social_response" | grep -q '"id"'; then
        local execution_id=$(echo "$social_response" | grep -o '"id":"[^"]*"' | cut -d'"' -f4)
        echo -e "${GREEN}✅ Social Media Pipeline test execution started: $execution_id${NC}"
        echo -e "   Monitor at: $KESTRA_URL/ui/executions/$execution_id"
        echo -e "${YELLOW}   Note: This may fail if test-business-id doesn't exist - that's expected${NC}"
    else
        echo -e "${YELLOW}⚠️ Social Media Pipeline test did not start${NC}"
        echo -e "   Response: $social_response"
        echo -e "${YELLOW}   This is expected if test business_id doesn't exist${NC}"
    fi
    
    # Test Instagram analysis pipeline manual trigger
    echo -e "${BLUE}Testing Instagram Analysis Pipeline manual trigger...${NC}"
    local instagram_response=$(curl -s -X POST "$KESTRA_URL/api/v1/executions/webhook/$NAMESPACE/$INSTAGRAM_FLOW/instagram_analysis_manual" \
        -H "Content-Type: application/json" \
        -d '{"action": "trigger_instagram_analysis"}')
    
    if echo "$instagram_response" | grep -q '"id"'; then
        local execution_id=$(echo "$instagram_response" | grep -o '"id":"[^"]*"' | cut -d'"' -f4)
        echo -e "${GREEN}✅ Instagram Analysis Pipeline test execution started: $execution_id${NC}"
        echo -e "   Monitor at: $KESTRA_URL/ui/executions/$execution_id"
    else
        echo -e "${YELLOW}⚠️ Instagram Analysis Pipeline test did not start (might be normal if no data)${NC}"
    fi
}

# Function to show pipeline information
show_pipeline_info() {
    echo -e "${GREEN}🎉 Complete Pipeline Setup Successful!${NC}"
    echo ""
    echo -e "${BLUE}📊 Pipeline Information:${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo -e "${PURPLE}1. 📱 Social Media Extraction Pipeline${NC}"
    echo -e "   Name: $SOCIAL_MEDIA_FLOW"
    echo -e "   URL: $KESTRA_URL/ui/flows/$NAMESPACE/$SOCIAL_MEDIA_FLOW"
    echo -e "   Trigger: Webhook with business_id parameter"
    echo -e "   Function: Extracts social media URLs from competitor websites for a specific business"
    echo ""
    echo -e "${PURPLE}2. 📸 Instagram Analysis Complete Pipeline${NC}"
    echo -e "   Name: $INSTAGRAM_FLOW"
    echo -e "   URL: $KESTRA_URL/ui/flows/$NAMESPACE/$INSTAGRAM_FLOW"
    echo -e "   Schedule: Every 2 hours + triggered by Pipeline 1"
    echo -e "   Function: Complete Instagram analysis (scraping + comments + images + stats)"
    echo ""
    echo -e "${BLUE}🔄 Integration Flow:${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Webhook with business_id → Pipeline 1 → Processes all competitors for that business"
    echo "          ↓"
    echo "  Pipeline 1 completes → Auto-triggers Pipeline 2 for same business"
    echo "          ↓"
    echo "  Pipeline 2 runs → Finds Instagram URLs for that business → Complete analysis"
    echo ""
}

# Function to show usage examples
show_usage_examples() {
    echo -e "${BLUE}🎯 Usage Examples:${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo -e "${YELLOW}▶️  Extract Social Media for Specific Business (Primary Use Case):${NC}"
    echo "curl -X POST $KESTRA_URL/api/v1/executions/webhook/$NAMESPACE/$SOCIAL_MEDIA_FLOW/social_media_extraction_by_business \\"
    echo "  -H \"Content-Type: application/json\" \\"
    echo "  -d '{"
    echo "    \"business_id\": \"12345678-1234-1234-1234-123456789012\","
    echo "    \"process_all_competitors\": true,"
    echo "    \"max_concurrent_extractions\": 3"
    echo "  }'"
    echo ""
    echo -e "${YELLOW}▶️  Process Only Competitors Needing Extraction:${NC}"
    echo "curl -X POST $KESTRA_URL/api/v1/executions/webhook/$NAMESPACE/$SOCIAL_MEDIA_FLOW/social_media_extraction_by_business \\"
    echo "  -H \"Content-Type: application/json\" \\"
    echo "  -d '{"
    echo "    \"business_id\": \"12345678-1234-1234-1234-123456789012\","
    echo "    \"process_all_competitors\": false"
    echo "  }'"
    echo ""
    echo -e "${YELLOW}▶️  Process Specific Competitors:${NC}"
    echo "curl -X POST $KESTRA_URL/api/v1/executions/webhook/$NAMESPACE/$SOCIAL_MEDIA_FLOW/social_media_extraction_by_business \\"
    echo "  -H \"Content-Type: application/json\" \\"
    echo "  -d '{"
    echo "    \"business_id\": \"12345678-1234-1234-1234-123456789012\","
    echo "    \"competitor_ids\": [\"comp-uuid-1\", \"comp-uuid-2\"]"
    echo "  }'"
    echo ""
    echo -e "${YELLOW}▶️  Direct Execution (No Webhook):${NC}"
    echo "curl -X POST $KESTRA_URL/api/v1/executions/$NAMESPACE/$SOCIAL_MEDIA_FLOW \\"
    echo "  -H \"Content-Type: application/json\" \\"
    echo "  -d '{"
    echo "    \"inputs\": {"
    echo "      \"business_id\": \"12345678-1234-1234-1234-123456789012\","
    echo "      \"process_all_competitors\": true,"
    echo "      \"max_concurrent_extractions\": 3"
    echo "    }"
    echo "  }'"
    echo ""
    echo -e "${YELLOW}▶️  Manual Instagram Analysis:${NC}"
    echo "curl -X POST $KESTRA_URL/api/v1/executions/webhook/$NAMESPACE/$INSTAGRAM_FLOW/instagram_analysis_manual \\"
    echo "  -H \"Content-Type: application/json\" \\"
    echo "  -d '{\"action\": \"trigger_instagram_analysis\"}'"
    echo ""
    echo -e "${YELLOW}▶️  Instagram Analysis for Specific Business:${NC}"
    echo "curl -X POST $KESTRA_URL/api/v1/executions/$NAMESPACE/$INSTAGRAM_FLOW \\"
    echo "  -H \"Content-Type: application/json\" \\"
    echo "  -d '{"
    echo "    \"inputs\": {"
    echo "      \"business_id\": \"12345678-1234-1234-1234-123456789012\","
    echo "      \"triggered_by\": \"manual_test\","
    echo "      \"max_concurrent_analysis\": 1,"
    echo "      \"wait_timeout_minutes\": 30"
    echo "    }"
    echo "  }'"
    echo ""
}

# Function to show monitoring information
show_monitoring_info() {
    echo -e "${BLUE}📈 Monitoring & Dashboard:${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "  🌐 Kestra Dashboard: $KESTRA_URL"
    echo -e "  📊 Flows Overview: $KESTRA_URL/ui/flows"
    echo -e "  📋 Executions: $KESTRA_URL/ui/executions"
    echo -e "  🔧 TaskIQ Admin: http://localhost:3000/tasks"
    echo ""
    echo -e "${BLUE}📚 Documentation:${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "  📖 Social Media Pipeline: pipelines/README_SOCIAL_MEDIA_PIPELINE.md"
    echo -e "  📖 Instagram Analysis Pipeline: pipelines/README_INSTAGRAM_ANALYSIS_PIPELINE.md"
    echo -e "  📖 General Pipelines: pipelines/README.md"
    echo ""
    echo -e "${BLUE}🎯 Key Changes in This Version:${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "  ✅ Social Media Pipeline now requires business_id parameter"
    echo -e "  ✅ No more automatic scheduling - fully webhook-driven"
    echo -e "  ✅ Business validation before processing competitors"
    echo -e "  ✅ Optional competitor_ids for selective processing"
    echo -e "  ✅ Configurable process_all_competitors flag"
    echo -e "  ✅ Improved error handling and logging"
    echo -e "  ✅ Auto-integration with Instagram Analysis Pipeline"
    echo ""
}

# Main execution
main() {
    echo -e "${BLUE}Configuration:${NC}"
    echo -e "   Kestra URL: $KESTRA_URL"
    echo -e "   Namespace: $NAMESPACE"
    echo -e "   Social Media Flow: $SOCIAL_MEDIA_FLOW"
    echo -e "   Instagram Flow: $INSTAGRAM_FLOW"
    echo ""
    
    # Check dependencies
    if ! command_exists curl; then
        echo -e "${RED}❌ curl is required but not installed${NC}"
        exit 1
    fi
    
    # Wait for Kestra to be ready
    wait_for_kestra
    
    # Upload pipelines
    echo -e "${BLUE}📦 Uploading Pipelines...${NC}"
    
    upload_pipeline "$SOCIAL_MEDIA_FLOW" "$SOCIAL_MEDIA_FILE" "Social Media Extraction Pipeline"
    upload_pipeline "$INSTAGRAM_FLOW" "$INSTAGRAM_FILE" "Instagram Analysis Complete Pipeline"
    
    # Verify deployments
    echo -e "${BLUE}🔍 Verifying Deployments...${NC}"
    
    verify_pipeline "$SOCIAL_MEDIA_FLOW" "Social Media Extraction Pipeline"
    verify_pipeline "$INSTAGRAM_FLOW" "Instagram Analysis Complete Pipeline"
    
    # Test triggers
    echo -e "${BLUE}🎯 Testing Triggers...${NC}"
    
    test_triggers "$SOCIAL_MEDIA_FLOW" "Social Media Extraction Pipeline"
    test_triggers "$INSTAGRAM_FLOW" "Instagram Analysis Complete Pipeline"
    
    # Run integration test
    echo -e "${BLUE}🧪 Integration Testing...${NC}"
    run_integration_test
    
    # Show information
    show_pipeline_info
    show_usage_examples
    show_monitoring_info
    
    echo -e "${GREEN}🎉 Setup completed successfully!${NC}"
    echo -e "${YELLOW}👀 Check the Kestra dashboard at $KESTRA_URL to monitor executions${NC}"
}

# Handle command line arguments
case "${1:-}" in
    "help"|"-h"|"--help")
        echo "Complete Competitor Analysis Pipelines Setup Script"
        echo ""
        echo "Usage: $0 [options]"
        echo ""
        echo "Options:"
        echo "  help, -h, --help    Show this help message"
        echo "  verify              Only verify existing pipelines"
        echo "  test                Only run integration tests"
        echo "  info                Only show pipeline information"
        echo ""
        echo "Environment Variables:"
        echo "  KESTRA_URL          Kestra server URL (default: http://localhost:8080)"
        echo ""
        echo "This script installs two integrated pipelines:"
        echo "  1. Social Media Extraction Pipeline"
        echo "  2. Instagram Analysis Complete Pipeline"
        echo ""
        exit 0
        ;;
    "verify")
        wait_for_kestra
        verify_pipeline "$SOCIAL_MEDIA_FLOW" "Social Media Extraction Pipeline"
        verify_pipeline "$INSTAGRAM_FLOW" "Instagram Analysis Complete Pipeline"
        exit 0
        ;;
    "test")
        wait_for_kestra
        run_integration_test
        exit 0
        ;;
    "info")
        show_pipeline_info
        show_usage_examples
        show_monitoring_info
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