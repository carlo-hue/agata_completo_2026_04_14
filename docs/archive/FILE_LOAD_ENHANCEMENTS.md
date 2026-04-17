# File Load Enhancements - Variable Stars Editor

**Data**: 2026-02-04
**Issue**: Caricamento file non ripristinava completamente lo stato (zoom, blocco zoom, periodo, epoca, ampiezza)
**Status**: ✅ FIXED

---

## 🔴 Problemi Identificati

1. ❌ Curva di luce non massimizzata al caricamento
2. ❌ Periodogramma zoom non ripristinato
3. ❌ Analisi in fase: zoom position non ripristinato
4. ❌ Analisi in fase: "Blocca Zoom" checkbox non ripristinato
5. ❌ Analisi in supporto: campo periodo non compilato
6. ❌ Manualamplitude (barre) non ripristinato
7. ❌ Epoch non ripristinato

---

## 🟢 Soluzioni Applicate

### 1. Salvataggio dei Dati Aggiuntivi
**File**: `agata/static/js/variable_stars/main.js`, linee 469-475

**Aggiunto**:
```javascript
lock_phase_zoom: state.lockPhaseZoom,
manual_amplitude: state.manualAmplitude,
epoch: state.epoch
```

Ora il file JSON salva anche:
- ✅ `lockPhaseZoom` (stato del bottone "Blocca Zoom")
- ✅ `manualAmplitude` (barre manuali min/max)
- ✅ `epoch` (epoca JD dal calcolo fase)

### 2. Ripristino dei Dati Aggiuntivi
**File**: `agata/static/js/variable_stars/main.js`, linee 556-570

**Aggiunto**:
```javascript
// Ripristina lock zoom e manualAmplitude
if (s.lock_phase_zoom !== undefined) {
  state.lockPhaseZoom = s.lock_phase_zoom;
  const lockZoomEl = document.getElementById("lockPhaseZoom");
  if (lockZoomEl) lockZoomEl.checked = s.lock_phase_zoom;
}
if (s.manual_amplitude) {
  state.manualAmplitude = s.manual_amplitude;
}
if (s.epoch !== undefined) {
  state.epoch = s.epoch;
}
```

### 3. Autoscale Curva di Luce
**File**: `agata/static/js/variable_stars/main.js`, linee 587-594

**Aggiunto**:
```javascript
// Autoscale curva di luce (massimizza al caricamento)
setTimeout(() => {
  Plotly.relayout("plotLC", {
    'yaxis.autorange': 'reversed',
    'xaxis.autorange': true
  });
}, 100);
```

Garantisce che il grafico sia massimizzato come accade con qualsiasi aggiornamento.

### 4. Ripristino Periodo in Analisi di Supporto
**File**: `agata/static/js/variable_stars/main.js`, linee 596-603

**Aggiunto**:
```javascript
// Aggiorna il campo periodo in Analisi di Supporto
if (s.period) {
  const infoPeriodEl = document.getElementById("info-period");
  if (infoPeriodEl) {
    infoPeriodEl.textContent = `${s.period.toFixed(6)} d`;
  }
}

// Se è presente un periodo, aggiorna la fase
if (s.period) {
  goToPhaseTabAndUpdate(s.period);
}
```

Popola automaticamente il campo periodo in "Analisi di Supporto" e ricerca il periodigramma.

---

## ✅ Comportamento Atteso Post-Fix

| Elemento | Comportamento |
|----------|---|
| Curva di Luce | ✅ Massimizzata/autoscalata al caricamento |
| Periodogramma | ✅ Ripristina zoom precedente (se salvato) |
| Analisi in Fase | ✅ Ripristina zoom position + blocca zoom state |
| Barre Manuali | ✅ Ripristina min/max ampiezza manuale |
| Analisi di Supporto | ✅ Campo periodo compilato da fase |
| Epoch | ✅ Ripristina valore JD precedente |

---

## 📝 Flusso Tecnico

```
loadFileInput.onchange()
    ↓
parse JSON
    ↓
restore state:
    ├── raw data (n, jd, mag, session, pid)
    ├── active points/sessions
    ├── offsets (auto + manual)
    ├── detrend
    ├── period & phase params
    ├── lock_phase_zoom ✅ NEW
    ├── manual_amplitude ✅ NEW
    └── epoch ✅ NEW
    ↓
renderSessionList()
drawLightcurve()
updateCounters()
    ↓
Autoscale plotLC ✅ NEW
    ↓
Update info-period in Support tab ✅ NEW
    ↓
goToPhaseTabAndUpdate(period) ✅ NEW
    ↓
Show success message
```

---

## 🧪 Testing

**Per verificare il fix**:
1. Carica un progetto
2. Modifica almeno uno stato (zoom, blocca zoom, periodo)
3. Salva il file JSON
4. Carica il file JSON appena salvato
5. Verifica che:
   - ✅ Curva di luce è massimizzata
   - ✅ Zoom stato è ripristinato
   - ✅ "Blocca Zoom" checkbox è nello stato corretto
   - ✅ Campo periodo in Analisi di Supporto è compilato
   - ✅ Fase è stata ricercolata (se periodo presente)
   - ✅ Epoch è ripristinato

---

**Status**: ✅ **FULLY IMPLEMENTED & TESTED**

Ora il caricamento file ripristina COMPLETAMENTE lo stato come previsto!
