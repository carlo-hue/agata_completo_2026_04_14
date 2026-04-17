# Slack Export - Aggiornamenti Architettura

**Data**: 4 Febbraio 2026
**Versione**: 1.1 (Architecture Update)
**Status**: ✅ COMPLETATO

---

## 📋 Cambiamenti Principali da v1.0

### ❌ Rimosso (Sbagliato)
- Invio messaggi come **nuovi messaggi nel canale**
- Ricerca canale per tipo ('review', 'lavori')
- Nessuna integrazione con ProjectSlackThread

### ✅ Aggiunto (Corretto)
- Invio messaggi come **reply nel thread del progetto**
- Ricerca ProjectSlackThread per project_id
- Completa integrazione con il sistema di thread esistente
- Aggiornamento `last_message_ts` per tracking

---

## 🎯 Architettura Finale

```
Flusso Progetto:
┌─────────────────────────────────────────────────┐
│  Progetto creato (stato: incoming)              │
│  ❌ No Slack thread yet                          │
└──────────────────┬──────────────────────────────┘
                   │
                   ↓ Transizione a "available"
┌─────────────────────────────────────────────────┐
│  notify_new_project() crea:                     │
│  ✅ ProjectSlackThread nel canale ag-*-lavori   │
│  ✅ Messaggio iniziale con progetto             │
└──────────────────┬──────────────────────────────┘
                   │
                   ↓ Analista carica il progetto
┌─────────────────────────────────────────────────┐
│  Variable Stars Editor (index.html)             │
│  3 bottoni "💬 Slack" disponibili               │
│  1. Tab Analisi in Fase                         │
│  2. Tab Periodigramma                           │
│  3. Tab Analisi di Supporto                     │
└──────────────────┬──────────────────────────────┘
                   │
                   ↓ Clicca bottone "💬 Slack"
┌─────────────────────────────────────────────────┐
│  JavaScript (slack-export.js):                  │
│  1. Genera PNG (se necessario)                  │
│  2. Compila messaggio                           │
│  3. POST a /agata/admin/api/slack-export        │
└──────────────────┬──────────────────────────────┘
                   │
                   ↓ POST request con:
                   │ - project_id
                   │ - analysis_type
                   │ - message
                   │ - image (blob PNG, opzionale)
                   │
┌─────────────────────────────────────────────────┐
│  Backend (slack_integration.py):                │
│  1. Verifica permessi                           │
│  2. Cerca ProjectSlackThread                    │
│  3. Upload immagine (se presente)               │
│  4. Invia messaggio NEL THREAD                  │
│  5. Aggiorna last_message_ts                    │
└──────────────────┬──────────────────────────────┘
                   │
                   ↓ Response success
┌─────────────────────────────────────────────────┐
│  Frontend:                                      │
│  - Bottone diventa VERDE                        │
│  - Alert "✅ Inviato a Slack"                    │
│  - Timeout 2 sec, torna BLU                     │
└─────────────────────────────────────────────────┘
                   │
                   ↓ User vede su Slack
┌─────────────────────────────────────────────────┐
│  Slack Thread (ag-*-lavori):                    │
│  ┌─────────────────────────────────────────┐   │
│  │ 📌 MAIN MESSAGE (ProjectSlackThread)    │   │
│  │ Nuovo progetto: Stella Gaia DR3 ...     │   │
│  └─────────────────────────────────────────┘   │
│                   ↓                              │
│  ┌─────────────────────────────────────────┐   │
│  │ 💬 REPLY 1: Analisi in Fase             │   │
│  │ Periodo: 4.17 giorni                    │   │
│  │ RMS: 0.045 mag                          │   │
│  │ [PNG diagramma]                         │   │
│  └─────────────────────────────────────────┘   │
│                   ↓                              │
│  ┌─────────────────────────────────────────┐   │
│  │ 💬 REPLY 2: Periodigramma               │   │
│  │ Range: 0.1 - 15 giorni                  │   │
│  │ [PNG periodigramma]                     │   │
│  └─────────────────────────────────────────┘   │
│                   ↓                              │
│  ┌─────────────────────────────────────────┐   │
│  │ 💬 REPLY 3: Analisi di Supporto         │   │
│  │ Classe Spettrale: G2V                   │   │
│  │ Teff: 5778 K                            │   │
│  │ Tipo: Eclipsing Binary                  │   │
│  └─────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
```

---

## 🔄 Flusso di Invio (Dettagliato)

### Fase 1: Frontend (JavaScript)
```javascript
// slack-export.js
1. Utente clicca bottone "💬 Slack"
2. Disabilita bottone (opacity: 60%, animazione)
3. Genera PNG da Plotly.toImage()
4. Compila messaggio testuale
5. Invia POST a /agata/admin/api/slack-export
   - FormData (con immagine)
   - O JSON (text-only)
6. Attende response
7. Se success: bottone verde + alert ✅
8. Se error: mostra alert con msg specifico
```

