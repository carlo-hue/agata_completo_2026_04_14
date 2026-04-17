# Knowledge Base AGATA - README

Sistema di ricerca semantica per email aziendali con AI.

---

## 🚀 Quick Start (3 comandi)

```bash
# 1. Installa (100% GRATIS)
pip install sentence-transformers

# 2. Genera embeddings
python -m agata.kb generate-embeddings --provider=sentence-transformers

# 3. Cerca!
python -m agata.kb search "Gaia DR3" --provider=sentence-transformers
```

---

## 📚 Guide Disponibili

1. **[INIZIA_QUI_SENTENCE_TRANSFORMERS.md](INIZIA_QUI_SENTENCE_TRANSFORMERS.md)** ⭐ **CONSIGLIATA**
   - Setup completo con Sentence Transformers
   - 100% gratis, nessuna API key
   - Funziona offline

2. **[KNOWLEDGE_BASE_QUICKSTART.md](KNOWLEDGE_BASE_QUICKSTART.md)**
   - Quick start con tutte le opzioni
   - Confronto provider (Sentence Transformers, Voyage AI, OpenAI)

3. **[VOYAGE_AI_SETUP.md](VOYAGE_AI_SETUP.md)**
   - Setup Voyage AI (richiede carta, free tier 200M tokens/mese)
   - Solo se vuoi massima qualità

4. **[docs/KNOWLEDGE_BASE_SETUP.md](docs/KNOWLEDGE_BASE_SETUP.md)**
   - Architettura dettagliata
   - Per sviluppatori

5. **[KNOWLEDGE_BASE_NO_OPENAI.md](KNOWLEDGE_BASE_NO_OPENAI.md)**
   - Alternative senza OpenAI

---

## 🎯 Provider Embeddings: Quale Scegliere?

| Provider | Costo | Qualità | Setup | Offline | API Key |
|----------|-------|---------|-------|---------|---------|
| **Sentence Transformers** ⭐ | 💚 GRATIS | ⭐⭐⭐ | Facile | ✅ Sì | ❌ No |
| Voyage AI | 💛 Free tier* | ⭐⭐⭐⭐⭐ | Media | ❌ No | ✅ Sì |
| OpenAI | 💰 Pagamento | ⭐⭐⭐⭐⭐ | Facile | ❌ No | ✅ Sì |

*Voyage AI: free tier 200M tokens/mese, ma **richiede carta di credito** per sbloccare rate limits

### ✅ Raccomandazione

**Usa Sentence Transformers** se:
- ✅ Vuoi 100% gratis (no carta richiesta)
- ✅ Vuoi privacy (tutto locale)
- ✅ Hai < 10,000 email
- ✅ Va bene qualità buona (non eccellente)

**Usa Voyage AI** se:
- ✅ Vuoi massima qualità
- ✅ Non ti dispiace aggiungere carta (comunque gratis)
- ✅ Hai > 10,000 email (più veloce)

---

## 📊 Comandi CLI

```bash
# Status
python -m agata.kb status

# Parse MBOX
python -m agata.kb parse-mbox --mbox-dir=kb_data/mbox_raw/

# Generate embeddings
python -m agata.kb generate-embeddings --provider=sentence-transformers

# Search
python -m agata.kb search "query" --provider=sentence-transformers --top-k=10

# Update DB status
python -m agata.kb update-db-status

# Help
python -m agata.kb --help
```

---

## 🏗️ Architettura

```
User Query: "Come configurare Gaia DR3?"
    ↓
[1. Sentence Transformers] Genera embedding query
    ↓
[2. Redis Vector Store] Cerca email simili (cosine similarity)
    ↓
[3. Top 5 email rilevanti] Recupera contenuto
    ↓
[4. Cerebras LLM] Genera risposta basata su email
    ↓
Output: "Per configurare Gaia DR3..."
```

**Separazione ruoli**:
- **Sentence Transformers**: Embeddings per ricerca (trova email rilevanti)
- **Cerebras**: LLM per risposte (genera testo basato su email trovate)

---

## 📂 Struttura Dati

```
kb_data/
├── mbox_raw/              # MBOX files da Google Takeout
│   ├── Inbox.mbox
│   └── Sent.mbox
├── gmail_parsed/          # Email estratte in JSON
│   ├── index.json
│   ├── abc123.json        # Email individuali
│   └── ...
└── embeddings/            # Cache embeddings (sentence-transformers)
```

**Redis**:
- `kb:vector:{email_id}` → numpy array (384 floats per Sentence Transformers)
- `kb:metadata:{email_id}` → JSON metadata
- `kb:index:all` → Set di tutti email_id

---

## 🔧 Requisiti

```bash
# Core
pip install sentence-transformers
pip install voyageai  # Opzionale
pip install redis numpy click

# Già installati in AGATA
python-dotenv
Flask
SQLAlchemy
```

---

## 🎓 Tutorial

### Parse MBOX
```bash
# Single file
python -m agata.kb parse-mbox --mbox-file=file.mbox --label=INBOX

# Directory
python -m agata.kb parse-mbox --mbox-dir=kb_data/mbox_raw/
```

### Generate Embeddings
```bash
# Test 10 email
python -m agata.kb generate-embeddings --provider=sentence-transformers --max-emails=10

# Tutte le email
python -m agata.kb generate-embeddings --provider=sentence-transformers
```

### Search
```bash
# Basic
python -m agata.kb search "Gaia DR3"

# Top 10
python -m agata.kb search "TESS photometry" --top-k=10

# Italian
python -m agata.kb search "come scaricare dati TESS" --provider=sentence-transformers
```

---

## 💾 Database

Tables create con `migrations/create_kb_tables.sql`:

- `agata_kb_sync_status` - Track sync status (MBOX, Teams, etc.)
- `agata_kb_search_history` - Analytics ricerche utenti

---

## 🔜 Prossimi Step

1. ✅ Parse MBOX
2. ✅ Generate embeddings
3. ✅ Search semantica
4. 🔜 **API endpoints** (`/api/kb/search`, `/api/kb/ask`)
5. 🔜 **UI tab** "Knowledge Base" in AGATA
6. 🔜 **RAG con Cerebras** (Q&A intelligente)
7. 🔜 **Microsoft Teams integration**

---

## 📞 Support

- **Quick Start**: [INIZIA_QUI_SENTENCE_TRANSFORMERS.md](INIZIA_QUI_SENTENCE_TRANSFORMERS.md)
- **Troubleshooting**: [KNOWLEDGE_BASE_QUICKSTART.md](KNOWLEDGE_BASE_QUICKSTART.md)
- **Architecture**: [docs/KNOWLEDGE_BASE_SETUP.md](docs/KNOWLEDGE_BASE_SETUP.md)

---

**Inizia ora**: `pip install sentence-transformers` 🚀
