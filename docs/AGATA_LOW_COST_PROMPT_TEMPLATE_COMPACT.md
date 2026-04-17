# AGATA – Ultra-Compact Prompt Set (Low Budget)

**Uso previsto:** VS Code / Claude / ChatGPT
**Obiettivo:** minimo consumo di token, massimo controllo architetturale

---
questo è un esempio mio
usando ARCHITECTURE_MAP.md  e ARCHITECTURE.md per avere una idea di come approcciare alla modifica del codice aggiungimi un campo note su progetti e catalogo stelle. Per il db scrivimi l'sql se servono delle modifiche al db. modifica l'interfaccia per rendere facile modificare il campo note. Risparmia token

---

## Header obbligatorio (copiaincolla SEMPRE)

```
Sistema: AGATA
Riferimenti normativi: ARCHITECTURE.md, ARCHITECTURE_MAP.md
Modulo: <admin | auth | services | variable_stars | static/js/variable_stars>
File: <path preciso>
Intervento: <modifica | nuova funzione | refactor | debug>
Regole: services=logica, variable_stars=orchestrazione, route=NO algoritmi
```

Se manca una di queste righe → risposta non valida.

---

## Prompt standard – Modifica locale

```
Obiettivo: cambiare comportamento locale senza toccare altro

Funzione/classe: <nome>
Input attuale: <1 riga>
Output desiderato: <1 riga>

Vincoli:
- non cambiare signature
- non toccare altri file
- rispettare ARCHITECTURE.md e ARCHITECTURE_MAP.md

Restituisci SOLO il codice modificato
```

---

## Prompt standard – Nuova funzione scientifica (`services/`)

```
Obiettivo: nuova funzione scientifica

Responsabilità:
- fa: <1 riga>
- NON fa: <1 riga>

Input: <tipo + unità>
Output: <tipo + unità>

Vincoli:
- deterministica
- nessuna dipendenza web/UI
- conforme ARCHITECTURE.md e ARCHITECTURE_MAP.md

Restituisci:
- signature
- docstring
- implementazione
```

---

## Prompt standard – Orchestrazione (`variable_stars/`)

```
Obiettivo: coordinare servizi esistenti

Servizi chiamati:
- <services.x>
- <services.y>

Vincoli:
- nessun calcolo nuovo
- solo orchestrazione
- conforme ARCHITECTURE.md e ARCHITECTURE_MAP.md

Restituisci prima pseudocodice, poi codice minimo
```

---

## Prompt standard – Debug rapido

```
Errore:
<traccia o sintomo>

Ambito: <services | variable_stars | admin>

Vincoli:
- fix minimo
- nessun refactor
- rispettare ARCHITECTURE.md e ARCHITECTURE_MAP.md

Restituisci:
- causa probabile
- patch puntuale
```

---

## ❗ Prompt di EMERGENZA (budget/token critico)

Usalo quando **non puoi permetterti rigenerazioni**.

```
RISPOSTA ULTRA-CORTA.

File: <path>
Funzione: <nome>
Problema: <1 frase>

Regole:
- rispettare ARCHITECTURE.md e ARCHITECTURE_MAP.md
- NON spiegare
- NON ripetere codice invariato
- SOLO patch minima

Output: codice o diff, nient’altro
```

---

## Anti-pattern (check mentale prima di inviare)

* logica scientifica fuori da services/
* calcoli in JS
* orchestrazione che calcola
* prompt vaghi tipo “aggiungi una feature”

Se stai violando uno di questi → stai sprecando token.

---

## Regola finale

> Meno contesto scrivi, **più deve essere preciso**.

Fine documento.
