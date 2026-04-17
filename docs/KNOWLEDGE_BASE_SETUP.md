# AGATA Knowledge Base - Setup Guide

Sistema di knowledge base per indicizzare email (MBOX) e conversazioni Teams, con ricerca semantica e AI Assistant.

## Architettura

```
┌──────────────────────────────────────────────────┐
│ MBOX Files (Google Takeout)                     │
│ /var/www/astrogen/kb_data/mbox_raw/              │
└────────────────┬─────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────┐
│ MBOX Parser                                      │
│ agata/kb/services/mbox_parser.py                 │
└────────────────┬─────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────┐
│ Parsed Emails (JSON)                             │
│ /var/www/astrogen/kb_data/gmail_parsed/          │
│   - msg_abc123.json                              │
│   - index.json (metadata)                        │
└────────────────┬─────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────┐
│ Embedding Service (OpenAI)                       │
│ agata/kb/services/embedding_service.py           │
│ Model: text-embedding-3-small (1536 dims)        │
└────────────────┬─────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────┐
│ Vector Store (Redis)                             │
│ agata/kb/services/vector_store.py                │
│ Keys: kb:vector:{doc_id}, kb:metadata:{doc_id}   │
└────────────────┬─────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────┐
│ Search API + UI                                  │
│ /api/kb/search, /api/kb/ask                      │
│ Tab: "📚 Knowledge Base"                         │
└──────────────────────────────────────────────────┘
```

## Setup Steps

### 1. Database Migration

Esegui la migrazione per creare le tabelle knowledge base:

```bash
# Come utente MySQL con permessi di CREATE TABLE
mysql -u root -p catalogo < /var/www/astrogen/migrations/create_kb_tables.sql
```

Tabelle create:
- `agata_kb_sync_status` - Track sync status per source (mbox, teams, etc.)
- `agata_kb_search_history` - Analytics ricerche utenti

### 2. Preparazione MBOX Files

Scarica email da Google Takeout in formato MBOX e caricale sul server:

```bash
# Crea directory per MBOX raw
mkdir -p /var/www/astrogen/kb_data/mbox_raw

# Upload dei file .mbox (via scp, sftp, etc.)
scp /path/to/Inbox.mbox user@server:/var/www/astrogen/kb_data/mbox_raw/
scp /path/to/Sent.mbox user@server:/var/www/astrogen/kb_data/mbox_raw/
```

### 3. Parse MBOX Files

Usa il CLI per estrarre le email in formato JSON:

```bash
cd /var/www/astrogen

# Parse singolo file
python -m agata.kb parse-mbox \
  --mbox-file=kb_data/mbox_raw/Inbox.mbox \
  --label=INBOX

# Parse intera directory
python -m agata.kb parse-mbox \
  --mbox-dir=kb_data/mbox_raw/
```

Output:
- Email estratte in `kb_data/gmail_parsed/{msg_id}.json`
- Index file: `kb_data/gmail_parsed/index.json`

### 4. Verifica Status

```bash
python -m agata.kb status
```

Output:
```
==============================================================
KNOWLEDGE BASE STATUS
==============================================================
Total emails indexed: 1,234
Last updated: 2026-01-31T10:30:00

Emails by label:
  INBOX                   856 emails
  Sent                    234 emails
  Important               144 emails

Date range:
  Earliest: 2020-01-15T08:23:00
  Latest: 2026-01-30T18:45:00

Storage location: /var/www/astrogen/kb_data/gmail_parsed
```

### 5. Update Database Status

Aggiorna il database con le statistiche di indicizzazione:

```bash
python -m agata.kb update-db-status
```

Questo aggiorna `agata_kb_sync_status` con:
- `total_items_indexed`
- `last_sync_at`
- `sync_status = 'completed'`

### 6. Generate Embeddings (TODO - prossimo step)

```bash
# CLI command da implementare
python -m agata.kb generate-embeddings \
  --source=mbox \
  --batch-size=50
```

Questo:
1. Legge email da `gmail_parsed/`
2. Genera embeddings con OpenAI
3. Salva in Redis Vector Store
4. Crea chunks per email lunghe

### 7. Test Search (TODO - prossimo step)

```bash
python -m agata.kb search "come configurare Gaia DR3 query"
```

## File Structure

