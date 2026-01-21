#!/bin/bash
# CardWatch Production Deployment Script
# Run from the project root directory

set -e

echo "=============================================="
echo "   CardWatch Production Deployment"
echo "=============================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Step tracking
STEP=1

step() {
    echo ""
    echo -e "${GREEN}[$STEP] $1${NC}"
    echo "----------------------------------------------"
    ((STEP++))
}

warn() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

error() {
    echo -e "${RED}❌ $1${NC}"
}

success() {
    echo -e "${GREEN}✅ $1${NC}"
}

# Check we're in the right directory
if [ ! -d "backend" ] || [ ! -d "frontend-nextjs" ]; then
    error "Please run this script from the BulkBidding root directory"
    exit 1
fi

step "Setting up PostgreSQL Database (Supabase)"
echo "You need a PostgreSQL database. Supabase offers a free tier."
echo ""
echo "1. Go to https://supabase.com and create a free account"
echo "2. Create a new project"
echo "3. Go to Settings > Database > Connection string"
echo "4. Copy the 'URI' connection string"
echo ""
read -p "Paste your Supabase PostgreSQL connection string: " SUPABASE_URL

if [ -z "$SUPABASE_URL" ]; then
    error "No connection string provided"
    exit 1
fi

# Convert to asyncpg format
PG_URL=$(echo "$SUPABASE_URL" | sed 's/postgres:\/\//postgresql+asyncpg:\/\//' | sed 's/\?.*$//')
echo ""
success "Database URL configured"

step "Running Database Migration"
echo "Migrating data from SQLite to PostgreSQL..."
cd backend
source venv/bin/activate 2>/dev/null || python3 -m venv venv && source venv/bin/activate

# Check if migration script exists
if [ -f "migrate_to_postgres.py" ]; then
    python migrate_to_postgres.py "$PG_URL"
    if [ $? -eq 0 ]; then
        success "Migration complete!"
    else
        warn "Migration had some issues. You may need to run it again."
    fi
else
    warn "Migration script not found. Skipping data migration."
fi
cd ..

step "Generating Secure Secret Key"
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
echo "Generated: $SECRET_KEY"

step "Deploying Backend to Railway"
echo ""
echo "Railway provides easy Python hosting with persistent processes."
echo ""
echo "1. Go to https://railway.app and sign up/login with GitHub"
echo "2. Run: npx @railway/cli login"
echo ""
read -p "Press Enter after you've logged into Railway CLI... "

cd backend

# Initialize Railway project
echo "Initializing Railway project..."
npx @railway/cli init --name cardwatch-api 2>/dev/null || true

# Set environment variables
echo "Setting environment variables..."
npx @railway/cli variables set DATABASE_URL="$PG_URL"
npx @railway/cli variables set SECRET_KEY="$SECRET_KEY"
npx @railway/cli variables set DEBUG="false"
npx @railway/cli variables set ENABLE_SCHEDULER="true"

echo ""
read -p "Enter your ANTHROPIC_API_KEY (for AI features): " ANTHROPIC_KEY
if [ ! -z "$ANTHROPIC_KEY" ]; then
    npx @railway/cli variables set ANTHROPIC_API_KEY="$ANTHROPIC_KEY"
fi

# Deploy
echo ""
echo "Deploying to Railway..."
npx @railway/cli up --detach

echo ""
echo "Waiting for deployment..."
sleep 10

# Get the backend URL
BACKEND_URL=$(npx @railway/cli status --json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('deploymentDomain',''))" 2>/dev/null || echo "")

if [ -z "$BACKEND_URL" ]; then
    echo ""
    echo "Could not auto-detect backend URL."
    read -p "Enter your Railway backend URL (e.g., cardwatch-api.up.railway.app): " BACKEND_URL
fi

BACKEND_URL="https://$BACKEND_URL"
success "Backend deployed to: $BACKEND_URL"

# Update CORS
npx @railway/cli variables set CORS_ORIGINS="https://*.vercel.app"

cd ..

step "Deploying Frontend to Vercel"
cd frontend-nextjs

echo "Logging into Vercel..."
npx vercel login

echo ""
echo "Deploying to Vercel..."
echo "Setting environment variables..."

# Deploy with environment variables
npx vercel --yes \
    -e NEXT_PUBLIC_API_URL="$BACKEND_URL" \
    -e NEXT_PUBLIC_GRAPHQL_URL="$BACKEND_URL/graphql" \
    --prod

FRONTEND_URL=$(npx vercel ls --json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0].get('url',''))" 2>/dev/null || echo "")

cd ..

step "Updating CORS for Production"
cd backend
npx @railway/cli variables set CORS_ORIGINS="https://$FRONTEND_URL,https://*.vercel.app"
cd ..

echo ""
echo "=============================================="
echo "   🎉 Deployment Complete!"
echo "=============================================="
echo ""
echo "Frontend: https://$FRONTEND_URL"
echo "Backend:  $BACKEND_URL"
echo "API Docs: $BACKEND_URL/docs"
echo "GraphQL:  $BACKEND_URL/graphql"
echo ""
echo "Scheduler Status: $BACKEND_URL/api/scheduler/status"
echo ""
echo "Next steps:"
echo "1. Test the frontend at https://$FRONTEND_URL"
echo "2. Check scheduler status to ensure scrapers are running"
echo "3. Regenerate your Anthropic API key (it was exposed in .env)"
echo ""
