# Coherence Failure Analysis - std_dev=4.08 > 2.0

**Date**: 2026-02-17
**Status**: Algorithm working as designed - BLOCKING applied correctly
**Issue**: Cannot see the detailed sample star values in logs

---

## What Happened

The VAST job you ran had a **PRE-PHASE FAILURE**:

```
Differences NOT coherent (std_dev=4.08 > 2.0) → BLOCKING ALL
```

**This is CORRECT behavior!** The algorithm detected that the first 5 VAST candidates had **inconsistent VAST-to-Gmag ratios** and correctly blocked the entire job to prevent bad calibration.

---

## Why We Need to See the Values

To understand WHY coherence failed (std_dev = 4.08), we need to see:

1. **The first 5 VAST candidate names**
2. **Their VAST_raw magnitudes** (from VAST photometry output)
3. **The Gaia Gmag values found** for each
4. **The calculated differences**: |VAST_raw - Gmag| for each
5. **The actual difference values** that caused std_dev=4.08

Currently, the code LOGS these values (lines 1332-1334 in vast_service.py):
```python
logger.info(f"Differences (VAST_raw - Gmag): {[f'{d:.2f}' for d in diffs]}")
logger.info(f"Mean difference: {mean_diff:.2f} mag")
logger.info(f"Std dev of differences: {std_diff:.2f} mag")
```

But you're only seeing:
```
Differences NOT coherent (std_dev=4.08 > 2.0) → BLOCKING ALL
```

**Missing**: The individual difference values before the failure message.

---

## Solutions to See the Values

### Option 1: Check Flask App Logs (Recommended)
Find where Flask is logging and check for:
```
DEBUG: Starting parallel Gaia queries
DEBUG: Calculating offset and calibration_diff from 5 sample stars (10" radius)...
DEBUG:   star1: VAST_raw=..., Gmag=..., Vmag=..., diff=...
DEBUG:   star2: VAST_raw=..., Gmag=..., Vmag=..., diff=...
...
INFO: Differences (VAST_raw - Gmag): [...]
INFO: Std dev of differences: 4.08 mag
ERROR: Differences NOT coherent (std_dev=4.08 > 2.0) → BLOCKING ALL
```

### Option 2: Add More Verbose Logging (Quick Fix)
Modify vast_service.py to log BEFORE the error:

Change line 1339-1341 from:
```python
if std_diff > threshold_std:
    logger.error(
        f"Differences NOT coherent (std_dev={std_diff:.2f} > {threshold_std}) → BLOCKING ALL"
    )
```

To:
```python
if std_diff > threshold_std:
    # LOG DETAILED INFO BEFORE BLOCKING
    logger.error(
        f"❌ Differences NOT coherent (std_dev={std_diff:.2f} > {threshold_std})")
    logger.error(f"    Differences: {[f'{d:.2f}' for d in diffs]}")
    logger.error(f"    Mean: {mean_diff:.2f}, Min: {min(diffs):.2f}, Max: {max(diffs):.2f}")
    logger.error(f"    → BLOCKING ALL")
```

### Option 3: Run Diagnostic Query
Once logs are captured, run SQL query to see what values were calculated:
```sql
SELECT name, Median_magnitude, gaia_gmag, gaia_vmag, gaia_source_id
FROM agata_vast_results
WHERE job_id = <YOUR_JOB_ID>
LIMIT 5;
```

---

## What We Know Currently

From the error message alone:
```
std_dev = 4.08 mag (threshold = 2.0 mag)
```

This means:
- The 5 sample star differences had VERY HIGH variance
- Possible causes:
  1. **Some stars HUGE diff (35+ mag)**: One star has very wrong VAST magnitude
  2. **Some stars SMALL diff (25 mag)**: Another star has normal VAST magnitude
  3. **Mixed field issue**: Stars from different images/sources
  4. **Calibration inconsistency**: VAST photometry not on consistent scale

---

## Recommended Next Steps

### Immediate (Next Run)
1. **Modify vast_service.py** to log detailed difference values when coherence fails
2. **Re-run VAST job** with same dataset
3. **Capture full logs** showing the 5 sample stars and their differences

### Analysis
1. Look at the actual difference values
2. Identify which stars caused the high std_dev (the outliers)
3. Check if those stars have unusual VAST magnitudes
4. Determine if dataset has quality issues

### Decision
1. **If sample stars are truly incoherent**: The dataset may need preprocessing
2. **If first 5 happens to be bad**: Try running multiple times - different sample may pass
3. **If consistent failure**: Investigate VAST photometry calibration in this field

---

## Code Fix to Capture Values

Add this after line 1334 in vast_service.py:

```python
# Add before the coherence check
if std_diff > threshold_std:
    # Log detailed diagnostics
    logger.warning(
        f"⚠️  PRE-PHASE COHERENCE CHECK:\n"
        f"    Sample stars: {len(diffs)}\n"
        f"    Differences: {[f'{d:.2f}' for d in diffs]}\n"
        f"    Mean: {mean_diff:.2f} mag\n"
        f"    Std dev: {std_diff:.2f} mag (threshold: {threshold_std})\n"
        f"    Min: {min(diffs):.2f}, Max: {max(diffs):.2f}, Range: {max(diffs)-min(diffs):.2f}\n"
        f"    Status: ❌ FAIL - Differences NOT coherent → BLOCKING ALL"
    )
```

---

## Expected Resolution

Once we see the actual difference values, we can determine:

1. **Why coherence failed** (which stars are problematic)
2. **Whether threshold should be adjusted** (2.0 mag is strict, could try 2.5 or 3.0)
3. **Whether dataset needs preprocessing** (bad VAST calibration, mixed sources, etc.)
4. **Next testing approach** (different dataset, different thresholds, etc.)

---

## Key Point

**The algorithm is WORKING CORRECTLY!** It's doing exactly what it should:
- ✅ Detecting incoherent sample stars
- ✅ Recognizing potential calibration issues early
- ✅ Blocking the job before applying bad calibration to all 689 stars

The "failure" is actually a SUCCESS - it's preventing a cascading error!

Next step: Capture the detailed values to understand WHY the sample was incoherent.

