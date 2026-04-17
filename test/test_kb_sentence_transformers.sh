#!/bin/bash
# Test script per Knowledge Base con Sentence Transformers (GRATIS)

echo "============================================================"
echo "AGATA Knowledge Base - Test Sentence Transformers"
echo "============================================================"
echo ""

# Colori per output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Check dipendenze
echo -e "${YELLOW}[1/4] Checking dependencies...${NC}"

if ! python -c "import sentence_transformers" 2>/dev/null; then
    echo -e "${RED}✗ sentence-transformers not installed${NC}"
    echo "Installing..."
    pip install sentence-transformers
else
    echo -e "${GREEN}✓ sentence-transformers installed${NC}"
fi

if ! python -c "import click" 2>/dev/null; then
    echo -e "${RED}✗ click not installed${NC}"
    pip install click
else
    echo -e "${GREEN}✓ click installed${NC}"
fi

# 2. Verifica struttura directory
echo ""
echo -e "${YELLOW}[2/4] Checking directory structure...${NC}"

if [ ! -d "kb_data" ]; then
    echo "Creating kb_data directories..."
    mkdir -p kb_data/{mbox_raw,gmail_parsed,embeddings}
fi
echo -e "${GREEN}✓ Directories OK${NC}"

# 3. Test embedding service
echo ""
echo -e "${YELLOW}[3/4] Testing embedding service...${NC}"

python -c "
from agata.kb.services.embedding_service import EmbeddingService

print('Initializing Sentence Transformers...')
service = EmbeddingService(provider='sentence-transformers')

print('Generating test embedding...')
text = 'This is a test email about Gaia DR3 and variable stars'
embedding = service.embed(text)

print(f'✓ Embedding generated: {len(embedding)} dimensions')
print(f'  First 5 values: {embedding[:5]}')
" || { echo -e "${RED}✗ Embedding test failed${NC}"; exit 1; }

echo -e "${GREEN}✓ Embedding service works${NC}"

# 4. Test vector store
echo ""
echo -e "${YELLOW}[4/4] Testing vector store...${NC}"

python -c "
from agata.kb.services.vector_store import VectorStore

store = VectorStore()
stats = store.get_stats()

print(f'Total vectors in Redis: {stats[\"total_vectors\"]}')

if stats['total_vectors'] == 0:
    print('No vectors yet (expected if first run)')
else:
    print(f'Sources: {stats[\"sources\"]}')
" || { echo -e "${RED}✗ Vector store test failed${NC}"; exit 1; }

echo -e "${GREEN}✓ Vector store works${NC}"

# Summary
echo ""
echo "============================================================"
echo -e "${GREEN}✓ ALL TESTS PASSED${NC}"
echo "============================================================"
echo ""
echo "Next steps:"
echo "  1. Upload MBOX files to: kb_data/mbox_raw/"
echo "  2. Parse: python -m agata.kb parse-mbox --mbox-dir=kb_data/mbox_raw/"
echo "  3. Generate embeddings: python -m agata.kb generate-embeddings --provider=sentence-transformers --max-emails=100"
echo "  4. Search: python -m agata.kb search 'Gaia DR3' --provider=sentence-transformers"
echo ""
