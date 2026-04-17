# Debug Guide: Bulk Delete Error

## Problema
Quando clicchi "Cancella Tutte", vedi: `✗ Errore di rete: Unexpected token '<'`

Ma la cancellazione sembra completa (stelle spariscono).

## Come Debuggare

### Step 1: Apri Browser DevTools
1. Accedi a: `https://app-test.astrogen.it/agata/admin/stars-catalog?import_id=117`
2. Premi **F12** (o Ctrl+Shift+I) per aprire Developer Tools
3. Vai al tab **Console**

### Step 2: Esegui Bulk Delete
1. Clicca "Seleziona Tutti" per selezionare le stelle
2. Clicca "Cancella Tutte"
3. Clicca "Conferma" nel modal

### Step 3: Controlla Console
Nella Console, dovresti vedere log come:
```
[BulkDelete] Response status: 200 ok: true
[BulkDelete] Success response: {success: true, deleted_count: 50, failed_count: 0, message: "..."}
```

Se vedi questo, significa che il server sta rispondendo correttamente.

### Possibili Problemi

#### 1. Response Status != 200
```
[BulkDelete] Response status: 500 ok: false
```
✅ **Soluzione**: C'è un errore server. Controlla i server logs con:
```bash
tail -f /var/log/agata/app.log | grep -i "bulk"
```

#### 2. Response ha success: false
```
[BulkDelete] Success response: {success: false, error: "..."}
```
✅ **Soluzione**: L'API ha restituito un errore specifico. Leggi il messaggio `error`.

#### 3. Non vedi nessun log
```
✗ Errore di rete: ...
```
✅ **Soluzione**: Il fetch stesso sta fallendo (CORS, network error).
- Controlla se il server è raggiungibile
- Controlla la scheda **Network** in DevTools per vedere la risposta HTTP raw

### Step 4: Se Vedi il Problema

Copia quello che vedi nella console e inviami:
```
✓ Response status + ok:
✓ Success response (JSON)
✓ Error message (se presente)
✓ Numero di stelle delete prima/dopo
```

## Server Logs

### Check Server Logs per Bulk Delete
```bash
# Terminal sul server
tail -f /var/log/agata/app.log | grep -i "pre-screening\|batch\|bulk"
```

Dovresti vedere:
```
[INFO] Batch pre-screening 50 stars for protection...
[INFO] Pre-screening complete: 45 deletable, 5 protected
[INFO] Starting batch deletion of 45 stars...
[INFO] Batch deletion complete: 45 stars, 12350 photometric points, 0 orphan assignments, 0 catalog attributes
```

Se vedi questi log, significa che il server ha completato la cancellazione ✅.

Se vedi un errore, il log dirà qualcosa come:
```
[ERROR] Bulk delete failed: <error message>
Traceback: ...
```

## Cosa Significa Ogni Errore

| Console Log | Significato |
|------------|-----------|
| `Response status: 200 ok: true` | ✅ Server OK |
| `Response status: 500 ok: false` | ❌ Server errore |
| `Success response: {success: true, ...}` | ✅ API success |
| `Errore di rete: Unexpected token` | ❌ JSON parse fail |
| `Server returned HTML error` | ❌ Server crash (HTML error page) |

---

## Next Steps After Debugging

1. **Se vedi Response 200**: Il fix potrebbe avere un bug logico. Manda i console logs.
2. **Se vedi Response 500**: C'è un'eccezione nel backend. Manda i server logs.
3. **Se vedi HTML error**: Il server è crashato. Restart Flask.

---

## Quick Test

Puoi anche fare un test direttamente via curl:
```bash
curl -X POST https://app-test.astrogen.it/agata/admin/api/stars-catalog/bulk-delete \
  -H "Content-Type: application/json" \
  -d '{
    "delete_mode": "all_in_filter",
    "import_id": "117"
  }' \
  -H "Cookie: session=YOUR_SESSION_ID" | jq .
```

Questo ti mostra direttamente il JSON di risposta dal server.
