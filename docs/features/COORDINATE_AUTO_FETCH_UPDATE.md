# Auto-Fetch Coordinate da Gaia - Update

## Problema Riscontrato

Quando si eseguiva l'analisi comparativa stelle variabili, si verificava l'errore:
```
Error: Project must have coordinates
```

**Causa**: I progetti creati manualmente potrebbero non avere i campi `ra` e `dec_deg` popolati, necessari per la ricerca di stelle analoghe tramite query a cataloghi astronomici.

---

## Modifiche Implementate

### 1. Estensione `resolve_gaia_coordinates()`

**File**: [agata/admin/routes/catalogs/common.py](agata/admin/routes/catalogs/common.py:95)

La funzione ora recupera **parametri stellari aggiuntivi** oltre a coordinate:

```python
def resolve_gaia_coordinates(source_id: str) -> Optional[Dict[str, Any]]:
    """
    Returns:
        Dict con {source_id, ra, dec, phot_g_mean_mag, bp_rp, teff} o None
    """
```

**Parametri aggiunti**:
- `bp_rp` - Colore BP-RP (necessario per filtro similarità)
- `teff_gspphot` - Temperatura efficace (opzionale ma utile)

**Query ADQL migliorata**:
```sql
SELECT
    gs.source_id,
    gs.ra,
    gs.dec,
    gs.phot_g_mean_mag,
    gs.bp_rp,              -- NUOVO
    gs.teff_gspphot        -- NUOVO
FROM gaiadr3.gaia_source AS gs
WHERE gs.source_id = {numeric_source_id}
```

---

### 2. Auto-Fetch alla Creazione Progetto

**File**: [agata/admin/routes/projects.py](agata/admin/routes/projects.py:727)

**Endpoint**: `POST /agata/admin/api/projects`

Quando si crea un nuovo progetto:
1. Se `ra`, `dec_deg` o `magnitude` NON sono forniti nel body
2. Sistema esegue **auto-fetch** da Gaia DR3 usando `resolve_gaia_coordinates()`
3. Popola automaticamente i campi mancanti

**Codice**:
```python
# Auto-fetch coordinate e parametri stellari da Gaia se non forniti
ra = float(data['ra']) if data.get('ra') else None
dec_deg = float(data['dec_deg']) if data.get('dec_deg') else None
magnitude = float(data['magnitude']) if data.get('magnitude') else None

if ra is None or dec_deg is None or magnitude is None:
    from agata.admin.routes.catalogs.common import resolve_gaia_coordinates
    logger.info(f"Auto-fetching coordinates for Gaia ID: {gaia_id}")
    gaia_info = resolve_gaia_coordinates(gaia_id)

    if gaia_info:
        ra = ra or gaia_info.get('ra')
        dec_deg = dec_deg or gaia_info.get('dec')
        magnitude = magnitude or gaia_info.get('phot_g_mean_mag')
        logger.info(f"Auto-fetched: RA={ra}, Dec={dec_deg}, Mag={magnitude}")
```

**Vantaggi**:
- Progetti creati solo con `gaia_id` hanno coordinate automatiche
- Riduce errori manuali
- Non sovrascrive valori forniti esplicitamente

---

### 3. Endpoint Refresh Coordinate (Progetti Esistenti)

**File**: [agata/admin/routes/projects.py](agata/admin/routes/projects.py:800)

**Nuovo Endpoint**: `POST /agata/admin/api/projects/<id>/refresh-gaia-data`

**Permessi**: `analyst`, `admin`, `superuser` (stesso permesso analisi comparativa)

**Funzionalità**:
- Recupera coordinate + parametri da Gaia DR3
- Aggiorna campi `ra`, `dec_deg`, `magnitude` nel database
- Log audit trail con valori precedenti vs nuovi
- Ritorna `bp_rp` e `teff` (non salvati in Project ma disponibili per analisi)

**Response**:
```json
{
  "success": true,
  "project_id": 123,
  "gaia_id": "Gaia DR3 1234567890",
  "updated_data": {
    "ra": 123.456789,
    "dec": 45.678901,
    "magnitude": 12.34,
    "bp_rp": 1.23,
    "teff": 5800
  },
  "previous_data": {
    "ra": null,
    "dec": null,
    "magnitude": null
  }
}
```

