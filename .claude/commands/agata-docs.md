# AGATA – Crea Documentazione

**Argomenti:** `$ARGUMENTS` = Nome del documento o feature da documentare

Esempio: `/agata-docs "VAST WCS flow"` oppure `/agata-docs "nuovo modulo spectroscopy"`

---

## Regola Fondamentale: NESSUN FILE .md in ROOT

**Tutti i file di documentazione vanno in `docs/`, MAI nella root del progetto.**

| Tipo di documento | Dove va |
|-------------------|---------|
| Feature non triviale | `docs/features/<nome>.md` |
| Feature VAST | `docs/features/vast/<nome>.md` |
| Note operative / session notes | `docs/archive/<nome>.md` |
| Architettura o design | `docs/<NOME>.md` |
| Auth / sicurezza | `docs/auth/<nome>.md` |
| Performance / ottimizzazione | `docs/performance/<nome>.md` |

**Non creare mai file come:**
- `FEATURE_COMPLETE.md` (root)
- `SESSION_XX_SUMMARY.md` (root)
- `BUG_FIX_NOTES.md` (root)

---

## Processo

### 1. Scegli il percorso corretto

- Feature nuova non triviale → `docs/features/<nome>.md`
- Sotto-feature VAST → `docs/features/vast/<nome>.md`
- Nota operativa temporanea (sync, deploy one-off) → `docs/archive/<nome>.md`
- Documento normativo / architettura → `docs/<NOME>.md`

### 2. Struttura del documento

```markdown
# Titolo Feature

**Data**: YYYY-MM-DD
**Status**: ✅ Complete / 🚧 In Progress

## Overview
Breve descrizione (2-3 frasi).

## Come funziona
Dettaglio tecnico.

## File coinvolti
- `path/to/file.py` – descrizione
```

### 3. Aggiorna l'indice

Dopo aver creato il documento, aggiungi un riferimento in `docs/INDEX.md` nella sezione appropriata.

---

## Output Atteso

1. File creato nel percorso corretto sotto `docs/`
2. Riferimento aggiunto in `docs/INDEX.md`
3. Conferma che la root del progetto non contiene nuovi file `.md`
