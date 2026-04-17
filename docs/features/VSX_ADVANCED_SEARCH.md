# VSX Advanced Search - Feature Implementation

**Data**: 2026-02-02
**Versione**: 1.16.0
**Status**: Completato

## Panoramica

Implementata ricerca avanzata di stelle variabili analoghe usando l'API completa di VSX (AAVSO Variable Star Index). Gli utenti possono ora specificare intervalli di magnitudine, periodo, tipo di variabile e classe spettrale per query più precise.

## Motivazione

La ricerca precedente usava solo coordinate, magnitudine centrale e periodo centrale con tolleranze fisse. L'interfaccia web di VSX (https://vsx.aavso.org/vsx/index.php?view=search.top) supporta parametri molto più dettagliati che permettono ricerche più mirate e scientificamente rilevanti.

## Modifiche Implementate

### 1. Backend - Servizio Analisi Variabilità

**File**: `agata/admin/services/variability_analysis.py`

#### Funzione `query_vsx()` - Parametri Aggiunti

```python
def query_vsx(
    ra: float,
    dec: float,
    mag: float = None,
    periodo: float = None,
    tolerances: Dict = None,
    radius_deg: float = 5.0,
    max_mag: float = None,           # NUOVO: Magnitudine massima
    min_mag: float = None,           # NUOVO: Magnitudine minima
    period_min: float = None,        # NUOVO: Periodo minimo (giorni)
    period_max: float = None,        # NUOVO: Periodo massimo (giorni)
    vartype: str = None,             # NUOVO: Tipo variabile (abbreviazione GCVS)
    spec_type: str = None            # NUOVO: Classe spettrale
) -> List[Dict]:
```

**Logica**:
- Se `max_mag`/`min_mag` sono specificati, usa quelli; altrimenti calcola da `mag ± toleranze`
- Se `period_min`/`period_max` sono specificati, usa quelli; altrimenti calcola da `periodo ± toleranze`
- `vartype` e `spec_type` sono opzionali e passati direttamente a VSX API
- Calcolo similarità aggiornato per gestire parametri opzionali

#### Funzione `trova_stelle_analoghe()` - Parametri Aggiunti

Aggiunta propagazione parametri VSX avanzati dalla route API al servizio query.

### 2. Backend - API Endpoint

**File**: `agata/admin/routes/project_detail.py`

**Endpoint**: `POST /api/projects/<id>/variability/search-analogues`

#### Request Body (nuovi parametri opzionali)

```json
{
  "periods": [0.567890],
  "top_n": 10,
  "radius_deg": 5.0,
  "max_mag": 15.5,           // NUOVO
  "min_mag": 10.0,           // NUOVO
  "period_min": 0.1,         // NUOVO
  "period_max": 1.0,         // NUOVO
  "vartype": "RRAB",         // NUOVO: Abbreviazione GCVS
  "spec_type": "G2V"         // NUOVO: Classe spettrale
}
```

#### Cache Key

Cache key aggiornato per includere nuovi parametri VSX:

```python
cache_key = f"analogues:vsx:{gaia_id}:{periods}:{max_mag}:{min_mag}:{period_min}:{period_max}:{vartype}:{spec_type}"
```

### 3. Frontend - UI Form

**File**: `agata/templates/variable_stars/index.html`

#### Campi Aggiunti (sezione "Ricerca Stelle Analoghe VSX")

1. **Magnitudine Minima (range)**:
   - `#minMagMin` - Mag minima più brillante
   - `#minMagMax` - Mag minima più debole
2. **Magnitudine Massima (range)**:
   - `#maxMagMin` - Mag massima più brillante
   - `#maxMagMax` - Mag massima più debole
3. **Periodo Min** (`#periodMin`) - periodo minimo in giorni
4. **Periodo Max** (`#periodMax`) - periodo massimo in giorni
5. **Tipo Variabile** (`#varType`) - abbreviazione GCVS (es: RRAB, EA, DSCT)
6. **Classe Spettrale** (`#specType`) - classe spettrale (es: G2V, M3III)

