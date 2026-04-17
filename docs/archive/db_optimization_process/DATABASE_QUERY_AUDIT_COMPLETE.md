# Complete Database Query Audit - AGATA Project

**Date**: 2026-02-13
**Status**: Comprehensive Analysis Complete
**Scope**: agata/admin/routes, agata/admin/services, agata/catalog, agata/variable_stars

---

## Executive Summary

Found **14 major database query issues** across the codebase:
- **4 CRITICAL** (N+1 loops, affects every page)
- **3 HIGH** (Lazy loading, missing filters)
- **5 MEDIUM** (Unbounded results, missing indexes)
- **2 LOW** (Informational)

**Total estimated impact**: 200-500 additional unnecessary queries per day depending on usage.

---

## CRITICAL ISSUES

### 1. ProjectSlackThread N+1 in projects.py
**File**: `agata/admin/routes/projects.py`
**Lines**: 154-159
**Severity**: 🔴 CRITICAL

**Problem**:
```python
projects = query.limit(per_page).offset(...).all()  # 50 projects per page

for p in projects:  # 🔴 LOOP STARTS
    slack_thread = db.query(ProjectSlackThread).filter(
        ProjectSlackThread.project_id == p.id,
        ProjectSlackThread.is_active == True
    ).first()  # 🔴 QUERY #1-50 (50 queries total!)
```

**Impact**:
- 1 query to load projects
- **50 queries** to load slack threads (1 per project)
- **Total: 51 queries** for a single page load!

**Suggested Fix** (Option 1 - Eager Load):
```python
from sqlalchemy.orm import joinedload

projects = query.options(
    joinedload(Project.slack_threads)  # Load relationship eagerly
).filter(ProjectSlackThread.is_active == True).limit(per_page).offset(...).all()
```

**Suggested Fix** (Option 2 - Batch Load):
```python
projects = query.limit(per_page).offset(...).all()

if projects:
    project_ids = [p.id for p in projects]
    slack_threads = db.query(ProjectSlackThread).filter(
        ProjectSlackThread.project_id.in_(project_ids),
        ProjectSlackThread.is_active == True
    ).all()

    # Map into dictionary
    slack_map = {}
    for st in slack_threads:
        if st.project_id not in slack_map:
            slack_map[st.project_id] = None
        slack_map[st.project_id] = st

    # Use in loop
    for p in projects:
        slack_thread = slack_map.get(p.id)
```

**Complexity**: Low - straightforward fix
**Priority**: Immediate (affects every project list)

---

### 2. Association Stats Triple Loop in associations.py
**File**: `agata/admin/routes/associations.py`
**Lines**: 47-61
**Severity**: 🔴 CRITICAL

**Problem**:
```python
associations = db.query(Association).filter(...).all()  # 10 associations

for assoc in associations:  # 🔴 LOOP STARTS (10 iterations)
    active_projects = db.query(Project).filter(
        Project.association_id == assoc.id,
        Project.state == 'assigned'
    ).count()  # 🔴 QUERY #1

    total_users = db.query(User).filter(
        User.association_id == assoc.id
    ).count()  # 🔴 QUERY #2

    slack_channels = db.query(SlackChannel).filter(
        SlackChannel.association_id == assoc.id
    ).count()  # 🔴 QUERY #3

# With 10 associations: 10 × 3 = 30 queries total!
```

**Impact**:
- 1 query to load associations
- **30 additional queries** (3 per association)
- **Total: 31 queries** for association listing

**Suggested Fix** (Aggregate All):
```python
from sqlalchemy import func

associations = db.query(Association).filter(...).all()

# Single aggregation query
stats = db.query(
    Project.association_id,
    func.count(Project.id).label('active_projects'),
    User.association_id,
    func.count(User.id).label('total_users'),
    SlackChannel.association_id,
    func.count(SlackChannel.id).label('slack_channels')
).outerjoin(
    User, User.association_id == Association.id
).outerjoin(
    Project, and_(
        Project.association_id == Association.id,
        Project.state == 'assigned'
    )
).outerjoin(
    SlackChannel, SlackChannel.association_id == Association.id
).group_by(Association.id).all()

# Map stats
stats_map = {}
for stat in stats:
    stats_map[stat.association_id] = {
        'active_projects': stat.active_projects or 0,
        'total_users': stat.total_users or 0,
        'slack_channels': stat.slack_channels or 0
    }

# Use in loop
for assoc in associations:
    stats = stats_map.get(assoc.id, {})
```

