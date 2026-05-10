#!/bin/bash

# =============================================================================
# Newman Test Runner for Properties Seasonal Pricing
# =============================================================================
# Usage: ./postman/scripts/run-seasonal-pricing-tests.sh [basic|e2e|all]
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
POSTMAN_DIR="$PROJECT_ROOT/postman"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Defaults
TEST_TYPE="${1:-all}"
REPORT_DIR="$POSTMAN_DIR/reports/newman-run-$(date +%s)"

# Function to print styled output
print_header() {
    echo -e "\n${BLUE}================================================${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}================================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ $1${NC}"
}

# Check if Newman is installed
check_newman() {
    if ! command -v newman &> /dev/null; then
        print_error "Newman not found. Installing..."
        npm install -g newman
        if [ $? -ne 0 ]; then
            print_error "Failed to install Newman"
            exit 1
        fi
        print_success "Newman installed"
    else
        print_success "Newman found: $(newman --version)"
    fi
}

# Check if services are running
check_services() {
    print_info "Checking if Properties service is running..."
    if ! curl -s http://localhost:8005/api/v1/properties 2>/dev/null | grep -q . ; then
        print_error "Properties service not responding on localhost:8005"
        print_info "Please run: make docker-up"
        exit 1
    fi
    print_success "Properties service is running on localhost:8005"
}

# Verify collection and environment files exist
verify_files() {
    print_info "Verifying Postman files..."
    
    if [ ! -f "$POSTMAN_DIR/collections/properties/seasonal-pricing-signed.postman_collection.json" ]; then
        print_error "Collection not found: seasonal-pricing-signed.postman_collection.json"
        exit 1
    fi
    print_success "Found: seasonal-pricing-signed.postman_collection.json"
    
    if [ ! -f "$POSTMAN_DIR/e2e/properties-seasonal-pricing/e2e-signature-integrity.postman_collection.json" ]; then
        print_error "Collection not found: e2e-signature-integrity.postman_collection.json"
        exit 1
    fi
    print_success "Found: e2e-signature-integrity.postman_collection.json"
    
    if [ ! -f "$POSTMAN_DIR/environments/travelhub-properties-seasonal-pricing-local.postman_environment.json" ]; then
        print_error "Environment not found: travelhub-properties-seasonal-pricing-local.postman_environment.json"
        exit 1
    fi
    print_success "Found: travelhub-properties-seasonal-pricing-local.postman_environment.json"
}

# Create report directory
mkdir -p "$REPORT_DIR"
print_success "Report directory created: $REPORT_DIR"

# Run basic tests
run_basic() {
    print_header "Running Basic Tests (seasonal-pricing-signed)"
    
    newman run "$POSTMAN_DIR/collections/properties/seasonal-pricing-signed.postman_collection.json" \
        -e "$POSTMAN_DIR/environments/travelhub-properties-seasonal-pricing-local.postman_environment.json" \
        --timeout 30000 \
        --reporters cli,json,html \
        --reporter-json-export "$REPORT_DIR/basic-tests.json" \
        --reporter-html-export "$REPORT_DIR/basic-tests.html"
    
    if [ $? -eq 0 ]; then
        print_success "Basic tests PASSED"
        return 0
    else
        print_error "Basic tests FAILED"
        return 1
    fi
}

# Run E2E tests
run_e2e() {
    print_header "Running E2E Tests (e2e-signature-integrity)"
    
    newman run "$POSTMAN_DIR/e2e/properties-seasonal-pricing/e2e-signature-integrity.postman_collection.json" \
        -e "$POSTMAN_DIR/environments/travelhub-properties-seasonal-pricing-local.postman_environment.json" \
        --timeout 30000 \
        --reporters cli,json,html \
        --reporter-json-export "$REPORT_DIR/e2e-tests.json" \
        --reporter-html-export "$REPORT_DIR/e2e-tests.html"
    
    if [ $? -eq 0 ]; then
        print_success "E2E tests PASSED"
        return 0
    else
        print_error "E2E tests FAILED"
        return 1
    fi
}

# Parse results and generate summary
generate_summary() {
    print_header "Test Summary"
    
    echo -e "${BLUE}Report Files:${NC}"
    echo "  • Basic tests JSON: $REPORT_DIR/basic-tests.json"
    echo "  • Basic tests HTML: $REPORT_DIR/basic-tests.html"
    echo "  • E2E tests JSON: $REPORT_DIR/e2e-tests.json"
    echo "  • E2E tests HTML: $REPORT_DIR/e2e-tests.html"
    
    echo -e "\n${BLUE}View HTML Reports:${NC}"
    if command -v open &> /dev/null; then
        echo "  • open $REPORT_DIR/basic-tests.html"
        echo "  • open $REPORT_DIR/e2e-tests.html"
    else
        echo "  • Check: file://$REPORT_DIR/basic-tests.html"
        echo "  • Check: file://$REPORT_DIR/e2e-tests.html"
    fi
}

# Main execution
main() {
    print_header "Properties Seasonal Pricing - Newman Test Runner"
    
    check_newman
    verify_files
    check_services
    
    OVERALL_PASSED=true
    
    case $TEST_TYPE in
        basic)
            run_basic || OVERALL_PASSED=false
            ;;
        e2e)
            run_e2e || OVERALL_PASSED=false
            ;;
        all)
            run_basic || OVERALL_PASSED=false
            run_e2e || OVERALL_PASSED=false
            ;;
        *)
            print_error "Invalid test type: $TEST_TYPE"
            echo "Usage: $0 [basic|e2e|all]"
            exit 1
            ;;
    esac
    
    generate_summary
    
    if [ "$OVERALL_PASSED" = true ]; then
        print_success "All tests PASSED ✓"
        exit 0
    else
        print_error "Some tests FAILED ✗"
        exit 1
    fi
}

main
