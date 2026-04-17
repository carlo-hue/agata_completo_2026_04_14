# AGATA – Fix Bug (Targeted)

**Argomenti:** `$ARGUMENTS` = Descrizione libera del bug (traceback, sintomo, file sospetto)

Esempio: `/agata-fix-bug "KeyError 'g_mag' in field_star_map/routes.py line 103 quando stella non ha fotometria Gaia"`

---

## Contesto Progetto

**Sistema:** AGATA | Fix minimo, nessun refactor non richiesto

---

## Processo

### Fase 1 – Diagnosi (prima di toccare codice):

1. Leggi il file/funzione indicata nel bug report
2. Identifica la causa radice (non il sintomo)
3. Verifica se il bug può essere in un service (logica) o in una route (validazione)
4. Controlla se esiste un pattern di gestione errori simile altrove nel modulo

### Fase 2 – Fix:

- Fix minimale: modifica solo il necessario
- Non riscrivere funzioni che funzionano
- Non introdurre nuove dipendenze per risolvere un edge case
- Se la causa è in un service: fix nel service. Se è in una route: fix nella route
- Aggiungi log (`logger.warning(...)`) se il bug era silenzioso

### Fase 3 – Verifica:

- Il fix non cambia l'API/signature
- Il fix non introduce regressioni nei casi normali
- Il fix rispetta i confini architetturali (nessuna logica scientifica nelle route, nessun Flask nei services)

---

## Regole Non Negoziabili

- **NO refactor non richiesto:** non "migliorare" codice funzionante mentre correggi il bug
- **NO cambi a signature o API** esistenti senza motivo esplicito
- Se il fix richiede una modifica al DB: segnalarlo separatamente (non eseguire)
- Se il bug è architetturale (logica scientifica in route, ecc.): segnalarlo come issue separata, non correggere silenziosamente

---

## Output Atteso

1. Causa radice identificata (1-2 frasi)
2. Fix puntuale (solo il codice modificato, non l'intero file)
3. Spiegazione di perché questo fix è corretto e non causa regressioni
4. Checklist:
   - [ ] Fix minimale (nessun refactor non richiesto)
   - [ ] Causa radice identificata (non solo sintomo)
   - [ ] API/signature invariata
   - [ ] Confini architetturali rispettati
   - [ ] Log aggiunto se bug era silenzioso
