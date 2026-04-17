#!/bin/bash

# Test script: Verifica che la bulk delete API ritorna JSON valido

echo "========================================"
echo "TEST: Bulk Delete API Response Format"
echo "========================================"
echo ""

# Test endpoint
ENDPOINT="https://app-test.astrogen.it/agata/admin/api/stars-catalog/bulk-delete"

echo "Testing API endpoint: $ENDPOINT"
echo ""

# Simula una richiesta con 0 stelle (all protected)
echo "Test 1: Empty delete (all protected)"
curl -s -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -d '{
    "delete_mode": "selected",
    "gaia_ids": []
  }' | python -m json.tool > /dev/null 2>&1

if [ $? -eq 0 ]; then
  echo "✅ Response is valid JSON"
else
  echo "❌ Response is NOT valid JSON"
  exit 1
fi

echo ""
echo "========================================"
echo "✅ All tests passed"
echo "========================================"
