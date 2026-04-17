// phase-quality.js - Metriche di qualità per l'analisi di fase
// String Length (SL) e Phase Dispersion Minimization (PDM)
// Usate per quantificare quanto è "buona" la curva in fase e per raffinare il periodo

import { state, getTotalOffset } from './state.js';
import { detrendValue } from './math-logic.js';

// =============================================================================
// COSTRUZIONE ARRAY FASE/MAG PER LE METRICHE
// =============================================================================

/**
 * Costruisce array di fase e magnitudine dal dataset attivo corrente.
 * Usa sempre 100% dei punti attivi (no sampling) per rendere la metrica
 * comparabile tra periodi diversi.
 * Per dataset > 200k punti applica stride deterministico ogni 3 punti (~67k punti).
 *
 * @param {number} period
 * @returns {{ phases: Float32Array, mags: Float32Array }}
 */
function buildPhaseArraysForMetric(period) {
  if (!state.jd || state.n === 0) return { phases: new Float32Array(0), mags: new Float32Array(0) };

  const epoch = state.epoch || state.jd[0];
  const shift = state.phaseShift || 0;
  const stride = state.n > 200000 ? 3 : 1;

  // Pre-conta per allocare arrays
  let count = 0;
  for (let i = 0; i < state.n; i += stride) {
    if (state.activePoint[i] === 0) continue;
    const sid = state.session[i];
    if (!state.activeSession.get(sid)) continue;
    count++;
  }

  const phases = new Float32Array(count);
  const mags = new Float32Array(count);
  let idx = 0;

  for (let i = 0; i < state.n; i += stride) {
    if (state.activePoint[i] === 0) continue;
    const sid = state.session[i];
    if (!state.activeSession.get(sid)) continue;

    const jd = state.jd[i];
    const rawMag = state.mag[i];
    const offset = getTotalOffset(sid);
    const detrend = detrendValue(sid, jd);
    const mag = rawMag - detrend + offset;

    let phase = (((jd - epoch) / period) + shift) % 1.0;
    if (phase < 0) phase += 1.0;

    phases[idx] = phase;
    mags[idx] = mag;
    idx++;
  }

  return { phases, mags };
}

// =============================================================================
// METRICHE
// =============================================================================

/**
 * String Length (Dworetsky 1983): somma delle distanze euclidee tra punti
 * adiacenti ordinati per fase. Più bassa = curva più liscia = periodo migliore.
 * La componente magnitudine è normalizzata per l'ampiezza per renderla
 * adimensionale e comparabile tra stelle diverse.
 *
 * @param {Float32Array|number[]} phases  valori in [0,1)
 * @param {Float32Array|number[]} mags    magnitudini corrispondenti
 * @returns {number|null}  String Length, null se n < 4
 */
export function computeStringLength(phases, mags) {
  const n = phases.length;
  if (n < 4) return null;

  // Calcola ampiezza per normalizzazione
  let minMag = mags[0], maxMag = mags[0];
  for (let i = 1; i < n; i++) {
    if (mags[i] < minMag) minMag = mags[i];
    if (mags[i] > maxMag) maxMag = mags[i];
  }
  const amplitude = maxMag - minMag;
  if (amplitude === 0) return null;

  // Ordina per fase crescente
  const indices = new Int32Array(n);
  for (let i = 0; i < n; i++) indices[i] = i;
  indices.sort((a, b) => phases[a] - phases[b]);

  // Somma distanze euclidee
  let sl = 0;
  for (let k = 0; k < n - 1; k++) {
    const ia = indices[k], ib = indices[k + 1];
    const dPhi = phases[ib] - phases[ia];
    const dMag = (mags[ib] - mags[ia]) / amplitude;
    sl += Math.sqrt(dPhi * dPhi + dMag * dMag);
  }

  return sl;
}

/**
 * Phase Dispersion Minimization (Stellingwerf 1978, semplificato).
 * Rapporto varianza nei bin / varianza totale. 0 = fold perfetto, 1 = rumore.
 *
 * @param {Float32Array|number[]} phases
 * @param {Float32Array|number[]} mags
 * @param {number} nBins  numero di bin (default 20)
 * @returns {number|null}  PDM in [0,1], null se n < 4
 */
export function computePDM(phases, mags, nBins = 20) {
  const n = phases.length;
  if (n < 4) return null;

  // Varianza totale
  let sum = 0;
  for (let i = 0; i < n; i++) sum += mags[i];
  const mean = sum / n;
  let varTotal = 0;
  for (let i = 0; i < n; i++) {
    const d = mags[i] - mean;
    varTotal += d * d;
  }
  varTotal /= (n - 1);
  if (varTotal === 0) return null;

  // Distribuisci punti nei bin
  const bins = [];
  for (let b = 0; b < nBins; b++) bins.push([]);
  for (let i = 0; i < n; i++) {
    const b = Math.floor(phases[i] * nBins) % nBins;
    bins[b].push(mags[i]);
  }

  // Varianza pesata per gradi di libertà
  let weightedVarSum = 0;
  let totalDof = 0;
  for (let b = 0; b < nBins; b++) {
    const bm = bins[b];
    if (bm.length < 2) continue;
    let bSum = 0;
    for (let j = 0; j < bm.length; j++) bSum += bm[j];
    const bMean = bSum / bm.length;
    let bVar = 0;
    for (let j = 0; j < bm.length; j++) {
      const d = bm[j] - bMean;
      bVar += d * d;
    }
    const dof = bm.length - 1;
    weightedVarSum += bVar;  // già somma dei (m-mean)^2, equivalente a dof*var
    totalDof += dof;
  }

  if (totalDof === 0) return null;

  const varBins = (weightedVarSum / totalDof);
  return varBins / varTotal;
}

