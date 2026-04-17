# 🧹 Duplicates & Cleanup Log

**Date**: 2026-02-02
**Status**: Documentation organization completed

---

## 📋 Files to Consider Removing/Archiving

### 1. Exact Duplicates (Same Content)

**None found** - All files have distinct purposes.

### 2. Near-Duplicates (Overlapping Content)

These files have overlapping content but serve different audiences/purposes:

| File 1 | File 2 | Overlap | Recommendation |
|--------|--------|---------|-----------------|
| INIZIA_QUI.md | KNOWLEDGE_BASE_SETUP.md | KB setup with Voyage AI | **KEEP BOTH** - INIZIA_QUI is quick-start, KNOWLEDGE_BASE_SETUP is detailed |
| INIZIA_QUI_SENTENCE_TRANSFORMERS.md | KNOWLEDGE_BASE_SETUP.md | Free embeddings setup | **KEEP BOTH** - INIZIA_QUI_ST is ultra-quick, KNOWLEDGE_BASE_SETUP is comprehensive |
| KNOWLEDGE_BASE_QUICKSTART.md | INIZIA_QUI.md | 5-minute setup | **CONSIDER MERGING** - QUICKSTART might be redundant with INIZIA_QUI |
| AGATA_AUTH_SETUP_GUIDE.md | TEST_LOGIN_GOOGLE.md | Google OAuth setup | **KEEP BOTH** - SETUP is for installation, TEST is for verification |
| AI_ADVISOR_IMPLEMENTATION.md | QUICK_START_AI.md | AI Advisor setup | **KEEP BOTH** - IMPLEMENTATION is detailed, QUICK_START is 5-minute |

### 3. Obsolete/Deprecated Files

These should be archived in `/docs/archive/`:

#### ✅ Already Identified & Archived
All files in `/docs/old/` and `/docs/auth/old/` (14 files total) - Documented completed implementations from January 2026.

#### ⚠️ Consider Archiving (If Not Using)

| File | Location | Why Archive | Keep if... |
|------|----------|-------------|-----------|
| SLACK_CLEANUP_INSTRUCTIONS.md | docs/old/ | Slack integration complete | Maintaining Slack channels |
| Guida_logging_js.md | docs/old/ | Legacy logging guide | Using old JS logging patterns |
| external_catalogs.md | docs/old/ | Moved to features | Only for historical context |
| Guida_logging_js.md | __pycache__/aaaat_backup_20260103_210904/ | Backup copy (outdated) | DELETE - it's a backup |

### 4. Files That Might Be Outdated

Check these for currency:

| File | Last Updated | Status | Action |
|------|--------------|--------|--------|
| README.md | 2026-01-13 | ⚠️ 20 days old | **REVIEW & UPDATE** |
| ARCHITECTURE.md | 2026-01-20 | ✅ Recent | Current |
| DATABASE_SCHEMA.md | 2026-01-31 | ✅ Recent | Current |
| MEMORY_OPTIMIZATION.md | 2026-02-01 | ✅ Very Recent | Current |
| REDIS_CACHING_GUIDE.md | 2026-01-31 | ✅ Recent | Current |
| agata/admin/README.md | 2026-01-13 | ⚠️ 20 days old | **REVIEW** |
| agata/variable_stars/AI_ADVISOR_README.md | 2026-01-12 | ⚠️ 21 days old | **REVIEW** |

---

## 🗑️ Cleanup Recommendations

### Phase 1: DONE ✅
- [x] Create CLAUDE.md (auto-loaded context)
- [x] Create docs/INDEX.md (documentation index)
- [x] Create docs/archive/README.md (archive explanation)
- [x] Identify duplicates and overlaps

### Phase 2: RECOMMENDED (Optional)

These are optional but would improve clarity:

1. **Merge overlapping KB quick-starts**
   - Merge KNOWLEDGE_BASE_QUICKSTART.md into INIZIA_QUI.md
   - Reason: Both 5-minute quick starts, confusing to have two
   - Impact: Low (remove 1 file)

2. **Update root README.md**
   - Last updated 2026-01-13, now 20 days old
   - Update with recent KB/AI features
   - Link to CLAUDE.md and docs/INDEX.md
   - Impact: Medium (maintains entry point)

3. **Update agata/admin/README.md**
   - Last updated 2026-01-13
   - Check if RBAC/audit features are complete and documented
   - Impact: Low (module-specific)

4. **Move archived backup files**
   - __pycache__/aaaat_backup_20260103_210904/Guida_logging_js.md - DELETE (outdated backup)
   - __pycache__/aaaat_backup_20260103_210904/readme.md - DELETE (backup copy)
   - Reason: These are stale backups, original exists in docs/old/
   - Impact: Cleanup (removes confusing duplicates)

