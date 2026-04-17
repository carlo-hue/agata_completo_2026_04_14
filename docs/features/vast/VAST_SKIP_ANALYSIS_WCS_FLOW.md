# Skip Analysis Mode - WCS Source (Quando skippi il VAST)

## Confronto: Normal vs Skip_vast

### 🔴 NORMAL FLOW (esegui VAST dentro app)

```
Step 1: Download images
  ↓
Step 2: Validate WCS (da immagini scaricate)
  ↓
Step 3: Esegui VAST (10 ore)
  ↓
Step 4: Parse output VAST
  ↓
Step 5: WCS conversion (prendi WCS da reference_frame = prima immagine scaricata)
  ↓
Step 6: Gaia query
```

---

### 🟢 SKIP_VAST FLOW (VAST già lanciato fuori)

```
Step 1: Download images (OPZIONALE! dipende da source_type)
  ↓
Step 2: Validate WCS (sempre, anche in skip mode)
  ↓
Step 3: SKIP VAST ← **Non esegui VAST**
           ↓ Usa output VAST esistente da vast_dir
  ↓
Step 4: Parse output VAST (da directory VAST)
  ↓
Step 5: WCS conversion (DA DOVE PRENDE IL WCS?)
  ↓
Step 6: Gaia query
```

---

## 🔑 KEY DIFFERENCE: Dove prende il reference_frame?

### Normal Mode
```python
# vast_service.py line 560-575
vast_result = self.vast_executor.run_vast_analysis(
    image_dir=tmpdir,              # ← Immagini scaricate
    reference_frame=image_paths[0] # ← Prima immagine scaricata
)

reference_frame = vast_result['reference_frame']
# = tmpdir/tess_2024-01-01.fits (scaricata da Google Drive)
```

### Skip_vast Mode
```python
# vast_service.py line 534-540
vast_result = self.vast_executor.validate_existing_output(
    image_dir=job.source_location if job.source_type == 'local_path' else tmpdir,
                                 # ↑ DIPENDE DA SOURCE_TYPE!
    reference_frame=image_paths[0] if image_paths else None
                                 # ↑ OPZIONALE, dipende se hai scaricato
)

reference_frame = vast_result.get('reference_frame')
# = ???? (dipende dalla logica sottostante)
```

---

## 📍 CRITICAL LOGIC: validate_existing_output()

### File: `vast_executor.py` line 153-223

```python
def validate_existing_output(self, image_dir=None, reference_frame=None):
    """
    Valida output VAST esistente (VAST già lanciato fuori dall'app).
    """
    vast_dir = os.path.dirname(self.vast_binary)  # ← /home/azureuser/Documents/vast-1.0rc87

    # Step 1: Verifica file VAST output nel vast_dir
    lightcurve_stats = os.path.join(vast_dir, 'vast_lightcurve_statistics.log')
    candidates_log = os.path.join(vast_dir, 'vast_autocandidates.log')

    # Check file obbligatori
    if not os.path.exists(lightcurve_stats):
        raise FileNotFoundError(...)
    if not os.path.exists(candidates_log):
        raise FileNotFoundError(...)

    # Step 2: **LOGICA CRITICA per reference_frame**

    # Se nessuna reference_frame fornita,
    # cerca nella directory immagini
    if not reference_frame and image_dir:
        fits_files = sorted(glob.glob(f"{image_dir}/*.fit*"))
        if fits_files:
            reference_frame = fits_files[0]  # ← Prima FITS trovata
            logger.info(f"Auto-selected reference frame: {reference_frame}")

    # Ritorna reference_frame (potrebbe essere None!)
    return {
        ...
        'reference_frame': reference_frame,  # ← QUESTO!
    }
```

---

## 🚨 PROBLEMA: reference_frame può essere None!

### Scenario 1: source_type = 'google_drive'

```python
# vast_service.py line 534-537
vast_result = self.vast_executor.validate_existing_output(
    image_dir=tmpdir,                    # ← Directory temporanea (scaricati)
    reference_frame=image_paths[0] if image_paths else None
)
```

**Se immagini scaricate correttamente**:
- `image_paths = ['/tmp/vast_job_161_xxx/tess_*.fits', ...]`
- `reference_frame = image_paths[0]`
- Passa a `validate_existing_output()`
- **✅ Ritorna il reference_frame**

