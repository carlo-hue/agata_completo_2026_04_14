# Check Passo-per-Passo: Pre-Phase fino al Controllo Coerenza

**Data**: 2026-02-17
**Scopo**: Verificare tutti i passaggi iniziali fino al controllo che verifica la calibrazione

---

## PANORAMICA FLUSSO

```
┌─────────────────────────────────────────────────────────────────────┐
│ _crossmatch_gaia() (called for entire job)                         │
└─────────────────────────────────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────┐
│ 1. Filter valid coordinates                                         │
│    Input: stars_df (689 stars)                                      │
│    stars_valid = df[ra != 0 AND dec != 0][['ra','dec','name'...]]  │
│    Output: stars_valid DataFrame                                    │
└─────────────────────────────────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────┐
│ PRE-PHASE: _calculate_magnitude_offset_from_sample()               │
│                                                                     │
│ 2. Take first 5 VAST stars                                         │
│    sample_stars = stars_valid.head(5)                              │
│                                                                     │
│ 3. For EACH star in sample (5 iterations):                         │
│    └─ Query Vizier 10" → get Gaia candidates                       │
│    └─ Sort by Gmag (brightest first)                               │
│    └─ Take first (brightest)                                       │
│    └─ Calculate Vmag (EDR3 formula)                                │
│    └─ Append to vmags list                                         │
│                                                                     │
│ 4. Calculate offset = mean(vmags)                                  │
│    Result: GLOBAL offset value                                     │
└─────────────────────────────────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────┐
│ 5. Submit workers with offset                                       │
│    For each of 689 stars:                                          │
│    executor.submit(_gaia_worker_query_single_star,                 │
│                    (name, ra, dec, 30, VAST_mag, offset))          │
└─────────────────────────────────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────┐
│ WORKER: _gaia_worker_query_single_star()                           │
│                                                                     │
│ 6. Unpack params: name, ra, dec, radius, vast_mag, offset         │
│    offset = pre-calculated global offset                           │
│                                                                     │
│ 7. STAGE 1: Query Vizier 10"                                       │
│    rows_10 = vizier_client.query_cone(..., radius_arcsec=10)       │
│    Build candidates_10 list (all results from 10")                 │
│                                                                     │
│ 8. Call process_candidates(candidates_10, offset, is_stage2=False)│
│                                                                     │
│    ├─ CALIBRATE VAST                                               │
│    │  vast_mag_calibrated = vast_mag + offset                      │
│    │  Log: "offset={offset:.2f}, VAST_calibrated={cal:.2f}"        │
│    │                                                                │
│    ├─ COHERENCE CHECK                                              │
│    │  coherence_diff = |vast_mag_calibrated - offset|              │
│    │  if coherence_diff > 2.0:                                     │
│    │      Log: "calibration NOT coherent ... → NO MATCH"           │
│    │      return 'no_match'  ← BLOCKS Stage 2!                     │
│    │  else:                                                         │
│    │      Log: "calibration coherent (diff={diff:.2f})"            │
│    │      Continue to magnitude filtering                          │
│    │                                                                │
│    └─ [If coherence PASSES: continue to Step 9]                    │
│                                                                     │
│ 9. [If no_match from coherence: return no_match]                   │
│    [If no compatible mags: fallback to STAGE 2]                    │
│    [If compatible found: return match]                             │
│                                                                     │
│ 10. [If Stage 1 no_match: return immediately, don't try Stage 2]   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## DETTAGLI PASSO-PASSO

### STEP 1: Filter Valid Coordinates

**File**: `agata/admin/services/vast_service.py`
**Location**: Lines 1360-1368
**Function**: `_crossmatch_gaia()`

```python
# Linea 1360-1361
valid_mask = (stars_df['ra'] != 0.0) & (stars_df['dec'] != 0.0)
stars_valid = stars_df[valid_mask][['ra', 'dec', 'name', 'Median_magnitude']].copy()

