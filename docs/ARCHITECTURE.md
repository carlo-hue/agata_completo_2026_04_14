# AGATA – Architecture Overview
 
**Documento:** ARCHITECTURE.md  
**Sistema:** AGATA  
**Versione:** v1.0  
**Data:** 2026-01-20  
**Stato:** Baseline architetturale  
**Target:** Developer
 
---
 
## Scopo del documento
 
Questo documento definisce l’**architettura di riferimento di AGATA**.
 
È un documento **normativo**, non descrittivo:
- stabilisce **confini**
- definisce **responsabilità**
- impone **regole non negoziabili**
 
Non descrive l’implementazione nel dettaglio né sostituisce la documentazione di singoli moduli.
 
---
 
## Macro-aree
 
### `admin/`
Area di **governo applicativo** e controllo.
 
Responsabilità:
- workflow e stati dei progetti
- policy e validazione delle azioni
- audit log e compliance
- gestione associazioni, utenti, configurazioni
- metriche e statistiche amministrative
 
Caratteristiche:
- contiene **business logic amministrativa**
- è **autorità sullo stato**
- **non** contiene logica scientifica
 
---
 
### `auth/`
Gestione identità e accesso.
 
Responsabilità:
- autenticazione utenti
- gestione ruoli e permessi
- magic link e OAuth
- sessioni e contesto utente
 
---
 
### `services/`
**Cuore scientifico e computazionale del sistema.**
 
Responsabilità:
- caricamento e normalizzazione dati
- algoritmi scientifici
- lettori di formati (es. TESS QLP)
- calcoli deterministici
- logica riutilizzabile e testabile
 
Caratteristiche:
- indipendente da Flask e routing
- nessuna dipendenza dalla UI
- funzioni e servizi **invocabili da più contesti**
 
👉 **Tutta la logica scientifica vive qui.**
 
---
 
### `variable_stars/`
Pipeline scientifica per l’analisi delle stelle variabili.
 
Responsabilità:
- orchestrazione dei servizi scientifici
- analisi di periodi, fasi, O–C
- validazioni scientifiche
- supporto ad AI advisor
 
Caratteristiche:
- non ridefinisce algoritmi di base
- coordina servizi già esistenti
 
---
 
### `static/js/variable_stars/`
Frontend di analisi interattiva.
 
Responsabilità:
- visualizzazione dei dati
- interazione utente (zoom, selezioni, confronti)
- supporto all’esplorazione scientifica
 
Caratteristiche:
- **non** contiene logica scientifica
- **non** prende decisioni di dominio
 
---
 
## Cataloghi esterni
 
I cataloghi esterni (TESS, ZTF, ASAS-SN, OGLE, file) sono trattati come **adattatori**.
 
Principi:
- nessuna dipendenza diretta dal dominio AGATA
- ogni catalogo è isolato dal resto del sistema
- i dati vengono **importati** e poi gestiti localmente
 
👉 **AGATA è autoritativo**: i cataloghi esterni non lo sono.
 
---
 
## Regole Architetturali (vincolanti)
 
1. **Le route non contengono logica scientifica**
  - orchestrano
  - validano input/output
  - delegano ai servizi
 
2. **La logica scientifica vive in `services/`**
  - codice deterministico
  - testabile
  - indipendente dal contesto web
 
3. **Lo stato è centrale e governato**
  - validato da policy
  - modificato solo da servizi/comandi autorizzati
  - auditato sistematicamente
 
4. **Slack e integrazioni esterne sono best-effort**
  - non bloccano il successo dell’operazione
  - non sono mai sorgente di verità
 
5. **Un bottone visibile = azione consentita**
  - nessuna logica duplicata in UI
  - la policy è unica e centralizzata
 
---
 
## Principi guida
 
- separazione netta dei concerns
- dominio scientifico isolato
- riproducibilità dei risultati
- tracciabilità completa (audit)
- estendibilità controllata
 
AGATA è progettato come **ambiente scientifico strutturato**, non come semplice applicazione web. --> questo quanto preso, va unito al tree?