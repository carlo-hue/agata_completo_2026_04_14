"""
fourier.py - Fourier decomposition e classificazione Simon & Lee

Funzioni pure per:
- Fourier least-squares fit su dati phase-folded
- Parametri Simon & Lee (R21, φ21, R31, φ31)
- Classificazione tipo variabile da Fourier + periodo
"""

import numpy as np


def fourier_fit(phase, mag, n_harmonics):
    """
    Fourier least-squares fit su dati phase-folded.

    Modello: m(φ) = A0 + Σ_k [a_k·sin(2πkφ) + b_k·cos(2πkφ)]

    Args:
        phase: Array fase (0-1)
        mag: Array magnitudini
        n_harmonics: Numero armoniche

    Returns:
        dict con coefficients, amplitudes, phases, fitted values, residuals
    """
    n = len(phase)
    n_cols = 1 + 2 * n_harmonics  # intercept + sin/cos pairs

    # Design matrix
    X = np.ones((n, n_cols))
    for k in range(1, n_harmonics + 1):
        angle = 2 * np.pi * k * phase
        X[:, 2 * k - 1] = np.sin(angle)
        X[:, 2 * k] = np.cos(angle)

    # Solve least-squares
    coeffs, residual_sum, _, _ = np.linalg.lstsq(X, mag, rcond=None)

    A0 = coeffs[0]
    fitted = X @ coeffs
    residuals = mag - fitted
    rms = float(np.sqrt(np.mean(residuals ** 2)))

    # Extract amplitudes and phases per harmonic
    harmonics = []
    for k in range(1, n_harmonics + 1):
        a_k = coeffs[2 * k - 1]  # sin coefficient
        b_k = coeffs[2 * k]      # cos coefficient
        R_k = float(np.sqrt(a_k ** 2 + b_k ** 2))
        phi_k = float(np.arctan2(a_k, b_k))
        harmonics.append({
            "k": k,
            "amplitude": R_k,
            "phase": phi_k,
            "a_k": float(a_k),
            "b_k": float(b_k)
        })

    return {
        "A0": float(A0),
        "harmonics": harmonics,
        "fitted": fitted,
        "residuals": residuals,
        "rms": rms,
        "coeffs": coeffs
    }


def simon_lee_params(harmonics):
    """
    Calcola parametri di Simon & Lee per classificazione.

    R21 = R2/R1, φ21 = φ2 - 2·φ1 (mod 2π)
    R31 = R3/R1, φ31 = φ3 - 3·φ1 (mod 2π)

    Riferimento: Simon & Lee 1981, ApJ 248, 291
    """
    if len(harmonics) < 2:
        return {}

    R1 = harmonics[0]["amplitude"]
    if R1 < 1e-10:
        return {}

    result = {}

    if len(harmonics) >= 2:
        R2 = harmonics[1]["amplitude"]
        phi1 = harmonics[0]["phase"]
        phi2 = harmonics[1]["phase"]
        result["R21"] = float(R2 / R1)
        result["phi21"] = float((phi2 - 2 * phi1) % (2 * np.pi))

    if len(harmonics) >= 3:
        R3 = harmonics[2]["amplitude"]
        phi1 = harmonics[0]["phase"]
        phi3 = harmonics[2]["phase"]
        result["R31"] = float(R3 / R1)
        result["phi31"] = float((phi3 - 3 * phi1) % (2 * np.pi))

    if len(harmonics) >= 4:
        R4 = harmonics[3]["amplitude"]
        result["R41"] = float(R4 / R1)

    return result


def classify_from_simon_lee(sl, period):
    """
    Classificazione basata su Simon & Lee + periodo.

    Regioni empiriche da Jurcsik & Kovacs 1996, Soszynski et al.
    """
    hints = []

    if not sl or "R21" not in sl:
        return _classify_from_period_only(period)

    R21 = sl["R21"]
    phi21 = sl.get("phi21", 0)

    # RR Lyrae ab: P=0.3-0.9d, R21=0.2-0.55, φ21=3.5-5.5
    if 0.3 < period < 0.9:
        if 0.2 < R21 < 0.55 and 3.5 < phi21 < 5.5:
            hints.append("RRab")
        elif R21 < 0.2 and 3.0 < phi21 < 6.0:
            hints.append("RRc")
        else:
            hints.append("RR Lyrae (incerto)")

    # Cepheids: P>1d, R21=0.1-0.5
    elif 1.0 < period < 100:
        if 0.1 < R21 < 0.5:
            hints.append("Cefeide")
        else:
            hints.append("Pulsante lungo periodo")

    # Short-period: P<0.3d
    elif period < 0.3:
        if R21 > 0.1:
            hints.append("δ Scuti / SX Phe")
        else:
            hints.append("Pulsante rapido")

    else:
        hints.append(_classify_from_period_only(period))

    return " / ".join(hints)


def _classify_from_period_only(period):
    """Classificazione di fallback basata solo sul periodo."""
    if period < 0.2:
        return "δ Scuti / SX Phe"
    elif period < 1.0:
        return "RR Lyrae"
    elif period < 10.0:
        return "Cefeide / Binaria"
    elif period < 100.0:
        return "Mira / Semi-regolare"
    return "Variabile lungo periodo"
