# Quick Debug Guide - Sincronizzazione Fase/Supporto

## 🔧 Troubleshooting rapido

### Problema: Bottone non clicca
```javascript
// Console: verificare che il bottone esista
document.getElementById('sync-phase-to-support')
// Dovrebbe tornare: <button type="button" id="sync-phase-to-support" ...>

// Se null: il template non è caricato o id è sbagliato
```

### Problema: Bottone clicca ma non sincronizza
```javascript
// Console: verificare che window.phaseAnalysisState esista
console.log(window.phaseAnalysisState);
// Dovrebbe tornare: { n: ..., jd: [...], mag: [...], ... }

// Se undefined: main.js non ha eseguito l'export
// Soluzione: ricarica la pagina
```

### Problema: Periodo non viene sincronizzato
```javascript
// Console: verificare il valore del campo periodo
document.getElementById('chosenP').value
// Dovrebbe tornare: un numero (es: "0.567890")

// Se vuoto (""): inserisci un valore nel campo Analisi in Fase
// Se errore: il campo non esiste (verificare template HTML)
```

### Problema: Ampiezza non viene sincronizzata
```javascript
// Console: verificare le barre manuali
console.log(window.phaseAnalysisState.manualAmplitude);
// Dovrebbe tornare: { min: number, max: number }

// Se null/undefined: non hai trascinato i cursori nel grafico di fase
// Soluzione: nel tab Analisi in Fase, trascina i cursori sopra e sotto

// Se non è un object: il tab Analisi in Fase non è stato renderizzato
// Soluzione: clicca il tab e attendi il rendering
```

### Problema: Epoch non viene sincronizzato
```javascript
// Console: verificare l'epoch
console.log(window.phaseAnalysisState.epoch);
// Dovrebbe tornare: un numero (es: 2459000.123)

// Se null/undefined: il tab Analisi in Fase non ha calcolato l'epoch
// Soluzione: clicca "Aggiorna" nel tab Analisi in Fase
```

### Problema: Bottone diventa rosso (❌)
```javascript
// Significa: almeno uno dei tre campi non è stato sincronizzato

// Console: esegui manualmente la sincronizzazione
window.syncPhaseToSupport();

// E poi controlla quali campi mancano:
console.log(document.getElementById('chosenP').value);          // periodo
console.log(window.phaseAnalysisState.manualAmplitude);        // ampiezza
console.log(window.phaseAnalysisState.epoch);                  // epoch
```

### Problema: Campi sincronizzati non restano verdi
```javascript
// Il verde (#d4edda) è un feedback visivo temporaneo
// Sparisce dopo pochi secondi (è normale)

// Per verificare che i dati siano rimasti:
console.log(document.getElementById('variability_amplitude').value);
console.log(document.getElementById('epoch').value);
// I valori dovrebbero essere ancora lì (il colore è solo feedback)
```

---

## 🎯 Checklist di Debug Minimo

Se il bottone non funziona, esegui in console questi comandi in ordine:

```javascript
// 1. Bottone esiste?
if (document.getElementById('sync-phase-to-support')) {
    console.log('✅ Bottone trovato');
} else {
    console.log('❌ Bottone non trovato - Template issue');
}

// 2. State esiste?
if (window.phaseAnalysisState) {
    console.log('✅ State globale presente');
} else {
    console.log('❌ State non esportato - main.js issue');
}

// 3. Periodo ha valore?
const p = document.getElementById('chosenP')?.value;
if (p && parseFloat(p) > 0) {
    console.log(`✅ Periodo ok: ${p}`);
} else {
    console.log('❌ Periodo vuoto o invalido');
}

// 4. Ampiezza ha valore?
const amp = window.phaseAnalysisState?.manualAmplitude;
if (amp?.min !== null && amp?.max !== null) {
    console.log(`✅ Ampiezza ok: min=${amp.min}, max=${amp.max}`);
} else {
    console.log('❌ Ampiezza non inizializzata');
}

// 5. Epoch ha valore?
const ep = window.phaseAnalysisState?.epoch;
if (ep !== null && ep !== undefined) {
    console.log(`✅ Epoch ok: ${ep}`);
} else {
    console.log('❌ Epoch non inizializzato');
}

// 6. Se tutto ok, clicca il bottone
if (window.syncPhaseToSupport) {
    console.log('✅ Funzione sync disponibile');
    window.syncPhaseToSupport(); // <-- esegui sync manualmente
} else {
    console.log('❌ Funzione sync non esportata');
}
```

