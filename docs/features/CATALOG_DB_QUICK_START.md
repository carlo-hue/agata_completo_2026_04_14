# Catalog Database Persistence - Quick Start Guide

**TL;DR**: Catalog queries now save to MySQL and reuse results for 180 days. Instant queries instead of 10-second Vizier timeouts.

---

## How It Works

1. **First Query**: Call Vizier, save to DB, display to user (10 seconds)
2. **Second Query** (same star): Retrieve from DB, instant response (100ms)
3. **After 180 days**: Refetch from Vizier automatically

---

## Key Features

### Smart Filtering
Only **configured attributes** (from CSV) are saved to DB.
- Prevents database bloat
- Respects your configuration

### TTL Management
Default cache lifetime: **180 days**
- Automatic expiration check on every query
- Manual refresh available (superuser: add `refresh=true`)

### Manual Refresh (Superuser Only)
```bash
POST /agata/catalog/api/query
{
    "gaia_id": "6917570577208762624",
    "context": "identificativi",
    "refresh": true    # Force Vizier query, bypass cache
}
```

---

## Database Table

New table: `agata_catalog_attributes`

| Column | Type | Purpose |
|--------|------|---------|
| gaia_id | VARCHAR(50) | Star ID (part of key) |
| catalog_id | VARCHAR(100) | Catalog name (part of key) |
| attribute_name | VARCHAR(100) | Attribute to save (part of key) |
| value | VARCHAR(500) | Stored value from Vizier |
| contesto | VARCHAR(100) | Context from CSV |
| reference | TEXT | Reference from CSV |
| ra_deg | DOUBLE | Star RA (for validation) |
| dec_deg | DOUBLE | Star Dec (for validation) |
| distance_arcsec | FLOAT | Match quality |
| fetched_at | DATETIME | When queried |
| expires_at | DATETIME | Cache expiration date |

---

## Code Integration Points

### Using DBCacheRepo Directly

```python
from agata.catalog.repositories.db_cache_repo import DBCacheRepo

repo = DBCacheRepo()

# Get single attribute
value = repo.get(
    gaia_id="6917570577208762624",
    catalog_id="I/305/out",
    attribute_name="GSC2.3"
)

# Get all attributes for a catalog
attrs = repo.get_all_attributes(
    gaia_id="6917570577208762624",
    catalog_id="I/305/out"
)
# Returns: {"GSC2.3": "GSC2.3 00123456", "Vmag": "9.87"}

# Get cache stats
stats = repo.get_stats(gaia_id="6917570577208762624")
# Returns: {total: 5, active: 5, expired: 0, catalogs: 2}

# Invalidate cache (force refetch)
count = repo.invalidate(gaia_id="6917570577208762624")
```

### QueryService with DB Cache

The `QueryService` automatically:
1. Checks in-memory cache first
2. On miss: fetches from Vizier
3. Filters to configured attributes (from CSV)
4. Saves to DB with 180-day TTL
5. Returns to user

No code changes needed - it's automatic!

---

## API Response

**Before** (every query hit Vizier):
```json
{
    "from_cache": false,
    "matches_count": 1,
    "payload": {...},
    "fetched_at": "2026-02-13T10:30:00"
}
```

**After** (DB saves results):
```json
{
    "from_cache": false,    // Still false (from Vizier)
    "matches_count": 1,
    "payload": {...},
    "fetched_at": "2026-02-13T10:30:00",
    "expires_at": "2026-08-13T10:30:00"  // 180 days later
}
```

**Next query** (within 180 days):
```json
{
    "from_cache": true,      // Now true (from DB, not Vizier)
    "matches_count": 1,
    "payload": {...},
    "fetched_at": "2026-02-13T10:30:00"
}
```

---

## Performance

| Query | Time | Source |
|-------|------|--------|
| 1st (cold) | ~10 sec | Vizier |
| 2nd (same session) | ~50 ms | In-memory cache |
| 3rd (after restart) | ~100 ms | DB cache |
| 4th (180+ days later) | ~10 sec | Vizier (expired) |

---

## Testing

### Quick Test: Save and Retrieve

```python
from agata.catalog.repositories.db_cache_repo import DBCacheRepo

repo = DBCacheRepo()

# Save
repo.save(
    gaia_id="test_123",
    catalog_id="I/305/out",
    attribute_name="GSC2.3",
    value="GSC2.3 00000001",
    context="identificativi",
    reference="Test reference",
    ra_deg=45.5,
    dec_deg=44.5,
    distance_arcsec=2.3,
    ttl_days=180
)

# Retrieve
value = repo.get("test_123", "I/305/out", "GSC2.3")
print(value)  # "GSC2.3 00000001"
```

### Query Service Integration Test

```python
from agata.catalog.flask_routes import _query_service, _db_cache_repo

# Verify integration
print(_query_service.db_cache is not None)  # True
print(_db_cache_repo is _query_service.db_cache)  # True
```

---

## Troubleshooting

### Cache Not Saving

Check:
```bash
# Verify table exists
mysql -u aaaat01 -p catalogo -e "SELECT * FROM agata_catalog_attributes LIMIT 1;"

# Check for errors in app logs
# Look for: "[Catalog] Error saving to DB cache:"
```

### Clear Cache (Manual)

```python
from agata.catalog.repositories.db_cache_repo import DBCacheRepo

repo = DBCacheRepo()

# Invalidate all for a star
repo.invalidate(gaia_id="6917570577208762624")

# Invalidate specific catalog
repo.invalidate(gaia_id="6917570577208762624", catalog_id="I/305/out")
```

### Check Expiration

```python
from agata.auth_models import CatalogAttribute
from agata.db import SessionLocal

session = SessionLocal()
entry = session.query(CatalogAttribute).filter_by(
    gaia_id='...',
    catalog_id='...',
    attribute_name='...'
).first()

print(f"Expired: {entry.is_expired}")
print(f"Age: {entry.age_days} days")
print(f"Expires: {entry.expires_at}")
```

---

## Configuration

### Change TTL (Default: 180 days)

Edit `agata/catalog/services/query_service.py`, line 492:
```python
'ttl_days': 180  # Change this value
```

### Disable DB Cache

Set `db_cache_repo=None` in `agata/catalog/flask_routes.py`:
```python
_query_service = QueryService(
    registry_repo=_registry_repo,
    cache_repo=_cache_repo,
    db_cache_repo=None,  # No persistent cache
    events_repo=_events_repo
)
```

---

## Files to Know

| File | Purpose |
|------|---------|
| `agata/auth_models/catalog_attribute.py` | Database model |
| `agata/catalog/repositories/db_cache_repo.py` | Cache repository |
| `agata/catalog/services/query_service.py` | Integration logic |
| `agata/catalog/flask_routes.py` | Flask setup |
| `docs/features/CATALOG_DATABASE_PERSISTENCE.md` | Complete reference |

---

## Summary

✅ **Persistent caching** works automatically
✅ **Smart filtering** saves only configured attributes
✅ **Fast queries** after first fetch (100ms vs 10s)
✅ **TTL management** automatic (180 days)
✅ **Zero changes** to frontend or API format

**No user action needed** - catalog queries automatically cache results to DB!

---

For detailed information, see: `docs/features/CATALOG_DATABASE_PERSISTENCE.md`
