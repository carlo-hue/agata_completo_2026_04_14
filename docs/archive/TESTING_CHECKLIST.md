# Testing Checklist - Sincronizzazione Periodo/Ampiezza/Epoch

**Data**: 2026-02-04
**Versione**: 1.16.1
**Componenti Testati**: Variable Stars Editor - Tab Analisi in Fase & Analisi di Supporto

---

## 🎯 Obiettivo Test

Verificare che:
1. Tutti i 4 tab carichino correttamente i dati
2. I grafici vengono renderizzati in ogni tab
3. Il bottone di sincronizzazione funziona correttamente
4. I valori di periodo, ampiezza ed epoch vengono sincronizzati dal tab "Analisi in Fase" al tab "Analisi di Supporto"

---

## 📋 Pre-requisiti

- [ ] Progetto Variable Stars caricato nell'editor
- [ ] Browser console aperta (F12) per verificare errori
- [ ] Almeno una stella con dati di curva di luce disponibile

---

## 🔍 Test 1: Caricamento Progetto

**Scenario**: Carica un progetto dal pannello admin

### Step:
1. [ ] Accedi al pannello admin dei Variable Stars
2. [ ] Seleziona/Apri un progetto con dati storici
3. [ ] Verifica che appaia il messaggio "Caricato ✅" nella sezione stato

**Risultato Atteso**:
- [ ] Non ci sono errori nella console browser
- [ ] Il messaggio di caricamento appare correttamente
- [ ] I dati sono disponibili nel browser DevTools (window.state)

---

## 🌙 Test 2: Tab "Curva di Luce"

**Scenario**: Verifica che il primo tab mostri il grafico della curva di luce

### Step:
1. [ ] Il tab "Curva di Luce" è attivo per default
2. [ ] Clicca sul tab per assicurarti che sia selezionato
3. [ ] Verifica che il grafico sia visibile dentro `#plotLC`

**Risultato Atteso**:
- [ ] Grafico Plotly renderizzato con punti osservativi
- [ ] Asse X: JD (Julian Date)
- [ ] Asse Y: Magnitudine
- [ ] Nessun errore in console

---

## 📊 Test 3: Tab "Periodogramma"

**Scenario**: Calcola il periodogramma e verifica il grafico

### Step:
1. [ ] Clicca sul tab "Periodogramma"
2. [ ] Imposta Min P. = 0.1, Max P. = 15 (valori default)
3. [ ] (Opzionale) Abilita "Pre-w." (Prewhitening) e seleziona "3" periodi
4. [ ] Clicca il bottone "Calcola"
5. [ ] Attendi che il calcolo termini (observa la console)
6. [ ] Verifica che il grafico del periodogramma sia visibile
7. [ ] Verifica che i picchi principali siano selezionabili

**Risultato Atteso**:
- [ ] Grafico Plotly renderizzato con picchi di potenza
- [ ] Pulsante "Calcola" cambia stato durante il calcolo
- [ ] Nella sezione "peaks" appare una lista di periodi candidati
- [ ] Nessun errore in console

---

## 🔄 Test 4: Tab "Analisi in Fase"

**Scenario**: Carica un periodo e verifica il folding della curva di luce

### Step:
1. [ ] Clicca sul tab "Analisi in Fase"
2. [ ] Verifica che il campo `#chosenP` (Periodo) sia vuoto o contenga un valore
3. [ ] (Da Periodogramma) Se hai calcolato un periodo, dovrebbe essere disponibile
4. [ ] Se il periodo è vuoto, inserisci manualmente un valore (es: 0.57)
5. [ ] Clicca il bottone "Aggiorna" nella sezione Phase Controls
6. [ ] Attendi il rendering del grafico di fase

**Risultato Atteso**:
- [ ] Grafico di fase (folded light curve) renderizzato dentro `#plotPhase`
- [ ] Punti osservativi distribuiti lungo 0-2 cicli di fase
- [ ] Nessun errore in console
- [ ] Due barre orizzontali (min e max) visibili sul grafico per selezionare l'ampiezza manuale

**Verifiche Aggiuntive**:
- [ ] Usa il cursore "Fine-tuning" per regolare il periodo
- [ ] Sposta lo slider di fase per centrare il minimo/massimo
- [ ] Verifica che il bottone "✓ 100%" sia disponibile per il sampling finale

---

## 🎯 Test 5: Sincronizzazione Bottone (CRITICAL)

**Scenario**: Sincronizza periodo, ampiezza ed epoch dal tab "Analisi in Fase" al tab "Analisi di Supporto"

### Step 5.1: Prepara i dati nel tab "Analisi in Fase"
1. [ ] Assicurati di essere nel tab "Analisi in Fase"
2. [ ] Inserisci un valore periodo (es: 0.567890) in `#chosenP`
3. [ ] Aggiorna il grafico cliccando "Aggiorna"
4. [ ] Trascina il cursore superiore della fase per impostare il massimo (ampiezza)
5. [ ] Trascina il cursore inferiore della fase per impostare il minimo
6. [ ] Verifica che `window.phaseAnalysisState.manualAmplitude.min` e `.max` siano valorizzati
   - Apri console: `console.log(window.phaseAnalysisState.manualAmplitude)`

