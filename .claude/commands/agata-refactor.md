# AGATA – Refactor Controllato (Behavior-Preserving)

**Argomenti:** `$ARGUMENTS` = `<file_o_modulo> "<motivo del refactor>"`

Esempio: `/agata-refactor agata/moduli/admin/routes/catalogs/tess.py "Duplicazione logica timeout con asassn.py, estrarre helper comune"`

---

## Contesto Progetto

**Sistema:** AGATA | Refactor = comportamento invariato, API invariata

---

## Regole Obbligatorie Prima di Iniziare

1. Leggi l'intero file target (e i file correlati se il refactor coinvolge interfaces)
2. Identifica esattamente cosa cambia e cosa NON cambia
3. Elenca le API pubbliche (funzioni/route/endpoint) che devono restare identiche
4. Verifica che il motivo del refactor sia uno di: duplicazione, leggibilità, testabilità, performance

---

## Vincoli Assoluti

- Output/comportamento identico prima e dopo
- Signature delle funzioni pubbliche invariata
- Nessuna nuova dipendenza esterna
- HTTP status codes invariati per le route
- Nessun cambio al DB schema come effetto collaterale

---

## Pattern di Refactor AGATA Comuni

### Estrazione funzione da route → service (legittimo):

Se codice in una route contiene logica che appartiene a un service, spostarlo.

Verifica: la funzione estratta ha zero import Flask.

### De-duplicazione servizi:

Se due catalogs hanno lo stesso helper, estrarre in `catalog_common_service.py`.

Verifica: tutti i caller aggiornati.

### Pulizia import:

Rimuovere import non usati, consolidare import dello stesso modulo.

---

## Output Atteso

1. Lista di cosa cambia (con file e righe)
2. Lista di cosa non cambia (API invariate)
3. Codice refactorizzato (solo le sezioni modificate se il file è lungo)
4. Se il refactor sposta logica tra file: entrambi i file modificati
5. Checklist:
   - [ ] Comportamento identico
   - [ ] Signature pubbliche invariate
   - [ ] Nessuna nuova dipendenza
   - [ ] HTTP status codes invariati (se route)
   - [ ] Tutti i caller aggiornati (se sposto funzione)