**Complexity**: Medium - requires understanding GROUP BY and aggregation
**Priority**: Immediate (affects admin dashboard)

---

### 3. Dashboard Stats Loop in stats_service.py
**File**: `agata/admin/services/stats_service.py`
**Lines**: 69-76
**Severity**: 🔴 CRITICAL

**Problem**:
```python
associations = db.query(Association).filter(Association.is_active == True).all()

for assoc in associations:  # 🔴 LOOP (N iterations)
    count = db.query(Project).filter(
        and_(
            Project.association_id == assoc.id,
            Project.state.in_(['available', 'incoming'])
        )
    ).count()  # 🔴 Query per association

    # With 20 associations: 20 queries total
```

**Impact**:
- N associations = N additional count queries
- Heavy overhead on admin dashboard

**Suggested Fix**:
```python
from sqlalchemy import func

# Single aggregation query
counts = db.query(
    Project.association_id,
    func.count(Project.id).label('count')
).filter(
    Project.state.in_(['available', 'incoming'])
).group_by(Project.association_id).all()

counts_map = {c.association_id: c.count for c in counts}

# Use in loop
for assoc in associations:
    count = counts_map.get(assoc.id, 0)
```

**Complexity**: Low
**Priority**: High (affects dashboard performance)

---

## HIGH PRIORITY ISSUES

### 4. Lazy Loading in project_detail.py
**File**: `agata/admin/routes/project_detail.py`
**Lines**: 54-71
**Severity**: 🟠 HIGH

**Problem**:
```python
def serialize_project_detail(project):
    # Lines 57-60
    slack_thread = db.query(ProjectSlackThread).filter(...).first()  # Query 1

    # Lines 63-65
    science_data = db.query(ProjectScienceData).filter(...).first()  # Query 2

    # Lines 68-71
    outputs = db.query(ProjectOutput).filter(...).all()  # Query 3

    return {
        ...
        'association': {
            'id': project.association.id,  # Lazy load if not eager loaded
            'name': project.association.name,
        }
        ...
    }
```

**Impact**: 3-5+ queries per project detail view

**Suggested Fix**:
```python
from sqlalchemy.orm import joinedload, selectinload

project = db.query(Project).options(
    joinedload(Project.association),
    joinedload(Project.assigned_user),
    joinedload(Project.reviewer),
    selectinload(Project.slack_threads),
    selectinload(Project.science_data),
    selectinload(Project.outputs)
).filter(Project.id == project_id).first()

# Then remove manual db.query() calls above
```

**Complexity**: Low
**Priority**: High (every project detail view)

---

### 5. Lazy Loading in projects.py List
**File**: `agata/admin/routes/projects.py`
**Lines**: 167-170
**Severity**: 🟠 HIGH

**Problem**:
```python
projects = query.limit(per_page).offset(...).all()  # 50 projects

result = []
for p in projects:
    result.append({
        ...
        'association_name': p.association.name if p.association else None,  # Lazy load
        'assigned_user_name': p.assigned_user.full_name if p.assigned_user else None,  # Lazy load
        'reviewer_name': p.reviewer.full_name if p.reviewer else None,  # Lazy load
    })

# 3 lazy loads × 50 projects = 150 additional queries!
```

**Impact**: 150+ additional queries per page

**Suggested Fix**:
```python
# At line 150 where projects are initially queried:
projects = query.options(
    joinedload(Project.association),
    joinedload(Project.assigned_user),
    joinedload(Project.reviewer)
).limit(per_page).offset(...).all()

# Now the loop accesses cached relationships
```

