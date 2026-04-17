# Algoritmo Corretto - Chiarificazione Finale

**Data**: 2026-02-17
**Stato**: Riscrittura da zero con logica corretta

---

## PRE-PHASE: Calcolo Offset (Passi 1-7)

### STEP 1: Prendi primi 5 VAST candidati

```
Input: 689 stelle VAST
Output: Primi 5 candidati selezionati
  - out31321
  - out42591
  - out08657
  - out30779
  - out36351
```

### STEP 2-3: Query Vizier 10" e prendi brightest per ogni stella

```
Per ogni stella dei 5:
  Stella 1 (out31321): Query Vizier 10"
    ├─ Candidate A: Gmag=14.5
    ├─ Candidate B: Gmag=12.3  ← brightest (prendi questo)
    └─ Candidate C: Gmag=16.8

  Stella 2 (out42591): Query Vizier 10"
    ├─ Candidate A: Gmag=18.1
    ├─ Candidate B: Gmag=16.2  ← brightest (prendi questo)
    └─ Candidate C: Gmag=20.3

  ... e così per le altre 3 stelle

Risultato: Una lista di 5 Gmag (il più brillante di ogni stella)
  gmag_list = [12.3, 16.2, 9.4, 11.8, 10.2]
```

### STEP 4: Calcola Vmag per ogni Gmag usando EDR3

```
Per ogni Gmag della lista, calcola Vmag con EDR3:
  Vmag = gmag + 0.02704 - 0.01424*BP_RP + 0.2156*BP_RP² - 0.01426*BP_RP³

Risultato:
  vmag_list = [11.3, 15.1, 8.7, 10.7, 9.8]
  (corrispondenti ai gmag [12.3, 16.2, 9.4, 11.8, 10.2])
```

### STEP 5: Calcola offset medio

```
offset = mean(vmag_list)
       = mean([11.3, 15.1, 8.7, 10.7, 9.8])
       = (11.3 + 15.1 + 8.7 + 10.7 + 9.8) / 5
       = 55.6 / 5
       = 11.12 mag

GLOBAL offset = 11.12 mag
```

### STEP 6: CALCOLO DELLA DIFFERENZA (NON ANCORA CALIBRAZIONE!)

**QUESTO È IL PASSO CRITICO CHE HO SBAGLIATO!**

```
Per ogni stella dei 5, calcola la differenza tra:
  - VAST_mag_strumentale (dal file vast_lightcurve_statistics.log)
  - Gmag della stella Gaia brightest trovata

Stella 1 (out31321):
  VAST_raw = -12.86 (dal file)
  Gmag_brightest = 12.3 (trovato da Vizier)
  diff_1 = |-12.86 - 12.3| = 25.16 mag

Stella 2 (out42591):
  VAST_raw = -11.5
  Gmag_brightest = 16.2
  diff_2 = |-11.5 - 16.2| = 27.7 mag

Stella 3 (out08657):
  VAST_raw = -13.2
  Gmag_brightest = 9.4
  diff_3 = |-13.2 - 9.4| = 22.6 mag

Stella 4 (out30779):
  VAST_raw = -12.1
  Gmag_brightest = 11.8
  diff_4 = |-12.1 - 11.8| = 23.9 mag

Stella 5 (out36351):
  VAST_raw = -11.8
  Gmag_brightest = 10.2
  diff_5 = |-11.8 - 10.2| = 22.0 mag

diff_list = [25.16, 27.7, 22.6, 23.9, 22.0]
```

### PASSO CRITICO: Verificare che le differenze siano TUTTE SIMILI

```
Se le differenze sono tutte simili (p.es: entro 1-2 mag):
  ✅ BUONO - la calibrazione avrà senso!
  prendi media_diff = mean([25.16, 27.7, 22.6, 23.9, 22.0]) = 24.27 mag

Se le differenze sono MOLTO diverse (p.es: 22, 40, 25, 23, 21):
  ❌ CATTIVO - c'è qualcosa di sbagliato!
  return 'no_match' - STOP, non continuare

Esempio BUONO (differenze simili):
  diff_list = [24.5, 24.8, 24.2, 23.9, 24.1]
  std_dev = 0.35 mag  ← molto bassa, buono!

Esempio CATTIVO (differenze diverse):
  diff_list = [22.0, 40.5, 24.1, 23.8, 21.9]
  std_dev = 7.5 mag  ← molto alta, cattivo!
```

