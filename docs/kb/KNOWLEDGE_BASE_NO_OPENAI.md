# Knowledge Base - Guida Senza OpenAI

Hai 3 opzioni per generare embeddings **senza OpenAI**:

## ✅ Opzione 1: Sentence Transformers (CONSIGLIATA)

**Vantaggi:**
- ✅ Completamente GRATUITO
- ✅ Nessuna API key necessaria
- ✅ Funziona offline (locale)
- ✅ Supporta italiano (modello multilingue)
- ✅ Privacy totale (nessun dato inviato a terzi)

**Svantaggi:**
- ⚠️ Più lento (CPU, non ottimizzato come API cloud)
- ⚠️ Qualità embeddings leggermente inferiore a OpenAI
- ⚠️ Richiede ~500MB disco per scaricare il modello

### Setup

```bash
# Installa dipendenze
pip install sentence-transformers

# Genera embeddings (GRATIS, locale)
python -m agata.kb generate-embeddings --provider=sentence-transformers

# Cerca (GRATIS, locale)
python -m agata.kb search "Gaia DR3 configuration" --provider=sentence-transformers
```

**Nessuna API key necessaria!** 🎉

---

## Opzione 2: Voyage AI (Free Tier)

**Vantaggi:**
- ✅ Raccomandato da Anthropic
- ✅ Free tier: **100M tokens/mese** (circa 50,000-100,000 email)
- ✅ Qualità embeddings ottima (paragonabile a OpenAI)
- ✅ Veloce (API cloud)

**Svantaggi:**
- ⚠️ Richiede API key
- ⚠️ Limite free tier (dopo 100M tokens diventa a pagamento)

### Setup

```bash
# 1. Ottieni API key gratis
# Vai su: https://dash.voyageai.com/
# Crea account e copia la API key

# 2. Configura API key
export VOYAGE_API_KEY=pa-xxxxxxxxxxxxx

# 3. Installa dipendenza
pip install voyageai

# 4. Genera embeddings
python -m agata.kb generate-embeddings --provider=voyage

# 5. Cerca
python -m agata.kb search "TESS photometry" --provider=voyage
```

**Costo dopo free tier**: ~$0.10 per 1M tokens (simile a OpenAI)

---

## Opzione 3: OpenAI (Se hai API key)

Se hai già accesso a OpenAI API:

```bash
export OPENAI_API_KEY=sk-...
python -m agata.kb generate-embeddings --provider=openai
python -m agata.kb search "query" --provider=openai
```

**Costo**: ~$0.00002 per email

---

## Confronto Provider

| Provider | Costo | Qualità | Velocità | Offline | Setup |
|----------|-------|---------|----------|---------|-------|
| **sentence-transformers** | 💚 GRATIS | ⭐⭐⭐ | 🐢 Lento | ✅ Sì | Facile |
| **Voyage AI** | 💛 Free tier | ⭐⭐⭐⭐⭐ | 🚀 Veloce | ❌ No | Facile |
| **OpenAI** | 💰 Pagamento | ⭐⭐⭐⭐⭐ | 🚀 Veloce | ❌ No | Facile |

---

## Setup Completo con Sentence Transformers (GRATIS)

### 1. Installa dipendenze

```bash
cd /var/www/astrogen
pip install sentence-transformers
```

### 2. Migrazione database

```bash
sudo mysql catalogo < migrations/create_kb_tables.sql
```

### 3. Carica MBOX files

```bash
mkdir -p kb_data/mbox_raw
# Carica qui i file .mbox da Google Takeout
```

### 4. Parse emails

```bash
python -m agata.kb parse-mbox --mbox-dir=kb_data/mbox_raw/
```

### 5. Genera embeddings (LOCALE, GRATIS)

```bash
# Prima volta: scarica modello (~500MB, una tantum)
python -m agata.kb generate-embeddings \
  --provider=sentence-transformers \
  --max-emails=100  # Test con 100 email

# Se funziona, processa tutte
python -m agata.kb generate-embeddings \
  --provider=sentence-transformers
```

**Tempo stimato**: ~1-2 secondi per email su CPU (più veloce su GPU)

### 6. Cerca

```bash
python -m agata.kb search "Gaia DR3" --provider=sentence-transformers
python -m agata.kb search "come scaricare dati TESS" --provider=sentence-transformers --top-k=10
```

---

## Performance Attese

### Sentence Transformers (locale)

- **Prima esecuzione**: ~2-3 minuti (download modello)
- **Embedding generation**: ~1-2 sec/email su CPU
- **Search**: ~100ms per query
- **Storage**: ~2KB/email (embeddings 384 dimensioni)

### Voyage AI (cloud)

- **Embedding generation**: ~0.1 sec/email
- **Search**: ~50ms per query
- **Storage**: ~4KB/email (embeddings 1024 dimensioni)

---

## Domande Frequenti

### Posso mescolare provider?

**NO.** Devi usare lo stesso provider per:
1. Generazione embeddings (`generate-embeddings`)
2. Ricerca (`search`)

Se cambi provider, devi rigenerare tutti gli embeddings.

### Quale scegliere?

- **Privacy/offline/gratis**: sentence-transformers
- **Qualità massima + free tier**: Voyage AI
- **Già hai OpenAI**: openai

### Sentence Transformers funziona in italiano?

Sì! Il modello `paraphrase-multilingual-MiniLM-L12-v2` supporta 50+ lingue incluso italiano.

### Quanto spazio su disco?

- **Modello sentence-transformers**: ~500MB (una volta)
- **Embeddings cache**: ~2KB per email
- **10,000 email**: ~20MB embeddings + 500MB JSON parsed

---

## Troubleshooting

### "No module named 'sentence_transformers'"

```bash
pip install sentence-transformers
```

### Download modello lento

Prima volta scarica ~500MB. Usa connessione veloce o pazienza ☕

### "Out of memory"

Sentence Transformers usa CPU/RAM. Se hai tante email, processa in batch:

```bash
python -m agata.kb generate-embeddings \
  --provider=sentence-transformers \
  --max-emails=1000 \
  --batch-size=10
```

### Search restituisce risultati strani

Assicurati di usare stesso provider per generate + search:

```bash
# ❌ SBAGLIATO
python -m agata.kb generate-embeddings --provider=sentence-transformers
python -m agata.kb search "query" --provider=voyage

# ✅ CORRETTO
python -m agata.kb generate-embeddings --provider=sentence-transformers
python -m agata.kb search "query" --provider=sentence-transformers
```

---

## Next Steps

Dopo aver testato il sistema con sentence-transformers:

1. ✅ Genera embeddings per tutte le email
2. ✅ Testa ricerca semantica
3. 🔜 Implementa UI web (prossimo step)
4. 🔜 Aggiungi Microsoft Teams integration
5. 🔜 RAG con Claude per Q&A

---

**La mia raccomandazione per te: Sentence Transformers**

È gratis, funziona offline, supporta italiano, e non richiede API key. Perfetto per iniziare! 🚀
