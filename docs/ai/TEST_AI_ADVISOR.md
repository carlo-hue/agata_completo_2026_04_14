# 🧪 Testing AI Advisor - Guida Rapida

## Setup Iniziale

### Opzione A: Cerebras (GRATUITO - RACCOMANDATO) 🎉

```bash
# 1. Ottieni chiave gratuita su: https://inference.cerebras.ai/
# 2. Configura
export AI_PROVIDER=cerebras
export CEREBRAS_API_KEY="csk-YOUR_KEY_HERE"

# 3. Test
./test_anthropic_setup.py
```

📖 **Guida completa**: [CEREBRAS_SETUP.md](CEREBRAS_SETUP.md)

### Opzione B: Claude (a pagamento)

```bash
# 1. Ottieni chiave su: https://console.anthropic.com/
# 2. Configura
export AI_PROVIDER=claude
export ANTHROPIC_API_KEY="sk-ant-api03-YOUR_KEY_HERE"
```

### Opzione C: OpenAI (a pagamento)

```bash
# 1. Ottieni chiave su: https://platform.openai.com/
# 2. Configura
export AI_PROVIDER=openai
export OPENAI_API_KEY="sk-YOUR_KEY_HERE"
```

### 3. Riavvia Flask

```bash
# Se usi systemd
sudo systemctl restart astrogen

# Se run manuale
python app.py
```

## Test Base (Senza Periodigramma)

1. Apri http://localhost:5000/agata/variable-stars/
2. Carica dati sintetici:
   - Tipo: "Multi-Periodo (3 periodi)"
   - Sessioni: 6
   - Premi "Carica dati"
3. Vai al tab **"🤖 AI Advisor"**
4. Premi **"✨ Analizza Ora"**
5. Attendi 5-10 secondi

### Cosa aspettarsi:

- ✅ **Riepilogo**: Punteggio qualità globale (es: "7.5/10")
- ✅ **Qualità Sessioni**: Ogni sessione con punteggio e problemi rilevati
- ✅ **Suggerimenti Pre-processing**: Azioni raccomandate (zero-align, detrending, ecc.)
- ✅ **Raccomandazioni Periodigramma**: Range ottimale per min/max periodo

## Test Completo (Con Classificazione Stella)

1. Segui i passi 1-2 del test base
2. Vai al tab **"Periodogramma"**
3. Attiva **Pre-whitening** ✓
4. Imposta parametri:
   - Min P: 0.1
   - Max P: 15
   - N periodi: 3
5. Premi **"Calcola"**
6. Attendi che il periodigramma sia completato
7. Vai al tab **"🤖 AI Advisor"**
8. Premi **"✨ Analizza Ora"**

### Cosa aspettarsi in più:

- ✅ **Classificazione Stella Variabile**: Tipo identificato (es: "Delta Scuti multiperiodica")
- ✅ **Confidenza**: Percentuale (es: 85%)
- ✅ **Spiegazione**: Motivazione scientifica
- ✅ **Tipi alternativi**: Classificazioni possibili alternative

## Test con Dati Reali

1. Carica dati da database:
   - Origine: "Database (GAIA)"
   - GAIA ID: inserisci un ID valido
   - Premi "Carica dati"
2. Segui gli stessi passi del test completo

## Cosa Testare

### ✅ Funzionalità Base

- [ ] Loading state appare durante analisi
- [ ] Empty state prima dell'analisi
- [ ] Risultati si visualizzano correttamente
- [ ] Punteggi sessioni realistici (0-10)
- [ ] Suggerimenti sono rilevanti per i dati

### ✅ Interazioni

- [ ] Click su "Applica Range al Periodigramma" aggiorna i campi
- [ ] Switch tab non causa errori
- [ ] Multiple analisi consecutive funzionano

### ✅ Edge Cases

- [ ] Analisi con 1 sola sessione
- [ ] Analisi con sessioni molto rumorose
- [ ] Analisi senza calcolare periodigramma prima
- [ ] Analisi dopo aver calcolato periodigramma
- [ ] Rianalisi dopo modifica dati (detrending, rimozione outlier)

## Debugging

### Controlla Console Browser

Apri Developer Tools (F12) → Console:

```javascript
// Verifica che AI Advisor sia inizializzato
console.log('AI Advisor loaded')

// Verifica risultati periodigramma in state
state.periodogramResult

// Verifica stato AI
window.aiState // (se disponibile)
```

### Controlla Log Backend

```bash
# Segui i log
journalctl -fu astrogen

# O se run manuale
# Guarda output console
```

Cerca messaggi tipo:
```
[AI] Inizializzazione AI Advisor
[AI] Avvio analisi AI
[AI] Invio richiesta con 1234 punti, 6 sessioni
Chiamata Claude API...
AI Advisor completato con successo
```

### Errori Comuni

**Errore**: "ANTHROPIC_API_KEY non configurata"
- **Fix**: Verifica `echo $ANTHROPIC_API_KEY` e riavvia Flask

**Errore**: "Carica prima dei dati!"
- **Fix**: Carica dati prima di premere "Analizza Ora"

**Errore**: Network error / timeout
- **Fix**: Verifica connessione internet, proxy firewall

**Warning**: "Nessun periodigramma disponibile"
- **Info**: Normale se non hai calcolato il periodigramma, l'analisi funzionerà comunque

## Output Esempio

```json
{
  "analysis": {
    "session_quality": {
      "overall_score": 7.8,
      "sessions": {
        "0": {
          "score": 8.5,
          "issues": [],
          "recommendations": ["Qualità ottima, nessun intervento necessario"]
        },
        "2": {
          "score": 5.2,
          "issues": ["Alto rumore fotometrico (MAD=0.25)"],
          "recommendations": ["Considerare sigma-clipping con soglia 2.5σ"]
        }
      }
    },
    "preprocessing_suggestions": [
      {
        "action": "zero_align",
        "priority": "high",
        "reason": "Sessioni 2 e 3 mostrano offset significativi...",
        "parameters": {"sigma": 3.0}
      }
    ],
    "periodogram_recommendations": {
      "min_period": 0.05,
      "max_period": 12.0,
      "reasoning": "Basato sulla durata delle sessioni..."
    },
    "variable_classification": {
      "type": "Delta Scuti multiperiodica",
      "confidence": "high",
      "reasoning": "3 periodi corti (0.1-0.5d), ampiezze moderate...",
      "alternative_types": ["Gamma Doradus", "Hybrid pulsator"]
    }
  },
  "summary": "Qualità globale: 7.8/10 • 1 azioni prioritarie • Possibile Delta Scuti",
  "warnings": [],
  "llm_model": "claude-sonnet-4-20250514"
}
```

## Performance Attese

- **Tempo risposta**: 3-15 secondi (dipende da carico API)
- **Costo per analisi**: ~$0.01-0.02
- **Precisione classificazione**: Alta per tipi comuni (RR Lyr, Delta Sct, Cepheid)

## Prossimi Passi

Dopo il test iniziale, considera:

1. **Test su dataset variati**: Prova con diversi tipi di stelle
2. **Valida suggerimenti**: Verifica che i consigli abbiano senso scientifico
3. **Performance monitoring**: Traccia tempi di risposta e costi
4. **Feedback loop**: Annota casi dove l'AI sbaglia per miglioramenti futuri

## Supporto

Per problemi o domande:
- Leggi [AI_ADVISOR_README.md](agata/variable_stars/AI_ADVISOR_README.md)
- Controlla logs backend e console browser
- Verifica che la API key sia valida
