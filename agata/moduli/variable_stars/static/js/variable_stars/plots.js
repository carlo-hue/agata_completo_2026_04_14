//plots.js
import { state, colorForSession, nameForSession, baseYRange, setBaseYRange, getTotalOffset } from './state.js';
import { detrendValue, buildAnalysisArraysTyped } from './math-logic.js';
import { buildArrowStreamJDMag } from '../common/utils-arrow.js';
import { calculatePhaseStatistics, renderPhaseStatistics } from './phase-statistics.js';
import { updateCounters } from './session-ui.js';
import { CONFIG, suggestNFreq } from './config.js';
import { computeMultiPeriod, classifySinglePeriod, computePeriodogramForData } from './period-analysis.js';
import { computePhaseData } from './phase-analysis.js';

// ── n_freq controller ──────────────────────────────────────────────────────
const _nFreqCtrl = {
  _userModified: false,
  _suggested: 6000,

  init() {
    const input = document.getElementById("nFreq");
    const reset = document.getElementById("nFreqReset");
    if (!input) return;

    input.addEventListener("input", () => {
      this._userModified = true;
      if (reset) reset.style.display = "inline-block";
      const badge = document.getElementById("nFreqSuggestBadge");
      if (badge) badge.style.display = "none";
    });
    reset?.addEventListener("click", () => this.resetToSuggested());

    const onRangeChange = () => { if (!this._userModified) this.updateSuggestion(); };
    document.getElementById("minP")?.addEventListener("change", onRangeChange);
    document.getElementById("maxP")?.addEventListener("change", onRangeChange);

    this.updateSuggestion();
  },

  updateSuggestion() {
    const minP = parseFloat(document.getElementById("minP")?.value) || 0.1;
    const maxP = parseFloat(document.getElementById("maxP")?.value) || 15;
    const jd = (state.jd?.length >= 2) ? state.jd : null;
    this._suggested = suggestNFreq(minP, maxP, jd);

    const hint = document.getElementById("nFreqHint");
    if (hint) hint.textContent = `Suggerito: ${this._suggested.toLocaleString('it-IT')}`;

    if (!this._userModified) {
      const input = document.getElementById("nFreq");
      if (input) input.value = this._suggested;
      const badge = document.getElementById("nFreqSuggestBadge");
      if (badge) badge.style.display = "inline";
    }
  },

  resetToSuggested() {
    this._userModified = false;
    const input = document.getElementById("nFreq");
    const reset = document.getElementById("nFreqReset");
    const badge = document.getElementById("nFreqSuggestBadge");
    if (input) input.value = this._suggested;
    if (reset) reset.style.display = "none";
    if (badge) badge.style.display = "inline";
  },

  getValue() {
    const raw = parseInt(document.getElementById("nFreq")?.value ?? this._suggested, 10);
    return Math.max(500, Math.min(isNaN(raw) ? this._suggested : raw, 20000));
  }
};
// ── end n_freq controller ──────────────────────────────────────────────────

/**
 * Calcola offset temporali per visualizzazione compatta
 * Mantiene relazioni temporali DENTRO ogni sessione, ma rimuove gap TRA sessioni
 */
function calculateCompactTimeOffsets() {
  const offsets = new Map();
  const sessionRanges = new Map();
  
  // 1. Trova range JD per ogni sessione
  for (let i = 0; i < state.n; i++) {
    if (state.activePoint[i] === 0) continue;
    const sid = state.session[i];
    if (!state.activeSession.get(sid)) continue;
    
    if (!sessionRanges.has(sid)) {
      sessionRanges.set(sid, { min: Infinity, max: -Infinity });
    }
    
    const range = sessionRanges.get(sid);
    if (state.jd[i] < range.min) range.min = state.jd[i];
    if (state.jd[i] > range.max) range.max = state.jd[i];
  }
  
  // 2. Calcola offset cumulativo per "impacchettare" le sessioni
  let cumulativeOffset = 0;
  const sortedSessions = Array.from(sessionRanges.keys()).sort((a, b) => {
    return sessionRanges.get(a).min - sessionRanges.get(b).min;
  });
  
  for (const sid of sortedSessions) {
    const range = sessionRanges.get(sid);
    
    // Offset = sposta questa sessione all'inizio del "pacchetto"
    offsets.set(sid, cumulativeOffset - range.min);
    
    // Prossima sessione parte dopo questa (con piccolo gap di 1 giorno)
    cumulativeOffset += (range.max - range.min) + 1.0;
  }
  
  return offsets;
}