### STEP 7: CONTROLLO DI COERENZA (dopo aver verificato similarità)

```
Se le differenze SONO simili:

  Prendi il valore rappresentativo (media delle differenze):
  calibration_diff = mean([25.16, 27.7, 22.6, 23.9, 22.0])
                   = 24.27 mag

  Poi, PER OGNI STELLA nel job (689 stelle), applicherai:
  VAST_calibrated = VAST_raw + calibration_diff

  E verifica:
  |VAST_calibrated - offset| <= 2.0 mag

  Cioè: |(VAST_raw + calibration_diff) - offset| <= 2.0
```

---

## IMPLEMENTAZIONE CORRETTA

### Pre-fase: Calcolo offset E calibration_diff

```python
def _calculate_magnitude_offset_from_sample(self, stars_valid, match_radius_arcsec):
    """
    STEP 1-7: Calcola offset e calibration_diff dalle prime 5 stelle
    """
    vizier_client = VizierClient(timeout_s=20)

    # STEP 1: Prendi primi 5
    sample_stars = stars_valid.head(5)

    vmags = []
    diffs = []

    for _, star_row in sample_stars.iterrows():
        star_name = star_row['name']
        star_ra = star_row['ra']
        star_dec = star_row['dec']
        vast_raw = star_row['Median_magnitude']  # ← VAST strumentale

        # STEP 2-3: Query Vizier 10", ordina per Gmag, prendi brightest
        rows = vizier_client.query_cone(
            catalog_id="I/355/gaiadr3",
            ra_deg=star_ra,
            dec_deg=star_dec,
            radius_arcsec=10,
            columns=['Source', 'RA_ICRS', 'DE_ICRS', 'Gmag', 'BP-RP']
        )

        if len(rows) == 0:
            continue

        rows_sorted = sorted(rows, key=lambda r: float(r.values.get('Gmag', 99)))
        brightest = rows_sorted[0]  # ← BRIGHTEST (smallest Gmag)

        gmag = float(brightest.values.get('Gmag', 99))
        bp_rp_val = brightest.values.get('BP-RP')
        bp_rp = float(bp_rp_val) if bp_rp_val is not None else None

        # STEP 4: Calcola Vmag
        vmag = _calculate_vmag_from_gaia(gmag, bp_rp)
        if vmag is None:
            continue

        vmags.append(vmag)

        # STEP 6: Calcola DIFFERENZA tra VAST_raw e Gmag
        # NON calibra ancora, solo calcola la differenza!
        diff = abs(vast_raw - gmag)
        diffs.append(diff)

        logger.debug(f"  {star_name}: VAST_raw={vast_raw:.2f}, Gmag={gmag:.2f}, "
                    f"Vmag={vmag:.2f}, diff={diff:.2f}")

    # STEP 5: Calcola offset come media Vmag
    if len(vmags) == 0:
        return None, None

    offset = float(np.mean(vmags))

    # PASSO CRITICO: Verifica che le differenze siano SIMILI
    if len(diffs) == 0:
        return None, None

    # Calcola std dev delle differenze
    std_diff = float(np.std(diffs))

    logger.info(f"Offset (mean Vmag): {offset:.2f} mag")
    logger.info(f"Differences: {diffs}")
    logger.info(f"Std dev of differences: {std_diff:.2f} mag")

    # Se le differenze sono troppo diverse, fallisci
    if std_diff > THRESHOLD_STD:  # Definire threshold (p.es: 2.0 mag)
        logger.warning(f"Differences NOT coherent (std={std_diff:.2f} > threshold)")
        return None, None

    # Se le differenze sono simili, prendi la media come calibration_diff
    calibration_diff = float(np.mean(diffs))

    logger.info(f"Calibration difference (mean): {calibration_diff:.2f} mag")

    return offset, calibration_diff
```

