#!/bin/bash

# ===========================================
# SECURE ENVIRONMENT GENERATOR
# ===========================================
# This script generates secure passwords and tokens for production

echo "🔐 Generating secure environment variables for production..."
echo ""

# Function to generate random password
generate_password() {
    local length=${1:-24}
    openssl rand -base64 $length | tr -d "=+/" | cut -c1-$length
}

# Function to generate strong token
generate_token() {
    openssl rand -base64 32 | tr -d "=+/"
}

# Generate secure values
POSTGRES_PASSWORD=$(generate_password 24)
KESTRA_POSTGRES_PASSWORD=$(generate_password 24)
REDIS_PASSWORD=$(generate_password 20)
TASKIQ_ADMIN_API_TOKEN=$(generate_token)
KESTRA_ADMIN_PASSWORD=$(generate_password 16)

echo "# Generated secure environment variables"
echo "# Generated on: $(date)"
echo "# IMPORTANT: Save these values securely and don't share them!"
echo ""
echo "# ===========================================
# DATABASE CONFIGURATION
# ===========================================
POSTGRES_USER=noit_backend_user
POSTGRES_PASSWORD=$POSTGRES_PASSWORD
POSTGRES_DB=noit_backend_prod

# Kestra Database
KESTRA_POSTGRES_DB=kestra_prod
KESTRA_POSTGRES_USER=kestra_prod_user
KESTRA_POSTGRES_PASSWORD=$KESTRA_POSTGRES_PASSWORD

# ===========================================
# REDIS CONFIGURATION
# ===========================================
REDIS_PASSWORD=$REDIS_PASSWORD
REDIS_PORT=6379

# ===========================================
# APPLICATION CONFIGURATION
# ===========================================
APP_PORT=8000

# ===========================================
# NGINX CONFIGURATION
# ===========================================
NGINX_HTTP_PORT=80
NGINX_HTTPS_PORT=443

# ===========================================
# TASKIQ CONFIGURATION
# ===========================================
TASKIQ_ADMIN_API_TOKEN=$TASKIQ_ADMIN_API_TOKEN
TASKIQ_ADMIN_PORT=3000

# ===========================================
# KESTRA WORKFLOW ENGINE CONFIGURATION
# ===========================================
KESTRA_BASIC_AUTH_ENABLED=true
KESTRA_ADMIN_EMAIL=admin@yourdomain.com
KESTRA_ADMIN_PASSWORD=$KESTRA_ADMIN_PASSWORD

# Kestra Ports
KESTRA_PORT=8080
KESTRA_MANAGEMENT_PORT=8081

# Kestra URL (adjust for your domain)
KESTRA_URL=https://kestra.yourdomain.com/"

echo ""
echo "✅ Secure environment variables generated!"
echo ""
echo "📋 Next steps:"
echo "1. Copy the generated values above to your .env file"
echo "2. Update the email addresses and URLs to match your domain"
echo "3. Make sure .env is in your .gitignore file"
echo "4. Set appropriate file permissions: chmod 600 .env"
echo "5. Test your configuration before deploying to production"
echo ""
echo "🔒 Security reminders:"
echo "- Never commit .env files to version control"
echo "- Use different passwords for each service"
echo "- Regularly rotate passwords and tokens"
echo "- Monitor your logs for suspicious activity"
echo "- Use SSL/TLS certificates for HTTPS" 