# Linea 1368
logger.info(f"Gaia cross-match: {len(stars_valid)}/{len(stars_df)} stars with valid coordinates")
```

**What happens**:
- Filters out stars with RA=0 or Dec=0 (WCS failures)
- Keeps only needed columns: ra, dec, name, Median_magnitude
- Example: 689 stars input → ~689 with valid coords

**Verification**: ✅
- Correct columns selected
- Correct condition (!=0.0 for both coords)
- Dataset size appropriate

---

### STEP 2-4: PRE-PHASE Offset Calculation

**File**: `agata/admin/services/vast_service.py`
**Location**: Lines 1212-1314 (method `_calculate_magnitude_offset_from_sample()`)
**Called from**: Line 1376 in `_crossmatch_gaia()`

#### 2a. Take First 5 VAST Stars

```python
# Linea 1247-1248
num_sample = min(5, len(stars_valid))
sample_stars = stars_valid.head(num_sample)

# Linea 1250
logger.info(f"Calculating offset from {num_sample} sample stars (10\" radius)...")
```

**What happens**:
- Takes min(5, len(stars_valid)) - se dataset <5, prende tutte
- Example: stars_valid has 689 stars → prendi primi 5

**Verification**: ✅
- Correct: head(5) takes first 5
- Correct: min() handles small datasets
- Logged

---

#### 2b. Setup Loop Over 5 Stars

```python
# Linea 1254
for _, star_row in sample_stars.iterrows():
    star_name = star_row['name']
    star_ra = star_row['ra']
    star_dec = star_row['dec']
```

**What happens**:
- Iterates over 5 sample stars
- Extracts name, ra, dec for each

**Verification**: ✅
- Loop structure correct
- Columns extracted correctly

---

#### 2c. Query Vizier 10" for Each Star

```python
# Linea 1261-1267
rows = vizier_client.query_cone(
    catalog_id=catalog_id,  # "I/355/gaiadr3"
    ra_deg=star_ra,
    dec_deg=star_dec,
    radius_arcsec=10,  # ← 10" fisso
    columns=columns     # ['Source', 'RA_ICRS', 'DE_ICRS', 'Gmag', 'BP-RP']
)

# Linea 1269-1271
if len(rows) == 0:
    logger.debug(f"  {star_name}: no Gaia sources in 10\"")
    continue
```

**What happens**:
- Queries Vizier I/355/gaiadr3 with 10" cone search
- If no candidates: skip this star
- Example: out31321 @ RA=133.929541, Dec=-14.044190 → finds N candidates in 10"

**Verification**: ✅
- Correct catalog (I/355/gaiadr3 = Gaia DR3)
- Correct radius (10" fisso)
- Correct columns (Source, RA_ICRS, DE_ICRS, Gmag, BP-RP)
- Error handling (continue if no rows)

---

#### 2d. Sort by Gmag and Take Brightest

```python
# Linea 1273-1276
rows_sorted = sorted(rows, key=lambda r: float(r.values.get('Gmag', 99)))
# Prendi il PRIMO candidato (più brillante)
first_candidate = rows_sorted[0]
```

**What happens**:
- Sorts candidates by Gmag in ascending order (brightest = smallest Gmag)
- Takes first element (index 0) = brightest star

**Example** (out31321):
- Before sort: [Gaia A (Gmag 16.52), Gaia B (Gmag 7.85), ...]
- After sort: [Gaia B (Gmag 7.85), Gaia A (Gmag 16.52), ...]
- Take [0]: Gaia B (brightest, Gmag 7.85) ✅

**Verification**: ✅
- Sorting logic correct (ascending = brightest first)
- Takes first element correctly
- Handles edge cases (default 99 if Gmag missing)

---

#### 2e. Extract Gmag and BP-RP

```python
# Linea 1277-1279
gmag = float(first_candidate.values.get('Gmag', 99))
bp_rp_val = first_candidate.values.get('BP-RP')
bp_rp = float(bp_rp_val) if bp_rp_val is not None else None
```

**What happens**:
- Gets Gmag value (or 99 if missing)
- Gets BP-RP value (or None if missing)

**Verification**: ✅
- Safe extraction (get with defaults)
- Type conversion correct
- Handles None/missing values

---

#### 2f. Calculate Vmag Using EDR3 Formula

```python
# Linea 1282
vmag = _calculate_vmag_from_gaia(gmag, bp_rp)

