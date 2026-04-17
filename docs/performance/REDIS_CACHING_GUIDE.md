# Redis Caching Implementation Guide

## Implementazioni Attuali

### 1. **Ricerca Stelle Analoghe VSX** ✅
**File**: `agata/admin/routes/project_detail.py:560`

```python
cache_key = f"analogues:{project.gaia_id}:{','.join(map(str, periodi[:3]))}"
analogues = cache.get(cache_key)

if analogues is None:
    analogues = trova_stelle_analoghe(...)
    cache.set(cache_key, analogues, timeout=3600)  # 1 ora
```

**Benefici**:
- Query VSX API (2-3 sec) → Cache hit (50ms)
- TTL: 1 ora (VSX è quasi statico)

---

## Implementazioni Consigliate Future

### 2. **Cache Query Gaia TAP**

**Where**: `agata/admin/routes/catalogs/common.py:resolve_gaia_coordinates`

```python
from agata.cache import cache

def resolve_gaia_coordinates(source_id: str):
    cache_key = f"gaia_coords:{source_id}"
    result = cache.get(cache_key)

    if result is None:
        # Query Gaia TAP (3-5 sec)
        result = _query_gaia_tap(source_id)
        cache.set(cache_key, result, timeout=86400)  # 24 ore

    return result
```

**Benefici**:
- Gaia DR3 è statico → cache valida per giorni
- Riduce carico su Gaia TAP (rate limits)

---

### 3. **Cache Lightcurve Query DB**

**Where**: `agata/admin/services/variability_analysis.py:get_lightcurve_from_db`

```python
def get_lightcurve_from_db(db, gaia_id: str, catalog: str = None):
    cache_key = f"lightcurve:{gaia_id}:{catalog or 'all'}"
    result = cache.get(cache_key)

    if result is None:
        # Query DB (può essere lenta su 100k+ punti)
        result = _fetch_from_db(db, gaia_id, catalog)
        cache.set(cache_key, result, timeout=3600)  # 1 ora

    return result
```

**Benefici**:
- Query su tabelle enormi (Cataloghi_esterni) cachate
- Lightcurve non cambia → cache sicura

---

### 4. **Cache Preview Import Cataloghi**

**Where**: `agata/admin/routes/catalogs/*.py`

```python
# Durante preview import
cache_key = f"import_preview:{import_id}"
cache.set(cache_key, {
    'gaia_id': gaia_id,
    'catalogs': {'TESS': {...}, 'ZTF': {...}},
    'total_points': 15000
}, timeout=600)  # 10 minuti

# User conferma import → read from cache
preview_data = cache.get(cache_key)
```

**Benefici**:
- Evita ri-query se user torna indietro nel wizard
- TTL breve (10 min) perché è transitorio

---

### 5. **Session Data Cache (alternativa DB)**

**Where**: `agata/auth_models/user_session.py`

```python
# Invece di scrivere in DB per ogni richiesta
cache.set(f'session:{session_id}', session_data, timeout=3600)

# Read
session = cache.get(f'session:{session_id}')
```

**Benefici**:
- Meno write su DB (performance)
- Session data è perfetto per cache volatili

---

### 6. **Feature Flags**

**Where**: `agata/admin/routes/*.py` o nuovo file `feature_flags.py`

```python
def is_feature_enabled(feature_name: str) -> bool:
    """Check se feature è abilitata senza restart app"""
    enabled = cache.get(f'feature:{feature_name}')
    if enabled is None:
        # Default da DB o config
        enabled = SystemConfig.get(feature_name, default=False)
        cache.set(f'feature:{feature_name}', enabled, timeout=300)
    return enabled

# Usage
if is_feature_enabled('experimental_vsx_match'):
    # Nuova feature
```

**Benefici**:
- A/B testing senza deploy
- Rollout graduali

---

### 7. **Rate Limiting**

**Where**: Nuovo decorator in `agata/admin/decorators.py`

