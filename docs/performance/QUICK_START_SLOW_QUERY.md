# Quick Start: Slow Query Analysis

**Attivato**: 2026-02-18 su astrogen01

## TL;DR - I 3 Comandi Che Devi Sapere

```bash
# 1. Vedi statistiche rapide (ogni 5 minuti)
./scripts/monitor-slow-queries.sh stats

# 2. Analisi dettagliata (ogni giorno)
python docs/performance/analyze_slow_queries.py

# 3. Top 10 query più lente (investigazione)
sudo mysqldumpslow -s at /var/log/mysql/mariadb-slow.log | head -30
```

---

## Status Attuale (2026-02-18)

✅ **Slow query log abilitato** con threshold 1 secondo

```
slow_query_log        = ON
log_slow_query_time   = 1.000000 seconds
log_slow_verbosity    = query_plan,explain
log-queries-not-using-indexes = ON
```

**Location**: `/var/log/mysql/mariadb-slow.log`

---

## Prima Query Lenta Catturata

| Metric | Value |
|--------|-------|
| Query Time | 5.527 seconds |
| Rows Examined | 2,468,985 |
| Table | `Cataloghi_esterni` |
| Issue | **NO INDEX on `association_id_owner` + filesort** |
| Operation | `DISTINCT ... GROUP BY` |

**Query**:
```sql
SELECT DISTINCT ce.Source as gaia_id, COUNT(*) as total_points, ...
FROM Cataloghi_esterni ce
LEFT JOIN agata_catalog_imports ci ON ce.catalog_import_id = ci.id
WHERE ce.association_id_owner IS NULL
GROUP BY ce.Source
```

**Problem**: Full table scan (ALL) + file-based sorting (Using filesort)

**Solution**: Add index `(association_id_owner, Source)` to speed up WHERE + GROUP BY

---

## Monitoring Strategy

### Daily (Automated with Cron)

```bash
# Add to crontab
0 9 * * * /var/www/astrogen/scripts/monitor-slow-queries.sh batch >> /var/log/astrogen-slowquery-analysis.log 2>&1
```

### Weekly (Manual Investigation)

1. Run batch analysis every Friday
2. Review top 10 slowest queries
3. Check for new indexes needed
4. Document findings in SLOW_QUERY_LOG_SETUP.md

### Monthly (Optimization Sprint)

- Implement recommended indexes
- Re-baseline performance
- Update query plans (ANALYZE TABLE)

---

## Quick Optimization Checklist

### High Priority (from Initial Analysis)

- [ ] Add index: `Cataloghi_esterni (association_id_owner, Source)`
- [ ] Add index: `Cataloghi_esterni (catalogo, hjd)` if doing time-range queries
- [ ] Analyze query: why `GROUP BY` needs filesort?

### From Strategic Plan (Session 25)

- [ ] Add index: `agata_vast_results (job_id, is_known_variable)`
- [ ] Add index: `agata_projects (association_id, stato, created_at)`
- [ ] Add index: `agata_catalog_attributes (gaia_id, contesto, expires_at)`

---

## Next Actions

**Timeline**: 2026-02-18 to 2026-02-25 (7 days data collection)

1. **Collect Data** (Feb 18-25)
   - Monitor slow queries continuously
   - Identify patterns
   - Document issues

2. **Analyze** (Feb 25)
   - Run full analysis
   - Prioritize indexes
   - Estimate impact

3. **Implement** (Feb 25-Mar 1)
   - Add high-priority indexes
   - Test performance
   - Verify improvement

4. **Monitor** (Ongoing)
   - Continue slow query logging
   - Review monthly
   - Adjust thresholds if needed

---

## Useful Commands

```bash
# View log in real-time
tail -f /var/log/mysql/mariadb-slow.log

# Count slow queries
sudo tail -1000 /var/log/mysql/mariadb-slow.log | grep "^# Query_time:" | wc -l

# Get log file size
sudo ls -lh /var/log/mysql/mariadb-slow.log

# View only query times
sudo tail -2000 /var/log/mysql/mariadb-slow.log | grep "^# Query_time:" | sort -t= -k2 -rn | head -20

# Check if log is rotating properly
ls -la /var/log/mysql/mariadb-slow.log*
```

---

## Disabling Slow Query Log (When Done)

```bash
# Temporary
sudo mysql -e "SET GLOBAL slow_query_log = OFF;"

# Permanent (edit config)
sudo sed -i '64s/^log_slow_query_file/# log_slow_query_file/' /etc/mysql/mariadb.conf.d/50-server.cnf
sudo systemctl restart mysql
```

---

## Reference

- **Full Guide**: [SLOW_QUERY_LOG_SETUP.md](SLOW_QUERY_LOG_SETUP.md)
- **Analysis Script**: `docs/performance/analyze_slow_queries.py`
- **Monitor Script**: `scripts/monitor-slow-queries.sh`
- **Strategic Plan**: (`.claude/plans/valiant-wobbling-fairy.md`) - PRIORITÀ 2

---

**Last Updated**: 2026-02-18
**Status**: ✅ Active, Collecting Data