# Function definition (linea 277-300)
def _calculate_vmag_from_gaia(gmag: float, bp_rp: Optional[float]) -> Optional[float]:
    if bp_rp is None or np.isnan(bp_rp):
        return None
    vmag = gmag + 0.02704 - 0.01424 * bp_rp + 0.2156 * (bp_rp ** 2) - 0.01426 * (bp_rp ** 3)
    return float(vmag)
```

**Formula**:
```
Vmag = gmag + 0.02704 - 0.01424*BP_RP + 0.2156*BP_RP² - 0.01426*BP_RP³
```

**What happens**:
- Calculates V-magnitude using Gaia EDR3 polynomial
- Returns None if BP-RP missing (can't calculate)

**Example** (Gaia 5734104703954270464, out31321):
- gmag = 7.85
- BP_RP = ~0.885
- Vmag = 7.85 + 0.02704 - 0.01424*(0.885) + 0.2156*(0.885²) - 0.01426*(0.885³)
- Vmag ≈ 7.90 ✓

**Verification**: ✅
- Formula matches Gaia EDR3 documentation
- Handles missing BP-RP (returns None)
- Type conversion correct

---

#### 2g. Append to vmags List

```python
# Linea 1284-1290
if vmag is not None:
    vmags.append(vmag)
    gaia_id = int(first_candidate.values.get('Source', 0))
    logger.debug(
        f"  {star_name}: Gaia {gaia_id}, Gmag={gmag:.2f}, "
        f"BP-RP={bp_rp}, Vmag={vmag:.2f}"
    )
else:
    logger.debug(f"  {star_name}: could not calculate Vmag (missing BP-RP)")
```

**What happens**:
- If Vmag valid: append to vmags list (for averaging later)
- If Vmag None: skip (can't calculate without BP-RP)
- Logs details for each star

**Verification**: ✅
- Correct filtering (only None vmags skipped)
- Logging shows all details
- Handles errors gracefully

---

#### 2h. Calculate Mean Offset

```python
# Linea 1298-1305
if len(vmags) > 0:
    offset = float(np.mean(vmags))
    logger.info(
        f"Magnitude offset calculated: {offset:.2f} mag "
        f"(from {len(vmags)}/{num_sample} sample stars)"
    )
    return offset
else:
    logger.warning("Could not calculate offset from sample (no valid Vmag values)")
    return 0.0
```

**What happens**:
- Calculates numpy mean of all Vmag values
- Returns offset (or 0.0 fallback if no valid Vmag)

**Example** (5 sample stars):
- vmags = [7.90, 8.12, 9.45, 7.88, 10.20]
- offset = mean([7.90, 8.12, 9.45, 7.88, 10.20]) = 8.71 mag

**Verification**: ✅
- Correct mean calculation
- Fallback to 0.0 if all invalid
- Logging shows sample rate

---

### STEP 3: Pass Offset to Workers

**File**: `agata/admin/services/vast_service.py`
**Location**: Lines 1376-1389

```python
# Linea 1376
offset = self._calculate_magnitude_offset_from_sample(stars_valid, match_radius_arcsec)
logger.info(f"Magnitude offset: {offset:.2f} mag")

# Linea 1387
executor.submit(_gaia_worker_query_single_star,
                (row['name'], row['ra'], row['dec'],
                 match_radius_arcsec, row['Median_magnitude'], offset))
```

**What happens**:
- Offset calculated ONCE before workers
- Offset passed to ALL 689 workers as parameter

**Verification**: ✅
- Offset calculated before loop
- Passed as 6th parameter to worker
- Same offset for all stars

---

### STEP 4: Worker Receives Offset

**File**: `agata/admin/services/vast_service.py`
**Location**: Lines 64-91 (worker function)

```python
# Linea 91
name, ra, dec, match_radius_arcsec, vast_mag, offset = params

