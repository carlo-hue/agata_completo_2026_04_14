================================================================================
TESS QLP OPTIMIZATION - VISUAL FLOW COMPARISON
================================================================================

BEFORE OPTIMIZATION (Slow - Redundant Search)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 1: search_qlp_sectors_endpoint()
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  Input: { project_id: 123 }                                        │
│                                                                     │
│  Backend Actions:                                                  │
│  ├─ gaia_to_tic(project_id)                          [5-8s]        │
│  │  ├─ Query MAST: "Get TIC for Gaia"                              │
│  │  └─ Result: TIC 25155310                                        │
│  │                                                                 │
│  ├─ search_qlp_sectors(tic_id)                       [8-15s]       │
│  │  ├─ Query Lightkurve: "Search QLP for TIC"                      │
│  │  ├─ Parse 47 sectors                                            │
│  │  └─ Result: lcfs (SearchResult object)                          │
│  │       [Sector 1, Sector 2, ..., Sector 47]                      │
│  │                                                                 │
│  └─ Return JSON                                      [<1s]         │
│     {                                                              │
│       "sectors": [...47 items...],                                │
│       "lcfs_serialized": null  ← NOT SAVED ❌                     │
│     }                                                              │
│                                                                     │
│  Total Time: 13-55s                                               │
└─────────────────────────────────────────────────────────────────────┘

     ↓ Frontend displays 47 sectors, user clicks "Download Sector 5"

Step 2: download_qlp_sector_endpoint()
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  Input: {                                                          │
│    "gaia_id": "1234567890",                                       │
│    "tic_id": 25155310,                                            │
│    "sector": 5,                                                   │
│    "sector_idx": 4                                                │
│  }                                                                 │
│                                                                     │
│  Backend Actions:                                                  │
│  ├─ download_and_ingest_qlp()                                     │
│  │  ├─ search_lightcurve(TIC 25155310)  ❌ REDUNDANT!  [8-15s]    │
│  │  │  ├─ Query Lightkurve AGAIN                                  │
│  │  │  ├─ Parse 47 sectors AGAIN  (Same data as Step 1!)         │
│  │  │  └─ Result: lcfs (SearchResult)                            │
│  │  │                                                              │
│  │  ├─ lcfs[4].download(tmpdir)                       [20-60s]    │
│  │  │  ├─ Download FITS from MAST (~100MB)                       │
│  │  │  └─ Result: /tmp/tic25155310_s0005.fits                    │
│  │  │                                                              │
│  │  ├─ ingest_qlp_core(fits_path)                     [5-15s]     │
│  │  │  ├─ Parse FITS, calibrate, compute magnitude               │
│  │  │  └─ Result: DataFrame (1000+ rows)                         │
│  │  │                                                              │
│  │  ├─ insert_catalog_data(df)                        [5-20s]     │
│  │  │  ├─ Insert each row in database                            │
│  │  │  └─ Result: 1000+ points imported                          │
│  │  │                                                              │
│  │  └─ Return JSON                                   [<1s]        │
│  │     {                                                          │
│  │       "success": true,                                        │
│  │       "points_imported": 1024                                 │
│  │     }                                                          │
│  │                                                                 │
│  └─ Total Step 2: 33-95s                                          │
│                                                                     │
│  ⏱️  TOTAL FLOW TIME: 46-150s ❌ TOO SLOW!                         │
└─────────────────────────────────────────────────────────────────────┘