export function drawLightcurve(preservedRange = null) {
  const traces = [];
  let totalCount = 0;
  const sids = Array.from(state.activeSession.keys()).sort((a,b)=>a-b);


  const compactMode = document.getElementById("compactView")?.checked || false;

  // Calcola JD origine per asse X 0-based (solo in modalità non-compatta)
  let jdOrigin = null;
  if (!compactMode) {
    let minJD = Infinity;
    for (let i = 0; i < state.n; i++) {
      if (state.activePoint[i] === 0) continue;
      if (!state.activeSession.get(state.session[i])) continue;
      if (state.jd[i] < minJD) minJD = state.jd[i];
    }
    if (isFinite(minJD)) {
      jdOrigin = Math.floor(minJD);
      state.jdOrigin = Math.floor(minJD);
    }
  }

  // ✅ Vista compatta: normalizza e compatta sequenzialmente
  let timeOffsets = null;
  let sessionNormalization = null;

  if (compactMode) {
    // 1. Raccolgo dati grezzi per ogni sessione (t, y, indices)
    const sessionData = new Map();

    for (let i = 0; i < state.n; i++) {
      if (state.activePoint[i] === 0) continue;
      const sid = state.session[i];
      if (!state.activeSession.get(sid)) continue;

      if (!sessionData.has(sid)) {
        sessionData.set(sid, { t: [], y: [], indices: [] });
      }

      const data = sessionData.get(sid);
      data.t.push(state.jd[i]);
      data.y.push(state.mag[i] - detrendValue(sid, state.jd[i]));
      data.indices.push(i);
    }

    // 2. Calcola range per ogni sessione individualmente (nessun raggruppamento)
    const sessionRanges = new Map(); // sid -> {tMin, tMax, tRange}
    for (const [sid, data] of sessionData) {
      const tMin = Math.min(...data.t);
      const tMax = Math.max(...data.t);
      sessionRanges.set(sid, { tMin, tMax, tRange: tMax - tMin || 1 });
    }

    // Ordina sessioni per tMin (dal più vecchio al più recente)
    const sortedSids = [...sessionRanges.keys()].sort(
      (a, b) => sessionRanges.get(a).tMin - sessionRanges.get(b).tMin
    );

    // Calcola tRange totale (somma di tutti i range)
    const totalRange = sortedSids.reduce(
      (sum, sid) => sum + sessionRanges.get(sid).tRange, 0
    );

    // Calcola shift cumulativo e scaleFactor proporzionale per ogni sessione
    // Ogni sessione occupa uno spazio [shift, shift+scaleFactor] sull'asse X normalizzato
    timeOffsets = new Map();
    sessionNormalization = new Map();
    let cumShift = 0;

    for (const sid of sortedSids) {
      const { tMin, tRange } = sessionRanges.get(sid);
      const scaleFactor = tRange / totalRange;
      sessionNormalization.set(sid, { tMin, tRange, shift: cumShift, scaleFactor });
      timeOffsets.set(sid, cumShift);
      cumShift += scaleFactor;
    }

    // Salva nello state per uso da zoomToSession
    state.sessionNormalization = sessionNormalization;
  }

  // TRACCE NORMALI
  for (const sid of sids) {
    if (!state.activeSession.get(sid)) continue;

    const totalOffset = getTotalOffset(sid);
    let m = 0;
    for (let i = 0; i < state.n; i++) if (state.activePoint[i] === 1 && state.session[i] === sid) m++;
    if (m === 0) continue;

    const x = new Float64Array(m);
    const y = new Float32Array(m);
    const rawMap = new Int32Array(m);
    const realJD = compactMode ? new Float64Array(m) : null;

    let j = 0;

    for (let i = 0; i < state.n; i++) {
      if (state.activePoint[i] === 0 || state.session[i] !== sid) continue;

      let xVal = (!compactMode && jdOrigin !== null) ? (state.jd[i] - jdOrigin) : state.jd[i];

      // Se in compactMode, normalizza il tempo
      if (compactMode && sessionNormalization) {
        const norm = sessionNormalization.get(sid);
        const tNorm = (state.jd[i] - norm.tMin) / norm.tRange; // [0, 1]
        xVal = norm.shift + tNorm * norm.scaleFactor; // proporzionale alla durata
      }

      x[j] = xVal;
      y[j] = (state.mag[i] - detrendValue(sid, state.jd[i])) + totalOffset;
      rawMap[j] = i;

      if (compactMode) {
        realJD[j] = state.jd[i]; // JD reale per hover
      }

      j++;
    }

    totalCount += m;

    traces.push({
      type: "scattergl",
      mode: "markers",
      x,
      y,
      name: state.simpleLegend ? nameForSession(sid) : `${nameForSession(sid)} (${m})`,
      marker: {
        size: state.currentMarkerSize,
        color: colorForSession(sid),
        opacity: 0.85
      },
      customdata: compactMode ? realJD : rawMap,
      hovertemplate: compactMode
        ? `<b>${nameForSession(sid)}</b><br>JD=%{customdata:.5f}<br>mag=%{y:.4f}<extra></extra>`
        : `<b>${nameForSession(sid)}</b><br>JD=%{x:.5f}<br>mag=%{y:.4f}<br><i>Shift+Click per offset rapido</i><extra></extra>`,
      sid: sid
    });
  }
  
  // OUTLIER SIGMA CLIPPING
  if (state.sigmaClipSuggested?.size > 0) {
    const outliersBySession = new Map();

    for (const idx of state.sigmaClipSuggested) {
      if (state.activePoint[idx] === 0) continue;

      const sid = state.session[idx];
      if (!state.activeSession.get(sid)) continue;

      if (!outliersBySession.has(sid)) {
        outliersBySession.set(sid, { x: [], y: [], indices: [] });
      }

      const data = outliersBySession.get(sid);

      let xVal = (!compactMode && jdOrigin !== null) ? (state.jd[idx] - jdOrigin) : state.jd[idx];

      // Se in compactMode, normalizza il tempo come sopra
      if (compactMode && sessionNormalization) {
        const norm = sessionNormalization.get(sid);
        const tNorm = (state.jd[idx] - norm.tMin) / norm.tRange;
        xVal = norm.shift + tNorm * norm.scaleFactor;
      }

      data.x.push(xVal);
      data.y.push((state.mag[idx] - detrendValue(sid, state.jd[idx])) + getTotalOffset(sid));
      data.indices.push(idx);
    }
    
    outliersBySession.forEach((data, sid) => {
      traces.push({
        type: "scattergl",
        mode: "markers",
        x: data.x,
        y: data.y,
        name: state.simpleLegend ? `🚨 ${nameForSession(sid)}` : `🚨 ${nameForSession(sid)} - Outlier (${data.x.length})`,
        marker: { 
          size: state.currentMarkerSize * CONFIG.PLOT.MARKER_SIZE.OUTLIER_MULTIPLIER,
          color: "#ef4444",
          symbol: "x",
          line: { width: 3, color: "#ffffff" },
          opacity: 1.0
        },
        hovertemplate: `<b>⚠️ OUTLIER σ-clip</b><br>${nameForSession(sid)}<br>JD=%{x:.5f}<br>mag=%{y:.4f}<extra></extra>`,
        showlegend: true,
        legendgroup: `outliers-${sid}`
      });
    });
  }
  
  // SELEZIONE MANUALE
  if (state.selectedRaw.size > 0) {
    const manualX = [], manualY = [];
    
    for (const idx of state.selectedRaw) {
      if (state.activePoint[idx] === 0) continue;
      if (state.sigmaClipSuggested.has(idx)) continue;
      
      const sid = state.session[idx];
      if (!state.activeSession.get(sid)) continue;
      
      let xVal = jdOrigin !== null ? (state.jd[idx] - jdOrigin) : state.jd[idx];
      if (compactMode && sessionNormalization) {
        const norm = sessionNormalization.get(sid);
        if (norm) {
          const tNorm = (state.jd[idx] - norm.tMin) / norm.tRange;
          xVal = norm.shift + tNorm * norm.scaleFactor;
        }
      }
      manualX.push(xVal);
      manualY.push((state.mag[idx] - detrendValue(sid, state.jd[idx])) + getTotalOffset(sid));
    }
    
    if (manualX.length > 0) {
      traces.push({
        type: "scattergl",
        mode: "markers",
        x: manualX,
        y: manualY,
        name: `📌 Selezione Manuale (${manualX.length})`,
        marker: { 
          size: state.currentMarkerSize * CONFIG.PLOT.MARKER_SIZE.SELECTED_MULTIPLIER, 
          color: "#f59e0b",
          symbol: "diamond",
          line: { width: 2, color: "#fff" },
          opacity: 0.9
        },
        hovertemplate: "<b>📌 Selezionato</b><br>JD=%{x:.5f}<br>mag=%{y:.4f}<extra></extra>",
        showlegend: true
      });
    }
  }

  const titleSuffix = compactMode ? " 📦" : "";
  const jd0Label = "";  // ora mostrato come sottotitolo del grafico

  // Costruisce barre verticali di misura
  const shapes = [];
  if (state.verticalBars.enabled) {
    if (state.verticalBars.bar1 === null || state.verticalBars.bar2 === null) {
      let xMin, xMax;
      if (preservedRange?.x) {
        [xMin, xMax] = preservedRange.x;
      } else {
        xMin = Infinity; xMax = -Infinity;
        for (const tr of traces) {
          for (const v of tr.x) { if (v < xMin) xMin = v; if (v > xMax) xMax = v; }
        }
      }
      if (isFinite(xMin)) {
        state.verticalBars.bar1 = xMin + (xMax - xMin) * 0.25;
        state.verticalBars.bar2 = xMin + (xMax - xMin) * 0.75;
      }
    }
    const mkBar = (x, color) => ({
      type: 'line', xref: 'x', yref: 'paper',
      x0: x, x1: x, y0: 0, y1: 1,
      line: { color, width: 2, dash: 'dash' },
      editable: true
    });
    shapes.push(mkBar(state.verticalBars.bar1, '#3b82f6'));
    shapes.push(mkBar(state.verticalBars.bar2, '#ef4444'));
  }

  // Costruisce barre orizzontali di misura ΔMag
  if (state.horizontalBars.enabled) {
    if (state.horizontalBars.bar1 === null || state.horizontalBars.bar2 === null) {
      let yMin, yMax;
      if (preservedRange?.y) {
        [yMin, yMax] = preservedRange.y;
      } else {
        yMin = Infinity; yMax = -Infinity;
        for (const tr of traces) {
          for (const v of tr.y) { if (v < yMin) yMin = v; if (v > yMax) yMax = v; }
        }
      }
      if (isFinite(yMin)) {
        state.horizontalBars.bar1 = yMin + (yMax - yMin) * 0.25;
        state.horizontalBars.bar2 = yMin + (yMax - yMin) * 0.75;
      }
    }
    state.horizontalBars._shapeIdx = shapes.length;
    const mkHBar = (y, color) => ({
      type: 'line', xref: 'paper', yref: 'y',
      x0: 0, x1: 1, y0: y, y1: y,
      line: { color, width: 2, dash: 'dash' },
      editable: true
    });
    shapes.push(mkHBar(state.horizontalBars.bar1, '#10b981'));
    shapes.push(mkHBar(state.horizontalBars.bar2, '#f97316'));
  }

  const layout = {
    title: `JD Plot`,
    xaxis: {
      title: compactMode ? "Tempo Relativo (d)" : (jdOrigin !== null ? `JD \u2212 ${jdOrigin}` : "JD"),
      ...(preservedRange ? { range: preservedRange.x } : { autorange: true })
    },
    yaxis: {
      title: "Mag",
      ...(preservedRange ? { range: preservedRange.y } : { autorange: "reversed" })
    },
    dragmode: "zoom",
    showlegend: true,
    legend: {
      x: 1.02,
      y: 1,
      xanchor: 'left',
      bgcolor: 'rgba(255,255,255,0.9)',
      bordercolor: '#e2e8f0',
      borderwidth: 1
    },
    shapes
  };

  const plotPromise = Plotly.react("plotLC", traces, layout, { responsive: true, displaylogo: false, editable: true });

  if (!baseYRange) {
    const gd = document.getElementById("plotLC");
    if (gd?.layout?.yaxis?.range) setBaseYRange([...gd.layout.yaxis.range]);
  }

  setupLightcurveInteractions();

  return plotPromise;
}

export function updateDeltaTDisplay() {
  const el = document.getElementById('lc-delta-t');
  if (!el) return;
  if (!state.verticalBars.enabled || state.verticalBars.bar1 === null || state.verticalBars.bar2 === null) {
    el.textContent = '';
    return;
  }
  const dt = Math.abs(state.verticalBars.bar2 - state.verticalBars.bar1);
  el.textContent = `\u0394T = ${dt.toFixed(4)} d`;
}

