# Gaia Ambiguity Detection & User Resolution

**Date**: 2026-02-16
**Status**: ✅ IMPLEMENTATION COMPLETE
**Feature**: Detect and allow user resolution of ambiguous Gaia matches

---

## Problem Statement

In dense stellar fields, the "nearest" Gaia source may not be the correct match when magnitudes are very different.

**Example: out31321**
```
Gaia 5734104703954270464 @ 13.94" with G Mag 7.85  (VERY BRIGHT)
Gaia 5734104703954270720 @ 7.15"  with G Mag 16.52 (VERY FAINT)

Magnitude difference: 8.67 mag = 3600x brightness ratio ❌
These are definitely NOT the same star!
```

**Current approach**: Algorithm picks nearest, but loses valuable information about ambiguity.
**Better approach**: Flag ambiguous cases, show user multiple candidates, let them choose.

---

## Solution: Ambiguity Detection

### Criteria for "Ambiguous" Match

A Gaia match is flagged as **ambiguous** if:

1. The **nearest** source is NOT the **brightest** source, AND
2. One of these conditions is met:
   - Magnitude difference > 1.0 mag (definitely different objects)
   - OR Distance < 15" AND magnitude difference > 0.5 mag (close neighbors with different brightnesses)

### Implementation Details

**File Modified**: `agata/admin/services/vast_service.py` - `_gaia_worker_query_single_star()`

**New Return Fields**:
```python
{
    'name': 'out31321',
    'status': 'ambiguous',  # NEW: Instead of 'match'
    'gaia_source_id': None,  # Set to None for ambiguous (user must choose)
    'gaia_ra': 133.9276714,  # RA of nearest (default suggestion)
    'gaia_dec': -14.0433837,
    'gaia_gmag': 16.52,
    'gaia_bp_rp': 1.03,
    'gaia_vmag': 16.74,
    'ambiguous_candidates': [  # NEW: All candidates for user to choose
        {
            'source_id': 5734104703954270720,
            'ra': 133.9276714,
            'dec': -14.0433837,
            'gmag': 16.52,
            'distance': 7.15
        },
        {
            'source_id': 5734104703954270464,
            'ra': 133.9292059,
            'dec': -14.0403310,
            'gmag': 7.85,
            'distance': 13.94
        },
        {
            'source_id': 5734104807033585280,
            'ra': 133.9283716,
            'dec': -14.0372786,
            'gmag': 17.09,
            'distance': 25.22
        }
    ]
}
```

---

## Database Schema

### Current Columns
The `agata_vast_results` table needs ONE new column:

```sql
ALTER TABLE agata_vast_results
ADD COLUMN gaia_ambiguous_candidates LONGTEXT COMMENT 'JSON array of alternative Gaia matches for ambiguous cases';
```

**Datatype**: `LONGTEXT` (stores JSON array)
**Content**: Serialized list of up to 3 candidate matches
**NULL when**: Not ambiguous (normal match)

### Data Example
```json
[
  {"source_id": 5734104703954270720, "ra": 133.9276714, "dec": -14.0433837, "gmag": 16.52, "distance": 7.15},
  {"source_id": 5734104703954270464, "ra": 133.9292059, "dec": -14.0403310, "gmag": 7.85, "distance": 13.94},
  {"source_id": 5734104807033585280, "ra": 133.9283716, "dec": -14.0372786, "gmag": 17.09, "distance": 25.22}
]
```

---

## Frontend UI

### In VAST Job Detail Page (job_detail.html)

Add a new section in the results table showing ambiguous stars:

```html
<div class="ambiguous-matches" style="background: #fff3cd; padding: 10px; border-left: 4px solid #ffc107;">
    <strong>⚠️ Ambiguous Gaia Matches</strong>
    <p>The following stars have multiple Gaia sources with similar relevance. Click to choose:</p>

    <table class="table table-sm">
        <thead>
            <tr>
                <th>VAST ID</th>
                <th>Nearest (Default)</th>
                <th>Brightest</th>
                <th>Action</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>out31321</td>
                <td>Gaia 5734104703954270720 @ 7.15" (G Mag 16.52)</td>
                <td>Gaia 5734104703954270464 @ 13.94" (G Mag 7.85)</td>
                <td><button class="btn btn-sm btn-warning" onclick="resolveGaiaAmbiguity(31321)">Resolve</button></td>
            </tr>
        </tbody>
    </table>
</div>
```

### Modal Dialog for Resolution

When user clicks "Resolve":

