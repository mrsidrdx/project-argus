#!/bin/bash

# Aegis Gateway Startup Script
# This script provides easy commands to start the system in different modes

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker and try again."
        exit 1
    fi
}

# Function to check if docker-compose is available
check_compose() {
    if ! command -v docker-compose > /dev/null 2>&1; then
        print_error "docker-compose is not installed. Please install it and try again."
        exit 1
    fi
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  dev         Start in development mode (with hot reload)"
    echo "  prod        Start in production mode"
    echo "  stop        Stop all services"
    echo "  restart     Restart all services"
    echo "  logs        Show logs from all services"
    echo "  status      Show status of all services"
    echo "  clean       Stop and remove all containers, networks, and volumes"
    echo "  build       Build all images"
    echo "  test        Run the test suite"
    echo "  help        Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 dev      # Start development environment"
    echo "  $0 prod     # Start production environment"
    echo "  $0 logs     # View logs from all services"
}

# Function to wait for services to be healthy
wait_for_services() {
    print_status "Waiting for services to be healthy..."
    
    # Wait for backend
    timeout=60
    counter=0
    while [ $counter -lt $timeout ]; do
        if curl -f http://localhost:8080/health > /dev/null 2>&1; then
            print_success "Backend is healthy"
            break
        fi
        sleep 2
        counter=$((counter + 2))
    done
    
    if [ $counter -ge $timeout ]; then
        print_warning "Backend health check timed out"
    fi
    
    # Wait for frontend
    counter=0
    while [ $counter -lt $timeout ]; do
        if curl -f http://localhost:3000/api/health > /dev/null 2>&1; then
            print_success "Frontend is healthy"
            break
        fi
        sleep 2
        counter=$((counter + 2))
    done
    
    if [ $counter -ge $timeout ]; then
        print_warning "Frontend health check timed out"
    fi
}

# Function to show service URLs
show_urls() {
    echo ""
    print_success "🚀 Aegis Gateway is running!"
    echo ""
    echo "📊 Admin Dashboard:    http://localhost:3000"
    echo "🔧 API Gateway:        http://localhost:8080"
    echo "📈 Jaeger Tracing:     http://localhost:16686"
    echo "📊 OTel Metrics:       http://localhost:8889/metrics"
    echo ""
    print_status "Default login credentials:"
    echo "  Username: admin"
    echo "  Password: admin123"
    echo ""
    print_warning "⚠️  Change default credentials in production!"
}

# Main script logic
case "${1:-help}" in
    "dev")
        print_status "Starting Aegis Gateway in development mode..."
        check_docker
        check_compose
        docker-compose up -d --build
        wait_for_services
        show_urls
        print_status "Use '$0 logs' to view logs or '$0 stop' to stop services"
        ;;
    
    "prod")
        print_status "Starting Aegis Gateway in production mode..."
        check_docker
        check_compose
        docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
        wait_for_services
        show_urls
        print_status "Use '$0 logs' to view logs or '$0 stop' to stop services"
        ;;
    
    "stop")
        print_status "Stopping all services..."
        check_compose
        docker-compose down
        print_success "All services stopped"
        ;;
    
    "restart")
        print_status "Restarting all services..."
        check_compose
        docker-compose restart
        wait_for_services
        show_urls
        ;;
    
    "logs")
        check_compose
        docker-compose logs -f
        ;;
    
    "status")
        check_compose
        docker-compose ps
        ;;
    
    "clean")
        print_warning "This will remove all containers, networks, and volumes!"
        read -p "Are you sure? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_status "Cleaning up..."
            docker-compose down -v --remove-orphans
            docker system prune -f
            print_success "Cleanup complete"
        else
            print_status "Cleanup cancelled"
        fi
        ;;
    
    "build")
        print_status "Building all images..."
        check_docker
        check_compose
        docker-compose build --no-cache
        print_success "All images built successfully"
        ;;
    
    "test")
        print_status "Running test suite..."
        check_docker
        check_compose
        
        # Start services if not running
        if ! docker-compose ps | grep -q "Up"; then
            print_status "Starting services for testing..."
            docker-compose up -d --build
            wait_for_services
        fi
        
        # Run backend tests
        print_status "Running backend tests..."
        docker-compose exec aegis-gateway python -m pytest tests/ -v
        
        # Run CLI tests
        print_status "Running CLI tests..."
        docker-compose exec aegis-gateway python cli.py test call --help
        
        print_success "All tests completed"
        ;;
    
    "help"|*)
        show_usage
        ;;
esac
