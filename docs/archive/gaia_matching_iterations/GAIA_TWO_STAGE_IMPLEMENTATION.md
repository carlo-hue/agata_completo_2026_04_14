# Gaia Two-Stage Cross-Matching Implementation - COMPLETE ✅

**Date**: 2026-02-17
**Status**: ✅ READY FOR TESTING
**Branch**: main

---

## Summary

Completely rewrote the Gaia cross-matching algorithm for VAST image analysis with a two-stage Vizier approach:
1. **Stage 1**: Tight 10" radius with Vmag compatibility filtering (tolerance 2.0 mag)
2. **Stage 2**: Fallback to 100" radius with magnitude-first ordering (all results marked ambiguous)

Key improvements:
- ✅ Uses **Vizier wrapper** instead of Gaia TAP (no login required, stable)
- ✅ Compares **VAST magnitude with Gaia Vmag** (not just position)
- ✅ Marks Stage 2 results as **ambiguous** (distance > 10")
- ✅ Sets `gaia_source_id=NULL` for ambiguous matches (enables manual selection UI)
- ✅ Calculates `is_ambiguous` field and persists to database
- ✅ Preserves existing manual selection UI in template

---

## Files Modified

### 1. **agata/admin/services/vast_service.py**

#### Function: `_gaia_worker_query_single_star()` (lines 64-246)
**COMPLETELY REWRITTEN** - Now implements two-stage Vizier query with Vmag filtering

**Changes**:
- **Before**: Gaia TAP with login, fixed 30" radius
- **After**: Vizier cone search, two-stage (10" + 100") with magnitude validation

**Stage 1 Logic (lines 99-167)**:
```python
# Query 10" radius
rows_10 = vizier_client.query_cone(..., radius_arcsec=10, ...)

# Filter by Vmag compatibility: |Vmag_gaia - VAST_mag| <= 2.0
compatible = [c for c in candidates_10 if c['vmag'] and abs(c['vmag'] - vast_mag) <= 2.0]

# Return closest compatible
# is_ambiguous=False, gaia_source_id=<selected>
```

**Stage 2 Logic (lines 169-237)**:
```python
# Query 100" radius (only if Stage 1 fails)
rows_100 = vizier_client.query_cone(..., radius_arcsec=100, ...)

# Sort by magnitude similarity (Δmag), then distance
candidates_100.sort(key=lambda x: (x['delta_mag'], x['distance']))

# Always ambiguous (distance > 10" guaranteed)
# is_ambiguous=True, gaia_source_id=None
```

**Key Features**:
- Uses existing `_calculate_vmag_from_gaia()` function (Gaia EDR3 formula)
- Calculates distance with SkyCoord.separation() (astropy)
- Returns `is_ambiguous` field (boolean)
- Returns `gaia_candidates` list (top 5/10 candidates for manual selection)
- Returns `gaia_source_id=None` for Stage 2 (ambiguous) to enable UI selection

#### Function: `_crossmatch_gaia()` (lines 1187-1332)
**MODIFIED** - Updated parameter passing and result merge

**Changes**:
- Line 1230: Changed column selection from `['ra', 'dec', 'name']` to `['ra', 'dec', 'name', 'Median_magnitude']`
  - **Critical fix**: Median_magnitude must be available in stars_valid for worker function
  - Ensures raw magnitude (9.827 for out31321) is passed to worker
- Line 1253: Changed from `(row['name'], row['ra'], row['dec'], match_radius_arcsec, GAIA_USER, GAIA_PWD)`
- To: `(row['name'], row['ra'], row['dec'], match_radius_arcsec, row['Median_magnitude'])`
- **Now passes raw Median_magnitude** (GREZZO: 9.827 for out31321, NOT calibrated 12.168)
- Updated parameter from 30 to 10 for Stage 1 radius

**Result Merge (lines 1278-1295)**:
- Added `is_ambiguous` to merge columns
- Ensured `is_ambiguous` is bool type
- Properly handles both Stage 1 (is_ambiguous=False) and Stage 2 (is_ambiguous=True)

**Fallback Handling (lines 1316-1329)**:
- Added `is_ambiguous=False` when no matches found
- Added `is_ambiguous=False` when exception occurs

#### VastResult Creation (line 1906)
**MODIFIED** - Added is_ambiguous field to database insert:
```python
is_ambiguous=candidate.get('is_ambiguous', False),
```

#### Logging Fix (lines 97-98)
**FIXED** - Corrected f-string formatting for vast_mag:
```python
vast_mag_str = f"{vast_mag:.2f}" if vast_mag else "N/A"
logger_worker.info(f"[GAIA TWO-STAGE] Star {name} @ RA={ra:.6f}, Dec={dec:.6f}, VAST_mag={vast_mag_str}")
```

---

### 2. **agata/auth_models/vast_job.py**

#### VastResult Model (line 282)
**ADDED** - New field for database persistence:
```python
is_ambiguous: Mapped[bool] = mapped_column(
    Boolean, default=False, nullable=False,
    comment="True if Gaia match is ambiguous (Stage 2 fallback or distance >10\")"
)
```

**Purpose**:
- Stores ambiguity flag in database (not just in-memory)
- Enables template to display visual indicators
- Used for backend logic (e.g., re-matching, manual selection)

---

### 3. **agata/templates/admin/vast/job_detail.html**

#### Gaia Source ID Column (lines 319-332)
**MODIFIED** - Added visual indicators for ambiguous matches:

```html
{% if result.gaia_source_id %}
    <a href="..." target="_blank" class="font-monospace small">
        {{ result.gaia_source_id }}
    </a>
    {% if result.is_ambiguous %}
        <span class="badge bg-warning text-dark ms-2" title="...">⚠</span>
    {% endif %}
{% else %}
    <span class="text-muted small">-</span>
    {% if result.is_ambiguous %}
        <span class="badge bg-danger ms-2" title="...">Ambiguous</span>
    {% endif %}
{% endif %}
```

**Behavior**:
- If `gaia_source_id` exists + `is_ambiguous=True`: Shows ⚠ warning badge (Stage 2 fallback with match)
- If `gaia_source_id=None` + `is_ambiguous=True`: Shows "Ambiguous" badge (requires manual selection)
- If `gaia_source_id` exists + `is_ambiguous=False`: No badge (confident Stage 1 match)

---

## Algorithm Behavior

### Example: out31321 (VAST mag = 9.827)

**Stage 1 (10" radius)**:
- Queries Vizier, finds 1 candidate: Gaia 5734104703954270720 (Gmag 16.516, Vmag 16.742)
- Calculates Δmag = |16.742 - 9.827| = 6.915
- Filters: 6.915 > 2.0 → **NOT COMPATIBLE** ❌
- Result: Stage 1 returns 0 compatible matches

**Stage 2 (100" fallback)**:
- Queries Vizier, finds 10+ candidates
- All have Vmag calculated, sorted by (Δmag, distance)
- Top candidate: Gaia 5734104703954270464 (Gmag 7.853, Vmag 7.895, distance 13.94", Δmag 1.93)
- Δmag = 1.93 < 2.0 → **COMPATIBLE** ✅
- Distance > 10" → **ALWAYS AMBIGUOUS** for Stage 2
- Returns: `is_ambiguous=True`, `gaia_source_id=None`, `gaia_candidates=[10 options]`

**Template Display**:
- Badge: "Ambiguous" (red) - indicates manual selection available
- Checkboxes in detail view allow user to retry matching or select manually

---

## Testing

### Syntax Verification ✅
```bash
$ python -m py_compile agata/admin/services/vast_service.py
$ python -m py_compile agata/auth_models/vast_job.py
✅ All syntax checks passed
```

### Functional Testing ✅
Tested with out31321 test case:
- ✅ Stage 1 correctly finds incompatible matches and falls through
- ✅ Stage 2 finds correct compatible match (Gaia 5734104703954270464)
- ✅ is_ambiguous correctly set to True (Stage 2)
- ✅ gaia_source_id correctly set to None (enables manual UI)
- ✅ gaia_candidates list populated with 10 options

---

## Magnitude Validation

### VAST Magnitude Source
**GREZZO (Raw/Uncalibrated)**:
- Source: `vast_lightcurve_statistics.log` column `Median_magnitude`
- Value for out31321: **9.827**
- NOT post-Gaia-calibrated (that would be 12.168)

### Gaia Vmag Calculation
**EDR3 Formula**:
```
Vmag = gmag + 0.02704 - 0.01424*BP_RP + 0.2156*BP_RP² - 0.01426*BP_RP³
```
- Implemented in: `_calculate_vmag_from_gaia()` function
- Returns None if BP-RP unavailable (candidate excluded from filter)

### Compatibility Tolerance
**Stage 1**: |Vmag_gaia - VAST_mag| ≤ 2.0 mag
- Typical match: within 1-2 mag
- Strict filter prevents false positives

**Stage 2**: No initial filter, sorted by similarity
- All candidates evaluated
- Closest in magnitude selected first

---

## Database Schema

### New Column: is_ambiguous
**Table**: `agata_vast_results`
**Type**: BOOLEAN
**Default**: FALSE
**Nullable**: NO
**Comment**: "True if Gaia match is ambiguous (Stage 2 fallback or distance >10\")"

### Migration (if applying to existing DB)
```sql
ALTER TABLE agata_vast_results
ADD COLUMN is_ambiguous BOOLEAN DEFAULT 0 NOT NULL
COMMENT 'True if Gaia match is ambiguous (Stage 2 fallback)';
```

---

## Performance Impact

### Parallel Execution
- **Workers**: 4 (ProcessPoolExecutor)
- **Queries per star**: 1-2 Vizier queries (Stage 1 + optional Stage 2)
- **Expected performance**: ~0.12-0.15 seconds per star (689 stars in ~90 seconds)
- **Bottleneck**: Vizier network latency (not local computation)

### Stage Distribution (Estimated)
- **Stage 1 success**: ~60-80% of stars (within 10" + compatible mag)
- **Stage 2 fallback**: ~20-40% of stars (outside 10" or incompatible mag)
- **No match**: <5% (likely isolated stars)

---

## Backward Compatibility

✅ **100% Backward Compatible**

- Old VAST job results: No changes (they remain with old gaia_source_id values)
- New jobs: Use new algorithm, new is_ambiguous field
- Manual selection UI: **PRESERVED** (critical requirement)
- API responses: Same format
- Database: New column only, no existing data affected

---

## Known Limitations & Design Decisions

### 1. Stage 1 Radius (10")
**Design**: Tight radius ensures high confidence matches
**Tradeoff**: Some valid matches fall into Stage 2 (marked ambiguous)
**Rationale**: False positives worse than false negatives; user can manually select

### 2. Magnitude Tolerance (2.0 mag)
**Design**: Allows ±2 mag difference between VAST and Gaia
**Rationale**: Accounts for different magnitude systems and calibration uncertainties
**Note**: Post-calibration tolerance is stricter (0.5 mag) in `_scale_vast_magnitudes()`

### 3. Stage 2 Always Ambiguous
**Design**: Any match from 100" fallback marked ambiguous
**Rationale**: Distance > 10" means possible alternative matches
**User Experience**: Shows as "Ambiguous", user can verify before accepting

---

## Next Steps (if needed)

### 1. Run Full VAST Job Test
```bash
# Execute a test VAST job to verify end-to-end behavior
# Monitor for:
# - Stage 1 vs Stage 2 distribution
# - Ambiguous match rate
# - Performance (time per star)
# - Correctness (manual spot-checks)
```

### 2. Monitor in Production
- Track ambiguous rate (if >50%, may need parameter tuning)
- Collect user feedback on Stage 2 matches
- Verify magnitude calibration uses correct reference

### 3. Optional Optimizations
- Fine-tune tolerance (2.0 → 2.5 if too restrictive)
- Add database index on `is_ambiguous` if frequently queried
- Cache Vizier results in DB (180-day TTL) for faster re-queries

---

## Quality Assurance Checklist

- [x] Syntax verified (Python -m py_compile)
- [x] Worker function tested with example case
- [x] is_ambiguous field added to model
- [x] Template updated with visual indicators
- [x] Magnitude source verified (GREZZO, not calibrated)
- [x] Database column added
- [x] Backward compatibility maintained
- [x] Manual selection UI preserved
- [x] Logging messages clear and informative
- [ ] Full VAST job test (next phase)

---

## Files Status

| File | Status | Changes |
|------|--------|---------|
| `vast_service.py` | ✅ READY | Complete rewrite of worker + merge logic |
| `vast_job.py` | ✅ READY | Added is_ambiguous field |
| `job_detail.html` | ✅ READY | Added visual indicators |

---

## Author Notes

This implementation is a significant improvement over the previous approach:

**Previous** (commit 2ee5223):
- Gaia TAP with login (broke post-upgrade)
- Fixed 30" radius (no magnitude validation)
- All results marked "match" (confusing for user)
- No ambiguity detection

**Current** (this implementation):
- Vizier (no login, stable)
- Two-stage with magnitude validation
- Proper ambiguity marking
- Manual selection enabled for ambiguous
- Full magnitude compatibility checking

The algorithm prioritizes **correctness over quantity** - better to have fewer confident matches than many false positives.

---

**Status**: Ready for integration and testing! 🚀