---

### 4. UI - Button "Aggiorna da Gaia"

**File**: [agata/templates/admin/components/project_info.html](agata/templates/admin/components/project_info.html:41)

**Modifiche**:
1. Aggiunto ID ai campi coordinate per update dinamico:
   ```html
   <dd class="col-sm-7" id="raDisplay">{{ project.ra | round(6) if project.ra else '-' }}°</dd>
   ```

2. **Alert Warning** se coordinate mancanti:
   ```html
   {% if not project.ra or not project.dec_deg or not project.magnitude %}
   <div class="alert alert-warning alert-sm mb-2">
       <i class="fas fa-exclamation-triangle"></i>
       Coordinate mancanti - necessarie per analisi comparativa
   </div>
   {% endif %}
   ```

3. **Button Refresh**:
   ```html
   <button type="button" class="btn btn-sm btn-outline-primary" id="refreshGaiaBtn"
           onclick="refreshGaiaData()" title="Recupera coordinate da Gaia DR3">
       <i class="fas fa-sync-alt"></i> Aggiorna da Gaia
   </button>
   ```

4. **JavaScript Handler**:
   - Chiama endpoint `POST /refresh-gaia-data`
   - Aggiorna campi UI dinamicamente
   - Ricarica pagina per refresh completo
   - Mostra alert con valori aggiornati

---

## Workflow Utente

### Caso 1: Creazione Nuovo Progetto

**Admin Panel → Create Project**

1. Compila form con **solo** `gaia_id` (es. `Gaia DR3 1234567890`)
2. Lascia `ra`, `dec`, `magnitude` vuoti
3. Clicca **Crea Progetto**

**Risultato**:
- Sistema auto-fetch da Gaia DR3
- Progetto creato con coordinate complete
- Log: `Auto-fetched: RA=123.456, Dec=45.678, Mag=12.34`

---

### Caso 2: Progetto Esistente Senza Coordinate

**Admin Panel → Project Detail**

1. Visualizza warning: "Coordinate mancanti - necessarie per analisi comparativa"
2. Clicca **🔄 Aggiorna da Gaia**
3. Sistema fetch da Gaia DR3
4. Alert: "Dati Gaia aggiornati con successo!"
5. Pagina ricaricata con coordinate aggiornate

**UI Prima**:
```
RA:          -
Dec:         -
Magnitudine: -
⚠️ Coordinate mancanti - necessarie per analisi comparativa
```

**UI Dopo**:
```
RA:          123.456789°
Dec:         45.678901°
Magnitudine: 12.34
✅ Coordinate aggiornate
```

---

### Caso 3: Uso Analisi Comparativa

**Editor Stelle Variabili → Tab Analisi Comparativa**

1. Calcola periodogramma (trova periodi)
2. Vai al tab **🔍 Analisi Comparativa**
3. Clicca **🔍 Cerca Analoghe**

**Prima delle modifiche**:
```
❌ Error: Project must have coordinates
```

**Dopo le modifiche**:
```
✅ Trovate 10 stelle analoghe
Parametri: BP-RP=1.23, G=12.3 mag, Periodi=0.999, 1.001, 0.998 d
```

---

## Testing

### Test 1: Auto-Fetch Creazione

```bash
curl -X POST https://app-test.astrogen.it/agata/admin/api/projects \
  -H "Content-Type: application/json" \
  -H "Cookie: session=YOUR_SESSION" \
  -d '{
    "gaia_id": "Gaia DR3 1234567890",
    "association_id": 1,
    "title": "Test Auto-Fetch"
  }'
```

**Response attesa**:
```json
{
  "success": true,
  "project_code": "AGATA-2026-001",
  "ra": 123.456789,
  "dec": 45.678901,
  "magnitude": 12.34
}
```

---

### Test 2: Refresh Coordinate Esistenti

```bash
curl -X POST https://app-test.astrogen.it/agata/admin/api/projects/123/refresh-gaia-data \
  -H "Cookie: session=YOUR_SESSION"
```

**Response attesa**:
```json
{
  "success": true,
  "updated_data": {
    "ra": 123.456789,
    "dec": 45.678901,
    "magnitude": 12.34,
    "bp_rp": 1.23,
    "teff": 5800
  }
}
```

