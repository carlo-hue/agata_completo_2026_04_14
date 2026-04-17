# Quick Test Guide - Gaia Algorithm

**Quick Reference for Testing the Implementation**

---

## Pre-Test (2 minutes)

```bash
# 1. Verify syntax
python -m py_compile agata/admin/services/vast_service.py
# Expected: ✅ No output = OK

# 2. Restart Flask app (if running)
# Kill current Flask process and restart
```

---

## What to Look For in Logs

### Pre-Phase (should appear once)
```
✅ LOOK FOR:
"Calculating offset and calibration_diff from 5 sample stars..."
"Offset (mean Vmag): 11.12 mag (from 5/5 stars)"
"Differences (VAST_raw - Gmag): ['25.16', '27.70', '22.60', '23.90', '22.00']"
"Mean difference: 24.27 mag"
"Std dev of differences: 2.1 mag"
"✅ Calibration coherent: offset=11.12, calibration_diff=24.27"

⚠️ IF YOU SEE:
"Differences NOT coherent (std_dev=X > 2.0) → BLOCKING ALL"
→ Entire job will be blocked (all 689 stars get no_match)
→ This means sample stars were too different from each other
```

### Worker (repeats for each star)
```
✅ LOOK FOR (per star):
"VAST_raw=-12.86, calibration_diff=24.27, VAST_calibrated=11.41, offset=11.12"
"calibration coherent (|VAST_raw - offset| = 0.26 <= 2.0)"
"compatible (|VAST_cal - Vmag| <= 2.0)"

⚠️ IF YOU SEE (per star):
"calibration NOT coherent" → Star rejected (no_match)
"compatible = 0" → No magnitude match in Stage 1, trying Stage 2
"STAGE 2 MATCH" → Star found match in 100" radius (ambiguous)
```

---

## Database Spot-Check (SQL Queries)

### Check Pre-Phase Success
```sql
SELECT COUNT(*) as total,
       COUNT(CASE WHEN gaia_source_id IS NOT NULL THEN 1 END) as with_gaia,
       COUNT(CASE WHEN is_ambiguous = 0 THEN 1 END) as stage1,
       COUNT(CASE WHEN is_ambiguous = 1 THEN 1 END) as stage2,
       COUNT(CASE WHEN gaia_source_id IS NULL AND is_ambiguous = 0 THEN 1 END) as no_match
FROM agata_vast_results
WHERE job_id = <YOUR_JOB_ID>;
```

**Expected Results**:
- total: 689 (or however many candidates)
- with_gaia: 60-80% of total (if pre-phase passed)
- stage1: 60-80% (10" radius matches)
- stage2: 20-40% (100" fallback matches)
- no_match: <5% (failure cases)

### Verify Specific Star
```sql
SELECT name, gaia_source_id, gaia_vmag, is_ambiguous, Median_magnitude
FROM agata_vast_results
WHERE name = 'out31321' AND job_id = <YOUR_JOB_ID>;
```

**Expected for out31321**:
```
name       | gaia_source_id | gaia_vmag | is_ambiguous | Median_magnitude
out31321   | 5734104703... | 7.90      | 0            | -12.86
```

### Check for Coherence Failures
```sql
SELECT COUNT(*) as failed_coherence
FROM agata_vast_results
WHERE job_id = <YOUR_JOB_ID>
  AND status = 'no_match'
  AND reason LIKE '%coherence%';
```

**Expected**: 0 (if pre-phase passed) or many thousands (if pre-phase failed)

---

## Success Criteria

✅ **Job Completes**: Without errors or timeouts

✅ **Pre-Phase**: Shows offset and calibration_diff in logs

✅ **Match Rate**: 60-80% Stage 1, 20-40% Stage 2, <5% no_match

✅ **Database**: gaia_source_id populated for most stars

✅ **Ambiguity**: is_ambiguous=0 for Stage 1, is_ambiguous=1 for Stage 2

✅ **Specific Star**: out31321 shows correct Gaia ID

---

## Failure Cases & Diagnosis

### Failure 1: Pre-Phase Blocked (entire job no_match)
```
Log: "Differences NOT coherent ... BLOCKING ALL"
Diagnosis: First 5 stars had very different VAST-to-Gmag ratios
Solution: Check if dataset is mixed sources or has calibration issue
```

### Failure 2: Too Many Stage 2 (>60% ambiguous)
```
Database: is_ambiguous=1 for most stars
Diagnosis: Very few Stage 1 matches, many falling back to Stage 2
Solution: Check if 10" radius too small, or magnitude tolerance too strict
```

### Failure 3: Coherence Check Failing Per-Star
```
Log: "calibration NOT coherent" repeated many times
Diagnosis: Individual stars failing |VAST_raw - offset| <= 2.0 check
Solution: Check if single outier star in sample throws off offset
```

### Failure 4: Wrong Gaia IDs
```
Database: out31321 shows different gaia_source_id than expected
Diagnosis: Algorithm matching to wrong star
Solution: Check logs for specific star - trace through Stage 1/2 matching
```

---

## Quick Debug Commands

### Show offset/calibration_diff
```bash
grep "Offset.*Calibration" <app.log> | head -1
```

### Show coherence status
```bash
grep "Calibration coherent\|NOT coherent" <app.log> | head -1
```

### Count pre-phase failures
```bash
grep "BLOCKING ALL" <app.log> | wc -l
```

### Count worker coherence failures
```bash
grep "\[STAGE 1\].*NOT coherent" <app.log> | wc -l
```

### Check specific star logs
```bash
grep "out31321" <app.log>
```

---

## Rollback (if needed)

If something goes wrong and you need to revert:

```bash
# Discard changes to vast_service.py (revert to last commit)
git checkout HEAD -- agata/admin/services/vast_service.py

# Restart Flask app
# Kill current process and restart
```

This reverts to the previous algorithm (Gaia TAP version).

---

## Quick Timeline

1. **Start job**: 00:00
2. **Download images**: ~5-10 min
3. **Validate WCS**: ~1 min
4. **VAST analysis**: ~10-20 min (depends on image size/count)
5. **Pre-phase** (offset calculation): ~10 sec
6. **Worker processing** (689 stars): ~40-60 sec
7. **Results upload**: ~1 min
8. **Total**: ~20-40 min for 50-100 images

---

## Key Log Patterns

### Good Run
```
✅ "Calculating offset and calibration_diff from 5 sample stars..."
✅ "Offset (mean Vmag): X.XX mag"
✅ "Std dev of differences: X.XX mag"
✅ "✅ Calibration coherent"
✅ "[STAGE 1]" appearing frequently
✅ "Starting parallel Gaia queries (4 workers, 689 stars)"
✅ "Gaia cross-matching completed"
```

### Bad Run
```
❌ "Differences NOT coherent ... BLOCKING ALL"
❌ "[STAGE 1] ... NOT coherent" appearing repeatedly
❌ "TimeoutError" from Vizier
❌ "No Gaia sources found" for all stars
```

---

## Next Steps

1. **Run test job** on small dataset (50 images)
2. **Monitor logs** for pre-phase messages
3. **Wait for completion** (~30 min)
4. **Check database** with spot-check queries above
5. **If OK**: Proceed to full job
6. **If issues**: Review logs and diagnostics

---

**Status**: Ready to test ✅