5. **Archive docs/auth/old/ files to docs/archive/auth-old/**
   - Keep with clear "OBSOLETE" marker
   - Add cross-reference in docs/auth/README.md
   - Impact: Organization (clarifies active vs archived)

### Phase 3: NOT RECOMMENDED

**Do NOT remove/archive these**, despite potential overlap:

- ✅ INIZIA_QUI.md + INIZIA_QUI_SENTENCE_TRANSFORMERS.md - Different audiences (Voyage AI vs free)
- ✅ AGATA_LOW_COST_PROMPT_TEMPLATE.md + AGATA_LOW_COST_PROMPT_TEMPLATE_COMPACT.md - Different use cases (full vs quick)
- ✅ ARCHITECTURE.md + ARCHITECTURE_MAP.md - Complementary (rules + mapping)
- ✅ DATABASE_SCHEMA.md + docs/architecture files - Complementary (schema + high-level)

---

## 📂 Final Directory Structure (After Cleanup)

```
/var/www/astrogen/
├── CLAUDE.md                          ← AUTO-LOADED context for Claude Code
├── README.md                          ← Entry point (should update)
├── INITIAL_SETUP.md                   ← Optional: consolidated quick start
├──
├── docs/
│   ├── INDEX.md                       ← Master documentation index
│   ├── ARCHITECTURE.md                ← Architecture (KEEP)
│   ├── ARCHITECTURE_MAP.md            ← Architecture mapping (KEEP)
│   ├── DATABASE_SCHEMA.md             ← DB schema (KEEP - authoritative)
│   ├── KNOWLEDGE_BASE_SETUP.md        ← KB detailed setup (KEEP)
│   ├── DUPLICATES_AND_CLEANUP.md      ← This file
│   │
│   ├── auth/
│   │   ├── AGATA_AUTH_SETUP_GUIDE.md  ← Current auth setup
│   │   ├── AGATA_AUTH_IMPLEMENTATION_SUMMARY.md
│   │   ├── TEST_LOGIN_GOOGLE.md
│   │   └── old/                       ← Superseded auth docs (reference only)
│   │
│   ├── ai/
│   │   ├── AI_ADVISOR_IMPLEMENTATION.md
│   │   ├── QUICK_START_AI.md
│   │   ├── CEREBRAS_SETUP.md
│   │   └── TEST_AI_ADVISOR.md
│   │
│   ├── refactoring/
│   │   ├── REFACTORING_SUMMARY.md
│   │   └── (old proposals in archive)
│   │
│   └── archive/
│       ├── README.md                  ← Archive explanation
│       ├── old/                       ← Completed features (Jan 2026)
│       ├── auth-old/                  ← Superseded auth docs
│       └── refactoring-proposals/     ← Completed refactor docs
│
├── agata/
│   ├── admin/
│   │   ├── README.md
│   │   └── services/
│   │       └── VARIABILITY_ANALYSIS_README.md
│   │
│   ├── variable_stars/
│   │   ├── STRUCTURE.md
│   │   └── AI_ADVISOR_README.md
│   │
│   └── exoplanets/
│       └── workflow_exoclock.md
```

---

## 🔄 Current Status

| Task | Status | Notes |
|------|--------|-------|
| Create CLAUDE.md | ✅ DONE | Auto-loaded context |
| Create docs/INDEX.md | ✅ DONE | Master documentation index |
| Create docs/archive/ structure | ✅ DONE | Ready for old docs |
| Identify duplicates | ✅ DONE | Documented above |
| **Update root README.md** | ⏳ RECOMMENDED | Hasn't been updated in 20 days |
| **Review agata/admin/README.md** | ⏳ RECOMMENDED | 20 days old, verify content |
| Delete __pycache__ backup files | ⏳ RECOMMENDED | Remove stale backups |
| Merge KB quick-starts (optional) | ⏳ OPTIONAL | Both serve different purposes |

---

## 📝 Notes

1. **CLAUDE.md is now the "golden source"** for project context. It's auto-loaded by Claude Code CLI and contains:
   - Project overview
   - Architecture principles
   - Directory structure
   - Key files to know
   - Common tasks

2. **docs/INDEX.md provides detailed navigation** with:
   - Links to all active documentation
   - Common workflows
   - When to use each doc
   - Quick reference map

3. **Archived documentation is preserved** for:
   - Historical understanding
   - Gap analysis
   - Learning from completed work

4. **No files deleted yet** - Only organized. Review the Phase 2 recommendations before deleting anything.

---

**Cleanup Coordinator**: Claude Code
**Next Review**: 2026-02-15 (recommended)
