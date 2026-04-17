# 📚 Archive Documentation Index

**Last Updated**: 2026-02-20
**Status**: Historical documentation (for reference and learning)
**Total Files**: 82 documents organized in 14 subdirectories

---

## Archive Organization

This directory contains historical documentation of development iterations, bug fixes, and optimization processes. Use this when you want to understand:
- Why a particular decision was made
- What approaches were tried before the current solution
- How long a feature took to stabilize
- Root cause analysis of past bugs

---

## 🔍 By Subdirectory

### 1. `gaia_matching_iterations/` (14 files)

**Purpose**: Complete history of Gaia cross-matching algorithm development

**Key Iterations**:
- Simple single-star queries (early attempt)
- TAP upload with JOIN (caused timeouts)
- BOX query approach (proven working)
- Two-stage Vizier fallback (final implementation)
- Gmag < 18 filtering (refinement)
- Manual correction UI (Session 24)
- Ambiguity detection & user resolution (NEW)
- 30" radius optimization fix (NEW)

**New Files** (2026-02-20):
- `AMBIGUITY_FLOW_DIAGRAM.md` - Complete user flow for resolving ambiguous Gaia matches
  - Detects when nearest ≠ brightest within TOP 10
  - Stores candidates in JSON for user selection
  - Modal UI for users to choose correct match
  - Saves user's choice and resolves match
- `GAIA_FIX_SUMMARY_FINAL.md` - Root cause of dense field Gaia mismatches
  - Problem: 125" radius, TOP 10 brightest (nearest not guaranteed)
  - Solution: Reduce to 30" radius (nearest always in TOP 10)
  - Impact: 95%+ → 99%+ match accuracy

**When to Read**:
- Understanding why the current algorithm is two-stage
- "What went wrong with TAP?" → See SESSION_SUMMARY_GAIA_ALGORITHM.md
- "How did we handle ambiguous matches?" → See GAIA_AMBIGUITY_DETECTION.md

**Key Files**:
- `GAIA_MATCHING_BUG_ROOT_CAUSE.md` - Why Gaia was returning 0 matches initially
- `SESSION_SUMMARY_GAIA_ALGORITHM.md` - Complete algorithm history
- `GAIA_FIX_BEFORE_AFTER.md` - Before/after comparison of fixes

---

### 2. `session_history/` (11 files)

**Purpose**: Session summaries and major checkpoint notes

**Session Snapshots**:
- SESSION_17_SUMMARY - Gaia TAP migration
- SESSION_18_COMPLETION_SUMMARY - Bug fixes completion
- SESSION_21_FINAL_SUMMARY - Gaia fix summary
- SESSION_23_IMPLEMENTATION_SUMMARY - Magnitude offset implementation
- SESSION_24_MANUAL_GAIA_CORRECTION_COMPLETE - Manual Gaia UI (Session 24)
- SESSION_24_THREE_LAYER_SOLUTION - Three-layer ambiguity solution
- DEPLOYMENT_CHECKLIST_SESSION_17 - Deployment preparation
- SESSION_SUMMARY_2026-02-13 - TESS QLP optimization
- COMMIT_SUMMARY - Last commit details

**New Files** (2026-02-20):
- `README_SESSION_17.md` - Session 17 detailed notes and setup context

**When to Read**:
- "When did we implement feature X?" → Check session summaries
- Understanding session context and dependencies
- Learning how problems were diagnosed and fixed

---

### 3. `db_optimization_process/` (8 files)

**Purpose**: Database query optimization iterations

**Optimization History**:
1. **INDEX_OPTIMIZATION_PLAN.md** - Initial plan (100x speedup for catalog)
2. **OPTIMIZATION_SUMMARY.md** - First optimization attempt
3. **OPTIMIZATION_SUMMARY_SESSION20.md** - Session 20 optimization results
4. **CRITICAL_QUERY_FIXES_HOTFIX.md** - Hotfix for query issues
5. **CRITICAL_QUERY_FIXES_SESSION_18.md** - Session 18 fixes
6. **DATABASE_QUERY_AUDIT_COMPLETE.md** - Complete audit of slow queries
7. **DATABASE_RELATIONSHIPS_ANALYSIS.md** - Relationship analysis
8. **USER_INDEX_NOTES_ANALYSIS.md** - Analysis of index impact

