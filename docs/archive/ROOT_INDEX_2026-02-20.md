# 📚 ASTROGEN Documentation Index (2026-02-20)

**Last Updated**: 2026-02-20
**Organization**: Clean root + organized archive
**Status**: ✅ Ready for reference

---

## 🚀 Start Here

1. **[CLAUDE.md](CLAUDE.md)** - Project overview (auto-loaded by Claude Code CLI)
2. **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System design and patterns
3. **[docs/DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md)** - Database structure (authoritative)
4. **[docs/INDEX.md](docs/INDEX.md)** - Main documentation index

---

## 📖 Root-Level Implementation Guides

These are the **10 primary reference documents** for completed features. Use these to understand how each major subsystem actually works:

### VAST Automation Pipeline
- **[VAST_VARIABLE_TYPE_INTEGRATION_COMPLETE.md](VAST_VARIABLE_TYPE_INTEGRATION_COMPLETE.md)**
  - Known variable detection, variable type classification, candidate identification
  - Status: ✅ Complete and stable

### Gaia Catalog Cross-Matching (3 documents)
- **[GAIA_TWO_STAGE_VIZIER_IMPLEMENTATION_FINAL.md](GAIA_TWO_STAGE_VIZIER_IMPLEMENTATION_FINAL.md)**
  - Two-stage Vizier matching algorithm, fallback strategy, Gmag < 18 filtering
  - Status: ✅ Final implementation (Session 2026-02-17)

- **[GAIA_MAGNITUDE_OFFSET_IMPLEMENTATION.md](GAIA_MAGNITUDE_OFFSET_IMPLEMENTATION.md)**
  - Global magnitude offset calculation from 5-star sample
  - Vmag formula and reference calculation
  - Status: ✅ Complete (Session 2026-02-23)

- **[SESSION_24_MANUAL_GAIA_CORRECTION_COMPLETE.md](SESSION_24_MANUAL_GAIA_CORRECTION_COMPLETE.md)**
  - Manual Gaia match verification and correction UI
  - Search modal, select interface, database update
  - Status: ✅ Complete (Session 2026-02-17)

### Magnitude System (2 documents)
- **[MAGNITUDE_CALIBRATION_FIX.md](MAGNITUDE_CALIBRATION_FIX.md)**
  - Magnitude offset calculation and coherence validation
  - Pre-calibration vs post-calibration checks
  - Status: ✅ Fixed

- **[GMAG_FILTER_FIX_COMPLETE.md](GMAG_FILTER_FIX_COMPLETE.md)**
  - Gmag < 18 filtering in Vizier queries (Stage 1)
  - Prevents over-bright star matches
  - Status: ✅ Fixed

### Database & Performance (2 documents)
- **[INDEX_OPTIMIZATION_COMPLETE.md](INDEX_OPTIMIZATION_COMPLETE.md)**
  - Catalog query indexes on Cataloghi_esterni table
  - 100x speedup for catalog browsing
  - Status: ✅ Complete (Session 2026-02-18)

- **[STARS_CATALOG_REFACTORING_COMPLETE.md](STARS_CATALOG_REFACTORING_COMPLETE.md)**
  - Stars catalog denormalized cache implementation
  - 80x speedup with agata_star table
  - 5-phase implementation with hooks and backfill
  - Status: ✅ Complete (Session 2026-02-20)

### TESS QLP Import
- **[TESS_QLP_IMPROVEMENTS_COMPLETE.md](TESS_QLP_IMPROVEMENTS_COMPLETE.md)**
  - SearchResult caching (eliminates 8-14s redundant search)
  - Vizier TIC lookup with MAST fallback
  - 25% overall speedup
  - Status: ✅ Complete (Session 2026-02-13)

### Project Documentation
- **[COMMIT_SUMMARY.md](COMMIT_SUMMARY.md)** - Last commit message and session summary
- **[TESTING_QUICK_START.md](TESTING_QUICK_START.md)** - Quick reference for common tests

---

## 🧪 Test Files Directory

All test scripts have been organized in the **[tests/](tests/)** directory:

