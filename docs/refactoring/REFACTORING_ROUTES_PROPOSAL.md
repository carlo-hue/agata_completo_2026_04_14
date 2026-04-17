# Proposta Refactoring: routes.py (2209 righe)

## Problema
Il file `agata/variable_stars/routes.py` è molto grande (2209 righe) e contiene logiche eterogenee:
- Caricamento dati
- Analisi periodogramma
- Phase folding
- Sigma clipping
- Gestione stato utente
- Calcolo estremi
- Allineamento zero-point
- AI Advisor con LLM

Questo rende il file:
- ❌ Difficile da navigare
- ❌ Complesso da testare (tutto accoppiato)
- ❌ Rischio merge conflict in team
- ❌ Viola Single Responsibility Principle

## Soluzione: Divisione in Moduli Tematici

### Struttura Proposta

```
agata/variable_stars/
├── __init__.py                    # Blueprint registration
├── routes/
│   ├── __init__.py                # Import e registrazione routes
│   ├── views.py                   # Rendering template (65 righe)
│   ├── data_routes.py             # Caricamento dati (155 righe)
│   ├── analysis_routes.py         # Periodogramma + multi-periodo (290 righe)
│   ├── phase_routes.py            # Phase folding (100 righe)
│   ├── quality_routes.py          # Sigma clipping + estremi (515 righe)
│   ├── calibration_routes.py     # Zero-point alignment (270 righe)
│   ├── ai_routes.py               # LLM Advisor (550 righe)
│   └── state_routes.py            # Persistenza stato (120 righe)
├── services/
│   ├── __init__.py
│   ├── arrow_parser.py            # Utility Arrow IPC
│   ├── statistics.py              # MAD, sigma-clipping helpers
│   ├── peak_detection.py          # find_peaks wrapper
│   └── llm_client.py              # AI provider abstraction
└── constants.py                   # MAX_SESSIONS, MIN_PERIOD, etc.
```

### Dettaglio Divisione

#### 1. `routes/views.py` (~10 righe)
```python
"""
Template rendering routes.
"""
from flask import render_template
from .. import variable_stars_bp

@variable_stars_bp.get("/")
def index():
    """Homepage AAAAT"""
    return render_template("variable_stars/index.html")
```

#### 2. `routes/data_routes.py` (~155 righe)
```python
"""
Data loading endpoints: lightcurve from DB or synthetic.
"""
from flask import request, Response, jsonify
import numpy as np
import pyarrow as pa
import pyarrow.ipc as ipc
from .. import variable_stars_bp
from agata.services.data_loader import get_lightcurve
from ..constants import MAX_SESSIONS

@variable_stars_bp.get("/api/lightcurve.arrow")
def api_lightcurve_arrow():
    """Carica curva di luce (DB o sintetica) in formato Arrow"""
    # ... (linee 81-236 dal file originale)
    pass
```

#### 3. `routes/analysis_routes.py` (~290 righe)
```python
"""
Periodogram analysis: Lomb-Scargle, multi-period pre-whitening.
"""
from flask import request, jsonify
import numpy as np
from astropy.timeseries import LombScargle
from .. import variable_stars_bp
from ..services.arrow_parser import read_arrow_table_from_request
from ..constants import MIN_PERIOD, MAX_PERIOD, MAX_N_FREQ

@variable_stars_bp.post("/api/periodogram.arrow")
def api_periodogram_arrow():
    """Calcola periodogramma Lomb-Scargle"""
    # ... (linee 268-400 dal file originale)
    pass

@variable_stars_bp.post("/api/multiperiod.arrow")
def api_multiperiod_arrow():
    """Analisi multi-periodo con pre-whitening"""
    # ... (linee 402-591 dal file originale)
    pass
```

#### 4. `routes/phase_routes.py` (~100 righe)
```python
"""
Phase folding endpoints (JSON and Arrow).
"""
from flask import request, jsonify, Response
import numpy as np
import pyarrow as pa
from .. import variable_stars_bp
from ..services.arrow_parser import read_arrow_table_from_request

@variable_stars_bp.post("/api/phase")
def api_phase_json():
    """Phase folding (JSON, backward compatible)"""
    # ... (linee 597-647)
    pass

@variable_stars_bp.post("/api/phase.arrow")
def api_phase_arrow():
    """Phase folding (Arrow, raccomandato)"""
    # ... (linee 649-730)
    pass
```

