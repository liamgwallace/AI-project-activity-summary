#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo "==================================="
echo "PAIS Container Entrypoint"
echo "==================================="

# Ensure required directories exist
echo -e "${GREEN}✓${NC} Creating required directories..."
mkdir -p /app/data /app/logs /app/config

# Check for required credential files
echo ""
echo "Checking for required credential files..."

missing_credentials=false

if [ ! -f "/app/config/gmail_credentials.json" ]; then
    echo -e "${YELLOW}⚠ Warning:${NC} gmail_credentials.json not found in /app/config/"
    echo "  Gmail integration will not work without this file."
    echo "  Download it from Google Cloud Console and place it in config/gmail_credentials.json"
    missing_credentials=true
else
    echo -e "${GREEN}✓${NC} gmail_credentials.json found"
fi

if [ ! -f "/app/config/calendar_credentials.json" ]; then
    echo -e "${YELLOW}⚠ Warning:${NC} calendar_credentials.json not found in /app/config/"
    echo "  Google Calendar integration will not work without this file."
    echo "  Download it from Google Cloud Console and place it in config/calendar_credentials.json"
    missing_credentials=true
else
    echo -e "${GREEN}✓${NC} calendar_credentials.json found"
fi

# Check for token files (these will be created by the app if missing)
echo ""
echo "Checking for token files..."

if [ ! -f "/app/data/gmail_token.json" ]; then
    echo -e "${YELLOW}⚠${NC} gmail_token.json not found - will be created on first Gmail auth"
else
    echo -e "${GREEN}✓${NC} gmail_token.json found"
fi

if [ ! -f "/app/data/calendar_token.json" ]; then
    echo -e "${YELLOW}⚠${NC} calendar_token.json not found - will be created on first Calendar auth"
else
    echo -e "${GREEN}✓${NC} calendar_token.json found"
fi

# Check for .env variables (GitHub token is most critical)
echo ""
echo "Checking for required environment variables..."

if [ -z "$PAIS_GITHUB_TOKEN" ]; then
    echo -e "${YELLOW}⚠ Warning:${NC} PAIS_GITHUB_TOKEN not set - GitHub integration disabled"
else
    echo -e "${GREEN}✓${NC} PAIS_GITHUB_TOKEN is set"
fi

if [ -z "$PAIS_OPENAI_API_KEY" ]; then
    echo -e "${YELLOW}⚠ Warning:${NC} PAIS_OPENAI_API_KEY not set - AI processing disabled"
else
    echo -e "${GREEN}✓${NC} PAIS_OPENAI_API_KEY is set"
fi

# Set correct permissions
echo ""
echo -e "${GREEN}✓${NC} Setting permissions..."
chmod -R 755 /app/data /app/logs 2>/dev/null || true

# Database initialization check
echo ""
echo "Checking database..."
if [ ! -f "/app/data/activity_system.db" ]; then
    echo -e "${YELLOW}⚠${NC} Database not found - will be created on first run"
else
    echo -e "${GREEN}✓${NC} Database exists"
fi

echo ""
echo "==================================="
echo "Starting PAIS..."
echo "==================================="
echo ""

# Execute the main command
exec "$@"
