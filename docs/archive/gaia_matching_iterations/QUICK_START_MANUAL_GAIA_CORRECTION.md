# Quick Start: Manual Gaia Match Correction Feature

**Status**: ✅ Ready to test with next VAST job

---

## What Changed?

### 1. Pre-Phase Optimization (Silent Fix)
- Pre-phase query now searches 100" radius instead of 10"
- Result: Better calibration offset calculation
- User Impact: None (automatic improvement)

### 2. Semantic Fix (Visible Improvement)
- Stars with no Gaia match now show correctly:
  - **Before**: "Ambiguous" badge (confusing)
  - **After**: "-" dash + search button (clear meaning)

### 3. Manual Verification Feature (New)
- Every VAST result row has a **search icon button** ✍️
- Click to open modal and search for Gaia matches
- Verify current match or select alternative
- User can manually correct any match in seconds

---

## How to Use the Manual Correction Feature

### For Verification (Checking a match is correct)

1. **Open VAST job detail page**
   - Go to `/agata/admin/vast/`
   - Click on completed job (e.g., Job 155)
   - Scroll to Results table

2. **Find the star you want to verify**
   - Look in the results table
   - Find row with your star (e.g., out31321)

3. **Click the search icon** 🔍
   - Button is in the Gaia ID column
   - Opens a modal dialog

4. **View current match info**
   - Shows VAST ID, coordinates, magnitude
   - Shows search radius (default 100")

5. **Search for candidates**
   - Click "Search" button
   - Wait 2-5 seconds for results
   - Modal shows all Gaia sources in radius (sorted by distance)

6. **Verify the match**
   - Current match should be near the top (closest distance)
   - If correct: Close modal
   - If wrong: Select correct match (see below)

7. **(Optional) Check SIMBAD**
   - Click "View in SIMBAD" button
   - Opens SIMBAD at VAST coordinates
   - 10 arcsec search radius

### For Correction (Fixing a wrong match)

Same as above (steps 1-5), then:

6. **Select correct match**
   - Find the Gaia source you want
   - Click the green "Select" button on that row

7. **Confirm**
   - Dialog asks: "Select Gaia XXXXXXXXX?"
   - Click OK to confirm

8. **Page reloads**
   - Database updated automatically
   - Results table shows new Gaia ID
   - Done! ✅

### For No-Match Cases (Assigning a Gaia match)

1. **Follow steps 1-5** (normal search)

2. **Select from candidates**
   - Modal shows all candidates
   - Pick the best match:
     - Usually closest (top row)
     - Or most similar magnitude
   - Click "Select"

3. **Confirm & update**
   - Dialog appears
   - Click OK
   - Database updated

---

## Common Scenarios

### Scenario 1: "I want to verify out27251 is correct"
1. Click search icon on out27251 row
2. Modal opens, click Search
3. See candidates list with distances
4. Current match is at top? ✓ Correct
5. Not at top? ✗ Can select better one

### Scenario 2: "out38700 has no Gaia match, I want to assign one"
1. Click search icon on out38700 row
2. Modal opens, shows "- Current: None"
3. Click Search (radius 100")
4. See list of 10-20 candidates
5. Pick closest one or best magnitude match
6. Click Select
7. Done! Now has Gaia source ID

### Scenario 3: "I want to use 50\" search radius instead of 100\""
1. Click search icon
2. Modal opens
3. Change radius from 100 to 50 in the input field
4. Click Search
5. See candidates within 50 arcsec only
6. Select if needed

---

## What Happens Behind the Scenes

### Search Endpoint
```
POST /agata/admin/api/vast/results/<id>/search-gaia
```
- Queries Vizier's Gaia DR3 catalog
- Filters to Gmag < 18 (avoids faint false positives)
- Calculates distance from VAST coordinates
- Returns results sorted by distance

### Update Endpoint
```
PUT /agata/admin/api/vast/results/<id>/update-gaia
```
- Saves selected Gaia source ID to database
- Sets is_ambiguous = False (manually selected = confirmed)
- Commits transaction
- Returns success/error

### Both Endpoints
- Require superuser login
- Timeout: 20 seconds per Vizier query
- Error handling: Shows error message if search fails

---

## Troubleshooting

### "Modal doesn't open"
- Check browser console for errors
- Try refreshing page
- Verify logged in as superuser

### "Search button not visible"
- Upgrade browser (modern CSS required)
- Try different browser (Chrome/Firefox recommended)
- Check Flask app is running

### "Search returns 0 results"
- Star may be outside Gaia footprint
- Try larger radius (300" max)
- Try SIMBAD link to verify coordinates

### "Select doesn't work"
- Confirmation dialog may be behind modal (try clicking OK if hidden)
- Check browser console for errors
- Verify superuser permissions

### "Page doesn't reload after selection"
- Manual reload: Press F5
- Check if database update failed (backend error)
- Verify database connection

---

## Tips & Tricks

### Best Practices
1. **Always verify before correcting**
   - Click search first to see candidates
   - Confirm current match is wrong before selecting new one

2. **Use distance as primary criterion**
   - Closest match = most likely correct
   - Magnitude similarity = secondary check

3. **Check SIMBAD when unsure**
   - Verify star name/designation
   - Check variability type
   - Confirm coordinates are reasonable

4. **Batch verification approach**
   - Do ambiguous results first (⚠ badge)
   - Then no-match results (-  with search button)
   - Document any unusual corrections

### Advanced
1. **Search in smaller radius first**
   - Try 50" to find closest matches only
   - If nothing, expand to 100" or 300"

2. **Magnitude filtering**
   - UI shows Gmag (already filtered Gmag < 18)
   - Compare with VAST magnitude in modal header
   - Large differences (>2 mag) = likely wrong

3. **Coordinate verification**
   - Modal shows VAST coordinates
   - Gaia coordinates in table
   - Huge difference (>300") = probably wrong field

---

## Technical Details (For Developers)

### Files Modified
- `agata/admin/services/vast_service.py` - Pre-phase fix + semantic fix
- `agata/admin/routes/vast_automation.py` - 2 new API endpoints
- `agata/templates/admin/vast/job_detail.html` - UI + JavaScript

### Authorization
- `@login_required` - Must be logged in
- `@superuser_required` - Must be superuser

### Performance
- Search: 2-5 seconds (Vizier query)
- Update: <100ms (database)
- Modal: Instant (CSS)

### Data Flow
```
Click button → Modal opens → User enters radius → POST /search-gaia
→ Vizier query → Sort by distance → Display results → User selects
→ User confirms → PUT /update-gaia → Database updates → Page reloads
```

---

## Next Steps

1. **Run next VAST job** (job 155+)
2. **Monitor results**:
   - Check out27251 status: should be "No Match" (not "Ambiguous")
   - Check out38700 status: should be "No Match" (not "Ambiguous")
3. **Test search feature**:
   - Click search icon on several results
   - Verify candidates are reasonable
   - Try manual selection on one result
   - Verify page reloads with new Gaia ID
4. **Batch verification** (if needed):
   - Use to check all ambiguous results
   - Document any corrections
   - Report any anomalies

---

## Questions?

- **"Why doesn't X work?"** → Check Troubleshooting section above
- **"Can I do batch corrections?"** → Not yet, manual one-by-one for now
- **"Is my correction saved?"** → Yes, database updates on selection
- **"Can I undo a correction?"** → Yes, select different match
- **"What if I select wrong Gaia?"** → Can always search again and correct

---

**Implementation Status**: ✅ COMPLETE & READY
**Deployment**: Ready after next Flask restart
**Testing**: Next VAST job will provide real-world test
