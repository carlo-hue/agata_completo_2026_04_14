# AGATA – Architecture Mapping

**Documento:** ARCHITECTURE_MAP.md  
**Sistema:** AGATA  
**Versione:** v1.0  
**Data:** 2026-01-20  
**Stato:** Allineamento struttura ↔ architettura  
**Dipende da:** ARCHITECTURE.md

---

## Scopo del documento

Questo documento **mappa l’architettura normativa definita in ARCHITECTURE.md**
sulla **struttura reale del repository**.

- NON introduce nuove regole
- NON ridefinisce principi
- NON sostituisce ARCHITECTURE.md
- NON documenta il dettaglio implementativo

Serve a:
- orientarsi nel codice
- verificare la conformità architetturale
- fornire contesto stabile per sviluppo e revisione

---

## Root package

Il repository è organizzato come **monorepo applicativo** Python,
con separazione netta tra:
- backend amministrativo
- dominio scientifico
- frontend interattivo

File root rilevanti:
- `db.py` → inizializzazione e accesso DB
- `models.py` → modelli condivisi di base
- `__init__.py` → bootstrap del package

---

## Mappatura Macro-Aree

### admin/

**Ruolo architetturale:**  
Area di **governo applicativo** e controllo.

**Sottostruttura:**
- `admin/routes/`  
  - route Flask amministrative
  - orchestrazione delle azioni
  - validazione input/output
- `admin/services/`  
  - logica amministrativa
  - policy di stato
  - audit e statistiche
- `admin/commands/`  
  - comandi di dominio (azioni atomiche)
  - transizioni di stato esplicite
- `admin/decorators.py`  
  - enforcement di permessi e policy

**Note di conformità:**
- contiene business logic **amministrativa**
- è autorità sullo stato dei progetti
- NON contiene logica scientifica

---

### auth/

**Ruolo architetturale:**  
Gestione identità e accesso.

**Sottostruttura:**
- `auth/routes.py`  
  - endpoint di autenticazione
- `auth/decorators.py`  
  - controllo accessi
- `auth/email_service.py`  
  - invio email (magic link)
- `auth/magic_link.py`  
  - gestione token temporanei
- `auth/oauth_providers.py`  
  - integrazione OAuth

**Note di conformità:**
- isolato dal dominio scientifico
- nessuna dipendenza dai servizi scientifici

---

### auth_models/

**Ruolo architetturale:**  
Modelli persistenti e di dominio condivisi.

**Contenuto:**
- modelli ORM per:
  - utenti e sessioni
  - progetti e stati
  - audit log
  - associazioni
  - catalog import
  - integrazioni Slack

**Note di conformità:**
- puri modelli dati
- nessuna logica applicativa complessa
- utilizzati trasversalmente da admin, auth e services

---

### services/

**Ruolo architetturale:**  
**Cuore scientifico e computazionale del sistema.**

**Sottostruttura:**
- `services/data_loader*.py`  
  - caricamento e normalizzazione dati
- `services/db_loader.py`  
  - persistenza dati scientifici
- `services/ephemeris_exoplanets.py`  
  - calcoli astronomici deterministici
- `services/synthetic*.py`  
  - generazione dati sintetici
- `services/external_catalogs/`  
  - adattatori verso sorgenti esterne
  - es. `gaia_resolver.py`

**Note di conformità:**
- codice indipendente da Flask
- nessuna dipendenza da UI
- funzioni riutilizzabili e testabili
- **tutta la logica scientifica di base vive qui**

---

### admin/routes/catalogs/

**Ruolo architetturale:**  
Adattatori amministrativi verso cataloghi esterni.

**Sottostruttura:**
- `ztf.py`
- `tess.py`
- `ogle.py`
- `asassn.py`
- `file_upload*.py`
- `common.py`

**Note di conformità:**
- orchestrano import e validazione
- NON contengono algoritmi scientifici
- delegano ai services per l’elaborazione

---

### variable_stars/

**Ruolo architetturale:**  
Pipeline scientifica per l’analisi delle stelle variabili.

**Sottostruttura:**
- `variable_stars/routes/`  
  - endpoint specifici del dominio
  - orchestrazione delle analisi
- `variable_stars/services/`  
  - servizi di dominio:
    - `peak_detection.py`
    - `statistics.py`
    - `arrow_parser.py`
    - `llm_client.py`
- `variable_stars/constants.py`  
  - costanti di dominio
- `STRUCTURE.md`  
  - documentazione interna di modulo

**Note di conformità:**
- NON ridefinisce algoritmi di base già in services/
- coordina e compone servizi
- valida coerenza scientifica
- supporta AI advisor come strumento ausiliario

---

### static/js/variable_stars/

**Ruolo architetturale:**  
Frontend di analisi interattiva.

**Contenuto:**
- moduli JS per:
  - analisi periodi
  - fasi
  - O–C
  - plotting
  - stato UI
  - esportazioni

**Note di conformità:**
- nessuna logica scientifica autoritativa
- nessuna decisione di dominio
- puro supporto esplorativo

---

### templates/

**Ruolo architetturale:**  
Rendering UI server-side.

**Sottostruttura:**
- `templates/admin/`
- `templates/variable_stars/`
- `templates/exoplanets/`

**Note di conformità:**
- presentazione
- nessuna logica di dominio

---

### exoplanets/

**Ruolo architetturale:**  
Modulo scientifico verticale dedicato agli esopianeti.

**Contenuto:**
- `routes.py`
- workflow documentato (`workflow_exoclock.md`)
- generatori dati di test

**Note di conformità:**
- segue le stesse regole di variable_stars
- usa services/ per la logica di base

---

## Eccezioni dichiarate

Le seguenti componenti sono **eccezioni consapevoli** alle regole generali:

- `variable_stars/services/llm_client.py`  
  Motivo: integrazione esterna LLM  
  Nota: non è logica scientifica deterministica

- `static/js/variable_stars/ai-advisor.js`  
  Motivo: supporto esplorativo AI  
  Nota: non è sorgente di verità

---

## Conformità complessiva

Lo stato attuale del repository è:

- **coerente** con ARCHITECTURE.md
- correttamente separato per responsabilità
- estendibile senza violare i confini definiti

Ogni nuova funzionalità deve:
- dichiarare la macro-area coinvolta
- rispettare la separazione dei concerns
- non introdurre logica scientifica fuori da services/