**Performance Gains**:
- Catalog queries: 0.77s → 0.03s (25x faster, indexes)
- Stars catalog: 4.57s → 0.48s (9.5x faster, remove LEFT JOIN)
- Stars catalog refactor: 80x expected with denormalized cache

**When to Read**:
- "Why did catalog queries get indexed?" → INDEX_OPTIMIZATION_PLAN.md
- Understanding the database audit process
- Learning index strategy patterns

---

### 4. `magnitude_calibration_debug/` (4 files)

**Purpose**: Magnitude calibration algorithm debugging

**Issues Addressed**:
- Coherence check implementation and removal
- Magnitude offset calculation methods
- Pre vs post-calibration validation
- Median implementation for robust statistics

**Key Problems Solved**:
- Over-strict post-calibration checks (removed)
- Pre-calibration vs post-calibration tolerance
- Offset calculation from sample vs per-star

**When to Read**:
- Understanding magnitude validation strategy
- "Why was the coherence check removed?" → COHERENCE_FAILURE_ANALYSIS.md
- Learning about magnitude offset robustness

---

### 5. `vast_debug/` (5 files)

**Purpose**: VAST automation debugging and analysis

**Topics**:
- Early stage pipeline checks
- VASTSTAT column fixes
- Coordinate system validation
- Variable type integration
- Delete UI/API

**When to Read**:
- "How did we validate VAST output?" → EARLY_STAGE_CHECK_WALKTHROUGH.md
- Understanding VAST coordinate systems
- Learning about delete operation implementation

---

### 6. `bug_fixes/` (4 files)

**Purpose**: Resolved bug reports and fixes

**Bugs Fixed**:
- Skip VAST mode coordinate issues
- Gaia TAP async hanging
- Bulk delete performance (N+1 queries)
- Inverted CONTAINS query syntax

**When to Read**:
- Understanding past bugs and their solutions
- Learning from debugging techniques
- Recognizing patterns that lead to bugs

---

### 7. `implementation_reports/` (8 files)

**Purpose**: Implementation tracking and specifications

**Contents**:
- Implementation readiness checks
- Detailed implementation specifications
- Test instructions
- Frontend integration specs
- Quick start guides
- Pedagogical documentation

**When to Read**:
- Understanding how features are specified
- Test strategies
- Integration approaches

---

### 8. `tess_qlp_optimization/` (5 files)

**Purpose**: TESS QLP import optimization history

**Optimizations**:
1. SearchResult caching (eliminates 8-14s redundant Lightkurve search)
2. Vizier TIC lookup with MAST fallback
3. Critical fixes for Vizier vs MAST priority

**New Files** (2026-02-20):
- `TESS_QLP_FLOW_DIAGRAM.md` - Visual before/after comparison
  - Before: 46-150s (redundant Lightkurve search in Step 2)
  - After: 34-99s (SearchResult cached and passed from Step 1)
  - Shows detailed timing breakdown for each step

**Performance Impact**: 25% overall speedup

**When to Read**:
- Understanding why Vizier-first broke QLP (returns wrong TIC)
- Learning about MAST vs Vizier trade-offs
- SearchResult serialization patterns

---

### 9. `stars_catalog_optimization/` (2 files)

**Purpose**: Stars catalog optimization iterations

**Topics**:
- Data flow analysis
- Performance optimization strategy
- Denormalized cache design

**When to Read**:
- Understanding the stars catalog refactoring approach
- Learning about cache invalidation patterns
- Performance analysis methodology

---

### 10. `test_data/` (1 file)

**Purpose**: Test result data and sample sizes

**Contents**:
- Test dataset specifications
- Sample size documentation
- Test result analysis

---

### 11. `analysis_reports/` (2 files)

**Purpose**: System analysis and status reports

**Topics**:
- Algorithm verification
- System status analysis

**When to Read**:
- Understanding system-level analysis approaches
- Learning verification methodologies

---