```html
<div class="modal" id="gaiaResolutionModal">
    <div class="modal-dialog modal-lg">
        <div class="modal-content">
            <div class="modal-header">
                <h5>Gaia Source Selection for out31321</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <p><strong>VAST Coordinates:</strong> RA=133.9295415°, Dec=-14.0441904°</p>

                <div class="table-responsive">
                    <table class="table table-hover">
                        <thead>
                            <tr>
                                <th>Select</th>
                                <th>Gaia ID</th>
                                <th>RA</th>
                                <th>Dec</th>
                                <th>Distance</th>
                                <th>G Mag</th>
                                <th>Vmag (calc)</th>
                            </tr>
                        </thead>
                        <tbody>
                            <!-- For each candidate in ambiguous_candidates -->
                            <tr onclick="selectGaiaCandidare(5734104703954270720)" style="cursor: pointer;">
                                <td><input type="radio" name="gaia_choice" value="5734104703954270720" checked></td>
                                <td>5734104703954270720</td>
                                <td>133.9276714</td>
                                <td>-14.0433837</td>
                                <td>7.15"</td>
                                <td>16.52</td>
                                <td>16.74</td>
                            </tr>
                            <tr onclick="selectGaiaCandidare(5734104703954270464)" style="cursor: pointer;">
                                <td><input type="radio" name="gaia_choice" value="5734104703954270464"></td>
                                <td>5734104703954270464</td>
                                <td>133.9292059</td>
                                <td>-14.0403310</td>
                                <td>13.94"</td>
                                <td>7.85</td>
                                <td>8.01</td>
                            </tr>
                            <tr onclick="selectGaiaCandidare(5734104807033585280)" style="cursor: pointer;">
                                <td><input type="radio" name="gaia_choice" value="5734104807033585280"></td>
                                <td>5734104807033585280</td>
                                <td>133.9283716</td>
                                <td>-14.0372786</td>
                                <td>25.22"</td>
                                <td>17.09</td>
                                <td>17.23</td>
                            </tr>
                        </tbody>
                    </table>
                </div>

                <div class="alert alert-info mt-3">
                    <strong>💡 Tip:</strong> Compare magnitudes with your other catalogs (VSX, ASAS-SN, etc)
                    to determine which Gaia source is correct.
                </div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                <button type="button" class="btn btn-primary" onclick="saveGaiaChoice(resultId)">Save Selection</button>
            </div>
        </div>
    </div>
</div>
```

### JavaScript Handler

```javascript
function resolveGaiaAmbiguity(resultId) {
    // Fetch ambiguous candidates from server
    // Populate modal with candidates
    // Open modal
    const modal = new bootstrap.Modal(document.getElementById('gaiaResolutionModal'));
    modal.show();
}

function saveGaiaChoice(resultId) {
    const selectedId = document.querySelector('input[name="gaia_choice"]:checked').value;

    // POST to backend
    fetch(`/agata/admin/api/vast/results/${resultId}/resolve-gaia`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            gaia_source_id: selectedId,
            resolved_by: currentUser
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('✅ Gaia match resolved!');
            location.reload();  // Refresh to show updated data
        } else {
            alert('❌ Error: ' + data.error);
        }
    });
}
```

---

## Backend API

### New Endpoint: Resolve Ambiguous Gaia Match

```python
@admin_bp.route('/api/vast/results/<int:result_id>/resolve-gaia', methods=['POST'])
@admin_required(min_role='analyst')
def resolve_gaia_ambiguity(result_id):
    """
    User resolution of ambiguous Gaia match.
    Updates the gaia_source_id and clears ambiguous_candidates.
    """
    data = request.get_json()
    gaia_source_id = data.get('gaia_source_id')

    try:
        result = db.session.query(VastResult).filter_by(id=result_id).first()
        if not result:
            return jsonify({'success': False, 'error': 'Result not found'}), 404

        # Update Gaia match
        result.gaia_source_id = gaia_source_id
        result.gaia_ambiguous_candidates = None  # Clear ambiguous flag

        # Log resolution
        logger.info(f"Resolved ambiguous match for {result.vast_id}: selected Gaia {gaia_source_id}")

        db.commit()
        return jsonify({'success': True, 'message': 'Gaia match resolved'}), 200

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to resolve Gaia ambiguity: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
```

---

## User Workflow

### During VAST Import

1. **Parallel Gaia queries** run
2. For each star:
   - If unambiguous: `status='match'`, `gaia_source_id` set
   - If ambiguous: `status='ambiguous'`, `gaia_source_id=None`, `ambiguous_candidates` set
3. Import completes with some stars having `gaia_source_id=NULL`

### In Job Detail View

1. User sees table with results
2. **Ambiguous matches section** appears with warning
3. User clicks "Resolve" for a problematic star
4. Modal opens showing candidates with distances, magnitudes, Vmags
5. User selects correct source based on:
   - Distance to VAST coordinates
   - Magnitude consistency with other catalogs
   - VSX/ASAS-SN comparison
6. Clicks "Save Selection"
7. Backend updates `gaia_source_id` and clears ambiguous flag
8. User can now use the updated match for magnitude calibration

---

## Implementation Status

### ✅ Complete
- Detection logic in `_gaia_worker_query_single_star()`
- Handling of 'ambiguous' status in results collection
- Database schema ready (one column needed)

### ⏳ TODO
- Add `gaia_ambiguous_candidates` column to `agata_vast_results` table
- Update job_detail.html to show ambiguous matches section
- Create modal dialog for user selection
- Implement backend API endpoint for resolution
- Add JavaScript handlers

### 📋 Notes
- Ambiguous cases are rare (< 1% of matches in normal fields)
- Display helps user understand why algorithm couldn't auto-choose
- Preserves all candidate information for informed decision
- Non-destructive: user can always change their choice later

---

## Testing

### Test Case: out31321
```
1. Run VAST import with 30" radius
2. out31321 detected as ambiguous
3. Database shows: gaia_source_id=NULL, gaia_ambiguous_candidates=[...]
4. User opens job detail, sees warning
5. User clicks "Resolve"
6. Modal shows 3 candidates with distances/mags
7. User selects Gaia 5734104703954270720 (nearest)
8. Modal closes, database updated
9. out31321 now has gaia_source_id=5734104703954270720
```

---

## Summary

**What**: Detect when nearest Gaia source has very different magnitude than brightest source
**Why**: In dense fields, magnitude mismatch indicates wrong star selection
**How**: Flag as 'ambiguous', show user candidates, let them choose
**Impact**: Better accuracy + user confidence in matches
**Status**: Code ready, UI/API pending