```
/var/www/astrogen/
├── kb_data/                              # Knowledge base data (NOT in git)
│   ├── mbox_raw/                         # Raw MBOX files from Google Takeout
│   │   ├── Inbox.mbox
│   │   ├── Sent.mbox
│   │   └── ...
│   ├── gmail_parsed/                     # Parsed emails as JSON
│   │   ├── index.json                    # Email index/metadata
│   │   ├── abc123def456.json             # Individual email
│   │   └── ...
│   ├── teams_parsed/                     # Teams conversations (future)
│   │   └── ...
│   └── embeddings/                       # Cached embeddings
│       └── openai_text-embedding-3-small_{hash}.json
│
├── agata/kb/                             # Knowledge base module
│   ├── __init__.py
│   ├── __main__.py                       # CLI entry point
│   ├── services/
│   │   ├── mbox_parser.py                # ✓ MBOX → JSON parser
│   │   ├── embedding_service.py          # ✓ OpenAI embeddings
│   │   ├── vector_store.py               # ✓ Redis vector storage
│   │   ├── teams_sync.py                 # TODO: Microsoft Teams integration
│   │   └── knowledge_base_service.py     # TODO: High-level search/RAG
│   └── cli/
│       ├── kb_cli.py                     # ✓ CLI commands
│       └── __init__.py
│
└── migrations/
    └── create_kb_tables.sql              # ✓ Database schema
```

## Environment Variables Required

```bash
# OpenAI for embeddings
OPENAI_API_KEY=sk-...

# Redis (already configured)
REDIS_URL=redis://localhost:6379/0

# LLM for RAG (already configured)
ANTHROPIC_API_KEY=sk-ant-...
# or CEREBRAS_API_KEY=...
```

## CLI Commands Reference

### Parse MBOX

```bash
# Single file with label
python -m agata.kb parse-mbox \
  --mbox-file=/path/to/file.mbox \
  --label=INBOX

# Entire directory
python -m agata.kb parse-mbox \
  --mbox-dir=/path/to/mbox_files/

# Custom output directory
python -m agata.kb parse-mbox \
  --mbox-file=/path/to/file.mbox \
  --output-dir=/custom/path
```

### Status

```bash
# Show indexing status
python -m agata.kb status

# Custom output directory
python -m agata.kb status --output-dir=/custom/path
```

### Update DB Status

```bash
# Sync file stats to database
python -m agata.kb update-db-status
```

## Next Steps (TODO)

1. **Generate Embeddings CLI**: Batch process parsed emails → embeddings → Redis
2. **Search API**: `/api/kb/search` endpoint with semantic search
3. **RAG Q&A API**: `/api/kb/ask` endpoint with LLM integration
4. **UI Tab**: Repurpose "Stelle VSX" → "Knowledge Base" with search interface
5. **Teams Integration**: Microsoft Graph API sync for Teams conversations
6. **Cron Jobs**: Auto-sync daily (if needed)

## Storage Estimates

- **MBOX files**: ~100KB per email → 1GB per 10,000 emails
- **Parsed JSON**: ~50KB per email → 500MB per 10,000 emails
- **Embeddings (Redis)**: ~6KB per email (1536 floats) → 60MB per 10,000 emails
- **Embedding cache (disk)**: ~10KB per email → 100MB per 10,000 emails

**Total per 10,000 emails**: ~1.6GB

## Troubleshooting

### Error: "Access denied for user"
Run migration as MySQL root or user with CREATE TABLE permissions.

### Error: "OPENAI_API_KEY not set"
```bash
export OPENAI_API_KEY=sk-...
```

### Redis connection refused
```bash
sudo systemctl start redis
redis-cli PING  # Should return PONG
```

### MBOX parsing errors
- Check file encoding (should be UTF-8 or ASCII)
- Large files may take time (progress printed every 100 emails)
- Partial failures are OK (errors counted but don't stop parsing)

## Performance

- **MBOX parsing**: ~100-500 emails/second (depends on email size)
- **Embedding generation**: ~50 emails/second (OpenAI API rate limit)
- **Vector search**: ~1000 queries/second (Python cosine similarity)
  - Can upgrade to Redis Stack for >10K queries/second

## Security Notes

- Email content stored in plain text JSON (consider encryption at rest)
- Redis should be password-protected in production
- Knowledge base data in `kb_data/` excluded from git (.gitignore)
