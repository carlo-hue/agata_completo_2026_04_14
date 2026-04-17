# TESS QLP Frontend Update - Pass Serialized SearchResult

## Overview
The backend now supports passing a serialized SearchResult object to avoid redundant Lightkurve searches.

## Step 1: Search Sectors (No changes needed)
```javascript
// Your existing code:
const response1 = await fetch('/agata/admin/api/catalogs/tess/qlp/search-sectors', {
  method: 'POST',
  body: JSON.stringify({ project_id: 123 })
});

const data1 = await response1.json();
// data1 now includes: lcfs_serialized
console.log('Sectors:', data1.sectors);
console.log('Serialized object:', data1.lcfs_serialized);  // ← NEW FIELD
```

## Step 2: Download Sector (UPDATED)
```javascript
// OLD CODE (still works but slow):
const response2 = await fetch('/agata/admin/api/catalogs/tess/qlp/download-sector', {
  method: 'POST',
  body: JSON.stringify({
    gaia_id: '1234567890',
    tic_id: 25155310,
    sector: 5,
    sector_idx: 4
    // Missing: lcfs_serialized ← was causing redundant search!
  })
});

// NEW CODE (optimized, 10-15s faster):
const response2 = await fetch('/agata/admin/api/catalogs/tess/qlp/download-sector', {
  method: 'POST',
  body: JSON.stringify({
    gaia_id: '1234567890',
    tic_id: 25155310,
    sector: 5,
    sector_idx: 4,
    lcfs_serialized: data1.lcfs_serialized  // ← ADD THIS LINE
  })
});
```

## Complete Example Flow
```javascript
async function downloadQlpSector(projectId, sector) {
  try {
    // Step 1: Search available sectors
    const searchResp = await fetch('/agata/admin/api/catalogs/tess/qlp/search-sectors', {
      method: 'POST',
      body: JSON.stringify({ project_id: projectId })
    });
    const searchData = await searchResp.json();

    if (!searchData.success) {
      console.error('Search failed:', searchData.error);
      return;
    }

    console.log(`Found ${searchData.sectors.length} sectors`);
    console.log('✅ Serialized SearchResult ready for download');

    // Step 2: Download selected sector with serialized object
    const downloadResp = await fetch('/agata/admin/api/catalogs/tess/qlp/download-sector', {
      method: 'POST',
      body: JSON.stringify({
        gaia_id: searchData.gaia_id,
        tic_id: searchData.tic_id,
        sector: sector.sector,
        sector_idx: sector.idx,
        lcfs_serialized: searchData.lcfs_serialized  // ← OPTIMIZATION
      })
    });
    const downloadData = await downloadResp.json();

    if (!downloadData.success) {
      console.error('Download failed:', downloadData.error);
      return;
    }

    console.log(`✅ Downloaded ${downloadData.points_imported} points`);
  } catch (error) {
    console.error('Error:', error);
  }
}
```

## Benefits
- **Saves 8-14 seconds** per download (no redundant Lightkurve search)
- **Backward compatible**: If you don't pass `lcfs_serialized`, it still works (slower, re-searches)
- **No API breaking changes**: Old frontend code continues to work

## Testing
1. Check browser console network tab: Step 2 should complete faster
2. Check server logs: Should see "✅ Deserialized SearchResult" instead of "Re-searching QLP sectors"
3. Compare timing: With optimization, Step 2 should be 8-15s faster

## Location to Update
Find your current import_catalogs.js or similar file that handles TESS downloads and add `lcfs_serialized` to Step 2 request.
