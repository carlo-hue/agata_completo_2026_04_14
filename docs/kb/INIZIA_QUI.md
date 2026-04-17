# Knowledge Base - Inizia Qui 🚀

Guida rapida per configurare il Knowledge Base con Voyage AI.

## Cosa Hai Già

✅ Cerebras API key (per LLM/chat)
✅ Voyage AI installato (`pip install voyageai`)
✅ Sistema completo implementato
⏳ Manca solo: API key Voyage AI

---

## Step 1: Ottieni API Key Voyage AI (2 minuti)

1. Vai su: **https://dash.voyageai.com/**
2. Sign up (usa Google o email)
3. Verifica email
4. Dashboard → **API Keys** → "Create new API key"
5. **Copia la chiave** (inizia con `pa-...`)

**Free tier**: 100 milioni tokens/mese (~50,000 email gratis)

---

## Step 2: Configura API Key

Apri il file `.env` e sostituisci `INSERISCI_QUI_LA_TUA_CHIAVE_VOYAGE` con la tua vera chiave:

```bash
nano .env
```

Cerca questa riga:
```
VOYAGE_API_KEY=INSERISCI_QUI_LA_TUA_CHIAVE_VOYAGE
```

Sostituisci con:
```
VOYAGE_API_KEY=pa-TUA_CHIAVE_VERA_QUI
```

Salva e chiudi (`Ctrl+O`, `Enter`, `Ctrl+X`)

---

## Step 3: Ricarica Environment

```bash
# Se usi systemd per Flask
sudo systemctl restart agata

# OPPURE se run manuale
source .env  # Ricarica variabili
```

---

## Step 4: Test Rapido

```bash
# Test Voyage AI
python -c "
import os
from dotenv import load_dotenv
load_dotenv()

from agata.kb.services.embedding_service import EmbeddingService

print('Testing Voyage AI...')
service = EmbeddingService(provider='voyage')
embedding = service.embed('Test email about Gaia DR3')
print(f'✓ Success! Dimensions: {len(embedding)}')
"
```

Se vedi `✓ Success! Dimensions: 1024` → funziona! 🎉

---

## Workflow Completo

### 1. Carica MBOX Files

```bash
mkdir -p kb_data/mbox_raw
# Carica qui i file .mbox da Google Takeout (via scp, sftp, etc.)
```

### 2. Migrazione Database (una volta sola)

```bash
sudo mysql catalogo < migrations/create_kb_tables.sql
```

### 3. Parse Emails

```bash
python -m agata.kb parse-mbox --mbox-dir=kb_data/mbox_raw/
```

Output:
```
Parsing MBOX file: kb_data/mbox_raw/Inbox.mbox
  Parsed 100 emails...
  Parsed 200 emails...

Parsing complete:
  Total messages: 1,234
  Successfully parsed: 1,234
```

### 4. Genera Embeddings (Voyage AI)

```bash
# Test con prime 10 email
python -m agata.kb generate-embeddings --provider=voyage --max-emails=10

# Se funziona, tutte le email
python -m agata.kb generate-embeddings --provider=voyage
```

Output:
```
============================================================
AGATA Knowledge Base - Embedding Generator
============================================================

Initializing services (provider: voyage)...
Found 1,234 parsed emails
Already embedded: 0 emails

Generating embeddings (batch size: 50)...
  Processed: 10, Skipped: 0, Errors: 0
  Processed: 20, Skipped: 0, Errors: 0
...

✓ Embeddings generated successfully!
Total vectors in store: 1,234
```

### 5. Ricerca Semantica

```bash
# Ricerca base
python -m agata.kb search "Gaia DR3 configuration" --provider=voyage

# Top 10 risultati
python -m agata.kb search "TESS data download" --provider=voyage --top-k=10

# In italiano
python -m agata.kb search "come configurare catalogo TESS" --provider=voyage
```

Output:
```
============================================================
Searching: Gaia DR3 configuration
============================================================
Using provider: voyage
Searching 1,234 documents...

1. Score: 0.8542
   Subject: Re: Gaia DR3 TAP query setup
   From: John Doe <john@example.com>
   Date: 2024-03-15T10:23:00
   Label: INBOX

2. Score: 0.7891
   Subject: Gaia archive configuration steps
   ...
```

---

## Comandi Utili

```bash
# Status knowledge base
python -m agata.kb status

# Aggiorna DB status
python -m agata.kb update-db-status

# Help
python -m agata.kb --help
python -m agata.kb generate-embeddings --help
python -m agata.kb search --help
```

---

## Come Funziona l'Architettura

```
User: "Come configurare Gaia DR3?"
  ↓
[1. Voyage AI] Cerca email simili tramite embeddings
  ↓ Trova top 5 email rilevanti
  ↓
[2. Cerebras LLM] Legge le 5 email e genera risposta
  ↓
Output: "Per configurare Gaia DR3 devi..."
```

**Separazione ruoli**:
- **Voyage AI**: Embeddings per ricerca semantica (trova email rilevanti)
- **Cerebras**: LLM per generare risposte (RAG - prossimo step)

---

## Monitoraggio Utilizzo

Dashboard Voyage AI: **https://dash.voyageai.com/usage**

- Free tier: 100M tokens/mese
- Reset: 1° giorno del mese
- Costo dopo free tier: ~$0.10 per 1M tokens

Stima: 1,000 email = ~500K tokens = ~0.5% del free tier

---

## Troubleshooting

### "VOYAGE_API_KEY environment variable not set"

Verifica `.env`:
```bash
grep VOYAGE_API_KEY .env
```

Se vuota, modifica `.env` e ricarica:
```bash
nano .env
source .env  # O restart Flask
```

### Test connessione Voyage AI

```bash
curl -X POST https://api.voyageai.com/v1/embeddings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $VOYAGE_API_KEY" \
  -d '{"input": ["test"], "model": "voyage-2"}'
```

Se vedi JSON con embeddings → API key valida! ✅

### "No emails found"

Prima esegui:
```bash
python -m agata.kb parse-mbox --mbox-dir=kb_data/mbox_raw/
```

---

## Prossimi Step (dopo setup base)

1. ✅ Configura Voyage AI
2. ✅ Parse MBOX
3. ✅ Genera embeddings
4. ✅ Test ricerca
5. 🔜 **Implementa UI web** (tab "Knowledge Base")
6. 🔜 **RAG con Cerebras** (Q&A intelligente)
7. 🔜 **Microsoft Teams integration**

---

## File Importanti

- **Configurazione**: `.env` (API keys)
- **Comandi CLI**: `python -m agata.kb --help`
- **Dati MBOX**: `kb_data/mbox_raw/` (crea e carica qui)
- **Email parsed**: `kb_data/gmail_parsed/` (generato automaticamente)
- **Embeddings**: Redis (`kb:vector:*`)

---

## Support

- **Questa guida**: `INIZIA_QUI.md`
- **Voyage AI Setup**: `VOYAGE_AI_SETUP.md`
- **Documentazione completa**: `docs/KNOWLEDGE_BASE_SETUP.md`
- **Quick start**: `KNOWLEDGE_BASE_QUICKSTART.md`

---

**Sei pronto!** 🚀

1. Ottieni API key Voyage AI
2. Modifica `.env`
3. Test con `python -c "..."`
4. Carica MBOX e inizia!
