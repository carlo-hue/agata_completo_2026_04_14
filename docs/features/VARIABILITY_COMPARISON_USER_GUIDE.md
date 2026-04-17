# Guida Utente: Analisi Comparativa Stelle Variabili

## Overview

Il nuovo tab **🔍 Analisi Comparativa** nell'editor stelle variabili permette di trovare stelle simili alla tua e confrontare le phased light curves per validare la classificazione.

---

## Workflow Passo-Passo

### Step 1: Carica Progetto dall'Admin

1. Vai nell'**Admin Panel** → **Projects**
2. Apri il **dettaglio progetto** di una stella variabile
3. Clicca sul link "Apri Editor Stelle Variabili" (automaticamente carica i dati)

### Step 2: Esegui Periodogramma

1. Vai al tab **Periodogramma**
2. Imposta range periodo (es. 0.1 - 15 giorni)
3. Abilita **Pre-whitening** per trovare periodi multipli
4. Clicca **Calcola**
5. Annota i top 3 periodi trovati (saranno usati automaticamente)

### Step 3: Ricerca Stelle Analoghe

1. Vai al nuovo tab **🔍 Analisi Comparativa**
2. (Opzionale) Regola tolleranze:
   - **BP-RP**: ±0.15 mag (colore stellare)
   - **Mag**: ±0.5 mag (luminosità)
   - **Teff**: ±300 K (temperatura)
   - **Max Risultati**: 10 (numero stelle da trovare)

3. Clicca **🔍 Cerca Analoghe**

**Cosa succede**:
- Sistema usa periodi dal periodogramma + parametri stella
- Query parallele a **Gaia DR3 Variability**, **VSX (AAVSO)**, **ASAS-SN**
- Risultati ranked per **similarity score** (0-100%)
- Cache Redis: query successive sono istantanee

### Step 4: Visualizza Risultati

Viene mostrata una **tabella interattiva** con:

| Colonna | Descrizione |
|---------|-------------|
| **Checkbox** | Seleziona per confronto (max 3) |
| **Gaia ID / Nome** | Identificativo stella |
| **Catalogo** | Gaia DR3 / VSX |
| **Tipo** | Classificazione variabile (es. DSCT, RR Lyrae) |
| **BP-RP** | Colore |
| **Mag** | Magnitudine |
| **Periodo** | Periodo in giorni (se disponibile) |
| **Similarità** | Score 0-100% (barra colorata) |

**Interpretazione Similarità**:
- 🟢 **>80%**: Stella molto simile
- 🟡 **60-80%**: Stella potenzialmente simile
- ⚫ **<60%**: Stella poco simile

### Step 5: Confronta Phased Light Curves

1. **Seleziona fino a 3 stelle** dalla tabella (checkbox)
2. Clicca **📊 Genera Plot**

**Output**:
- Plot multi-panel (1 panel per stella)
- Asse X: Fase (0-1)
- Asse Y: Flux normalizzato
- **Linea rossa**: Fit Fourier 2nd order
- **Titolo panel**: Label stella + χ² ridotto

**Interpretazione χ²**:
- **χ² < 2**: Buon fit periodico, stella ben caratterizzata
- **χ² 2-5**: Fit moderato, possibile variabilità complessa
- **χ² > 5**: Fit scarso, periodo errato o variabilità irregolare

---

## Esempi Pratici

### Esempio 1: Delta Scuti Variable

**Scenario**: Hai una stella con periodo ~0.12 giorni, BP-RP = 0.35, G = 11.2 mag

**Workflow**:
1. Periodogramma → Trova P = 0.1234 giorni (FAP < 0.001)
2. Analisi Comparativa → Cerca Analoghe
3. **Risultati**: 8 stelle simili, tutte classificate DSCT (δ Scuti)
4. Seleziona top 3 (similarità >85%)
5. Genera Plot → χ² ~1.5 per tutte (buon fit)

**Conclusione**: Conferma classificazione come **Delta Scuti**

### Esempio 2: RR Lyrae

**Scenario**: Stella con P = 0.58 giorni, BP-RP = 0.45, G = 14.5 mag

**Workflow**:
1. Periodogramma → P primario 0.5812 d, P secondario 0.2906 d (alias)
2. Analisi Comparativa → Top risultato: RR Lyrae da VSX (similarità 92%)
3. Plot confronto → χ² = 1.2 (eccellente)

**Conclusione**: RR Lyrae tipo RRab

---

## Tolleranze e Tuning

### Quando Aumentare Tolleranze

**Problema**: Nessuna stella trovata

**Soluzione**:
- Aumenta **Mag** a ±1.0 (include stelle più lontane)
- Aumenta **Teff** a ±500 K (per stelle con dati scarsi)

### Quando Ridurre Tolleranze

**Problema**: Troppe stelle, poco specifiche

**Soluzione**:
- Riduci **BP-RP** a ±0.10 (più selettivo su colore)
- Riduci **Max Risultati** a 5

---

## Cache Management (Solo Admin)

**Quando usare**:
- Nuovi dati importati per la stella
- Periodi aggiornati dopo analisi migliorata
- Test con tolleranze diverse

**Come**:
1. Scroll in fondo al tab Analisi Comparativa
2. Clicca **🧹 Pulisci Cache** (sezione gialla Admin)
3. Conferma

**Effetto**: Prossima ricerca rifarà query live (più lenta ma aggiornata)

---

## Troubleshooting

### Errore: "Nessun periodo trovato"

**Causa**: Periodogramma non eseguito o nessun picco significativo

**Soluzione**:
1. Vai al tab Periodogramma
2. Calcola periodogramma
3. Verifica che ci siano picchi con FAP < 0.01

### Errore: "No lightcurve data for Gaia XXX"

**Causa**: Progetto senza dati fotometrici importati

**Soluzione**:
1. Admin Panel → External Catalogs
2. Importa dati da ASAS-SN o TESS per il Gaia ID
3. Riprova

### Errore: "bp_rp required (not found in Gaia)"

**Causa**: Stella non ha colore BP-RP in Gaia DR3

**Soluzione**:
- Inserisci manualmente BP-RP se noto
- Oppure usa solo VSX (non richiede BP-RP)

### Warning: "Massimo 3 stelle selezionabili"

**Causa**: Plot supporta max 3 panel per leggibilità

**Soluzione**: Deseleziona alcune stelle prima di aggiungerne altre

---

## FAQ

**Q: Quanti periodi vengono usati nella ricerca?**
A: I top 3 periodi dal periodogramma (ordinati per power)

**Q: Posso cercare senza progetto caricato?**
A: No, serve progetto dall'admin con Gaia ID

**Q: Come funziona il ranking similarità?**
A: Distanza euclidea normalizzata su BP-RP, Mag, Teff, Periodo

**Q: I risultati sono cached?**
A: Sì, per 1h in Redis (velocizza ricerche ripetute)

**Q: Posso modificare cataloghi interrogati?**
A: Attualmente Gaia DR3 + VSX. ASAS-SN in roadmap.

---

## Roadmap Features

- [ ] Export tabella analoghe CSV
- [ ] Filter per tipo variabile (solo DSCT, solo RR, etc.)
- [ ] Plot interattivo Plotly invece di PNG statico
- [ ] Cross-match Gaia + VSX + ASAS-SN per validazione
- [ ] Selezione catalogo dati per phased plot (TESS, ZTF, etc.)

---

**Versione**: 1.0.0
**Ultimo aggiornamento**: 2026-01-30
**Supporto**: info@astrogen.it
