#!/bin/bash
set -e

# Quick start script for Sprites + Chat demo

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

print_header "🚀 boring-ui + Sprites Chat Demo"

# Check if running with --help
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --help, -h          Show this help"
    echo "  --demo              Run interactive demo dashboard"
    echo "  --test              Run integration tests"
    echo "  --backend-only      Start only backend"
    echo "  --frontend-only     Start only frontend"
    echo ""
    echo "Examples:"
    echo "  $0                  Start full app"
    echo "  $0 --demo           Open demo dashboard"
    echo "  $0 --test           Run integration tests"
    exit 0
fi

# Check credentials
print_info "Checking Sprites.dev credentials..."
if [ -z "$SPRITES_TOKEN" ]; then
    print_warning "SPRITES_TOKEN not set, trying to get from Vault..."
    if command -v vault &> /dev/null; then
        SPRITES_TOKEN=$(vault kv get -field=api_token secret/agent/boringdata-agent 2>/dev/null || true)
    fi
fi

if [ -z "$SPRITES_ORG" ]; then
    print_warning "SPRITES_ORG not set, trying to get from Vault..."
    if command -v vault &> /dev/null; then
        SPRITES_ORG=$(vault kv get -field=sprites_org secret/agent/boringdata-agent 2>/dev/null || true)
    fi
fi

if [ -z "$SPRITES_TOKEN" ] || [ -z "$SPRITES_ORG" ]; then
    print_error "Missing Sprites.dev credentials!"
    echo ""
    echo "Set environment variables:"
    echo "  export SPRITES_TOKEN=your-token"
    echo "  export SPRITES_ORG=your-org"
    echo ""
    echo "Or configure in Vault:"
    echo "  vault kv put secret/agent/boringdata-agent api_token=... sprites_org=..."
    exit 1
fi

print_success "Sprites credentials found"
print_info "Org: $SPRITES_ORG"

# Handle special modes
case "${1:-}" in
    --demo)
        print_header "Opening Demo Dashboard"
        print_info "Opening examples/sprites_chat_demo.html in browser..."
        if command -v xdg-open &> /dev/null; then
            xdg-open "examples/sprites_chat_demo.html"
        elif command -v open &> /dev/null; then
            open "examples/sprites_chat_demo.html"
        else
            print_warning "Could not open browser automatically"
            echo "Open manually: file://$PROJECT_ROOT/examples/sprites_chat_demo.html"
        fi
        exit 0
        ;;
    --test)
        print_header "Running Integration Tests"
        python3 examples/test_sprites_chat_integration.py
        exit 0
        ;;
    --backend-only)
        print_header "Starting Backend Only (port 8000)"
        export SANDBOX_PROVIDER=sprites
        export SPRITES_TOKEN
        export SPRITES_ORG
        python3 -c "
from boring_ui.api.app import create_app
import uvicorn

app = create_app(include_sandbox=True, include_companion=True)
uvicorn.run(app, host='0.0.0.0', port=8000, log_level='info')
"
        exit $?
        ;;
    --frontend-only)
        print_header "Starting Frontend Only (port 5173)"
        npx vite --host 0.0.0.0 --port 5173
        exit $?
        ;;
esac

# Install dependencies
print_header "Installing Dependencies"

if [ ! -d "node_modules" ]; then
    print_info "Installing npm packages..."
    npm install > /dev/null
    print_success "Frontend dependencies installed"
else
    print_success "Frontend dependencies already installed"
fi

if ! python3 -c "import boring_ui" 2>/dev/null; then
    print_info "Installing Python packages..."
    pip3 install -e . --break-system-packages > /dev/null
    print_success "Backend dependencies installed"
else
    print_success "Backend dependencies already installed"
fi

# Start services
print_header "Starting Services"

# Backend
print_info "Starting backend (port 8000)..."
export SANDBOX_PROVIDER=sprites
export SPRITES_TOKEN
export SPRITES_ORG

python3 << 'PYTHON_EOF' &
import os
from boring_ui.api.app import create_app
import uvicorn

app = create_app(include_sandbox=True, include_companion=True)
uvicorn.run(
    app,
    host='0.0.0.0',
    port=8000,
    log_level='info',
)
PYTHON_EOF
BACKEND_PID=$!
sleep 3

# Frontend
print_info "Starting frontend (port 5173)..."
npx vite --host 0.0.0.0 --port 5173 &
FRONTEND_PID=$!
sleep 2

# Print banner
print_header "✅ All Services Running"
echo ""
echo "🌐 Open in browser:"
echo "   • Main UI:    ${BLUE}http://localhost:5173${NC}"
echo "   • Sandbox:    ${BLUE}http://localhost:5173?chat=sandbox${NC}"
echo "   • Chat:       ${BLUE}http://localhost:5173?chat=companion${NC}"
echo ""
echo "📊 Demo Dashboard:"
echo "   • Interactive: ${BLUE}file://$PROJECT_ROOT/examples/sprites_chat_demo.html${NC}"
echo ""
echo "🔗 API Endpoints:"
echo "   • Status:  ${BLUE}curl http://localhost:8000/api/sandbox/status${NC}"
echo "   • Start:   ${BLUE}curl -X POST http://localhost:8000/api/sandbox/start${NC}"
echo "   • Logs:    ${BLUE}curl http://localhost:8000/api/sandbox/logs${NC}"
echo "   • Health:  ${BLUE}curl http://localhost:8000/api/sandbox/health${NC}"
echo ""
echo "✨ Provider: ${YELLOW}Sprites.dev ($SPRITES_ORG)${NC}"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Cleanup on exit
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM

# Wait for processes
wait
