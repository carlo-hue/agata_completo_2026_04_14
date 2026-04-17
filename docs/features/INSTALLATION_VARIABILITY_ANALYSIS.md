# Installazione Analisi Comparativa Stelle Variabili

## Overview

Questa guida descrive l'installazione e configurazione del modulo di analisi comparativa stelle variabili per AGATA.

---

## Prerequisiti

- Python 3.8+
- MySQL/MariaDB con database AGATA
- Redis Server 5.0+ (opzionale ma raccomandato per production)

---

## Step 1: Installazione Dipendenze Python

```bash
cd /var/www/astrogen

# Installa nuove dipendenze
pip install -r requirements.txt

# Verifica installazione
python -c "import astroquery, redis, flask_caching, lightkurve, matplotlib; print('OK')"
```

**Dipendenze aggiunte**:
- `astroquery==0.4.8` - Query Gaia TAP e cataloghi astronomici
- `redis==5.0.1` - Client Redis per caching
- `Flask-Caching==2.3.0` - Wrapper Flask per cache
- `lightkurve==2.5.0` - Gestione light curves
- `matplotlib==3.9.4` - Generazione plot

---

## Step 2: Installazione e Configurazione Redis

### Ubuntu/Debian

```bash
# Install Redis Server
sudo apt update
sudo apt install redis-server

# Verifica versione (minimo 5.0)
redis-server --version

# Start e enable al boot
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Test connessione
redis-cli ping
# Output atteso: PONG
```

### Configurazione Redis (Opzionale)

Edita `/etc/redis/redis.conf`:

```conf
# Bind solo localhost (sicurezza)
bind 127.0.0.1 ::1

# Password (raccomandato per production)
requirepass your_strong_password_here

# Max memory (es. 512MB per cache)
maxmemory 512mb
maxmemory-policy allkeys-lru

# Persistence (opzionale, cache può essere volatile)
save ""
appendonly no
```

Riavvia Redis dopo modifiche:

```bash
sudo systemctl restart redis-server
```

---

## Step 3: Configurazione Ambiente

Il file `.env` è già configurato con:

```bash
REDIS_URL=redis://localhost:6379/0
```

### Se hai configurato password Redis:

```bash
# In .env
REDIS_URL=redis://:your_strong_password_here@localhost:6379/0
```

### Verifica configurazione:

```bash
# Test connessione con password
redis-cli -a your_strong_password_here ping
```

---

## Step 4: Restart Flask Application

```bash
# Se usi systemd service
sudo systemctl restart astrogen-app

# Oppure manualmente
cd /var/www/astrogen
python app.py
```

Verifica logs per confermare cache inizializzato:

```bash
tail -f /var/log/astrogen/app.log | grep -i cache
```

Output atteso:
```
INFO: Flask-Caching initialized with Redis backend
```

---

## Step 5: Test API Endpoints

### Test 1: Health Check

```bash
curl https://app-test.astrogen.it/health
# Output: {"status": "ok", "service": "AGATA"}
```

### Test 2: Search Analogues (richiede autenticazione)

```bash
# Login prima per ottenere session cookie
# Poi testa endpoint:

curl -X POST https://app-test.astrogen.it/api/projects/1/variability/search-analogues \
  -H "Content-Type: application/json" \
  -H "Cookie: session=YOUR_SESSION_COOKIE" \
  -d '{
    "periods": [0.5, 1.0],
    "top_n": 5
  }'
```

**Response attesa**:
```json
{
  "success": true,
  "project_id": 1,
  "gaia_id": "Gaia DR3 XXXXX",
  "analogues_count": 5,
  "analogues": [...]
}
```

### Test 3: Phased Comparison

```bash
curl -X POST https://app-test.astrogen.it/api/projects/1/variability/phased-comparison \
  -H "Content-Type: application/json" \
  -H "Cookie: session=YOUR_SESSION_COOKIE" \
  -d '{
    "periodo": 0.5,
    "analogue_gaia_ids": ["1234567891"],
    "catalog": "ASAS-SN"
  }'
```

**Response attesa**:
```json
{
  "success": true,
  "plot": "data:image/png;base64,iVBORw0KGgo...",
  "lc_count": 2
}
```

---

## Troubleshooting

### Errore: `ConnectionRefusedError: [Errno 111] Connection refused`

**Causa**: Redis non attivo o URL errato

**Soluzione**:
```bash
# Verifica Redis
sudo systemctl status redis-server

# Se non attivo
sudo systemctl start redis-server

# Test connessione
redis-cli ping
```

### Errore: `NOAUTH Authentication required`

**Causa**: Redis ha password ma `.env` non la specifica

**Soluzione**:
```bash
# Aggiungi password in .env
REDIS_URL=redis://:PASSWORD@localhost:6379/0
```

### Errore: `ModuleNotFoundError: No module named 'astroquery'`

**Causa**: Dipendenze non installate

**Soluzione**:
```bash
pip install -r requirements.txt
```

### Errore: `No lightcurve data for Gaia XXX`

**Causa**: Dati non ancora importati nel database

**Soluzione**:
1. Importa dati da ASAS-SN: `POST /api/catalogs/asassn/auto/download-data`
2. Verifica tabella `Cataloghi_esterni` contiene dati per il `gaia_id`

```sql
SELECT COUNT(*) FROM Cataloghi_esterni WHERE gaia_id = 'Gaia DR3 XXXXX';
```

---

## Monitoring

### Redis Memory Usage

```bash
# Connetti a Redis
redis-cli

# Info memory
INFO memory

# Key count
DBSIZE

# Lista keys cache (attenzione: KEYS * è slow in production)
KEYS analogues:*
```

### Flask Logs

```bash
# Segui logs real-time
tail -f /var/log/astrogen/app.log

# Filtra cache events
grep -i "cache" /var/log/astrogen/app.log
```

---

## Performance Tuning

### Redis Max Memory

Per evitare OOM, limita memoria Redis:

```conf
# In /etc/redis/redis.conf
maxmemory 512mb
maxmemory-policy allkeys-lru
```

### Cache TTL

Modifica TTL cache in `app.py`:

```python
# Default: 3600s (1h)
app.config['CACHE_DEFAULT_TIMEOUT'] = 7200  # 2h
```

### Gaia Query Limit

Limita risultati Gaia per performance:

```python
# In variability_analysis.py
MAX_CANDIDATES = 50  # Default: 100
```

---

## Backup & Restore (Opzionale)

Se Redis persistence abilitato:

```bash
# Backup Redis
redis-cli SAVE
sudo cp /var/lib/redis/dump.rdb /backup/redis_$(date +%Y%m%d).rdb

# Restore
sudo systemctl stop redis-server
sudo cp /backup/redis_YYYYMMDD.rdb /var/lib/redis/dump.rdb
sudo chown redis:redis /var/lib/redis/dump.rdb
sudo systemctl start redis-server
```

---

## Documentazione API Completa

Vedi: [VARIABILITY_ANALYSIS_README.md](agata/admin/services/VARIABILITY_ANALYSIS_README.md)

---

## Support

Per issues o feature requests:
- Email: info@astrogen.it
- Logs: `/var/log/astrogen/app.log`

---

**Installazione completata!** 🎉

Il sistema di analisi comparativa stelle variabili è ora operativo nell'admin panel del progetto.
