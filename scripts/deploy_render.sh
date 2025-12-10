#!/bin/bash
# ==============================================================================
# Render Deployment Helper Script for Irish Historical Sites GIS
# ==============================================================================
#
# This script helps prepare and verify your deployment to Render.com
# with Render PostgreSQL + PostGIS
#
# Prerequisites:
#   1. GitHub repository connected to Render
#   2. render.yaml blueprint file in repository root (creates database automatically)
#
# Usage:
#   chmod +x scripts/deploy_render.sh
#   ./scripts/deploy_render.sh
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
echo -e "${BLUE}║     Irish Historical Sites GIS - Render Deployment           ║${NC}"
echo -e "${BLUE}║     (Using Render PostgreSQL + PostGIS)                      ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"

# ==============================================================================
# STEP 1: Verify Prerequisites
# ==============================================================================

echo -e "\n${YELLOW}[1/4] Verifying prerequisites...${NC}"

# Check if render.yaml exists
if [ ! -f "render.yaml" ]; then
    echo -e "${RED}render.yaml not found in project root!${NC}"
    exit 1
fi
echo -e "${GREEN}✓ render.yaml found${NC}"

# Check if Dockerfile exists
if [ ! -f "Dockerfile" ]; then
    echo -e "${RED}Dockerfile not found!${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Dockerfile found${NC}"

# Check if build.sh exists and is executable
if [ ! -f "build.sh" ]; then
    echo -e "${RED}build.sh not found!${NC}"
    exit 1
fi
echo -e "${GREEN}✓ build.sh found${NC}"

# ==============================================================================
# STEP 2: Test Docker Build Locally
# ==============================================================================

echo -e "\n${YELLOW}[2/4] Testing Docker build locally...${NC}"

if command -v docker &> /dev/null; then
    if docker info &> /dev/null; then
        echo "Building Docker image..."
        docker build -t irish-geo-webapp:test . --quiet
        echo -e "${GREEN}✓ Docker build successful${NC}"
    else
        echo -e "${YELLOW}⚠ Docker not running, skipping local build test${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Docker not installed, skipping local build test${NC}"
fi

# ==============================================================================
# STEP 3: Collect Static Files (for verification)
# ==============================================================================

echo -e "\n${YELLOW}[3/4] Verifying static files...${NC}"

if [ -d "staticfiles" ]; then
    STATIC_COUNT=$(find staticfiles -type f | wc -l | tr -d ' ')
    echo -e "${GREEN}✓ staticfiles directory exists with ${STATIC_COUNT} files${NC}"
else
    echo -e "${YELLOW}⚠ staticfiles directory not found (will be created during build)${NC}"
fi

# ==============================================================================
# STEP 4: Display Deployment Instructions
# ==============================================================================

echo -e "\n${YELLOW}[4/4] Deployment Instructions${NC}"
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              READY FOR RENDER DEPLOYMENT                      ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"

echo -e "\n${BLUE}Option 1: Blueprint Deployment (Recommended)${NC}"
echo "1. Push your code to GitHub"
echo "2. Go to https://dashboard.render.com/"
echo "3. Click 'New' > 'Blueprint'"
echo "4. Connect your GitHub repository"
echo "5. Render will auto-detect render.yaml and configure both database and web service"
echo "6. DATABASE_URL is automatically provided when database is linked"
echo ""
echo -e "${YELLOW}   Note:${NC}"
echo "   - The render.yaml blueprint creates the PostgreSQL database automatically"
echo "   - DATABASE_URL is automatically provided by Render"
echo "   - No manual database configuration needed"
echo ""

echo -e "${BLUE}Option 2: Manual Web Service${NC}"
echo "1. Go to https://dashboard.render.com/"
echo "2. Click 'New' > 'Web Service'"
echo "3. Connect your GitHub repository"
echo "4. Configure:"
echo "   - Runtime: Docker"
echo "   - Region: Frankfurt (or closest to your users)"
echo "   - Plan: Starter or Standard"
echo "5. Add environment variables (same as above)"
echo "6. Deploy!"
echo ""

echo -e "${YELLOW}Post-Deployment Checklist:${NC}"
echo "□ Verify the app is accessible at https://irish-geo-webapp.onrender.com"
echo "□ Check logs for any startup errors"
echo "□ Test API endpoints: /api/v1/sites/"
echo "□ Verify map loads correctly"
echo "□ Test PWA installation on mobile"
echo ""

echo -e "${YELLOW}Useful Render Dashboard Links:${NC}"
echo "• Logs: Dashboard > Your Service > Logs"
echo "• Environment: Dashboard > Your Service > Environment"
echo "• Redeploy: Dashboard > Your Service > Manual Deploy"
echo ""

echo -e "${GREEN}Deployment preparation complete!${NC}"