#### 5. `routes/quality_routes.py` (~515 righe)
```python
"""
Data quality analysis: sigma clipping, extrema detection.
"""
from flask import request, jsonify
import numpy as np
from scipy.signal import find_peaks
from astropy.stats import mad_std
from .. import variable_stars_bp
from ..services.arrow_parser import read_arrow_table_from_request
from ..services.statistics import robust_sigma_clip_per_session
from ..constants import DEFAULT_SIGMA_THRESHOLD, MIN_POINTS_PER_SESSION

@variable_stars_bp.post("/api/sigma_clip.arrow")
def api_sigma_clip_arrow():
    """Identifica outlier con MAD sigma clipping per sessione"""
    # ... (linee 736-976)
    pass

@variable_stars_bp.post("/api/extrema.arrow")
def api_compute_extrema_per_session():
    """Calcola massimi/minimi robusti per sessione"""
    # ... (linee 1126-1338)
    pass
```

#### 6. `routes/calibration_routes.py` (~270 righe)
```python
"""
Photometric calibration: zero-point alignment.
"""
from flask import request, jsonify
import numpy as np
from astropy.stats import sigma_clipped_stats, mad_std
from .. import variable_stars_bp
from ..services.arrow_parser import read_arrow_table_from_request
from ..services.statistics import weighted_median

@variable_stars_bp.post("/api/align_zeropoint.arrow")
def api_align_zeropoint():
    """Allinea sessioni fotometriche con zero-point calibration"""
    # ... (linee 1344-1613)
    pass
```

#### 7. `routes/ai_routes.py` (~550 righe)
```python
"""
AI-powered analysis advisor using LLM (Claude, Cerebras, OpenAI).
"""
from flask import request, jsonify
import numpy as np
import json
import os
from astropy.stats import mad_std
from .. import variable_stars_bp
from ..services.arrow_parser import read_arrow_table_from_request
from ..services.llm_client import get_ai_analysis
from ..constants import MIN_POINTS_PER_SESSION

@variable_stars_bp.post("/api/analyze_with_llm.arrow")
def api_analyze_with_llm():
    """Analizza sessioni con AI advisor"""
    # ... (linee 1619-2157)
    pass

def _generate_summary(analysis):
    """Genera riassunto da suggerimenti AI"""
    # ... (linee 2159-2190)
    pass

def _extract_warnings(session_stats):
    """Estrai warning critici"""
    # ... (linee 2192-2206)
    pass
```

#### 8. `routes/state_routes.py` (~120 righe)
```python
"""
User state persistence: save/load analysis state.
"""
from flask import request, jsonify, session as flask_session
import json
import uuid
from sqlalchemy.exc import SQLAlchemyError
from .. import variable_stars_bp
from agata.db import SessionLocal
from agata.models import UserState

def _get_state_id():
    """Ottieni o genera ID stato per sessione"""
    # ... (linee 982-998)
    pass

@variable_stars_bp.post("/api/state/save")
def api_state_save():
    """Salva stato applicazione"""
    # ... (linee 1000-1068)
    pass

@variable_stars_bp.get("/api/state/load")
def api_state_load():
    """Carica stato salvato"""
    # ... (linee 1070-1120)
    pass
```

### Servizi Condivisi

#### `services/arrow_parser.py`
```python
"""
Utility per parsing Apache Arrow IPC streams.
"""
import pyarrow as pa
import pyarrow.ipc as ipc
from flask import request

def read_arrow_table_from_request() -> pa.Table:
    """
    Legge tabella Arrow da body della richiesta POST.

    Returns:
        pa.Table: Tabella Arrow deserializzata

    Raises:
        ValueError: Se body vuoto o formato non valido
    """
    raw = request.get_data(cache=False)

    if not raw:
        raise ValueError("Body richiesta vuoto")

    reader = ipc.open_stream(pa.BufferReader(raw))
    return reader.read_all()
```

