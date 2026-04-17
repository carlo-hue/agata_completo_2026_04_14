# VAST Candidates File Selection - Implementation Details

## Files Modified

### 1. agata/auth_models/vast_job.py (1 line changed)

**Location**: Line 64
**Change**: Updated comment for processing_params field

```python
# BEFORE
comment="Parametri VAST: {threshold, field_size, ...}"

# AFTER
comment="Parametri processing: {skip_vast: bool, use_details_file: bool, ...}"
```

**Why**: Documents the new flag for developers reviewing the code

---

### 2. agata/templates/admin/vast/jobs.html (60+ lines added/modified)

#### Addition 1: New Checkbox HTML (lines ~191-208)

```html
<!-- Use Detailed Candidates File checkbox (visible only for local_path) -->
<div class="mb-3" id="useDetailsFileSection" style="display: none;">
    <div class="form-check form-switch">
        <input class="form-check-input" type="checkbox" id="useDetailsFile" name="use_details_file">
        <label class="form-check-label" for="useDetailsFile">
            <strong>Use detailed candidates file</strong>
            <i class="fas fa-info-circle text-muted"
               data-bs-toggle="tooltip"
               title="Parse vast_autocandidates_details.log instead of vast_autocandidates.log. Includes all detected stars with filtering for calibration markers."></i>
        </label>
    </div>
    <small class="form-text text-muted">
        Check this to analyze all detected stars instead of only VAST's top candidates.
        Rows with FRACTION_OF flags or ID-only entries will be excluded.
    </small>
</div>
```

#### Addition 2: Updated Form Submission JavaScript (lines ~254-262)

**BEFORE**:
```javascript
const skipVast = document.getElementById('skipVast').checked;

const data = {
    target_name: targetName,
    source_type: sourceType,
    source_location: sourceLocation,
    processing_params: skipVast ? { skip_vast: true } : {}
};
```

**AFTER**:
```javascript
const skipVast = document.getElementById('skipVast').checked;
const useDetailsFile = document.getElementById('useDetailsFile').checked;

const processingParams = {};
if (skipVast) {
    processingParams.skip_vast = true;
}
if (useDetailsFile) {
    processingParams.use_details_file = true;
}

const data = {
    target_name: targetName,
    source_type: sourceType,
    source_location: sourceLocation,
    processing_params: processingParams
};
```

#### Addition 3: Updated Visibility Handler (lines ~312-347)

**BEFORE**:
```javascript
if (this.value === 'drive_folder') {
    driveFolderSection.style.display = 'block';
    localPathSection.style.display = 'none';
    skipVastSection.style.display = 'none';
    // ...
} else if (this.value === 'local_path') {
    driveFolderSection.style.display = 'none';
    localPathSection.style.display = 'block';
    skipVastSection.style.display = 'block';
    // ...
}
```

**AFTER**:
```javascript
const useDetailsFileSection = document.getElementById('useDetailsFileSection');

if (this.value === 'drive_folder') {
    driveFolderSection.style.display = 'block';
    localPathSection.style.display = 'none';
    skipVastSection.style.display = 'none';
    useDetailsFileSection.style.display = 'none';
    document.getElementById('skipVast').checked = false;
    document.getElementById('useDetailsFile').checked = false;
    // ...
} else if (this.value === 'local_path') {
    driveFolderSection.style.display = 'none';
    localPathSection.style.display = 'block';
    skipVastSection.style.display = 'block';
    useDetailsFileSection.style.display = 'block';  // NEW
    // ...
}
```

---

### 3. agata/admin/services/vast_service.py (~80 lines modified)

**Method**: `_parse_vast_output()` (lines 860-942)

#### Key Changes:

1. **Flag Check** (line ~876):
```python
use_details_file = self.job.processing_params.get('use_details_file', False) if self.job.processing_params else False
```

2. **Conditional Logic** (lines ~901-931):
```python
if use_details_file:
    # User explicitly requested details file (stricter filtering)
    if not os.path.exists(candidates_details_log):
        raise FileNotFoundError(f"Detailed candidates file not found...")
    
    logger.info("Using vast_autocandidates_details.log (user selected)")
    with open(candidates_details_log, 'r') as f:
        for line in f:
            name = line[0:12].strip()
            candidate_flag = line[13:].strip() if len(line) > 13 else ''
            
            # Filter 1: FRACTION_OF
            if 'FRACTION_OF' in candidate_flag:
                continue
            
            # Filter 2: ID-only rows
            if not candidate_flag:
                continue
            
            candidate_names.add(name)

else:
    # Default behavior: priority system (unchanged logic)
    if candidates_log and os.path.exists(candidates_log):
        # Use autocandidates.log
        with open(candidates_log, 'r') as f:
            candidate_names = set(line.strip() for line in f if line.strip())
    
    elif candidates_details and os.path.exists(candidates_details):
        # Fallback to details with FRACTION_OF filtering
        with open(candidates_details, 'r') as f:
            for line in f:
                name = line[0:12].strip()
                candidate_flag = line[13:].strip() if len(line) > 13 else ''
                if 'FRACTION_OF' not in candidate_flag:
                    candidate_names.add(name)
```

