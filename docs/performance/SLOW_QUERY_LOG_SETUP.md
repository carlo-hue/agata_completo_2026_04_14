# Slow Query Log Setup & Analysis Guide

**Date**: 2026-02-18
**Status**: ✅ Activated on astrogen01
**Database**: MariaDB (MySQL compatible)
**Threshold**: 1 second (tutte le query > 1s vengono loggat)

---

## Current Configuration

### MariaDB Config (50-server.cnf)

```ini
# Enable the slow query log to see queries with especially long duration
log_slow_query_file    = /var/log/mysql/mariadb-slow.log
log_slow_query_time    = 1                              # Threshold: 1 second
log_slow_verbosity     = query_plan,explain             # Include execution plan
log-queries-not-using-indexes                           # Log queries without indexes
log_slow_min_examined_row_limit = 0                     # No minimum rows examined
```

### Status

```
slow_query_log               = ON ✅
slow_query_log_file          = /var/log/mysql/mariadb-slow.log
log_slow_query_time          = 1.000000 seconds
log_slow_verbosity           = query_plan,explain
log_queries_not_using_indexes = ON
```

---

## How to Analyze Slow Queries

### Method 1: mysqldumpslow (Built-in Tool)

View top slow queries by total time:
```bash
sudo mysqldumpslow -s at /var/log/mysql/mariadb-slow.log | head -20
```

View top slow queries by count:
```bash
sudo mysqldumpslow -s c /var/log/mysql/mariadb-slow.log | head -20
```

View queries from database `catalogo` only:
```bash
sudo mysqldumpslow -db catalogo /var/log/mysql/mariadb-slow.log | head -30
```

### Method 2: Tail in Real-Time

Monitor as queries come in:
```bash
sudo tail -f /var/log/mysql/mariadb-slow.log
```

### Method 3: Python Script for AGATA-Specific Analysis

```python
#!/usr/bin/env python3
"""
Analyze AGATA slow queries from MariaDB log
Usage: python analyze_slow_queries.py
"""

import subprocess
import re
from datetime import datetime
from collections import defaultdict

def parse_slow_log():
    """Parse MariaDB slow query log and extract query statistics."""

    result = subprocess.run(
        ['sudo', 'tail', '-2000', '/var/log/mysql/mariadb-slow.log'],
        capture_output=True, text=True, check=True
    )

    lines = result.stdout.split('\n')
    queries = []
    current_entry = {}

    for line in lines:
        if line.startswith('# Time:'):
            if current_entry and 'query_time' in current_entry:
                queries.append(current_entry)
            current_entry = {'timestamp': line[7:]}

        elif line.startswith('# User@Host:'):
            current_entry['user'] = line[13:].split('[')[0].strip()

        elif line.startswith('# Query_time:'):
            match = re.search(r'Query_time: ([\d.]+)\s+Lock_time: ([\d.]+)\s+Rows_sent: (\d+)\s+Rows_examined: (\d+)', line)
            if match:
                current_entry['query_time'] = float(match.group(1))
                current_entry['lock_time'] = float(match.group(2))
                current_entry['rows_sent'] = int(match.group(3))
                current_entry['rows_examined'] = int(match.group(4))

        elif line and not line.startswith('#') and not line.startswith('SET'):
            if 'query' not in current_entry:
                current_entry['query'] = line[:100]  # First 100 chars

    if current_entry and 'query_time' in current_entry:
        queries.append(current_entry)

    return queries

def analyze():
    """Analyze and display slow query statistics."""

    print("=" * 80)
    print("AGATA SLOW QUERY ANALYSIS")
    print("=" * 80)

    queries = parse_slow_log()

    if not queries:
        print("No slow queries found in log")
        return

    # Sort by query time
    queries.sort(key=lambda x: x.get('query_time', 0), reverse=True)

    # Statistics
    total_queries = len(queries)
    total_time = sum(q.get('query_time', 0) for q in queries)
    avg_time = total_time / total_queries if total_queries > 0 else 0
    max_time = max(q.get('query_time', 0) for q in queries) if queries else 0

    print(f"\n📊 Summary Statistics:")
    print(f"  Total slow queries: {total_queries}")
    print(f"  Total time: {total_time:.2f}s")
    print(f"  Average time: {avg_time:.3f}s")
    print(f"  Max time: {max_time:.3f}s")

    # Top 10 queries
    print(f"\n🔴 Top 10 Slowest Queries:\n")
    print(f"{'Time (s)':>10} | {'Lock (ms)':>10} | {'Rows Ex.':>10} | Query")
    print("-" * 80)

    for q in queries[:10]:
        time_s = q.get('query_time', 0)
        lock_ms = q.get('lock_time', 0) * 1000
        rows_ex = q.get('rows_examined', 0)
        query = q.get('query', 'N/A')[:60]

        print(f"{time_s:>10.3f} | {lock_ms:>10.1f} | {rows_ex:>10} | {query}...")

    # Queries per user
    print(f"\n👤 Queries by User:")
    user_stats = defaultdict(lambda: {'count': 0, 'total_time': 0})
    for q in queries:
        user = q.get('user', 'unknown')
        user_stats[user]['count'] += 1
        user_stats[user]['total_time'] += q.get('query_time', 0)

    for user, stats in sorted(user_stats.items(), key=lambda x: x[1]['total_time'], reverse=True):
        print(f"  {user:20} - {stats['count']:3} queries, {stats['total_time']:7.2f}s total")

    print("\n" + "=" * 80)

if __name__ == '__main__':
    analyze()
```

