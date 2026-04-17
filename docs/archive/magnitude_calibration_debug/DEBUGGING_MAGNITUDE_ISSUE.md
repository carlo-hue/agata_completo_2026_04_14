# Investigation: Negative Magnitude Values in Gaia Cross-Matching

**Status**: Enhanced debug logging added, awaiting test results
**Issue**: VAST magnitudes are negative (-12.8) instead of positive (9.827)

## Observed Symptoms

From latest test logs:
```
[GAIA WARNING] Star out31321.dat: VAST_mag=-12.8555 is outside reasonable range (-5 to 30)!
[GAIA WARNING] Star out42591.dat: VAST_mag=-12.7546 is outside reasonable range (-5 to 30)!
...
```

All magnitudes are negative, not positive as expected. This indicates one of:

1. **Wrong column being read**: The `Median_magnitude` column might be pulling from wrong position
2. **File format issue**: The statistics log format might have changed
3. **Magnitude calibration didn't run**: Even though Step 4.5 was enabled, it might not be producing correct values
4. **Column order mismatch**: The DataFrame columns might not match the VAST_STAT_COLUMNS definition

## Hypothesis

The VAST statistics file (`vast_lightcurve_statistics.log`) format defined at line 36-43:
```python
VAST_STAT_COLUMNS = [
    'Median_magnitude', 'idx00_STD', 'x', 'y', 'name',
    'idx01_wSTD', 'idx02_skew', ... (30 total columns)
]
```

But the actual file might have:
- Different column order
- Extra/missing columns
- Different format (fixed-width vs space-separated)
- Comment lines that aren't being skipped

When pandas reads the file with `pd.read_csv()`, if the column order is wrong, then `Median_magnitude` would be reading from the wrong column position!

## Debug Logging Added

Enhanced the `_crossmatch_gaia()` function to show:

1. **Column structure**: What columns are actually in `stars_valid`
2. **First row values**: Exact values being read for the first star
3. **Full DataFrame structure**: All columns present in the full `stars_df`
4. **Column existence check**: Does `Median_magnitude` column actually exist in the full DataFrame?

### What to Look For in Logs

When running the next VAST job, look for:
```
[DEBUG CROSSMATCH] First stars_valid row: name=..., ra=..., dec=..., Median_magnitude=...
[DEBUG CROSSMATCH] Full stars_df first row - columns: [...]
[DEBUG CROSSMATCH] Median_magnitude in full: ...
```

### If Magnitude is Still Negative

This means:
- The column being read is definitely from the wrong position
- The statistics file format doesn't match the defined VAST_STAT_COLUMNS
- We need to fix the column definition or the file parsing

### If Magnitude is Now Positive (~9.827)

This means:
- The magnitude calibration step DID work
- The issue was indeed that it wasn't being run before
- Gaia matching should now work correctly

## Possible Solutions (If Still Negative)

### Solution 1: Re-examine the statistics file format
```bash
# Check actual file structure:
head -20 /path/to/vast_lightcurve_statistics.log
# Count columns:
head -1 /path/to/vast_lightcurve_statistics.log | wc -w
```

### Solution 2: Check if pandas is reading file correctly
```python
df = pd.read_csv(stats_log, sep=r'\s+', header=None, nrows=1)
print(df.iloc[0].values)  # See raw values
```

### Solution 3: Re-order columns if needed
Update `VAST_STAT_COLUMNS` to match actual file order

### Solution 4: Use different magnitude source
If instrumental magnitudes are fundamentally wrong, consider:
- Reading magnitudes from the `.cat.ucac5` file instead
- Using Gaia magnitudes only (no VAST magnitude filtering)
- Skipping magnitude validation in Stage 1

## Expected Next Steps

1. **Run next VAST job**
2. **Check debug logs** for actual Median_magnitude values
3. **If still negative**:
   - Use the log values to infer correct column order
   - Update VAST_STAT_COLUMNS definition
   - OR implement alternative magnitude source

4. **If now positive**:
   - Confirm Gaia matching works correctly
   - Check Stage 1 vs Stage 2 success rates
   - Verify delta_mag values are reasonable (~1-2)

## Why This Happened

The VAST pipeline has several magnitude sources:
1. **Instrumental magnitudes** in statistics log (negative, raw VAST output)
2. **VAST calibration output** in `.cat.ucac5` file (positive, calibrated)
3. **Post-calibration scaling** using Gaia reference (further adjusted)

The code attempted to:
- Use instrumental magnitudes (option 1) for Gaia matching ❌
- Then run calibration to get corrected values (option 2) ✅
- Then scale based on Gaia reference (option 3) ✅

But the ORDER was wrong: we were using uncalibrated magnitudes (option 1) for matching, then calibrating later. The fix (enabled Step 4.5) should have corrected this, but the debug logs suggest the magnitudes are STILL coming from the instrumental source.

This could mean:
- Step 4.5 calibration isn't producing the `.cat.ucac5` file
- The magnitude calibration step is failing silently
- The magnitudes aren't being read from the calibrated source after all

## Next Investigation

The enhanced debug logging will show us:
1. Whether magnitude_calibration.sh is producing output
2. Whether the `.cat.ucac5` file is being found
3. Whether the `_read_vast_catalog_ucac5()` call is updating the DataFrame
4. What exact values are in the `Median_magnitude` column when Gaia matching runs

This will pinpoint the exact source of the problem!