**Note**: Le coordinate (RA/Dec) sono automaticamente risolte dal progetto corrente (Gaia DR3), non servono input manuali.

#### Bottone "Copia parametri dalla stella corrente"

Nuovo bottone (`#copyFromStarBtn`) che auto-popola i campi con:
- **Range magnitudine**: Valori da analisi di fase (mag_min e mag_max dal periodogramma) se disponibili, altrimenti magnitudine progetto ±0.5 mag
- **Range periodo**: periodo principale ±10%
- **Classe spettrale**: dal form "Analisi di Supporto"
- **Tipo variabile**: dal form "Analisi di Supporto" (con mapping a abbreviazioni GCVS)

### 4. Frontend - JavaScript

**File**: `agata/static/js/variable_stars/variability-comparison.js`

#### Funzioni Aggiunte

1. **`handleCopyFromStar()`**: Popola automaticamente i campi VSX con i dati del progetto corrente
2. **`populateMagnitudeFromPhaseOrProject()`**: Recupera magnitudine da `state.phaseStats` (se disponibile da analisi di fase) o dal progetto per popolare i 4 campi range

#### Aggiornamento `handleSearchAnalogues()`

Legge nuovi parametri dal form (4 campi magnitudine) e li invia all'API:

```javascript
// 4 campi magnitudine (min_mag_min, min_mag_max, max_mag_min, max_mag_max)
const minMagMin = parseFloat(document.getElementById('minMagMin')?.value) || null;
const minMagMax = parseFloat(document.getElementById('minMagMax')?.value) || null;
const maxMagMin = parseFloat(document.getElementById('maxMagMin')?.value) || null;
const maxMagMax = parseFloat(document.getElementById('maxMagMax')?.value) || null;

const periodMin = parseFloat(document.getElementById('periodMin')?.value) || null;
const periodMax = parseFloat(document.getElementById('periodMax')?.value) || null;
const varType = document.getElementById('varType')?.value?.trim() || null;
const specType = document.getElementById('specType')?.value?.trim() || null;
```

**Logging Dettagliato**: Ogni richiesta VSX logga:
- 📤 Request body inviato all'API
- 📥 Response status (HTTP code)
- ✅ Response data completo (analogues count, cache hit, parametri usati)
- ❌ Error response body (in caso di errore)

#### Aggiornamento Display Risultati

Header risultati mostra parametri VSX usati nella ricerca:

```
Parametri VSX: Mag: 10.0-15.5 | P: 0.1000-1.0000 d | Type: RRAB | Spec: G2V | Raggio: 5°
```

## Parametri VSX API

### Riferimenti Documentazione

- **VSX API Docs**: https://www.aavso.org/apis-aavso-resources
- **Direct Web Query**: https://www.aavso.org/direct-web-query-vsxvsp
- **VSX Search Interface**: https://vsx.aavso.org/vsx/index.php?view=search.top

### Parametri Supportati

| Parametro | Tipo | Descrizione | Esempio |
|-----------|------|-------------|---------|
| `coords` | string | RA,Dec in gradi | "123.456,45.678" |
| `size` | float | Raggio cone search (gradi) | 5.0 |
| `max_mag` | float | Magnitudine massima | 15.5 |
| `min_mag` | float | Magnitudine minima | 10.0 |
| `period_min` | float | Periodo minimo (giorni) | 0.1 |
| `period_max` | float | Periodo massimo (giorni) | 1.0 |
| `vartype` | string | Tipo variabile (abbreviazione GCVS) | "RRAB", "EA", "DSCT" |
| `spec_type` | string | Classe spettrale | "G2V", "M3III" |
| `num_results` | int | Numero massimo risultati | 100 |

### Abbreviazioni GCVS Comuni

| Nome Completo | Abbreviazione GCVS |
|---------------|--------------------|
| RR Lyrae (ab) | RRAB |
| RR Lyrae (c) | RRC |
| RR Lyrae (d) | RRD |
| Classical Cepheid | DCEP |
| Type II Cepheid | CW |
| Delta Scuti | DSCT |
| SX Phoenicis | SXPHE |
| Mira | M |
| Semi-Regular | SR |
| Eclipsing Algol | EA |
| Eclipsing Beta Lyrae | EB |
| Eclipsing W UMa | EW |