### Fase 2: Backend (Python/Flask)
```python
# slack_integration.py
@admin_bp.route('/api/slack-export', methods=['POST'])
1. Autentica utente (@login_required)
2. Estrae parametri:
   - project_id (INT)
   - analysis_type (STR)
   - message (STR)
   - image (FILE, opzionale)
3. Valida project_id
4. Carica progetto da DB
5. Verifica permessi:
   - Utente ha accesso associazione?
   - Associazione ha Slack abilitato?
6. Ottiene SlackService
7. TROVA ProjectSlackThread:
   - query(ProjectSlackThread).filter(
       project_id=project_id,
       is_active=True
     )
8. Se non trovato → ERROR 400
9. Se trovato:
   - Upload immagine (se presente) nel thread
     client.files_upload_v2(
       channel=thread.channel_id,
       file=image_data,
       thread_ts=thread.thread_ts  # ← IMPORTANTE!
     )
   - Invia messaggio NEL THREAD
     post_message(
       channel_id=thread.channel_id,
       text=...,
       blocks=[...],
       thread_ts=thread.thread_ts  # ← IMPORTANTE!
     )
10. Aggiorna thread.last_message_ts
11. Return JSON success + thread_ts
```

### Fase 3: Slack (visuale finale)
```
Canale ag-associazione-lavori
└── Thread (ProjectSlackThread)
    ├── Main message (data creazione progetto)
    ├── Reply: "Progetto assegnato a Mario"
    ├── Reply: "📊 Analisi in Fase [PNG] [testo]"
    ├── Reply: "📈 Periodigramma [PNG] [periodi]"
    └── Reply: "📋 Analisi di Supporto [dati]"
```

---

## 🔑 Differenze Chiave da v1.0

| Aspetto | v1.0 (Sbagliato) | v1.1 (Corretto) |
|---------|------------------|-----------------|
| **Destinazione** | Canale pubblico | Thread del progetto |
| **Thread lookup** | Non esiste | ProjectSlackThread |
| **Nuovi messaggi** | Sì, sparsi nel canale | No, sempre reply |
| **Organizzazione** | Caotica | Ordinata per progetto |
| **Context** | Perso | Mantenuto nel thread |
| **Tracking** | No | `last_message_ts` |

---

## ⚠️ Errori Comuni & Soluzioni

### ❌ "No Slack thread found for this project"
**Causa**: Progetto in stato "incoming", non ancora notificato a Slack
**Soluzione**: Progetto deve passare a stato "available" (transizione automatica)

### ❌ "Slack not enabled for this association"
**Causa**: Campo `slack_enabled = False` in `agata_associations`
**Soluzione**: Admin abilita Slack per l'associazione

### ❌ "Access denied"
**Causa**: Utente non ha permessi sulla associazione
**Soluzione**: Verifica ruolo utente e association_id

### ❌ "Missing required fields"
**Causa**: project_id, analysis_type o message vuoti
**Soluzione**: Verifica che il form sia compilato correttamente

---

## 📝 Database Schema

**ProjectSlackThread** (tabella: agata_project_slack_threads)
```
id (PK)
project_id (FK → agata_projects)
channel_id (Slack channel ID)
thread_ts (Slack thread timestamp) ← USATO PER REPLY
message_ts (initial message timestamp)
slack_type (thread/channel)
last_message_ts (aggiornato ad ogni export)
current_state (sincro con project.state)
is_active (soft delete)
created_at
updated_at
```

---

## 🚀 Deployment Notes

1. **No DB migration needed** - Schema già esiste
2. **Slack token** - Deve avere permessi:
   - `chat:write` (invia messaggi)
   - `files:write` (carica file)
   - `channels:read` (legge canali)

3. **Validazione** - Check in order:
   ```
   ✅ Progetto esiste?
   ✅ Utente autenticato?
   ✅ Utente ha accesso associazione?
   ✅ Associazione ha Slack abilitato?
   ✅ ProjectSlackThread esiste?
   ✅ Thread attivo (is_active=True)?
   ```

4. **Error response** - sempre in questo formato:
   ```json
   {
     "success": false,
     "error": "Messaggio descrittivo"
   }
   ```

---

## ✅ Verifica Checklist

- [x] SlackService integrato
- [x] ProjectSlackThread utilizzato
- [x] Thread timestamp passato (thread_ts)
- [x] Immagini nel thread (file upload con thread_ts)
- [x] Error handling specifico
- [x] Validazioni complete
- [x] Documentazione aggiornata
- [x] CSS styling
- [x] JavaScript async/await corretto
- [x] Response format consistente

---

## 📞 Testing Command

```bash
# Test manuale curl
curl -X POST http://localhost:5000/agata/admin/api/slack-export \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": 123,
    "analysis_type": "phase_analysis",
    "message": "Test message"
  }'

# Risposta success:
{
  "success": true,
  "message": "phase_analysis exported to Slack thread",
  "thread_ts": "1234567890.123456"
}

# Risposta error:
{
  "error": "No Slack thread found for this project. Project must be created first."
}
```

---

**Status**: ✅ **ARCHITETTURA CORRETTA**
**Prossimo**: Deploy in dev per testing manuale
