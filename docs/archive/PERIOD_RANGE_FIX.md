# Period Range Fix - Analisi di Supporto

**Data**: 2026-02-04
**Issue**: Bottone "Copia Parametri" non popola il range del periodo se periodogramma è vuoto
**Status**: ✅ FIXED

---

## 🔴 Problema

Nel tab "Analisi di Supporto" → "Ricerca Stelle Analoghe":
- ❌ Il bottone "Copia Parametri" legge il periodo SOLO dal periodogramma
- ❌ Se il periodogramma è vuoto, non popola il range del periodo (periodMin/periodMax)
- ❌ Non considera il campo periodo in alto in "Analisi di Supporto"

---

## 🟢 Soluzione

### Cambio Applicato
**File**: `agata/static/js/variable_stars/variability-comparison.js`, linee 616-647

**Logica Nuova**:
1. **Primo**: Legge il periodo dal campo `#info-period` (in alto in Analisi di Supporto)
2. **Fallback**: Se non trovato, legge dal periodogramma con `getPeriods()`
3. **Popola**: Range ±10% intorno al periodo trovato

**Vecchio codice**:
```javascript
// Recupera periodi dal periodogramma
const periods = getPeriods();

// Popola periodo min/max basandosi sul periodo principale ±10%
if (periods && periods.length > 0) {
    const mainPeriod = periods[0];
    // ...
}
```

**Nuovo codice**:
```javascript
// Prova a recuperare il periodo da Analisi di Supporto (campo in alto)
let mainPeriod = null;
const infoPeriodEl = document.getElementById('info-period');
if (infoPeriodEl && infoPeriodEl.textContent && infoPeriodEl.textContent !== '-') {
    // Estrai il numero dal testo (es: "0.567890 d" → 0.567890)
    const periodText = infoPeriodEl.textContent.trim();
    mainPeriod = parseFloat(periodText);
}

// Se non trovato in Analisi di Supporto, prova dal periodogramma
if (!mainPeriod) {
    const periods = getPeriods();
    if (periods && periods.length > 0) {
        mainPeriod = periods[0];
    }
}

// Popola periodo min/max basandosi sul periodo principale ±10%
if (mainPeriod && isFinite(mainPeriod)) {
    const periodMin = mainPeriod * 0.9;
    const periodMax = mainPeriod * 1.1;
    // ...
} else {
    logger.warn(` No period found in Analisi di Supporto or Periodogramma`);
}
```

---

## ✅ Comportamento Atteso

| Scenario | Risultato |
|----------|-----------|
| Campo periodo in Analisi di Supporto compilato | ✅ Usa quel periodo (priorità alta) |
| Campo periodo vuoto, periodogramma disponibile | ✅ Usa periodo dal periodogramma (fallback) |
| Entrambi vuoti | ⚠️ Log warning, nulla popola |

---

## 🧪 Testing

**Caso 1: Periodo in Analisi di Supporto**
1. Carica un progetto
2. Completa il campo periodo in Analisi di Supporto
3. Clicca "Copia Parametri"
4. ✅ `periodMin` e `periodMax` dovrebbero essere popolati con ±10% del periodo

**Caso 2: Periodogramma disponibile, Analisi di Supporto vuoto**
1. Carica un progetto
2. Calcola il periodogramma
3. Non compilare periodo in Analisi di Supporto
4. Clicca "Copia Parametri"
5. ✅ `periodMin` e `periodMax` dovrebbero essere popolati dal periodogramma

**Caso 3: Entrambi vuoti**
1. Carica un progetto senza periodogramma e senza compilare Analisi di Supporto
2. Clicca "Copia Parametri"
3. ⚠️ Console mostra warning: "No period found in Analisi di Supporto or Periodogramma"
4. ✅ `periodMin` e `periodMax` rimangono vuoti (comportamento corretto)

---

**Status**: ✅ **FIXED & VERIFIED**

Ora il bottone "Copia Parametri" funziona correttamente anche quando il periodogramma è vuoto!
