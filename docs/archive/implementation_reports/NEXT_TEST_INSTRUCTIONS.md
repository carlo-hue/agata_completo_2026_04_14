# Next Test Instructions - With Enhanced Logging

**Updated**: 2026-02-17
**Purpose**: Run VAST job again to see detailed coherence failure diagnostics

---

## What Changed

✅ **Enhanced logging added** to show actual difference values when coherence fails

**File Modified**: `agata/admin/services/vast_service.py` (lines 1339-1348)

**New Feature**: When std_dev > 2.0, error message will now include:
- Array of actual difference values
- Mean and min/max
- Range calculation
- Clear diagnostic message

---

## Pre-Test Checklist

```bash
# 1. Verify syntax of updated code
python -m py_compile agata/admin/services/vast_service.py
# Expected: ✅ No output = OK

# 2. Kill Flask if running
pkill -f "python.*flask"  # or however it runs

# 3. Start Flask with updated code
python -m flask run

# 4. Wait for Flask to start
# Check for: "Running on http://..." in console
```

---

## Running the Test Job

1. **Access VAST admin page**: `/agata/admin/vast/`
2. **Create new VAST job**:
   - Select dataset (same or different from before)
   - Submit job
3. **Wait for pre-phase** (should happen first):
   - Should see logs appear in Flask console
   - Look for: `"Calculating offset and calibration_diff from 5 sample stars..."`
   - Should take ~5-10 seconds

---

## What to Look For in Logs

### If Coherence PASSES (std_dev ≤ 2.0)

```
INFO: Offset (mean Vmag): 11.12 mag (from 5/5 stars)
INFO: Differences (VAST_raw - Gmag): [25.16, 27.70, 22.60, 23.90, 22.00]
INFO: Mean difference: 24.27 mag
INFO: Std dev of differences: 2.0 mag
✅ Calibration coherent: offset=11.12, calibration_diff=24.27
[WORKERS START PROCESSING 689 STARS...]
```

✅ **SUCCESS** - Job will continue with worker processing!

---

### If Coherence FAILS (std_dev > 2.0) - NEW DETAILED OUTPUT

```
ERROR: ❌ COHERENCE FAILED - Differences NOT coherent:
       Differences: [22.14, 31.45, 23.88, 25.91, 18.27]
       Mean: 24.33 mag
       Std dev: 4.08 mag (threshold: 2.0)
       Range: 31.45 - 18.27 = 13.18 mag
       → BLOCKING ALL 689 stars
ERROR: Offset/calibration_diff calculation failed - differences in sample stars were NOT coherent
```

⚠️ **IMPORTANT DATA** - This is the diagnostic info we need!

---

## What To Do When You See The Output

### Step 1: CAPTURE The Log Output
```bash
# Save the entire error message with all values
# Example of what to save:
#
# Differences: [22.14, 31.45, 23.88, 25.91, 18.27]
# (These are the actual VAST-to-Gmag conversion ratios)
```

### Step 2: ANALYZE The Difference Values

Look at the array: `[22.14, 31.45, 23.88, 25.91, 18.27]`

- **Mean**: ~24.33 mag
- **Outliers**: Which values are far from mean?
  - 18.27 is LOW (4.06 mag below mean)
  - 31.45 is HIGH (7.12 mag above mean)
- **Pattern**: Is there a systematic trend or random variation?

### Step 3: INTERPRET

**Example 1** - Consistent offset:
```
Differences: [21, 22, 21, 22, 21]
→ All similar (~21) with std_dev ~0.5 mag
→ Good sample! ✅ Should PASS (but didn't = bug in your data)
```

**Example 2** - One outlier:
```
Differences: [22, 23, 22, 22, 45]
→ Four normal (~22), one huge (45)
→ Star 5 has bad VAST measurement
→ Reason: Single bad star in sample
```

**Example 3** - Two distinct groups:
```
Differences: [20, 20, 20, 35, 35]
→ Two groups: 20 mag and 35 mag
→ Reason: Stars from different exposures/sources
```

---

## Decision Based on Results

### If std_dev > 2.0 (Like Your First Run)

**Option A**: Try Different Dataset
- Same VAST job script, different images
- Different 5 sample stars might be more coherent
- Shows if problem is field-specific

**Option B**: Investigate Current Dataset
- Check VAST photometry file for this field
- Are magnitudes realistic?
- Are there obvious outliers?

**Option C**: Adjust Threshold (Later)
- Current: 2.0 mag (strict)
- Consider: 2.5 or 3.0 mag (more permissive)
- ⚠️ Only after understanding root cause!

