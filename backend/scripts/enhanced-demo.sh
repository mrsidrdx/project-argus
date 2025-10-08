#!/bin/bash

# Enhanced demo script showing call-chain awareness, approval gates, and admin UI
BASE_URL="http://localhost:8080"

echo "=== Enhanced Aegis Gateway Demo ==="
echo

echo "🔗 CALL-CHAIN AWARENESS DEMO"
echo "1. Testing call-chain with X-Parent-Agent header:"
curl -s -H "X-Agent-ID: restricted-agent" \
     -H "X-Parent-Agent: supervisor-agent" \
     -H "Content-Type: application/json" \
     -X POST $BASE_URL/tools/files/read \
     -d '{"path":"/public/readme.txt"}' | jq .
echo

echo "2. Same agent without required parent (should be blocked):"
curl -s -H "X-Agent-ID: restricted-agent" \
     -H "Content-Type: application/json" \
     -X POST $BASE_URL/tools/files/read \
     -d '{"path":"/public/readme.txt"}' | jq .
echo

echo "🛡️ APPROVAL GATES DEMO"
echo "3. High-value payment requiring approval:"
APPROVAL_RESPONSE=$(curl -s -H "X-Agent-ID: finance-agent-high-value" \
     -H "Content-Type: application/json" \
     -X POST $BASE_URL/tools/payments/create \
     -d '{"amount":25000, "currency": "USD", "vendor_id": "V99"}')
echo $APPROVAL_RESPONSE | jq .

# Extract approval ID if present
APPROVAL_ID=$(echo $APPROVAL_RESPONSE | jq -r '.approval_id // empty')

if [ ! -z "$APPROVAL_ID" ]; then
    echo
    echo "4. Approving the high-value payment:"
    curl -s -H "Content-Type: application/json" \
         -X POST $BASE_URL/approve/$APPROVAL_ID \
         -d '{"approved_by": "admin"}' | jq .
    echo
fi

echo "📊 ADMIN API DEMO"
echo "5. Checking registered agents:"
curl -s $BASE_URL/admin/agents | jq .
echo

echo "6. Policy summary:"
curl -s $BASE_URL/admin/policies | jq .
echo

echo "7. Recent decisions (last 10):"
curl -s "$BASE_URL/admin/decisions?limit=10" | jq '.decisions | length as $count | "Found \($count) recent decisions"'
echo

echo "🌐 ADMIN UI ACCESS"
echo "Admin UI available at: http://localhost:3000"
echo "- View real-time policy decisions"
echo "- Monitor agent activity"
echo "- Browse policy configuration"
echo "- Track approval workflows"
echo

echo "🔄 HOT-RELOAD DEMO"
echo "Try editing backend/policies/*.yaml files to see hot-reload in action!"
echo "Watch the logs: docker-compose logs -f aegis-gateway | grep -i policy"
echo

echo "Enhanced demo completed! 🎉"