#### `services/statistics.py`
```python
"""
Statistical utilities: MAD, sigma-clipping, weighted median.
"""
import numpy as np
from astropy.stats import sigma_clipped_stats, mad_std

def robust_sigma_clip_per_session(session_mag, sigma=3.0, max_iters=5):
    """
    Esegue sigma-clipping robusto su array magnitudini.

    Uses MAD (Median Absolute Deviation) as robust estimator.

    Args:
        session_mag: Array magnitudini
        sigma: Soglia sigma per clipping
        max_iters: Iterazioni max

    Returns:
        tuple: (mean, median, std, n_clipped)
    """
    from astropy.stats import sigma_clip

    masked = sigma_clip(
        session_mag,
        sigma=sigma,
        maxiters=max_iters,
        stdfunc=mad_std
    )

    mean_clipped = np.mean(masked[~masked.mask])
    median_clipped = np.median(masked[~masked.mask])
    std_clipped = mad_std(masked[~masked.mask])
    n_clipped = masked.mask.sum() if hasattr(masked, 'mask') else 0

    return mean_clipped, median_clipped, std_clipped, n_clipped

def weighted_median(values, weights):
    """
    Calcola mediana pesata.

    Args:
        values: Array valori
        weights: Array pesi (stesso shape di values)

    Returns:
        float: Mediana pesata
    """
    sorted_idx = np.argsort(values)
    sorted_values = values[sorted_idx]
    sorted_weights = weights[sorted_idx]

    cumsum_weights = np.cumsum(sorted_weights)
    total_weight = cumsum_weights[-1]
    median_idx = np.searchsorted(cumsum_weights, total_weight / 2.0)

    return float(sorted_values[median_idx])
```

#### `services/llm_client.py`
```python
"""
Abstraction layer for AI providers (Claude, Cerebras, OpenAI).
"""
import os
import logging

logger = logging.getLogger(__name__)

class LLMClient:
    """Client unificato per provider AI"""

    def __init__(self, provider='cerebras'):
        self.provider = provider.lower()
        self._validate_api_key()

    def _validate_api_key(self):
        """Verifica che API key esista per provider"""
        key_map = {
            'cerebras': 'CEREBRAS_API_KEY',
            'claude': 'ANTHROPIC_API_KEY',
            'openai': 'OPENAI_API_KEY'
        }

        key_name = key_map.get(self.provider)
        if not key_name or not os.getenv(key_name):
            raise ValueError(f"API key mancante per {self.provider}: {key_name}")

    def chat_completion(self, prompt, max_tokens=4096, temperature=0.3):
        """
        Esegue chat completion con provider configurato.

        Args:
            prompt: Prompt testuale
            max_tokens: Token massimi risposta
            temperature: Creatività (0=deterministico, 1=creativo)

        Returns:
            str: Risposta del modello
        """
        if self.provider == 'cerebras':
            return self._cerebras_completion(prompt, max_tokens, temperature)
        elif self.provider == 'claude':
            return self._claude_completion(prompt, max_tokens, temperature)
        elif self.provider == 'openai':
            return self._openai_completion(prompt, max_tokens, temperature)
        else:
            raise ValueError(f"Provider non supportato: {self.provider}")

    def _cerebras_completion(self, prompt, max_tokens, temperature):
        from openai import OpenAI

        client = OpenAI(
            api_key=os.getenv('CEREBRAS_API_KEY'),
            base_url="https://api.cerebras.ai/v1"
        )

        completion = client.chat.completions.create(
            model="llama-3.3-70b",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature
        )

        return completion.choices[0].message.content

    def _claude_completion(self, prompt, max_tokens, temperature):
        from anthropic import Anthropic

        client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}]
        )

        return message.content[0].text

    def _openai_completion(self, prompt, max_tokens, temperature):
        from openai import OpenAI

        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature
        )

        return completion.choices[0].message.content

def get_ai_analysis(prompt, provider='cerebras'):
    """
    Helper function per ottenere analisi AI.

    Args:
        prompt: Prompt da inviare
        provider: Provider AI ('cerebras', 'claude', 'openai')

    Returns:
        str: Risposta AI
    """
    client = LLMClient(provider)
    return client.chat_completion(prompt)
```

