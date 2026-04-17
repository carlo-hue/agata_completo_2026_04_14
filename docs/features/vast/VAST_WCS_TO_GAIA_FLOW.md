# VAST WCS → Gaia Query Flow (Job #161)

## Overview
Il job VAST #161 prende coordinate pixel da VAST, le converte in RA/Dec usando il WCS del FITS reference frame, e poi le usa per query Gaia.

---

## 1. DOWNLOAD IMMAGINI (Step 1)

**File**: `execute_job()` in `vast_service.py` line 511

```
VAST-2026-161:
  source_type: 'google_drive'
  ↓
  _download_images()
  ↓
  tmpdir/tess_2024*.fits (n immagini TESS)
```

**Output**: `image_paths = ['/tmp/vast_job_161_xxx/tess_*.fits', ...]`

---

## 2. VALIDAZIONE WCS (Step 2)

**File**: `_validate_wcs()` in `vast_service.py` line 514-518

```python
for img_path in image_paths:
    with fits.open(img_path) as hdul:
        header = hdul[0].header
        wcs = WCS(header)

        # Verifica: wcs.has_celestial
        if wcs.has_celestial:
            ✅ WCS valido
        else:
            ❌ WCS mancante
```

**Cosa fa**:
- Apre ogni FITS file
- Legge header[0] (HDU 0 per TESS)
- Estrae WCS object usando Astropy
- Verifica che abbia coordinate celestiali (RA/Dec)

**Output**: WCS validation passed, ora abbiamo i FITS con WCS verificato

---

## 3. ESECUZIONE VAST (Step 3)

**File**: `execute_job()` in `vast_service.py` line 560-575

```python
vast_result = self.vast_executor.run_vast_analysis(
    image_dir=tmpdir,
    output_dir=tmpdir,
    reference_frame=image_paths[0]  # ← PRIMA IMMAGINE COME REFERENCE
)
```

**VAST produce**:
```
tmpdir/
  ├── vast_lightcurve_statistics.log  (tutte le stelle)
  ├── vast_autocandidates.log        (690 top candidates)
  ├── vast_autocandidates_details.log (dettagli)
  └── reference_frame.fits           (salvato/aggiornato)
```

**Output**:
- `vast_result['reference_frame']` = path al FITS reference
- `vast_result['vast_dir']` = directory VAST output

---

## 4. PARSE VAST OUTPUT (Step 4)

**File**: `_parse_vast_output()` in `vast_service.py` line 1030-1100

```python
# Legge SOLO vast_autocandidates.log (690 candidates)
stars_df = pd.read_csv(vast_autocandidates.log, ...)

# Colonne risultato:
# x       = pixel column (da VAST, 0-indexed)
# y       = pixel row    (da VAST, 0-indexed)
# name    = 'out31321', 'out45470', ...
# Median_magnitude = instrumental magnitude (non calibrata)
```

**Output**: DataFrame con 690 stelle + coordinate pixel

---

## 5. CONVERSIONE WCS PIXEL → CELESTIAL (Step 5)

### **QUESTO È IL PASSAGGIO CRITICO**

**File**: `_convert_wcs_pixel_to_sky()` in `vast_service.py` line 1170-1246

### 5a. Leggi WCS dal FITS reference frame

```python
reference_frame = vast_result['reference_frame']  # ← path al FITS

# Per TESS: prova HDU 1, fallback a HDU 0
is_tess = 'tess' in job.target_name.lower()
hdu_number = 1 if is_tess else 0

with fits.open(reference_frame, memmap=True) as hdul:
    header = hdul[hdu_number].header
    wcs = WCS(header)  # ← WCS OBJECT ESTRATTO QUI

    # Leggi anche il centro del campo (per Vizier)
    ra_center = header.get('CRVAL1', 0.0)   # RA centro
    dec_center = header.get('CRVAL2', 0.0)  # Dec centro
```

**Cosa contiene il WCS**:
- CRVAL1/CRVAL2: coordinate centro immagine (RA/Dec)
- CRPIX1/CRPIX2: pixel del centro (solitamente 1024, 1024)
- CD1_1, CD1_2, CD2_1, CD2_2: matrice rotazione + scala (arcsec/pixel)
- CTYPE: tipo proiezione ('RA---TAN', 'DEC--TAN')
- Se disponibile: SIP coefficienti distorsione

### 5b. Converti coordinate VAST (pixel) → RA/Dec

```python
# Per OGNI stella nel DataFrame:
# stars_df['x'] = coordinate pixel X (colonna, 0-indexed)
# stars_df['y'] = coordinate pixel Y (riga, 0-indexed)

# Conversione vettorizzata:
ra_arr, dec_arr = wcs.all_pix2world(
    np.float64(stars_df['x']),  # pixel column
    np.float64(stars_df['y']),  # pixel row
    1  # origin=1 (FITS convention)
)

# Risultato:
stars_df['ra']  = ra_arr   # RA in gradi (es 131.9045°)
stars_df['dec'] = dec_arr  # Dec in gradi (es -14.3707°)
```

