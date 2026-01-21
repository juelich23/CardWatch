#!/bin/bash

# BulkBidding - Easy Run Script
# Usage:
#   ./run.sh              - Start site + run scrapers
#   ./run.sh site         - Start site only (backend + frontend)
#   ./run.sh scrape       - Run scrapers only
#   ./run.sh backend      - Start backend only
#   ./run.sh frontend     - Start frontend only

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend-nextjs"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

check_port() {
    lsof -i :$1 > /dev/null 2>&1
    return $?
}

start_backend() {
    print_header "Starting Backend (FastAPI)"

    if check_port 8000; then
        echo -e "${YELLOW}Backend already running on port 8000${NC}"
        return 0
    fi

    cd "$BACKEND_DIR"
    source venv/bin/activate
    echo -e "${GREEN}Starting uvicorn on port 8000...${NC}"
    uvicorn app.main:app --reload --port 8000 &
    BACKEND_PID=$!
    echo "Backend PID: $BACKEND_PID"

    # Wait for backend to be ready
    echo "Waiting for backend to start..."
    for i in {1..30}; do
        if curl -s http://localhost:8000/health > /dev/null 2>&1; then
            echo -e "${GREEN}Backend is ready!${NC}"
            return 0
        fi
        sleep 1
    done
    echo -e "${RED}Backend failed to start${NC}"
    return 1
}

start_frontend() {
    print_header "Starting Frontend (Next.js)"

    if check_port 3000; then
        echo -e "${YELLOW}Frontend already running on port 3000${NC}"
        return 0
    fi

    cd "$FRONTEND_DIR"
    echo -e "${GREEN}Starting Next.js on port 3000...${NC}"
    npm run dev &
    FRONTEND_PID=$!
    echo "Frontend PID: $FRONTEND_PID"

    # Wait for frontend to be ready
    echo "Waiting for frontend to start..."
    for i in {1..30}; do
        if curl -s http://localhost:3000 > /dev/null 2>&1; then
            echo -e "${GREEN}Frontend is ready!${NC}"
            return 0
        fi
        sleep 1
    done
    echo -e "${YELLOW}Frontend may still be compiling...${NC}"
    return 0
}

run_scrapers() {
    print_header "Running All Scrapers"

    cd "$BACKEND_DIR"
    source venv/bin/activate

    echo -e "${GREEN}Starting scrapers...${NC}"
    python reload_all_auctions.py --max-items 5000
    echo -e "${GREEN}Scrapers complete!${NC}"
}

start_site() {
    start_backend
    start_frontend

    print_header "Site is Running!"
    echo -e "Backend:  ${GREEN}http://localhost:8000${NC}"
    echo -e "API Docs: ${GREEN}http://localhost:8000/docs${NC}"
    echo -e "GraphQL:  ${GREEN}http://localhost:8000/graphql${NC}"
    echo -e "Frontend: ${GREEN}http://localhost:3000${NC}"
    echo ""
}

# Main logic
case "${1:-all}" in
    site)
        start_site
        echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
        wait
        ;;
    scrape)
        run_scrapers
        ;;
    backend)
        start_backend
        echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
        wait
        ;;
    frontend)
        start_frontend
        echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
        wait
        ;;
    all|"")
        start_site
        run_scrapers
        print_header "All Done!"
        echo -e "Site is running at ${GREEN}http://localhost:3000${NC}"
        echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
        wait
        ;;
    *)
        echo "Usage: ./run.sh [site|scrape|backend|frontend|all]"
        echo ""
        echo "Commands:"
        echo "  (no args) - Start site + run scrapers"
        echo "  site      - Start site only (backend + frontend)"
        echo "  scrape    - Run scrapers only"
        echo "  backend   - Start backend only"
        echo "  frontend  - Start frontend only"
        exit 1
        ;;
esac