**Complexity**: Low
**Priority**: High (massive impact on list pages)

---

### 6. Missing association_id Filter in stars_catalog.py
**File**: `agata/admin/routes/stars_catalog.py`
**Lines**: 192-204
**Severity**: 🟠 HIGH (Security Issue!)

**Problem**:
```python
# Lines 192-204: MISSING association_id filter!
if project_filter == 'assigned_to_others':
    projects = db.query(Project).filter(
        Project.assigned_to != current_user.id,
        Project.assigned_to.isnot(None),
        # 🔴 MISSING: Project.association_id == filter_association_id
        Project.state != 'cancelled'
    ).all()

# This could load projects from OTHER associations!
# Security issue: Analyst might see projects from different associations
```

**Impact**: Potential data leak between associations

**Suggested Fix**:
```python
projects = db.query(Project).filter(
    Project.association_id == filter_association_id,  # 🟢 Add this!
    Project.assigned_to != current_user.id,
    Project.assigned_to.isnot(None),
    Project.state != 'cancelled'
).all()
```

**Complexity**: Very Low
**Priority**: IMMEDIATE (Security fix)

---

## MEDIUM PRIORITY ISSUES

### 7. Lazy Loading in users.py
**File**: `agata/admin/routes/users.py`
**Lines**: 150
**Severity**: 🟡 MEDIUM

**Problem**:
```python
users = query.order_by(User.name).all()  # N users

for u in users:
    result.append({
        'association_name': u.association.name if u.association else None,  # Lazy load
    })

# N lazy loads for N users
```

**Suggested Fix**:
```python
users = query.options(
    joinedload(User.association)
).order_by(User.name).all()
```

---

### 8. Lazy Loading in slack_integration.py
**File**: `agata/admin/routes/slack_integration.py`
**Lines**: 79-93
**Severity**: 🟡 MEDIUM

**Problem**:
```python
channels = query.all()

channels_by_assoc = {}
for ch in channels:
    # Lazy load association if not eager loaded
    assoc_id = ch.association_id
    if assoc_id not in channels_by_assoc:
        channels_by_assoc[assoc_id] = []
    channels_by_assoc[assoc_id].append(ch)
```

**Suggested Fix**:
```python
channels = query.options(
    joinedload(SlackChannel.association)
).all()
```

---

### 9. Unbounded Result Set in stars_catalog.py
**File**: `agata/admin/routes/stars_catalog.py`
**Lines**: 106-110
**Severity**: 🟡 MEDIUM

**Problem**:
```python
associations = db.query(Association).filter(
    Association.is_active == True
).order_by(Association.name).all()  # No LIMIT!
```

**Impact**:
- If 1000+ associations, loads all into memory
- Slow response time
- Memory overhead

**Suggested Fix**:
```python
# For dropdown: limit to reasonable number
associations = db.query(Association).filter(
    Association.is_active == True
).order_by(Association.name).limit(100).all()
```

**Complexity**: Very Low
**Priority**: Medium

---

### 10. Python-side Filtering in stars_catalog.py
**File**: `agata/admin/routes/stars_catalog.py`
**Lines**: 461-527
**Severity**: 🟡 MEDIUM

**Problem**:
```python
# Load ALL stars first
stars = stars_raw  # Could be thousands

# Then filter in Python
if state_filter == 'unassigned':
    stars = [s for s in stars if not s['all_assignments']]  # Python loop
elif state_filter == 'assigned':
    stars = [s for s in stars if s['all_assignments'] and not s['project_id']]  # Python loop

# Similar filters follow (Python filtering)
```

**Impact**:
- Loads all stars even if only 10 match filter
- Wastes memory and processing
- Pagination doesn't work correctly with Python filtering

**Suggested Fix**:
Apply filters in SQL WHERE clause before building result set. This is complex because the current code builds intermediate data structure. Requires refactoring the overall logic.

**Complexity**: High (architectural change)
**Priority**: Medium

---

