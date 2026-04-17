# Index Optimization Plan - Based on User Analysis

**Date**: 2026-02-20
**Status**: PLANNING PHASE - Ready for Implementation

---

## Summary of Issues Found

Based on database analysis and user notes, several index issues need correction:

### Current State vs Desired State

---

## 1. agata_catalog_attributes

**Current**: ✅ CORRECT
```
✅ id (PRIMARY KEY)
✅ gaia_id (INDEX) - single column
✅ attribute_name (INDEX)
✅ catalog_id (INDEX)
```

**Desired**: ✅ CORRECT
- gaia_id as indexed foreign key (not PK, correctly indexed)
- Supports fast lookup: `WHERE gaia_id = ?`

**Action**: ✅ NO CHANGES NEEDED

---

## 2. Cataloghi_esterni

**Current State** (PROBLEMATIC):
```
❌ catalog_import_id - Used as FK in composite indexes (idx_cataloghi_esterni_source_catalog)
❌ No clear PRIMARY KEY on Source (gaia_id)
❌ Multiple overlapping indexes:
    - idx_cataloghi_esterni_source_owner (Source, association_id_owner)
    - idx_cataloghi_esterni_source_catalog (Source, catalog_import_id)
    - idx_cataloghi_esterni_assoc_source (association_id_owner, Source)
    - idx_cataloghi_esterni_group_by (association_id_owner, Source, hjd)
    - idx_cataloghi_esterni_null_source (association_id_owner, Source)
```

**User's Requirements**:
- ❌ REMOVE: catalog_import_id from being a key (too much cardinality)
- ✅ CREATE: Index on Source (gaia_id) as PRIMARY concept
- ✅ CREATE: Index on association_id_owner as FK

**Desired State**:
```sql
-- PRIMARY: (Source, association_id_owner) - composite for GROUP BY operations
CREATE UNIQUE INDEX idx_cataloghi_esterni_source_assoc_pk
ON Cataloghi_esterni(Source, association_id_owner);

-- SECONDARY: Source only (for single-star lookups)
CREATE INDEX idx_cataloghi_esterni_source
ON Cataloghi_esterni(Source);

-- SECONDARY: association_id_owner only (for filtering by owner)
CREATE INDEX idx_cataloghi_esterni_assoc_owner
ON Cataloghi_esterni(association_id_owner);

-- REMOVE: idx_cataloghi_esterni_source_catalog
-- REASON: catalog_import_id should NOT be indexed (cardinality explosion)
```

**Action**: RESTRUCTURE
```sql
-- 1. Drop problematic indexes
DROP INDEX idx_cataloghi_esterni_source_catalog ON Cataloghi_esterni;
DROP INDEX idx_cataloghi_esterni_group_by ON Cataloghi_esterni;
DROP INDEX idx_cataloghi_esterni_null_source ON Cataloghi_esterni;

-- 2. Keep useful indexes
-- idx_cataloghi_esterni_source_owner ✓
-- idx_cataloghi_esterni_assoc_source ✓
-- idx_cataloghi_esterni_assoc_owner ✓

-- 3. Verify fk_catalog_import exists (for DELETE cascade)
-- Should exist but verify it's there
```

---

## 3. agata_star_assignments

**Current State** (MOSTLY CORRECT):
```
✅ id (PRIMARY KEY)
✅ gaia_id (INDEX) - ix_star_assignment_gaia_id
✅ association_id (INDEX) - ix_star_assignment_association
✅ project_id (FK) - fk_star_assignment_project
✅ assigned_by (FK) - fk_star_assignment_user
✅ UNIQUE: (gaia_id, association_id) - ix_star_assignment_unique
```

**User's Notes**:
- "ha gaia_id come chiave e association_id come chiave e project_id come chiave esterna"
- One assignment per (gaia_id, association_id)
- One project per assignment

**Desired State**: ✅ ALREADY CORRECT
```
The UNIQUE index (gaia_id, association_id) is perfect.
Ensures: Only ONE assignment per star per association.
```

**Action**: ✅ NO CHANGES NEEDED

---

## 4. agata_projects

**Current State** (HAS ISSUES):
```
❌ association_id (INDEX) - appears in 4 different indexes
   - idx_association
   - idx_association_state
   - idx_projects_assoc_state

❌ Multiple overlapping indexes on same columns:
   - idx_gaia_id
   - idx_projects_gaia_id (duplicate?)

❌ association_id indexed individually AND in composites (redundant)
```

**User's Notes**:
- "non deve avere association_id (da cancellare che c'è su agata_star_assignments dove c'è un solo progetto per associazione per stella)"
- ONE project per (gaia_id, association_id) pair
- association_id should NOT be a separate index

**Analysis**:
- agata_projects.association_id is NOT a foreign key (no explicit FK constraint)
- agata_star_assignments.association_id IS the FK (projects are accessed via assignments)

**Desired State**:
```sql
-- KEEP: PK on id
-- KEEP: project_code UNIQUE INDEX (for lookups)
-- KEEP: gaia_id INDEX (for finding projects by star)
-- KEEP: state INDEX (for filtering by state)
-- KEEP: assigned_to INDEX (for filtering by analyst)

-- REMOVE: All association_id indexes
--   Reason: association_id should be accessed via agata_star_assignments
--   Projects should be looked up: projects WHERE gaia_id = ? AND state != 'cancelled'
```

