# AGATA – Low‑Cost Prompt Template

**Documento:** AGATA_LOW_COST_PROMPT_TEMPLATE.md
**Sistema:** AGATA
**Obiettivo:** sviluppo a basso consumo di token su codebase complessa
**Target:** Developer / AI-assisted development

---

## Scopo

Questo documento definisce **template di prompt vincolanti**, progettati specificamente per **AGATA**, con l’obiettivo di:

* ridurre drasticamente il consumo di token
* evitare rigenerazioni inutili di codice
* mantenere coerenza architetturale
* impedire violazioni dei confini di dominio

È uno **strumento operativo**, non descrittivo.

---

## Contesto architetturale minimo (OBBLIGATORIO)

Ogni prompt **DEVE** iniziare con questa sezione, compilata:

```
Sistema: AGATA
Architettura: vincolata (vedi ARCHITECTURE.md)
Modulo coinvolto: <admin | auth | services | variable_stars | static/js/variable_stars>
File target: <percorso/i preciso/i>
Tipo intervento: <modifica locale | nuova funzione | refactor | debug | review>

Regole non negoziabili:
- nessuna logica scientifica fuori da services/
- le route non contengono algoritmi
- variable_stars orchestra, non calcola
- frontend solo visualizzazione
```

⚠️ **Se questa sezione manca o è vaga, il risultato è considerato non valido.**

---

## Mappa dei confini (AGATA‑specifica)

### `admin/`

Consentito:

* policy
* validazioni di stato
* workflow

Vietato:

* algoritmi scientifici
* parsing dati astronomici
* calcoli numerici

---

### `auth/`

Consentito:

* identità
* ruoli
* sessioni

Vietato:

* logica di dominio
* decisioni scientifiche

---

### `services/`

Consentito (UNICO LUOGO):

* algoritmi scientifici
* calcoli deterministici
* normalizzazione dati
* parser cataloghi

Vietato:

* dipendenze Flask
* accesso diretto a request / session
* decisioni UI

---

### `variable_stars/`

Consentito:

* orchestrazione pipeline
* chiamata servizi
* validazioni scientifiche di alto livello

Vietato:

* riscrivere algoritmi
* duplicare logica di services/

---

### `static/js/variable_stars/`

Consentito:

* grafici
* interazioni
* visualizzazione

Vietato:

* calcoli scientifici
* decisioni di dominio

---

## Anti‑pattern vietati (AGATA)

Questi pattern **NON DEVONO MAI comparire**:

* logica scientifica in route Flask
* `if scientific_condition` in JS
* funzioni duplicate tra services/ e variable_stars/
* parsing cataloghi fuori da services/
* stato mutato senza policy admin
* side‑effect non auditati

Se uno di questi è necessario, il prompt è **sbagliato**.

---

## Template 1 – Modifica locale (LOW TOKEN)

Usare per modifiche puntuali.

```
Obiettivo: modificare comportamento locale SENZA cambiare API

File: <file singolo>
Funzione/classe: <nome preciso>

Input attuale:
<descrizione sintetica>

Output desiderato:
<descrizione sintetica>

Vincoli:
- non modificare altre funzioni
- non cambiare signature
- non introdurre nuove dipendenze

Restituisci:
- SOLO il diff o la funzione aggiornata
```

---

## Template 2 – Nuova funzione in `services/`

```
Obiettivo: introdurre nuova funzione scientifica

Modulo: services/
File target: <path>

Responsabilità della funzione:
- cosa fa
- cosa NON fa

Input:
- tipo
- unità

Output:
- tipo
- unità

Vincoli AGATA:
- deterministica
- nessun accesso a web/UI
- testabile in isolamento

Restituisci:
- signature
- docstring
- implementazione
```

---

## Template 3 – Orchestrazione in `variable_stars/`

```
Obiettivo: coordinare servizi esistenti

Servizi coinvolti:
- <services.foo>
- <services.bar>

Ruolo del modulo:
- orchestration only

Vincoli:
- nessun calcolo nuovo
- nessuna duplicazione logica

Restituisci:
- pseudocodice
- poi implementazione minima
```

---

## Template 4 – Refactor controllato

```
Obiettivo: refactor senza cambiare comportamento

File:
- <lista precisa>

Motivo:
- duplicazione
- leggibilità
- testabilità

Vincoli:
- output invariato
- API invariata
- coverage logico preservato

Restituisci:
- elenco cambi
- codice refactorizzato
```

---

## Template 5 – Debug a basso costo

```
Errore osservato:
<traccia o comportamento>

Ambito:
<services | variable_stars | admin>

Ipotesi consentite:
- <lista>

Vincoli:
- non riscrivere moduli
- intervento minimo

Restituisci:
- causa probabile
- fix puntuale
```

---

## Checklist pre‑prompt (OBBLIGATORIA)

Prima di inviare:

* [ ] ho indicato il modulo AGATA corretto
* [ ] ho limitato i file coinvolti
* [ ] non sto chiedendo “aggiungi una feature” in modo vago
* [ ] non sto violando i confini services / variable_stars

Se una risposta ignora questa checklist, va rigenerata.

---

## Regola d’oro

> **AGATA non è un’app CRUD.**
> Ogni prompt deve rispettare il dominio scientifico e i suoi confini.

Fine documento.
