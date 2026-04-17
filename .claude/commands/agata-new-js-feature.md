# AGATA – Nuova Feature JavaScript (ES6 Module)

**Argomenti:** `$ARGUMENTS` = `<modulo> <nome_file_js> "<descrizione feature>"`

Esempio: `/agata-new-js-feature variable_stars spectral_overlay "Overlay classificazione spettrale sul grafico LC"`

---

## Contesto Progetto

**Sistema:** AGATA | ES6 modules, no framework UI

**Pattern JS obbligatorio:** leggi `agata/moduli/variable_stars/static/js/variable_stars/import_catalogs.js`

**Struttura module:** leggi `agata/moduli/variable_stars/static/js/variable_stars/main.js` (come vengono importati)

**Naming convention:** leggi i file in `agata/moduli/variable_stars/static/js/variable_stars/`

---

## Struttura Obbligatoria

### File: `agata/moduli/<modulo>/static/<blueprint_name>/js/<nome_file>.js`

```javascript
/**
 * <NomeFeature> - <Descrizione una riga>
 *
 * <Descrizione dettagliata: cosa fa, quali API usa, dipendenze>
 *
 * API Endpoints:
 * - METHOD /percorso/endpoint - Descrizione
 *
 * Dependencies:
 * - state.js (se usa state globale)
 * - plots.js (se usa grafici)
 */

import { state } from './state.js';  // solo se necessario

/**
 * Inizializza la feature. Chiamata da main.js.
 * @param {Object} options - Opzioni configurazione
 */
export function init<NomeFeature>(options = {}) {
  console.log('[<NomeFeature>] Module initialized');
  // setup event listeners, wiring
}

// Funzioni esportate pubbliche (usate da altri moduli)
export function <pubblica>() { ... }

// Funzioni private (non esportate)
async function _<privata>() { ... }

// Handlers globali (solo se richiamate da HTML onclick=)
window.<handlerGlobale> = async function() { ... };
```

### Modifica `main.js`:

Aggiungi import e chiamata init:

```javascript
import { init<NomeFeature> } from './<nome_file>.js';
// ... alla fine, dopo altri init:
init<NomeFeature>();
```

---

## Regole Non Negoziabili

- ES6 modules: usa `import`/`export`, non `var` globali (eccetto handlers `window.xxx` per HTML onclick)
- **Nessun calcolo scientifico in JS** (regola fondamentale AGATA)
- Async/await per tutte le chiamate API (non `.then()` chains)
- Gestione errori: `try/catch` su ogni `fetch()`, mai swallowing silenzioso
- `console.log('[<NomeModulo>] ...')` per debug (prefix per identificare sorgente)
- Status feedback: aggiorna UI per ogni stato (loading, success, error) — mai lasciare l'utente senza feedback
- `const` per variabili che non cambiano, `let` per quelle che cambiano

---

## Pattern Fetch Obbligatorio

```javascript
async function _callApi(endpoint, body) {
  try {
    const resp = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.error || `HTTP ${resp.status}`);
    }
    return await resp.json();
  } catch (e) {
    console.error('[<NomeModulo>] API error:', e);
    throw e;
  }
}
```

---

## Output Atteso

1. File JS completo con JSDoc, export, init function
2. Modifica a `main.js` (import + init call)
3. Se necessari nuovi elementi HTML: snippet da aggiungere al template
4. Se necessaria una nuova route API: note con riferimento a `/agata-new-route`
5. Checklist:
   - [ ] Nessun calcolo scientifico in JS
   - [ ] Async/await (non .then chains)
   - [ ] Try/catch su ogni fetch
   - [ ] Inizializzazione in main.js
   - [ ] Prefisso console.log per identificazione
   - [ ] JSDoc completo su funzioni pubbliche
