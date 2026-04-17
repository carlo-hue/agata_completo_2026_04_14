# Gaia Cross-Matching with Global Magnitude Offset

## Implementation Status: ✅ COMPLETE

**Date**: 2026-02-17
**Session**: 23 (Final Implementation)
**Status**: Ready for VAST Job Testing

---

## Algorithm Overview

### Purpose
Calibrate VAST instrumental magnitudes using a global offset calculated from a representative sample of Gaia matches, enabling consistent magnitude-based filtering across all 689 VAST candidates.

### Key Concept: Global Offset
Instead of calculating magnitude calibration per-star, this implementation:

1. **Pre-calculates a single offset** from the first 5 VAST candidates
2. **Applies this offset to all 689 stars** in the job
3. **Uses the offset** for magnitude compatibility checking (not for final calibration)

This ensures consistent, reliable magnitude-based filtering without the complexity of per-star variations.

---

## Implementation Details

### 1. Magnitude Offset Calculation (`_calculate_magnitude_offset_from_sample`)

**Location**: `agata/admin/services/vast_service.py` lines 1212-1311

**Method Signature**:
```python
def _calculate_magnitude_offset_from_sample(self, stars_valid: pd.DataFrame, match_radius_arcsec: int) -> float:
```

**Algorithm**:
```
1. Take first min(5, len(stars_valid)) VAST candidates
2. For each candidate:
   - Query Vizier I/355/gaiadr3 with 10" radius
   - Take the FIRST result (brightest star, smallest Gmag)
   - Calculate V-magnitude using EDR3 formula
   - Append to vmags list
3. Return mean(vmags) as the global offset
```

**Error Handling**:
- If offset calculation fails: returns 0.0 (no calibration)
- If Vizier timeout: gracefully continues with available samples
- If no valid Vmag values: falls back to 0.0

**Logging**:
- Logs each sample star query with Gaia ID, Gmag, BP-RP, and Vmag
- Logs final offset and sample size
- Example: "Magnitude offset calculated: 0.75 mag (from 5/5 sample stars)"

### 2. Worker Function Modification (`_gaia_worker_query_single_star`)

**Location**: `agata/admin/services/vast_service.py` lines 64-274

**Parameter Signature**:
```python
params = (name, ra, dec, match_radius_arcsec, vast_mag, offset)
```

**Key Changes**:
- Added `offset` parameter to worker params tuple
- Offset is passed through from `_crossmatch_gaia()`
- Immutable throughout worker execution