---

## 📍 Posizioni nel Codice

Se devi modificare qualcosa:

| Cosa | File | Righe | Nota |
|------|------|-------|------|
| HTML Bottone | agata/templates/variable_stars/index.html | 564-572 | Cerca `sync-phase-to-support` |
| CSS Bottone | agata/static/css/variable_stars.css | 432-461 | Cerca `.btn-sync-small` |
| Event Listener | agata/static/js/variable_stars/support-analysis.js | 29-52 | Nel metodo `initSupportAnalysis()` |
| Funzione Sync | agata/static/js/variable_stars/support-analysis.js | 586-648 | Funzione `syncPhaseToSupport()` |
| State Export | agata/static/js/variable_stars/main.js | 1004-1008 | Riga finale del file |
| Bug Fix Save | agata/static/js/variable_stars/main.js | 431-445 | Nel handler `saveFileBtn.onclick` |

---

## 🔍 Console Logging Aggiuntivo

Per aggiungere logging dettagliato durante il click:

```javascript
// Aggiungi temporaneamente in syncPhaseToSupport() dopo riga 587:
console.log('[DEBUG] syncPhaseToSupport() called');
console.log('[DEBUG] chosenP =', chosenP);
console.log('[DEBUG] manualAmplitude =', manualAmplitude);
console.log('[DEBUG] epoch =', epoch);
console.log('[DEBUG] syncCount =', syncCount);
```

---

## 🎨 Verifica Visuale

Se il bottone non appare nel posto giusto:

```javascript
// Console: ispeziona il layout
const btn = document.getElementById('sync-phase-to-support');
if (btn) {
    console.log('Position:', btn.getBoundingClientRect());
    console.log('Parent:', btn.parentElement.className);
    console.log('Style:', window.getComputedStyle(btn));
}
```

---

## 💾 Reset dello State (se bloccato)

Se sei bloccato e vuoi un reset:

```javascript
// Ricrea lo state da zero
window.phaseAnalysisState = {
    n: 0,
    jd: [],
    mag: [],
    manualAmplitude: { min: null, max: null },
    epoch: null
};

// Oppure ricarica la pagina
location.reload();
```

---

## 🚨 Errori Comuni

| Errore | Causa | Soluzione |
|--------|-------|-----------|
| `Cannot read properties of null (reading 'value')` | Campo input non esiste | Verificare id elemento HTML |
| `syncPhaseToSupport is not defined` | Funzione non esportata | Verificare `window.syncPhaseToSupport = ...` in support-analysis.js |
| Bottone non clicca | Event listener non attaccato | Verificare `addEventListener('click', syncPhaseToSupport)` |
| Niente cambia | State non inizializzato | Ricaricare pagina / attendere rendering |
| Colore bottone sbagliato | CSS non caricato | Verificare `variable_stars.css` è incluso nel template |

---

## 📱 Testing Mobile

Se testi su mobile:

```javascript
// Tocco potrebbe essere lento, aggiungi feedback:
const btn = document.getElementById('sync-phase-to-support');
btn.addEventListener('touchstart', () => btn.style.opacity = '0.7');
btn.addEventListener('touchend', () => btn.style.opacity = '1');
```

---

## 🔐 Verificare Integrità Dati

Dopo sincronizzazione, verifica i dati:

```javascript
// Tutti e tre i campi dovrebbero avere valori
const period = document.getElementById('info-period').textContent;
const amplitude = document.getElementById('variability_amplitude').value;
const epoch = document.getElementById('epoch').value;

console.log('Period:', period);        // es: "0.567890 d"
console.log('Amplitude:', amplitude);  // es: "0.542"
console.log('Epoch:', epoch);          // es: "2459000.12345"

// Se tutti hanno valore: ✅ SUCCESSO
if (period !== '-' && amplitude && epoch) {
    console.log('✅ Sincronizzazione completata');
} else {
    console.log('❌ Sincronizzazione incompleta');
}
```

---

## 📞 Escalation

Se il problema persiste dopo questi step:

1. Copia gli output della console
2. Screenshot del tab (mostra il bottone)
3. Descrivi i step che hai fatto
4. Fornisci al team di sviluppo

---

**Last Updated**: 2026-02-04
**Version**: 1.16.1