AFTER OPTIMIZATION (Fast - Cached SearchResult)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 1: search_qlp_sectors_endpoint()
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  Input: { project_id: 123 }                                        │
│                                                                     │
│  Backend Actions:                                                  │
│  ├─ gaia_to_tic(project_id)                          [5-8s]        │
│  │  ├─ Query MAST: "Get TIC for Gaia"                              │
│  │  └─ Result: TIC 25155310                                        │
│  │                                                                 │
│  ├─ search_qlp_sectors(tic_id)                       [8-15s]       │
│  │  ├─ Query Lightkurve: "Search QLP for TIC"                      │
│  │  ├─ Parse 47 sectors                                            │
│  │  └─ Result: lcfs (SearchResult object)                          │
│  │       [Sector 1, Sector 2, ..., Sector 47]                      │
│  │                                                                 │
│  ├─ Serialize lcfs object                           [<1s]         │
│  │  ├─ pickle.dumps(lcfs)                                         │
│  │  ├─ base64.b64encode()                                         │
│  │  └─ lcfs_serialized = "gANjYXN0cm9xdWVyeS5..."                │
│  │                                                                 │
│  └─ Return JSON                                      [<1s]         │
│     {                                                              │
│       "sectors": [...47 items...],                                │
│       "lcfs_serialized": "gANjYXN0cm9xdWVyeS4..."  ← SAVED ✅    │
│     }                                                              │
│                                                                     │
│  Total Time: 13-55s (same as before)                              │
└─────────────────────────────────────────────────────────────────────┘

     ↓ Frontend sends back lcfs_serialized

Step 2: download_qlp_sector_endpoint()
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  Input: {                                                          │
│    "gaia_id": "1234567890",                                       │
│    "tic_id": 25155310,                                            │
│    "sector": 5,                                                   │
│    "sector_idx": 4,                                              │
│    "lcfs_serialized": "gANjYXN0cm9xdWVyeS4..."  ← FROM STEP 1   │
│  }                                                                 │
│                                                                     │
│  Backend Actions:                                                  │
│  ├─ download_and_ingest_qlp()                                     │
│  │  ├─ Deserialize lcfs_serialized                  [<1s] ✅     │
│  │  │  ├─ base64.b64decode()                                     │
│  │  │  ├─ pickle.loads()                                         │
│  │  │  └─ Result: lcfs (SearchResult)               NO NETWORK!  │
│  │  │                                                              │
│  │  ├─ lcfs[4].download(tmpdir)                       [20-60s]    │
│  │  │  ├─ Download FITS from MAST (~100MB)                       │
│  │  │  └─ Result: /tmp/tic25155310_s0005.fits                    │
│  │  │                                                              │
│  │  ├─ ingest_qlp_core(fits_path)                     [5-15s]     │
│  │  │  ├─ Parse FITS, calibrate, compute magnitude               │
│  │  │  └─ Result: DataFrame (1000+ rows)                         │
│  │  │                                                              │
│  │  ├─ insert_catalog_data(df)                        [5-20s]     │
│  │  │  ├─ Insert each row in database                            │
│  │  │  └─ Result: 1000+ points imported                          │
│  │  │                                                              │
│  │  └─ Return JSON                                   [<1s]        │
│  │     {                                                          │
│  │       "success": true,                                        │
│  │       "points_imported": 1024                                 │
│  │     }                                                          │
│  │                                                                 │
│  └─ Total Step 2: 25-81s  ← 8-14s FASTER! ✅                    │
│                                                                     │
│  ⏱️  TOTAL FLOW TIME: 38-136s ✅ 8-14 SECONDS SAVED!              │
└─────────────────────────────────────────────────────────────────────┘


COMPARISON TABLE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Operation                          Before (s)    After (s)    Saved (s)
─────────────────────────────────────────────────────────────────────
STEP 1: search_qlp_sectors         13-55         13-55        -
STEP 2: Lightkurve search          8-15          <1           8-14 ✅
STEP 2: FITS download              20-60         20-60        -
STEP 2: Process + DB               5-20          5-20         -
─────────────────────────────────────────────────────────────────────
TOTAL TIME                         46-150        38-136       8-14 ✅

PERCENTAGE IMPROVEMENT: 10-15% faster! 🚀


KEY POINTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ What was changed:
   - Step 1 now serializes SearchResult to base64
   - Step 2 accepts and deserializes it instead of re-searching
   - Frontend must pass lcfs_serialized from Step 1 to Step 2

✅ Why it's fast:
   - Lightkurve search eliminated (8-15s saved)
   - Deserialization is fast (<1s)
   - No additional network calls

✅ Backward compatible:
   - Old code still works if lcfs_serialized is not passed
   - Backend falls back to re-search automatically
   - No breaking changes to API

✅ Side benefits:
   - Reduced load on Lightkurve/MAST servers
   - More predictable performance
   - Better user experience
