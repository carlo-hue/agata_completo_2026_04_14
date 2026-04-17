"""
constants.py - Costanti globali per analisi curve di luce

Questo modulo contiene tutte le costanti di configurazione usate
dall'applicazione per validazione input, limiti, e soglie predefinite.
"""

# ==========================================================
# VALIDAZIONE INPUT - LIMITI
# ==========================================================

# Sessioni sintetiche
MAX_SESSIONS = 50              # Massimo numero sessioni sintetiche
MIN_POINTS_PER_SESSION = 5     # Minimo punti per statistiche affidabili

# Periodi
MAX_PERIOD = 4000.0            # Periodo massimo [giorni] - ZTF baseline ~10 anni
MIN_PERIOD = 0.001             # Periodo minimo [giorni]

# Periodogramma
MAX_N_FREQ = 20000             # Massimo frequenze nel periodogramma

# Decomposizione multi-componente
MAX_HARMONICS = 15             # Massimo armoniche per Fourier fit
MAX_PREWHITEN_ITERATIONS = 10  # Massimo iterazioni pre-whitening
GP_MAX_POINTS = 10000          # Massimo punti per GP (downsample se più)

# ==========================================================
# ANALISI - SOGLIE PREDEFINITE
# ==========================================================

# Sigma clipping
DEFAULT_SIGMA_THRESHOLD = 3.0  # Sigma clipping default

# ==========================================================
# TIPI STELLE SINTETICHE SUPPORTATI
# ==========================================================

ALLOWED_SYNTHETIC_KINDS = {
    "rrlyrae",
    "delta_scuti",
    "eclipsing",
    "cepheid",
    "irregular",
    "multiperiod"
}