# Linea 175
logger_worker.info(f"[WORKER] Star {name} @ RA={ra:.6f}, Dec={dec:.6f}, VAST_mag_strumentale={vast_mag:.2f}")
```

**What happens**:
- Worker unpacks 6 parameters
- offset is now available as variable in worker scope

**Verification**: ✅
- Correct unpacking order
- offset is immutable (passed by value)

---

### STEP 5: Query Vizier 10" in Worker (STAGE 1)

**File**: `agata/admin/services/vast_service.py`
**Location**: Lines 177-212

```python
# Linea 178
logger_worker.info(f"[STAGE 1] Star {name}: querying 10\" radius")

# Linea 180-186
rows_10 = vizier_client.query_cone(
    catalog_id=catalog_id,
    ra_deg=ra,
    dec_deg=dec,
    radius_arcsec=10,
    columns=columns
)

# Linea 188
logger_worker.info(f"[STAGE 1] Star {name}: got {len(rows_10)} candidates in 10\"")

# Linea 191-212: Build candidates_10 list with vmag + distance
for row in rows_10:
    gaia_id = int(row.values.get('Source', 0))
    gaia_ra = float(row.values.get('RA_ICRS', 0))
    gaia_dec = float(row.values.get('DE_ICRS', 0))
    gmag = float(row.values.get('Gmag', 99))
    bp_rp = float(...) if bp_rp_val is not None else None

    vmag = _calculate_vmag_from_gaia(gmag, bp_rp)
    distance = vast_coord.separation(gaia_coord).to(u.arcsec).value

    candidates_10.append({...})
```

**What happens**:
- Query Vizier 10" for THIS specific star (not sample)
- Build list of all candidates with:
  - source_id, ra, dec, gmag, bp_rp
  - Vmag (calculated)
  - distance (to VAST star)

**Example** (out31321):
- Found candidates in 10": [Gaia A @ 7.15" Vmag 16.74, Gaia B @ 13.94" Vmag 7.89, ...]

**Verification**: ✅
- Query correct (10" radius)
- All candidates processed
- Vmag calculated for each
- Distance calculated for each

---

### STEP 6: CALIBRATE VAST MAGNITUDE

**File**: `agata/admin/services/vast_service.py`
**Location**: Lines 106-112 (inside process_candidates helper)

```python
# Linea 107
vast_mag_calibrated = vast_mag + global_offset

# Linea 109-112
logger_worker.info(
    f"[{radius_desc}] Star {name}: offset={global_offset:.2f} (global), "
    f"VAST_calibrated={vast_mag_calibrated:.2f}"
)
```

**What happens**:
- Formula: `VAST_calibrated = VAST_strumentale + offset`
- offset is the global offset from pre-phase

**Example** (out31321):
- VAST_mag_strumentale = -12.8555 (VAST raw value)
- offset = 8.71 (from pre-phase average)
- VAST_calibrated = -12.8555 + 8.71 = -4.1455

**Verification**: ✅
- Formula correct
- Uses global offset (not recalculated)
- Logged with values

---

### STEP 7: COHERENCE CHECK ✅ QUESTO È IL CHECK CRITICO

**File**: `agata/admin/services/vast_service.py`
**Location**: Lines 114-126 (inside process_candidates helper)

```python
# Linea 114-115
coherence_tolerance = 2.0
coherence_diff = abs(vast_mag_calibrated - global_offset)

# Linea 116-122
if coherence_diff > coherence_tolerance:
    logger_worker.warning(
        f"[{radius_desc}] Star {name}: calibration NOT coherent "
        f"(|{vast_mag_calibrated:.2f} - {global_offset:.2f}| = {coherence_diff:.2f} > {coherence_tolerance}) → NO MATCH"
    )
    return 'no_match'  # Ritorna stringa speciale per bloccare completamente

