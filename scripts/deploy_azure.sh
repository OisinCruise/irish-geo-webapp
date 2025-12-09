#!/bin/bash
# ==============================================================================
# Azure Deployment Script for Irish Historical Sites GIS
# ==============================================================================
#
# Uses Neon.tech for PostgreSQL+PostGIS (Azure for Students doesn't support it)
#
# Prerequisites:
#   1. Azure CLI installed: brew install azure-cli
#   2. Docker installed and running
#   3. Logged into Azure: az login
#   4. Neon.tech database created with PostGIS enabled
#
# Usage:
#   chmod +x scripts/deploy_azure.sh
#   ./scripts/deploy_azure.sh
#
# ==============================================================================

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     Irish Historical Sites GIS - Azure Deployment           ║${NC}"
echo -e "${BLUE}║     (Using Neon.tech for PostgreSQL + PostGIS)              ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"

# ==============================================================================
# CONFIGURATION - Modify these values as needed
# ==============================================================================

RESOURCE_GROUP="irish-geo-webapp-rg"
LOCATION="italynorth"  # Italy North - allowed for Azure for Students
ACR_NAME="irishgeowebappacr$(date +%s | tail -c 5)"  # Unique name
APP_NAME="irish-geo-webapp-$(date +%s | tail -c 5)"   # Unique name

# ==============================================================================
# NEON DATABASE CONFIGURATION
# ==============================================================================

echo ""
echo -e "${YELLOW}Neon.tech Database Configuration${NC}"
echo -e "Get these values from your Neon dashboard → Connect"
echo ""

# Default values from your Neon setup (can be overridden)
DEFAULT_DB_HOST="ep-silent-breeze-a8a70nhq-pooler.eastus2.azure.neon.tech"
DEFAULT_DB_NAME="neondb"
DEFAULT_DB_USER="neondb_owner"

read -p "Database Host [$DEFAULT_DB_HOST]: " DB_HOST
DB_HOST=${DB_HOST:-$DEFAULT_DB_HOST}

read -p "Database Name [$DEFAULT_DB_NAME]: " DB_NAME
DB_NAME=${DB_NAME:-$DEFAULT_DB_NAME}

read -p "Database User [$DEFAULT_DB_USER]: " DB_USER
DB_USER=${DB_USER:-$DEFAULT_DB_USER}

read -sp "Database Password (from Neon): " DB_PASSWORD
echo ""

if [ -z "$DB_PASSWORD" ]; then
    echo -e "${RED}Database password is required!${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Database configuration received${NC}"

# ==============================================================================
# STEP 1: Verify Prerequisites
# ==============================================================================

echo -e "\n${YELLOW}[1/6] Verifying prerequisites...${NC}"

# Check Azure CLI
if ! command -v az &> /dev/null; then
    echo -e "${RED}Azure CLI not found. Install with: brew install azure-cli${NC}"
    exit 1
fi

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker not found. Please install Docker Desktop.${NC}"
    exit 1
fi

# Check if Docker is running
if ! docker info &> /dev/null; then
    echo -e "${RED}Docker is not running. Please start Docker Desktop.${NC}"
    exit 1
fi

# Check if logged into Azure
if ! az account show &> /dev/null; then
    echo -e "${YELLOW}Not logged into Azure. Opening browser for login...${NC}"
    az login
fi

SUBSCRIPTION=$(az account show --query name -o tsv)
echo -e "${GREEN}✓ Logged into Azure subscription: ${SUBSCRIPTION}${NC}"
echo -e "${GREEN}✓ Docker is running${NC}"

# ==============================================================================
# STEP 2: Create Resource Group
# ==============================================================================

echo -e "\n${YELLOW}[2/6] Creating resource group...${NC}"

az group create \
    --name $RESOURCE_GROUP \
    --location $LOCATION \
    --output none

echo -e "${GREEN}✓ Resource group created: ${RESOURCE_GROUP}${NC}"

# ==============================================================================
# STEP 3: Create Azure Container Registry
# ==============================================================================

echo -e "\n${YELLOW}[3/6] Creating Azure Container Registry...${NC}"

az acr create \
    --resource-group $RESOURCE_GROUP \
    --name $ACR_NAME \
    --sku Basic \
    --admin-enabled true \
    --output none

ACR_LOGIN_SERVER=$(az acr show --name $ACR_NAME --query loginServer --output tsv)
echo -e "${GREEN}✓ Container Registry created: ${ACR_LOGIN_SERVER}${NC}"

# ==============================================================================
# STEP 4: Build and Push Docker Image
# ==============================================================================

echo -e "\n${YELLOW}[4/6] Building and pushing Docker image...${NC}"

# Login to ACR
az acr login --name $ACR_NAME

# Build the image
docker build -t $ACR_LOGIN_SERVER/irish-geo-webapp:latest .

# Push to ACR
docker push $ACR_LOGIN_SERVER/irish-geo-webapp:latest

echo -e "${GREEN}✓ Docker image pushed to registry${NC}"

# ==============================================================================
# STEP 5: Create App Service Plan and Web App
# ==============================================================================

echo -e "\n${YELLOW}[5/6] Creating App Service Plan and Web App...${NC}"

