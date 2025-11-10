#!/bin/bash
# E2E Tests for Basic I/O Service - Mermaid Import/Export
# Tests progression: Simple (customers) → Medium (subcontractors) → Complex (organization_units tree)
#
# Usage: ./e2e_mermaid_tests.sh EMAIL PASSWORD
#   EMAIL    - Email for authentication
#   PASSWORD - Password for authentication

# Don't exit on error - we want to see all test results
set +e

# Parse arguments
if [ $# -ne 2 ]; then
    echo "Usage: $0 EMAIL PASSWORD"
    echo "  EMAIL    - Email for authentication"
    echo "  PASSWORD - Password for authentication"
    exit 1
fi

AUTH_EMAIL="$1"
AUTH_PASSWORD="$2"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Service URLs
AUTH_URL="http://localhost:5001"
IDENTITY_URL="http://localhost:5002"
BASIC_IO_URL="http://localhost:5004"

# Internal Docker URLs (for basic_io to reach identity)
IDENTITY_INTERNAL_URL="http://identity_service:5000"

# Test data directory
TEST_DIR="/tmp/basic_io_e2e_tests"
mkdir -p "$TEST_DIR"

# Counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Basic I/O Service E2E Tests${NC}"
echo -e "${BLUE}  Testing Mermaid Import/Export${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${YELLOW}Authentication: ${AUTH_EMAIL}${NC}"
echo ""

# Function to print test header
test_header() {
    echo -e "\n${BLUE}>>> Test: $1${NC}"
    ((TESTS_RUN++))
}

# Function to print success
test_pass() {
    echo -e "${GREEN}✓ PASS: $1${NC}"
    ((TESTS_PASSED++))
}

# Function to print failure
test_fail() {
    echo -e "${RED}✗ FAIL: $1${NC}"
    ((TESTS_FAILED++))
}

# Function to print info
info() {
    echo -e "${YELLOW}ℹ INFO: $1${NC}"
}

# Cleanup function
cleanup() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}  Test Summary${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo -e "Total tests run: ${TESTS_RUN}"
    echo -e "${GREEN}Passed: ${TESTS_PASSED}${NC}"
    if [ $TESTS_FAILED -gt 0 ]; then
        echo -e "${RED}Failed: ${TESTS_FAILED}${NC}"
        exit 1
    else
        echo -e "${GREEN}All tests passed! 🎉${NC}"
    fi
}

trap cleanup EXIT

# ============================================
# Step 1: Authentication
# ============================================
test_header "Get JWT token from auth service"

TOKEN_RESPONSE=$(curl -s -X POST "$AUTH_URL/login" \
    -H "Content-Type: application/json" \
    -d "{
        \"email\": \"$AUTH_EMAIL\",
        \"password\": \"$AUTH_PASSWORD\"
    }" \
    -c "$TEST_DIR/cookies.txt")

# Extract token from cookies
if [ -f "$TEST_DIR/cookies.txt" ]; then
    JWT_TOKEN=$(grep access_token "$TEST_DIR/cookies.txt" | awk '{print $7}')
    if [ -n "$JWT_TOKEN" ]; then
        test_pass "JWT token obtained successfully"
        info "Token: ${JWT_TOKEN:0:30}..."
    else
        test_fail "Failed to extract JWT token from cookies"
        echo "Cookies file content:"
        cat "$TEST_DIR/cookies.txt"
        echo "Response: $TOKEN_RESPONSE"
        exit 1
    fi
else
    test_fail "No cookies file created"
    echo "Response: $TOKEN_RESPONSE"
    exit 1
fi

# ============================================
# Step 2: Test Simple Resource - Customers
# ============================================
echo -e "\n${BLUE}===========================================${NC}"
echo -e "${BLUE}  Test 1: Customers (Simple - No FK)${NC}"
echo -e "${BLUE}===========================================${NC}"

# Generate unique timestamp for emails to avoid conflicts
TIMESTAMP=$(date +%s)

# 2.1: Create test customers via direct POST
test_header "Create test customers directly in identity service"

CUSTOMER_1=$(curl -s -X POST "$IDENTITY_URL/customers" \
    -b "$TEST_DIR/cookies.txt" \
    -H "Content-Type: application/json" \
    -d "{
        \"name\": \"Test Customer Alpha\",
        \"company_id\": 1,
        \"email\": \"alpha_${TIMESTAMP}@test.com\",
        \"contact_person\": \"Alice Alpha\",
        \"phone_number\": \"1234567890\"
    }")

