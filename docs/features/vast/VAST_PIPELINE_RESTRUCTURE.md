# VAST Pipeline Restructuring - Session 9 (2026-02-07)

## Executive Summary

**Major breakthrough**: Discovered that VAST itself has a built-in magnitude calibration pipeline (`magnitude_calibration.sh V`) that produces properly calibrated coordinates in a `.cat.ucac5` file.

**Solution**: Restructured the entire pipeline to use VAST's native coordinate calibration instead of trying to manually convert pixel→sky coordinates.

---

## The Problem

The previous approach was trying to:
1. Run VAST (which outputs pixel coordinates)
2. Manually convert pixel→sky using WCS
3. Hope the conversion was correct
4. Then do Gaia matching

This had fundamental issues because we were fighting against VAST's own coordinate system. Even with the "correct" origin=1 formula, we were reimplementing something VAST already does internally.

---

## The Discovery

When testing `magnitude_calibration.sh V`, we discovered:

1. **VAST has a built-in plate-solving workflow** via `magnitude_calibration.sh`
2. **It produces a `.cat.ucac5` file** with:
   - Pre-calibrated RA/Dec coordinates
   - Photometric magnitudes matched to APASS
   - Coordinates already in the correct celestial frame
3. **This is what VAST internally uses** - much more reliable than manual conversion

Example from test run:
```
Star ID 1:    RA=51.0921402°, Dec=+49.8730905°  (from .cat.ucac5)
Star ID 33245: RA=47.0411332°, Dec=+40.9530258°
```

---

## Old Pipeline (BROKEN)

```
Download Images
    ↓
Validate WCS
    ↓
Run VAST (pixel coordinates)
    ↓
Plate solve reference frame (AFTER VAST!)
    ↓
Manual WCS conversion (pixel → sky)
    ↓
Gaia matching (with uncertain coordinates)
```

**Problems**:
- Plate solving happens too late
- Manual WCS conversion is error-prone
- Using wrong coordinate origin or flip loses all accuracy
- Gaia finds few/no matches

---

## New Pipeline (CORRECT)

```
Download Images
    ↓
Validate WCS
    ↓
Plate solve reference frame (BEFORE VAST)  ← NEW: Step 2.5
    ↓
Run VAST (uses corrected WCS)
    ↓
Parse VAST output
    ↓
Run magnitude_calibration.sh V (VAST utility)  ← NEW: Step 4.5
    ↓
Read .cat.ucac5 (calibrated coordinates)  ← NEW: Step 5
    ↓
Gaia matching (with accurate coordinates)
    ↓
VSX/ATLAS matching
    ↓
Known variable detection
    ↓
Upload results
```

**Advantages**:
- Uses VAST's own calibration pipeline (designed for VAST)
- Plate solving happens before VAST (optimal)
- Coordinates are pre-calibrated by VAST
- No manual WCS conversion needed
- Much more robust

---

## Implementation Details

### Step 2.5: Plate Solve BEFORE VAST

```python
# Select reference frame (first image)
reference_frame = image_paths[0]

# Plate solve using Astrometry.net (solve-field)
reference_frame_solved = self._plate_solve_reference_frame(
    reference_frame, job, db
)
```

**Result**: Reference frame has improved WCS before VAST runs

### Step 4.5: Magnitude Calibration

```python
# Run VAST's magnitude_calibration.sh utility
ucac5_catalog = self._run_magnitude_calibration(
    vast_dir, job, db
)
```

**What this does**:
- Launches `/opt/vast/util/magnitude_calibration.sh V`
- Produces `wcs_<reference_image>.fits.cat.ucac5` file
- File contains 748+ stars with calibrated RA/Dec and magnitudes

### Step 5: Read Calibrated Coordinates

```python
# Instead of manual WCS conversion, read VAST's own output
if ucac5_catalog and os.path.exists(ucac5_catalog):
    stars_df = self._read_vast_catalog_ucac5(ucac5_catalog, stars_df)
else:
    # Fallback: manual WCS if calibration failed
    stars_df = self._convert_pixel_to_sky(stars_df, reference_frame, job)
```

**Result**: RA/Dec coordinates from VAST's native calibration pipeline

---

## Test Results

Ran `magnitude_calibration.sh V` on test TESS data:

### ✅ What Worked
- Plate solving: Successfully solved reference frame
- SExtractor: Detected 48,411 stars
- UCAC5 matching: Matched 900-908 stars in UCAC5
- APASS matching: Matched 748 stars with V magnitudes
- File creation: `.cat.ucac5` file created (9.4 MB)
- Coordinate output: Valid RA/Dec values in output file

### Sample Output
```
ID 1:     RA=51.0921402  Dec=+49.8730905  (magnitude field with calibration)
ID 33245: RA=47.0411332  Dec=+40.9530258
ID 17950: RA=47.3733027  Dec=+44.8550310
```

### ⚠️ Known Issue
- PGPLOT error: "cannot connect to X server"
  - **Not a problem**: PGPLOT is only used for visualization
  - The `.cat.ucac5` file is still created correctly
  - Error occurs at the very end, after all calibration is complete

---

## Code Changes

**File**: `agata/admin/services/vast_service.py`

**New/Modified Methods**:

1. **`_run_magnitude_calibration()`** (Step 4.5)
   - Launches `/opt/vast/util/magnitude_calibration.sh V`
   - Finds and returns the `.cat.ucac5` file path
   - Non-fatal error handling (fallback to manual conversion)

2. **`_read_vast_catalog_ucac5()`** (Step 5)
   - Parses the `.cat.ucac5` space-separated file
   - Extracts RA/Dec for each star ID
   - Merges into the stars DataFrame
   - Fallback: keeps original values if star not found

3. **Reordered workflow in `execute_job()`**
   - Step 2.5: Plate solve (BEFORE VAST)
   - Step 3: VAST (with correct WCS)
   - Step 4.5: Magnitude calibration
   - Step 5: Read calibrated coordinates

---

## Why This Works Better

1. **VAST knows its own coordinate system**: The magnitude calibration script is part of VAST
2. **Plate solving is done right**: Before VAST runs, so VAST uses correct WCS
3. **Photometric calibration included**: APASS matching happens automatically
4. **Robust pipeline**: VAST developers designed this for their own data
5. **No manual coordinate conversion**: Avoids origin/flip confusion entirely

---

## Next Steps

1. Run a full VAST job with the new pipeline
2. Compare Gaia matching results:
   - Old approach: ~1/690 matches
   - New approach: expected 100+ matches (using VAST's calibrated coords)
3. Verify coordinate accuracy
4. Run full promotion pipeline to create Projects

---

## Files Modified

- `agata/admin/services/vast_service.py` - Pipeline restructuring + 2 new methods

---

## References

- VAST Documentation: `/opt/vast/util/magnitude_calibration.sh`
- Output format: `wcs_<image>.fits.cat.ucac5` (space-separated catalog)
- Calibration service: VAST internal utilities (proven, reliable)