**Se download FALLISCE**:
- `image_paths = []`
- `reference_frame = None`
- Passa a `validate_existing_output(image_dir=tmpdir, reference_frame=None)`
- In validate_existing_output:
  ```python
  if not reference_frame and image_dir:  # ← True
      fits_files = sorted(glob.glob(f"{tmpdir}/*.fit*"))  # ← Niente!
      if fits_files:  # ← False (no files scaricati)
          reference_frame = fits_files[0]
  ```
- **❌ Ritorna reference_frame = None**

### Scenario 2: source_type = 'local_path'

```python
# vast_service.py line 534-537
vast_result = self.vast_executor.validate_existing_output(
    image_dir=job.source_location,  # ← Directory locale (NON tmpdir!)
    reference_frame=image_paths[0] if image_paths else None
)
```

**Se le immagini esistono localmente**:
- `image_paths = None` (non scaricate, sono locali)
- `reference_frame = None`
- Passa a `validate_existing_output(image_dir='/data/vast_images/', reference_frame=None)`
- In validate_existing_output:
  ```python
  if not reference_frame and image_dir:  # ← True
      fits_files = sorted(glob.glob(f"/data/vast_images/*.fit*"))
      if fits_files:  # ← True! Trovate localmente
          reference_frame = fits_files[0]
  ```
- **✅ Ritorna reference_frame = prima FITS locale**

---

## 📊 Diagramma: Skip_vast WCS Resolution

```
SKIP_VAST MODE:
├─ source_type = 'google_drive'
│   ├─ Step 1: Download images → tmpdir/tess_*.fits
│   │   ├─ Success → image_paths = ['/tmp/...', ...]
│   │   └─ Fail → image_paths = None
│   │
│   ├─ Step 3: validate_existing_output(
│   │           image_dir=tmpdir,
│   │           reference_frame=image_paths[0] if image_paths else None
│   │       )
│   │
│   ├─ Inside validate_existing_output:
│   │   ├─ reference_frame dato? → Usa quello
│   │   ├─ reference_frame None?
│   │   │   └─ Cerca in tmpdir/ ← Dove sono immagini scaricate
│   │   │       ├─ Trovate? → reference_frame = prima FITS ✅
│   │   │       └─ Non trovate? → reference_frame = None ❌
│   │   │
│   │   └─ Return: {'reference_frame': ...}
│   │
│   └─ reference_frame usato per Step 5 (WCS conversion)
│
├─ source_type = 'local_path'
│   ├─ Step 1: Download SKIPPED (immagini già locali)
│   │   └─ image_paths = None
│   │
│   ├─ Step 3: validate_existing_output(
│   │           image_dir=job.source_location ('/data/vast_images/'),
│   │           reference_frame=None
│   │       )
│   │
│   ├─ Inside validate_existing_output:
│   │   ├─ reference_frame None? → Yes
│   │   ├─ image_dir fornito? → Yes
│   │   ├─ Cerca in image_dir
│   │   │   └─ fits_files = glob('/data/vast_images/*.fit*')
│   │   │       ├─ Trovate? → reference_frame = prima FITS ✅
│   │   │       └─ Non trovate? → reference_frame = None ❌
│   │   │
│   │   └─ Return: {'reference_frame': ...}
│   │
│   └─ reference_frame usato per Step 5 (WCS conversion)
```

---

## ✅ QUANDO FUNZIONA (reference_frame trovato)

### Case 1: Google Drive + Download Success
```
1. Download: /tmp/vast_job_161_xxx/tess_2024-01-01.fits ✅
2. image_paths[0] = '/tmp/.../tess_2024-01-01.fits'
3. validate_existing_output(..., reference_frame='/tmp/.../tess_2024-01-01.fits')
4. WCS prende header da '/tmp/.../tess_2024-01-01.fits' ✅
```

### Case 2: Local path
```
1. source_type = 'local_path'
2. job.source_location = '/var/data/vast_job_161/'
3. validate_existing_output(image_dir='/var/data/vast_job_161/', reference_frame=None)
4. Cerca /var/data/vast_job_161/*.fit* → trova 'frame.fits'
5. WCS prende header da '/var/data/vast_job_161/frame.fits' ✅
```