```python
from functools import wraps
from flask import request, jsonify

def rate_limit(max_per_minute=60):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            key = f'rate_limit:{request.remote_addr}:{f.__name__}'
            count = cache.get(key) or 0

            if count >= max_per_minute:
                return jsonify({'error': 'Rate limit exceeded'}), 429

            cache.set(key, count + 1, timeout=60)
            return f(*args, **kwargs)
        return wrapped
    return decorator

# Usage
@rate_limit(max_per_minute=10)
def expensive_api_endpoint():
    ...
```

---

### 8. **Background Job Status**

**Where**: Future async import jobs

```python
# Job worker
cache.set(f'job:{job_id}', {
    'status': 'running',
    'progress': 45,
    'current_catalog': 'ZTF',
    'points_imported': 5000,
    'total_estimated': 15000
}, timeout=7200)

# Frontend polls
GET /api/import-jobs/{job_id}/status
→ cache.get(f'job:{job_id}')
```

---

## Best Practices

### TTL Guidelines

| Tipo Dato | TTL | Rationale |
|-----------|-----|-----------|
| Gaia DR3 data | 24h - 7d | Catalogo statico |
| VSX analogues | 1h - 6h | Aggiornamenti rari |
| Lightcurve DB | 1h | Dati non cambiano spesso |
| Import preview | 10min | Dati transitori |
| Session data | 30min - 1h | Expire con inattività |
| Feature flags | 5min | Aggiornamenti frequenti |
| Rate limiting | 1min | Reset veloce |

### Key Naming Convention

```
{namespace}:{entity_type}:{identifier}[:{variant}]

Examples:
- analogues:1234567890:0.999,1.001,0.998
- gaia_coords:1234567890
- lightcurve:1234567890:ZTF
- session:abc123def456
- feature:experimental_vsx
- rate_limit:192.168.1.1:api_search
- job:import_567:status
```

### Invalidation Strategies

1. **TTL-based** (preferito per dati quasi-statici)
2. **Manual invalidate** (quando dati cambiano):
   ```python
   cache.delete(f'lightcurve:{gaia_id}:all')
   ```
3. **Pattern-based clear** (admin utility):
   ```python
   # Clear all analogues caches
   keys = cache._client.keys('analogues:*')
   for key in keys:
       cache.delete(key)
   ```

---

## Monitoring Redis

### Check Usage

```bash
# Connect to Redis
redis-cli

# Info generale
INFO

# Statistiche memoria
INFO memory

# Chiavi presenti
KEYS *

# Chiavi per pattern
KEYS analogues:*
KEYS lightcurve:*

# Monitor real-time
MONITOR
```

### Performance Metrics

```python
# Nel codice
import time

start = time.time()
result = cache.get(cache_key)
if result is None:
    result = expensive_query()
    cache.set(cache_key, result, timeout=3600)
    logger.info(f"Cache MISS: {cache_key}, query took {time.time() - start:.2f}s")
else:
    logger.info(f"Cache HIT: {cache_key}, took {time.time() - start:.4f}s")
```

---

## Configuration

**File**: `app.py`

```python
app.config['CACHE_TYPE'] = 'redis'
app.config['CACHE_REDIS_URL'] = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
app.config['CACHE_DEFAULT_TIMEOUT'] = 3600  # 1 ora default
app.config['CACHE_KEY_PREFIX'] = 'agata_'  # Namespace per evitare collisioni
```

**File**: `.env`

```bash
REDIS_URL=redis://localhost:6379/0
```

---

## Eviction Policy

Redis configurato con `maxmemory-policy allkeys-lru`:
- Quando memoria piena, rimuove chiavi Least Recently Used
- Perfetto per cache applicativa

Check config:
```bash
redis-cli CONFIG GET maxmemory-policy
```

---

**Last Updated**: 2026-01-31
**Redis Version**: 7.0.15
**Flask-Caching Version**: 2.3.1