**Esempio concreto (out31321)**:
```
VAST output: x=854.60 px, y=952.40 px
WCS conversion (origin=1):
  RA = 131.90455°
  Dec = -14.37065°
```

---

## 6. CROSS-MATCH GAIA (Step 6)

**File**: `_crossmatch_gaia()` in `vast_service.py` line 1445-1600

### 6a. Calcola offset di magnitudine

```python
# Prendi PRIME 5 stelle (campione)
# Per ognuna: query Vizier 10"
offset, calibration_diff = self._calculate_magnitude_offset_from_sample(
    stars_valid,
    match_radius_arcsec=30
)

# Risultato: offset = 14.5 mag (es.)
# Significa: VAST magnitude - offset = Vmag Gaia
```

### 6b. Parallelo: Query Gaia per TUTTE le stelle

```python
# ProcessPoolExecutor: 4 worker paralleli

futures = {
    executor.submit(_gaia_worker_query_single_star, (
        row['name'],              # 'out31321'
        row['ra'],                # 131.90455  ← DA WCS!
        row['dec'],               # -14.37065  ← DA WCS!
        match_radius_arcsec=30,   # 30 arcsec standard
        row['Median_magnitude'],   # instrumental mag
        offset,                   # 14.5
        calibration_diff          # offset calibrazione
    )): idx
    for idx, (_, row) in enumerate(stars_valid.iterrows())
}
```

### 6c. Worker Gaia: Two-Stage Query

**File**: `_gaia_worker_query_single_star()` in `vast_service.py` line 66-300

```
STAGE 1 (10" radius):
  - Query Vizier: CONE(RA, Dec, 10")
  - Se trova candidati compatibili per magnitudine:
    ✅ Return: gaia_source_id, gmag, bp_rp (MATCH)
  - Else:
    → Procedi a STAGE 2

STAGE 2 (100" radius):
  - Query Vizier: CONE(RA, Dec, 100")
  - Se trova candidati:
    ⚠️ Return: gaia_source_id=NULL (AMBIGUOUS, no clear match)
  - Else:
    ❌ Return: NO_MATCH
```

**Parametri query Vizier**:
```python
from agata.catalog.services.vizier_client import VizierClient

vizier = VizierClient()
rows = vizier.query_cone(
    ra=row['ra'],       # 131.90455
    dec=row['dec'],     # -14.37065
    radius_arcsec=10,   # STAGE 1
    catalog='I/355/gaiadr3'  # Gaia DR3
)
```

**Output per ogni stella**:
```python
{
    'name': 'out31321',
    'ra': 131.90455,
    'dec': -14.37065,
    'status': 'match',  # 'match' | 'ambiguous' | 'no_match'
    'gaia_source_id': 5734104703954270464,  # ← KEY RESULT
    'gaia_gmag': 15.27,
    'gaia_bp_rp': 1.45,
    'gaia_vmag': 15.8,
    'distance_arcsec': 0.48,
}
```

---

## 7. SALVATAGGIO RISULTATI (Step 7)

**File**: `execute_job()` in `vast_service.py` line 1560-1600

```python
# Per ogni match:
insert_result = db.execute(
    text("""
        INSERT INTO agata_vast_results (
            job_id,
            gaia_source_id,
            gaia_vmag,
            name,
            ra,
            dec,
            Median_magnitude,
            ...
        ) VALUES (
            :job_id,
            :gaia_source_id,  # ← DA GAIA WORKER
            :gaia_vmag,       # ← CALCOLATO DA OFFSET
            :name,            # ← DA VAST
            :ra,              # ← DA WCS CONVERSION
            :dec,             # ← DA WCS CONVERSION
            :mag,             # ← DA VAST
            ...
        )
    """), {
        'job_id': job.id,
        'gaia_source_id': result['gaia_source_id'],  # KEY!
        'gaia_vmag': result['gaia_vmag'],
        'name': result['name'],
        'ra': result['ra'],
        'dec': result['dec'],
        ...
    }
)
```

---

## 📊 Diagramma Flusso Completo