**Action**: CLEANUP
```sql
-- Remove redundant association_id indexes
DROP INDEX idx_association ON agata_projects;
DROP INDEX idx_association_state ON agata_projects;
DROP INDEX idx_projects_assoc_state ON agata_projects;

-- Keep useful indexes
-- idx_projects_gaia_id ✓
-- idx_state ✓
-- idx_assigned ✓
-- project_code ✓
```

---

## 5. agata_catalog_imports

**Current State**: ✅ CORRECT
```
✅ id (PRIMARY KEY)
✅ resolved_gaia_id (INDEX) - idx_import_gaia, idx_catalog_imports_resolved_gaia_id
✅ project_id (FK) - project_id
✅ target_association_id (FK) - target_association_id
✅ state (INDEX) - idx_import_state
✅ requested_by (INDEX) - idx_import_user
```

**User's Notes**:
- "id come pk e resolved_gaia_id come altra chiave"
- "project_id come FK (sto capendo a cosa serve)"
- "target_association_id come FK (sto capendo a cosa serve)"

**What These FKs Do**:
- `project_id`: If import is linked to a project (some imports are standalone searches)
- `target_association_id`: The association that requested this import (for permission checking)

**Desired State**: ✅ ALREADY CORRECT (no changes needed)

**Action**: ✅ NO CHANGES NEEDED

---

## 6. agata_star

**Current State** (NEEDS PRIMARY KEY):
```
✅ gaia_id (PRIMARY KEY)
✅ last_imported_at (INDEX)
✅ has_active_project (INDEX)
✅ is_known_variable (INDEX)
✅ min_mag, max_mag (COMPOSITE INDEX)
✅ num_assignments (COMPOSITE INDEX with has_active_project)
✅ latest_import_id (FK)
```

**User's Notes**:
- "gaia_id chiave con indice"
- "catalog_import_id come FK guarda se ti è utile"

**Analysis**:
- agata_star.gaia_id is already the PRIMARY KEY ✓
- catalog_import_id is NOT on agata_star currently
- latest_import_id is the import reference (points to agata_catalog_imports)

**Question from User**: "catalog_import_id come FK guarda se ti è utile"
- Looking at star_catalog.py, we query: `ci.id = s.latest_import_id`
- So latest_import_id IS the catalog_import FK, not catalog_import_id
- This is CORRECT - naming is just different

**Desired State**: ✅ ALREADY CORRECT
```
✅ gaia_id (PK)
✅ latest_import_id (FK to agata_catalog_imports)
✅ Indexes for filtering queries
```

**Action**: ✅ NO CHANGES NEEDED (verify FK constraint is present)

---

## Summary of Actions Required

| Table | Action | Priority | Risk |
|-------|--------|----------|------|
| agata_catalog_attributes | ✅ No changes | - | - |
| Cataloghi_esterni | 🔧 RESTRUCTURE indexes | HIGH | Medium (may need query analysis) |
| agata_star_assignments | ✅ No changes | - | - |
| agata_projects | 🔧 REMOVE association_id indexes | MEDIUM | Low |
| agata_catalog_imports | ✅ No changes | - | - |
| agata_star | ✅ Verify FK constraint | LOW | Low |

---

## Implementation Order

1. **Phase 1** (LOW RISK): Add FK constraint to agata_star
   - `ALTER TABLE agata_star ADD CONSTRAINT fk_star_latest_import FOREIGN KEY (latest_import_id) REFERENCES agata_catalog_imports(id) ON DELETE SET NULL;`
   - This clarifies the relationship

2. **Phase 2** (MEDIUM RISK): Clean up agata_projects indexes
   - Remove association_id indexes (they're accessed via agata_star_assignments)
   - Test queries to ensure no slowdown

3. **Phase 3** (HIGHER RISK): Restructure Cataloghi_esterni indexes
   - Remove catalog_import_id composite indexes
   - Keep Source-based lookups optimized
   - Test GROUP BY operations for performance

---

## Queries That Will Be Affected

### Affected by Cataloghi_esterni changes:
```sql
-- Current (with catalog_import_id in WHERE)
SELECT Source FROM Cataloghi_esterni WHERE catalog_import_id = 185;
-- Will still work, just won't use idx_cataloghi_esterni_source_catalog
-- WILL use: idx_cataloghi_esterni_source_owner or other composite
```

### Affected by agata_projects changes:
```sql
-- Current (filtering by association_id)
SELECT * FROM agata_projects WHERE association_id = 5;
-- Should still work via other indexes, or change to:
SELECT p.* FROM agata_projects p
JOIN agata_star_assignments sa ON sa.gaia_id = p.gaia_id
WHERE sa.association_id = 5;
-- But most queries don't filter by association_id directly on agata_projects
```

---

## Next Steps

1. Verify current query performance (use slow query log)
2. Implement Phase 1 (FK constraint - safe)
3. Implement Phase 2 (agata_projects cleanup - test first)
4. Implement Phase 3 (Cataloghi_esterni restructure - most critical)
5. Re-run performance tests to verify improvements

---

**User Review Required**:
- [ ] Approve Cataloghi_esterni index restructuring
- [ ] Confirm agata_projects should NOT have direct association_id access
- [ ] Confirm no other queries use association_id on agata_projects directly