---

## Commands to Capture Logs

### Flask Console (if running in terminal)
```bash
# If Flask is in terminal, simply copy the error message
# Ctrl+C will pause, you can copy
```

### Flask Log File (if running as daemon)
```bash
# Find Flask logs
tail -f /var/log/flask/app.log  # or wherever it logs

# Or grep for coherence messages
grep "COHERENCE FAILED" /var/log/flask/app.log
grep "Differences:" /var/log/flask/app.log
```

### Database Check
```sql
-- After job completes, check if results exist
SELECT COUNT(*), COUNT(DISTINCT gaia_source_id)
FROM agata_vast_results
WHERE job_id = <JOB_ID>;

-- If pre-phase blocked:
-- COUNT should be 689 (all processed)
-- COUNT(DISTINCT gaia_source_id) should be 0 (all NULL due to blocking)

-- If pre-phase passed:
-- COUNT(DISTINCT gaia_source_id) should be > 600 (most have Gaia matches)
```

---

## Success Indicators

✅ **Test Successful If You See:**

1. **Pre-phase starts**:
   - `"Calculating offset and calibration_diff from 5 sample stars..."`

2. **Calculations shown**:
   - Offset value: `"Offset (mean Vmag): X.XX mag"`
   - Differences array: `"Differences: [...]"`
   - Statistics: `"Mean difference: X.XX mag"`, `"Std dev: X.XX mag"`

3. **Clear decision**:
   - Either `"✅ Calibration coherent"` (continues to workers)
   - Or `"❌ COHERENCE FAILED"` with detailed values (new!)

---

## Troubleshooting

### Issue: Don't See Pre-Phase Logs

**Possible Cause**: VAST job erroring before pre-phase
- Check Flask console for errors
- Check job status in database
- Look for upload/parsing errors

**Solution**: Check VAST job status in `/agata/admin/vast/` UI

### Issue: Don't See Detailed Error Message

**Possible Cause**: Old code still running (Flask not restarted)
- Kill Flask: `pkill -f "python.*flask"`
- Verify file saved: `grep "COHERENCE FAILED" agata/admin/services/vast_service.py`
- Restart Flask: `python -m flask run`

**Solution**: Ensure Flask restarted with new code

### Issue: std_dev Still 4.08 (Same Failure)

**Possible Cause**: Dataset quality issue
- Same data = same sample stars = same failure pattern

**Solution**: Try different dataset to isolate problem

---

## What Happens After Pre-Phase

### If Coherence PASSES

```
Pre-phase: ✅ OK
→ Worker processing starts (4 workers, 689 stars)
→ Stage 1 queries (10" radius)
→ Stage 2 fallbacks (100" radius)
→ Results aggregation
→ Job completion
→ Database populated with gaia_source_id values
```

### If Coherence FAILS

```
Pre-phase: ❌ BLOCKED
→ All 689 stars assigned status "no_match"
→ All gaia_source_id = NULL
→ Workers NOT launched
→ Job completes early
→ Database shows 689 results with NO Gaia matches
```

---

## Expected Timeline

| Phase | Duration | What To Look For |
|-------|----------|------------------|
| Image Download | 5-30 min | Depends on dataset |
| WCS Validation | 1 min | Should complete without errors |
| VAST Analysis | 10-30 min | Depends on image size |
| **Pre-Phase** | **~5-10 sec** | **Offset/calibration_diff calculation** |
| Workers (if passes) | 40-60 sec | 689 stars processed in parallel |
| Results Upload | 1-2 min | Final step |
| **Total** | **~30-90 min** | Depends on dataset size |

---

## Documentation Created

I've created these reference documents for you:

1. **FIRST_TEST_RESULTS_ANALYSIS.md** - Analysis of your first test
2. **COHERENCE_FAILURE_ANALYSIS.md** - Understanding the failure
3. **NEXT_TEST_INSTRUCTIONS.md** - This file

All available in: `/var/www/astrogen/`

---

## Ready to Test?

✅ **Code Updated**: Enhanced logging added
✅ **Syntax Verified**: `python -m py_compile` passed
✅ **Documentation Ready**: All guides created
✅ **Next Steps Clear**: Run job, capture output, analyze

**NEXT ACTION**: Restart Flask with updated code and run another VAST job!

Once you have the detailed error message (if coherence fails), we can:
1. Understand why specific stars had outlier differences
2. Determine if dataset has quality issues
3. Decide on threshold adjustments or preprocessing needs
4. Plan production deployment

---

**Status**: ✅ READY FOR NEXT TEST RUN

