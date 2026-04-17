# Slack Export Implementation - Analisi Variabili Stelle

**Data**: 4 Febbraio 2026
**Componenti**: 3 bottoni "Invia a Slack" nei tab principali
**Status**: ✅ Completato

---

## 📋 Panoramica

Sono stati implementati tre bottoni per esportare i risultati dell'analisi di stelle variabili direttamente a Slack:

1. **Tab Analisi in Fase** - Esporta PNG diagramma in fase + dati minimali
2. **Tab Periodigramma** - Esporta PNG periodigramma + valori testuali periodi
3. **Tab Analisi di Supporto** - Esporta dati completi formattati in testo

---

## 🎯 Funzionalità per Tab

### 1. Tab "Analisi in Fase" (Phase Analysis)

**Ubicazione bottone**: Riga "Periodo & Fine-Tuning e Sampling Dataset"
**Bottone ID**: `btn-slack-phase-analysis`
**Colore**: 🔵 Blu (#3b82f6)

**Cosa invia**:
- ✅ PNG del diagramma in fase (1200x800px, scala 2x per qualità)
- ✅ Messaggio testuale compatto:
  - Periodo in giorni
  - RMS fit (magnitudini)
  - χ² ridotto
  - Copertura fase (%)

**Esempio messaggio Slack**:
```
📊 *Analisi in Fase*
Inviato dall'editor AGATA

*Periodo:* 4.17263800 giorni
*RMS:* 0.045231 mag
*χ² ridotto:* 1.2345
*Copertura fase:* 87.5%
```

**Backend**: Carica PNG su Slack file storage + invia messaggio formattato

---

### 2. Tab "Periodigramma" (Periodogram)

**Ubicazione bottone**: A destra dei box dei periodi (peaks)
**Bottone ID**: `btn-slack-periodogram`
**Colore**: 🔵 Blu (#3b82f6)

**Cosa invia**:
- ✅ PNG periodigramma (1200x600px, scala 2x)
- ✅ Messaggio testuale con:
  - Range periodo (min, max)
  - Pre-whitening status (abilitato/disabilitato)
  - N periodi per pre-whitening (se abilitato)
  - Lista periodi trovati (peaks)

**Esempio messaggio Slack**:
```
📈 *Periodigramma*
Inviato dall'editor AGATA

*Range Periodo:* 0.100 - 15.00 giorni
*Pre-whitening:* ✅ Abilitato
*N. Periodi per pre-whitening:* 3

*Periodi trovati:*
P1: 4.172638 giorni (FAP: 0.001)
P2: 2.086319 giorni (FAP: 0.045)
P3: 1.391546 giorni (FAP: 0.234)
```

**Backend**: Carica PNG + invia periodi come testo

---

### 3. Tab "Analisi di Supporto" (Support Analysis)

**Ubicazione bottone**: Angolo in alto a destra del header principale
**Bottone ID**: `btn-slack-support-analysis`
**Colore**: 🔵 Blu (#3b82f6)

**Cosa invia**:
- ✅ Dati completi formattati in testo (NO immagine)
- ✅ Struttura divisa per sezioni:
  - Informazioni Base (progetto, Gaia ID, coordinate, periodo)
  - Parametri Fisici Stella (spettro, Teff, distanza, luminosità, raggio, massa, colori)
  - Tipo di Variabile
  - Identificatori Cataloghi (VSX, ASASSN, TYC, etc.)
  - Parametri Variabilità (ampiezza, passband, epoch)

**Esempio messaggio Slack** (estratto):
```
📊 *Analisi di Supporto - Preparazione AAVSO/VSX*
Inviato dall'editor AGATA

*═══ INFORMAZIONI BASE ═══*
Nome Progetto: Stella Gaia DR3 4189513999074055552
Stella Gaia DR3: 4189513999074055552
Coordinate (RA, Dec): 123.45678, +45.67890
Periodo (dall'analisi in fase): 4.172638 d

*═══ PARAMETRI FISICI STELLA ═══*
Classe Spettrale: G2V
Teff (K): 5778
Distanza (pc): 10.5
Luminosità (L☉): 1.0
Raggio (R☉): 1.0
Massa (M☉): 1.0
Colore B-V: 0.656
Colore BP-RP: 0.863

*═══ TIPO DI VARIABILE ═══*
Tipo Proposto: Eclipsing Binary - EA (Algol-type)

*═══ IDENTIFICATORI CATALOGHI ═══*
• VSX J123456.7+123456
• ASASSN-V J123456.78+123456.7
• TYC 1234-5678-1

*═══ PARAMETRI VARIABILITÀ ═══*
Ampiezza Variabilità (mag): 0.072
Passband: G
Epoch (JD): 2459770.00000
```

---

## 🏗️ Architettura Tecnica

### ⚡ Requisito Fondamentale

**I messaggi vanno nel THREAD del progetto, non in un canale generale.**

- Ogni progetto ha un `ProjectSlackThread` creato quando il progetto viene notificato a Slack
- Il thread esiste nel canale 'lavori' dell'associazione
- Tutti gli export (fase, periodigramma, supporto) vanno come risposte nel thread

### Frontend (JavaScript)

**File**: `agata/static/js/variable_stars/slack-export.js`

Modulo con 6 funzioni principali:

1. **`exportPhaseAnalysisToSlack()`** - Gestisce export fase
   - Genera PNG (1200x800, scale 2x)
   - Compila messaggio minimalista
   - Invia a backend

2. **`generatePhaseAnalysisPNG()`** - Helper generazione PNG fase
   - Usa Plotly.toImage()

3. **`buildPhaseAnalysisMessage()`** - Compila messaggio fase
   - Periodo, RMS, χ², copertura

4. **`exportPeriodogramToSlack()`** - Gestisce export periodigramma
   - Genera PNG (1200x600)
   - Compila messaggio con periodi

5. **`generatePeriodogramPNG()`** - Helper generazione PNG periodogramma
   - Usa Plotly.toImage()

6. **`buildPeriodogramMessage()`** - Compila messaggio periodigramma
   - Range, pre-whitening, periodi trovati

7. **`exportSupportAnalysisToSlack()`** - Gestisce export supporto
   - Compila messaggio completo (senza immagine)
   - Dati da form HTML

8. **`buildSupportAnalysisMessage()`** - Compila messaggio supporto
   - Estrae tutti i dati dal form
   - Formatta in sezioni

9. **`sendImageAndMessageToSlack()`** - Helper comunicazione backend
   - Carica immagine via FormData
   - Invia a `/agata/admin/api/slack-export`

10. **`sendMessageToSlack()`** - Helper comunicazione backend (text-only)
    - Invia JSON a `/agata/admin/api/slack-export`

11. **`initSlackExportButtons()`** - Inizializzazione
    - Attacca event handler ai bottoni
    - Esportata e chiamata da main.js

**Importazione**: In `main.js` (line 32-33)
```javascript
import { initSlackExportButtons } from './slack-export.js';
```

**Inizializzazione**: Nel DOMContentLoaded di main.js
```javascript
initSlackExportButtons();
console.log('✅ Bottoni Slack export inizializzati');
```

---

### Backend (Python Flask)

**File**: `agata/admin/routes/slack_integration.py`

Nuovo endpoint:

```python
@admin_bp.route('/api/slack-export', methods=['POST'])
@login_required
def api_slack_export():
```

**Funzionalità**:
- ✅ Autenticazione utente
- ✅ Verifica permessi associazione
- ✅ Verifica Slack abilitato per associazione
- ✅ Trova ProjectSlackThread per il progetto
- ✅ Carica immagine (se presente) **nel thread**
- ✅ Invia messaggio **nel thread** con Slack blocks
- ✅ Aggiorna `last_message_ts` del thread
- ✅ Error handling completo

**Validazioni**:
- Project ID valido
- Associazione corretta
- Slack configurato per associazione
- ProjectSlackThread esiste (progetto creato)

**Errori specifici gestiti**:
- ❌ "No Slack thread found" → Progetto non ancora notificato a Slack
- ❌ "Slack not enabled" → Integrazione disabilitata per associazione
- ❌ "Access denied" → Utente non ha permessi

**Risposta success**:
```json
{
  "success": true,
  "message": "phase_analysis exported to Slack thread",
  "thread_ts": "1234567890.123456"
}
```

---

### Template HTML

**File**: `agata/templates/variable_stars/index.html`

**Modifiche**:

1. **Line ~917** (tab-phase): Bottone in riga "Periodo & Fine-Tuning"
   ```html
   <button id="btn-slack-phase-analysis"
           title="Invia analisi in fase (PNG + dati) a Slack"
           style="padding: 4px 10px; background: #3b82f6; color: white; ...">
     💬 Slack
   </button>
   ```

2. **Line ~530** (tab-period): Bottone a destra dei periodi
   ```html
   <button id="btn-slack-periodogram"
           title="Invia periodigramma (PNG + periodi) a Slack"
           style="padding: 6px 12px; background: #3b82f6; ...">
     💬 Slack
   </button>
   ```

3. **Line ~556** (tab-comparison): Bottone nell'header support analysis
   ```html
   <button id="btn-slack-support-analysis"
           title="Invia analisi di supporto (dati formattati) a Slack"
           style="padding: 0.6rem 1.2rem; background: #3b82f6; ...">
     💬 Invia a Slack
   </button>
   ```

---

### Styling CSS

**File**: `agata/static/css/variable_stars.css`

Aggiunte regole CSS (lines 1740-1776):

```css
/* Bottoni Slack generic */
[id^="btn-slack"] {
    transition: all 0.2s ease;
    box-shadow: 0 1px 3px rgba(59, 130, 246, 0.2);
}

[id^="btn-slack"]:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
}

[id^="btn-slack"].success {
    background: #10b981 !important;
    box-shadow: 0 4px 12px rgba(16, 185, 129, 0.4);
}

/* Animazione caricamento */
@keyframes slack-loading {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.7; }
}
```

**Feedback visivo**:
- ✅ Hover: translate su + shadow più grande
- ✅ Loading: opacity 60% + animazione fade
- ✅ Success: colore verde + messaggio

---

## 📡 Flusso Comunicazione

### Phase Analysis
```
1. Utente clicca "💬 Slack" in tab Analisi in Fase
   ↓
2. JavaScript genera PNG del diagramma (Plotly.toImage)
   ↓
3. Compila messaggio tesuale minimalista
   ↓
4. POST a /agata/admin/api/slack-export con:
   - project_id (FormData)
   - image (PNG blob)
   - message (testo)
   - analysis_type = "phase_analysis"
   ↓
5. Backend:
   - Verifica permessi e associazione
   - Trova ProjectSlackThread per il progetto
   - Carica PNG nel thread
   - Invia messaggio NEL THREAD con Slack blocks
   - Aggiorna last_message_ts del thread
   ↓
6. Risposta success → Alert ✅ + bottone diventa verde
```

### Periodogram
```
Simile a Phase Analysis, ma:
- PNG del periodigramma (1200x600)
- Messaggio include periodi trovati
- analysis_type = "periodogram"
- Invia NEL THREAD come response
```

### Support Analysis
```
1. Utente clicca "💬 Invia a Slack" in header Analisi di Supporto
   ↓
2. JavaScript estrae dati da tutti i form fields
   ↓
3. Compila messaggio completo formattato
   ↓
4. POST a /agata/admin/api/slack-export con:
   - project_id (JSON)
   - message (testo completo)
   - analysis_type = "support_analysis"
   (NO image)
   ↓
5. Backend:
   - Verifica permessi e associazione
   - Trova ProjectSlackThread per il progetto
   - Invia messaggio NEL THREAD con Slack blocks
   - Aggiorna last_message_ts del thread
   ↓
6. Risposta success → Alert ✅ + bottone diventa verde
```

---

## 🔐 Sicurezza

✅ **Autenticazione**: @login_required su tutte le rotte
✅ **Autorizzazione**: Verifica associazione + ruolo utente
✅ **Validazione Input**: Project ID + analysis_type + message
✅ **Validazione File**: Solo PNG accettati (check extension)
✅ **Rate Limiting**: Nessuno al momento, aggiungibile in futuro
✅ **Audit**: Tutti gli export a Slack sono loggati (user, timestamp, type)

---

## ⚠️ Prerequisiti per Funzionamento

**IMPORTANTE**: I bottoni funzionano SOLO se:

1. ✅ Progetto è stato **creato** e notificato a Slack
   - Il progetto deve avere un `ProjectSlackThread` associato
   - Questo accade automaticamente quando il progetto entra nello stato "available"
   - Se il progetto non ha ancora un thread, vedrai errore: "No Slack thread found"

2. ✅ Associazione ha **Slack abilitato**
   - Campo `slack_enabled = True` nella tabella `agata_associations`

3. ✅ Utente ha **permessi sulla associazione**
   - Ruolo: admin, reviewer, analyst (non viewer)
   - Stessa associazione del progetto

4. ✅ **Canale attivo** per associazione
   - Almeno uno tra 'review' o 'lavori' deve essere configurato

---

## 🧪 Testing

### Test Manuale

1. **Prerequisito: Progetto creato**
   - Accedi come admin
   - Naviga a Progetto con stato "available" o successivo
   - Verifica che il progetto abbia un thread su Slack (canale ag-*-lavori)

2. **Load Progetto**
   - Carica il progetto dalla lista admin
   - Verifica che project_id sia in `<input id="projectId">`

3. **Tab Analisi in Fase**
   - Calcola analisi in fase (clicca "Aggiorna")
   - Clicca bottone "💬 Slack" nella riga Sampling
   - Aspetta risposta (2-3 sec)
   - Bottone diventa verde ✅
   - Verifica messaggio su Slack **nel thread del progetto** (canale `ag-*-lavori`)

4. **Tab Periodigramma**
   - Calcola periodigramma (imposta range + clicca "Calcola")
   - Clicca bottone "💬 Slack" a destra periodi
   - Bottone diventa verde ✅
   - Verifica messaggio **nel thread** con PNG e periodi trovati

5. **Tab Analisi di Supporto**
   - Compila alcuni campi (facoltativo)
   - Clicca "💬 Invia a Slack" nell'header
   - Bottone diventa verde ✅
   - Verifica messaggio **nel thread** con tutti i dati disponibili

### Test Error Handling

- ❌ No project_id → Alert "Project ID non trovato"
- ❌ No Slack thread → Alert "Il progetto deve essere creato prima di esportare a Slack"
- ❌ Slack disabled → Alert "Slack non è abilitato per questa associazione"
- ❌ Network error → Alert con messaggio errore
- ❌ Progetto in stato "incoming" → Nessun thread creato, export fallisce

---

## 📦 File Modificati

| File | Tipo | Linee | Descrizione |
|------|------|-------|-------------|
| `agata/static/js/variable_stars/slack-export.js` | ➕ NEW | 330 | Modulo export Slack completo |
| `agata/static/js/variable_stars/main.js` | ✏️ EDIT | +2 | Import + init bottoni Slack |
| `agata/templates/variable_stars/index.html` | ✏️ EDIT | +6 | 3 bottoni + attributi |
| `agata/admin/routes/slack_integration.py` | ✏️ EDIT | +120 | Nuovo endpoint API |
| `agata/static/css/variable_stars.css` | ✏️ EDIT | +37 | Styling bottoni Slack |

**Totale modifiche**: ~500 righe di codice

---

## 🚀 Deploy Checklist

- [x] File creati/modificati
- [x] Sintassi Python validata
- [x] CSS compatibile
- [x] HTML ben formato
- [x] Importazioni JS corrette
- [ ] Test manuale in dev
- [ ] Deploy a produzione
- [ ] Verify Slack integration attiva
- [ ] Monitor log per errori

---

## 📝 Note

1. **Slot delle immagini**: Usa Plotly.toImage() che genera PNG a 300px scale
   - Scala 2x → 600px/1200px per qualità migliore
   - Slack comprime automaticamente

2. **Formato messaggi**: Usa Slack Markdown (mrkdwn)
   - `*testo*` = bold
   - `_testo_` = italic
   - `` `codice` `` = monospace

3. **Thread vs Canale**: I messaggi vanno SEMPRE nel thread del progetto
   - Ogni progetto ha un ProjectSlackThread creato quando entra in stato "available"
   - Il thread esiste nel canale "lavori" dell'associazione
   - Tutti gli export sono reply nel thread, mai messaggi nuovi nel canale

4. **File in thread**: Le immagini sono caricate nel thread con `thread_ts`
   - Slack preserva la relazione file-thread
   - Visibili nel contesto del progetto

5. **Cache**: NO caching di immagini per evitare stale data

6. **Timeout**: POST ha timeout 30sec (default Flask)

---

## 🆘 Troubleshooting

### Errore "Slack not configured: Slack integration is disabled globally"

**Causa**: Variabile d'ambiente `SLACK_INTEGRATION_ENABLED=false` in `.env`

**Quando succede**:
- Click "Send to Slack" su astrogen01 (dev)
- POST `/api/slack-export` restituisce HTTP 500
- Log mostra: "ValueError: Slack integration is disabled globally (SLACK_INTEGRATION_ENABLED=false)"

**Soluzione**:
- **Per ambienti di sviluppo**: Comportamento atteso! Slack è disabilitato intenzionalmente per evitare notifiche duplicate quando dev e prod condividono lo stesso workspace Slack. Non è un errore.
- **Per produzione**: Verifica che `.env` contenga `SLACK_INTEGRATION_ENABLED=true` o rimuovi la variabile (default = true).

**Come distinguere tra dev e prod**:
```bash
# Su astrogen01 (dev):
grep SLACK_INTEGRATION_ENABLED /var/www/astrogen/.env
# Atteso: SLACK_INTEGRATION_ENABLED=false

# Su astrogen03 (prod):
grep SLACK_INTEGRATION_ENABLED /var/www/astrogen/.env
# Atteso: SLACK_INTEGRATION_ENABLED=true (o assente)
```

### Errore "Slack test connection" → HTTP 503

**Causa**: Integrazione Slack disabilitata globalmente su questo server

**Quando succede**:
- Admin naviga a `/agata/admin/slack`
- Click bottone "Test Connection"
- Risposta HTTP 503 Service Unavailable con messaggio: "Slack integration is disabled globally"

**Soluzione**: Stesso come sopra. Su astrogen01 è atteso. Su astrogen03 significa che `SLACK_INTEGRATION_ENABLED=false`.

### Bottone "Send to Slack" non visibile

**Causa possibile**:
- Association ha `slack_enabled=false` nel database
- Variabile d'ambiente `SLACK_INTEGRATION_ENABLED=false`

**Verifica**:
```bash
# Check variabile d'ambiente
grep SLACK_INTEGRATION_ENABLED /var/www/astrogen/.env

# Check flag nel database
mysql -u aaaat01 catalogo -e "SELECT id, name, slack_enabled FROM agata_associations WHERE id = <YOUR_ASSOCIATION_ID>;"
# Se slack_enabled=0, update: UPDATE agata_associations SET slack_enabled=1 WHERE id=<ID>;
```

---

## 🔮 Sviluppi Futuri

- [x] ✅ **Thread organization** - Implementato! Tutti i messaggi vanno nel thread del progetto
- [ ] Bulk export (più progetti contemporaneamente)
- [ ] Scheduled exports (notifiche programmate)
- [ ] Custom format templates per messaggi
- [ ] Webhook callbacks per reaction emoji (approvazione rapida)
- [ ] Export in altri formati (PDF, JSON)
- [ ] Rate limiting per associazione
- [ ] Archive/cleanup thread dopo submission AAVSO
- [ ] Emoji reactions per status (✅ approved, ❌ rejected)

---

**Status**: ✅ **IMPLEMENTAZIONE COMPLETATA**
**Data Completion**: 4 Feb 2026
**Developer**: Claude Code AI
**Next Review**: 11 Feb 2026