```
┌─────────────────────────────────────────────────────────────────┐
│ VAST AUTOMATION JOB #161                                         │
└─────────────────────────────────────────────────────────────────┘

STEP 1: Download Images
  Google Drive
    ↓
  tmpdir/tess_2024-01-01.fits
  tmpdir/tess_2024-01-02.fits
  (n file TESS)

STEP 2: Validate WCS
  Apri ogni FITS
  Leggi header[0]
  ✅ WCS validated

STEP 3: VAST Execution
  vast_lightcurve_statistics.log (all stars)
  vast_autocandidates.log (690 candidates)
  reference_frame.fits (plate-solved)

STEP 4: Parse VAST Output
  ┌────────────────────┐
  │ stars_df (690)     │
  │ ├─ name: 'out31321'│
  │ ├─ x: 854.60 px    │
  │ ├─ y: 952.40 px    │
  │ └─ mag: 17.5       │
  └────────────────────┘

STEP 5: WCS Conversion (CRITICAL)
  ┌──────────────────────────────────┐
  │ reference_frame.fits (HDU 1)      │
  │ ├─ header.CRVAL1 = 45.93°        │
  │ ├─ header.CRVAL2 = 44.07°        │
  │ ├─ header.CD1_1, CD1_2, ...      │
  │ └─ wcs = WCS(header)             │
  └──────────────────────────────────┘
             ↓
  wcs.all_pix2world(x, y, origin=1)
             ↓
  ┌────────────────────────────────────┐
  │ Converted to RA/Dec                │
  │ ├─ x=854.60 px → RA=131.90455°    │ ← INPUT FOR GAIA!
  │ ├─ y=952.40 px → Dec=-14.37065°   │ ← INPUT FOR GAIA!
  │ └─ 690 stars converted             │
  └────────────────────────────────────┘

STEP 6: Gaia Cross-Match
  Parallel (4 workers)

  For each star (ra, dec from WCS):
    ├─ offset = 14.5 (from sample)
    ├─ Worker query:
    │   ├─ Vizier CONE(ra, dec, 10")
    │   │   ├─ Find candidates
    │   │   ├─ Magnitude validation
    │   │   └─ Take closest: gaia_source_id = 5734104703954270464
    │   │
    │   └─ Return: {
    │       'gaia_source_id': 5734104...,
    │       'gaia_vmag': 15.8,
    │       'ra': 131.90455,  ← SAME AS INPUT
    │       'dec': -14.37065, ← SAME AS INPUT
    │   }
    │
    └─ Salva in agata_vast_results

STEP 7: Database Insert
  INSERT INTO agata_vast_results (
    job_id,
    name,
    ra,           ← 131.90455 (from WCS)
    dec,          ← -14.37065 (from WCS)
    gaia_source_id ← 5734104703954270464
  )
```

---

## 🔑 Key Points

### WCS Source
1. **Reference frame**: Prima immagine TESS scaricata (tmpdir/tess_2024-01-01.fits)
2. **WCS location**: header[0] (HDU 0 per ground-based, HDU 1 per TESS)
3. **WCS content**:
   - CRVAL1/CRVAL2: centro campo
   - CD matrix: scala + rotazione
   - SIP (opzionale): distorsione

### Conversion
1. **Input**: Pixel coordinates da VAST (x, y) in 0-indexed SExtractor convention
2. **Output**: Celestial coordinates (RA, Dec) in gradi
3. **Formula**: `wcs.all_pix2world(x, y, origin=1)` con `origin=1` = FITS convention

### Gaia Query
1. **Input**: RA/Dec dalle WCS conversion
2. **Query**: Vizier cone search a 10" (Stage 1) o 100" (Stage 2)
3. **Output**: gaia_source_id per ogni stella

### Quality Checks
- **WCS validation**: Verifica che WCS.has_celestial = True
- **RA/Dec validation**: Scarta stelle con ra=0, dec=0 (WCS failed)
- **Magnitude validation**: Verifica offset = mean(Vmag) sia coerente
- **Gaia match**: Two-stage approach per robustezza

---

## 💡 Debug Hints for Job #161

Se il job ha problemi:

1. **WCS non trovato?**
   ```
   Check: Job #161 reference_frame file esiste?
   Check: HDU number corretto (1 per TESS)?
   Check: WCS.has_celestial = True?
   ```

2. **Coordinate sbagliate (RA/Dec = 0)?**
   ```
   Check: WCS conversion fallita?
   Check: Pixel coordinates (x, y) sono validi?
   Check: origin=1 usato correttamente?
   ```

3. **Gaia match non trovato?**
   ```
   Check: RA/Dec dalle WCS sono nel campo giusto?
   Check: Offset calculation da prime 5 stelle è coerente?
   Check: Magnitude validation passata?
   ```

4. **Visualizza log dettagliato**:
   ```
   grep "WCS conversion:" /var/log/astrogen/vast.log
   grep "Gaia cross-match:" /var/log/astrogen/vast.log
   grep "offset" /var/log/astrogen/vast.log
   ```

---

**Generated**: 2026-02-24
**Reference**: Job VAST-2026-161 (TESS import)
