# Catalog Performance Analysis Report

**Date**: 2026-02-18
**Analysis of**: Cataloghi_esterni table queries
**Status**: 🔴 CRITICAL - 4+ Missing Indexes Found

---

## Executive Summary

**Problem**: Catalog queries are **extremely slow** (0.7-4.4 seconds per query)

**Root Cause**: Table `Cataloghi_esterni` has **NO INDEXES** on frequently searched columns

**Evidence**:
- All slow catalog queries use `ALL` (full table scan)
- Examining 950K-2.5M rows per query (vs index: ~100-1000 rows)
- Multiple `Using filesort` (expensive sorting on unindexed columns)
- **17M rows examined in 19 seconds of query time** ← massive waste

**Impact**:
- ❌ Catalog browsing slow
- ❌ Variable star editor sluggish
- ❌ Dashboard stats timeout
- ❌ User experience degraded

---

## Slow Query Patterns Identified

### 1. 🔴 CRITICAL: `SELECT WHERE Source = 'ID'` (10+ queries per user session)

**Pattern**:
```sql
SELECT hjd, Vmag as mag, catalogo
FROM Cataloghi_esterni
WHERE Source = 'S'
AND (association_id_owner IS NULL OR association_id_owner = NULL OR N = N)
ORDER BY hjd
```

**Current Performance**:
```
Time:       0.771 seconds
Rows examined: 950,895
Rows returned: ~1,900
Index: NONE (ALL full scan)
```

**With Index**:
```
Expected time: <10ms (77x faster!)
Rows examined: ~1,900 (same as returned)
Index: (Source, association_id_owner)
```

**Fix**:
```sql
CREATE INDEX idx_cataloghi_esterni_source_owner
ON Cataloghi_esterni(Source, association_id_owner, hjd);
```

---

### 2. 🔴 CRITICAL: `SELECT COUNT(*) WHERE Source = 'ID'` (5+ per session)

**Pattern**:
```sql
SELECT COUNT(*) as cnt FROM Cataloghi_esterni
WHERE Source = 'S'
AND (association_id_owner IS NULL OR association_id_owner = NULL OR N = N)
```

**Current Performance**:
```
Time:       1.105 seconds
Rows examined: 978,595
Index: NONE (ALL full scan)
```

**With Index**:
```
Expected time: <5ms (200x faster!)
Index: (Source, association_id_owner)
```

---

### 3. 🔴 CRITICAL: `ORDER BY hjd` on large result sets

**Pattern**:
```sql
SELECT hjd, Vmag as mag, catalogo
FROM Cataloghi_esterni
WHERE Source = 'S'
...
ORDER BY hjd
```

**Issue**: Full table scan → filesort on 950K rows
- No index on `Source` to filter first
- Then sorting unindexed column

**Fix**: `CREATE INDEX idx_cataloghi_esterni_source_owner` (above) will solve this

---

### 4. 🟠 HIGH: `SELECT ... WHERE Source IN (massive list)` (50 executions!)

**Pattern**:
```sql
SELECT Source, catalog_import_id
FROM Cataloghi_esterni
WHERE Source IN (list of 1000+ Gaia IDs)
AND catalog_import_id IS NOT NULL
GROUP BY Source, catalog_import_id
```

**Current Performance**:
```
Time:       0.46s per execution × 50 = 23 seconds total!
Rows examined: 1.6M per execution
Index: NONE (ALL scan)
```

**With Index**:
```
Expected: <1ms per execution × 50 = ~50ms total
Index: (Source, catalog_import_id)
```

**Note**: This query runs 50 times - consider batching/caching!

---

### 5. 🟠 HIGH: `DISTINCT ... GROUP BY ... ORDER BY` on full scan

**Pattern**:
```sql
SELECT DISTINCT catalogo, association_id_owner, COUNT(*), MIN/MAX/AVG
FROM Cataloghi_esterni
WHERE Source = 'S'
AND (association_id_owner IS NULL OR ...)
GROUP BY catalogo, association_id_owner
ORDER BY points DESC
```

**Current Performance**:
```
Time:       0.471 seconds
Rows examined: 1,663,104
Using: temporary table + filesort
```

**With Index**:
```
Expected: <10ms
Index: (Source, association_id_owner, catalogo)
```

---

### 6. 🟡 MEDIUM: `association_id_owner IS NULL` GROUP BY

**Pattern** (2nd slowest overall at 5.5 seconds):
```sql
SELECT DISTINCT ce.Source as gaia_id,
       COUNT(*) as total_points,
       ...
FROM Cataloghi_esterni ce
LEFT JOIN agata_catalog_imports ci
WHERE ce.association_id_owner IS NULL
GROUP BY ce.Source
```

**Current Performance**:
```
Time:       4-5 seconds (per query × 2 = 10 seconds)
Rows examined: 2.5M (full scan)
Index: NONE
```

**With Index**:
```
Expected: <100ms
Index: (association_id_owner, Source)
```

