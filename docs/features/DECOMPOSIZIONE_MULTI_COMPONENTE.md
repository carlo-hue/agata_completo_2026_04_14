# Decomposizione Multi-Componente — Guida Completa

**Versione**: 1.0
**Data**: Febbraio 2026
**Modulo**: Tab "🔬 Decomposizione" nell'editor Variable Stars

---

## Cosa Fa

La tab **Decomposizione** è uno strumento professionale per analizzare curve di luce di stelle variabili che contengono **fenomeni simultanei**:

- 🎼 **Pulsazioni multi-modo** (RR Lyrae, δ Scuti, γ Dor)
- 🌙 **Eclissi binarie** + pulsazioni
- 🔄 **Rotazione stellare** con macchie
- ⚡ **Flares** transitori
- 🔴 **Rumore rosso** (correlato nel tempo)

Ti permette di separare visualmente e quantitativamente queste componenti usando quattro strumenti complementari.

---

## Quick Start

1. Apri l'editor Variable Stars
2. Vai al tab **"🔬 Decomposizione"**
3. Calcola il **Periodogramma** dal tab **"Periodogramma"** (se non l'hai già fatto)
4. Il periodo si sincronizza automaticamente da "Analisi in Fase"
5. Clicca uno dei quattro bottoni analisi

---

## I Quattro Strumenti

### 1️⃣ ⚡ Quick FFT — FFT Cliente-Side Istantanea

**Quando usarlo**: Per una preview veloce dello spettro di potenza

**Cosa fa**:
- Calcola FFT su dati **in fase** (binned su 2048 bin)
- Mostra lo spettro di potenza fino a 15 cicli/fase
- Identifica automaticamente armoniche significative (SNR > 3)
- **Istantaneo** — nessuna chiamata server

**Output**:
- Grafico sinistra: spettro FFT in log-scale (Power Spectrum)
- Grafico destra: segnale in fase binned (curva smooth)
- Tabella: # armonica, frequenza, ampiezza, SNR

**Interpretazione**:
- Armoniche con ⭐ hanno SNR > 3 (significative)
- Se vedi picchi nitidi: il segnale è **ben sinusoidale** (RRab, Cefeide)
- Se vedi lo spettro "sporco": **rumore** o **fenomeni complessi** (rotazione, eclissi)

**Esempio RRab**:
```
1× f₀: Ampiezza=0.35 mag, SNR=45 ⭐
2× f₀: Ampiezza=0.10 mag, SNR=12 ⭐  ← R21=0.29 (RRab signature)
3× f₀: Ampiezza=0.03 mag, SNR=4  ⭐
```

---

### 2️⃣ 📈 Fourier Fit — Decomposizione Fourier N-Armoniche + Simon & Lee

**Quando usarlo**: Per classificare il tipo di stella e quantificare la forma della curva in fase

**Cosa fa** (server-side):
1. Phase-fold i dati al periodo specificato
2. Fit sinusoidale multi-armonica (lstsq): `m(φ) = A₀ + Σ[aₖ·sin(2πkφ) + bₖ·cos(2πkφ)]`
3. Calcola parametri Simon & Lee: `R₂₁ = A₂/A₁`, `φ₂₁ = φ₂ - 2φ₁`, ...
4. Classifica automaticamente (RRab? RRc? Cefeide?)
5. Calcola residui e morfologia (skewness, kurtosis)

**Output**:
- **Grafico sinistra**: Dati in fase + overlay fit Fourier (rosso)
- **Grafico destra**: Residui in fase (scarto dal fit)
- **Tabella**: Per ogni armonica k:
  - Ampiezza (mag)
  - Fase (rad)
  - SNR
- **Panel Simon & Lee**:
  - R₂₁, φ₂₁ (se ≥2 armoniche)
  - R₃₁, φ₃₁ (se ≥3 armoniche)
  - Regioni di classificazione RRab/RRc/Cefeide

**Parametri**:
- **Periodo**: Sincronizzato dal tab "Analisi in Fase", oppure modifica manualmente
- **N armoniche**: 4-12 (default 8). Aumenta per segnali complessi

**Come Interpretare — Diagramma Simon & Lee (R₂₁ vs φ₂₁)**:

| Regione | R₂₁ | φ₂₁ (rad) | Classificazione |
|---------|-----|----------|-----------------|
| RRab | 0.20–0.55 | 3.5–5.5 | RR Lyrae Fond. (ab-type) |
| RRc | 0.02–0.20 | 2.5–5.0 | RR Lyrae primo overtone |
| Cefeide | 0.10–0.50 | Varia | Classica + longer period |
| δ Scuti | >0.1 | Sparsa | Se P < 0.3 d |

**Interpretazione Residui**:
- **RMS piccolo** (<0.01 mag) → Segnale **puro sinusoidale**
- **RMS grande** (>0.05 mag) → Segnale **complesso** o **rumore** (usa GP per modellare meglio)
- **Residui non casuali** (pattern) → Indicano **componenti aggiuntive** (flares, eclissi, etc.)

**Esempio Reale — RRab**:
```
Periodo: 0.5729 d
N armoniche: 8

Tabella Armoniche:
  1× f₀: A=0.346 mag, SNR=52
  2× f₀: A=0.103 mag, SNR=18
  3× f₀: A=0.038 mag, SNR=7
  ...

Simon & Lee:
  R₂₁ = 0.298
  φ₂₁ = 4.12 rad
  R₃₁ = 0.109
  φ₃₁ = 2.89 rad

  → CLASSIFICAZIONE: RRab (Jurcsik & Kovacs 1996)

Residui:
  RMS = 0.0087 mag ✓ (stella pura)
  Skewness = -0.23 (leggermente asimmetrica)
  Kurtosis = 2.1 (coda normale)
```

---

### 3️⃣ 🔁 Pre-Whitening — Decomposizione Iterativa Multi-Componente

**Quando usarlo**: Per identificare **tutte le componenti periodiche** in una stella multi-periodica (RR Lyrae multi-modo, δ Scuti, binaria + pulsazione)

**Cosa fa** (server-side, nel dominio del tempo):
1. Lomb-Scargle sul dataset completo → trova **primo** periodo dominante
2. Fourier fit multi-armonica a quel periodo
3. Sottrae modello dai dati (pre-whiten)
4. Ripete sul residuo per trovare **seconda** componente
5. Continua fino a 6 iterazioni o SNR < 4

**Output**:
- **Grafico sinistra**: Periodogrammi sovrapposti (uno per step)
  - Grigio (background): spettro originale
  - Colori: spettro residuo ad ogni step
  - Linea rossa tratteggiata: soglia FAP 0.1%
- **Grafico destra**: Curva RMS vs step (riduzione rumore)
- **Tabella**: Per ogni step:
  - Periodo trovato
  - Frequenza
  - Ampiezza prima armonica (A₁)
  - SNR
  - FAP (significatività)
  - % Riduzione RMS
- **Summary**: RMS finale, riduzione totale %, numero componenti

**Come Leggerlo**:

```
Step 1: P = 0.5729 d, A₁ = 0.346 mag, SNR = 52, FAP < 0.001
        RMS: 0.1543 → 0.0892 (42.1% riduzione)
        ✓ Componente significativa

Step 2: P = 0.3954 d, A₁ = 0.042 mag, SNR = 8.2, FAP = 0.001
        RMS: 0.0892 → 0.0845 (5.3% riduzione)
        ✓ Possibile overtone (δ Scuti multi-modo)

Step 3: P = 2.1634 d, A₁ = 0.008 mag, SNR = 3.1, FAP = 0.05
        RMS: 0.0845 → 0.0831 (1.7% riduzione)
        ⚠ Marginal (rumore?, effetto alias?)

STOP: SNR < 4, riduzione < 3%

CONCLUSIONE: Stella **multi-periodica** con:
  - Componente principale P₁ = 0.5729 d (RRab)
  - Possibile overtone P₂ = 0.3954 d (overtone primo RRab)
  - Rumore residuo RMS = 0.0831 mag
```

**Parametri**:
- **N armoniche per step**: Quante armoniche fitta ad ogni componente (default 4)
- **N iterazioni massime**: Quante componenti cercare (max 10, default 6)

**Quando Fermarsi**:
- SNR del picco < 4 → **Non significativo** (rumore)
- Riduzione RMS < 3% → **Non migliora** il fit
- FAP > 0.01 → Meno del **1% probabilità reale** (potrebbe essere alias)

---

### 4️⃣ 🌊 GP Model — Gaussian Process per Segnali Non-Sinusoidali

**Quando usarlo**: Per modellare curve complesse, non-sinusoidali: rotazione con macchie, eclissi parziali, flares, "beating" tra pulsazioni

**Cosa fa** (server-side, celerite2, nel dominio del tempo):
1. Stima errore fotometrico (MAD-based)
2. Costruisce kernel Gaussian Process (SHOTerm / Matérn32)
3. Ottimizza iperparametri via log-space + L-BFGS-B
4. Predice su griglia fine con **bande di incertezza ±2σ**
5. Calcola residui e log-likelihood

**Output**:
- **Grafico sinistra**:
  - Dati raw (blu, semi-trasparenti)
  - Predizione GP media (viola, linea spessa)
  - Bande ±2σ (viola, ombreggiato)
- **Grafico destra**: Residui nel tempo (sparsi attorno a zero)
- **Panel Info**: Kernel usato, periodo stimato, RMS residui, log-likelihood, parametri

**Kernels Disponibili**:

| Kernel | Uso | Formula |
|--------|-----|---------|
| **Quasi-periodico** (default) | Stella con rotazione + macchie, eclissi parziali | SHOTerm underdamped: oscillazione smorzata |
| **SHO** | Oscillatore stocastico puro | SHOTerm con Q libero |
| **Matérn-3/2** | Rumore rosso correlato (variabilità lenta) | Kernel Matérn: decadimento esponenziale |

**Iperparametri (in output)**:
- `sigma`: Ampiezza della variabilità (mag)
- `rho` (o `periodo`): Scala temporale caratteristica (giorni)
- `tau`: Tempo di decadimento (solo SHO) — quanto rapidamente l'oscillazione si smorza

**Interpretazione**:

```
Kernel: Quasi-periodico
Periodo stimato: 1.234 d  ← Periodo rotazione
sigma: 0.087 mag         ← Ampiezza variabilità da macchie
tau: 12.34 d             ← Quanto velocemente si smorza

RMS residui: 0.012 mag   ← Bontà del fit
log-likelihood: 245.3    ← "Verosimiglianza" del modello

Interpretazione:
  Stella con macchie rotanti, periodo = 1.234 d
  Variabilità ≈ 0.087 mag (compatibile con macchie ~10% della superficie)
  Decadimento tau=12.34d suggerisce **morfologia stabile** per ~2 settimane
```

**Quando Usare Ogni Kernel**:

- **Quasi-periodico** (predefinito):
  - Stelle con rotazione visibile + macchie
  - Eclissi binaria con pulsazioni
  - δ Scuti in rotazione
  - **Consigliato per start**

- **SHO**:
  - Se vuoi solo oscillazione senza decadimento
  - Sistemi molto stazionari

- **Matérn-3/2**:
  - Variabili lente (Mira, semi-regolari)
  - Rumore fotometrico correlato (long-term trends)
  - Quando la stella NON ha periodicità netta

---

## Workflow Consigliato

### Scenario 1: Stella Nuova — Scopri Che Tipo È

```
1. Vai a "Periodogramma" → calcola Lomb-Scargle → copia periodo
2. Vai a "Decomposizione"
3. Incolla periodo in [Periodo (d)]
4. Clicca ⚡ Quick FFT
   → Vedi lo spettro di potenza
   → Armoniche significative?

5. Se FFT è "pulito" (pochi picchi, ben definiti):
   → Clicca 📈 Fourier Fit
   → Leggi il diagramma Simon & Lee
   → Sistema classifica la stella automaticamente

6. Se FFT è "sporco" o vedi pattern complessi:
   → Clicca 🌊 GP Model (scegli kernel Quasi-periodico)
   → Vedi se le bande di incertezza catturano il segnale
```

### Scenario 2: RR Lyrae — Classifica Come ab o c

```
1. Calcola periodo (tab Periodogramma)
2. Va a Decomposizione, incolla periodo
3. Clicca 📈 Fourier Fit (N armoniche = 8)
4. Guarda il diagramma Simon & Lee:

   ✓ R21=0.25–0.55, φ21=3.5–5.5? → RRab
   ✓ R21=0.02–0.20, φ21=2.5–5.0? → RRc

5. Confronta con tabelle Jurcsik & Kovacs 1996 in letteratura
```

### Scenario 3: Stella Multi-Periodica — Trova Tutte le Componenti

```
1. Periodogramma → copia il primo periodo massimo
2. Decomposizione, incolla periodo
3. Clicca 🔁 Pre-Whitening (N harmoniche/step = 4-6)
4. Leggi la tabella: quante componenti trovate?
5. Salva i periodi trovati
6. Per ciascun periodo:
   - Torna al tab "Analisi in Fase"
   - Cambia periodo
   - Clicca 📈 Fourier Fit
   - Vedi la forma in fase di quella componente
```

### Scenario 4: Rotazione Stellare + Macchie — Analizza la Morfologia

```
1. Dal Periodogramma, trova il periodo rotazione (tipicamente 1-100 giorni)
2. Decomposizione, incolla periodo
3. Clicca 🌊 GP Model (kernel = Quasi-periodico)
4. Leggi i parametri:
   - sigma = ampiezza macchie
   - rho = periodo rotazione (dovrebbe matchare il tuo periodo)
   - tau = stabilità macchie (quanto a lungo persistono?)
5. Se tau >> rho:
   → Macchie stabili (vivono per settimane)
6. Se tau ≈ rho:
   → Macchie effimere (cambiano ogni rotazione)
```

---

## Confronto con Tab "Analisi in Fase"

| Feature | Analisi in Fase | Decomposizione |
|---------|-----------------|-----------------|
| **Periodo** | Visuale, fine-tuning manuale | Auto-sync + visualizzazione quantitativa |
| **Fit** | Polinomiale (detrend) | Fourier N-armoniche + GP |
| **Output** | Curva in fase + polinomio | Parametri Simon & Lee, periodogrammi, residui |
| **Componenti Multiple** | ✗ | ✓ (Pre-Whitening trova tutte) |
| **Classificazione** | ✗ | ✓ (Automatica da Simon & Lee) |
| **Non-Sinusoidale** | ✗ | ✓ (GP per rotazione, eclissi) |
| **Export** | Slack export | Residui, parametri nel DOM |

**In pratica**:
- **"Analisi in Fase"** = regola il periodo manualmente, vedi la curva in fase
- **"Decomposizione"** = analizza quantitativamente: armoniche, componenti, tipo di stella

---

## Buone Pratiche

### 1. Sempre Partire da Periodogramma Accurato
Se il periodo è sbagliato di 0.001 d, il Fourier fit sarà pessimo. Vai al tab Periodogramma prima.

### 2. Ordine Consigliato: FFT → Fourier → Pre-Whiten → GP
Non serve eseguirli tutti, ma l'ordine logico è:
1. ⚡ FFT (capire se il segnale è sinusoidale)
2. 📈 Fourier (classificare, parametri Simon & Lee)
3. 🔁 Pre-Whiten (se sospetti multi-componenti)
4. 🌊 GP (se residui non casuali, segnale complesso)

### 3. Salvare i Risultati
- Screenshot del **diagramma Simon & Lee** (best per report)
- Tabella **Fourier**: ampiezze, SNR
- Tabella **Pre-Whitening**: periodi + amplitudini
- **RMS residui finale** e **log-likelihood GP**

### 4. Quando Usare GP Instead di Fourier
- Residui Fourier non casuali (pattern visibile)? → GP
- RMS Fourier > 0.02 mag? → Prova GP
- Stella con rotazione + macchie? → Usa sempre GP Quasi-periodico
- Variabile lenta (Mira)? → Usa GP Matérn32

### 5. Validazione Interna
- **FAP < 0.01** in Pre-Whitening → componente reale (99% confidence)
- **SNR > 5** in Fourier → armonica ben definita
- **2σ bands catturano i dati** in GP → fit buono (95% of points dentro le bande)

---

## Troubleshooting

### GP Model Dice "celerite2 Non Installato" (HTTP 501)
Il server non ha celerite2. Contatta l'admin per installarlo:
```bash
pip install celerite2
```

### Fourier Fit Mostra Residui Grandi
- Aumenta `N armoniche` (da 8 a 12-15)
- Controlla il periodo (vai a "Periodogramma" e verifica)
- Se residui rimangono non-casuali → usa GP Model

### Pre-Whitening Si Ferma dopo Step 1
- Probabilmente la stella è sinusoidale pura (RRab semplice)
- Step 2+ trovano solo rumore (SNR < 4)
- È normale ✓

### Diagramma Simon & Lee Mostra Punto Fuori dalle Regioni
- La stella potrebbe essere:
  - Un ibrido (RRab + pulsazioni rapide)
  - Una variabile insolita
  - Mal classificata
- Consulta cataloghi VSX / GCVS per confermare

---

## Performance & Limiti

| Metric | Valore | Note |
|--------|--------|------|
| Quick FFT | <100 ms | Client-side, istantaneo |
| Fourier Fit | ~2-5 s | Dipende da N armoniche |
| Pre-Whitening | ~10-30 s | 6 iterazioni, 10K freq |
| GP Model | ~20-120 s | Ottimizzazione L-BFGS-B |
| Max Punti Pre-Whiten | 500K | Downsampling automatico |
| Max Punti GP | 10K | Downsampling a 10K se più |

---

## Letteratura & Riferimenti

- **Simon & Lee (1981)**: Classification of RR Lyrae Stars via Fourier Parameters — diagramma R₂₁ vs φ₂₁
- **Jurcsik & Kovacs (1996)**: Classification of RR Lyrae Variables — parametri diagnostici ottimali
- **Soszynski et al. (2009)**: Variability Type Classification in OGLE-III
- **Rasmussen & Williams (2006)**: Gaussian Processes for Machine Learning — teoria GP
- **celerite2**: Fast Gaussian Processes in PyTorch — https://celerite2.readthedocs.io/

---

## Contatti & Feedback

Per domande sulla tab "Decomposizione", consultare:
- **CLAUDE.md** — Documentazione generale architettura
- **ARCHITECTURE.md** — Principi di design
- Tab **"🤖 AI Advisor"** — Chiedi a Claude per interpretazione stellare

