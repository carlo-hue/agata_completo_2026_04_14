# Debugging Notes: Magnitude Calculation Issue

**Status**: Debug logging added, awaiting test results
**Issue**: Δmag values are ~20+ instead of ~2 (incorrect vast_mag being passed)

## Symptoms

From VAST job logs:
```
[STAGE 2 MATCH] Star out31321.dat: selected Gaia 5734104703954270464 @ 13.94" (Δmag=20.75) - AMBIGUOUS
```

This indicates:
- Gaia Vmag = 7.895 (correct)
- Calculated Δmag = 20.75
- If Δmag = |Vmag - vast_mag|, then vast_mag ≈ -12.855 (WRONG!)

Expected vast_mag should be ~9.827 (from VAST Median_magnitude)

## Root Cause Hypothesis

The `vast_mag` parameter being passed to the worker function is negative or otherwise incorrect. This could be due to:

1. **Column Mismatch**: The `Median_magnitude` column is being read from the wrong index
2. **Data Corruption**: The `Median_magnitude` values are modified before reaching the worker
3. **Row Misalignment**: The `.iterrows()` loop is pulling data from misaligned rows
4. **Type Issue**: The magnitude value is being interpreted incorrectly (e.g., as string, int, etc.)

## Debug Logging Added

Added comprehensive debug logging to `vast_service.py`:

### 1. Before Worker Submission (lines ~1254-1262)
```python
# Log column info
logger.debug(f"stars_valid columns: {stars_valid.columns.tolist()}")
logger.debug(f"stars_valid dtypes: {stars_valid.dtypes.to_dict()}")

# Log first row sample
first_row = stars_valid.iloc[0]
logger.debug(f"First row sample: name={first_row['name']}, ra={first_row['ra']}, "
             f"dec={first_row['dec']}, Median_magnitude={first_row['Median_magnitude']}")

# Log each worker submission (first 3)
if idx < 3:
    logger.debug(f"[WORKER SUBMIT {idx}] name={name}, ra={ra:.6f}, dec={dec:.6f}, Median_mag={vast_mag}")
```

### 2. In Worker Function (lines ~97-101)
```python
# Log parameter types
vast_mag_str = f"{vast_mag:.2f}" if vast_mag else "N/A"
logger_worker.info(f"[GAIA TWO-STAGE] Star {name} @ RA={ra:.6f}, Dec={dec:.6f}, "
                   f"VAST_mag={vast_mag_str} (type={type(vast_mag).__name__})")

# Warn if magnitude out of range
if vast_mag is not None and (vast_mag < -5 or vast_mag > 30):
    logger_worker.warning(f"[GAIA WARNING] Star {name}: VAST_mag={vast_mag} is outside reasonable range!")
```

## What to Check in Logs

When running the next VAST job test, look for:

1. **Column names**: Should show `['ra', 'dec', 'name', 'Median_magnitude']`
2. **Data types**: Should show `Median_magnitude` as `float64`
3. **First row sample**: Should show something like:
   ```
   First row sample: name=out31321, ra=133.929541, dec=-14.044190, Median_magnitude=9.827
   ```
4. **Worker submission**: Should show:
   ```
   [WORKER SUBMIT 0] name=out31321, ra=133.929541, dec=-14.044190, Median_mag=9.827
   ```
5. **Worker received**: Should show:
   ```
   [GAIA TWO-STAGE] Star out31321 @ RA=133.929541, Dec=-14.044190, VAST_mag=9.83 (type=float64)
   ```

## If Debug Logs Show Correct Values

If the logs show that `vast_mag` is being correctly received as 9.827, then the issue is in the calculation AFTER that. Check:
- Is `_calculate_vmag_from_gaia()` returning correct values?
- Is the delta_mag calculation correct: `delta_mag = abs(vmag - vast_mag)`?
- Are the Gaia Vmag values correct?

## If Debug Logs Show Incorrect Values

If the logs show negative or unexpected vast_mag values, then:
- Check column alignment in DataFrame
- Verify `.iterrows()` is pulling correct row data
- Check if `Median_magnitude` column was properly added to `stars_valid`
- Verify no modifications to `stars_df` or `Median_magnitude` between filtering and worker submission

## Next Steps

1. Run a test VAST job
2. Check Flask/application logs for debug output
3. Look for pattern of incorrect magnitude values
4. Report findings to enable targeted fix

## Additional Notes

- The `.dat` suffix in star names (e.g., "out31321.dat") is added somewhere downstream
  - In the statistics file, names might be just "out31321"
  - This is expected and should not affect magnitude values
- The row iteration uses `.iterrows()` which returns (index, Series) pairs
  - Series should support dict-like access via `row['column_name']`
  - If there's a KeyError here, it means the column doesn't exist in the DataFrame