### 12. `deployment_setup/` (1 file)

**Purpose**: Deployment configuration notes

**Contents**:
- SSH deployment setup
- Configuration management

**When to Read**:
- Understanding deployment infrastructure

---

## 🎯 Finding What You Need

### "I want to understand the Gaia algorithm evolution"
```
gaia_matching_iterations/
├── GAIA_MATCHING_BUG_ROOT_CAUSE.md (why it started failing)
├── GAIA_TWO_STAGE_IMPLEMENTATION.md (first two-stage attempt)
├── GAIA_ALGORITHM_READY_FOR_TESTING.md (testing checkpoint)
├── STAGE2_FALLBACK_CLOSEST_FIX.md (fallback refinement)
└── SESSION_SUMMARY_GAIA_ALGORITHM.md (complete history)
```

### "I need to optimize a slow query"
```
db_optimization_process/
├── DATABASE_QUERY_AUDIT_COMPLETE.md (audit methodology)
├── INDEX_OPTIMIZATION_PLAN.md (indexing strategy)
└── OPTIMIZATION_SUMMARY.md (results)
```

### "I want to see how we debugged the magnitude system"
```
magnitude_calibration_debug/
├── MAGNITUDE_DEBUG_NOTES.md (debugging log)
├── COHERENCE_FAILURE_ANALYSIS.md (what failed and why)
└── MEDIAN_IMPLEMENTATION_COMPLETE.md (final approach)
```

### "I need to understand VAST coordinate systems"
```
vast_debug/
├── EARLY_STAGE_CHECK_WALKTHROUGH.md (validation process)
└── (other VAST-specific docs)
```

### "I want to learn about a specific fix"
```
bug_fixes/
└── (Each file documents a specific bug fix)
```

---

## 📊 Statistics

| Category | Files | Purpose |
|----------|-------|---------|
| Gaia development | 14 | Algorithm iterations |
| Session history | 11 | Session summaries |
| DB optimization | 10 | Query/index optimization |
| Magnitude debug | 6 | Calibration debugging |
| VAST analysis | 6 | VAST pipeline debugging |
| Bug fixes | 4 | Resolved issues |
| Implementation | 11 | Spec and tracking |
| TESS optimization | 5 | QLP import speedup |
| Stars catalog | 3 | Catalog optimization |
| Test data | 3 | Test results |
| Analysis reports | 2 | System analysis |
| Deployment | 1 | Deploy setup |
| **TOTAL** | **76** | **Historical docs** |

**Note**: 4 new files added 2026-02-20 (Ambiguity diagrams, Gaia fix summary, TESS flow)

---

## ⏰ Timeline View

### February 2026

**Early Feb (Sessions 1-10)**: VAST automation pipeline
- Integration with Google Drive
- Gaia TAP cross-matching (early attempts)
- WCS validation and solving

**Mid Feb (Sessions 11-20)**: Gaia algorithm refinement
- TAP timeout issues → BOX query migration
- Two-stage Vizier fallback development
- Manual Gaia correction UI

**Late Feb (Sessions 21-24)**: Performance & Stability
- Magnitude calibration refinement
- TESS QLP optimization
- Stars catalog refactoring
- Database index optimization

---

## 🔗 Reference Links

**Current Implementation Guides** (use these):
- [Root: VAST_VARIABLE_TYPE_INTEGRATION_COMPLETE.md](../../VAST_VARIABLE_TYPE_INTEGRATION_COMPLETE.md)
- [Root: GAIA_TWO_STAGE_VIZIER_IMPLEMENTATION_FINAL.md](../../GAIA_TWO_STAGE_VIZIER_IMPLEMENTATION_FINAL.md)
- [Root: INDEX_OPTIMIZATION_COMPLETE.md](../../INDEX_OPTIMIZATION_COMPLETE.md)

**Archive Navigation**:
- [Back to Root INDEX.md](../../INDEX.md)
- [Back to CLAUDE.md](../../CLAUDE.md)

---

**Last organized**: 2026-02-20
**Archive purpose**: Learning from development history
**Recommendation**: Read archive when understanding "why this way?" not "what to do?"
