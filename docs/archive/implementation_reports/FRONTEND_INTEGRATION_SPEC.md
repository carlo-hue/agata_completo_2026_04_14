# Frontend Integration Specification - TESS QLP Optimization

## Overview
Backend now supports passing serialized SearchResult to eliminate redundant Lightkurve searches.

## API Changes

### Endpoint 1: POST `/agata/admin/api/catalogs/tess/qlp/search-sectors`

#### Request (No changes)
```json
{
  "project_id": 123
}
```

#### Response (NEW: added `lcfs_serialized`)
```json
{
  "success": true,
  "gaia_id": "1234567890",
  "tic_id": 25155310,
  "tmag": 10.234,
  "sectors": [
    {
      "sector": 1,
      "idx": 0,
      "duration_days": 35.2,
      "date_start": "Jan 2019",
      "date_end": "Feb 2019"
    },
    // ... more sectors
  ],
  "lcfs_serialized": "gANjYXN0cm9xdWVyeS5zZWFyY2guc2VhcmNoX3Jlc3VsdHM=...",
  "message": "Trovati 47 settori QLP disponibili"
}
```

### Endpoint 2: POST `/agata/admin/api/catalogs/tess/qlp/download-sector`

#### Request (NEW: add `lcfs_serialized`)
```json
{
  "gaia_id": "1234567890",
  "tic_id": 25155310,
  "sector": 5,
  "sector_idx": 4,
  "lcfs_serialized": "gANjYXN0cm9xdWVyeS5zZWFyY2guc2VhcmNoX3Jlc3VsdHM=..."
}
```

#### Response (No changes)
```json
{
  "success": true,
  "import_id": 456,
  "points_imported": 1024,
  "source_name": "TESS-QLP_Sector5",
  "gaia_id": "1234567890",
  "sector": 5
}
```

---

## Implementation Steps

### Step 1: Capture `lcfs_serialized` from Step 1
```javascript
const searchResponse = await fetch('/agata/admin/api/catalogs/tess/qlp/search-sectors', {
  method: 'POST',
  body: JSON.stringify({ project_id: projectId })
});

const searchData = await searchResponse.json();

// ✅ Store this for Step 2
const lcfsSerializedData = searchData.lcfs_serialized;
console.log('Received serialized SearchResult:', lcfsSerializedData);
```

### Step 2: Pass `lcfs_serialized` to Step 2
```javascript
// When user clicks "Download Sector 5"
const downloadResponse = await fetch('/agata/admin/api/catalogs/tess/qlp/download-sector', {
  method: 'POST',
  body: JSON.stringify({
    gaia_id: searchData.gaia_id,
    tic_id: searchData.tic_id,
    sector: sectorNumber,
    sector_idx: sectorIndex,
    lcfs_serialized: lcfsSerializedData  // ← ADD THIS LINE
  })
});

const downloadData = await downloadResponse.json();
```

---

## Complete Working Example

```javascript
class TESSQlpDownloader {
  constructor() {
    this.lcfsSerializedData = null;
  }

  async searchSectors(projectId) {
    try {
      console.log('Step 1: Searching QLP sectors...');

      const response = await fetch('/agata/admin/api/catalogs/tess/qlp/search-sectors', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_id: projectId })
      });

      const data = await response.json();

      if (!data.success) {
        console.error('Search failed:', data.error);
        return null;
      }

      // ✅ Store serialized object for later use
      this.lcfsSerializedData = data.lcfs_serialized;

      console.log(`✅ Found ${data.sectors.length} sectors`);
      console.log('✅ Serialized SearchResult ready for download');

      return data;
    } catch (error) {
      console.error('Search error:', error);
      return null;
    }
  }

  async downloadSector(sectorInfo, searchData) {
    try {
      console.log(`Step 2: Downloading sector ${sectorInfo.sector}...`);

      const downloadPayload = {
        gaia_id: searchData.gaia_id,
        tic_id: searchData.tic_id,
        sector: sectorInfo.sector,
        sector_idx: sectorInfo.idx,
        lcfs_serialized: this.lcfsSerializedData  // ← PASS IT HERE
      };

      const response = await fetch('/agata/admin/api/catalogs/tess/qlp/download-sector', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(downloadPayload)
      });

      const data = await response.json();

      if (!data.success) {
        console.error('Download failed:', data.error);
        return null;
      }

      console.log(`✅ Downloaded ${data.points_imported} points`);
      return data;
    } catch (error) {
      console.error('Download error:', error);
      return null;
    }
  }
}

// Usage
const downloader = new TESSQlpDownloader();

// Step 1: Search
const searchData = await downloader.searchSectors(123);

// Step 2: Download (when user selects sector)
const selectedSector = searchData.sectors[0];
const result = await downloader.downloadSector(selectedSector, searchData);
```

---

## Performance Verification

### Logs to Check

**Before optimization** (old frontend):
```
[Backend] Lightkurve search for TIC (Step 2)... (8-15 seconds)
[Backend] Re-searching QLP sectors (lcfs_serialized not provided or failed)
```

**After optimization** (updated frontend):
```
[Backend] ✅ Deserialized Lightkurve SearchResult (found 47 results)
[Backend] Download FITS... (starts immediately, no delay)
```

### Timeline Comparison

**Before**:
```
Step 1: 13-55s (Gaia lookup + Lightkurve search)
Step 2: 33-95s (Lightkurve search AGAIN + download + process)
Total: 46-150s
```

**After**:
```
Step 1: 13-55s (Gaia lookup + Lightkurve search)
Step 2: 25-81s (Deserialization <1s + download + process)
Total: 38-136s ✅ FASTER by 8-14 seconds!
```

---

## Error Handling

### Case 1: `lcfs_serialized` not provided (old frontend)
```
Backend: Re-searches Lightkurve (fallback)
Result: Works but slower (8-15s extra)
Impact: Backward compatible
```

### Case 2: `lcfs_serialized` is invalid (corrupted data)
```
Backend: Catches deserialization error
Backend: Falls back to re-search automatically
Result: Still works, just slower
Impact: Graceful degradation
```

### Case 3: `lcfs_serialized` is valid (new frontend)
```
Backend: Deserializes successfully
Backend: Uses object directly (no network call)
Result: Works fast (~<1s for deserialization)
Impact: 8-14 seconds saved! ✅
```

---

## Testing Checklist

- [ ] Frontend captures `lcfs_serialized` from Step 1 response
- [ ] Frontend passes `lcfs_serialized` to Step 2 request
- [ ] Backend logs show "✅ Deserialized SearchResult" (not "Re-searching")
- [ ] Step 2 completes 8-14 seconds faster than before
- [ ] Test with missing `lcfs_serialized` (backward compatibility)
- [ ] Test with corrupted data (graceful fallback)

---

## FAQ

**Q: Do I need to update my frontend immediately?**
A: No! Old code still works. But you'll get 8-14 seconds faster downloads if you update.

**Q: What if deserialization fails?**
A: Backend automatically re-searches (fallback). Slower, but still works.

**Q: Is this a breaking change?**
A: No! Completely backward compatible. Old frontends continue to work.

**Q: Where do I store `lcfs_serialized` between steps?**
A: Store it as a JavaScript variable in your component/class (see example above).

**Q: Can I pass it in URL parameters instead of JSON body?**
A: Not recommended (URL limits, special characters in base64). Use JSON request body.

---

## Support

If you have questions:
1. Check backend logs: Look for "Deserialized" or "Re-searching" messages
2. Check timing: Is Step 2 still 8-15s slower? If yes, `lcfs_serialized` not being used
3. Review example code above