---

## ❌ QUANDO FALLISCE (reference_frame = None)

### Case 1: Google Drive + Download Fail
```
1. Download FAILS → image_paths = None
2. reference_frame = None
3. validate_existing_output(image_dir='/tmp/vast_job_161_xxx/', reference_frame=None)
4. glob('/tmp/vast_job_161_xxx/*.fit*') → [] (directory vuota!)
5. reference_frame rimane None
6. Step 5 WCS conversion: reference_frame = None
   ↓
   with fits.open(None) → CRASHES ❌
```

### Case 2: Local path + Files Not Found
```
1. source_type = 'local_path'
2. job.source_location = '/var/data/vast_job_161/'
3. But directory non esiste o non ha FITS
4. validate_existing_output(image_dir='/var/data/vast_job_161/', reference_frame=None)
5. glob('/var/data/vast_job_161/*.fit*') → [] (no files!)
6. reference_frame rimane None
7. Step 5 WCS conversion: reference_frame = None
   ↓
   with fits.open(None) → CRASHES ❌
```

---

## 🔧 FIX (Possibile)

### Opzione 1: Fallback to VAST directory

Se non trovi reference_frame, cerca nel vast_dir (dove VAST fu lanciato):

```python
def validate_existing_output(self, image_dir=None, reference_frame=None):
    vast_dir = os.path.dirname(self.vast_binary)

    # Step 1: Se reference_frame fornito, usa quello
    if reference_frame:
        return {..., 'reference_frame': reference_frame}

    # Step 2: Cerca in image_dir
    if image_dir:
        fits_files = sorted(glob.glob(f"{image_dir}/*.fit*"))
        if fits_files:
            reference_frame = fits_files[0]
            return {..., 'reference_frame': reference_frame}

    # Step 3: NUOVO - Fallback a vast_dir
    fits_files = sorted(glob.glob(f"{vast_dir}/*.fit*"))
    if fits_files:
        reference_frame = fits_files[0]
        logger.info(f"Using reference frame from vast_dir: {reference_frame}")
        return {..., 'reference_frame': reference_frame}

    # Step 4: Fallback to None (permetti Step 5 di gestire)
    logger.warning("No reference frame found anywhere!")
    return {..., 'reference_frame': None}
```

### Opzione 2: Richiedi reference_frame esplicito

```python
# vast_service.py line 534
if skip_vast:
    if not image_paths:
        raise ValueError("skip_vast mode requires reference_frame or images")

    vast_result = self.vast_executor.validate_existing_output(
        image_dir=...,
        reference_frame=image_paths[0]  # ← REQUIRED
    )
```

---

## 📋 Checklist per Debug Skip_vast Job

```
Quando job FALLISCE in skip_vast:

□ 1. reference_frame value?
     Log: "WCS conversion: reference=..."
     ✅ Se non è None → continua
     ❌ Se è None → problema!

□ 2. Se None, check source_type:
     ✅ google_drive: immagini scaricate in tmpdir?
     ✅ local_path: job.source_location esiste?

□ 3. WCS conversion:
     Log: "WCS conversion complete: X stars"
     ✅ Se completo → Gaia query ha coordinate
     ❌ Se fallito → RA/Dec = 0, no Gaia match

□ 4. Step 5 traceback:
     grep "WCS conversion failed:" job.log
     └─ Se "NoneType object", reference_frame = None
```

---

## 🎯 Summary

| Aspetto | Normal Flow | Skip_vast Mode |
|---------|-------------|----------------|
| **VAST** | Eseguito (10h) | Saltato (output esterno) |
| **reference_frame** | Prima immagine scaricata | Dipende da source_type + image_dir |
| **WCS source** | tmpdir/tess_*.fits | image_dir/*.fits OR job.source_location/*.fits |
| **Possibile None?** | No | ✅ Sì, se download fallisce o path sbagliato |
| **WCS conversion** | Da WCS header scaricato | Da WCS header locale o scaricato |
| **Gaia query** | RA/Dec da WCS | RA/Dec da WCS (o None se fallito) |

---

**Generated**: 2026-02-24
**Context**: Skip_vast mode in VAST automation