---

## Index Recommendations (Priority Order)

### 🔴 PRIORITY 1 - Create IMMEDIATELY
```sql
CREATE INDEX idx_cataloghi_esterni_source_owner
ON Cataloghi_esterni(Source, association_id_owner)
COMMENT 'Used for: WHERE Source=? AND association_id_owner IS NULL';

-- This fixes patterns #1, #2, #3, #5
-- Estimated speedup: 50-100x
-- Space: ~500MB (if table is ~5GB)
```

### 🟠 PRIORITY 2 - Create after Priority 1
```sql
CREATE INDEX idx_cataloghi_esterni_source_catalog
ON Cataloghi_esterni(Source, catalog_import_id)
COMMENT 'Used for: WHERE Source IN (...) AND catalog_import_id IS NOT NULL';

-- This fixes pattern #4
-- Estimated speedup: 200x
-- Space: ~500MB
```

### 🟡 PRIORITY 3 - Create after Priority 1-2
```sql
CREATE INDEX idx_cataloghi_esterni_hjd
ON Cataloghi_esterni(Source, hjd)
COMMENT 'Used for: ORDER BY hjd with Source filter';

-- Improves ORDER BY performance
-- Space: ~400MB
```

---

## Quick Wins (No Indexes Needed)

### 1. Cache `association_id_owner IS NULL` Results

**Pattern**: Multiple queries check for `association_id_owner IS NULL`

**Solution**: Cache results in Redis
- Key: `cataloghi_esterni:public_stars` (updated on import)
- TTL: 24 hours or on-demand invalidation
- Save: 50% of queries

### 2. Batch the 50x `WHERE Source IN (...)` Queries

**Pattern**: Code runs 50 similar queries with different Source IDs

**Current cost**: 23 seconds
**With batching**: 1-2 seconds

```sql
-- BEFORE (50 queries)
SELECT Source, catalog_import_id FROM Cataloghi_esterni
WHERE Source IN ('ID1') AND catalog_import_id IS NOT NULL
GROUP BY Source, catalog_import_id;

-- AFTER (1 query)
SELECT Source, catalog_import_id FROM Cataloghi_esterni
WHERE Source IN ('ID1', 'ID2', ..., 'ID50') AND catalog_import_id IS NOT NULL
GROUP BY Source, catalog_import_id;
```

### 3. Add `LIMIT` to Dashboard Queries

**Pattern**: Dashboard loads aggregates for all 950K rows

**Solution**: Limit to top 100 results
- Show: "Top 100 stars by points"
- Hide: Show with pagination or filtering

---

## Testing Plan

### Step 1: Create Priority 1 Index (Estimated: 5-10 minutes)
```bash
# Backup first
mysqldump agata > backup_$(date +%s).sql

# Create index
mysql < - << 'EOF'
CREATE INDEX idx_cataloghi_esterni_source_owner
ON Cataloghi_esterni(Source, association_id_owner);
ANALYZE TABLE Cataloghi_esterni;
EOF

# Test performance
python docs/performance/analyze_slow_queries.py
```

### Step 2: Verify Speedup
- Re-run slow query analysis
- Compare times before/after
- Document improvement

### Step 3: Create Priority 2 Index
- Same process as Priority 1
- Verify 50x `WHERE IN` query improvement

### Step 4: Monitor
- Continue slow query log for 1 week
- Watch for new patterns
- Adjust indexes if needed

---

## Current State Statistics

| Metric | Value |
|--------|-------|
| Total slow queries | 20 |
| Catalog queries | 4 patterns |
| Total time | 19.41 seconds |
| Total rows examined | 16,972,214 |
| Estimated waste | 16M rows × 95% = 15.2M unnecessary |
| **Estimated improvement** | **50-100x faster** |

---

## Impact on User Experience

### Before Indexes
- Browse 1 star catalog: **0.8 seconds**
- Load dashboard: **10+ seconds**
- Variable star editor: **sluggish**

### After Indexes
- Browse 1 star catalog: **<10ms**
- Load dashboard: **<200ms**
- Variable star editor: **responsive**

---

## Related Documentation

- [SLOW_QUERY_LOG_SETUP.md](SLOW_QUERY_LOG_SETUP.md) - How this analysis was done
- [DATABASE_SCHEMA.md](../DATABASE_SCHEMA.md) - Table structure
- Strategic Plan: [.claude/plans/valiant-wobbling-fairy.md](.claude/plans/valiant-wobbling-fairy.md) - PRIORITÀ 2

---

## Action Items

- [ ] **ASAP**: Backup database
- [ ] **ASAP**: Create Priority 1 index (5-10 min)
- [ ] **Today**: Verify 50-100x speedup
- [ ] **This week**: Create Priority 2-3 indexes
- [ ] **Ongoing**: Monitor slow query log for regressions

---

**Created**: 2026-02-18
**Status**: Ready for implementation
**Estimated total fix time**: 30 minutes (including testing)
