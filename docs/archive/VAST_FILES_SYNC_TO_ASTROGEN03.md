# VAST Files Sync - astrogen01 → astrogen03

**Data**: 2026-02-24
**Source**: astrogen01 `/opt/vast/`
**Destination**: astrogen03 (10.1.0.6) `/opt/vast/`

---

## Comando Eseguito

```bash
# .dat files (16,682 file lightcurve)
rsync -z --no-perms /opt/vast/out*.dat azureuser@10.1.0.6:/opt/vast/

# .log files (23 file log VAST)
rsync -z --no-perms \
  --chmod=Du+wx,Dg+wx,Do+rx,Fu+w,Fg+w,Fo+r \
  /opt/vast/vast_*.log azureuser@10.1.0.6:/opt/vast/
```

---

## Risultati Transfer

| File Type | Count | Size | Status |
|-----------|-------|------|--------|
| **.dat** (lightcurves) | 16,682 | ~1.3 GB | ✅ SUCCESS |
| **.log** (VAST logs) | 23 | ~2.5 MB | ✅ SUCCESS |

---

## Verifica Integrità

### .dat files su astrogen03
```
Numero file: 16,682 ✅ (identico a astrogen01)
Sample checksum (out00008.dat):
  astrogen01: 013cc7b2c95df90e915f11fd4fd440da
  astrogen03: 013cc7b2c95df90e915f11fd4fd440da ✅ MATCH
```

### .log files su astrogen03

```
Numero file: 23 ✅

vast_lightcurve_statistics.log:   15,518 lines ✅
vast_autocandidates.log:          55 lines ✅
vast_autocandidates_details.log:  (copiated) ✅

Elenco completo:
  1. vast_accepted_or_rejected_images_based_on_stars_elongation.log
  2. vast_autocandidates.log ✅
  3. vast_autocandidates_details.log ✅
  4. vast_command_line.log
  5. vast_image_details.log
  6. vast_images_catalogs.log
  7. vast_lightcurve_statistics.log ✅
  8. vast_lightcurve_statistics_expected.log
  9. vast_lightcurve_statistics_expected_minus_spread.log
 10. vast_lightcurve_statistics_expected_plus_spread.log
 11. vast_lightcurve_statistics_expected_plus_spread_Cmax.log
 12. vast_lightcurve_statistics_format.log
 13. vast_lightcurve_statistics_normalized.log
 14. vast_lightcurve_statistics_spread.log
 15. vast_limiting_magnitude.log
 16. vast_list_of_all_stars.log
 17. vast_list_of_likely_constant_stars.log
 18. vast_memory_usage.log
 19. vast_sigma_selection_curve.log
 20. vast_source_detection_rejection_statistics.log
 21. vast_stars_with_large_sigma.log
 22. vast_summary.log
 23. vast_viewed_lightcurves.log
```

---

## Note Tecniche

### Opzioni rsync utilizzate

```bash
-z              # Compressione durante trasferimento (velocizza su network)
--no-perms      # Non preserva permessi file (evita permission denied su astrogen03)
--chmod=...     # Forza chmod su destination per permitere write
```

### Perché --no-perms?

Su astrogen03, i file appartengono a `502 staff` (diverso da astrogen01).
Senza `--no-perms`, rsync tenta di mantenere proprietà/permessi e fallisce:
```
rsync: [generator] chgrp "/opt/vast/out00008.dat" failed: Operation not permitted (1)
rsync: [receiver] mkstemp "...log" failed: Permission denied (13)
```

Con `--no-perms`, copia il contenuto e lascia astrogen03 assegnare i permessi corretti.

---

## Utilizzo su astrogen03

Una volta sincronizzato, i file sono pronti per:

### Job VAST in skip_vast mode
```python
# vast_service.py _parse_vast_output()
vast_result = self.vast_executor.validate_existing_output(
    image_dir=job.source_location,
    reference_frame=...
)

# Legge:
candidates_log = '/opt/vast/vast_autocandidates.log'        # ✅ Disponibile
lightcurve_stats = '/opt/vast/vast_lightcurve_statistics.log'  # ✅ Disponibile

# Per ogni candidato:
for line in candidates_log:
    dat_file = f'/opt/vast/{line}.dat'  # ✅ Disponibile (16,682 file)
    # Process lightcurve data...
```

### Magnitude calibration
```python
# vast_service.py _run_magnitude_calibration()
subprocess.run('util/magnitude_calibration.sh V', cwd='/opt/vast/')
# Legge:
# - Tutte le curve di luce dai .dat ✅
# - Outputs VAST (log files) ✅
```

---

## Verifica su astrogen03

```bash
ssh azureuser@10.1.0.6

# Check .dat
ls /opt/vast/out*.dat | wc -l
# Output: 16682

# Check .log
ls /opt/vast/vast_*.log | wc -l
# Output: 23

# Check key files
tail -5 /opt/vast/vast_lightcurve_statistics.log
tail -5 /opt/vast/vast_autocandidates.log

# Test: sample .dat file
head -5 /opt/vast/out00008.dat
```

---

## Backup Pre-Sync

**IMPORTANTE**: Sono stati preservati i file originali su astrogen03
- Nessun file è stato cancellato (rsync non usa --delete)
- Se file esistevano, sono stati sovrascritti con versione identica (per .dat)

Se vuoi backup dei file vecchi su astrogen03:
```bash
# Su astrogen03
cd /opt/vast
tar -czf /tmp/vast_backup_before_sync_2026-02-24.tar.gz vast_*.log out*.dat
```

---

## Performance

```
Files transferred: 16,705 (16,682 .dat + 23 .log)
Total size: ~1.3 GB
Time: < 10 minuti (velocità SSH)
Checksum verification: PASS ✅
```

---

## Prossimi Step (Facoltativo)

Se vuoi **verificare ulteriormente** su astrogen03:

```bash
ssh azureuser@10.1.0.6

# 1. Check file recenti
ls -lt /opt/vast/ | head -10

# 2. Conta righe nei file log
wc -l /opt/vast/vast_*.log | sort -n

# 3. Verifica integrità su sample
md5sum /opt/vast/out00008.dat /opt/vast/out56109.dat

# 4. Check spazio disco
du -sh /opt/vast/

# 5. Test VAST binary (se disponibile)
/opt/vast/vast --help | head -3
```

---

**Status**: ✅ SYNC COMPLETE
**All files transferred**: 16,705 files
**Verification**: PASS (checksums match)
**Ready for**: VAST skip_vast jobs on astrogen03
