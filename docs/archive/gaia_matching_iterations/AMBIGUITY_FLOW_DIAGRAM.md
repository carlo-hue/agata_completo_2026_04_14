╔══════════════════════════════════════════════════════════════════════════════════════════════════╗
║                        GAIA AMBIGUITY DETECTION & USER RESOLUTION FLOW                        ║
╚══════════════════════════════════════════════════════════════════════════════════════════════════╝

┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│ STEP 1: GAIA QUERY (30" radius)                                                               │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘

    VAST Star: out31321 @ RA=133.9295415°, Dec=-14.0441904°

    ⬇

    Query: SELECT TOP 10 sources within 30" radius
    
    Result:
    ┌─────────────────────────────────────────────────────────┐
    │ Rank  │ Gaia ID              │ Distance │ G Mag       │
    ├─────────────────────────────────────────────────────────┤
    │  #1   │ 5734104703954270464  │ 13.94"   │ 7.85 ✨     │ ← BRIGHTEST
    │  #2   │ 5734104703954270720  │ 7.15"    │ 16.52       │ ← NEAREST
    │  #3   │ 5734104807033585280  │ 25.22"   │ 17.09       │
    │  #4   │ 5734104703954402432  │ 10.51"   │ 18.00       │
    └─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│ STEP 2: AMBIGUITY DETECTION                                                                   │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘

    Nearest star: Gaia 5734104703954270720 @ 7.15"
    Brightest star: Gaia 5734104703954270464 @ 13.94"

    ⬇ Check conditions:

    ✓ Nearest ≠ Brightest?
      5734104703954270720 ≠ 5734104703954270464
      YES ✓

    ✓ Magnitude difference > 1.0 mag?
      |16.52 - 7.85| = 8.67 mag
      YES ✓ (HUGE difference = definitely different stars!)

    ⬇

    ❌ AMBIGUOUS! Mark for user resolution

┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│ STEP 3: DATABASE STORAGE                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘

    agata_vast_results record for out31321:
    ┌──────────────────────────────────────────────────────────┐
    │ vast_id: 'out31321'                                      │
    │ gaia_source_id: NULL  ← User must choose!               │
    │ gaia_ambiguous_candidates: [                             │
    │   {                                                      │
    │     "source_id": 5734104703954270720,                   │
    │     "ra": 133.9276714,                                  │
    │     "dec": -14.0433837,                                 │
    │     "gmag": 16.52,                                      │
    │     "distance": 7.15                                    │
    │   },                                                    │
    │   {                                                    │
    │     "source_id": 5734104703954270464,                   │
    │     "ra": 133.9292059,                                  │
    │     "dec": -14.0403310,                                 │
    │     "gmag": 7.85,                                       │
    │     "distance": 13.94                                   │
    │   },                                                    │
    │   {                                                    │
    │     "source_id": 5734104807033585280,                   │
    │     "ra": 133.9283716,                                  │
    │     "dec": -14.0372786,                                 │
    │     "gmag": 17.09,                                      │
    │     "distance": 25.22                                   │
    │   }                                                    │
    │ ]                                                        │
    └──────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│ STEP 4: USER SEES WARNING IN JOB DETAIL PAGE                                                  │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘

    ┌──────────────────────────────────────────────────────────────────┐
    │ ⚠️  AMBIGUOUS GAIA MATCHES                                       │
    │ The following stars have multiple Gaia sources with similar      │
    │ relevance. Click to choose:                                      │
    ├──────────────────────────────────────────────────────────────────┤
    │ VAST ID  │ Nearest (Default)        │ Brightest        │ Action │
    ├──────────────────────────────────────────────────────────────────┤
    │ out31321 │ Gaia ...270720 @ 7.15"   │ Gaia ...270464   │ [Res.] │
    │          │ (G Mag 16.52)            │ @ 13.94" (7.85)  │        │
    └──────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│ STEP 5: USER CLICKS "RESOLVE" → MODAL APPEARS                                                │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘

    ╔════════════════════════════════════════════════════════════════╗
    ║ Gaia Source Selection for out31321                            ║
    ╠════════════════════════════════════════════════════════════════╣
    ║ VAST Coordinates: RA=133.9295415°, Dec=-14.0441904°           ║
    ║                                                                 ║
    ║ ○ Gaia 5734104703954270720 @ 7.15" | G Mag 16.52   [NEAREST]  ║
    ║ ○ Gaia 5734104703954270464 @ 13.94" | G Mag 7.85   [BRIGHTEST]║
    ║ ○ Gaia 5734104807033585280 @ 25.22" | G Mag 17.09             ║
    ║                                                                 ║
    ║ 💡 Tip: Check VSX/ASAS-SN to determine correct match          ║
    ║                                                                 ║
    ║ [Cancel]    [Save Selection] ✓                                ║
    ╚════════════════════════════════════════════════════════════════╝

┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│ STEP 6: USER DECIDES BASED ON:                                                               │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘

    Option A: DISTANCE (pick NEAREST)
    ──────────────────────────────────
    "It's the closest to my VAST coordinates"
    → Select: 5734104703954270720 @ 7.15"

    Option B: MAGNITUDE (pick BRIGHTEST)
    ────────────────────────────────────
    "My star is bright (VSX says magnitude ~8), not faint"
    → Select: 5734104703954270464 @ 7.85"

    Option C: EXTERNAL CATALOG MATCH
    ────────────────────────────────
    "It matches VSX ID XYZ which is at RA=133.9283716°"
    → Select: 5734104807033585280

┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│ STEP 7: USER SAVES CHOICE                                                                    │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘

    POST /agata/admin/api/vast/results/[id]/resolve-gaia
    Body: {"gaia_source_id": 5734104703954270720}

    ⬇

    Backend:
    - Updates gaia_source_id in database
    - Clears gaia_ambiguous_candidates
    - Logs: "out31321 resolved by user@email.com to Gaia 5734104703954270720"
    - Returns: {"success": true}

┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│ STEP 8: COMPLETION                                                                           │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘

    Modal closes → Page reloads

    Database now shows:
    ┌──────────────────────────────────────────────────────────┐
    │ vast_id: 'out31321'                                      │
    │ gaia_source_id: 5734104703954270720  ✓ RESOLVED         │
    │ gaia_ambiguous_candidates: NULL  (cleared)              │
    └──────────────────────────────────────────────────────────┘

    Ambiguous section now shows: "✓ 1 match resolved"
    Pipeline can now proceed with magnitude calibration using correct Gaia source!


═══════════════════════════════════════════════════════════════════════════════════════════════════
SUMMARY
═══════════════════════════════════════════════════════════════════════════════════════════════════

BEFORE (v1): Algorithm picks "nearest" automatically
  ❌ Sometimes wrong in dense fields
  ❌ No visibility into why
  ❌ Hard to fix after import

AFTER (v2): Algorithm detects ambiguity, user chooses
  ✓ Rare ambiguous cases (~1%) are caught
  ✓ User has all info to make correct choice
  ✓ Easy to fix before proceeding
  ✓ Confidence in VAST import results
  ✓ Full audit trail of user decisions

