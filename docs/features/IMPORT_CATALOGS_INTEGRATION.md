# Import Cataloghi - Integration with Variable Stars Editor

**Date**: 2026-02-13
**Status**: ✅ Implemented and Ready
**Feature**: Download automatico cataloghi fotometrici nel Variable Stars Editor

---

## Overview

Integrated the existing "Download Automatico TESS QLP" functionality from `/agata/admin/external-catalogs` into the Variable Stars Editor with a new **📥 Import Cataloghi** tab.

**No new functionality created** - only reused existing admin endpoints and UI logic.

---

## What Was Added

### 1. New JavaScript Module
**File**: `agata/static/js/variable_stars/import_catalogs.js` (180 lines)

Core functions:
- `initImportCatalogs()` - Initialize with Gaia ID from project
- `searchImportCatalogs()` - Call `/agata/admin/api/external-catalogs/search`
- `executeImport()` - Call `/agata/admin/api/external-catalogs/<id>/import`
- `displayImportResults()` - Render available sectors with checkboxes
- `showImportStatus()` - Display status messages
- `updateImportSummary()` - Update selected sector count

### 2. New Tab in Editor
**File**: `agata/templates/variable_stars/index.html`

Added:
- Tab button: `📥 Import Cataloghi` (after `🔭 Cataloghi`)
- Tab panel with:
  - Gaia ID input (auto-populated from project)
  - Catalog selector (TESS, ZTF, ASAS-SN, OGLE)
  - Search button
  - Help text explaining the workflow
  - Status display area
  - Results area (for sector selection)

### 3. Module Import
**File**: `agata/static/js/variable_stars/main.js`

Added:
- Import statement: `import { initImportCatalogs } from './import_catalogs.js';`
- Initialization call: `initImportCatalogs();`

---

## API Endpoints Used

### 1. Search Catalogs
```bash
POST /agata/admin/api/external-catalogs/search

Request Body:
{
    "gaia_id": "6917570577208762624",
    "catalogs": ["TESS", "ZTF"]  // optional, null = all
}

Response:
{
    "import_id": 123,
    "total_points": 1500,
    "resolved_gaia_id": "6917570577208762624",
    "catalogs_with_data": ["TESS", "ZTF"],
    "results": {
        "TESS": { "data_count": 1000 },
        "ZTF": { "data_count": 500 }
    }
}
```

### 2. Import Data
```bash
POST /agata/admin/api/external-catalogs/<import_id>/import

Request Body:
{
    "selected_catalogs": ["TESS"],
    "gaia_id": "6917570577208762624"
}

Response:
{
    "success": true,
    "points_imported": 1000,
    "project_created": false,
    "project_code": null,
    "message": "Importati 1000 punti fotometrici"
}
```

---

## Workflow

### For Users (same as admin)

1. **Open Variable Stars Editor** → `/agata/variable-stars/<project_id>`
2. **Click "📥 Import Cataloghi" tab**
3. **Gaia ID auto-filled** from project
4. **Select catalogs** (TESS, ZTF, ASAS-SN, OGLE)
5. **Click "🔍 Cerca"**
   - Step 1: Searches MAST for available sectors (no downloads yet)
   - Shows results with checkboxes
6. **Select sectors** to import
7. **Click "⬇️ Importa settori selezionati"**
   - Step 2: Downloads files one-by-one
   - Processes automatically
   - Deletes files after processing
   - Shows progress and completion

### Permissions

- **Superuser**: Can import for any Gaia ID → public data
- **Admin/Analyst**: Can import only for projects in their association → association data

---

## Code Structure

### JavaScript Module
```javascript
export function initImportCatalogs()
  ↓ populates Gaia ID from project
  ↓ attaches window.searchImportCatalogs()
  ↓ attaches window.executeImport()

window.searchImportCatalogs()
  ↓ validates Gaia ID
  ↓ POST /agata/admin/api/external-catalogs/search
  ↓ calls displayImportResults()
  ↓ user selects sectors

window.executeImport(gaiaId)
  ↓ collects checked sector IDs
  ↓ POST /agata/admin/api/external-catalogs/<import_id>/import
  ↓ shows completion status
  ↓ user can start new import
```

### HTML Structure
```html
<!-- Tab button (nav) -->
<button onclick="switchTab(event, 'tab-import-catalogs')">
  📥 Import Cataloghi
</button>

<!-- Tab panel -->
<div id="tab-import-catalogs" class="tab-panel">
  <!-- Input: Gaia ID -->
  <input id="import-gaia-id" readonly />

  <!-- Input: Catalog selector -->
  <input name="import-catalogs" type="checkbox" value="TESS" checked />
  ...

  <!-- Button: Search -->
  <button onclick="searchImportCatalogs()">🔍 Cerca</button>

  <!-- Status display -->
  <div id="import-status"></div>

  <!-- Results area -->
  <div id="import-results"></div>
</div>
```

---

## Features

✅ **Auto-populated Gaia ID** - From project field
✅ **Multi-catalog support** - TESS, ZTF, ASAS-SN, OGLE
✅ **Sector selection** - Checkboxes for multi-select
✅ **Status messages** - Info, success, error
✅ **Progress tracking** - Step 1/2 workflow indication
✅ **Permission-based** - Same as admin (superuser vs user scoping)
✅ **Reuses existing endpoints** - No new backend code needed

---

## Files Created

1. **agata/static/js/variable_stars/import_catalogs.js** (180 lines)
   - Complete module for import catalogs UI and API calls

## Files Modified

1. **agata/templates/variable_stars/index.html**
   - Added tab button: `📥 Import Cataloghi`
   - Added tab panel with controls and results area

2. **agata/static/js/variable_stars/main.js**
   - Added import statement
   - Added initialization call

---

## Testing

### Quick Test
1. Navigate to `/agata/variable-stars/<any_project_id>`
2. Click "📥 Import Cataloghi" tab
3. Verify:
   - Gaia ID auto-populated ✅
   - "🔍 Cerca" button present ✅
   - Catalog checkboxes visible ✅
   - Help text displayed ✅

### Functional Test
1. Enter Gaia ID (or use auto-filled)
2. Click "🔍 Cerca"
3. Verify:
   - Status shows "Step 1/2: Ricerca settori..."
   - Results appear with sector checkboxes
   - "⬇️ Importa..." button appears
4. Select sectors
5. Click "⬇️ Importa..."
6. Verify:
   - Import starts (button disabled, status updates)
   - Shows completion with points imported

---

## Notes

- **No database changes** - Uses existing CatalogImport table
- **No new endpoints** - Reuses admin endpoints
- **Same permissions** - Admin endpoints enforce role checking
- **Same workflow** - Identical to admin external-catalogs page
- **Backward compatible** - Existing functionality unchanged

---

## Future Enhancements (Out of Scope)

1. Add more catalog types (APASS, Tycho-2, etc.)
2. Bulk import for multiple stars
3. Import history view in tab
4. Cache downloaded files locally
5. Resumable downloads

---

## Conclusion

Successfully integrated existing admin functionality into Variable Stars Editor with:
- ✅ Zero new backend code
- ✅ Clean module-based frontend
- ✅ Reused existing endpoints and logic
- ✅ Same permissions and workflow
- ✅ Ready for production

**Status**: Ready to Use
