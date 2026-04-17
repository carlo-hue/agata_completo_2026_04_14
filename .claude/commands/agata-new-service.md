# AGATA – Nuova Funzione/Service Puro

**Argomenti:** `$ARGUMENTS` = `<modulo> <file_service> "<descrizione funzione>"`

Esempio: `/agata-new-service field_star_map gaia_service "Cross-match coordinate con catalogo Gaia DR3"`

---

## Contesto Progetto

**Sistema:** AGATA | Python puro, no Flask nei services

**Gold standard servizi:** leggi `agata/moduli/field_star_map/services/gaia_service.py`

**Regola fondamentale:** services = logica scientifica pura, testabile senza Flask.

---

## Requisiti Obbligatori

### Struttura funzione/service:

- `from __future__ import annotations`
- `from dataclasses import dataclass` per ogni input/output complesso
- `import logging; logger = logging.getLogger(__name__)`
- **ZERO import Flask** (no `request`, no `jsonify`, no `current_app`)
- Timeout per API esterne: `int(os.getenv("XXXX_TIMEOUT_SECONDS", "20"))`
- Retry configurabile: `int(os.getenv("XXXX_RETRIES", "2"))`
- Exception custom per errori specifici del dominio (es. `GaiaQueryError`)
- Docstring con: responsabilità, input (tipo + unità), output (tipo + unità), eccezioni sollevate

### Se usa astropy (obbligatorio per calcoli astronomici):

- Coordinate: `SkyCoord` con `frame='icrs'`
- Unità: sempre esplicite (`u.deg`, `u.arcsec`, etc.)
- Mai reimplementare calcoli astronomici standard

### Se usa API esterna:

- Retry con backoff (vedi pattern `_launch_job_with_retry` in gaia_service.py)
- Exception wrapping: eccezioni esterne → eccezione custom del modulo
- Log warning su ogni retry tentato

---

## Anti-Pattern Vietati

- `from flask import ...` in qualsiasi punto del service
- Accesso a `request`, `session`, `g` Flask
- Calcoli scientifici reinventati invece di astropy
- Eccezioni inghiottite senza log (`except: pass`)
- Ritornare dict non tipizzato quando una dataclass è appropriata

---

## Output Atteso

1. Dataclass/i di input e output (se applicabile)
2. Funzione completa con docstring, signature tipizzata, implementazione
3. Exception class custom (se nuovo dominio di errore)
4. Come chiamarla dalla route corrispondente (2-3 righe di esempio)
5. Checklist:
   - [ ] Nessun import Flask
   - [ ] Dataclass per I/O complesso
   - [ ] Timeout espliciti per API esterne
   - [ ] Testabile con `python -c "from agata.moduli... import ..."`
   - [ ] Docstring completo con input/output/eccezioni