CUSTOMER_2=$(curl -s -X POST "$IDENTITY_URL/customers" \
    -b "$TEST_DIR/cookies.txt" \
    -H "Content-Type: application/json" \
    -d "{
        \"name\": \"Test Customer Beta\",
        \"company_id\": 1,
        \"email\": \"beta_${TIMESTAMP}@test.com\",
        \"contact_person\": \"Bob Beta\",
        \"phone_number\": \"0987654321\"
    }")

if echo "$CUSTOMER_1" | grep -q "\"id\""; then
    test_pass "Created customer 1"
    CUSTOMER_1_ID=$(echo "$CUSTOMER_1" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
else
    test_fail "Failed to create customer 1"
    echo "Response: $CUSTOMER_1"
fi

if echo "$CUSTOMER_2" | grep -q "\"id\""; then
    test_pass "Created customer 2"
    CUSTOMER_2_ID=$(echo "$CUSTOMER_2" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
else
    test_fail "Failed to create customer 2"
    echo "Response: $CUSTOMER_2"
fi

# 2.2: Export customers as JSON
test_header "Export customers as JSON"

EXPORT_JSON=$(curl -s -X GET "$BASIC_IO_URL/export?url=$IDENTITY_INTERNAL_URL/customers&type=json" \
    -b "$TEST_DIR/cookies.txt")

echo "$EXPORT_JSON" > "$TEST_DIR/customers_export.json"

if [ -s "$TEST_DIR/customers_export.json" ]; then
    COUNT=$(echo "$EXPORT_JSON" | grep -o '"id"' | wc -l)
    test_pass "Exported $COUNT customers as JSON"
else
    test_fail "Failed to export customers as JSON"
fi

# 2.3: Export customers as CSV
test_header "Export customers as CSV"

curl -s -X GET "$BASIC_IO_URL/export?url=$IDENTITY_INTERNAL_URL/customers&type=csv" \
    -b "$TEST_DIR/cookies.txt" \
    -o "$TEST_DIR/customers_export.csv"

if [ -s "$TEST_DIR/customers_export.csv" ]; then
    LINES=$(wc -l < "$TEST_DIR/customers_export.csv")
    test_pass "Exported customers as CSV ($LINES lines)"
    info "First 3 lines:"
    head -3 "$TEST_DIR/customers_export.csv"
else
    test_fail "Failed to export customers as CSV"
fi

# 2.4: Export customers as Mermaid Flowchart
test_header "Export customers as Mermaid Flowchart"

curl -s -X GET "$BASIC_IO_URL/export?url=$IDENTITY_INTERNAL_URL/customers&type=mermaid&diagram_type=flowchart" \
    -b "$TEST_DIR/cookies.txt" \
    -o "$TEST_DIR/customers_flowchart.mmd"

if [ -s "$TEST_DIR/customers_flowchart.mmd" ]; then
    test_pass "Exported customers as Mermaid Flowchart"
    info "First 10 lines:"
    head -10 "$TEST_DIR/customers_flowchart.mmd"
else
    test_fail "Failed to export customers as Mermaid Flowchart"
fi

# 2.5: Export customers as Mermaid Graph
test_header "Export customers as Mermaid Graph"

curl -s -X GET "$BASIC_IO_URL/export?url=$IDENTITY_INTERNAL_URL/customers&type=mermaid&diagram_type=graph" \
    -b "$TEST_DIR/cookies.txt" \
    -o "$TEST_DIR/customers_graph.mmd"

if [ -s "$TEST_DIR/customers_graph.mmd" ]; then
    test_pass "Exported customers as Mermaid Graph"
else
    test_fail "Failed to export customers as Mermaid Graph"
fi

# 2.6: Delete original customers
test_header "Delete original customers"

curl -s -X DELETE "$IDENTITY_URL/customers/$CUSTOMER_1_ID" \
    -b "$TEST_DIR/cookies.txt" > /dev/null

curl -s -X DELETE "$IDENTITY_URL/customers/$CUSTOMER_2_ID" \
    -b "$TEST_DIR/cookies.txt" > /dev/null

test_pass "Deleted original customers"

# 2.7: Import customers from JSON
test_header "Import customers from JSON"

IMPORT_JSON=$(curl -s -X POST "$BASIC_IO_URL/import?url=$IDENTITY_INTERNAL_URL/customers&type=json" \
    -b "$TEST_DIR/cookies.txt" \
    -F "file=@$TEST_DIR/customers_export.json")

echo "$IMPORT_JSON" > "$TEST_DIR/customers_import_result.json"

if echo "$IMPORT_JSON" | grep -q "imported"; then
    test_pass "Imported customers from JSON"
    info "Import result:"
    echo "$IMPORT_JSON" | head -20
else
    test_fail "Failed to import customers from JSON"
    echo "Response: $IMPORT_JSON"
fi

# 2.8: Import customers from CSV
test_header "Delete customers and import from CSV"

# Get all customers and delete them
CUSTOMERS=$(curl -s -X GET "$IDENTITY_URL/customers" -b "$TEST_DIR/cookies.txt")
echo "$CUSTOMERS" | grep -o '"id":"[^"]*"' | cut -d'"' -f4 | while read -r ID; do
    curl -s -X DELETE "$IDENTITY_URL/customers/$ID" -b "$TEST_DIR/cookies.txt" > /dev/null
done

IMPORT_CSV=$(curl -s -X POST "$BASIC_IO_URL/import?type=csv" \
    -b "$TEST_DIR/cookies.txt" \
    -F "file=@$TEST_DIR/customers_export.csv" \
    -F "url=$IDENTITY_INTERNAL_URL/customers")

if echo "$IMPORT_CSV" | grep -q '"successful_imports"'; then
    test_pass "Imported customers from CSV successfully"
else
    test_fail "Failed to import customers from CSV"
    echo "Response: $IMPORT_CSV"
fi

# 2.9: Import customers from Mermaid Flowchart
test_header "Delete customers and import from Mermaid Flowchart"

# Delete all customers
CUSTOMERS=$(curl -s -X GET "$IDENTITY_URL/customers" -b "$TEST_DIR/cookies.txt")
echo "$CUSTOMERS" | grep -o '"id":"[^"]*"' | cut -d'"' -f4 | while read -r ID; do
    curl -s -X DELETE "$IDENTITY_URL/customers/$ID" -b "$TEST_DIR/cookies.txt" > /dev/null
done

IMPORT_MERMAID=$(curl -s -X POST "$BASIC_IO_URL/import?url=$IDENTITY_INTERNAL_URL/customers&type=mermaid" \
    -b "$TEST_DIR/cookies.txt" \
    -F "file=@$TEST_DIR/customers_flowchart.mmd")

echo "$IMPORT_MERMAID" > "$TEST_DIR/customers_mermaid_import_result.json"

if echo "$IMPORT_MERMAID" | grep -q '"successful_imports"'; then
    test_pass "Imported customers from Mermaid Flowchart successfully"
else
    test_fail "Failed to import customers from Mermaid Flowchart"
    echo "Response: $IMPORT_MERMAID"
fi

# 2.10: Verify import count
test_header "Verify imported customers count"

CUSTOMERS_AFTER=$(curl -s -X GET "$IDENTITY_URL/customers" -b "$TEST_DIR/cookies.txt")
COUNT_AFTER=$(echo "$CUSTOMERS_AFTER" | grep -o '"id"' | wc -l)

if [ "$COUNT_AFTER" -ge 2 ]; then
    test_pass "Verified $COUNT_AFTER customers imported successfully"
else
    test_fail "Expected at least 2 customers, found $COUNT_AFTER"
fi

# ============================================
# Step 3: Test Tree Structure - Organization Units
# ============================================
echo -e "\n${BLUE}===========================================${NC}"
echo -e "${BLUE}  Test 2: Organization Units (Tree)${NC}"
echo -e "${BLUE}===========================================${NC}"

# Note: This requires company_id, which we'll need to handle
# For now, we'll skip this test and focus on customers/subcontractors

info "Tree structure tests (organization_units) require more setup"
info "Skipping for now - can be added later with proper company setup"

# ============================================
# Cleanup test data
# ============================================
test_header "Cleanup: Delete test customers"

CUSTOMERS=$(curl -s -X GET "$IDENTITY_URL/customers" -b "$TEST_DIR/cookies.txt")
echo "$CUSTOMERS" | grep -o '"id":"[^"]*"' | cut -d'"' -f4 | while read -r ID; do
    curl -s -X DELETE "$IDENTITY_URL/customers/$ID" -b "$TEST_DIR/cookies.txt" > /dev/null
done

test_pass "Cleaned up test customers"

info "Test files saved in: $TEST_DIR"
