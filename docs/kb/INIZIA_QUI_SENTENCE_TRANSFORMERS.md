# Knowledge Base - Quick Start con Sentence Transformers 🚀

Guida rapida per usare il Knowledge Base **100% GRATIS** con Sentence Transformers (nessuna API key, tutto locale).

---

## ✅ Cosa Hai Già

- ✅ 554 email già parsed!
- ✅ Sistema completo implementato
- ✅ Redis funzionante

---

## 🎯 Setup in 3 Comandi

### 1. Installa Sentence Transformers

```bash
pip install sentence-transformers
```

**Nota**: Prima esecuzione scarica modello multilingue (~500MB). Supporta italiano! 🇮🇹

### 2. Genera Embeddings (tutte le 554 email)

```bash
python -m agata.kb generate-embeddings --provider=sentence-transformers
```

**Tempo stimato**: ~10-20 minuti per 554 email (CPU)

### 3. Cerca!

```bash
# Ricerca semantica
python -m agata.kb search "Gaia DR3" --provider=sentence-transformers
python -m agata.kb search "TESS photometry" --provider=sentence-transformers
python -m agata.kb search "come scaricare dati" --provider=sentence-transformers --top-k=10
```

---

## 📊 Comandi Utili

```bash
# Status knowledge base
python -m agata.kb status

# Aggiorna DB status
python -m agata.kb update-db-status

# Help
python -m agata.kb --help
```

---

## 💡 Vantaggi Sentence Transformers

- ✅ **100% GRATIS** (sempre, per sempre)
- ✅ **Nessuna API key** necessaria
- ✅ **Offline** (funziona senza internet dopo download modello)
- ✅ **Privacy totale** (nessun dato inviato a terzi)
- ✅ **Supporta italiano** (modello multilingue)
- ✅ **Qualità buona** (⭐⭐⭐ su 5)

**Svantaggi**:
- ⚠️ Più lento di Voyage AI (ma va bene per 554 email)
- ⚠️ Qualità leggermente inferiore a Voyage/OpenAI

---

## 🔄 Workflow Completo

```
1. Parse MBOX (FATTO! ✅)
   ↓
2. Generate embeddings (Sentence Transformers)
   ↓
3. Search semantica (trova email rilevanti)
   ↓
4. RAG con Cerebras (genera risposte)
```

**Separazione ruoli**:
- **Sentence Transformers**: Embeddings per ricerca semantica
- **Cerebras**: LLM per generare risposte intelligenti

---

## 🧪 Test Rapido

```bash
# Test con 10 email
python -m agata.kb generate-embeddings --provider=sentence-transformers --max-emails=10

# Cerca
python -m agata.kb search "variable stars" --provider=sentence-transformers
```

---

## 📈 Performance Attese

- **Download modello**: ~2-3 minuti (prima volta)
- **Embedding generation**: ~1-2 sec/email (CPU)
- **Ricerca**: ~100-200ms per query
- **Storage**: ~2KB/email (embeddings 384 dimensioni)

**Per 554 email**:
- Tempo totale: ~15-20 minuti
- Storage totale: ~1.1MB embeddings + 500MB modello

---

## ❓ FAQ

### Funziona in italiano?
✅ Sì! Modello `paraphrase-multilingual-MiniLM-L12-v2` supporta 50+ lingue.

### Devo pagare qualcosa?
❌ No, mai. Completamente gratis.

### Serve internet?
Solo per scaricare il modello (~500MB) la prima volta. Dopo funziona offline.

### Posso passare a Voyage AI dopo?
✅ Sì, basta rigenerare embeddings con `--provider=voyage` (ma serve carta).

---

## 🚀 Inizia Ora!

```bash
# Tutto in un comando
pip install sentence-transformers && \
python -m agata.kb generate-embeddings --provider=sentence-transformers && \
python -m agata.kb search "Gaia DR3" --provider=sentence-transformers
```

**Hai finito!** 🎉

---

## 📚 Prossimi Step

Dopo aver testato il sistema base:

1. ✅ Genera embeddings per tutte le 554 email
2. ✅ Testa ricerca semantica
3. 🔜 **Implementa UI web** (tab "Knowledge Base")
4. 🔜 **RAG con Cerebras** (Q&A intelligente)
5. 🔜 **Microsoft Teams integration**

---

**Tutto pronto!** Inizia con `pip install sentence-transformers` 🚀