## Workflow Utente

### Scenario 1: Ricerca Automatica con "Copia parametri"

1. Utente carica progetto con stella variabile
2. Esegue analisi periodogramma per ottenere periodo
3. Compila form "Analisi di Supporto" (tipo variabile, classe spettrale)
4. Va al tab "Analisi di Supporto" → sezione "Ricerca Stelle Analoghe VSX"
5. Clicca **"📋 Copia parametri dalla stella corrente"**
6. Sistema auto-popola:
   - Range magnitudine (±1 mag)
   - Range periodo (±10%)
   - Tipo variabile (da form supporto)
   - Classe spettrale (da form supporto)
7. Utente verifica/modifica parametri se necessario
8. Clicca **"🔍 Cerca Analoghe"**
9. Risultati mostrano stelle simili da VSX con score similarità

### Scenario 2: Ricerca Manuale Personalizzata

1. Utente carica progetto
2. Va al tab "Analisi di Supporto" → sezione "Ricerca Stelle Analoghe VSX"
3. Compila manualmente:
   - **Mag Massima**: 15.0
   - **Mag Minima**: 12.0
   - **Periodo Min**: 0.3 d
   - **Periodo Max**: 0.6 d
   - **Tipo Variabile**: RRAB (RR Lyrae tipo ab)
   - **Classe Spettrale**: A-F (stelle di tipo A o F)
4. Clicca **"🔍 Cerca Analoghe"**
5. VSX restituisce solo stelle che matchano **tutti** i criteri specificati

## Vantaggi

1. **Ricerche più mirate**: L'utente può filtrare stelle per caratteristiche fisiche specifiche
2. **Compatibilità con VSX**: Usa parametri standard AAVSO VSX
3. **Flessibilità**: Può usare auto-popolamento o input manuale
4. **Retrocompatibilità**: Se parametri avanzati non specificati, usa comportamento precedente
5. **Cache efficiente**: Cache key include tutti parametri per evitare collisioni

## Testing

### Test Manuale

1. **Test auto-popolamento**:
   - Caricare progetto GAIAID1868255974288176128
   - Eseguire periodogramma
   - Compilare form supporto con tipo "RR Lyrae - RRab"
   - Cliccare "Copia parametri"
   - Verificare popolamento corretto campi

2. **Test ricerca manuale**:
   - Inserire manualmente:
     - Mag: 12.0-15.0
     - Periodo: 0.3-0.6 d
     - Tipo: RRAB
   - Eseguire ricerca
   - Verificare risultati VSX

3. **Test cache**:
   - Eseguire stessa ricerca due volte
   - Verificare "✓ Cache" su secondo risultato

### Comandi Test Backend

```bash
# Test compilazione
python -m py_compile agata/admin/services/variability_analysis.py
python -m py_compile agata/admin/routes/project_detail.py

# Test import
python -c "from agata.admin.services.variability_analysis import query_vsx, trova_stelle_analoghe"
```

## Note Implementative

### Gestione Parametri Opzionali

La funzione `query_vsx()` gestisce parametri opzionali con logica a cascata:

1. **Magnitudine**: Se `max_mag`/`min_mag` specificati → usa quelli, altrimenti `mag ± toleranze`
2. **Periodo**: Se `period_min`/`period_max` specificati → usa quelli, altrimenti `periodo ± toleranze`
3. **Tipo/Classe**: Sempre opzionali, passati solo se specificati

### Calcolo Similarità

Il calcolo similarità è stato aggiornato per gestire componenti opzionali:

```python
dist_components = []

# Magnitudine (se disponibile)
if mag_central is not None and obj_mag > 0:
    dist_components.append(((obj_mag - mag_central) / tol['mag'])**2)

# Periodo (se disponibile)
if periodo_central is not None and obj_period is not None:
    dist_components.append(((obj_period - periodo_central) / period_tolerance)**2)

# Similarità finale
if len(dist_components) > 0:
    dist = np.sqrt(sum(dist_components))
    similarity = 1 / (1 + dist)
else:
    similarity = 0.5  # Score neutro se nessun parametro
```