---

### 4. agata/templates/admin/vast/job_detail.html (~15 lines added)

**Location**: In "Job Info" card, after "Created By" field

```html
{% if job.processing_params %}
<dt>Processing Options</dt>
<dd>
    {% if job.processing_params.get('skip_vast') %}
        <span class="badge badge-info">Skip VAST</span>
    {% endif %}
    {% if job.processing_params.get('use_details_file') %}
        <span class="badge badge-primary">Detailed Candidates File</span>
    {% endif %}
    {% if not job.processing_params.get('skip_vast') and not job.processing_params.get('use_details_file') %}
        <span class="text-muted small">Default</span>
    {% endif %}
</dd>
{% endif %}
```

---

## Code Flow Diagram

```
User Creates Job
    ↓
Form shows checkboxes:
  □ Skip VAST
  □ Use detailed candidates file
    ↓
User selects options (e.g., use_details_file=TRUE)
    ↓
JavaScript builds processingParams object:
  {
    "use_details_file": true
  }
    ↓
POST /agata/admin/api/vast/jobs with processingParams
    ↓
Backend creates VastJob with processing_params
    ↓
Job execution starts
    ↓
_parse_vast_output() called
    ↓
Read use_details_file flag from processing_params
    ↓
IF use_details_file == TRUE:
    Use vast_autocandidates_details.log ONLY
    Filter: FRACTION_OF ✗ + ID-only ✗
    ~X candidates (stricter)
ELSE:
    Use priority: autocandidates.log > fallback
    Filter: FRACTION_OF ✗ (in fallback only)
    ~Y candidates
    ↓
Continue with cross-matching, etc.
```

---

## Backward Compatibility Verification

### Old Code Path (No Flag)
```python
# Before implementation
processing_params = {}  # or None

# In _parse_vast_output():
# Would skip the if use_details_file block
# Would enter else block (default priority system)
# ✅ Behavior unchanged
```

### New Code Path (With Flag)
```python
# With new implementation
processing_params = {"use_details_file": True}

# In _parse_vast_output():
use_details_file = True
# Enters if use_details_file block
# Uses details file with stricter filtering
# ✅ New behavior as intended
```

### Mixed Parameters
```python
processing_params = {
    "skip_vast": True,
    "use_details_file": True
}

# Both flags can coexist and work together
# ✅ No conflicts
```

---

## Testing Checklist

- [x] Syntax validation (Python + Jinja2)
- [x] Parameter structure correct (JSON)
- [x] Filtering logic tested with sample data
- [x] Form field names consistent everywhere
- [x] Visibility logic correct (local_path only)
- [x] Checkbox unchecked by default
- [x] Processing params passed to backend
- [x] Backend reads flag correctly
- [x] Default path when flag missing
- [x] Error handling for missing details file
- [x] Logging updated for debugging
- [x] Job detail page shows processing options
- [x] No breaking changes to existing code

---

## Performance Impact

### Frontend
- Minimal: One additional checkbox, no extra data transfer

### Backend
- **Same**: When flag is false (default behavior unchanged)
- **Potentially more**: When flag is true (more candidates = more processing)
- Example: 690 candidates → 1500 candidates = ~2.2x more work

### Storage
- No change (no new database columns, only JSON flag)

---

## Rollback Plan

If needed to revert:

1. Remove checkbox HTML from jobs.html
2. Remove JavaScript changes from jobs.html
3. Revert vast_service.py to original _parse_vast_output()
4. Remove Processing Options display from job_detail.html
5. No database migration needed (flag simply ignored)

---

## Future Enhancement Ideas

1. **Batch Display**: Show candidate count difference in UI
   ```
   Default: 690 candidates | Details: 1,247 candidates
   ```

2. **Advanced Filtering**: Allow users to select specific filters
   ```
   ☐ Exclude FRACTION_OF
   ☐ Exclude ID-only
   ☐ Minimum variability threshold
   ```

3. **API Endpoint**: Pre-job file availability check
   ```
   GET /api/vast/candidates-available?path=/path/to/fits
   Returns: {has_autocandidates: true, has_details: true, details_count: 15255}
   ```

4. **Analytics**: Track usage of each mode
   ```
   Default mode: 85% of jobs
   Details mode: 15% of jobs
   ```

---

**Implementation Date**: 2026-02-15
**Status**: ✅ Complete and tested
**Ready for**: Production deployment