az appservice plan create \
    --resource-group $RESOURCE_GROUP \
    --name "${APP_NAME}-plan" \
    --is-linux \
    --sku B1 \
    --output none

echo -e "${GREEN}✓ App Service Plan created${NC}"

ACR_USERNAME=$(az acr credential show --name $ACR_NAME --query username --output tsv)
ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query "passwords[0].value" --output tsv)

az webapp create \
    --resource-group $RESOURCE_GROUP \
    --plan "${APP_NAME}-plan" \
    --name $APP_NAME \
    --container-image-name "$ACR_LOGIN_SERVER/irish-geo-webapp:latest" \
    --container-registry-url "https://$ACR_LOGIN_SERVER" \
    --container-registry-user $ACR_USERNAME \
    --container-registry-password "$ACR_PASSWORD" \
    --output none

echo -e "${GREEN}✓ Web App created${NC}"

# ==============================================================================
# STEP 6: Configure Environment Variables
# ==============================================================================

echo -e "\n${YELLOW}[6/6] Configuring environment variables...${NC}"

DJANGO_SECRET_KEY=$(openssl rand -base64 50 | tr -dc 'a-zA-Z0-9' | head -c 50)

az webapp config appsettings set \
    --resource-group $RESOURCE_GROUP \
    --name $APP_NAME \
    --settings \
        DJANGO_DEBUG="False" \
        DJANGO_SECRET_KEY="$DJANGO_SECRET_KEY" \
        DJANGO_ALLOWED_HOSTS="${APP_NAME}.azurewebsites.net,localhost" \
        DB_NAME="$DB_NAME" \
        DB_USER="$DB_USER" \
        DB_PASSWORD="$DB_PASSWORD" \
        DB_HOST="$DB_HOST" \
        DB_PORT="5432" \
        DB_SSLMODE="require" \
        DJANGO_SETTINGS_MODULE="config.settings.production" \
        WEBSITES_PORT="8000" \
    --output none

echo -e "${GREEN}✓ Environment variables configured${NC}"

# ==============================================================================
# DEPLOYMENT COMPLETE
# ==============================================================================

APP_URL="https://${APP_NAME}.azurewebsites.net"

echo -e "\n${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                    DEPLOYMENT COMPLETE!                       ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Your app is now deploying. It may take 2-5 minutes to start.${NC}"
echo ""
echo -e "App URL:        ${GREEN}${APP_URL}${NC}"
echo -e "Resource Group: ${RESOURCE_GROUP}"
echo -e "Database Host:  ${DB_HOST} (Neon.tech)"
echo -e "Registry:       ${ACR_LOGIN_SERVER}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Wait 2-5 minutes for the app to start"
echo "2. Visit ${APP_URL} to verify deployment"
echo "3. Run migrations (see below)"
echo "4. Import your data"
echo ""
echo -e "${YELLOW}To run migrations:${NC}"
echo "az webapp ssh --resource-group $RESOURCE_GROUP --name $APP_NAME"
echo "python manage.py migrate"
echo ""
echo -e "${YELLOW}To view logs:${NC}"
echo "az webapp log tail --resource-group $RESOURCE_GROUP --name $APP_NAME"
echo ""
echo -e "${YELLOW}To redeploy after code changes:${NC}"
echo "docker build -t $ACR_LOGIN_SERVER/irish-geo-webapp:latest ."
echo "docker push $ACR_LOGIN_SERVER/irish-geo-webapp:latest"
echo "az webapp restart --resource-group $RESOURCE_GROUP --name $APP_NAME"
echo ""
echo -e "${RED}IMPORTANT: Save these credentials securely!${NC}"
echo "Django Secret Key: $DJANGO_SECRET_KEY"
echo ""

# Save deployment info to file
cat > deployment_info.txt << EOF
Irish Historical Sites GIS - Azure Deployment Info
===================================================
Deployed: $(date)

App URL: ${APP_URL}
Resource Group: ${RESOURCE_GROUP}
Location: ${LOCATION}

Container Registry: ${ACR_LOGIN_SERVER}
ACR Username: ${ACR_USERNAME}

Database (Neon.tech):
  Host: ${DB_HOST}
  Name: ${DB_NAME}
  User: ${DB_USER}
  SSL: Required

Django Secret Key: ${DJANGO_SECRET_KEY}

Commands:
---------
View logs: az webapp log tail --resource-group $RESOURCE_GROUP --name $APP_NAME
SSH: az webapp ssh --resource-group $RESOURCE_GROUP --name $APP_NAME
Restart: az webapp restart --resource-group $RESOURCE_GROUP --name $APP_NAME

Redeploy:
  docker build -t $ACR_LOGIN_SERVER/irish-geo-webapp:latest .
  docker push $ACR_LOGIN_SERVER/irish-geo-webapp:latest
  az webapp restart --resource-group $RESOURCE_GROUP --name $APP_NAME

Cleanup Azure Resources (DELETE EVERYTHING):
  az group delete --name $RESOURCE_GROUP --yes --no-wait

Note: This does NOT delete your Neon database. 
Manage it at: https://console.neon.tech
EOF

echo -e "${GREEN}Deployment info saved to: deployment_info.txt${NC}"