**Stage 1 (10" radius)**:
```python
1. Query Vizier 10" → candidates_10
2. Calculate Vmag for each candidate
3. Calibrate VAST: VAST_cal = vast_mag + offset
4. Check coherence: |VAST_cal - offset| ≤ 2.0 mag
   - If fails: return {'status': 'no_match'} (blocks Stage 2)
   - If passes: continue
5. Filter: keep only compatible (|VAST_cal - Vmag| ≤ 2.0)
6. If compatible found:
   - Sort by distance, pick nearest
   - Return match with is_ambiguous=False
7. Else: proceed to Stage 2
```

**Stage 2 (100" radius)**:
```python
1. Query Vizier 100" → candidates_100
2. Same coherence check as Stage 1
   - If fails: return {'status': 'no_match'}
3. Filter by magnitude compatibility
4. If compatible found:
   - Sort by (distance), pick nearest
   - Return match with is_ambiguous=True, gaia_source_id=None
5. Else: return no_match
```

**Helper Function** (`process_candidates`):
```python
def process_candidates(candidates_list, radius_desc, global_offset, is_stage2=False):
    # Uses global_offset for all magnitude calculations
    # Returns dict on success, None if no candidates, 'no_match' if coherence fails
```

### 3. Caller Implementation (`_crossmatch_gaia`)

**Location**: `agata/admin/services/vast_service.py` lines ~1216-1358

**Key Steps**:

**Line 1372** - Calculate offset before workers:
```python
offset = self._calculate_magnitude_offset_from_sample(stars_valid, match_radius_arcsec)
logger.info(f"Magnitude offset: {offset:.2f} mag")
```

**Line 1383** - Pass offset to all workers:
```python
executor.submit(_gaia_worker_query_single_star,
                (row['name'], row['ra'], row['dec'], match_radius_arcsec,
                 row['Median_magnitude'], offset))  # ← offset parameter
```

**Merge Results** (lines 1309-1327):
- Merges worker results with stars_df
- Preserves is_ambiguous field
- Converts gaia_source_id to Int64 type

---

## Magnitude Filtering Logic

### Coherence Check (New)
**Purpose**: Validate that the calibrated VAST magnitude is reasonable

**Formula**:
```
coherence_diff = |VAST_calibrated - offset|
is_coherent = coherence_diff ≤ 2.0 mag
```

**Behavior**:
- If coherence check FAILS in Stage 1: immediately return no_match (blocks Stage 2)
- If coherence check FAILS in Stage 2: return no_match
- If coherence check PASSES: continue to magnitude compatibility filtering

### Magnitude Compatibility Filter
**Purpose**: Find Gaia sources with similar apparent magnitude to the VAST source

**Formula**:
```
for each Gaia candidate:
    vmag = _calculate_vmag_from_gaia(gmag, bp_rp)
    delta_mag = |vmag - vast_calibrated|
    is_compatible = delta_mag ≤ 2.0 mag
```

**Both Stages**: Filter by magnitude compatibility FIRST, then pick nearest

---

## Data Flow

```
VAST Job Started
    ↓
_crossmatch_gaia() called with stars_df (689 stars)
    ↓
Filter valid coordinates → stars_valid (typically ~689)
    ↓
[PRE-PHASE] _calculate_magnitude_offset_from_sample(stars_valid, 30)
    ├─ Vizier query 10" for star 1 → take first → calc Vmag
    ├─ Vizier query 10" for star 2 → take first → calc Vmag
    ├─ Vizier query 10" for star 3 → take first → calc Vmag
    ├─ Vizier query 10" for star 4 → take first → calc Vmag
    ├─ Vizier query 10" for star 5 → take first → calc Vmag
    └─ offset = mean(vmag1, vmag2, vmag3, vmag4, vmag5)
    ↓
Start ProcessPoolExecutor (4 workers)
    ↓
For each of 689 stars, submit worker:
    _gaia_worker_query_single_star(name, ra, dec, 30, vast_mag, offset)
    ↓
[IN WORKER - STAGE 1]
    ├─ Vizier query 10" → candidates_10
    ├─ For each: calc Vmag
    ├─ Check coherence: |vast_mag + offset - offset| ≤ 2.0 ✓
    ├─ Filter: |vast_mag + offset - vmag| ≤ 2.0
    ├─ If found: sort by distance → pick nearest → return match
    └─ If not found: → STAGE 2
    ↓
[IN WORKER - STAGE 2 - FALLBACK]
    ├─ Vizier query 100" → candidates_100
    ├─ Check coherence again: |vast_mag + offset - offset| ≤ 2.0 ✓
    ├─ Filter: |vast_mag + offset - vmag| ≤ 2.0
    ├─ If found: sort by distance → pick nearest → return ambiguous
    └─ If not found: → no_match
    ↓
All workers complete
    ↓
Merge results → stars_df with Gaia columns
    ↓
_scale_vast_magnitudes() for final calibration
    ↓
Upload results to database
```

---

## Testing Checklist

### Pre-Deployment
- [x] Syntax check: `python -m py_compile agata/admin/services/vast_service.py` ✅
- [x] Helper function exists and is callable ✅
- [x] Worker receives offset parameter ✅
- [x] process_candidates() calls pass offset ✅
- [x] Offset calculation is done before workers start ✅

### Deployment Testing (When Ready)
- [ ] Run VAST job with small test dataset (~50 stars)
- [ ] Check logs for offset calculation
- [ ] Verify Stage 1 and Stage 2 queries execute
- [ ] Check that is_ambiguous is marked correctly
- [ ] Verify gaia_source_id is NULL for ambiguous matches
- [ ] Run on full dataset (689 stars)
- [ ] Check final results in database

---

## Key Implementation Notes

### Why Global Offset?
- **Simplicity**: Single calculation, applied to all stars
- **Stability**: Not affected by local field variations
- **Reproducibility**: Same offset used for all workers
- **Efficiency**: Sample-based, not per-star intensive

### Magnitude Offset vs Magnitude Scaling
- **Offset (used here)**: Pre-phase calibration, passed to all workers for magnitude comparison
- **Scaling (Step 7)**: Post-phase actual magnitude calibration using Gaia Vmag reference
- They are different operations with different purposes

### Error Recovery
- If offset calculation fails → offset=0.0 → magnitudes not pre-calibrated but matching continues
- If Stage 1 fails → no Stage 2 allowed if coherence check fails
- If Vizier times out → error status returned, user can retry job

### Performance
- Offset calculation: ~2-3 seconds (5 Vizier queries)
- Worker pool: ~689 stars × 0.1 s/star ÷ 4 workers ≈ 17 seconds
- Total Gaia phase: ~20 seconds (expected)

---

## Database Integration

### VastResult Model
The `is_ambiguous` field (already in model) captures:
- `is_ambiguous=False`: Stage 1 successful match, gaia_source_id populated
- `is_ambiguous=True`: Stage 2 fallback, gaia_source_id NULL (for manual UI selection)

### Template Display (job_detail.html)
- Shows "Ambiguous" badge when is_ambiguous=True
- Shows manual selection list when gaia_source_id=NULL
- Allows user to manually select from gaia_candidates list

---

## Files Modified

### 1. agata/admin/services/vast_service.py
- **Added**: `_calculate_magnitude_offset_from_sample()` method (lines 1212-1311)
- **Modified**: `_gaia_worker_query_single_star()` to accept offset parameter (line 91)
- **Modified**: `process_candidates()` to use global_offset (lines 93-166)
- **Modified**: `_crossmatch_gaia()` to calculate and pass offset (lines 1372, 1383)
- **Modified**: Both process_candidates() calls to pass offset (lines 215, 261)

### 2. No Other Files Modified
- agata/auth_models/vast_job.py: No changes (is_ambiguous field already exists)
- Templates: No changes (already have correct display logic)

---

## Success Criteria

✅ Implementation is **COMPLETE** when:

1. ✅ Helper function `_calculate_magnitude_offset_from_sample()` implemented
2. ✅ Worker function accepts and uses offset parameter
3. ✅ process_candidates() receives and uses global_offset
4. ✅ Offset calculation happens before workers start
5. ✅ Offset passed to all 689 worker submissions
6. ✅ Syntax check passes without errors
7. ✅ Logic matches user's 8-step algorithm specification

**Current Status**: ✅ ALL CRITERIA MET - READY FOR TESTING

---

## Next Steps

1. **Immediate**: Run test VAST job with this implementation
   - Monitor logs for offset calculation
   - Check Stage 1/Stage 2 distribution
   - Verify is_ambiguous field population

2. **Verification**:
   - Compare results with previous Gaia matching
   - Check that coherence failures are properly handled
   - Verify ambiguous matches have NULL gaia_source_id

3. **Optimization** (if needed):
   - Monitor Vizier query times
   - Optimize sample size if needed
   - Adjust magnitude tolerance if results poor

---

## Troubleshooting

### Issue: Offset calculation stuck/timeout
**Solution**: VizierClient has 20-second timeout per query. Check network connectivity.

### Issue: All matches marked ambiguous
**Solution**: Check if Stage 1 is consistently finding no compatible candidates. May indicate:
- Magnitude tolerance too strict (currently 2.0 mag)
- Offset calculation producing invalid values
- Coordinate accuracy issues

### Issue: is_ambiguous field NULL in database
**Solution**: Check that worker returns dict with is_ambiguous key. Verify template merge logic.

### Issue: Offset calculation returns 0.0
**Solution**: Check logs for Vizier query failures. Fallback is normal, magnitude filtering will skip.

---

## Documentation References

- **Algorithm Design**: Plan file in claude-code: `velvet-baking-dragon.md`
- **Previous Sessions**: Memory.md Session 23 notes
- **Vizier Integration**: `CATALOG_INTEGRATION.md`
- **VAST Pipeline**: `VAST_IMPLEMENTATION_SUMMARY.md`

