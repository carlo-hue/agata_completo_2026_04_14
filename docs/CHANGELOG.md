# AGATA – Changelog Storico

**Data compilazione**: 2026-03-25
**Fonte**: `git log --all` (tutti i commit dalla nascita del progetto)
**Uso**: Documento di riferimento per capire l'evoluzione del progetto, pianificare refactor, orientare nuovi collaboratori.

---

## Indice Rapido

| Era | Periodo | Tema principale |
|-----|---------|-----------------|
| [Prototipo Flask](#era-0--prototipo-flask-apr-dic-2025) | Apr–Dic 2025 | Nascita, auth Microsoft, APOD, effemeridi, editor curve |
| [v1.0–v1.8](#era-1--editor-curve-di-luce-dic-2025--gen-2026) | Dic 2025 – Gen 2026 | Editor curve di luce, sessioni, sigma-clipping, fase |
| [v1.9–v1.12](#era-2--analisi-in-fase--struttura-modulare-gen-2026) | Gen 2026 | Analisi in fase, esopianeti (bozza), autenticazione Google, catalogo stelle |
| [v1.13–v1.19](#era-3--cataloghi-esterni--vast-automation-gen-feb-2026) | Gen–Feb 2026 | TESS/ASAS-SN import, VAST photometry pipeline, field star map |
| [v1.20–v1.23](#era-4--reingegnerizzazione-catalogo--galassie-nane-feb-2026) | Feb 2026 | Nuovo catalogo stelle, galassie nane, decomposizione |
| [v2.0–v2.3](#era-5--deploy-automation--architettura-v20-feb-mar-2026) | Feb–Mar 2026 | Deploy automation, versione dinamica, ASAS-SN tab, barre ΔT |
| [v2.4–v2.9](#era-6--ux-analisi-variabili--tess-bulk-import-mar-2026) | Mar 2026 | Session navigator, Slack integration, TESS bulk import, pre-whitening |
| [v2.10–v2.14.10](#era-7--qualità-e-consolidamento-mar-2026) | Mar–Apr 2026 | Phase preview, tutorial, vendor assets, UX Analisi Supporto, rimozione Redis, AI Advisor unificato KB |
| [v3.0.0–v3.0.6](#era-8--timeescaledb--postgresql-migration-mar-apr-2026) | Apr 2026 | TimescaleDB hypertable optimization, PostgreSQL migration, eliminazione TESS curl entries, dynamic n_freq, closed projects, catalog DB cache UI |

---

## Era 0 – Prototipo Flask (Apr–Dic 2025)

### Aprile 2025 – Nascita del progetto

| Data | Commit | Descrizione |
|------|--------|-------------|
| 2025-04-15 | `Initial commit` | Prima versione, struttura Flask base |
| 2025-04-16 | `versione base` | Layout iniziale |
| 2025-04-18 | `Aggiunta autenticazione Microsoft` | Primo sistema auth (Microsoft OAuth, poi sostituito con Google) |

### Luglio 2025 – Funzionalità astronomiche primordiali

| Data | Commit | Descrizione |
|------|--------|-------------|
| 2025-07-07 | `aggiunto apod` | APOD (Astronomy Picture of the Day) – feature visuale |
| 2025-07-12 | `foto serata` | Gallery foto serata osservativa |
| 2025-07-28 | `effemeridi v1` | Prima implementazione effemeridi planetarie |
| 2025-07-28 | `gestione ora pianeti` | Orari pianeti, cartella dati |
| 2025-08-02 | `pop up iscrizioni canali` | Gestione canali notifica |

### Dicembre 2025 – Nascita dell'editor curve di luce

| Data | Commit | Descrizione |
|------|--------|-------------|
| 2025-12-14 | `prima versione che funzionicchia` | Primissimo prototipo editor curve |
| 2025-12-19 | `prima versione buona partendo da zero` | Riscrittura completa, grafica a pannelli |
| 2025-12-19 | `modificato i colori delle sessioni` | Colori per sessione su curva e fase |
| 2025-12-21 | `sessioni con nome modificabile` | Sessioni named, titolo grafico fase modificabile |
| 2025-12-21 | `salvataggio su file completo` | Export progetto su file |
| 2025-12-21 | `opzioni salvataggio, FAP, shift-click` | FAP (False Alarm Probability), range [-1,1] |
| 2025-12-22 | `armoniche, oc e nuova funzione sintetica` | O-C diagram, fit armonico, curva sintetica |
| 2025-12-22 | `detrend`, `caricamento da DB`, `css` | Detrend automatico, caricamento dati DB per Gaia ID |
| 2025-12-23 | `zero point e grafica v1.0` | Zero-point fotometrico, refactoring grafica |
| 2025-12-24 | `v1.1 – sigma clipping e shift-click su phase` | Sigma clipping iterativo, interazione click su fase |
| 2025-12-24 | `v1.1.1`, `v1.1.2` | Statistiche curva in fase, multiplot fase |
| 2025-12-27–31 | `v2.0.0beta – v2.1.0beta` | Sperimentazione layer system avanzato (poi abbandonata in favore del branch stabile) |

---

## Era 1 – Editor Curve di Luce (Dic 2025 – Gen 2026)

**Tema**: Consolidamento editor, analisi periodale, import da DB.

### v1.9.x (Gen 2026)

| Versione | Data | Descrizione |
|----------|------|-------------|
| v1.9.0 | 2026-01-03 | Nuova struttura modulare + bozza modulo esopianeti |
| v1.9.1 | 2026-01-04 | Esopianeti bozza, phase control separati |
| v1.9.2 | 2026-01-10 | Refactor: rimosso ui-bridge, introdotto sessions/period files |
| v1.9.3 | — | Ampiezza sessioni |
| v1.9.4 | — | Align zero funzionante, phase plot con titolo Gaia ID |
| v1.9.5 | — | Export: bottone effemeridi centra su min/max |
| v1.9.6 | 2026-01-12 | **Periodogramma multi-periodo con pre-whitening** |
| v1.9.7 | 2026-01-12 | **AI Advisor** (prima implementazione, Claude/Cerebras) |
| v1.9.8 | — | Refactoring routes |
| v1.9.9 | 2026-01-13 | Blocca zoom in fase |

### v1.10.x (Gen 2026)

| Versione | Data | Descrizione |
|----------|------|-------------|
| v1.10.1 | 2026-01-13 | **Autenticazione Google OAuth 2.0** (sostituisce Microsoft) |
| v1.10.2 | — | Ampiezza manuale, ricalcolo e bug fix |
| v1.10.3 | — | Estensione amministrazione |
| v1.10.4 | — | Cancellazioni associazioni |

---

## Era 2 – Analisi in Fase + Struttura Modulare (Gen 2026)

**Tema**: Potenziamento analisi, gestione progetti, catalogo stelle.

### v1.11.x (Gen 2026)

| Versione | Data | Descrizione |
|----------|------|-------------|
| v1.11.0 | 2026-01-16 | **Catalogo stelle** – prima implementazione |
| v1.11.1 | 2026-01-16 | Assegnazione lavorazione progetti, workflow review |
| v1.11.2 | — | Account mail generica, invio mail ad assegnazione |
| v1.11.3 | 2026-01-18 | Slack opzionale per associazione |
| v1.11.4 | 2026-01-18 | Upload da file |

### v1.12.x (Gen 2026)

| Versione | Data | Descrizione |
|----------|------|-------------|
| v1.12.8 | 2026-01-26 | Logica editor usa `project_id` anziché `gaia_id` |
| v1.12.9 | 2026-01-26 | Bug fixing filtri cataloghi e apertura editor |
| v1.12.9.1 | 2026-01-26 | Bug fixing import e associazione |
| v1.12.9.2 | 2026-01-26 | Vista compatta (work in progress) |

---

## Era 3 – Cataloghi Esterni + VAST Automation (Gen–Feb 2026)

**Tema**: Integrazione cataloghi esterni (TESS, ASAS-SN), fotometria VAST, field star map.

### v1.13.x – v1.15.x (Gen–Feb 2026)

| Versione | Data | Descrizione |
|----------|------|-------------|
| v1.13.0 | 2026-01-29 | **Import TESS QLP tramite Gaia ID** |
| v1.13.1 | 2026-01-29 | Caricamento dati da ASAS-SN |
| v1.14.0 | 2026-01-30 | Analisi comparativa + coordinate Gaia nel progetto |
| v1.15.0 | 2026-02-02 | Analisi comparativa basata su mail Otero (VSX) |
| v1.15.1 | 2026-02-02 | Documenti riorganizzati |

### v1.16.x (Feb 2026)

| Versione | Data | Descrizione |
|----------|------|-------------|
| v1.16.0 | 2026-02-02 | **Analisi di Supporto con documento VSX** |
| v1.16.1 | 2026-02-03 | Ricerca VSX correlati |
| v1.16.2 | 2026-02-04 | Ricarica valori da analisi in fase, bug salvataggio progetto |
| v1.16.3 | 2026-02-04 | Invio Slack: periodogramma, fase e dettagli |
| v1.16.4 | 2026-02-06 | Invio a review da editor con info blocco |

### v1.17.x – v1.19.x (Feb 2026) – VAST Pipeline

| Versione | Data | Descrizione |
|----------|------|-------------|
| v1.17.0 | 2026-02-09 | **VAST Import** – fotometria automatizzata da FITS |
| v1.17.1 | 2026-02-10 | VAST caricamento senza rilanciare pipeline |
| v1.17.2 | 2026-02-11 | Bug fixing VAST e gestione magnitudini |
| v1.18.0 | 2026-02-13 | Ricerca cataloghi e import da editor |
| v1.18.1 | 2026-02-13 | Copia valori da catalogo |
| v1.18.2 | 2026-02-13 | Bug cache catalogo |
| v1.18.3 | 2026-02-13 | Ricerca per ZTF ID, performance catalogo |
| v1.18.4 | 2026-02-13 | Query optimization |
| v1.18.5 | 2026-02-15 | Cancellazione stelle da catalogo |
| v1.18.6 | 2026-02-15 | VAST import: dettagli e modalità minimal |
| v1.18.7 | 2026-02-15 | VAST import: retry Gaia match |
| v1.19.0 | 2026-02-16 | **Field Star Map standalone** – nuovo modulo autonomo |
| v1.19.1 | 2026-02-16 | Bug import VAST ricerca Gaia |
| v1.19.2 | 2026-02-16 | Cancellazione import VAST, check distanza-magnitudine |
| v1.19.3 | 2026-02-17 | VAST: recupero Gaia (bug fix) |
| v1.19.4 | 2026-02-17 | VAST: Gaia import bug |
| v1.19.5 | 2026-02-17 | VAST: import manuale Gaia |
| v1.19.6 | 2026-02-17 | VAST: bug import manuale |
| v1.19.7 | 2026-02-17 | Filtro catalogo per stelle non note |
| v1.19.8 | 2026-02-18 | Check performance DB |

---

## Era 4 – Reingegnerizzazione Catalogo + Galassie Nane (Feb 2026)

**Tema**: Nuovo schema tabella stars, galassie nane, decomposizione, field map in editor.

### v1.20.x (Feb 2026)

| Versione | Data | Descrizione |
|----------|------|-------------|
| v1.20.0 | 2026-02-20 | **Reingegnerizzazione catalogo** – nuova tabella `agata_stars` |
| v1.20.1 | 2026-02-20 | Bug catalogo, badge QLP già caricati |
| v1.20.2 | 2026-02-20 | Import ZTF con check cataloghi esistenti |
| v1.20.3 | 2026-02-20 | Togliere punti da analisi in fase + conteggio punti tolti |
| v1.20.4 | 2026-02-20 | Salvataggio progetto: nome migliore + ZIP |
| v1.20.5 | 2026-02-20 | Bug Cerebras LLM aggiornato |
| v1.20.6 | 2026-02-20 | Rimosso catalogo ATLAS da VAST |
| v1.20.7 | 2026-02-20 | Promozione VAST per singola candidata |
| v1.20.8 | 2026-02-20 | Check promozione VAST se stelle già presenti |
| v1.20.9 | 2026-02-20 | VAST import: bug coordinate Gaia troppo lunghe a Vizier |
| v1.20.10 | 2026-02-20 | VAST: sempre coordinate per check Gaia |

### v1.21.x – v1.23.x (Feb 2026)

| Versione | Data | Descrizione |
|----------|------|-------------|
| v1.21.0 | 2026-02-20 | **Field Map nell'editor** – mappa stelle integrata nell'editor |
| v1.21.1 | 2026-02-20 | Documentazione |
| v1.22.0 | 2026-02-20 | **Decomposizione su editor** – analisi Fourier interattiva |
| v1.22.1 | 2026-02-22 | Creazione progetti con ID cancellati in precedenza |
| v1.22.2 | 2026-02-22 | Editor gestisce progetti senza dati fotometrici |
| v1.23.0 | 2026-02-23 | **Galassie Nane** – nuovo modulo con RBAC |
| v1.23.1 | 2026-02-24 | Bug import in produzione su worker |
| v1.23.2 | 2026-02-24 | Cancellazione job falliti e file associati |
| v1.23.3 | 2026-02-24 | Rinominato da `Cataloghi_esterni` a `agata_star_photometry` |
| v1.23.4 | 2026-02-24 | Link galassie nane e field star map su admin |
| v1.23.5 | 2026-02-24 | Bug caricamento da file di progetto non esistente |

---

## Era 5 – Deploy Automation + Architettura v2.0 (Feb–Mar 2026)

**Tema**: Deploy unificato con script automatico, versione dinamica, pulizia architetturale.

### v2.0.x (Feb–Mar 2026)

| Versione | Data | Descrizione |
|----------|------|-------------|
| v2.0.0 | 2026-02-28 | **Deploy automation** (`scripts/deploy.sh`) + versione dinamica `{{ app_version }}` |
| v2.0.1 | 2026-03-02 | Preserva chart tool mode (zoom/select) dopo delete punti |

> **Note v2.0.0**: primo script deploy unificato (10 step automatici: backup, push, pull, SQL, pip, restart). Skeema integrato per schema diffing (poi rimosso in v2.14.2 per semplicità).

### v2.1.x – v2.3.x (Mar 2026)

| Versione | Data | Descrizione |
|----------|------|-------------|
| v2.1.0 | 2026-03-02 | **ASAS-SN nel tab Import Cataloghi** |
| v2.1.1 | 2026-03-06 | Bug import ASAS-SN |
| v2.2.0 | 2026-03-06 | Audit architetturale fase 1 – fix strutturali |
| v2.3.0 | 2026-03-07 | **Barre verticali draggabili ΔT** + rescaling asse X |
| v2.3.1 | 2026-03-07 | Fix canali Slack, superuser self-association |
| v2.3.2 | 2026-03-07 | Fix filtro stars-catalog `assigned` |

---

## Era 6 – UX Analisi Variabili + TESS Bulk Import (Mar 2026)

**Tema**: Session navigator, Slack integration, catalogo avanzato, TESS/ZTF pipelines.

### v2.4.x – v2.6.x (Mar 2026)

| Versione | Data | Descrizione |
|----------|------|-------------|
| v2.4.0 | 2026-03-07 | **Session Navigator** con smart sigma-clip zoom |
| v2.5.1 | 2026-03-08 | Session navigator improvements + fix zoom |
| v2.6.0 | 2026-03-08 | **Periodogramma per-sessione** con layout a due colonne |
| v2.6.1 | 2026-03-08 | Fix barre ΔT rispettano zoom sessione attiva |
| v2.6.2 | 2026-03-08 | Fix ASAS-SN fallback, ZTF TAP dispatcher, Cerebras |

### v2.7.x (Mar 2026) – Slack + Import CSV + Allineamento

| Versione | Data | Descrizione |
|----------|------|-------------|
| v2.7.0 | 2026-03-09 | **Bottone Allinea a Riferimento** con modale sessione/magnitudine |
| v2.7.1 | 2026-03-09 | Fix JD₀ intero su asse X |
| v2.7.2 | 2026-03-09 | Fix Lomb-Scargle: detrend lineare, cap baseline/3, picchi locali |
| v2.7.3 | 2026-03-10 | Barre ΔMag, zoom stabile su delete, periodogramma unificato |
| v2.7.4 | 2026-03-10 | **Import da file CSV** nel tab Import Cataloghi |
| v2.7.5 | 2026-03-10 | Link ASAS-SN SkyPatrol con istruzioni |
| v2.7.6 | 2026-03-10 | Tab bar compatta con bottone collapse |
| v2.7.7 | 2026-03-10 | **Bottone Slack** su curva di luce: PNG + riepilogo sessioni |
| v2.7.8 | 2026-03-10 | Fix: crea thread Slack dopo promote-to-available |
| v2.7.9 | 2026-03-10 | Fix: PNG upload curva di luce Slack |
| v2.7.10 | 2026-03-10 | Aggiunge ΔT e ΔMag al messaggio Slack |
| v2.7.11 | 2026-03-10 | **Nuovo flusso ASAS-SN** via LB endpoint + selezione bande |
| v2.7.12 | 2026-03-11 | Salva Vista Compatta, navigazione sessione e barre ΔT/ΔMag nel ZIP |
| v2.7.13 | 2026-03-11 | Refactor `field_star_map` – nuovo blueprint `mappe_stelle`, tab embedded |
| v2.7.14 | 2026-03-11 | Fix Vista Compatta: sessioni non più sovrapposte |

### v2.8.x (Mar 2026) – Help Online + RBAC Superuser

| Versione | Data | Descrizione |
|----------|------|-------------|
| v2.8.0 | 2026-03-11 | **Restrizioni ruolo superuser** + assegnazione progetto al superuser |
| v2.8.1 | 2026-03-12 | **Modulo Help online** con bottoni contestuali ed editor inline (superadmin) |
| v2.8.2 | 2026-03-12 | Espansione e correzione file help |
| v2.8.3 | 2026-03-12 | Help Visualizzazione separato da Curva di Luce |
| v2.8.4 | 2026-03-13 | Box Epoch JD₀ con slider/bottoni, centra su min/max, reset slider periodo |

### v2.9.x (Mar 2026) – TESS/ZTF Bulk Pipelines

| Versione | Data | Descrizione |
|----------|------|-------------|
| v2.9.0 | 2026-03-14 | **Riorganizzazione modulare completa** (gold standard field_star_map) |
| v2.9.1 | 2026-03-15 | Semplificazione filtri catalogo stelle |
| v2.9.2 | 2026-03-15 | **TESS Bulk Import Pipeline** – state machine completa |
| v2.9.3 | 2026-03-15 | Coordinate J2000 e magnitudine V in Analisi di Supporto |
| v2.9.4 | 2026-03-15 | Fix TESS bulk import: MySQL server gone away |
| v2.9.5 | 2026-03-15 | **TESS Bulk Import checkpoint/resume** – ripresa da interruzione |
| v2.9.6 | 2026-03-16 | ZTF Survey: miglioramenti UI e fix pipeline promozione |
| v2.9.7 | 2026-03-16 | Cifre significative periodo/epoch + Dec.P/Dec.E + state save |
| v2.9.8 | 2026-03-17 | **Coordinate J2000 editabili con correzione proper motion** (astropy) |
| v2.9.9 | 2026-03-18 | **Pre-whitening Fourier N-armoniche** nel periodogramma |

---

## Era 7 – Qualità e Consolidamento (Mar 2026)

**Tema**: Phase preview, tutorial interattivo, vendor assets, cleanup codice.

### v2.10.x – v2.11.x (Mar 2026)

| Versione | Data | Descrizione |
|----------|------|-------------|
| v2.10.0 | 2026-03-20 | **Phase preview inline** nel periodogramma + pulizia decomposition/OC |
| v2.10.1 | 2026-03-20 | Fix phase preview: filtra sessioni correttamente |
| v2.11.0 | 2026-03-20 | **Saved queries e preset query** nel catalogo stelle |
| v2.11.1 | 2026-03-20 | Fix performance TESS bulk import job detail |
| v2.11.2 | 2026-03-20 | **Refactor architetturale**: migrazione `agata/services/` → nei moduli |
| v2.11.3 | 2026-03-20 | Fix progress Gaia cross-match in ZTF survey job detail |
| v2.11.4 | 2026-03-20 | Deduplicazione Gaia ID nel ZTF Survey (`is_duplicate`) |

### v2.12.x – v2.14.x (Mar 2026)

| Versione | Data | Descrizione |
|----------|------|-------------|
| v2.12.0 | 2026-03-21 | **Login page redesign** + slash commands sistema prompt AGATA |
| v2.12.1 | 2026-03-21 | Fix Google OAuth: forza selezione account (`prompt=select_account`) |
| v2.13.0 | 2026-03-21 | **Preview lightcurve** da job pipeline (ZTF/TESS/VAST) |
| v2.13.1 | 2026-03-23 | Fix: Plotly load, sidebar icons, docs cleanup |
| v2.14.0 | 2026-03-23 | **Tutorial interattivo** analisi stelle variabili |
| v2.14.1 | 2026-03-23 | **Vendor JS/CSS locali** per ogni modulo (no CDN esterni) |
| v2.14.2 | 2026-03-23 | Rimozione import inutilizzati, codice morto e ridondanze |
| v2.14.3 | 2026-03-24 | Sigma clipping: checkbox sessione integrato nel contatore punti |
| v2.14.4 | 2026-03-25 | Fix scroll tab (Periodogramma, Analisi Supporto, Cataloghi); Field Star Map a tutta altezza; modal import catalogo compatto; fix cache key analoghe VSX (multi-tenant) |
| v2.14.5 | 2026-03-25 | Rimozione Flask-Caching/Redis (sovraingegneria); fix validazione ricerca analoghe (accetta range periodo/magnitudine) |
| v2.14.6 | 2026-03-25 | UX Analisi di Supporto: ricerca analoghe VSX aperta di default e spostata prima della KB; bottone "Copia da Stella" accanto a "Cerca Analoghe"; KB collassabile; rimossa funzione confronto phased LC (incompleta) |
| v2.14.7 | 2026-03-27 | **AI Advisor unificato con KB**: nuovo endpoint `analyze-with-kb` (superuser); consolidate 3 sezioni KB separate nel tab AI Advisor; ricerca semantica stelle analoghe GrAGVar (rating≥8) con immagini Teams inline (phase plot, periodogramma, TPF); guida LLM compilazione template AAVSO; stelle analoghe identificate con Gaia DR3 ID; dati completi stella dalla KB (Teff, distanza, luminosità, BP-RP, cataloghi) passati al prompt |
| v2.14.8 | 2026-03-27 | Fix produzione AI Advisor: modello sentence-transformers pre-caricato su prod (PermissionError `/var/www/.cache`); testo "AGATA sta analizzando" (era "Claude") |
| v2.14.9 | 2026-03-27 | **Metrica qualità fase + Raffina Periodo automatico**: String Length (SL) e PDM in tempo reale sull'analisi in fase; pulsante "Raffina P" scansiona P±N×ΔP e trova il minimo SL; grafico paesaggio SL nel box centrale; layout pannello fase riorganizzato a 3 colonne (Periodo, Raffina P, Epoch+Sampling); fix periodogramma combinato (cards picchi + preview fase affiancate, FAP >99 formattato `<10⁻⁹⁹`) |
| v2.14.10 | 2026-04-11 | **TPF modulo** – analisi dati TPF completa; **Script Library TESS** – upload .sh/.zip/.7z una volta, riuso batch multipli senza re-upload, auto-offset tracking, support estrazione archivi, parsing URL migliorato (virgolette doppie/singole), batch naming leggibile |

---

## Era 8 – TimescaleDB + PostgreSQL Migration (Mar–Apr 2026)

**Tema**: Ottimizzazione hypertable, migration MySQL→PostgreSQL, eliminazione tabelle ridondanti.

### v2.15.x (Mar 2026) – Phase 3 TimescaleDB Optimization

| Versione | Data | Descrizione |
|----------|------|-------------|
| v2.15.0 | 2026-03-28 | **Phase 3 TimescaleDB optimization** – 5 hypertable, 3 continuous agg (cagg), on-demand refresh |
| v2.15.1 | 2026-03-28 | TESS import cagg refresh post-job completion (< 100ms) |
| v2.15.2 | 2026-04-01 | Monitoring cagg e job summaries denormalizzati |

### v3.0.0 (Apr 2026) – PostgreSQL Migration Complete

| Versione | Data | Descrizione |
|----------|------|-------------|
| v3.0.0 | 2026-04-11 | **PostgreSQL migration da MySQL** – 1.76M rows migrate, type casting, FK ordering, zero downtime |
| v3.0.1 | 2026-04-11 | Production deployment: PostgreSQL live, MySQL backup-only |

### v3.0.x – Elimina TESS Curl Entries + Job Code Improvement (Apr 2026)

| Versione | Data | Descrizione |
|----------|------|-------------|
| v3.0.2 | 2026-04-12 | **Eliminazione `agata_tess_curl_entries`** tabella (18 GB reduction) – entries lette on-demand da file |
| — | — | Job code format: da `TESTIMPORT-YYYY-NNNNN` (casuale) a `TESS_IMPORT-S{sector}-{progressivo}` |
| — | — | Fix bug project period loading (JS null check su `chosenP` elemento) |
| v3.0.3 | 2026-04-13 | **Deploy automation per SQL migrations** – `migrate-prod.sh` script con credenziali remote via SSH |
| — | — | Aggiornato CLAUDE.md con procedura migration manuale |
| v3.0.4 | 2026-04-13 | **Dynamic n_freq control nel periodogramma** con auto-suggerimento Horne-Baliunas (frequenza Nyquist adattiva) |
| v3.0.5 | 2026-04-13 | **Progetti chiusi nel catalogo stelle** con visual distinction (badge, opacità, disabilitato drag-drop) |
| v3.0.6 | 2026-04-13 | **Tab cataloghi: auto-load da DB cache** – `GET /api/db-attributes` endpoint, caricamento istantaneo senza query Vizier, layout compatto con separatori per contesto |

---

## Feature Map – Dove sono nate le cose

| Feature | Prima apparizione | Versione matura |
|---------|------------------|-----------------|
| Autenticazione | v1.0 (Microsoft) | v1.10.1 (Google OAuth) |
| Editor curve di luce | Dic 2025 | v2.7.x |
| Periodogramma Lomb-Scargle | v1.9.6 | v2.9.9 (pre-whitening N-armoniche) |
| Analisi in fase | v1.1 (sigma clip) | v2.10.0 (phase preview inline) |
| AI Advisor (Claude/Cerebras) | v1.9.7 | v2.6.2 |
| Catalogo stelle | v1.11.0 | v2.11.0 (saved queries) |
| TESS import | v1.13.0 | v2.9.5 (bulk + checkpoint) |
| ASAS-SN import | v1.13.1 | v2.7.11 (LB endpoint + bande) |
| ZTF import | v1.20.2 | v2.11.4 (deduplicazione Gaia) |
| VAST photometry | v1.17.0 | v2.9.x (pipeline refactored) |
| Field Star Map | v1.19.0 | v2.7.13 (blueprint mappe_stelle) |
| TPF (TESS Pixel Data) | v2.14.10 | v2.14.10 (modulo autonomo completo) |
| TESS Script Library | v2.14.10 | v2.14.10 (upload .sh/.zip/.7z, batch reuse, offset tracking) |
| Slack integration | v1.16.3 | v2.7.10 (PNG + ΔT/ΔMag) |
| Galassie Nane | v1.23.0 | v1.23.0 |
| Deploy automation | v2.0.0 | v2.14.2 (semplificato, 8 step) |
| Help online | v2.8.1 | v2.8.3 |
| Barre ΔT misurazione | v2.3.0 | v2.7.3 (ΔMag aggiunto) |
| Preview lightcurve job | v2.13.0 | v2.13.0 |
| Tutorial interattivo | v2.14.0 | v2.14.0 |

---

## Statistiche

### Progetto

- **Primo commit**: 2025-04-15
- **Versione attuale**: v3.0.6 (2026-04-13)
- **Durata sviluppo**: ~12 mesi
- **Tag rilasciati**: 75+
- **Commit totali**: ~260+
- **Architettura attuale**: Flask + PostgreSQL + TimescaleDB, moduli autonomi sotto `agata/moduli/`, RBAC multi-tenant
- **Database**: PostgreSQL + TimescaleDB hypertables (migration da MySQL completata in v3.0.0)
- **Lingue**: Python 3.12 (backend), JavaScript ES6 modules (frontend), Jinja2 (template)

### Righe di codice per modulo (Apr 2026)

I valori escludono file vendor (Bootstrap Icons, Plotly, Arrow.js, Bootstrap, ecc.), file minificati (.min.js/.min.css).

| Modulo | Python | JavaScript | HTML | CSS | Totale |
|--------|-------:|----------:|-----:|----:|-------:|
| `variable_stars` | 3,478 | 12,969 | 1,687 | 1,549 | **19,683** |
| `admin` | 22,116 | 121 | 11,585 | 50 | **33,872** |
| `tpf` | 2,955 | 2,234 | 274 | 537 | **6,000** |
| `tess_tce` | 1,447 | 2,047 | 204 | 857 | **4,555** |
| `exoplanets` | 1,776 | 748 | 345 | 664 | **3,533** |
| `galassie_nane` | 756 | 452 | 223 | 426 | **1,857** |
| `lightcurve` | 839 | 603 | 319 | — | **1,761** |
| `field_star_map` | 413 | 440 | 131 | 339 | **1,323** |
| **Totale moduli** | **42,569** | **19,743** | **15,198** | **4,675** | **82,185** |
| Core (`agata/` non-moduli) | 8,789 | 129 | 430 | 253 | **9,601** |
| **TOTALE PROGETTO** | **51,358** | **19,743** | **15,628** | **4,675** | **~91,404** |

> **Note**: 
> - Escludendo vendor (Plotly, Bootstrap, Arrow.js, minified files), **il vero codice sviluppato è ~91.4k righe**
> - Il modulo `admin` contiene VAST pipeline, ZTF Survey, TESS bulk import, gestione RBAC (~41% del codice totale)
> - Il modulo `variable_stars` è il più complesso (12.9k JS + 3.5k Python) per analisi periodiche avanzate
> - Il modulo `tpf` (nuovo) contiene analisi dati TESS Pixel: 6k righe complete

---

*Questo file è generato da analisi `git log --all`. Aggiornare con `/agata-docs "CHANGELOG aggiornamento vX.Y.Z"` per nuove release significative.*