**Risultato Atteso**:
- [ ] I cursori (barre) si muovono sul grafico di fase
- [ ] L'ampiezza calcolata è `Math.abs(max - min)` (valore positivo)
- [ ] L'epoch è memorizzato in `window.phaseAnalysisState.epoch`

### Step 5.2: Sincronizza al tab "Analisi di Supporto"
1. [ ] Vai al tab "Analisi di Supporto" (📊 tab)
2. [ ] Nella sezione "📍 Informazioni Base" trova il bottone 🔄 accanto a "Periodo (dall'analisi in fase):"
3. [ ] Clicca il bottone 🔄

**Risultato Atteso**:
- [ ] Il bottone diventa **verde** e mostra ✅ 3 (significa 3 campi sincronizzati)
- [ ] Dopo 1.5 secondi, il bottone torna al colore originale
- [ ] I tre campi seguenti si aggiornano con sfondo verde (#d4edda):
  - [ ] `#info-period`: mostra il periodo formattato (es: "0.567890 d")
  - [ ] `#variability_amplitude`: input compilato con l'ampiezza
  - [ ] `#epoch`: input compilato con l'epoch JD

**Se il sincronismo fallisce**:
- [ ] Il bottone diventa **rosso** e mostra ❌
- [ ] Nessun campo viene aggiornato
- [ ] Controlla console per errori

---

## 📍 Test 6: Informazioni Base Tab "Analisi di Supporto"

**Scenario**: Verifica che le info base vengano caricate correttamente

### Step:
1. [ ] Sei nel tab "Analisi di Supporto"
2. [ ] Scorri fino alla sezione "📍 Informazioni Base"
3. [ ] Verifica i campi seguenti:

**Campi Attesi**:
- [ ] Nome Progetto: (es: "MyProject_RRLyrae")
- [ ] Gaia ID: (es: "Gaia DR3 1234567890")
- [ ] Coordinate (RA, Dec): (es: "12:34:56.7 +45:32:10.0")
- [ ] Periodo (dall'analisi in fase): "-" o valore sincronizzato
- [ ] Bottone 🔄: deve essere visibile a destra del campo Periodo

**Risultato Atteso**:
- [ ] Tutti i campi sono leggibili
- [ ] Il bottone è allineato a destra (non sotto)
- [ ] Nessun overflow di testo

---

## 🔬 Test 7: Form Parametri Fisici

**Scenario**: Compila il form con dati fisici della stella

### Step:
1. [ ] Nella sezione "🔬 Parametri Fisici Stella" compila almeno:
   - [ ] Ampiezza Variabilità (mag): (es: 0.5)
   - [ ] Passband: (es: V)
   - [ ] Epoch (JD): (sincronizzato dal bottone 🔄)
2. [ ] Opzionalmente compila altri parametri:
   - [ ] Classe Spettrale
   - [ ] Teff
   - [ ] Distanza
   - [ ] Etc.
3. [ ] Clicca "💾 Salva Dati"

**Risultato Atteso**:
- [ ] Il bottone "Salva" mostra feedback (es: "Salvato ✅")
- [ ] I dati vengono persistiti (ricaricando la pagina, rimangono)
- [ ] Nessun errore in console

---

## 🔄 Test 8: Tab "Analisi di Supporto" (Completo)

**Scenario**: Verifica tutte le sezioni del tab di supporto

### Sezioni da Verificare:
1. [ ] **Informazioni Base**: progetti, Gaia ID, coordinate, periodo + bottone sync
2. [ ] **Parametri Fisici**: form editabile con campi compilabili
3. [ ] **Validazione con Knowledge Base**:
   - [ ] Zona query (textarea) per domande
   - [ ] 4 bottoni suggerimenti colorati
   - [ ] Bottone "Chiedi a KB"
4. [ ] **Ricerca Stelle Analoghe VSX**: (collassabile)
   - [ ] Sezione ricerca stella analoghe
   - [ ] Parametri: Max Risultati, Magnitudine, Periodo
   - [ ] Bottone "🔍 Cerca Analoghe"

**Risultato Atteso**:
- [ ] Tutti gli elementi sono visibili e ben formattati
- [ ] Nessun errore di CSS o layout
- [ ] Sezioni collassabili si espandono/collassano correttamente

---

## 🐛 Test 9: Verifica Errori in Console

**Scenario**: Controlla che non ci siano errori JavaScript durante tutte le operazioni

### Step:
1. [ ] Apri F12 (DevTools)
2. [ ] Vai alla tab "Console"
3. [ ] Ripeti tutti i test precedenti
4. [ ] Osserva la console per:
   - [ ] **Errori rossi** (❌ non dovrebbero esserci)
   - [ ] **Warning gialli** (⚠️ alcuni possono essere normali)
   - [ ] **Log info** (ℹ️ di debug - ok)

**Errori Critici da Evitare**:
- [ ] "Cannot read properties of null"
- [ ] "undefined is not a function"
- [ ] "Uncaught SyntaxError"

**Errori Attesi (possono ignorarsi)**:
- [ ] Warning su CORS (se risorse esterne)
- [ ] Warning su deprecated APIs

---

## 📊 Test 10: Verifica Grafica Complessiva

**Scenario**: Controlla il rendering grafico di tutti i 4 tab

| Tab | Grafico Atteso | Elemento ID |
|-----|---|---|
| Curva di Luce | Scatter plot con punti | `#plotLC` |
| Periodogramma | Power spectrum con picchi | `#plotPeriod` |
| Analisi in Fase | Folded light curve | `#plotPhase` |
| Analisi di Supporto | (no grafico) Form + Info | `#tab-comparison` |

**Step**:
1. [ ] Per ogni tab con grafico, verifica:
   - [ ] Il contenitore `div` è visibile
   - [ ] Plotly ha renderizzato i dati (visibile il grafico)
   - [ ] Assi e etichette sono chiari
   - [ ] Legenda (se presente) è leggibile

**Risultato Atteso**:
- [ ] Tutti i grafici sono visibili
- [ ] Nessun grafico è "vuoto" o mostra "undefined"

---

## 🎨 Test 11: CSS Bottone Sincronizzazione

**Scenario**: Verifica lo stile del bottone di sincronizzazione

### Step:
1. [ ] Vai al tab "Analisi di Supporto"
2. [ ] Posiziona il mouse sopra il bottone 🔄 accanto al periodo
3. [ ] Clicca il bottone

**Risultato Atteso**:
- [ ] Bottone è **blu** (`#3b82f6`) per default
- [ ] Al hover: diventa **blu scuro** (`#2563eb`) + leggero sollevamento (shadow)
- [ ] Al click: cambio temporaneo a **verde** (`#10b981`) con ✅ + numero
- [ ] Se errore: cambio a **rosso** (`#ef4444`) con ❌
- [ ] Dopo 1.5s: torna al colore originale
- [ ] Dimensioni: piccole e compatte (6px padding, 13px font)

---

## 🔧 Test 12: Browser DevTools Diagnostics

**Scenario**: Verifica variabili JavaScript globali

### Step (Console Browser):
```javascript
// Controlla lo state globale
console.log(window.phaseAnalysisState);

// Controlla l'ampiezza manuale
console.log(window.phaseAnalysisState.manualAmplitude);

// Controlla l'epoch
console.log(window.phaseAnalysisState.epoch);

// Controlla il periodo scelto
console.log(document.getElementById('chosenP').value);

// Controlla i campi sincronizzati
console.log(document.getElementById('variability_amplitude').value);
console.log(document.getElementById('epoch').value);
```

**Risultato Atteso**:
- [ ] `window.phaseAnalysisState` è un oggetto con proprietà
- [ ] `manualAmplitude` ha `.min` e `.max` valorizzati dopo aver mosso i cursori
- [ ] `epoch` è un numero (JD)
- [ ] Dopo click bottone sync: i tre input HTML sono compilati

---

## 📝 Summary Risultati

Compila questa sezione alla fine del test:

| Test | Status | Note |
|------|--------|------|
| 1. Caricamento Progetto | ⬜ TODO | |
| 2. Tab Curva di Luce | ⬜ TODO | |
| 3. Tab Periodogramma | ⬜ TODO | |
| 4. Tab Analisi in Fase | ⬜ TODO | |
| 5. Sincronizzazione Bottone | ⬜ TODO | **CRITICAL** |
| 6. Informazioni Base | ⬜ TODO | |
| 7. Form Parametri Fisici | ⬜ TODO | |
| 8. Tab Analisi di Supporto (Completo) | ⬜ TODO | |
| 9. Errori Console | ⬜ TODO | |
| 10. Grafica Complessiva | ⬜ TODO | |
| 11. CSS Bottone | ⬜ TODO | |
| 12. DevTools Diagnostics | ⬜ TODO | |

---

## ✅ Test Superato?

- [ ] **SÌ** - Tutti i test sono PASS ✅
- [ ] **NO** - Alcuni test sono FAIL ❌ (vedi Note sotto)

### Note Fallimenti:
```
[Descrivi qui eventuali problemi riscontrati]
```

---

## 📞 Contatti / Escalation

Se trovi errori critici:
1. Cattura screenshot
2. Copia l'errore dalla console
3. Annota i step per riprodurre
4. Contatta il team di sviluppo

---

**Data Completamento**: ___________
**Tester**: ___________
**Feedback**: ___________