/**
 * Calcola entrambe le metriche per un dato periodo.
 *
 * @param {number} period
 * @returns {{ sl: number|null, pdm: number|null }}
 */
export function computeMetricsForPeriod(period) {
  if (!isFinite(period) || period <= 0) return { sl: null, pdm: null };
  const { phases, mags } = buildPhaseArraysForMetric(period);
  if (phases.length < 4) return { sl: null, pdm: null };
  return {
    sl: computeStringLength(phases, mags),
    pdm: computePDM(phases, mags)
  };
}

// =============================================================================
// RAFFINAMENTO AUTOMATICO DEL PERIODO
// =============================================================================

/**
 * Scansiona P ± nSteps×deltaP e trova il periodo con String Length minima.
 *
 * @param {number} centerPeriod  periodo di partenza
 * @param {number} deltaP        passo di scansione
 * @param {number} nSteps        numero di step da ogni lato (default 50)
 * @returns {{
 *   bestPeriod: number,
 *   bestSL: number,
 *   landscape: Array<{period:number, offset:number, sl:number|null, pdm:number|null}>
 * }}
 */
export function refinePeriod(centerPeriod, deltaP, nSteps = 50) {
  const landscape = [];
  let bestPeriod = centerPeriod;
  let bestSL = Infinity;

  for (let k = -nSteps; k <= nSteps; k++) {
    const p = centerPeriod + k * deltaP;
    if (p <= 0) continue;
    const { sl, pdm } = computeMetricsForPeriod(p);
    landscape.push({ period: p, offset: k, sl, pdm });
    if (sl !== null && sl < bestSL) {
      bestSL = sl;
      bestPeriod = p;
    }
  }

  return { bestPeriod, bestSL: bestSL === Infinity ? null : bestSL, landscape };
}

// =============================================================================
// AGGIORNAMENTO UI — BADGE
// =============================================================================

/**
 * Aggiorna i badge QUAL con i valori correnti di SL e PDM.
 * Colore badge: grigio (no baseline), verde (migliorato >2%), rosso (peggiorato >2%)
 *
 * @param {number|null} sl
 * @param {number|null} pdm
 * @param {number|null} baselineSL
 */
export function updateQualityBadge(sl, pdm, baselineSL) {
  const slBadge = document.getElementById('phaseQualityBadge');
  const pdmBadge = document.getElementById('phaseQualityPDM');

  if (slBadge) {
    slBadge.textContent = sl !== null ? `SL ${sl.toFixed(2)}` : '— SL';
    slBadge.classList.remove('quality-good', 'quality-bad');

    if (sl !== null && baselineSL !== null) {
      if (sl < baselineSL * 0.98) {
        slBadge.classList.add('quality-good');
      } else if (sl > baselineSL * 1.02) {
        slBadge.classList.add('quality-bad');
      }
    }
  }

  if (pdmBadge) {
    pdmBadge.textContent = pdm !== null ? `PDM ${pdm.toFixed(2)}` : '— PDM';
  }
}

// =============================================================================
// VISUALIZZAZIONE PAESAGGIO
// =============================================================================

/**
 * Renderizza il mini grafico Plotly del paesaggio SL vs offset di periodo.
 *
 * @param {Array<{period:number, offset:number, sl:number|null, pdm:number|null}>} landscape
 * @param {number} bestPeriod  periodo con SL minima
 * @param {number} centerPeriod  periodo di partenza della scansione
 */
export function renderRefineLandscape(landscape, bestPeriod, centerPeriod) {
  const plotEl = document.getElementById('phaseRefinePlot');
  if (!plotEl || typeof Plotly === 'undefined') return;

  const valid = landscape.filter(p => p.sl !== null);
  if (valid.length === 0) return;

  // Nascondi il hint placeholder
  const hint = document.getElementById('phaseRefinePlotHint');
  if (hint) hint.style.display = 'none';

  const xData = valid.map(p => p.offset);
  const yData = valid.map(p => p.sl);

  const bestOffset = Math.round((bestPeriod - centerPeriod) /
    (landscape.length > 1 ? (landscape[1].period - landscape[0].period) : 1));

  const trace = {
    x: xData,
    y: yData,
    type: 'scatter',
    mode: 'lines',
    line: { color: '#3b82f6', width: 1.5 },
    hovertemplate: 'Offset: %{x}<br>SL: %{y:.3f}<extra></extra>'
  };

  // Linea verticale al minimo
  const minSL = Math.min(...yData);
  const maxSL = Math.max(...yData);

  const layout = {
    margin: { t: 4, b: 22, l: 38, r: 4 },
    autosize: true,
    xaxis: {
      title: { text: 'Offset (×ΔP)', font: { size: 8 } },
      tickfont: { size: 7 },
      zeroline: true, zerolinecolor: '#94a3b8', zerolinewidth: 1
    },
    yaxis: {
      title: { text: 'SL', font: { size: 8 } },
      tickfont: { size: 7 }
    },
    shapes: [
      {
        type: 'line', x0: bestOffset, x1: bestOffset,
        y0: minSL, y1: maxSL,
        line: { color: '#22c55e', width: 1.5, dash: 'dash' }
      }
    ],
    plot_bgcolor: '#f0fdf4',
    paper_bgcolor: 'transparent',
    showlegend: false
  };

  const config = { displayModeBar: false, responsive: true };

  Plotly.react(plotEl, [trace], layout, config).then(() => {
    Plotly.Plots.resize(plotEl);
  });
}