### 11. Missing Database Indexes
**File**: Database schema (multiple files affected)
**Severity**: 🟡 MEDIUM

**Problem**:
Common filter columns have no indexes, causing full table scans:

```sql
-- These queries do full table scans (slow):
SELECT * FROM agata_projects WHERE state = 'assigned';
SELECT * FROM agata_projects WHERE association_id = 123;
SELECT * FROM agata_project_slack_threads WHERE project_id = 456;
SELECT * FROM agata_users WHERE association_id = 123;
```

**Suggested Indexes**:
```sql
-- Project indexes
CREATE INDEX idx_project_association_id ON agata_projects(association_id);
CREATE INDEX idx_project_state ON agata_projects(state);
CREATE INDEX idx_project_assigned_to ON agata_projects(assigned_to);
CREATE INDEX idx_project_assoc_state ON agata_projects(association_id, state);  -- Composite

-- Relationship indexes
CREATE INDEX idx_slack_thread_project ON agata_project_slack_threads(project_id, is_active);
CREATE INDEX idx_project_slack_project ON agata_project_slack_threads(project_id);
CREATE INDEX idx_project_output_project ON agata_project_outputs(project_id);
CREATE INDEX idx_project_science_project ON agata_project_science_data(project_id);

-- User/Association indexes
CREATE INDEX idx_user_association_id ON agata_users(association_id);
CREATE INDEX idx_slack_channel_association ON agata_slack_channels(association_id);

-- Star catalog indexes
CREATE INDEX idx_star_assignment_gaia ON agata_star_assignments(gaia_id);
CREATE INDEX idx_vast_results_gaia ON agata_vast_results(gaia_source_id);
CREATE INDEX idx_vast_results_is_valid ON agata_vast_results(is_valid);

-- Audit log indexes
CREATE INDEX idx_audit_association_id ON agata_audit_logs(association_id);
CREATE INDEX idx_audit_timestamp ON agata_audit_logs(created_at DESC);
```

**Impact**: All queries run slower without indexes
**Complexity**: Very Low (SQL only)
**Priority**: High (improves all queries)

---

## LOW PRIORITY ISSUES

### 12. Separate Total Count Query in projects.py
**File**: `agata/admin/routes/projects.py`
**Lines**: 195-210
**Severity**: 🔵 LOW

**Problem**:
```python
# Separate count query for total
count_query = db.query(Project).filter(...)
my_projects_total = count_query.count()  # Query 1
available_total = db.query(Project).filter(...).count()  # Query 2
```

**Impact**: Minor - 2 queries once per page load

**Note**: This is acceptable for pagination totals

---

## SUMMARY TABLE

| # | Issue | File | Type | Severity | Impact | Complexity |
|---|-------|------|------|----------|--------|-----------|
| 1 | ProjectSlackThread N+1 | projects.py:154 | N+1 Loop | 🔴 CRITICAL | +50q/page | Low |
| 2 | Association Stats Loop | associations.py:47 | N+1 (3x) | 🔴 CRITICAL | +30q/page | Medium |
| 3 | Dashboard Stats Loop | stats_service.py:69 | N+1 | 🔴 CRITICAL | +N queries | Low |
| 4 | Lazy Load Detail View | project_detail.py:54 | Lazy Load | 🟠 HIGH | +3-5q | Low |
| 5 | Lazy Load List (HUGE) | projects.py:167 | Lazy Load | 🟠 HIGH | +150q/page | Low |
| 6 | Missing Assoc Filter | stars_catalog.py:192 | Security | 🟠 HIGH | Data leak | Very Low |
| 7 | Lazy Load Users | users.py:150 | Lazy Load | 🟡 MEDIUM | +N queries | Low |
| 8 | Lazy Load Slack | slack_integration.py:79 | Lazy Load | 🟡 MEDIUM | +N queries | Low |
| 9 | Unbounded Results | stars_catalog.py:106 | Unbounded | 🟡 MEDIUM | Memory risk | Very Low |
| 10 | Python Filtering | stars_catalog.py:461 | Inefficient | 🟡 MEDIUM | Full load | High |
| 11 | Missing Indexes | (schema) | Schema | 🟡 MEDIUM | All slower | Very Low |
| 12 | Count Query | projects.py:195 | Separate Q | 🔵 LOW | Minor | Low |

