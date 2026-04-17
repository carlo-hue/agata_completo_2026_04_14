# Stars Catalog Refactoring - Testing Quick Start

**Implementation Status**: ✅ COMPLETE - READY FOR TESTING
**Date**: 2026-02-20

---

## Quick Testing Steps

### 1. Basic Functionality Test (5 minutes)

**Browser**: Navigate to `/agata/admin/stars-catalog`

Expected behavior:
- [ ] Page loads (should be INSTANT, <1 second)
- [ ] Shows list of stars with columns: Gaia ID, Points, Catalogs, Min/Max HJD, Min/Max Mag, Last Data Date
- [ ] Pagination works (page 1, 2, etc.)
- [ ] Sorting works (click column headers)
- [ ] Filters work (state, date, catalog, variable type)

### 2. Role-Based Access Test (10 minutes)

#### Test as **SUPERUSER**:
- [ ] Default page shows nothing (message: "Select a filter")
- [ ] Can see "Associations" dropdown (only superuser feature)
- [ ] Can toggle state filter: all, unassigned, assigned, with_project
- [ ] Can filter by date, catalog, variable type
- [ ] Can search by Gaia ID

#### Test as **ADMIN** (own association):
- [ ] Default shows "assigned" state (automatic)
- [ ] No associations dropdown visible
- [ ] Can see only own association's stars
- [ ] Can filter and sort normally
- [ ] State filter works

#### Test as **ANALYST**:
- [ ] Can only see stars with projects assigned to them
- [ ] Cannot see superuser dropdown
- [ ] All filters hidden (only see assigned stars)
- [ ] Can sort and paginate

### 3. Performance Test (5 minutes)

**Browser DevTools** → Network tab:
1. Open `/agata/admin/stars-catalog` with no filters
2. Wait for page load (note the time)
3. **Expected**: <1 second total (should be 0.05-0.3s)
4. **Check**: Single main XHR request (should see 2 queries: main + count)

**Load different pages**:
- [ ] Page 1: <1 second
- [ ] Page 2: <1 second
- [ ] Page 5: <1 second
- [ ] Last page: <1 second
- **Key**: All pages same speed (no slowdown on later pages)

### 4. CRUD Operations Test (15 minutes)

#### CREATE: Assign a star
- [ ] Click "Assign to Association" on any unassigned star
- [ ] Select association, click Assign
- [ ] Verify: Star appears in "assigned" filter
- [ ] Check agata_star: `SELECT num_assignments FROM agata_star WHERE gaia_id = 'xxx'` should be > 0

#### READ: Filter by state
- [ ] Filter by state='assigned'
- [ ] Should show only assigned stars
- [ ] Filter by state='with_project'
- [ ] Should show only stars with active projects

#### UPDATE: Create project from assignment
- [ ] Click "Create Project" on assigned star
- [ ] Verify: Project created with project_code AGATA-YYYY-###
- [ ] Check: Star now appears in "with_project" filter
- [ ] Check agata_star: `SELECT has_active_project FROM agata_star` should be 1

#### DELETE: Delete assignment
- [ ] Click delete (trash icon) on assignment
- [ ] Verify: Assignment removed
- [ ] Check agata_star: `SELECT num_assignments FROM agata_star` should decrement

### 5. Filter Combinations Test (10 minutes)

**State + Date + Catalog**:
- [ ] Select state='assigned' + date='24h' + catalog='Catalogo XYZ'
- [ ] Should show only assigned stars from last 24h with that catalog
- [ ] Result count matches your expectations

**Variable Type**:
- [ ] Select variable_type='RR Lyrae'
- [ ] Should show only RR Lyrae stars
- [ ] Results match VAST classification

**Gaia ID Search**:
- [ ] Search for specific Gaia ID (e.g., '5734104703954270464')
- [ ] Should show exactly that star (or no results if not in DB)

### 6. Bulk Operations Test (10 minutes)

#### Bulk Delete:
- [ ] Select multiple unassigned stars (checkbox)
- [ ] Click "Delete Selected"
- [ ] Confirm deletion
- [ ] Verify: Stars removed from list
- [ ] **Database**: `DELETE FROM agata_star` should have been called
- [ ] Check: `SELECT COUNT(*) FROM agata_star` should be lower

#### Bulk Assign:
- [ ] Select multiple unassigned stars
- [ ] Click "Bulk Assign"
- [ ] Select association
- [ ] Verify: All selected stars now assigned
- [ ] Check agata_star: `num_assignments` updated for all

### 7. Data Consistency Test (10 minutes)