### Worker: Usa calibration_diff per calibrare

```python
def _gaia_worker_query_single_star(params):
    """
    Usa pre-calculated offset e calibration_diff
    """
    name, ra, dec, match_radius_arcsec, vast_raw, offset, calibration_diff = params

    # STEP 7: Calibra e verifica coerenza
    vast_calibrated = vast_raw + calibration_diff

    logger.info(f"[WORKER] Star {name}: VAST_raw={vast_raw:.2f}, "
               f"calibration_diff={calibration_diff:.2f}, "
               f"VAST_cal={vast_calibrated:.2f}, offset={offset:.2f}")

    # Controllo coerenza: |VAST_calibrated - offset| <= 2.0
    coherence_diff = abs(vast_calibrated - offset)
    if coherence_diff > 2.0:
        logger.warning(f"[STAGE 1] Star {name}: coherence FAILED "
                      f"(|{vast_calibrated:.2f} - {offset:.2f}| = {coherence_diff:.2f} > 2.0)")
        return {'name': name, 'status': 'no_match'}

    logger.info(f"[STAGE 1] Star {name}: coherence OK (diff={coherence_diff:.2f})")

    # STEP 8: Query Vizier 10" e matchmaking
    # ... resto come prima ...
```

---

## CAMBIO CRITICO

**PRIMA (SBAGLIATO)**:
- Calcola offset da Vmag (corretto)
- Applica direttamente: VAST_cal = VAST_raw + offset
- Verifica: |VAST_cal - offset| <= 2.0
- ❌ Fallisce perché offset è basato su Vmag Gaia, non su differenza VAST-Gmag

**DOPO (CORRETTO)**:
- Calcola offset da Vmag (corretto) ✅
- **Calcola calibration_diff come media delle differenze VAST_raw - Gmag** ✅
- **Verifica che calibration_diff sia coerente (std dev bassa)** ✅
- Applica: VAST_cal = VAST_raw + calibration_diff
- Verifica: |VAST_cal - offset| <= 2.0 ✅

---

## ESEMPIO CONCRETO

### Scenario: 5 stelle sample

```
Star 1: VAST_raw=-12.86, Gmag=12.3, Vmag=11.3
Star 2: VAST_raw=-11.50, Gmag=16.2, Vmag=15.1
Star 3: VAST_raw=-13.20, Gmag=9.4,  Vmag=8.7
Star 4: VAST_raw=-12.10, Gmag=11.8, Vmag=10.7
Star 5: VAST_raw=-11.80, Gmag=10.2, Vmag=9.8

offset = mean([11.3, 15.1, 8.7, 10.7, 9.8]) = 11.12 mag

diffs = [|-12.86-12.3|, |-11.50-16.2|, |-13.20-9.4|, |-12.10-11.8|, |-11.80-10.2|]
      = [25.16, 27.70, 22.60, 23.90, 22.00]

std_diff = std([25.16, 27.70, 22.60, 23.90, 22.00]) = 2.1 mag

Se std_diff < threshold (p.es 2.5):
  ✅ OK, le differenze sono coerenti
  calibration_diff = mean([25.16, 27.70, 22.60, 23.90, 22.00]) = 24.27 mag

Per stella generica out99999:
  VAST_raw = -13.5
  VAST_cal = -13.5 + 24.27 = 10.77

  Coerenza check:
  |10.77 - 11.12| = 0.35 < 2.0 ✅ OK!

  Procedi a Stage 1 matching
```

---

## PARAMETRI DA PASSARE AL WORKER

```python
# PRIMA (SBAGLIATO):
(name, ra, dec, match_radius_arcsec, VAST_raw, offset)

# DOPO (CORRETTO):
(name, ra, dec, match_radius_arcsec, VAST_raw, offset, calibration_diff)
```

---

## THRESHOLD

Qual è la threshold per std_dev delle differenze? Valori suggeriti:
- 1.0 mag: molto ristruttivo
- 2.0 mag: moderato
- 3.0 mag: generoso

Forse 2.0 mag è un buon punto di partenza?