export function updateDeltaMagDisplay() {
  const el = document.getElementById('lc-delta-mag');
  if (!el) return;
  if (!state.horizontalBars.enabled || state.horizontalBars.bar1 === null || state.horizontalBars.bar2 === null) {
    el.textContent = '';
    return;
  }
  const dm = Math.abs(state.horizontalBars.bar2 - state.horizontalBars.bar1);
  el.textContent = `\u0394Mag = ${dm.toFixed(4)}`;
}

// Interazioni avanzate: Shift+Click per selezione rapida sessione
function setupLightcurveInteractions() {
  const gd = document.getElementById("plotLC");
  gd.removeAllListeners?.('plotly_click');
  gd.removeAllListeners?.('plotly_selected');
  gd.removeAllListeners?.('plotly_relayout');

  gd.on('plotly_click', (data) => {
    if (data.event.shiftKey && data.points && data.points.length > 0) {
      const sid = data.points[0].data.sid;
      if (sid !== undefined) {
        const slider = document.getElementById(`slider${sid}`);
        if (slider) {
          slider.scrollIntoView({ behavior: 'smooth', block: 'center' });
          slider.focus();
          
          const card = slider.closest('.session-card');
          if (card) {
            card.style.transition = 'all 0.3s';
            card.style.background = '#dbeafe';
            card.style.transform = 'scale(1.02)';
          }
        }
      }
    }
  });
  
  gd.on('plotly_selected', (eventData) => {
    state.selectedRaw.clear();
    if (!eventData || !eventData.points) return;
    for (const p of eventData.points) {
      const rawIdx = p.customdata;
      if (rawIdx !== undefined && rawIdx !== null) {
        state.selectedRaw.add(rawIdx);
      }
    }
    updateCounters();
  });

  gd.on('plotly_relayout', (eventData) => {
    let updatedV = false, updatedH = false;
    for (const key of Object.keys(eventData)) {
      if (state.verticalBars.enabled) {
        if (key === 'shapes[0].x0' || key === 'shapes[0].x1') {
          const v = eventData[key];
          if (typeof v === 'number' && isFinite(v)) { state.verticalBars.bar1 = v; updatedV = true; }
        } else if (key === 'shapes[1].x0' || key === 'shapes[1].x1') {
          const v = eventData[key];
          if (typeof v === 'number' && isFinite(v)) { state.verticalBars.bar2 = v; updatedV = true; }
        }
      }
      if (state.horizontalBars.enabled) {
        const idx = state.horizontalBars._shapeIdx ?? 0;
        if (key === `shapes[${idx}].y0` || key === `shapes[${idx}].y1`) {
          const v = eventData[key];
          if (typeof v === 'number' && isFinite(v)) { state.horizontalBars.bar1 = v; updatedH = true; }
        } else if (key === `shapes[${idx + 1}].y0` || key === `shapes[${idx + 1}].y1`) {
          const v = eventData[key];
          if (typeof v === 'number' && isFinite(v)) { state.horizontalBars.bar2 = v; updatedH = true; }
        }
      }
    }
    if (updatedV) updateDeltaTDisplay();
    if (updatedH) updateDeltaMagDisplay();
  });
}

/**
 * Sigma-clip locale per una sessione (MAD-based, come il backend Python).
 * Non modifica lo state — ritorna solo i Set di indici.
 * @param {number} sid - Session ID
 * @param {number} sigma - Soglia sigma (default 3.0)
 * @returns {{ outliers: Set<number>, inlierIndices: number[], median: number, sigmaEquiv: number }}
 */
function sigmaClipSession(sid, sigma = 3.0) {
  const mags = [], indices = [];
  for (let i = 0; i < state.n; i++) {
    if (state.activePoint[i] === 0 || state.session[i] !== sid) continue;
    mags.push(state.mag[i]);
    indices.push(i);
  }

  if (mags.length < 4) {
    return { outliers: new Set(), inlierIndices: indices, median: 0, sigmaEquiv: 0 };
  }

  const sorted = [...mags].sort((a, b) => a - b);
  const median = sorted[Math.floor(sorted.length / 2)];
  const deviations = mags.map(m => Math.abs(m - median)).sort((a, b) => a - b);
  const mad = deviations[Math.floor(deviations.length / 2)];
  const sigmaEquiv = Math.max(mad * 1.4826, 0.0001);
  const threshold = sigmaEquiv * sigma;

  const outliers = new Set();
  for (let k = 0; k < mags.length; k++) {
    if (Math.abs(mags[k] - median) > threshold) outliers.add(indices[k]);
  }

  return {
    outliers,
    inlierIndices: indices.filter(i => !outliers.has(i)),
    median,
    sigmaEquiv
  };
}

/**
 * Zoom ottimale sulla sessione sid.
 * Usa sigma-clip locale per escludere outlier dal calcolo del range Y.
 * Gli outlier vengono aggiunti a state.sigmaClipSuggested (evidenziati in rosso).
 * Le altre sessioni vengono dimmate (opacity 0.12) per mantenere il contesto.
 *
 * @param {number} sid - Session ID
 * @param {number} sigma - Soglia sigma per zoom ottimale (default 3.0)
 * @returns {{ nOutliers: number, outlierIndices: number[] }}
 */
export async function zoomToSession(sid, sigma = 5.0) {
  const gd = document.getElementById("plotLC");
  if (!gd || !gd.data) return { nOutliers: 0, outlierIndices: [] };

  const compactMode = document.getElementById("compactView")?.checked || false;

  // Raccoglie xs, ys e indici paralleli
  const xs = [], ys = [], pointIndices = [];

  for (let i = 0; i < state.n; i++) {
    if (state.activePoint[i] === 0 || state.session[i] !== sid) continue;

    let xVal;
    if (compactMode && state.sessionNormalization) {
      const norm = state.sessionNormalization.get(sid);
      xVal = norm
        ? norm.shift + (state.jd[i] - norm.tMin) / norm.tRange * norm.scaleFactor
        : state.jd[i];
    } else {
      xVal = state.jdOrigin !== null ? (state.jd[i] - state.jdOrigin) : state.jd[i];
    }

    xs.push(xVal);
    ys.push((state.mag[i] - detrendValue(sid, state.jd[i])) + getTotalOffset(sid));
    pointIndices.push(i);
  }

  if (xs.length === 0) return { nOutliers: 0, outlierIndices: [] };

  // Sigma-clip locale: calcola outlier per zoom ottimale
  const clip = sigmaClipSession(sid, sigma);

  // Range X: tutti i punti (outlier restano visibili sull'asse temporale)
  const xMin = Math.min(...xs);
  const xMax = Math.max(...xs);

  // Range Y: solo inlier (zoom ottimale, outlier fuori range ma visibili)
  const ysInlier = pointIndices
    .map((idx, k) => clip.outliers.has(idx) ? null : ys[k])
    .filter(v => v !== null);

  const yVals = ysInlier.length >= 2 ? ysInlier : ys; // fallback se tutti outlier
  const yMin = Math.min(...yVals);
  const yMax = Math.max(...yVals);

  const xPad = Math.max((xMax - xMin) * 0.05, 0.1);
  const yPad = Math.max((yMax - yMin) * 0.15, 0.005);

  // Rimuovi prima tutti gli outlier di questa sessione dal set (reset per sigma cambiato)
  // poi aggiungi solo i nuovi — così cambiare sigma non accumula mai outlier vecchi
  for (const idx of [...state.sigmaClipSuggested]) {
    if (state.session[idx] === sid) state.sigmaClipSuggested.delete(idx);
  }
  const newOutlierIndices = [];
  for (const idx of clip.outliers) {
    state.sigmaClipSuggested.add(idx);
    newOutlierIndices.push(idx);
  }

  // Ridisegna sempre: aggiorna evidenziazione outlier in rosso + dim altre sessioni
  // (drawLightcurve resetta il layout, quindi zoom va applicato DOPO)
  await drawLightcurve();

  // Applica zoom
  const gdEl = document.getElementById("plotLC");
  Plotly.relayout(gdEl, {
    "xaxis.range": [xMin - xPad, xMax + xPad],
    "yaxis.range": [yMax + yPad, yMin - yPad]  // Y invertito per magnitudine
  });

  // Dimma le tracce delle altre sessioni
  const opacities = gdEl.data.map(trace => trace.sid === sid ? 0.85 : 0.12);
  Plotly.restyle(gdEl, { "marker.opacity": opacities });

  return { nOutliers: clip.outliers.size, outlierIndices: newOutlierIndices };
}