- **[tests/INDEX.md](tests/INDEX.md)** - Test directory guide
- **tests/gaia/** (19 tests) - Gaia cross-matching algorithm tests
- **tests/other/** (3 tests) - Miscellaneous debugging tests
- **tests/vast/, tests/tess/, tests/auth/, tests/kb/, tests/catalog/** (ready for use)

---

## 📁 Documentation Tree

### Main Docs (`docs/`)

**Core Architecture**
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) - System design (normative)
- [ARCHITECTURE_MAP.md](docs/ARCHITECTURE_MAP.md) - Architecture → repo mapping
- [DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md) - Complete DB schema (authoritative)
- [INDEX.md](docs/INDEX.md) - Docs index

**Setup & Integration**
- [AGATA_AUTH_SETUP_GUIDE.md](docs/auth/AGATA_AUTH_SETUP_GUIDE.md) - OAuth configuration
- [KNOWLEDGE_BASE_SETUP.md](docs/KNOWLEDGE_BASE_SETUP.md) - KB system setup
- [DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md) - Production deployment (multi-environment)

**Features**
- [docs/features/](docs/features/) - Feature-specific documentation
  - CATALOG_INTEGRATION.md - Vizier catalog querying
  - CATALOG_DATABASE_PERSISTENCE.md - 180-day DB cache
  - IMPORT_CATALOGS_INTEGRATION.md - TESS QLP import
  - SLACK_EXPORT_IMPLEMENTATION.md - Slack export
  - vast/ - VAST automation (10 documents)

**Performance & Optimization**
- [docs/performance/](docs/performance/) - Performance documentation
  - MEMORY_OPTIMIZATION.md - Memory and caching strategy
  - REDIS_CACHING_GUIDE.md - Redis usage patterns
  - SLOW_QUERY_LOG_SETUP.md - Query logging and analysis
  - analyze_slow_queries.py - Analysis script

**AI & Analytics**
- [docs/ai/](docs/ai/) - AI Advisor setup
- [docs/kb/](docs/kb/) - Knowledge Base guides

**Admin Module**
- [agata/admin/README.md](agata/admin/README.md) - Admin blueprint overview

---

## 📦 Historical Documentation (`docs/archive/`)

**52 historical documents organized by topic** (preserved for reference):

| Directory | Purpose | Files |
|-----------|---------|-------|
| `gaia_matching_iterations/` | Gaia algorithm development history | 11 |
| `session_history/` | Previous session summaries | 6 |
| `db_optimization_process/` | Database optimization iterations | 8 |
| `magnitude_calibration_debug/` | Magnitude debugging notes | 4 |
| `vast_debug/` | VAST analysis debug docs | 5 |
| `bug_fixes/` | Resolved bug reports | 4 |
| `implementation_reports/` | Implementation tracking | 4 |
| `tess_qlp_optimization/` | TESS optimization iterations | 4 |
| `stars_catalog_optimization/` | Stars catalog iterations | 2 |
| `test_data/` | Test results | 1 |
| `analysis_reports/` | System analysis reports | 2 |
| `deployment_setup/` | Deployment notes | 1 |

**Quick Links** (if you need history):
- When did we implement the two-stage Gaia algorithm? → `docs/archive/gaia_matching_iterations/`
- What was wrong with magnitude calibration? → `docs/archive/magnitude_calibration_debug/`
- How did we optimize catalog queries? → `docs/archive/db_optimization_process/`

---

## 🎯 By Use Case

### "I need to understand how VAST works"
1. Start: [docs/features/vast/VAST_SETUP_GUIDE.md](docs/features/vast/VAST_SETUP_GUIDE.md)
2. Then: [VAST_VARIABLE_TYPE_INTEGRATION_COMPLETE.md](VAST_VARIABLE_TYPE_INTEGRATION_COMPLETE.md)
3. Deep dive: [docs/features/vast/](docs/features/vast/) (10 documents)

### "I need to fix a Gaia matching bug"
1. Start: [GAIA_TWO_STAGE_VIZIER_IMPLEMENTATION_FINAL.md](GAIA_TWO_STAGE_VIZIER_IMPLEMENTATION_FINAL.md)
2. Reference: [SESSION_24_MANUAL_GAIA_CORRECTION_COMPLETE.md](SESSION_24_MANUAL_GAIA_CORRECTION_COMPLETE.md)
3. History: `docs/archive/gaia_matching_iterations/` (11 iterations)

### "Why is database slow?"
1. Start: [docs/performance/SLOW_QUERY_LOG_SETUP.md](docs/performance/SLOW_QUERY_LOG_SETUP.md)
2. Optimization: [INDEX_OPTIMIZATION_COMPLETE.md](INDEX_OPTIMIZATION_COMPLETE.md)
3. Refactoring: [STARS_CATALOG_REFACTORING_COMPLETE.md](STARS_CATALOG_REFACTORING_COMPLETE.md)

### "How does the authentication system work?"
1. Start: [docs/auth/AGATA_AUTH_SETUP_GUIDE.md](docs/auth/AGATA_AUTH_SETUP_GUIDE.md)
2. Reference: [docs/auth/AGATA_AUTH_IMPLEMENTATION_SUMMARY.md](docs/auth/AGATA_AUTH_IMPLEMENTATION_SUMMARY.md)

### "What's the project architecture?"
1. Start: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
2. Then: [docs/ARCHITECTURE_MAP.md](docs/ARCHITECTURE_MAP.md)
3. Database: [docs/DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md)

### "How do I deploy?"
1. [docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md) - Complete guide
2. Multi-env setup: Slack configuration section for dev/prod

---

## 📊 Key Project References

| Aspect | Reference |
|--------|-----------|
| **System Design** | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| **Database** | [docs/DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md) |
| **Authentication** | [docs/auth/](docs/auth/) |
| **VAST Automation** | [VAST_VARIABLE_TYPE_INTEGRATION_COMPLETE.md](VAST_VARIABLE_TYPE_INTEGRATION_COMPLETE.md) + [docs/features/vast/](docs/features/vast/) |
| **Gaia Matching** | [GAIA_TWO_STAGE_VIZIER_IMPLEMENTATION_FINAL.md](GAIA_TWO_STAGE_VIZIER_IMPLEMENTATION_FINAL.md) |
| **Catalog Integration** | [docs/features/CATALOG_INTEGRATION.md](docs/features/CATALOG_INTEGRATION.md) |
| **Performance** | [docs/performance/](docs/performance/) |
| **Admin Module** | [agata/admin/README.md](agata/admin/README.md) |

---

## 📝 Quick Command Reference

```bash
# View slow queries
python docs/performance/analyze_slow_queries.py

# Test Gaia matching
# -> See: GAIA_TWO_STAGE_VIZIER_IMPLEMENTATION_FINAL.md

# Start Flask
python -m flask run

# Check DB schema
# -> Read: docs/DATABASE_SCHEMA.md
```

---

## 📌 Important Notes

- **CLAUDE.md** - Auto-loaded by Claude Code CLI (keep updated)
- **Root .md files** - 10 final implementation guides (for reference)
- **docs/** - Main documentation tree (ARCHITECTURE, DATABASE_SCHEMA, features, etc.)
- **docs/archive/** - 52 historical documents (development process preserved)
- **All links are relative** - Works from project root

---

**Last organized**: 2026-02-20
**Total documents**: 74 (12 in root + 62 in docs/)
**Status**: ✅ Clean, organized, navigation complete
