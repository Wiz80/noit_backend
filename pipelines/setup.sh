#!/bin/bash

# Kestra Pipeline Setup Script
# Este script configura y despliega los pipelines de Kestra para análisis de competidores

set -e

echo "🚀 Configurando Pipelines de Kestra para Análisis de Competidores"
echo "================================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
KESTRA_URL=${KESTRA_URL:-"http://localhost:8080"}
API_URL=${API_URL:-"http://localhost:8000"}
NAMESPACE="business.understanding"

# Functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check dependencies
check_dependencies() {
    log_info "Verificando dependencias..."
    
    if ! command -v curl &> /dev/null; then
        log_error "curl no está instalado. Por favor instálalo primero."
        exit 1
    fi
    
    if ! command -v jq &> /dev/null; then
        log_warning "jq no está instalado. Algunas verificaciones podrían fallar."
    fi
    
    log_success "Dependencias verificadas"
}

# Check if Kestra is running
check_kestra() {
    log_info "Verificando que Kestra esté ejecutándose..."
    
    if curl -s "$KESTRA_URL/api/v1/health" > /dev/null 2>&1; then
        log_success "Kestra está ejecutándose en $KESTRA_URL"
    else
        log_error "Kestra no está accesible en $KESTRA_URL"
        log_info "Por favor ejecuta: docker compose -f docker-compose_local.yml up -d"
        exit 1
    fi
}

# Check if API is running
check_api() {
    log_info "Verificando que la API esté ejecutándose..."
    
    if curl -s "$API_URL/health" > /dev/null 2>&1 || curl -s "$API_URL/" > /dev/null 2>&1; then
        log_success "API está ejecutándose en $API_URL"
    else
        log_warning "API no está accesible en $API_URL"
        log_info "Asegúrate de que el backend esté ejecutándose"
    fi
}

# Deploy flow to Kestra
deploy_flow() {
    local flow_file=$1
    local flow_name=$(basename "$flow_file" .yml)
    
    log_info "Desplegando flow: $flow_name"
    
    if [ ! -f "$flow_file" ]; then
        log_error "Archivo no encontrado: $flow_file"
        return 1
    fi
    
    # Create namespace if it doesn't exist
    curl -s -X PUT "$KESTRA_URL/api/v1/namespaces/$NAMESPACE" \
        -H "Content-Type: application/json" \
        -d '{"id": "'$NAMESPACE'", "description": "Business Understanding Namespace"}' > /dev/null
    
    # Deploy the flow
    response=$(curl -s -X PUT "$KESTRA_URL/api/v1/flows/$NAMESPACE/$flow_name" \
        -H "Content-Type: application/yaml" \
        --data-binary "@$flow_file")
    
    if echo "$response" | grep -q "id"; then
        log_success "Flow $flow_name desplegado correctamente"
        return 0
    else
        log_error "Error desplegando $flow_name: $response"
        return 1
    fi
}

# Test internal endpoint
test_internal_endpoint() {
    log_info "Probando endpoint interno de análisis de competidores..."
    
    test_payload='{
        "business_id": "test-business-id",
        "language": "es",
        "research_model": "gpt-4",
        "search_prompt": "Test análisis",
        "base_url": "'$API_URL'",
        "triggered_by": "setup_script_test"
    }'
    
    response=$(curl -s -X POST "$API_URL/api/v1/analyze-competitors/test-business-id" \
        -H "Content-Type: application/json" \
        -d "$test_payload" 2>/dev/null || echo "ERROR")
    
    if [[ "$response" == *"ERROR"* ]] || [[ "$response" == *"404"* ]]; then
        log_warning "Endpoint interno no está disponible o no hay datos de prueba"
        log_info "El endpoint funcionará cuando tengas business models reales en la DB"
    else
        log_success "Endpoint interno está disponible y responde"
    fi
}

# Verify database connectivity
test_database() {
    log_info "Verificando conectividad a la base de datos..."
    
    # This will trigger a flow execution to test DB connectivity
    response=$(curl -s -X POST "$KESTRA_URL/api/v1/executions/$NAMESPACE/business-model-advanced-trigger" \
        -H "Content-Type: application/json" \
        -d '{
            "inputs": {
                "check_interval_minutes": 60,
                "max_concurrent_analysis": 1
            }
        }' 2>/dev/null || echo "ERROR")
    
    if [[ "$response" == *"id"* ]]; then
        execution_id=$(echo "$response" | jq -r '.id' 2>/dev/null || echo "unknown")
        log_success "Test de conectividad iniciado (execution: $execution_id)"
        log_info "Revisa los logs en: $KESTRA_URL/ui/executions/$execution_id"
    else
        log_warning "No se pudo iniciar test de conectividad"
    fi
}

# Main execution
main() {
    echo
    log_info "Iniciando configuración..."
    
    # Step 1: Check dependencies
    check_dependencies
    echo
    
    # Step 2: Check services
    check_kestra
    check_api
    echo
    
    # Step 3: Deploy flows
    log_info "Desplegando flows..."
    
    if deploy_flow "business-model-trigger.yml"; then
        log_success "Flow básico desplegado"
    fi
    
    if deploy_flow "business-model-advanced-trigger.yml"; then
        log_success "Flow avanzado desplegado"
    fi
    echo
    
    # Step 4: Test components
    log_info "Ejecutando pruebas..."
    test_internal_endpoint
    test_database
    echo
    
    # Step 5: Final instructions
    log_success "¡Configuración completada!"
    echo
    echo "🎯 Próximos pasos:"
    echo "1. Ve a $KESTRA_URL para monitorear los pipelines"
    echo "2. Busca el namespace '$NAMESPACE'"
    echo "3. El pipeline 'business-model-advanced-trigger' se ejecutará cada 2 minutos"
    echo "4. Crea un modelo de negocio para probar el flujo completo"
    echo
    echo "📊 URLs útiles:"
    echo "- Kestra UI: $KESTRA_URL"
    echo "- API Docs: $API_URL/docs"
    echo "- Endpoint Interno: $API_URL/api/v1/analyze-competitors/{business_id}"
    echo
    echo "📖 Para más información, lee el README.md en este directorio"
    echo
    echo "⚠️  IMPORTANTE: El endpoint analyze-competitors ahora es para uso INTERNO solamente"
    echo "   (sin autenticación). El frontend NO debe llamarlo directamente."
}

# Handle script arguments
case "${1:-}" in
    "deploy")
        log_info "Solo desplegando flows..."
        check_dependencies
        check_kestra
        deploy_flow "business-model-trigger.yml"
        deploy_flow "business-model-advanced-trigger.yml"
        ;;
    "test")
        log_info "Solo ejecutando pruebas..."
        check_dependencies
        check_kestra
        check_api
        test_internal_endpoint
        test_database
        ;;
    "help"|"-h"|"--help")
        echo "Uso: $0 [comando]"
        echo
        echo "Comandos:"
        echo "  (ninguno)  - Configuración completa"
        echo "  deploy     - Solo desplegar flows"
        echo "  test       - Solo ejecutar pruebas"
        echo "  help       - Mostrar esta ayuda"
        ;;
    *)
        main
        ;;
esac 