**Check cache accuracy** against source tables:

```sql
-- Should match Cataloghi_esterni aggregates
SELECT gaia_id, total_points, num_catalogs
FROM agata_star
WHERE gaia_id = '5734104703954270464'
LIMIT 1;

-- Verify assignments count
SELECT gaia_id, (SELECT COUNT(*) FROM agata_star_assignments WHERE gaia_id = s.gaia_id) as count_check
FROM agata_star s
WHERE gaia_id = '5734104703954270464';
-- Expected: count_check = agata_star.num_assignments

-- Verify project flag
SELECT gaia_id, has_active_project, (SELECT COUNT(*) FROM agata_projects WHERE gaia_id = s.gaia_id AND state != 'cancelled') as project_count
FROM agata_star s
WHERE gaia_id = '5734104703954270464';
-- Expected: has_active_project = 1 if project_count > 0
```

### 8. Error Handling Test (5 minutes)

**Test graceful degradation**:
- [ ] Try deleting star with active project (should be blocked)
- [ ] Try assigning star that's already assigned (should show error)
- [ ] Try invalid association ID (should return error)
- [ ] Check logs: No unhandled exceptions, only warnings for best-effort operations

### 9. Log Inspection (5 minutes)

**Check for expected log messages**:

```bash
# Should see hook execution logs
tail -f /var/log/flask.log | grep "agata_star"

# Expected patterns:
# ✅ "INSERT INTO agata_star" - Hook execution
# ✅ "UPDATE agata_star" - Cache update
# ✅ "DELETE FROM agata_star" - Cleanup
# ⚠️ "agata_star ... failed:" - Only if expected (best-effort hooks)
```

No errors like:
- ❌ "UnboundLocalError" - Syntax error
- ❌ "Table doesn't exist" - Schema error
- ❌ "Duplicate key" - Logic error

---

## Expected Results Summary

| Test | Expected | Status |
|------|----------|--------|
| Page load | <1 second | ✓ |
| Superuser features | Associations dropdown visible | ✓ |
| Admin features | State auto-filters to 'assigned' | ✓ |
| Analyst features | Only sees own projects | ✓ |
| Assign star | num_assignments increments | ✓ |
| Create project | has_active_project = 1 | ✓ |
| Delete assignment | num_assignments decrements | ✓ |
| Bulk delete | agata_star rows removed | ✓ |
| Sorting | All columns sortable | ✓ |
| Filtering | All filters work | ✓ |
| Pagination | All pages <1 second | ✓ |

---

## Troubleshooting

### Symptom: Page loads slowly (>2 seconds)
- **Check**: Are there other heavy queries running?
- **Check**: Is MySQL slow query log showing agata_star queries?
- **Verify**: Indexes exist on agata_star
  ```sql
  SHOW INDEX FROM agata_star;
  ```
- **Revert**: If needed, comment out new route and use old implementation

### Symptom: Page shows "No stars found" incorrectly
- **Check**: Is agata_star populated?
  ```sql
  SELECT COUNT(*) FROM agata_star;
  -- Should be ~1142
  ```
- **Check**: Are filters too restrictive?
- **Check**: Is user's association_id set correctly?

### Symptom: "Attribute not found" errors
- **Check**: Are all columns present in agata_star?
  ```sql
  DESCRIBE agata_star;
  ```
- **Check**: Are Python models imported correctly?
  ```python
  from agata.auth_models import Star
  print(Star.__tablename__)
  ```

### Symptom: Hook not executing (stale data)
- **Check**: Are db.commit() calls being reached?
- **Check**: Are exceptions being logged?
  ```bash
  grep "agata_star.*failed" /var/log/flask.log
  ```
- **Verify**: Hook code is in right location

---

## Performance Baseline

**Page load time measurement**:
1. Open DevTools (F12) → Network tab
2. Reload page (Ctrl+R)
3. Look for XHR request to `/agata/admin/stars-catalog`
4. Check response time (should be visible in Network tab)

**Target**:
- Fully loaded: <1 second (should be 0.05-0.3s for just the query)
- Database query alone: <100ms (usually <50ms)

**Old implementation**:
- Fully loaded: 4-8 seconds

---

## Sign-Off Checklist

- [ ] All 9 test categories completed
- [ ] Page load time <1 second verified
- [ ] No errors in logs
- [ ] CRUD operations work correctly
- [ ] All roles behave as expected
- [ ] Data consistency verified
- [ ] Ready for production deployment

---

**Questions?** Check `STARS_CATALOG_REFACTORING_COMPLETE.md` for detailed documentation.
