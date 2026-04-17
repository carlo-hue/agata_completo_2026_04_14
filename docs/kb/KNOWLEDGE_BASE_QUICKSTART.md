# Knowledge Base - Quick Start Guide

Sistema per indicizzare email aziendali (MBOX) con ricerca semantica AI.

## Setup in 5 minuti

### 1. Database Migration

```bash
# Esegui come utente MySQL root
sudo mysql catalogo < migrations/create_kb_tables.sql
```

### 2. Carica MBOX Files

```bash
# Crea directory e carica i file .mbox da Google Takeout
mkdir -p kb_data/mbox_raw
# Copia qui i tuoi file .mbox
```

### 3. Parse Emails

```bash
# Parse tutti gli MBOX in una directory
python -m agata.kb parse-mbox --mbox-dir=kb_data/mbox_raw/

# Oppure singolo file
python -m agata.kb parse-mbox --mbox-file=kb_data/mbox_raw/Inbox.mbox --label=INBOX
```

Output: Email estratte in formato JSON in `kb_data/gmail_parsed/`

### 4. Genera Embeddings

**🌟 OPZIONE CONSIGLIATA: Sentence Transformers (100% GRATIS)**
```bash
# Installa sentence-transformers
pip install sentence-transformers

# Genera embeddings (GRATIS, offline, nessuna API key)
python -m agata.kb generate-embeddings --provider=sentence-transformers

# Test con prime 10 email
python -m agata.kb generate-embeddings --provider=sentence-transformers --max-emails=10
```

**Vantaggi**: Gratis sempre, offline, privacy totale, supporta italiano.
**Tempo**: ~1-2 sec/email (CPU). Per 1000 email: ~20-30 minuti.

---

**Opzione B: Voyage AI** (richiede carta di credito, free tier 200M tokens/mese)
```bash
# Richiede aggiunta carta su https://dashboard.voyageai.com/billing
# Comunque gratis fino a 200M tokens/mese
pip install voyageai
python -m agata.kb generate-embeddings --provider=voyage
```

**Opzione C: OpenAI** (a pagamento, ~$0.00002/email)
```bash
export OPENAI_API_KEY=sk-...
python -m agata.kb generate-embeddings --provider=openai
```

### 5. Cerca!

```bash
# Ricerca semantica (usa stesso provider di generate-embeddings)
python -m agata.kb search "come configurare Gaia DR3" --provider=sentence-transformers
python -m agata.kb search "TESS data download" --provider=sentence-transformers --top-k=10

# Con Voyage AI
python -m agata.kb search "query" --provider=voyage

# Con OpenAI
python -m agata.kb search "query" --provider=openai
```

**IMPORTANTE**: Usa lo stesso `--provider` per generate-embeddings e search!

## Comandi Utili

```bash
# Mostra statistiche
python -m agata.kb status

# Aggiorna database status
python -m agata.kb update-db-status

# Help
python -m agata.kb --help
python -m agata.kb parse-mbox --help
```

## Storage

- **MBOX raw**: `kb_data/mbox_raw/` (file originali)
- **Email JSON**: `kb_data/gmail_parsed/` (~50KB per email)
- **Embeddings**: Redis + disk cache `kb_data/embeddings/` (~6KB per email)

## Prossimi Step

- [ ] Integrazione Microsoft Teams (Graph API)
- [ ] UI tab "Knowledge Base" in AGATA
- [ ] API `/api/kb/search` e `/api/kb/ask` (RAG)
- [ ] Cron job per sync automatico

## Costi Provider

### Sentence Transformers (locale)
- **Costo**: 💚 **GRATIS** (completamente)
- **Setup**: Download modello ~500MB (una tantum)
- **Privacy**: ✅ Nessun dato inviato a terzi

### Voyage AI (cloud)
- **Free tier**: 100M tokens/mese (~50,000 email)
- **Dopo free tier**: ~$0.10 per 1M tokens

### OpenAI (cloud)
- **Embedding**: ~$0.00002 per email
- **10,000 email**: ~$0.20
- **100,000 email**: ~$2.00

**Raccomandazione**: Inizia con sentence-transformers (gratis!) 💰

## Troubleshooting

### "OPENAI_API_KEY not set"
```bash
export OPENAI_API_KEY=sk-proj-...
# Aggiungi a ~/.bashrc per persistenza
```

### "No emails found"
Prima esegui `parse-mbox`

### "No embeddings found"
Prima esegui `generate-embeddings`

### Redis connection refused
```bash
sudo systemctl start redis
redis-cli PING  # deve rispondere PONG
```

## Documentazione Completa

Vedi [docs/KNOWLEDGE_BASE_SETUP.md](docs/KNOWLEDGE_BASE_SETUP.md) per architettura dettagliata.
