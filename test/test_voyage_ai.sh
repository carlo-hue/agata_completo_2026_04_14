#!/bin/bash
# Test Voyage AI Knowledge Base Setup

echo "============================================================"
echo "AGATA Knowledge Base - Voyage AI Test"
echo "============================================================"
echo ""

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 1. Check API key
echo -e "${YELLOW}[1/5] Checking VOYAGE_API_KEY...${NC}"

if [ -z "$VOYAGE_API_KEY" ]; then
    echo -e "${RED}✗ VOYAGE_API_KEY not set${NC}"
    echo ""
    echo "Please set your Voyage AI API key:"
    echo "  1. Get key from: https://dash.voyageai.com/"
    echo "  2. Export: export VOYAGE_API_KEY=pa-YOUR_KEY_HERE"
    echo "  3. Or add to ~/.bashrc for persistence"
    exit 1
fi

if [[ ! "$VOYAGE_API_KEY" =~ ^pa- ]]; then
    echo -e "${RED}✗ Invalid VOYAGE_API_KEY format (should start with 'pa-')${NC}"
    exit 1
fi

echo -e "${GREEN}✓ VOYAGE_API_KEY is set (${VOYAGE_API_KEY:0:10}...)${NC}"

# 2. Check voyageai library
echo ""
echo -e "${YELLOW}[2/5] Checking voyageai library...${NC}"

if ! python -c "import voyageai" 2>/dev/null; then
    echo -e "${RED}✗ voyageai not installed${NC}"
    echo "Installing..."
    pip install voyageai
else
    echo -e "${GREEN}✓ voyageai installed${NC}"
fi

# 3. Test embedding service
echo ""
echo -e "${YELLOW}[3/5] Testing Voyage AI embedding service...${NC}"

python -c "
import sys
from agata.kb.services.embedding_service import EmbeddingService

try:
    print('Initializing Voyage AI client...')
    service = EmbeddingService(provider='voyage')

    print('Generating test embedding...')
    text = 'This is a test email about Gaia DR3 and variable stars'
    embedding = service.embed(text)

    print(f'✓ Embedding generated successfully')
    print(f'  Provider: {service.provider}')
    print(f'  Model: {service.model}')
    print(f'  Dimensions: {len(embedding)}')
    print(f'  First 5 values: {embedding[:5]}')

except Exception as e:
    print(f'✗ Error: {e}')
    sys.exit(1)
" || { echo -e "${RED}✗ Voyage AI test failed${NC}"; exit 1; }

echo -e "${GREEN}✓ Voyage AI embedding service works${NC}"

# 4. Test vector store
echo ""
echo -e "${YELLOW}[4/5] Testing vector store...${NC}"

python -c "
from agata.kb.services.vector_store import VectorStore

store = VectorStore()
stats = store.get_stats()

print(f'Total vectors in Redis: {stats[\"total_vectors\"]}')

if stats['total_vectors'] == 0:
    print('No vectors yet (this is OK for first run)')
else:
    print(f'Sources: {stats[\"sources\"]}')
" || { echo -e "${RED}✗ Vector store test failed${NC}"; exit 1; }

echo -e "${GREEN}✓ Vector store works${NC}"

# 5. Test full workflow (if MBOX files exist)
echo ""
echo -e "${YELLOW}[5/5] Checking for MBOX files...${NC}"

if [ -d "kb_data/mbox_raw" ] && [ "$(ls -A kb_data/mbox_raw/*.mbox 2>/dev/null)" ]; then
    echo -e "${GREEN}✓ MBOX files found${NC}"
    echo ""
    echo "You can now run the full workflow:"
    echo "  1. python -m agata.kb parse-mbox --mbox-dir=kb_data/mbox_raw/"
    echo "  2. python -m agata.kb generate-embeddings --provider=voyage --max-emails=10"
    echo "  3. python -m agata.kb search 'Gaia DR3' --provider=voyage"
else
    echo -e "${YELLOW}⚠ No MBOX files found in kb_data/mbox_raw/${NC}"
    echo ""
    echo "Upload MBOX files to kb_data/mbox_raw/ to continue"
fi

# Summary
echo ""
echo "============================================================"
echo -e "${GREEN}✓ ALL VOYAGE AI TESTS PASSED${NC}"
echo "============================================================"
echo ""
echo "API Key: ${VOYAGE_API_KEY:0:15}..."
echo "Free tier: 100M tokens/month (~50,000 emails)"
echo "Dashboard: https://dash.voyageai.com/usage"
echo ""
echo "Next steps:"
echo "  1. Upload MBOX files to: kb_data/mbox_raw/"
echo "  2. Parse: python -m agata.kb parse-mbox --mbox-dir=kb_data/mbox_raw/"
echo "  3. Generate embeddings: python -m agata.kb generate-embeddings --provider=voyage --max-emails=100"
echo "  4. Search: python -m agata.kb search 'Gaia DR3' --provider=voyage"
echo ""
