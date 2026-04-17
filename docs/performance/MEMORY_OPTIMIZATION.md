# Ottimizzazione Memoria AGATA

## Problema
Il processo Flask occupa ~1.2GB di RAM principalmente a causa di:
1. Modello sentence-transformers (~384MB)
2. Librerie ML/scientifiche (numpy, scipy, etc)
3. Flask + dipendenze

## Soluzioni Implementate

### 1. Singleton per EmbeddingService ✅
- Il modello sentence-transformers viene caricato solo una volta
- Riutilizzato per tutte le query successive
- Risparmio: evita ricaricamenti multipli del modello

## Ottimizzazioni Raccomandate

### 2. Lazy Loading del Modello
Il modello viene caricato solo quando necessario (già implementato con singleton).

### 3. Ridurre Worker Gunicorn (se in produzione)
```bash
# In produzione, usa:
gunicorn --workers 2 --threads 2 --worker-class=gthread \
  --max-requests 1000 --max-requests-jitter 50 \
  --timeout 120 --bind 0.0.0.0:5000 "agata:create_app()"
```

**Nota**: Con 2 worker, ogni worker avrà il suo modello in memoria (~800MB x 2 = 1.6GB totale)

### 4. Servizio Separato per Embeddings (opzionale)
Creare un microservizio dedicato per gli embedding:

```python
# embedding_server.py
from flask import Flask, request, jsonify
from agata.kb.services.embedding_service import EmbeddingService

app = Flask(__name__)
embedding_service = EmbeddingService(provider='sentence-transformers')

@app.route('/embed', methods=['POST'])
def embed():
    text = request.json.get('text')
    embedding = embedding_service.embed(text)
    return jsonify({'embedding': embedding})

if __name__ == '__main__':
    app.run(port=5001)
```

Poi da agata chiamare via HTTP invece di caricare il modello in-process.

### 5. Usare Modello Più Piccolo (trade-off qualità)
Alternative più leggere a `paraphrase-multilingual-MiniLM-L12-v2`:
- `paraphrase-MiniLM-L3-v2` (solo inglese, 61MB, 384 dim)
- `all-MiniLM-L6-v2` (solo inglese, 80MB, 384 dim)

Cambiare in `agata/kb/services/embedding_service.py` linea 82:
```python
self.client = SentenceTransformer('all-MiniLM-L6-v2')  # Più piccolo
```

**Trade-off**: Modelli più piccoli = qualità ricerca leggermente inferiore

### 6. Cache Redis per Embedding
Gli embedding delle query vengono già cachati su disco, ma potresti usare Redis per cache in-memory:
- Già implementato in `EmbeddingService.embed()`
- Cache dir: `/var/www/astrogen/kb_data/embeddings`

### 7. Monitoraggio Memoria
```bash
# Controlla memoria in tempo reale
watch -n 2 'ps aux | grep python | grep -v grep'

# Log memoria Flask
# Aggiungi in agata/__init__.py:
import psutil
import os

@app.before_request
def log_memory():
    process = psutil.Process(os.getpid())
    mem = process.memory_info().rss / 1024 / 1024  # MB
    if mem > 800:
        app.logger.warning(f"High memory usage: {mem:.0f}MB")
```

## Configurazione Attuale
- **Modalità**: Development (`flask run`)
- **Worker**: 1 processo
- **Memoria**: ~1.2GB
- **Embedding Model**: paraphrase-multilingual-MiniLM-L12-v2 (384MB)

## Raccomandazioni Immediate

1. ✅ **Singleton già implementato** - il modello viene caricato una sola volta
2. ⚠️ **Limita query KB** - usa solo quando necessario
3. 💡 **Considera modello più piccolo** se 1.2GB è troppo per il server
4. 🔧 **In produzione** usa max 2 worker Gunicorn invece di auto-scaling

## Test Memoria
```bash
# Prima query (carica modello)
curl -X POST http://localhost:5000/agata/admin/api/projects/13/kb-query \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}' \
  --cookie "session=..."

# Controlla memoria
ps aux | grep python

# Seconda query (riusa modello - nessun aumento memoria)
# Ripeti comando curl...

# Verifica che memoria non aumenta
ps aux | grep python
```

## Link Utili
- Sentence Transformers Models: https://www.sbert.net/docs/pretrained_models.html
- Gunicorn Worker Types: https://docs.gunicorn.org/en/stable/design.html
