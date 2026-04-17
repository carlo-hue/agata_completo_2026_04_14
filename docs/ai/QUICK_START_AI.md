# ⚡ Quick Start - AI Advisor con Cerebras (5 minuti)

## 1️⃣ Ottieni Chiave API Gratuita

1. Vai su **https://inference.cerebras.ai/**
2. Click **"Sign Up"** (usa GitHub per velocità)
3. Vai su **https://cloud.cerebras.ai/platform**
4. Click **"API Keys"** → **"Create new API key"**
5. **Copia la chiave** (inizia con `csk-...`)

## 2️⃣ Configura

```bash
export AI_PROVIDER=cerebras
export CEREBRAS_API_KEY="csk-TUA_CHIAVE_QUI"
```

## 3️⃣ Test

```bash
./test_anthropic_setup.py
```

Dovresti vedere:
```
✅ TUTTI I TEST PASSATI!
🚀 AI Advisor pronto per l'uso con CEREBRAS
💰 Costo: $0.00 - COMPLETAMENTE GRATUITO! 🎉
```

## 4️⃣ Riavvia Flask

```bash
# Se systemd
sudo systemctl restart astrogen

# Se manuale
python app.py
```

## 5️⃣ Usa AI Advisor!

1. Apri http://localhost:5000/agata/variable-stars/
2. Carica dati (es: sintetici Multi-Periodo)
3. Tab **"🤖 AI Advisor"**
4. Click **"✨ Analizza Ora"**
5. **DONE!** ✨

---

## Troubleshooting Veloce

**Errore API key?**
```bash
echo $CEREBRAS_API_KEY  # Verifica sia impostata
```

**Errore libreria?**
```bash
./flask/bin/pip install openai==1.59.5
```

**Altri problemi?**
Leggi [CEREBRAS_SETUP.md](CEREBRAS_SETUP.md) per guida completa.

---

## Perché Cerebras?

| Feature | Cerebras | Claude | OpenAI |
|---------|----------|--------|--------|
| **Costo** | **$0.00** 🎉 | $0.01-0.02 | $0.03-0.05 |
| **Qualità** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Velocità** | ⚡⚡⚡ | ⚡⚡ | ⚡⚡ |
| **Setup** | 2 min | 2 min | 2 min |

**Verdict**: Per test e uso normale → **Cerebras** 🏆

---

Buon divertimento! 🚀
