# AGATA – Nuovo Endpoint Route

**Argomenti:** `$ARGUMENTS` = `<modulo> <file_routes> "<HTTP_METHOD /percorso/endpoint>" "<descrizione>"`

Esempio: `/agata-new-route field_star_map routes "GET /api/nearby-variables" "Trova variabili nel raggio del target"`

---

## Contesto Progetto

**Sistema:** AGATA | Route = thin layer, nessun algoritmo

**Pattern di riferimento:** leggi `agata/moduli/field_star_map/routes.py`

**Decoratori RBAC:** leggi `agata/moduli/admin/decorators.py`

---

## Struttura Obbligatoria della Route

```python
@<blueprint>.get("/api/<percorso>")          # o .post(), .put(), .delete()
@login_required                               # sempre
@admin_required('<ruolo_minimo>')             # se route admin; @before_request se modulo non-admin
def <nome_handler>():
    """Docstring: cosa fa, parametri attesi, risposta."""
    # 1. Parse e validazione input (try/except ValueError → 422)
    try:
        param = _parse_float_arg("param_name", default_value)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422

    # 2. Chiama service (try/except per errori specifici)
    try:
        result = service_function(param)
    except DomainSpecificError as exc:
        return jsonify({"error": "...", "detail": str(exc)}), 502
    except Exception as exc:
        logger.exception("Unexpected error in <handler_name>")
        return jsonify({"error": "Internal server error", "detail": str(exc)}), 500

    # 3. Restituisci risposta
    return jsonify(result_to_dict(result)), 200
```

---

## Regole Non Negoziabili

- **Nessun algoritmo scientifico nella route** (delegare al service)
- HTTP status semantici: 200 OK, 201 Created, 422 Validazione, 404 Not Found, 502 Servizio esterno, 500 Errore interno
- `logger.exception()` (non `.error()`) per errori inattesi (include traceback)
- JSON API: `Content-Type: application/json` sempre
- Route UI (HTML): `render_template("<blueprint>/template.html", ...)`
- Multi-tenant: filtrare sempre per `association_id` se la query tocca dati tenantizzati

---

## Se la Route È in un Grande Modulo (admin, variable_stars)

- File target nella directory `routes/` appropriata
- Non aggiungere a `routes.py` monolitico se esiste già una directory `routes/`
- Se è un nuovo dominio: proporre nuovo file `routes/<dominio>.py`

---

## Output Atteso

1. Codice completo della route
2. Helper functions di parsing (se non già esistono nel file)
3. Import da aggiungere in testa al file
4. Se richiesto un service inesistente: nota con stub da creare prima
5. Checklist:
   - [ ] Nessuna logica scientifica nella route
   - [ ] Tutti i casi di errore gestiti con status code corretto
   - [ ] Multi-tenant filtering se dati tenantizzati
   - [ ] `logger.exception()` per eccezioni inattese
   - [ ] Docstring completo