### Mapping Tipi Variabili

JavaScript include mapping nome completo → abbreviazione GCVS per auto-popolamento:

```javascript
const varTypeMapping = {
    'RR Lyrae - RRab': 'RRAB',
    'Classical Cepheid': 'DCEP',
    'Delta Scuti': 'DSCT',
    'EA': 'EA',
    // ... altri mapping
};
```

## Debug & Troubleshooting

### Browser Console Logging

La funzione `handleSearchAnalogues()` in [variability-comparison.js](../../agata/static/js/variable_stars/variability-comparison.js#L90-L190) implementa logging dettagliato per debug:

**Console Output Example**:
```
[VariabilityComparison]  Search params: topN=10, minMag=[12.5,13.0], maxMag=[14.0,14.5], period=[0.3,0.6], varType=RRAB, specType=A-F
[VariabilityComparison]  📤 Request to API: {periods: Array(3), top_n: 10, min_mag_min: 12.5, ...}
[VariabilityComparison]  📥 Response status: 200 OK
[VariabilityComparison]  ✅ Response data: {analogues: Array(8), analogues_count: 8, ...}
[VariabilityComparison]  📊 Found 8 analogues
```

**Error Logging**:
```
[VariabilityComparison]  ❌ Error response body: {"error": "Project must have coordinates"}
```

**Come Usare**:
1. Apri DevTools (F12) → Console
2. Clicca "Cerca Analoghe"
3. Monitora i log per vedere:
   - Parametri inviati all'API backend
   - Status HTTP della risposta VSX
   - Numero di analoghe trovate
   - Eventuali errori (coordinate mancanti, JSON parsing failed, etc.)

### Errori Comuni

| Errore | Causa | Soluzione |
|--------|-------|-----------|
| "Project must have coordinates" | Progetto senza RA/Dec in DB | Sistema auto-risolve da Gaia DR3; verificare `gaia_id` valido |
| "Expecting value: line 1 column 1 (char 0)" | VSX restituisce HTML invece di JSON | VSX API potrebbe essere down o parametri invalidi; controllare log backend |
| "Nessun periodo trovato" | Periodogramma non eseguito | Eseguire prima l'analisi periodogramma nel tab principale |
| "No analogues found" | Parametri troppo restrittivi o nessuna stella match | Allargare range magnitudine/periodo o rimuovere filtri vartype/spec_type |

## Limitazioni Note

1. **VSX API Limit**: VSX limita a 9999 risultati per query (gestito con `MAX_CANDIDATES = 100`)
2. **No Full-Text Search**: `vartype` e `spec_type` sono match esatti, non supportano wildcards
3. **Cache Invalidation**: Cache per 1h, pulire manualmente se necessario con "Pulisci Cache"
4. **Timeout**: Query VSX ha timeout 30s (configurabile in `requests.get(..., timeout=30)`)
5. **Coordinate Resolution**: Se RA/Dec mancano nel progetto, sistema tenta auto-risoluzione da Gaia DR3; richiede `gaia_id` valido

## Roadmap Futura

- [ ] Aggiungere supporto per wildcards in `vartype` (es: "RR*" per tutti i RR Lyrae)
- [ ] Implementare ricerca multi-catalogo (VSX + Gaia + ASAS-SN) con merge risultati
- [ ] Aggiungere filtro per data ultima osservazione
- [ ] Export risultati ricerca in CSV
- [ ] Visualizzazione light curves analoghe sovrapposte

## Riferimenti

- **VSX API**: https://www.aavso.org/apis-aavso-resources
- **GCVS Variable Types**: https://vsx.aavso.org/index.php?view=about.vartypes
- **AGATA Architecture**: [ARCHITECTURE.md](../ARCHITECTURE.md)
- **Variability Analysis Service**: [agata/admin/services/VARIABILITY_ANALYSIS_README.md](../../agata/admin/services/VARIABILITY_ANALYSIS_README.md)

---

**Autore**: Claude Code AI
**Ultima Modifica**: 2026-02-02
**Branch**: main
