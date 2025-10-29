#!/bin/bash
# Dimensigon 2.0 Quick Deployment Script
# This script provides a guided deployment experience

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

print_banner() {
    echo -e "${GREEN}"
    echo "================================================================"
    echo "  Dimensigon 2.0 - Production Deployment Script"
    echo "  Distributed Orchestration Platform"
    echo "================================================================"
    echo -e "${NC}"
}

check_requirements() {
    log_step "Checking system requirements..."

    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        echo "Visit: https://docs.docker.com/get-docker/"
        exit 1
    fi
    log_info "Docker: $(docker --version)"

    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed. Please install Docker Compose first."
        echo "Visit: https://docs.docker.com/compose/install/"
        exit 1
    fi
    log_info "Docker Compose: $(docker-compose --version)"

    # Check for required files
    if [ ! -f "docker-compose.production.yml" ]; then
        log_error "docker-compose.production.yml not found!"
        exit 1
    fi

    log_info "All requirements satisfied!"
}

create_environment_file() {
    log_step "Creating environment configuration..."

    if [ -f ".env" ]; then
        log_warn ".env file already exists."
        read -p "Do you want to overwrite it? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Using existing .env file"
            return 0
        fi
    fi

    if [ ! -f ".env.example" ]; then
        log_error ".env.example not found!"
        exit 1
    fi

    cp .env.example .env
    log_info "Created .env from template"

    # Generate random secrets
    log_info "Generating secure random secrets..."

    SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')
    POSTGRES_PASSWORD=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
    REDIS_PASSWORD=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')

    # Update .env file
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "s/DM_SECRET_KEY=.*/DM_SECRET_KEY=${SECRET_KEY}/" .env
        sed -i '' "s/POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=${POSTGRES_PASSWORD}/" .env
        sed -i '' "s/REDIS_PASSWORD=.*/REDIS_PASSWORD=${REDIS_PASSWORD}/" .env
    else
        # Linux
        sed -i "s/DM_SECRET_KEY=.*/DM_SECRET_KEY=${SECRET_KEY}/" .env
        sed -i "s/POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=${POSTGRES_PASSWORD}/" .env
        sed -i "s/REDIS_PASSWORD=.*/REDIS_PASSWORD=${REDIS_PASSWORD}/" .env
    fi

    log_info "Secrets generated and saved to .env"
    log_warn "Please review and customize .env file for your environment"
}

setup_ssl_certificates() {
    log_step "Setting up SSL certificates..."

    mkdir -p ssl

    if [ -f "ssl/cert.pem" ] && [ -f "ssl/key.pem" ]; then
        log_info "SSL certificates already exist"
        return 0
    fi

    log_info "Generating self-signed SSL certificate..."

    openssl req -x509 -nodes -days 3650 -newkey rsa:4096 \
        -keyout ssl/key.pem \
        -out ssl/cert.pem \
        -subj "/C=US/ST=State/L=City/O=Dimensigon/OU=IT/CN=dimensigon.local" \
        2>/dev/null

    chmod 600 ssl/key.pem
    chmod 644 ssl/cert.pem

    log_info "Self-signed certificate generated (valid for 10 years)"
    log_warn "For production, replace with CA-signed certificates"
}

create_data_directories() {
    log_step "Creating data directories..."

    mkdir -p data/{postgres,redis,dimensigon/{config,logs,data},nginx/logs}

    log_info "Data directories created"
}

deploy_services() {
    log_step "Deploying Dimensigon services..."

    log_info "Pulling Docker images..."
    docker-compose -f docker-compose.production.yml pull

    log_info "Building Dimensigon image..."
    docker-compose -f docker-compose.production.yml build

    log_info "Starting services..."
    docker-compose -f docker-compose.production.yml up -d

    log_info "Waiting for services to be ready..."
    sleep 10

    # Check service status
    docker-compose -f docker-compose.production.yml ps
}

initialize_dimension() {
    log_step "Initializing Dimensigon dimension..."

    echo ""
    read -p "Do you want to create a new dimension? (Y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        read -p "Enter dimension name [production-cluster]: " DIMENSION_NAME
        DIMENSION_NAME=${DIMENSION_NAME:-production-cluster}

        log_info "Creating new dimension: ${DIMENSION_NAME}"
        docker-compose -f docker-compose.production.yml exec dimensigon \
            dimensigon new "${DIMENSION_NAME}"
    else
        log_info "Skipping dimension initialization"
        log_info "To join an existing dimension, use:"
        log_info "  docker-compose exec dimensigon dimensigon join <server-ip> <token>"
    fi
}

show_deployment_info() {
    log_step "Deployment complete!"

    echo ""
    echo -e "${GREEN}================================================================${NC}"
    echo -e "${GREEN}  Dimensigon 2.0 Successfully Deployed!${NC}"
    echo -e "${GREEN}================================================================${NC}"
    echo ""

    # Get the port from .env or use default
    PORT=$(grep "^DIMENSIGON_PORT=" .env 2>/dev/null | cut -d'=' -f2)
    PORT=${PORT:-20194}

    echo "Access Information:"
    echo "  - Web GUI: https://localhost:${PORT}/"
    echo "  - API: https://localhost:${PORT}/api/v1.0/"
    echo "  - Health Check: https://localhost:${PORT}/health"
    echo ""

    echo "Default Credentials:"
    echo "  - Username: root"
    echo "  - Password: (set during dimension initialization)"
    echo ""

    echo "Useful Commands:"
    echo "  - View logs: docker-compose -f docker-compose.production.yml logs -f"
    echo "  - Check status: docker-compose -f docker-compose.production.yml ps"
    echo "  - Stop services: docker-compose -f docker-compose.production.yml down"
    echo "  - Restart services: docker-compose -f docker-compose.production.yml restart"
    echo ""

    echo "Next Steps:"
    echo "  1. Access the Web GUI and log in"
    echo "  2. Configure gates and network settings"
    echo "  3. Set up monitoring and backups"
    echo "  4. Review DEPLOYMENT_GUIDE.md for production hardening"
    echo ""

    echo -e "${GREEN}================================================================${NC}"
}

cleanup_on_error() {
    log_error "Deployment failed!"
    log_info "Cleaning up..."
    docker-compose -f docker-compose.production.yml down 2>/dev/null || true
    exit 1
}

# Main deployment flow
main() {
    trap cleanup_on_error ERR

    print_banner

    # Check if running as root
    if [ "$EUID" -eq 0 ]; then
        log_warn "Running as root is not recommended"
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi

    check_requirements
    create_environment_file
    setup_ssl_certificates
    create_data_directories
    deploy_services
    initialize_dimension
    show_deployment_info

    log_info "Deployment script completed successfully!"
}

# Help function
show_help() {
    echo "Dimensigon 2.0 Deployment Script"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --help     Show this help message"
    echo "  -q, --quick    Quick deployment without prompts (use existing config)"
    echo ""
    echo "This script will:"
    echo "  1. Check system requirements"
    echo "  2. Create .env configuration"
    echo "  3. Generate SSL certificates"
    echo "  4. Create data directories"
    echo "  5. Deploy Docker services"
    echo "  6. Initialize Dimensigon dimension"
    echo ""
    echo "For detailed documentation, see DEPLOYMENT_GUIDE.md"
}

# Parse command line arguments
case "${1:-}" in
    -h|--help)
        show_help
        exit 0
        ;;
    -q|--quick)
        log_info "Quick deployment mode"
        check_requirements
        deploy_services
        show_deployment_info
        ;;
    *)
        main
        ;;
esac