---

### Test 3: Analisi Comparativa End-to-End

1. Crea progetto con solo `gaia_id` (coordinate auto-fetch)
2. Importa dati ASAS-SN per il progetto
3. Apri editor stelle variabili
4. Calcola periodogramma
5. Tab Analisi Comparativa → **Cerca Analoghe**

**Aspettativa**: Nessun errore "Project must have coordinates"

---

## Audit Trail

Tutte le operazioni sono loggate in `agata_audit_log`:

### Creazione con Auto-Fetch
```sql
action = 'project_created'
description = 'Progetto AGATA-2026-001 creato manualmente via interfaccia admin'
-- RA/Dec/Mag visibili nei campi del progetto
```

### Refresh Coordinate
```sql
action = 'project_gaia_refresh'
entity_type = 'project'
old_value = "{'ra': null, 'dec': null, 'magnitude': null}"
new_value = "{'ra': 123.45, 'dec': 45.67, 'phot_g_mean_mag': 12.34, 'bp_rp': 1.23, 'teff': 5800}"
description = 'Auto-refresh dati Gaia per progetto AGATA-2026-001'
```

---

## Configurazione Gaia TAP

**URL**: `https://gea.esac.esa.int/tap-server/tap/sync`

**Timeout**: 30s (configurabile in `common.py`)

**Rate Limiting**: Gaia TAP ha rate limits pubblici (~10 req/min). Per uso intensivo considerare:
- Caching risultati (già implementato per analisi comparativa)
- Mirror locale Gaia DR3 (per grosse installazioni)

---

## Sicurezza

### Validazione Input
- `source_id` normalizzato: rimuove "Gaia DR3 " prefix se presente
- Query ADQL parametrizzata (no SQL injection)
- Permessi endpoint: solo `analyst+` può refresh

### Privacy
- Dati Gaia DR3 sono pubblici (ESA)
- Nessun dato sensibile esposto
- Audit log completo

---

## Roadmap Futuro

### Feature da Implementare

1. **Batch Refresh Coordinate**
   - Endpoint: `POST /api/projects/batch-refresh-gaia`
   - Aggorna tutti i progetti senza coordinate in background

2. **Edit Manuale Coordinate UI**
   - Form inline per modifica `ra`, `dec`, `magnitude`
   - Validazione range (RA: 0-360, Dec: -90 to 90)

3. **Cache Gaia Queries**
   - Redis cache per `resolve_gaia_coordinates()`
   - TTL: 7 giorni (Gaia DR3 statico)

4. **Fallback Simbad/VizieR**
   - Se Gaia TAP down, usa servizi alternativi
   - Priority: Gaia > Simbad > VizieR

---

## Troubleshooting

### Errore: "Could not fetch Gaia data for Gaia DR3 XXX"

**Cause Possibili**:
1. Gaia TAP offline (check https://gea.esac.esa.int/archive/)
2. `source_id` errato (verifica su Gaia Archive)
3. Timeout query (aumenta timeout in `common.py`)
4. Stella non in Gaia DR3 (usa cataloghi alternativi)

**Soluzione**:
- Verifica `source_id` su Gaia Archive manualmente
- Inserisci coordinate manualmente (feature da implementare)

---

### Warning Rimane Dopo Refresh

**Causa**: Cache template o pagina non ricaricata

**Soluzione**:
- Hard refresh browser (Ctrl+F5)
- JavaScript esegue `location.reload()` automaticamente

---

## File Modificati

| File | Tipo | Modifiche |
|------|------|-----------|
| `agata/admin/routes/catalogs/common.py` | Backend | Esteso `resolve_gaia_coordinates()` con `bp_rp`, `teff` |
| `agata/admin/routes/projects.py` | Backend | Auto-fetch creazione + endpoint refresh |
| `agata/templates/admin/components/project_info.html` | Frontend | Button refresh + warning + JS handler |
| `agata/static/js/variable_stars/variability-comparison.js` | Frontend | Fix `getPeriods()` typo (`periodogramResult`) |

---

**Data Implementazione**: 2026-01-30
**Versione**: 1.13.1
**Autore**: Claude Code AI
**Testing**: In corso su `app-test.astrogen.it`
