# VAST Candidates File Selection Feature - User Guide

**Feature Added**: 2026-02-15
**Status**: ✅ Ready for Production
**Backward Compatible**: Yes - existing jobs unaffected

## Quick Summary

Users can now select which candidate file to parse when creating VAST jobs:

1. **Default mode** (unchecked): Analyzes VAST's top candidates (fast, curated)
2. **Details mode** (checked): Analyzes all detected stars with smart filtering

## How to Use

### Creating a Job

1. Go to **VAST Automation** page
2. Click **"New Job"** button
3. Fill in required fields:
   - Target Name
   - Source Type (select "Local Path")
   - Local Path (to FITS images)
4. **NEW**: Check the box **"Use detailed candidates file"** (optional)
5. Click **"Start Processing"**

### Understanding the Options

#### Default Mode (Unchecked) ✅
- **File used**: `vast_autocandidates.log`
- **Candidates**: ~690 (VAST's top picks based on variability indices)
- **Best for**: Quick analysis of most interesting candidates
- **Speed**: Fast (fewer candidates to process)
- **Fallback**: If autocandidates.log missing, uses details file with FRACTION_OF filtering

#### Details Mode (Checked) ☑️
- **File used**: `vast_autocandidates_details.log`
- **Candidates**: All detected stars (minus filtering)
- **Filtering applied**:
  - ❌ Excludes FRACTION_OF_FAINTEST / FRACTION_OF_BRIGHTEST (calibration stars)
  - ❌ Excludes ID-only rows (rows with just star ID, no data)
- **Best for**: Complete analysis, finding fainter candidates
- **Speed**: Slower (more candidates = more processing)
- **Error handling**: Fails with clear message if file is missing

### Filtering Details

**What is FRACTION_OF?**
- Marks reference/calibration stars used by VAST for magnitude scale
- Not real candidates for variability study
- Example: `FRACTION_OF_BRIGHTEST`, `FRACTION_OF_FAINTEST`

**What are ID-only rows?**
- Lines in details file with just the star ID, no variability flags
- Filtered OUT in details mode, kept in default fallback mode
- Allows details mode to be more selective

## Viewing Job Details

After creating a job, view its details page to see:
- **Processing Options** section showing which flags were active
  - "Skip VAST" badge (if applicable)
  - "Detailed Candidates File" badge (if you selected it)
- All results and cross-match data as usual

## Technical Details

### Processing Parameters

Jobs store this in the `processing_params` JSON field:

```json
{
  "skip_vast": false,
  "use_details_file": true
}
```

Both flags are optional. If missing, they default to `false`.

### Candidate File Formats

**vast_autocandidates.log** (simple list):
```
out00001
out00234
out00567
```

**vast_autocandidates_details.log** (fixed-width):
```
out00001         PERIODIC
out00234         FRACTION_OF_BRIGHTEST
out00567
```

Columns:
- 0-12: Star ID
- 13+: Variability flags/notes

### File Selection Logic

```
IF user selected "Use details file"
    THEN use vast_autocandidates_details.log exclusively
    FILTER OUT: FRACTION_OF + ID-only rows
    ERROR: if file missing
ELSE
    IF vast_autocandidates.log exists
        THEN use it (no filtering)
    ELSE IF vast_autocandidates_details.log exists
        THEN use it as fallback
        FILTER OUT: FRACTION_OF only (keep ID-only)
    ELSE
        THEN use all stars from statistics log
```

## Example Scenarios

### Scenario 1: Quick Analysis of Interesting Stars
- **Action**: Leave "Use detailed candidates file" UNCHECKED
- **Result**: Analyzes ~690 top candidates from autocandidates.log
- **Time**: Fast (< 1 hour typically)
- **Use case**: Initial survey, finding obvious variables

### Scenario 2: Comprehensive Analysis
- **Action**: Check "Use detailed candidates file"
- **Result**: Analyzes all detected stars (minus calibration markers)
- **Time**: Slower (depends on image count, but potentially several hours)
- **Use case**: Hunting for faint variables, published catalogs

### Scenario 3: Re-analyze with Different Settings
- **Action**:
  1. Use "Skip VAST" if VAST already run
  2. Select "Use detailed candidates file" for different filtering
- **Result**: Reuses existing VAST output with new parsing
- **Time**: Very fast (no VAST re-execution)
- **Use case**: Experimenting with different candidate sets

## FAQ

**Q: What's the difference in candidate count?**
A: Typically:
- Default mode: ~690 candidates
- Details mode: ~690-1500 candidates (depends on number of ID-only rows)
- The difference is ID-only rows that have no variability flags

**Q: Which mode should I use?**
A:
- Use **default** for quick surveys and most analysis
- Use **details** if you want to hunt for fainter or less obvious variables
- Use **details** if you suspect the autocandidates.log was too selective

**Q: What if I select details mode but the file doesn't exist?**
A: The job will fail with a clear error message indicating that the details file was required but missing. This typically means VAST wasn't run properly or the directory structure is wrong.

**Q: Can I change the mode for an existing job?**
A: Not directly, but you can use "Skip VAST" to re-process with different settings:
1. Create new job
2. Enable "Skip VAST"
3. Set "Use detailed candidates file" to desired state
4. Start processing

**Q: Is this backward compatible?**
A: Yes, 100%! Existing jobs and workflows are unaffected. The flag is optional and defaults to standard behavior.

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| Details mode job fails | vast_autocandidates_details.log missing | Re-run VAST, or use default mode |
| Fewer candidates than expected | ID-only filtering in details mode | This is expected - keep them filtered for data quality |
| Default mode uses fallback file | autocandidates.log not created | Check VAST ran successfully |
| Processing slower than expected | Analyzing more candidates | This is expected with details mode - consider default mode |

## API Reference

### Job Creation Endpoint

**POST** `/agata/admin/api/vast/jobs`

Request body:
```json
{
  "target_name": "Betelgeuse",
  "source_type": "local_path",
  "source_location": "/path/to/fits",
  "processing_params": {
    "skip_vast": false,
    "use_details_file": true
  }
}
```

All `processing_params` are optional.

## Support

For issues or questions:
1. Check job detail page for error message
2. Verify VAST output files exist in the specified directory
3. Review logs in the job's current_step field
4. Contact admin if persistent

---

**Implementation Date**: 2026-02-15
**Files Modified**: 4 (model, 2 templates, 1 service)
**Lines Added**: ~120
**Breaking Changes**: None
**Database Migrations**: None required
