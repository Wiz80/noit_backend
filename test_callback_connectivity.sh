#!/bin/bash

# Test Callback Connectivity Script
# This script tests if the callback URL is accessible from different contexts

echo "🔍 Testing Callback Connectivity..."
echo "=================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get the callback URL from environment or use default
# For web-research-system (host) to callback to backend (Docker): use localhost:8000
CALLBACK_BASE_URL=${CALLBACK_BASE_URL:-"http://localhost:8000"}
TEST_ENDPOINT="${CALLBACK_BASE_URL}/health"

echo -e "${YELLOW}Testing URL: ${TEST_ENDPOINT}${NC}"
echo ""

# Test 1: From host system (like web-research-system would)
echo "🌐 Test 1: From host system..."
if curl -s -f "${TEST_ENDPOINT}" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ SUCCESS: Can reach backend from host system${NC}"
else
    echo -e "${RED}❌ FAILED: Cannot reach backend from host system${NC}"
    echo "   This means web-research-system won't be able to send callbacks"
fi

echo ""

# Test 2: From within Docker network (if running inside container)
echo "🐳 Test 2: From Docker network..."
DOCKER_INTERNAL_URL="http://localhost:8000/health"
if curl -s -f "${DOCKER_INTERNAL_URL}" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ SUCCESS: Can reach backend from Docker network${NC}"
else
    echo -e "${YELLOW}⚠️  INFO: Cannot reach localhost:8000 (expected if running from host)${NC}"
fi

echo ""

# Show current configuration
echo "📋 Current Configuration:"
echo "   CALLBACK_BASE_URL: ${CALLBACK_BASE_URL}"
echo "   WEB_RESEARCH_BASE_URL: ${WEB_RESEARCH_BASE_URL:-"http://localhost:8001"}"

echo ""

# Check if environment file exists
if [ -f ".env" ]; then
    echo "📄 Environment file found (.env)"
    if grep -q "CALLBACK_BASE_URL" .env; then
        echo -e "${GREEN}✅ CALLBACK_BASE_URL is configured in .env${NC}"
    else
        echo -e "${YELLOW}⚠️  CALLBACK_BASE_URL not found in .env${NC}"
        echo "   Add this line to your .env file:"
        echo "   CALLBACK_BASE_URL=http://localhost:8000"
    fi
else
    echo -e "${YELLOW}⚠️  No .env file found${NC}"
    echo "   Create a .env file with:"
    echo "   CALLBACK_BASE_URL=http://localhost:8000"
fi

echo ""

# Show Docker status
echo "🐳 Docker Status:"
if docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "(noit|app)" > /dev/null 2>&1; then
    echo "   Running containers:"
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "(noit|app)" | head -5
else
    echo -e "${YELLOW}   No noit-related containers found running${NC}"
fi

echo ""
echo "🔧 Quick Fix Commands:"
echo "   1. Add to .env file:"
echo "      echo 'CALLBACK_BASE_URL=http://localhost:8000' >> .env"
echo ""
echo "   2. Restart Docker services:"
echo "      docker-compose -f docker-compose_local.yml down"
echo "      docker-compose -f docker-compose_local.yml up -d"
echo ""
echo "   3. Test again:"
echo "      ./test_callback_connectivity.sh"

echo ""
echo "📚 For more details, see: DOCKER_NETWORKING_SETUP.md" 