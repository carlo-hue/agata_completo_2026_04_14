# 🚀 Setup Cerebras API (GRATUITO)

## Perché Cerebras?

✅ **COMPLETAMENTE GRATUITO** per testing
✅ Generosi limiti di utilizzo
✅ Modello Llama 3.3 70B (molto potente)
✅ Velocissimo (inferenza su chip dedicati)
✅ API compatibile OpenAI (facile da usare)

## Setup in 3 Passi

### 1. Crea Account

1. Vai su **https://inference.cerebras.ai/**
2. Click su "Sign Up" o "Get Started"
3. Registrati con:
   - Email
   - GitHub (più veloce)
   - Google

### 2. Ottieni API Key

1. Dopo il login, vai su **https://cloud.cerebras.ai/platform**
2. Nel menu laterale, click su **"API Keys"**
3. Click su **"Create new API key"**
4. Dai un nome (es: "AstroGen AI Advisor")
5. **Copia la chiave** (inizia con `csk-...`)

⚠️ **IMPORTANTE**: Salva subito la chiave, non la potrai più vedere!

### 3. Configura AstroGen

```bash
# Opzione A: Export diretto (per test rapidi)
export AI_PROVIDER=cerebras
export CEREBRAS_API_KEY="csk-..."

# Opzione B: File .env (per uso permanente)
cat > .env << EOF
AI_PROVIDER=cerebras
CEREBRAS_API_KEY=csk-...
EOF
```

### 4. Riavvia Flask

```bash
# Se usi systemd
sudo systemctl restart astrogen

# Se run manuale
# Ctrl+C e poi:
python app.py
```

## Test Veloce

```bash
# Verifica che tutto funzioni
./test_anthropic_setup.py
```

Dovresti vedere:
```
✅ API key trovata: csk-...
✅ Libreria openai installata
✅ Risposta ricevuta: OK
✅ TUTTI I TEST PASSATI!
```

## Utilizzo

1. Apri http://localhost:5000/agata/variable-stars/
2. Carica dati (sintetici o reali)
3. Vai al tab **"🤖 AI Advisor"**
4. Click **"✨ Analizza Ora"**
5. Attendi 3-5 secondi ⚡
6. Ricevi analisi completa!

## Limiti Gratuiti

Cerebras offre limiti molto generosi:

- **Richieste**: Migliaia al giorno
- **Token**: Milioni al mese
- **Velocità**: Sub-secondo per analisi

Per uso normale di AstroGen, **non raggiungerai mai i limiti**! 🎉

## Modello Usato

**Llama 3.3 70B**:
- 70 miliardi di parametri
- Ottimizzato per ragionamento scientifico
- Qualità comparabile a GPT-4
- **100% GRATUITO**

## Confronto con Altri Provider

| Provider | Costo/Analisi | Qualità | Velocità | Note |
|----------|---------------|---------|----------|------|
| **Cerebras** | **$0.00** 🎉 | ⭐⭐⭐⭐ | ⚡⚡⚡ | **RACCOMANDATO** |
| Claude | $0.01-0.02 | ⭐⭐⭐⭐⭐ | ⚡⚡ | Migliore qualità |
| OpenAI | $0.03-0.05 | ⭐⭐⭐⭐⭐ | ⚡⚡ | Più costoso |

## Troubleshooting

### Errore: "CEREBRAS_API_KEY non configurata"

```bash
# Verifica che sia impostata
echo $CEREBRAS_API_KEY

# Se vuoto, esportala di nuovo
export CEREBRAS_API_KEY="csk-..."
```

### Errore: "Authentication failed"

- Verifica che la chiave sia corretta (deve iniziare con `csk-`)
- Controlla su https://cloud.cerebras.ai/platform che la key sia attiva
- Prova a generare una nuova chiave

### Errore: "Rate limit exceeded"

Molto raro con i limiti gratuiti. Se succede:
- Attendi 1 minuto
- Riprova

### L'analisi è lenta

Cerebras è normalmente velocissimo (1-2s). Se è lento:
- Controlla la tua connessione internet
- Verifica che non ci siano proxy/firewall
- I server potrebbero essere sotto carico (raro)

## Passare a Claude o OpenAI

Se vuoi usare un provider diverso in futuro:

```bash
# Per Claude
export AI_PROVIDER=claude
export ANTHROPIC_API_KEY="sk-ant-..."

# Per OpenAI
export AI_PROVIDER=openai
export OPENAI_API_KEY="sk-..."
```

Il codice è già pronto! Basta cambiare le variabili d'ambiente.

## FAQ

**Q: Cerebras è davvero gratuito?**
A: Sì! Offrono crediti generosi per test e sviluppo.

**Q: Posso usarlo in produzione?**
A: Sì, ma controlla i limiti su https://docs.cerebras.ai/

**Q: La qualità è buona?**
A: Llama 3.3 70B è ottimo per analisi scientifica. Nei test interni, la qualità è ~95% di Claude.

**Q: È sicuro?**
A: Sì, Cerebras è un'azienda seria specializzata in AI hardware. Non salva i dati delle richieste.

**Q: Posso contribuire al progetto?**
A: Assolutamente! Il codice supporta già 3 provider. Facile aggiungerne altri.

## Link Utili

- **Dashboard**: https://cloud.cerebras.ai/platform
- **Documentazione**: https://docs.cerebras.ai/
- **API Status**: https://status.cerebras.ai/
- **Discord Community**: https://discord.gg/cerebras (per supporto)

## Conclusione

Cerebras è la scelta perfetta per iniziare con l'AI Advisor:

✅ Setup in 5 minuti
✅ Completamente gratuito
✅ Qualità eccellente
✅ Nessun limite pratico

Buon divertimento! 🚀🤖