/**
 * Ripristina la vista globale: autorange su entrambi gli assi e opacity normale.
 */
export async function resetSessionZoom() {
  // Pulisce outlier di sessione (aggiunti da zoomToSession) — ripristina tutti i punti visibili
  state.sigmaClipSuggested.clear();

  await drawLightcurve();

  const gd = document.getElementById("plotLC");
  if (!gd || !gd.data) return;

  Plotly.relayout(gd, {
    "xaxis.autorange": true,
    "yaxis.autorange": "reversed"
  });

  const opacities = gd.data.map(() => 0.85);
  Plotly.restyle(gd, { "marker.opacity": opacities });
}

export function getCurrentLCRange() {
  const gd = document.getElementById("plotLC");
  if (!gd || !gd.layout) return null;
  const xr = gd.layout.xaxis?.range;
  const yr = gd.layout.yaxis?.range;
  if (!xr || !yr) return null;
  return {
    x: [...xr],
    y: [...yr]
  };
}

export async function computePeriodogram(callbackClick) {
  await _computePeriodogramPerSession(callbackClick);
}

export function initNFreqController() {
  _nFreqCtrl.init();
}

export function refreshNFreqSuggestion() {
  _nFreqCtrl.updateSuggestion();
}

async function _computePeriodogramClassic(callbackClick) {
  const minP = Number(document.getElementById("minP").value);
  const maxP = Number(document.getElementById("maxP").value);
  const enablePrewhitening = document.getElementById("enablePrewhitening")?.checked || false;
  const nPeriods = enablePrewhitening ? parseInt(document.getElementById("nPeriods")?.value || 3) : 1;
  const nFreq = _nFreqCtrl.getValue();

  // Layout classico: 70% grafico + 30% info picchi (come per-sessione)
  const container = document.getElementById("plotPeriod-container");
  if (container) {
    container.innerHTML = `
      <div style="display: flex; height: 400px;">
        <div id="plotPeriod" style="flex: 0 0 30%; min-width: 0;"></div>
        <div style="flex: 0 0 70%; min-width: 0; display: flex; flex-direction: column; border-left: 1px solid #e2e8f0; background: #f8fafc;">
          <div id="plotPeriod-classic-phase-preview" style="flex: 1; min-height: 180px; border-bottom: 1px solid #e2e8f0;">
            <div style="color:#94a3b8; font-size:10px; padding:8px; text-align:center; margin-top:60px;">Clicca un periodo per la preview</div>
          </div>
          <div id="plotPeriod-classic-peaks" style="height: auto; max-height: 140px; overflow-y: auto; padding: 8px; display: flex; flex-direction: column; gap: 5px;">
            <div style="color:#94a3b8; font-size:10px; font-style:italic;">Calcolo...</div>
          </div>
        </div>
      </div>`;
  }

  await _computePeriodogramImpl(minP, maxP, enablePrewhitening, nPeriods, nFreq, "plotPeriod", callbackClick, /*updatePeaks=*/true);
}

async function _computePeriodogramImpl(minP, maxP, enablePrewhitening, nPeriods, nFreq, plotDivId, callbackClick, updatePeaks) {
  const minP_val = minP;
  const maxP_val = maxP;

  const fapStyles = {
    "0.1": {dash:"dot", color:"#f97316", name:"FAP 10%"},
    "0.01": {dash:"dash", color:"#facc15", name:"FAP 1%"},
    "0.001": {dash:"solid", color:"#22c55e", name:"FAP 0.1%"}
  };
  const colors = ["#22c55e", "#3b82f6", "#a855f7", "#f59e0b", "#ef4444"];

  // ✅ MODALITÀ MULTI-PERIODO CON PRE-WHITENING
  if (enablePrewhitening && nPeriods > 1) {
    console.log(`🎯 Modalità multi-periodo: cercando ${nPeriods} periodi con pre-whitening`);

    try {
      const multiResults = await computeMultiPeriod(nPeriods, minP_val, maxP_val, nFreq);
      const data = multiResults[0].spectrum;

      console.log(`📊 Spettro: ${data.period.length} punti, range power: ${Math.min(...data.power).toFixed(4)} - ${Math.max(...data.power).toFixed(4)}`);

      const traces = [
        {
          x: data.period,
          y: data.power,
          mode: "lines",
          name: "Spettro Originale",
          line: { color: "#38bdf8", width: 1.5 },
          opacity: 0.8,
          showlegend: true
        }
      ];

      Object.entries(data.fap_levels).forEach(([k, yval]) => {
        traces.push({
          x: [data.period[0], data.period[data.period.length-1]],
          y: [yval, yval],
          mode: "lines",
          name: fapStyles[k].name,
          line: { ...fapStyles[k], width: 2 },
          hoverinfo: "name"
        });
      });

      multiResults.forEach((result, idx) => {
        traces.push({
          x: [result.period],
          y: [result.power],
          mode: "markers+text",
          marker: {
            size: 14 + (2 * (nPeriods - idx)),
            color: colors[idx % colors.length],
            symbol: "star",
            line: {width: 2, color: '#fff'}
          },
          text: [`P${idx + 1}`],
          textposition: "top center",
          textfont: { size: 11, color: colors[idx % colors.length], family: "monospace" },
          hovertemplate:
            `<b>Periodo ${idx + 1}</b><br>` +
            `P: ${result.period.toFixed(6)} d<br>` +
            `Power: ${result.power.toFixed(3)}<br>` +
            `Amplitude: ${result.amplitude != null ? result.amplitude.toFixed(4) + " mag" : "n/a"}<br>` +
            `FAP: ${result.fap.toExponential(2)}<br>` +
            `SNR: ${result.snr.toFixed(1)}<extra></extra>`,
          name: `P${idx + 1}: ${result.period.toFixed(6)} d`,
          showlegend: true
        });
      });

      Plotly.react(plotDivId, traces, {
        title: {
          text: `Analisi Multi-Periodo (${multiResults.length} periodi trovati)`,
          font: { size: 14, color: "#1e293b" }
        },
        paper_bgcolor: "#ffffff",
        plot_bgcolor: "#fafafa",
        font: {color: "#1e293b"},
        xaxis: { title: "Periodo (giorni)", gridcolor: "#e2e8f0", type: "linear" },
        yaxis: { title: "Power", gridcolor: "#e2e8f0", type: "linear" },
        showlegend: true,
        legend: {x: 0.02, y: 0.98, bgcolor: "rgba(255,255,255,0.8)", font: {size: 10}},
        hovermode: "closest",
        margin: {t: 40, b: 40, l: 50, r: 20}
      });

      if (updatePeaks) _renderSessionPeriodInfo("plotPeriod-classic-peaks", { periods: multiResults }, "#38bdf8", callbackClick, "plotPeriod-classic-phase-preview");

      const pd = document.getElementById(plotDivId);
      if (pd && callbackClick) pd.on("plotly_click", (ev) => { if (ev.points) callbackClick(ev.points[0].x); });

      if (updatePeaks) {
        state.periodogramResult = {
          periods: multiResults.map(r => r.period),
          amplitudes: multiResults.map(r => r.amplitude),
          powers: multiResults.map(r => r.power),
          peaks: multiResults.map(r => ({ period: r.period, power: r.power, fap: r.fap, snr: r.snr, amplitude: r.amplitude })),
          timestamp: Date.now() / 86400000 + 2440587.5
        };
        console.log('📊 Risultati periodigramma salvati in state per AI Advisor');
      }

      return multiResults.map(r => ({ period: r.period, power: r.power, fap: r.fap, snr: r.snr }));

    } catch (error) {
      console.error("❌ Errore analisi multi-periodo:", error);
      if (updatePeaks) alert(`Errore: ${error.message}`);
      return [];
    }
  }

  // ✅ MODALITÀ STANDARD (SINGOLO PERIODO)
  const { jd, mag } = buildAnalysisArraysTyped();

  const res = await fetch(`/agata/variable-stars/api/periodogram.arrow?min_period=${minP_val}&max_period=${maxP_val}&n_freq=${nFreq}`, {
    method: "POST",
    body: buildArrowStreamJDMag(jd, mag)
  });

  const data = await res.json();
  const traces = [
    { x: data.period, y: data.power, mode: "lines", name: "Lomb—Scargle", line: { color: "#38bdf8" } }
  ];

  Object.entries(data.fap_levels).forEach(([k, yval]) => {
    traces.push({
      x: [data.period[0], data.period[data.period.length-1]],
      y: [yval, yval],
      mode: "lines",
      name: fapStyles[k].name,
      line: { ...fapStyles[k], width: 2 },
      hoverinfo: "name"
    });
  });

  traces.push({
    x: data.peaks.map(p => p.period),
    y: data.peaks.map(p => p.power),
    mode: "markers",
    marker: {
      size: 10,
      color: data.peaks.map(p => p.fap < 1e-3 ? "#22c55e" : p.fap < 1e-2 ? "#facc15" : "#f97316"),
      line: {width: 2, color: '#fff'}
    },
    text: data.peaks.map(p => `P: ${p.period.toFixed(6)} d<br>Power: ${p.power.toFixed(3)}<br>FAP: ${p.fap.toExponential(2)}<br>SNR: ${p.snr.toFixed(1)}`),
    hoverinfo: "text",
    name: "Top Peaks"
  });

  Plotly.react(plotDivId, traces, {
    title: "Periodogramma Lomb-Scargle",
    paper_bgcolor: "#ffffff",
    plot_bgcolor: "#fafafa",
    font: {color: "#1e293b"},
    xaxis: {title: "Periodo (giorni)", gridcolor: "#e2e8f0"},
    yaxis: {title: "Power", gridcolor: "#e2e8f0"},
    showlegend: true,
    legend: {x: 0.02, y: 0.98, bgcolor: "rgba(255,255,255,0.8)"},
    margin: {t: 40, b: 40, l: 50, r: 20}
  });

  const pd = document.getElementById(plotDivId);
  if (pd && callbackClick) pd.on("plotly_click", (ev) => { if (ev.points) callbackClick(ev.points[0].x); });

  if (updatePeaks) {
    state.periodogramResult = {
      periods: data.peaks.map(p => p.period),
      amplitudes: [],
      powers: data.peaks.map(p => p.power),
      peaks: data.peaks.map(p => ({ period: p.period, power: p.power, fap: p.fap, snr: p.snr })),
      timestamp: Date.now() / 86400000 + 2440587.5
    };
    console.log('📊 Risultati periodigramma salvati in state per AI Advisor');
    _renderSessionPeriodInfo("plotPeriod-classic-peaks", { periods: data.peaks }, "#38bdf8", callbackClick, "plotPeriod-classic-phase-preview");
  }

  return data.peaks;
}

