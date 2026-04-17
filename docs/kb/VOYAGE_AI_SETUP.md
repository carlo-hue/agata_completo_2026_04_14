# Knowledge Base con Voyage AI - Setup Completo

Voyage AI è il provider di embeddings raccomandato da Anthropic. Offre:
- ✅ **Free tier**: 100M tokens/mese (~50,000-100,000 email)
- ✅ **Qualità eccellente** (migliore di Sentence Transformers)
- ✅ **Veloce** (API cloud ottimizzata)
- ✅ **Supporta italiano**

---

## 1. Ottieni API Key (2 minuti)

1. Vai su: **https://dash.voyageai.com/**
2. Clicca "Sign Up" (puoi usare Google/GitHub)
3. Verifica email
4. Dashboard → **API Keys** → "Create new API key"
5. Copia la chiave (inizia con `pa-...`)

**Free tier**: 100 milioni di tokens al mese (rinnovato ogni mese)

---

## 2. Configura API Key sul Server

### Opzione A: Temporanea (per questa sessione)

```bash
export VOYAGE_API_KEY=pa-TUA_CHIAVE_QUI
```

### Opzione B: Permanente (consigliata)

```bash
# Aggiungi al tuo .bashrc
echo 'export VOYAGE_API_KEY=pa-TUA_CHIAVE_QUI' >> ~/.bashrc
source ~/.bashrc
```

### Verifica configurazione

```bash
echo $VOYAGE_API_KEY
# Dovrebbe mostrare: pa-...
```

---

## 3. Test Rapido

```bash
# Test embedding service
python -c "
from agata.kb.services.embedding_service import EmbeddingService

print('Testing Voyage AI...')
service = EmbeddingService(provider='voyage')

text = 'Test email about Gaia DR3 variable stars'
embedding = service.embed(text)

print(f'✓ Embedding generated: {len(embedding)} dimensions')
print(f'  Model: {service.model}')
print(f'  Provider: {service.provider}')
"
```

Output atteso:
```
Testing Voyage AI...
✓ Embedding generated: 1024 dimensions
  Model: voyage-2
  Provider: voyage
```

---

## 4. Workflow Completo

### Step 1: Migrazione Database (una volta)

```bash
sudo mysql catalogo < migrations/create_kb_tables.sql
```

### Step 2: Carica MBOX Files

```bash
mkdir -p kb_data/mbox_raw
# Carica qui i file .mbox da Google Takeout
```

### Step 3: Parse Emails

```bash
python -m agata.kb parse-mbox --mbox-dir=kb_data/mbox_raw/
```

Output:
```
Parsing MBOX file: kb_data/mbox_raw/Inbox.mbox
Label: Inbox
  Parsed 100 emails...
  Parsed 200 emails...
...

Parsing complete:
  Total messages: 1,234
  Successfully parsed: 1,234
  Skipped (duplicates): 0
  Errors: 0
```

### Step 4: Genera Embeddings con Voyage AI

```bash
# Test con prime 10 email
python -m agata.kb generate-embeddings \
  --provider=voyage \
  --max-emails=10

# Se funziona, processa tutte (o un batch più grande)
python -m agata.kb generate-embeddings \
  --provider=voyage \
  --max-emails=1000

# Tutte le email
python -m agata.kb generate-embeddings \
  --provider=voyage
```

**Performance attese**: ~10-20 email/secondo (rate limit API)

Output:
```
============================================================
AGATA Knowledge Base - Embedding Generator
============================================================

Initializing services (provider: voyage)...
Found 1,234 parsed emails
Already embedded: 0 emails

Generating embeddings (batch size: 50)...
------------------------------------------------------------
  Processed: 10, Skipped: 0, Errors: 0
  Processed: 20, Skipped: 0, Errors: 0
...

============================================================
EMBEDDING GENERATION COMPLETE
============================================================
Successfully processed: 1,234
Skipped (already embedded): 0
Errors: 0

Total vectors in store: 1,234

Vectors by source:
  mbox: 1,234

✓ Embeddings generated successfully!
```

### Step 5: Ricerca Semantica

```bash
# Ricerca base
python -m agata.kb search "Gaia DR3 configuration" --provider=voyage

# Top 10 risultati
python -m agata.kb search "TESS data download" --provider=voyage --top-k=10

# Query in italiano
python -m agata.kb search "come configurare catalogo TESS" --provider=voyage
```

