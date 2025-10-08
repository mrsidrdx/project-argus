#!/bin/bash

# Demo script showing allowed and blocked flows
BASE_URL="http://localhost:8080"

echo "=== Aegis Gateway Demo ==="
echo

echo "1. Blocked high-value payment (exceeds max_amount 5000):"
curl -s -H "X-Agent-ID: finance-agent" \
     -H "Content-Type: application/json" \
     -X POST $BASE_URL/tools/payments/create \
     -d '{"amount":50000, "currency": "USD", "vendor_id": "V99"}' | jq .
echo

echo "2. Allowed payment within limits:"
curl -s -H "X-Agent-ID: finance-agent" \
     -H "Content-Type: application/json" \
     -X POST $BASE_URL/tools/payments/create \
     -d '{"amount":1000, "currency": "USD", "vendor_id": "V99"}' | jq .
echo

echo "3. Allowed HR file read inside /hr-docs/:"
curl -s -H "X-Agent-ID: hr-agent" \
     -H "Content-Type: application/json" \
     -X POST $BASE_URL/tools/files/read \
     -d '{"path":"/hr-docs/employee-handbook.pdf"}' | jq .
echo

echo "4. Blocked HR file read outside /hr-docs/ (e.g., /legal/contract.docx):"
curl -s -H "X-Agent-ID: hr-agent" \
     -H "Content-Type: application/json" \
     -X POST $BASE_URL/tools/files/read \
     -d '{"path":"/legal/contract.docx"}' | jq .
echo

echo "5. Blocked currency (not in allowed list):"
curl -s -H "X-Agent-ID: finance-agent" \
     -H "Content-Type: application/json" \
     -X POST $BASE_URL/tools/payments/create \
     -d '{"amount":1000, "currency": "JPY", "vendor_id": "V99"}' | jq .
echo

echo "Demo completed!"