/**
 * Render tabella riassuntiva periodi multipli
 */
function renderMultiPeriodTable(results, onPeriodClick) {
  const peaksDiv = document.getElementById("peaks");
  if (!peaksDiv) {
    console.error("❌ Elemento #peaks non trovato!");
    return;
  }

  console.log(`📋 Rendering tabella per ${results.length} periodi`);
  peaksDiv.innerHTML = "";

  // Layout orizzontale per i periodi
  peaksDiv.style.flexDirection = "row";
  peaksDiv.style.alignItems = "stretch";
  peaksDiv.style.justifyContent = "flex-start";
  peaksDiv.style.flexWrap = "wrap";
  peaksDiv.style.gap = "10px";

  // Colori per i periodi
  const colors = ["#22c55e", "#3b82f6", "#a855f7", "#f59e0b", "#ef4444"];

  results.forEach((result, idx) => {
    const div = document.createElement("div");
    div.className = "peak-item";
    div.style.cssText = `
      cursor: pointer;
      padding: 10px;
      background: #f8fafc;
      border: 2px solid ${colors[idx % colors.length]};
      border-radius: 6px;
      transition: all 0.2s;
      flex: 1;
      min-width: 200px;
      max-width: 300px;
    `;

    const qualityColor = result.fap < 1e-3 ? "#22c55e" : result.fap < 1e-2 ? "#facc15" : "#f97316";

    // Genera suggerimento specifico per QUESTO periodo
    const suggestion = classifySinglePeriod(result.period);
    console.log(`🔬 P${idx + 1}: ${result.period.toFixed(6)} d → "${suggestion}"`);

    div.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
        <strong style="font-size: 14px; color: ${colors[idx % colors.length]};">
          P${idx + 1}: ${result.period.toFixed(6)} d
        </strong>
        <span style="background: ${qualityColor}; color: #000; padding: 2px 6px; border-radius: 4px; font-size: 9px; font-weight: 600;">
          FAP: ${result.fap.toExponential(1)}
        </span>
      </div>
      <div style="font-size: 10px; color: #64748b; line-height: 1.5; margin-bottom: 8px;">
        Power: <strong>${result.power.toFixed(3)}</strong><br>
        ${result.amplitude != null ? `Amp: <strong>${result.amplitude.toFixed(4)} mag</strong><br>` : ""}
        SNR: <strong>${result.snr.toFixed(1)}</strong>
      </div>
      <div style="font-size: 10px; color: #6366f1; font-weight: 500; font-style: italic; padding-top: 6px; border-top: 1px solid #e2e8f0;">
        ${suggestion}
      </div>
    `;

    div.onmouseover = () => {
      div.style.transform = "translateY(-2px)";
      div.style.boxShadow = "0 4px 12px rgba(0,0,0,0.15)";
    };

    div.onmouseout = () => {
      div.style.transform = "translateY(0)";
      div.style.boxShadow = "none";
    };

    div.onclick = () => onPeriodClick(result.period);

    peaksDiv.appendChild(div);
  });

  // Verifica che sia stato aggiunto
  console.log(`✅ Periodi aggiunti a #peaks orizzontalmente`);
}

// ─── PER-SESSION PERIODOGRAM ──────────────────────────────────────────────────

/**
 * Costruisce array JD/MAG filtrati per una singola sessione (punti attivi)
 * Include detrend e offset, identico a buildAnalysisArraysTyped() ma per sid specifico
 */
function _buildArraysForSession(sid) {
  let count = 0;
  for (let i = 0; i < state.n; i++) {
    if (state.session[i] === sid && state.activePoint[i] === 1) count++;
  }

  const jd = new Float64Array(count);
  const mag = new Float32Array(count);
  let j = 0;

  const auto = state.sessionAutoOffset.get(sid) || 0;
  const manual = state.sessionManualOffset.get(sid) || 0;

  for (let i = 0; i < state.n; i++) {
    if (state.session[i] !== sid || state.activePoint[i] === 0) continue;
    jd[j] = state.jd[i];
    mag[j] = (state.mag[i] - detrendValue(sid, state.jd[i])) + auto + manual;
    j++;
  }

  return { jd, mag };
}

/**
 * Plotta un periodogramma da risultato di computePeriodogramForData() su un div specifico
 */
function _plotSessionPeriodogram(result, plotDivId, sessionColor, title, callbackClick) {
  const spectrum = result.spectrum;
  if (!spectrum || !spectrum.period || spectrum.period.length === 0) return;

  const lineColor = sessionColor || "#38bdf8";
  const fapStyles = {
    "0.1": {dash:"dot", color:"#f97316", name:"FAP 10%"},
    "0.01": {dash:"dash", color:"#facc15", name:"FAP 1%"},
    "0.001": {dash:"solid", color:"#22c55e", name:"FAP 0.1%"}
  };
  const peakColors = ["#22c55e", "#3b82f6", "#a855f7", "#f59e0b", "#ef4444"];

  const traces = [
    { x: spectrum.period, y: spectrum.power, mode: "lines", name: "L-S", line: { color: lineColor, width: 1.5 }, showlegend: false }
  ];

  if (spectrum.fap_levels) {
    Object.entries(spectrum.fap_levels).forEach(([k, yval]) => {
      traces.push({
        x: [spectrum.period[0], spectrum.period[spectrum.period.length-1]],
        y: [yval, yval],
        mode: "lines",
        name: fapStyles[k]?.name || k,
        line: { ...(fapStyles[k] || {}), width: 1.2 },
        hoverinfo: "name",
        showlegend: false
      });
    });
  }

  // Marca i periodi trovati
  result.periods.forEach((p, idx) => {
    if (!p.period || !p.power) return;
    traces.push({
      x: [p.period],
      y: [p.power],
      mode: "markers+text",
      marker: { size: 10, color: peakColors[idx % peakColors.length], symbol: "star", line: {width: 1, color: '#ffffff'} },
      text: [`P${idx + 1}`],
      textposition: "top center",
      textfont: { size: 9, color: peakColors[idx % peakColors.length] },
      hovertemplate: `P${idx+1}: ${p.period.toFixed(6)} d<br>Power: ${p.power.toFixed(3)}<br>FAP: ${p.fap.toExponential(2)}<extra></extra>`,
      name: `P${idx + 1}`,
      showlegend: false
    });
  });

  Plotly.react(plotDivId, traces, {
    title: { text: title, font: { size: 12, color: "#1e293b" } },
    paper_bgcolor: "#ffffff",
    plot_bgcolor: "#fafafa",
    font: { color: "#1e293b", size: 10 },
    xaxis: { title: "P (d)", gridcolor: "#e2e8f0", tickfont: {size: 9}, color: "#475569" },
    yaxis: { title: "Power", gridcolor: "#e2e8f0", tickfont: {size: 9}, color: "#475569" },
    showlegend: false,
    margin: { t: 30, b: 35, l: 45, r: 10 },
    hovermode: "closest"
  });

  const pd = document.getElementById(plotDivId);
  if (pd && callbackClick) {
    pd.on("plotly_click", (ev) => { if (ev.points) callbackClick(ev.points[0].x); });
  }
}

/**
 * Stato per la modalità per-sessione (ricalcolo combinato senza rifare tutti)
 */
const _perSessionState = {
  sessionResults: [],   // [{sid, jd, mag, result}]
  callbackClick: null
};

async function _computePeriodogramPerSession(callbackClick) {
  const minP = Number(document.getElementById("minP").value);
  const maxP = Number(document.getElementById("maxP").value);
  const nFreq = _nFreqCtrl.getValue();
  const enableGlobalPW = document.getElementById("enablePrewhitening")?.checked || false;
  const globalNPeriods = enableGlobalPW ? parseInt(document.getElementById("nPeriods")?.value || 3) : 1;
  const enablePerSession = document.getElementById("enablePerSession")?.checked ?? true;
  const globalAdvancedFourier = enableGlobalPW && (document.getElementById("enableAdvancedPrewhiten")?.checked || false);
  const globalNHarmonics = globalAdvancedFourier ? parseInt(document.getElementById("nHarmonics")?.value || 4) : 4;

  // Sessioni attive (visibili)
  const activeSessions = [...(state.activeSession?.entries() || [])].filter(([, active]) => active);

  if (activeSessions.length === 0) {
    console.warn("⚠️ Nessuna sessione attiva");
    return;
  }

  const container = document.getElementById("plotPeriod-container");
  if (!container) return;

  container.innerHTML = "";
  _perSessionState.sessionResults = [];
  _perSessionState.callbackClick = callbackClick;

  // ─── 1. Sezione COMBINATO (in cima) ───
  const combinedBlock = document.createElement("div");
  combinedBlock.id = "session-period-combined-block";
  combinedBlock.style.cssText = "border-bottom: 2px solid #cbd5e1;";

  // Header combinato con checkbox selezione sessioni
  const combinedHeader = document.createElement("div");
  combinedHeader.style.cssText = "padding: 5px 12px; background: #f1f5f9; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; border-left: 3px solid #475569; border-bottom: 1px solid #e2e8f0;";
  combinedHeader.innerHTML = `<span style="font-size: 11px; font-weight: 700; color: #1e293b;">COMBINATO</span>
    <span id="combined-session-labels" style="display:flex; gap:8px; flex-wrap:wrap; align-items:center;"></span>`;

  // Body combinato: layout diverso in base a per-sessione ON/OFF
  const combinedBody = document.createElement("div");
  const combinedHeight = enablePerSession ? "auto" : "calc(100vh - 320px)";
  combinedBody.style.cssText = `display: flex; height: ${combinedHeight}; align-items: stretch;`;

  const combinedPlotDiv = document.createElement("div");
  combinedPlotDiv.id = "plotPeriod-combined";

  if (enablePerSession) {
    // Per-sessione ON: 3 colonne → 30% periodigramma | 30% period cards | 40% phase preview
    combinedPlotDiv.style.cssText = "flex: 0 0 30%; min-width: 0; min-height: 260px;";

    const combinedPeaksDiv = document.createElement("div");
    combinedPeaksDiv.id = "plotPeriod-combined-peaks";
    combinedPeaksDiv.style.cssText = "flex: 0 0 30%; min-width: 0; padding: 8px; background: #f8fafc; border-left: 1px solid #e2e8f0; display: flex; flex-direction: column; gap: 5px;";
    combinedPeaksDiv.innerHTML = `<div style="color:#94a3b8; font-size:10px; font-style:italic;">Calcolo...</div>`;

    const combinedPhasePreview = document.createElement("div");
    combinedPhasePreview.id = "plotPeriod-combined-phase-preview";
    combinedPhasePreview.style.cssText = "flex: 0 0 40%; min-width: 0; min-height: 260px; border-left: 1px solid #e2e8f0; background: #f8fafc;";
    combinedPhasePreview.innerHTML = `<div style="color:#94a3b8; font-size:10px; padding:8px; text-align:center; margin-top:80px;">Clicca un periodo per la preview</div>`;

    combinedBody.appendChild(combinedPlotDiv);
    combinedBody.appendChild(combinedPeaksDiv);
    combinedBody.appendChild(combinedPhasePreview);
  } else {
    // Per-sessione OFF: 2 colonne → 30% periodigramma | 70% (cards sinistra + phase preview destra)
    combinedPlotDiv.style.cssText = "flex: 0 0 30%; min-width: 0;";

    const combinedInfoContainer = document.createElement("div");
    combinedInfoContainer.style.cssText = "flex: 0 0 70%; min-width: 0; display: flex; flex-direction: row; border-left: 1px solid #e2e8f0; background: #f8fafc;";

    const combinedPeaksDiv = document.createElement("div");
    combinedPeaksDiv.id = "plotPeriod-combined-peaks";
    combinedPeaksDiv.style.cssText = "flex: 0 0 220px; overflow-y: auto; padding: 8px; display: flex; flex-direction: column; gap: 5px; border-right: 1px solid #e2e8f0;";
    combinedPeaksDiv.innerHTML = `<div style="color:#94a3b8; font-size:10px; font-style:italic;">Calcolo...</div>`;

    const combinedPhasePreview = document.createElement("div");
    combinedPhasePreview.id = "plotPeriod-combined-phase-preview";
    combinedPhasePreview.style.cssText = "flex: 1; min-width: 0;";
    combinedPhasePreview.innerHTML = `<div style="color:#94a3b8; font-size:10px; padding:8px; text-align:center; margin-top:60px;">Clicca un periodo per la preview</div>`;

    combinedInfoContainer.appendChild(combinedPeaksDiv);
    combinedInfoContainer.appendChild(combinedPhasePreview);

    combinedBody.appendChild(combinedPlotDiv);
    combinedBody.appendChild(combinedInfoContainer);
  }
  combinedBlock.appendChild(combinedHeader);
  combinedBlock.appendChild(combinedBody);
  container.appendChild(combinedBlock);

  // ─── 2. Prepara strutture sessioni (DOM + dati) prima di calcolare ───
  const sessionDataList = [];

  for (const [sid] of activeSessions) {
    const { jd, mag } = _buildArraysForSession(sid);
    if (jd.length < 5) {
      console.warn(`⚠️ Sessione ${sid}: solo ${jd.length} punti, skip`);
      continue;
    }

    const sessionName = state.sessionName?.get(sid) || state.sessionNameFromDB?.get(sid) || `Sessione ${sid}`;
    const sessionColor = state.sessionColor?.get(sid) || "#38bdf8";
    const pwCheckId = `session-pw-${sid}`;
    const pwNId = `session-pw-n-${sid}`;
    const plotDivId = `plotPeriod-session-${sid}`;
    const blockId = `session-period-block-${sid}`;

    // Checkbox nel header combinato
    const cbLabel = document.createElement("label");
    cbLabel.style.cssText = `display:flex; align-items:center; gap:3px; font-size:10px; color:${sessionColor}; cursor:pointer;`;
    cbLabel.innerHTML = `<input type="checkbox" class="combined-session-cb" data-sid="${sid}" checked style="cursor:pointer;"> ${sessionName}`;
    document.getElementById("combined-session-labels").appendChild(cbLabel);

    // Blocco sessione individuale (solo se "Per sessione" è ON)
    if (!enablePerSession) {
      sessionDataList.push({ sid, jd, mag, sessionName, sessionColor, pwCheckId, pwNId, plotDivId: null });
      _perSessionState.sessionResults.push({ sid, jd, mag, result: null });
      continue;
    }

    // Blocco sessione individuale
    const block = document.createElement("div");
    block.id = blockId;
    block.style.cssText = "border-bottom: 1px solid #e2e8f0;";

    const header = document.createElement("div");
    header.style.cssText = `padding: 5px 12px; background: #f8fafc; display: flex; align-items: center; gap: 8px; border-left: 3px solid ${sessionColor}; border-bottom: 1px solid #e2e8f0;`;
    // Se il pre-whitening globale è attivo, il checkbox locale inizia checked e lo stato riflette enableGlobalPW
    const pwChecked = enableGlobalPW ? "checked" : "";
    header.innerHTML = `
      <span style="font-size:11px; font-weight:600; color:${sessionColor}; text-shadow: 0 0 0 transparent;">${sessionName}</span>
      <span style="font-size:10px; color:#64748b;">${jd.length} pt</span>
      <div style="margin-left:auto; display:flex; align-items:center; gap:6px;">
        <label style="font-size:10px; color:#64748b; display:flex; align-items:center; gap:3px; cursor:pointer;">
          <input type="checkbox" id="${pwCheckId}" ${pwChecked} style="cursor:pointer;">
          Pre-w.
        </label>
        <select id="${pwNId}" style="width:40px; padding:1px 2px; font-size:10px; background:#ffffff; color:#334155; border:1px solid #cbd5e1; border-radius:3px;">
          <option value="2">2</option>
          <option value="3" selected>3</option>
          <option value="4">4</option>
          <option value="5">5</option>
        </select>
        <button data-sid="${sid}" class="session-recalc-btn"
          style="padding:1px 7px; font-size:10px; background:#ffffff; color:#64748b; border:1px solid #cbd5e1; border-radius:3px; cursor:pointer;">
          ↻
        </button>
      </div>
    `;

    const body = document.createElement("div");
    body.style.cssText = "display: flex; height: auto; align-items: stretch;";

    // 3 colonne: 30% periodigramma | 30% period cards | 40% phase preview
    const plotDiv = document.createElement("div");
    plotDiv.id = plotDivId;
    plotDiv.style.cssText = "flex: 0 0 30%; min-width: 0; min-height: 200px;";

    const infoDiv = document.createElement("div");
    infoDiv.id = `session-period-info-${sid}`;
    infoDiv.style.cssText = "flex: 0 0 30%; min-width: 0; padding: 8px; background: #f8fafc; border-left: 1px solid #e2e8f0; display: flex; flex-direction: column; gap: 5px;";
    infoDiv.innerHTML = `<div style="color:#94a3b8; font-size:10px; font-style:italic;">Calcolo...</div>`;

    const sessionPhasePreview = document.createElement("div");
    sessionPhasePreview.id = `session-phase-preview-${sid}`;
    sessionPhasePreview.style.cssText = "flex: 0 0 40%; min-width: 0; min-height: 200px; border-left: 1px solid #e2e8f0; background: #f8fafc;";
    sessionPhasePreview.innerHTML = `<div style="color:#94a3b8; font-size:10px; padding:8px; text-align:center; margin-top:60px;">Clicca un periodo</div>`;

    body.appendChild(plotDiv);
    body.appendChild(infoDiv);
    body.appendChild(sessionPhasePreview);
    block.appendChild(header);
    block.appendChild(body);
    container.appendChild(block);

    sessionDataList.push({ sid, jd, mag, sessionName, sessionColor, pwCheckId, pwNId, plotDivId });
    _perSessionState.sessionResults.push({ sid, jd, mag, result: null });
  }

  // ─── 3. Event listeners ───
  container.addEventListener("click", async (e) => {
    const btn = e.target.closest(".session-recalc-btn");
    if (!btn) return;
    const sid = parseInt(btn.dataset.sid);
    await _recalcOneSession(sid, minP, maxP, nFreq, callbackClick);
  });

  container.addEventListener("change", (e) => {
    if (e.target.classList.contains("combined-session-cb")) {
      _recomputeCombined(minP, maxP, globalNPeriods, enableGlobalPW, nFreq, callbackClick);
    }
  });

  // ─── 4. Calcola prima il combinato (con tutti i dati disponibili) ───
  // Merge tutti i JD/MAG delle sessioni valide per il combinato iniziale
  {
    const allJd = [], allMag = [];
    for (const s of sessionDataList) {
      for (let i = 0; i < s.jd.length; i++) { allJd.push(s.jd[i]); allMag.push(s.mag[i]); }
    }
    if (allJd.length >= 5) {
      const jdAll = new Float64Array(allJd);
      const magAll = new Float32Array(allMag);
      try {
        const result = await computePeriodogramForData(jdAll, magAll, minP, maxP, enableGlobalPW, globalNPeriods, globalAdvancedFourier, globalNHarmonics, nFreq);
        _plotSessionPeriodogram(result, "plotPeriod-combined", "#e5e7eb",
          `Combinato (${sessionDataList.length} sessioni, ${allJd.length} pt)`, callbackClick);
        const combinedSids = new Set(sessionDataList.map(s => s.sid));
        _renderSessionPeriodInfo("plotPeriod-combined-peaks", result, "#e5e7eb", callbackClick, "plotPeriod-combined-phase-preview", combinedSids);
      } catch (err) {
        console.error("❌ Errore combinato iniziale:", err);
        combinedPlotDiv.innerHTML = `<div style="padding:16px;color:#ef4444;font-size:12px;">Errore: ${err.message}</div>`;
      }
    }
  }

  // ─── 5. Calcola sessioni individuali in sequenza (solo se "Per sessione" ON) ───
  if (!enablePerSession) return;

  for (const s of sessionDataList) {
    const { sid, jd, mag, sessionName, sessionColor, pwCheckId, pwNId, plotDivId } = s;
    if (!plotDivId) continue; // skip sessioni senza blocco (modalità combinato-only)
    const usePrewhiten = document.getElementById(pwCheckId)?.checked || false;
    const nPeriods = usePrewhiten ? parseInt(document.getElementById(pwNId)?.value || 3) : 1;

    try {
      const result = await computePeriodogramForData(jd, mag, minP, maxP, usePrewhiten, nPeriods, globalAdvancedFourier, globalNHarmonics, nFreq);
      const entry = _perSessionState.sessionResults.find(e => e.sid === sid);
      if (entry) entry.result = result;

      const titleStr = globalAdvancedFourier ? `Fourier ${globalNHarmonics}arm.` : usePrewhiten ? `pre-whitening (${result.periods.length} periodi)` : `Lomb-Scargle`;
      _plotSessionPeriodogram(result, plotDivId, sessionColor, titleStr, callbackClick);
      _renderSessionPeriodInfo(`session-period-info-${sid}`, result, sessionColor, callbackClick, `session-phase-preview-${sid}`, new Set([sid]));
    } catch (err) {
      console.error(`❌ Errore sessione ${sid}:`, err);
      const pd = document.getElementById(plotDivId);
      if (pd) pd.innerHTML = `<div style="padding:8px;color:#ef4444;font-size:11px;">Errore: ${err.message}</div>`;
      const id = document.getElementById(`session-period-info-${sid}`);
      if (id) id.innerHTML = `<div style="color:#ef4444;font-size:10px;">Errore</div>`;
    }
  }
}

/**
 * Mini phase-folded preview inline nel periodigramma.
 * @param {string} divId - ID del div contenitore
 * @param {number} period - Periodo in giorni
 * @param {Set<number>|null} [sessionFilter=null] - Se fornito, mostra solo queste sessioni
 */
function renderMiniPhasePreview(divId, period, sessionFilter) {
  const div = document.getElementById(divId);
  if (!div) return;

  const { traces } = computePhaseData(period, { sessionFilter: sessionFilter || null });
  if (traces.length === 0) {
    div.innerHTML = `<div style="color:#94a3b8; font-size:10px; padding:8px; text-align:center;">Nessun dato</div>`;
    return;
  }

  const plotTraces = traces.map(t => ({
    x: t.x, y: t.y,
    type: 'scattergl', mode: 'markers',
    marker: { size: 2, color: t.color, opacity: 0.5 },
    hoverinfo: 'skip',
    showlegend: false
  }));

  const layout = {
    margin: { t: 14, b: 18, l: 30, r: 4 },
    xaxis: { range: [0, 1], dtick: 0.5, tickfont: { size: 8, color: '#94a3b8' }, showgrid: true, gridcolor: '#f1f5f9' },
    yaxis: { autorange: 'reversed', tickfont: { size: 8, color: '#94a3b8' }, showgrid: true, gridcolor: '#f1f5f9' },
    plot_bgcolor: '#ffffff',
    paper_bgcolor: '#f8fafc',
    showlegend: false,
    annotations: [{
      text: `P = ${period.toFixed(6)} d`,
      xref: 'paper', yref: 'paper', x: 0.5, y: 1.0,
      showarrow: false,
      font: { size: 9, color: '#475569', family: 'monospace' }
    }]
  };

  Plotly.react(divId, plotTraces, layout, { displayModeBar: false, responsive: true, staticPlot: true }).then(() => {
    Plotly.Plots.resize(div);
  });
}

/**
 * Renderizza il pannello informativo periodi (colonna destra 30%)
 */
function _renderSessionPeriodInfo(divId, result, sessionColor, callbackClick, previewDivId, sessionFilter) {
  const div = document.getElementById(divId);
  if (!div) return;

  const peakColors = ["#22c55e", "#3b82f6", "#a855f7", "#f59e0b", "#ef4444"];
  const periods = result.periods.slice(0, 5);

  if (periods.length === 0) {
    div.innerHTML = `<div style="color:#475569; font-size:10px;">Nessun picco trovato</div>`;
    return;
  }

  div.innerHTML = "";
  periods.forEach((p, idx) => {
    if (!p.period) return;
    const col = peakColors[idx % peakColors.length];
    const fapColor = p.fap < 1e-3 ? "#22c55e" : p.fap < 1e-2 ? "#facc15" : "#f97316";
    const typeStr = classifySinglePeriod(p.period);

    const card = document.createElement("div");
    card.style.cssText = `
      padding: 6px 8px;
      border-left: 2px solid ${col};
      background: #ffffff;
      border: 1px solid #e2e8f0;
      border-left: 2px solid ${col};
      border-radius: 3px;
      cursor: pointer;
      transition: background 0.15s;
    `;
    card.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:3px;">
        <span style="font-size:11px; font-weight:700; color:${col}; font-family:monospace;">P${idx+1}: ${p.period.toFixed(6)} d</span>
        <span style="display:flex; align-items:center; gap:4px;">
          <span style="font-size:9px; background:${fapColor}; color:#fff; padding:1px 4px; border-radius:2px; font-weight:600;">${p.fap < 1e-99 ? '<10⁻⁹⁹' : p.fap.toExponential(1)}</span>
          <button class="go-to-phase-btn" title="Apri nel tab Fase"
            style="padding:1px 5px; font-size:10px; background:#3b82f6; color:#fff; border:none; border-radius:3px; cursor:pointer; line-height:1.4;">→</button>
        </span>
      </div>
      <div style="font-size:9px; color:#64748b; line-height:1.6;">
        Power: <b style="color:#334155;">${p.power.toFixed(3)}</b>
        &nbsp;·&nbsp;SNR: <b style="color:#334155;">${p.snr.toFixed(1)}</b>
        ${p.amplitude != null ? `&nbsp;·&nbsp;Amp: <b style="color:#334155;">${p.amplitude.toFixed(4)}</b>` : ""}
      </div>
      <div style="font-size:9px; color:#6366f1; font-style:italic; margin-top:2px;">${typeStr}</div>
    `;
    // Hover
    card.onmouseover = () => { if (!card.classList.contains('period-card-active')) card.style.background = "#f1f5f9"; };
    card.onmouseout = () => { if (!card.classList.contains('period-card-active')) card.style.background = "#ffffff"; };
    // Click: aggiorna mini phase preview
    card.onclick = (e) => {
      if (e.target.closest('.go-to-phase-btn')) return;
      if (previewDivId) renderMiniPhasePreview(previewDivId, p.period, sessionFilter);
      div.querySelectorAll('.period-card-active').forEach(c => { c.classList.remove('period-card-active'); c.style.background = '#ffffff'; });
      card.classList.add('period-card-active');
      card.style.background = '#eff6ff';
    };
    // Bottone →: switch completo al tab Fase
    const goBtn = card.querySelector('.go-to-phase-btn');
    if (goBtn) goBtn.onclick = (e) => { e.stopPropagation(); if (callbackClick) callbackClick(p.period); };
    div.appendChild(card);
  });

  // Auto-preview del periodo piu forte (P1)
  if (previewDivId && periods.length > 0 && periods[0].period) {
    renderMiniPhasePreview(previewDivId, periods[0].period, sessionFilter);
    const firstCard = div.querySelector('div');
    if (firstCard) { firstCard.classList.add('period-card-active'); firstCard.style.background = '#eff6ff'; }
  }
}

/**
 * Ricalcola una singola sessione (bottone ↻)
 */
async function _recalcOneSession(sid, minP, maxP, nFreq, callbackClick) {
  const pwCheckId = `session-pw-${sid}`;
  const pwNId = `session-pw-n-${sid}`;
  const usePrewhiten = document.getElementById(pwCheckId)?.checked || false;
  const nPeriods = usePrewhiten ? parseInt(document.getElementById(pwNId)?.value || 3) : 1;
  const advancedFourier = usePrewhiten && (document.getElementById("enableAdvancedPrewhiten")?.checked || false);
  const nHarmonics = advancedFourier ? parseInt(document.getElementById("nHarmonics")?.value || 4) : 4;

  const entry = _perSessionState.sessionResults.find(e => e.sid === sid);
  if (!entry) return;

  const sessionColor = state.sessionColor?.get(sid) || "#38bdf8";
  const plotDivId = `plotPeriod-session-${sid}`;

  try {
    const result = await computePeriodogramForData(entry.jd, entry.mag, minP, maxP, usePrewhiten, nPeriods, advancedFourier, nHarmonics, nFreq);
    entry.result = result;

    const titleStr = advancedFourier ? `Fourier ${nHarmonics}arm.` : usePrewhiten ? `pre-whitening (${result.periods.length} periodi)` : `Lomb-Scargle`;

    _plotSessionPeriodogram(result, plotDivId, sessionColor, titleStr, callbackClick);
    _renderSessionPeriodInfo(`session-period-info-${sid}`, result, sessionColor, callbackClick, `session-phase-preview-${sid}`, new Set([sid]));
  } catch (err) {
    console.error(`❌ Errore ricalcolo sessione ${sid}:`, err);
  }
}

/**
 * Ricalcola solo il combinato con le sessioni attualmente selezionate via checkbox
 */
async function _recomputeCombined(minP, maxP, nPeriods, enablePW, nFreq, callbackClick) {
  const combinedPlotDiv = document.getElementById("plotPeriod-combined");
  const combinedPeaksDiv = document.getElementById("plotPeriod-combined-peaks");
  if (!combinedPlotDiv) return;

  // Raccoglie sessioni selezionate
  const selectedSids = new Set(
    [...document.querySelectorAll(".combined-session-cb:checked")].map(cb => parseInt(cb.dataset.sid))
  );

  // Merge JD/MAG delle sessioni selezionate
  const allJd = [];
  const allMag = [];
  for (const entry of _perSessionState.sessionResults) {
    if (!selectedSids.has(entry.sid) || !entry.jd) continue;
    for (let i = 0; i < entry.jd.length; i++) {
      allJd.push(entry.jd[i]);
      allMag.push(entry.mag[i]);
    }
  }

  if (allJd.length < 5) {
    combinedPlotDiv.innerHTML = `<div style="padding:16px; color:#94a3b8; font-size:12px;">Seleziona almeno una sessione con dati sufficienti.</div>`;
    return;
  }

  const jd = new Float64Array(allJd);
  const mag = new Float32Array(allMag);

  const advancedFourier = enablePW && (document.getElementById("enableAdvancedPrewhiten")?.checked || false);
  const nHarmonics = advancedFourier ? parseInt(document.getElementById("nHarmonics")?.value || 4) : 4;

  try {
    if (combinedPeaksDiv) combinedPeaksDiv.innerHTML = `<div style="color:#94a3b8; font-size:10px; font-style:italic;">Calcolo...</div>`;
    const result = await computePeriodogramForData(jd, mag, minP, maxP, enablePW, nPeriods, advancedFourier, nHarmonics, nFreq);

    _plotSessionPeriodogram(result, "plotPeriod-combined", "#e5e7eb",
      `Combinato (${selectedSids.size} sessioni, ${jd.length} pt)`, callbackClick);

    _renderSessionPeriodInfo("plotPeriod-combined-peaks", result, "#e5e7eb", callbackClick, "plotPeriod-combined-phase-preview", selectedSids);

    state.periodogramResult = {
      periods: result.periods.map(p => p.period),
      amplitudes: result.periods.map(p => p.amplitude || 0),
      powers: result.periods.map(p => p.power),
      peaks: result.periods.map(p => ({ period: p.period, power: p.power, fap: p.fap, snr: p.snr, amplitude: p.amplitude })),
      timestamp: Date.now() / 86400000 + 2440587.5
    };

  } catch (err) {
    console.error("❌ Errore combinato:", err);
    combinedPlotDiv.innerHTML = `<div style="padding:16px; color:#ef4444; font-size:12px;">Errore: ${err.message}</div>`;
  }
}