Uso:
```bash
python /var/www/astrogen/docs/performance/analyze_slow_queries.py
```

### Method 4: MySQL Workbench Performance Schema

Se vuoi interfaccia grafica:
```bash
# Visualizza queries problematiche direttamente da DB
mysql -u aaaat01 -pdwedfAA1saa14 -e "
SELECT
    SQL_TEXT,
    COUNT(*) as call_count,
    SUM(TIMER_WAIT)/1000000000000 as total_wait_sec,
    AVG(TIMER_WAIT)/1000000000000 as avg_wait_sec,
    MAX(TIMER_WAIT)/1000000000000 as max_wait_sec
FROM performance_schema.events_statements_history_long
WHERE TIMER_WAIT IS NOT NULL
GROUP BY SQL_TEXT
ORDER BY total_wait_sec DESC
LIMIT 20;
"
```

---

## AGATA-Specific Analysis Checklist

### Critical Tables to Monitor

Basandosi sul piano strategico (Session 25), monitora queste query:

- **`agata_vast_results`** (18,499 righe):
  - Filtri per `job_id` + `is_known_variable` (Session 24 manual UI)
  - `gaia_source_id` lookup (cross-match queries)
  - Ordine per distanza/magnitude

- **`agata_catalog_attributes`** (155 righe, crescita rapida):
  - Lookup `(gaia_id, contesto, expires_at)` per cache retrieval
  - TTL expiration cleanup

- **`agata_projects`** (17 righe):
  - Dashboard stats query `(association_id, stato, created_at)`
  - Project detail queries

- **`agata_vast_jobs`** (88 righe):
  - Job list pagination
  - Status filtering

### Expected Slow Queries to Investigate

| Query Pattern | Why Slow | Action |
|---------------|----------|--------|
| `SELECT * FROM agata_vast_results WHERE job_id=X` | No index on `(job_id)` | Add composite index |
| `SELECT COUNT(*) FROM agata_catalog_attributes WHERE expires_at < NOW()` | Full table scan for TTL cleanup | Add index on `expires_at` |
| `SELECT ... FROM agata_projects p JOIN agata_vast_jobs v ON p.id=v.project_id` | Missing FK index | Verify FK index exists |
| `SELECT * FROM agata_vast_results ORDER BY distance_arcsec` | No index on sort column | Add if queried frequently |

### Optimization Priorities (from Strategic Plan)

After collecting 24 hours of slow query data:

1. **Priority A**: Queries on `agata_vast_results` (largest table, 18K rows)
   - Add `INDEX (job_id, is_known_variable)`
   - Add `INDEX (gaia_source_id)` if doing cross-match lookups

2. **Priority B**: Queries on `agata_projects` (dashboard stats)
   - Add `INDEX (association_id, stato, created_at)`

3. **Priority C**: Queries on `agata_catalog_attributes` (cache cleanup)
   - Add `INDEX (gaia_id, contesto, expires_at)`

---

## Rotating the Log File

Slow query log grows quickly. Rotate daily:

```bash
# Create logrotate config
sudo tee /etc/logrotate.d/mysql-slow-query > /dev/null << 'EOF'
/var/log/mysql/mariadb-slow.log {
    daily
    rotate 7
    compress
    delaycompress
    notifempty
    create 0640 mysql mysql
    sharedscripts
    postrotate
        /usr/lib/mysql-common/mysql-logrotate post-flush
    endscript
}
EOF

# Test logrotate
sudo logrotate -f /etc/logrotate.d/mysql-slow-query
```

---

## Disabling Slow Query Log (When Done Analyzing)

```bash
# Temporary (until MySQL restart)
sudo mysql -e "SET GLOBAL slow_query_log = OFF;"

# Permanent (edit config)
sudo sed -i '64s/^log_slow_query_file/# log_slow_query_file/; 65s/^log_slow_query_time/# log_slow_query_time/; 66s/^log_slow_verbosity/# log_slow_verbosity/; 67s/^log-queries-not-using-indexes/# log-queries-not-using-indexes/; 68s/^log_slow_min_examined_row_limit/# log_slow_min_examined_row_limit/' /etc/mysql/mariadb.conf.d/50-server.cnf

sudo systemctl restart mysql
```

---

## Documentation Location

- **This file**: `/var/www/astrogen/docs/performance/SLOW_QUERY_LOG_SETUP.md`
- **MariaDB Config**: `/etc/mysql/mariadb.conf.d/50-server.cnf`
- **Log file**: `/var/log/mysql/mariadb-slow.log`
- **Analysis script**: `/var/www/astrogen/docs/performance/analyze_slow_queries.py`

---

## Related Documentation

- [MEMORY_OPTIMIZATION.md](MEMORY_OPTIMIZATION.md) - Memory profiling
- [REDIS_CACHING_GUIDE.md](REDIS_CACHING_GUIDE.md) - Query caching with Redis
- [DATABASE_SCHEMA.md](../DATABASE_SCHEMA.md) - Schema and indexes
- [Strategic Plan](../../.claude/plans/valiant-wobbling-fairy.md) - PRIORITÀ 2: Database Query Optimization

---

**Last Updated**: 2026-02-18
**Status**: ✅ Active on astrogen01
**Next Review**: After 7 days of data collection (2026-02-25)