#### `constants.py`
```python
"""
Global constants for variable stars analysis.
"""

# Limiti validazione input
MAX_SESSIONS = 50          # Massimo numero sessioni sintetiche
MAX_PERIOD = 1000.0        # Periodo massimo [giorni]
MIN_PERIOD = 0.001         # Periodo minimo [giorni]
MAX_N_FREQ = 50000         # Massimo frequenze nel periodogramma
DEFAULT_SIGMA_THRESHOLD = 3.0  # Sigma clipping default
MIN_POINTS_PER_SESSION = 5     # Minimo punti per statistiche affidabili

# AI Provider configuration
DEFAULT_AI_PROVIDER = 'cerebras'  # Default gratuito
SUPPORTED_AI_PROVIDERS = ['cerebras', 'claude', 'openai']
```

### Registrazione Routes

#### `routes/__init__.py`
```python
"""
Centralized route registration for variable_stars blueprint.
"""
from flask import Blueprint

# Import routes (questo registra i decorator @bp.route automaticamente)
from . import (
    views,
    data_routes,
    analysis_routes,
    phase_routes,
    quality_routes,
    calibration_routes,
    ai_routes,
    state_routes
)

__all__ = [
    'views',
    'data_routes',
    'analysis_routes',
    'phase_routes',
    'quality_routes',
    'calibration_routes',
    'ai_routes',
    'state_routes'
]
```

#### `agata/variable_stars/__init__.py` (modificato)
```python
"""
Variable stars analysis blueprint.
"""
from flask import Blueprint

# Crea blueprint
variable_stars_bp = Blueprint(
    'variable_stars',
    __name__,
    url_prefix='/agata/variable_stars',
    template_folder='../../templates'
)

# Import routes (questo registra tutti gli endpoint)
from . import routes

__all__ = ['variable_stars_bp']
```

### Piano di Migrazione

#### Fase 1: Preparazione (NO Breaking Changes)
1. Crea nuova struttura directory `routes/` e `services/`
2. Estrai `constants.py`
3. Estrai utility in `services/` (arrow_parser, statistics, llm_client)
4. Test: tutti i test passano ancora

#### Fase 2: Divisione Graduale
1. Sposta `views.py` (semplice, poche dipendenze)
2. Sposta `data_routes.py`
3. Sposta `state_routes.py`
4. Test dopo ogni spostamento

#### Fase 3: Analisi Routes
1. Sposta `analysis_routes.py`
2. Sposta `phase_routes.py`
3. Sposta `quality_routes.py`
4. Sposta `calibration_routes.py`
5. Test

#### Fase 4: AI Routes (ultima, più complessa)
1. Refactor LLM client in service
2. Sposta `ai_routes.py`
3. Test completi

#### Fase 5: Cleanup
1. Elimina `routes.py` originale
2. Aggiorna import in test
3. Update documentation

### Vantaggi Refactoring

✅ **Leggibilità**: File piccoli (100-300 righe) facili da navigare
✅ **Testabilità**: Test isolati per ogni modulo
✅ **Manutenibilità**: Modifiche locali, meno side-effects
✅ **Scalabilità**: Aggiungi nuove routes senza toccare file esistenti
✅ **Team-friendly**: Meno merge conflict, ownership chiaro
✅ **Riusabilità**: Services usabili da altre parti dell'app

### Metriche

| Metrica | Prima | Dopo |
|---------|-------|------|
| Righe/file max | 2209 | ~550 |
| File totali | 1 | 12 |
| Coupling | Alto | Basso |
| Test isolation | No | Sì |
| Import time | Lungo | Corto |

### Compatibilità

✅ **Zero breaking changes**: endpoint URLs invariati
✅ **API contract**: request/response identici
✅ **Frontend**: nessuna modifica necessaria
✅ **Deploy**: drop-in replacement

### Stima Effort

- Extraction utility services: **2-3 ore**
- Split routes (8 file): **4-6 ore**
- Testing completo: **2-3 ore**
- Documentation update: **1 ora**

**Totale: 1-1.5 giorni lavoro**

### Priorità

**HIGH**: Questo refactoring è raccomandato perché:
1. File già difficile da mantenere (2200+ righe)
2. Crescita futura prevista (nuovi endpoint AI, filtri, export)
3. Setup ideale per contributi team (moduli indipendenti)
4. Migliora drasticamente developer experience

---

## Domande?

- Preferenze naming convention per routes?
- Test coverage target (attualmente quant'è)?
- CI/CD: test automatici su PR?