# Linea 124-126
logger_worker.info(
    f"[{radius_desc}] Star {name}: calibration coherent (diff={coherence_diff:.2f})"
)
```

**FORMULA - Coherence Check**:
```
coherence_diff = |VAST_calibrated - offset|
is_coherent = coherence_diff <= 2.0 mag
```

**What happens**:
- Check IF `|VAST_calibrated - offset| > 2.0`:
  - If YES: return 'no_match' ← BLOCKS Stage 2 completely!
  - If NO: continue to magnitude filtering

**Logic Breakdown**:
```
VAST_calibrated = VAST_strumentale + offset
offset = average_vmag_from_sample

coherence_diff = |(VAST_strumentale + offset) - offset|
                = |VAST_strumentale + offset - offset|
                = |VAST_strumentale|
```

**So it's checking**: `|VAST_strumentale| <= 2.0 mag`

**Example** (out31321):
- VAST_strumentale = -12.8555
- offset = 8.71
- VAST_calibrated = -12.8555 + 8.71 = -4.1455
- coherence_diff = |-4.1455 - 8.71| = |-12.8555| = 12.8555
- 12.8555 > 2.0? YES! ← FAILS COHERENCE CHECK ❌

**This means**: out31321 would be marked NO_MATCH!

---

## POTENZIALE PROBLEMA SCOPERTO

### Issue: Coherence Check Formula

La formula di coerenza potrebbe non essere corretta come implementata:

```python
coherence_diff = abs(vast_mag_calibrated - global_offset)
```

**Current Logic**:
- VAST_calibrated = VAST_strumentale + offset
- coherence_diff = |VAST_calibrated - offset| = |VAST_strumentale|

**This checks**: Se il VAST strumentale raw è ragionevole (<2.0 mag)

**But you specified**:
> "CONTROLLO DI COERENZA del calibration: Verifica che |VAST_mag_calibrato - offset| <= tolerance"

**Interpretation ambiguity**:
1. Intendi: `|VAST_calibrated - offset| <= 2.0` (implementazione attuale) ← = `|VAST_strumentale| <= 2.0`
2. Oppure: `|VAST_calibrated - (mean of Gaia Vmag for THIS star)| <= 2.0` (paragone con Gaia)

### Domanda per te:

La formula di coerenza è corretta così come implementata, oppure dovrebbe fare un confronto diverso?

---

## SUMMARY TABLE - Early Stages

| Step | Location | Input | Operation | Output | Status |
|------|----------|-------|-----------|--------|--------|
| 1 | Line 1360 | stars_df (689) | Filter coords ≠ 0 | stars_valid (~689) | ✅ |
| 2a | Line 1247 | stars_valid | head(5) | sample_stars (5) | ✅ |
| 2b | Line 1254 | sample_stars | Loop 5 times | Iterate | ✅ |
| 2c | Line 1261 | each star coords | Vizier 10" | rows (N cands) | ✅ |
| 2d | Line 1273 | rows | sort(Gmag) | rows_sorted | ✅ |
| 2e | Line 1276 | rows_sorted[0] | take brightest | first_candidate | ✅ |
| 2f | Line 1282 | gmag, bp_rp | EDR3 formula | vmag | ✅ |
| 2g | Line 1285 | vmag | append to list | vmags list | ✅ |
| 2h | Line 1300 | vmags list | mean() | offset | ✅ |
| 3 | Line 1387 | offset, 689 stars | submit workers | futures | ✅ |
| 4 | Line 91 | params tuple | unpack | name, ra, dec, vast_mag, offset | ✅ |
| 5 | Line 180 | star coords, offset | Vizier 10" | candidates_10 | ✅ |
| 6 | Line 107 | vast_mag, offset | add | vast_mag_calibrated | ✅ |
| 7 | Line 116 | vast_mag_calibrated, offset | \|diff\| check | Pass/Fail | ⚠️ **CHECK** |