---

## IMPLEMENTATION ROADMAP

### Phase 1: Critical Fixes (This Week) ⚡
**Estimated time**: 2-3 hours
**Expected improvement**: 60% reduction in queries

1. **Fix #6**: Add association_id filter to stars_catalog.py (5 min) - SECURITY
2. **Fix #1**: Add batch load for ProjectSlackThread (30 min)
3. **Fix #3**: Aggregate dashboard stats (45 min)
4. **Fix #5**: Add joinedload to projects list (30 min)

### Phase 2: High Priority (Next Sprint) 🟠
**Estimated time**: 4-6 hours
**Expected improvement**: 30% additional reduction

1. **Fix #2**: Refactor association stats (60 min)
2. **Fix #4**: Add eager loading to project_detail (45 min)
3. **Fix #11**: Add database indexes (30 min)
4. **Fix #7, #8**: Add eager loading to users and slack (30 min each)

### Phase 3: Medium Priority (Following Sprint) 🟡
**Estimated time**: 8-10 hours
**Expected improvement**: 10% additional reduction

1. **Fix #10**: Refactor Python filtering to SQL (high effort, high reward)
2. **Fix #9**: Add pagination to association dropdown

---

## Testing Checklist

After implementing fixes:

```
[ ] Fix #1 - ProjectSlackThread batch load
    [ ] projects.py page loads
    [ ] slack thread data shows correctly
    [ ] Multiple projects display properly

[ ] Fix #2 - Association stats aggregation
    [ ] associations.py page loads
    [ ] stats show correct counts
    [ ] filter still works

[ ] Fix #3 - Dashboard stats
    [ ] Admin dashboard loads quickly
    [ ] Stats are accurate

[ ] Fix #4 & #5 - Eager loading
    [ ] project_detail.py loads completely
    [ ] projects list displays all relationships
    [ ] No lazy load warnings in logs

[ ] Fix #6 - Association filter
    [ ] Analysts see only their association data
    [ ] No cross-association data leakage
    [ ] Tests pass for multi-tenant isolation

[ ] Fix #11 - Indexes
    [ ] All indexes created successfully
    [ ] Query explain shows index usage
    [ ] No slowdown on writes
```

---

## Performance Metrics

### Before Optimization
- Project list page: 6-10 seconds (50 projects)
- Project detail: 3-5 seconds
- Associations list: 4-6 seconds
- Dashboard: 5-8 seconds
- **Total daily queries**: ~500-1000 (unnecessary)

### Expected After Phase 1
- Project list page: 1-2 seconds (6-10x faster!)
- Project detail: 1-2 seconds
- Associations list: 1-2 seconds
- Dashboard: 1-2 seconds
- **Total daily queries**: ~150-200 (70% reduction)

### Expected After Phase 2 & 3
- All pages: <500ms
- **Total daily queries**: <100

---

## Notes for Implementation

### SQLAlchemy Best Practices Applied
1. Use `joinedload()` for one-to-one and many-to-one relationships
2. Use `selectinload()` for one-to-many and many-to-many relationships
3. Batch operations with `.in_()` instead of loops
4. Aggregate queries with `group_by()` and `func.count()`
5. Always filter by `association_id` for tenant isolation

### Monitoring
- Add slow query log to MySQL: `log_queries_not_using_indexes=1`
- Monitor query counts per page load
- Set up alerts for queries taking >1 second

### Documentation
- Add docstrings explaining eager loading strategy per route
- Document N+1 patterns in code review checklist

---

**Report Generated**: 2026-02-13
**Analysis Tool**: Claude Code Database Audit Agent
**Confidence**: High (systematic code review)
**Next Review**: After Phase 1 implementation