Output esempio:
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
   From: Jane Smith <jane@example.com>
   Date: 2024-02-20T14:30:00
   Label: Important

...
```

---

## 5. Monitoraggio Utilizzo

### Controlla utilizzo free tier

Dashboard Voyage AI: https://dash.voyageai.com/usage

- **100M tokens/mese** = ~50,000-100,000 email
- **Reset**: Primo giorno del mese
- **Costo dopo free tier**: ~$0.10 per 1M tokens

### Stima utilizzo

```bash
# Mostra statistiche knowledge base
python -m agata.kb status
```

Output:
```
Total emails indexed: 1,234
Last updated: 2026-01-31T15:45:00

Emails by label:
  INBOX                   856 emails
  Sent                    234 emails
  Important               144 emails
```

**Stima tokens**: ~1,234 email × 500 tokens = ~617,000 tokens (~0.6% del free tier)

---

## 6. Comandi Utili

```bash
# Status generale
python -m agata.kb status

# Aggiorna database
python -m agata.kb update-db-status

# Genera embeddings per nuove email
python -m agata.kb parse-mbox --mbox-file=new_emails.mbox
python -m agata.kb generate-embeddings --provider=voyage

# Ricerca
python -m agata.kb search "query" --provider=voyage --top-k=5
```

---

## 7. Troubleshooting

### "VOYAGE_API_KEY environment variable not set"

```bash
# Verifica se è impostata
echo $VOYAGE_API_KEY

# Se vuota, esporta di nuovo
export VOYAGE_API_KEY=pa-TUA_CHIAVE
```

### "Rate limit exceeded"

Voyage free tier ha rate limit. Se vedi questo errore:
- Attendi 1 minuto
- Usa `--batch-size=10` per rallentare
- Oppure processa in più sessioni

### "Invalid API key"

Verifica che la chiave sia corretta:
```bash
echo $VOYAGE_API_KEY  # Deve iniziare con 'pa-'
```

Se sbagliata, ricopia da dashboard Voyage AI.

### Embeddings già esistenti non processati

Se hai già generato embeddings con sentence-transformers e vuoi passare a Voyage:

```bash
# Pulisci vector store Redis
redis-cli FLUSHDB  # ⚠️ Cancella TUTTI i dati Redis

# Rigenera con Voyage
python -m agata.kb generate-embeddings --provider=voyage
```

---

## 8. Confronto con Sentence Transformers

| Feature | Sentence Transformers | Voyage AI |
|---------|----------------------|-----------|
| **Costo** | 💚 GRATIS | 💛 Free tier (100M tok/mese) |
| **Qualità** | ⭐⭐⭐ Buona | ⭐⭐⭐⭐⭐ Eccellente |
| **Velocità** | 🐢 1-2 sec/email (CPU) | 🚀 0.05-0.1 sec/email |
| **Offline** | ✅ Sì | ❌ No (richiede internet) |
| **Setup** | Medio (~500MB download) | Facile (solo API key) |
| **Italiano** | ✅ Supportato | ✅ Supportato |
| **Dimensioni** | 384 | 1024 |

**Quando usare Voyage AI**:
- ✅ Vuoi massima qualità
- ✅ Hai internet stabile
- ✅ Hai <50,000 email (free tier)

**Quando usare Sentence Transformers**:
- ✅ Vuoi privacy totale (offline)
- ✅ Nessun limite di utilizzo
- ✅ Non vuoi dipendere da API esterne

---

## 9. Prossimi Step

Dopo aver configurato Voyage AI:

1. ✅ Parse MBOX files
2. ✅ Genera embeddings
3. ✅ Test ricerca semantica
4. 🔜 **Implementa UI web** (tab "Knowledge Base")
5. 🔜 **API endpoints** (`/api/kb/search`, `/api/kb/ask`)
6. 🔜 **RAG con Claude** (Q&A intelligente)
7. 🔜 **Microsoft Teams integration**

---

## Support

- **Voyage AI Docs**: https://docs.voyageai.com/
- **Dashboard**: https://dash.voyageai.com/
- **Support**: support@voyageai.com

---

**Pronto per iniziare!** 🚀

Modifica `~/.bashrc` con la tua vera API key, poi esegui il workflow sopra.
