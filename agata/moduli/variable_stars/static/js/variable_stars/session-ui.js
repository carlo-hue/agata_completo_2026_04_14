// session-ui.js
import { state, colorForSession, nameForSession, invalidateSamplingCache } from './state.js';
import { drawLightcurve, zoomToSession, resetSessionZoom } from './plots.js';
import { computeDetrendCoefficients, calculateGlobalSliderRange, recalculateManualAmplitude } from './math-logic.js';
import { computePhase, invalidateEpoch } from './phase-analysis.js';
import { calculatePhaseStatistics, renderPhaseStatistics } from './phase-statistics.js';
import { updateEphemerisIfVisible } from './phase-controls.js';
import { formatExtremaForSession } from './extrema-analysis.js';

/**
 * Aggiorna i contatori e le statistiche delle sessioni
 */
export function updateCounters() {
  const div = document.getElementById("stats");
  if (!div) return; // Se stats box non esiste, esci gracefully
  let total = 0, rows = [];

  // Mostra TUTTE le sessioni (anche disabilitate) con checkbox di esclusione
  Array.from(state.activeSession.keys()).sort((a, b) => a - b).forEach(sid => {
    const enabled = state.activeSession.get(sid);
    let cnt = 0;
    for (let i = 0; i < state.n; i++) {
      if (state.activePoint[i] === 1 && state.session[i] === sid) cnt++;
    }
    if (enabled) total += cnt;
    rows.push(`
      <div style="display:flex;align-items:center;gap:6px;padding:2px 0;">
        <input type="checkbox" data-counter-sess="${sid}" ${enabled ? 'checked' : ''}
               style="width:13px;height:13px;cursor:pointer;flex-shrink:0;accent-color:${colorForSession(sid)};">
        <span style="width:11px;height:11px;background:${colorForSession(sid)};border-radius:50%;flex-shrink:0;"></span>
        <span style="flex:1;${enabled ? '' : 'color:#94a3b8;'}">${nameForSession(sid)}:</span>
        <strong style="${enabled ? '' : 'color:#94a3b8;'}">${cnt}</strong>
      </div>
    `);
  });

  let html = rows.join("");

  // Calcola punti rimossi
  let removed = 0;
  for (let i = 0; i < state.n; i++) {
    if (state.activePoint[i] === 0) removed++;
  }

  html += `<hr style="margin: 8px 0; border:none; border-top:1px solid var(--border);">`;
  html += `<div style="display: flex; justify-content: space-between; align-items: center; padding: 4px 0;">
    <strong>Attivi:</strong>
    <span style="font-weight: 700; color: #2563eb;">${total}</span>
  </div>`;

  if (removed > 0) {
    html += `<div style="display: flex; justify-content: space-between; align-items: center; padding: 4px 0;">
      <strong>Rimossi:</strong>
      <span style="font-weight: 700; color: #ef4444;">${removed}</span>
    </div>`;
  }

  // ✅ DETTAGLIO SELEZIONI (se presenti)
  if (state.selectedRaw.size > 0 || state.sigmaClipSuggested.size > 0) {
    const manualCount = state.selectedRaw.size;
    const sigmaCount = state.sigmaClipSuggested.size;

    // Calcola overlap
    const overlap = [...state.selectedRaw].filter(i => state.sigmaClipSuggested.has(i)).length;
    const uniqueSelected = new Set([...state.selectedRaw, ...state.sigmaClipSuggested]).size;

    // Conta per sessione
    const sigmaBySession = new Map();
    const manualBySession = new Map();

    for (const idx of state.sigmaClipSuggested) {
      if (state.activePoint[idx] === 0) continue;
      const sid = state.session[idx];
      sigmaBySession.set(sid, (sigmaBySession.get(sid) || 0) + 1);
    }

    for (const idx of state.selectedRaw) {
      if (state.activePoint[idx] === 0) continue;
      if (state.sigmaClipSuggested.has(idx)) continue; // Evita conteggio doppio
      const sid = state.session[idx];
      manualBySession.set(sid, (manualBySession.get(sid) || 0) + 1);
    }

    html += `
      <hr style="margin: 8px 0; border:none; border-top:2px solid #f59e0b;">
      <div style="padding: 10px; background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); border-radius: 6px; border: 2px solid #f59e0b;">
        <div style="font-weight: 700; margin-bottom: 8px; color: #92400e; text-align: center;">
          🎯 Selezionati per Rimozione
        </div>
    `;

    // ✅ SIGMA CLIPPING
    if (sigmaCount > 0) {
      html += `
        <div style="margin-bottom: 8px; padding: 6px; background: white; border-radius: 4px; border-left: 3px solid #ef4444;">
          <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">
            <span style="color: #ef4444; font-size: 14px; font-weight: bold;">✕</span>
            <strong>Outlier σ-clip:</strong>
            <span style="margin-left: auto; font-weight: 700; color: #ef4444;">${sigmaCount}</span>
          </div>
      `;

      // Dettaglio per sessione
      if (sigmaBySession.size > 0) {
        html += '<div style="font-size: 11px; padding-left: 20px;">';
        sigmaBySession.forEach((count, sid) => {
          html += `
            <div style="display: flex; gap: 4px; align-items: center;">
              <span style="width: 8px; height: 8px; background: ${colorForSession(sid)}; border-radius: 50%;"></span>
              <span>${nameForSession(sid)}: ${count}</span>
            </div>
          `;
        });
        html += '</div>';
      }

      html += '</div>';
    }


    // ✅ SELEZIONE MANUALE
    if (manualCount > 0) {
      html += `
        <div style="margin-bottom: 8px; padding: 6px; background: white; border-radius: 4px; border-left: 3px solid #f59e0b;">
          <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">
            <span style="color: #f59e0b; font-size: 14px; font-weight: bold;">◆</span>
            <strong>Manuali:</strong>
            <span style="margin-left: auto; font-weight: 700; color: #f59e0b;">${manualCount - overlap}</span>
          </div>
      `;

      // Dettaglio per sessione
      if (manualBySession.size > 0) {
        html += '<div style="font-size: 11px; padding-left: 20px;">';
        manualBySession.forEach((count, sid) => {
          html += `
            <div style="display: flex; gap: 4px; align-items: center;">
              <span style="width: 8px; height: 8px; background: ${colorForSession(sid)}; border-radius: 50%;"></span>
              <span>${nameForSession(sid)}: ${count}</span>
            </div>
          `;
        });
        html += '</div>';
      }

      html += '</div>';
    }

    // ✅ OVERLAP
    if (overlap > 0) {
      html += `
        <div style="font-size: 11px; padding: 4px 6px; background: white; border-radius: 4px; text-align: center; color: #6b7280; margin-bottom: 6px;">
          (${overlap} punti in entrambe le selezioni)
        </div>
      `;
    }

    // ✅ TOTALE
    html += `
        <div style="padding: 6px; background: #dc2626; color: white; border-radius: 4px; text-align: center; font-weight: 700; font-size: 13px;">
          TOTALE DA RIMUOVERE: ${uniqueSelected}
        </div>
      </div>
    `;
  }

  div.innerHTML = html;

  // Checkbox di esclusione sessione nella lista contatori
  div.querySelectorAll('[data-counter-sess]').forEach(cb => {
    cb.addEventListener('change', (e) => {
      const sid = parseInt(e.target.dataset.counterSess);
      state.activeSession.set(sid, e.target.checked);
      invalidateSamplingCache();
      invalidateEpoch();
      computeDetrendCoefficients();
      drawLightcurve();
      updateCounters();
      // Sincronizza il checkbox nella sezione Sessioni & Allineamenti
      const mainCb = document.getElementById(`cb${sid}`);
      if (mainCb) mainCb.checked = e.target.checked;
      if (state.lastPeriod) {
        computePhase();
        const phaseStats = calculatePhaseStatistics();
        renderPhaseStatistics(phaseStats);
      }
    });
  });
}

/**
 * Renderizza la lista delle sessioni con tutti i controlli
 */
export function renderSessionList() {
  const div = document.getElementById("sessionList");
  div.innerHTML = "";

  Array.from(state.activeSession.keys()).sort((a,b)=>a-b).forEach(sid => {
    const row = document.createElement("div");
    row.className = "session-card";

    const auto = state.sessionAutoOffset.get(sid) || 0;
    const manual = state.sessionManualOffset.get(sid) || 0;

    // ✅ Usa range salvato o default [-2, 2]
    let sliderRange = state.sessionSliderRange.get(sid);
    if (!sliderRange) {
      // Prima volta: usa default conservativo
      sliderRange = { min: -2, max: 2 };
    }

    row.innerHTML = `
      <!-- Prima riga: nome e controlli principali -->
      <div class="session-row-1">
        <input type="checkbox" id="cb${sid}" class="session-checkbox"
               ${state.activeSession.get(sid)?'checked':''}>
        <input type="text" id="name${sid}" value="${nameForSession(sid)}"
               class="session-name">
        <input type="color" id="color${sid}" value="${colorForSession(sid)}"
               class="session-color">
        <button id="zoom${sid}" class="session-zoom-btn" title="Zoom su questa sessione" style="background:none;border:1px solid #cbd5e1;border-radius:4px;cursor:pointer;padding:2px 5px;font-size:12px;line-height:1.4;color:#475569;" onmouseenter="this.style.background='#f1f5f9'" onmouseleave="this.style.background='none'">&#128269;</button>
      </div>

      <!-- Seconda riga: offset -->
      <div class="session-row-2">
        <!-- Offset automatico -->
        <div class="offset-group">
          <label class="offset-label">Auto Offset</label>
          <div class="offset-controls">
            <span class="offset-value">${auto >= 0 ? "+" : ""}${auto.toFixed(4)}</span>
          </div>
        </div>

        <!-- Offset manuale con delta mag -->
        <div class="offset-group">
          <label class="offset-label">
            Manuale <span class="delta-mag-label">(Δ mag)</span>
          </label>
          <div class="offset-controls">
            <input type="range" id="slider${sid}" class="offset-slider"
                   min="${sliderRange.min}" max="${sliderRange.max}" step="0.01" value="${manual}">
            <input type="number" step="0.01" id="off${sid}"
                   value="${manual}" class="offset-input">
          </div>
        </div>
      </div>

      <!-- Terza riga: Estremi (Min, Max, Ampiezza) -->
      <div id="extrema${sid}" class="session-extrema">
        ${formatExtremaForSession(sid)}
      </div>

      <!-- Quarta riga: Sigma zoom + info outlier -->
      <div id="sigma-zoom-row-${sid}" style="display:flex;align-items:center;gap:5px;padding:3px 0 1px;font-size:11px;">
        <label style="color:#64748b;white-space:nowrap;">σ zoom:</label>
        <input type="number" id="sigmaZoom${sid}" value="5" min="1" max="10" step="0.5"
               style="width:44px;padding:1px 4px;font-size:11px;border:1px solid #cbd5e1;border-radius:3px;">
        <span id="sigmaZoomInfo${sid}" style="flex:1;color:#ef4444;font-size:10px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;"></span>
        <button id="removeOutliersSid${sid}"
                style="display:none;font-size:10px;padding:2px 6px;background:#fee2e2;color:#dc2626;border:1px solid #fca5a5;border-radius:3px;cursor:pointer;white-space:nowrap;">
          Rimuovi
        </button>
      </div>
    `;


    div.appendChild(row);

    // ============================================
    // ✅ FUNZIONE HELPER per aggiornamento completo fase
    // ============================================
    const updatePhaseIfNeeded = () => {
      if (state.lastPeriod) {
        computePhase();
        const stats = calculatePhaseStatistics();
        renderPhaseStatistics(stats);
        updateEphemerisIfVisible();
      }
    };

    // ============================================
    // Event listeners
    // ============================================

    // ✅ CHECKBOX: Attiva/disattiva sessione
    row.querySelector(`#cb${sid}`).onchange = (e) => {
      state.activeSession.set(sid, e.target.checked);
      invalidateSamplingCache();
      invalidateEpoch();
      computeDetrendCoefficients();
      drawLightcurve();
      updateCounters();

      // ✅ Aggiorna fase COMPLETA (con stats + effemeridi)
      updatePhaseIfNeeded();
    };

    // ✅ OFFSET: Funzione condivisa per slider + input
    const updateOffset = (value) => {
      const val = parseFloat(value) || 0;
      state.sessionManualOffset.set(sid, val);
      row.querySelector(`#slider${sid}`).value = val;
      row.querySelector(`#off${sid}`).value = val;
      drawLightcurve();
      updateCounters();

      // ✅ Aggiorna fase COMPLETA
      updatePhaseIfNeeded();
    };

    // ✅ SLIDER: Input + supporto tasti freccia sinistra/destra
    const sliderEl = row.querySelector(`#slider${sid}`);
    sliderEl.oninput = (e) => updateOffset(e.target.value);

    // ✅ Tasti freccia sinistra/destra per lo slider
    sliderEl.addEventListener('keydown', (e) => {
      const step = parseFloat(sliderEl.step) || 0.01;
      const currentValue = parseFloat(sliderEl.value) || 0;

      if (e.key === 'ArrowLeft') {
        e.preventDefault();
        const newValue = Math.max(parseFloat(sliderEl.min), currentValue - step);
        updateOffset(newValue);
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        const newValue = Math.min(parseFloat(sliderEl.max), currentValue + step);
        updateOffset(newValue);
      }
    });

    // ✅ INPUT NUMBER: Change + supporto nativo frecce su/giù
    const inputEl = row.querySelector(`#off${sid}`);
    inputEl.onchange = (e) => updateOffset(e.target.value);

    // ✅ Input su frecce su/giù (già supportato nativamente da type="number")
    inputEl.oninput = (e) => updateOffset(e.target.value);

    // ✅ NOME: Cambio nome sessione
    row.querySelector(`#name${sid}`).onchange = (e) => {
      state.sessionName.set(sid, e.target.value || `S${sid}`);
      updateCounters();
      drawLightcurve();

      // ✅ Aggiorna fase COMPLETA (nome appare nella legenda)
      updatePhaseIfNeeded();
    };

    // ✅ COLORE: Cambio colore sessione
    row.querySelector(`#color${sid}`).onchange = (e) => {
      state.sessionColor.set(sid, e.target.value);
      drawLightcurve();
      updateCounters();

      // ✅ Aggiorna fase COMPLETA (colore cambia nel plot)
      updatePhaseIfNeeded();
    };

    // ✅ ZOOM: Zoom sulla sessione con sigma-clip locale
    let _lastOutlierIndices = [];

    const doZoom = async () => {
      const sigma = parseFloat(row.querySelector(`#sigmaZoom${sid}`)?.value || 5);
      const result = await zoomToSession(sid, sigma);
      _lastOutlierIndices = result?.outlierIndices || [];

      const infoEl = row.querySelector(`#sigmaZoomInfo${sid}`);
      const removeBtn = row.querySelector(`#removeOutliersSid${sid}`);

      if (result?.nOutliers > 0) {
        if (infoEl) infoEl.textContent = `${result.nOutliers} outlier σ${sigma}`;
        if (removeBtn) removeBtn.style.display = '';
      } else {
        if (infoEl) infoEl.textContent = '';
        if (removeBtn) removeBtn.style.display = 'none';
      }

      // Aggiorna label navigator e sincronizza sigma nel navigator se questa è la sessione attiva
      if (window._sessionNavSetActive) window._sessionNavSetActive(sid, sigma);
    };

    row.querySelector(`#zoom${sid}`).onclick = doZoom;

    // ✅ RIMUOVI OUTLIER SESSIONE: rimuove definitivamente solo gli outlier di questa sessione
    row.querySelector(`#removeOutliersSid${sid}`).onclick = async () => {
      if (_lastOutlierIndices.length === 0) return;

      for (const idx of _lastOutlierIndices) {
        state.activePoint[idx] = 0;
        state.sigmaClipSuggested.delete(idx);
      }
      _lastOutlierIndices = [];

      const infoEl = row.querySelector(`#sigmaZoomInfo${sid}`);
      const removeBtn = row.querySelector(`#removeOutliersSid${sid}`);
      if (infoEl) infoEl.textContent = '';
      if (removeBtn) removeBtn.style.display = 'none';

      // Ridisegna prima (aggiorna legenda e rimuove tracce outlier rosse)
      await drawLightcurve();
      updateCounters();
      // Poi reapplica zoom sulla sessione (senza ricalcolare sigma-clip)
      const gdEl = document.getElementById("plotLC");
      if (gdEl?.data) {
        const opacities = gdEl.data.map(trace => trace.sid === sid ? 0.85 : 0.12);
        Plotly.restyle(gdEl, { "marker.opacity": opacities });
      }
    };
  });

}

/**
 * Ricalcola l'ampiezza manuale (✏️) e i range degli slider
 * usando sigma clipping sui dati/sessioni attivi correnti
 */
export function recalculateAllSliderRanges() {
  // ✅ STEP 1: Ricalcola ampiezza manuale con sigma clipping
  const ampResult = recalculateManualAmplitude();

  if (!ampResult) {
    console.warn('⚠️ Impossibile ricalcolare ampiezza manuale');
    return 0;
  }

  // ✅ STEP 2: Calcola range slider basato sulla nuova ampiezza
  const globalRange = calculateGlobalSliderRange();

  let updated = 0;

  // ✅ STEP 3: Applica il range a tutte le sessioni attive
  state.activeSession.forEach((enabled, sid) => {
    if (!enabled) return;

    // Salva nello state
    state.sessionSliderRange.set(sid, { min: globalRange.min, max: globalRange.max });
    updated++;
  });

  // ✅ STEP 4: Ridisegna plot fase con le nuove linee
  if (state.lastPeriod) {
    computePhase();
  }

  // ✅ STEP 5: Ri-renderizza statistiche di fase
  const stats = calculatePhaseStatistics();
  if (stats) {
    renderPhaseStatistics(stats);
  }

  // ✅ STEP 6: Ri-renderizza lista sessioni
  renderSessionList();

  console.log(`✅ Ampiezza manuale: ${ampResult.amplitude.toFixed(3)} mag → Range slider: [${globalRange.min}, ${globalRange.max}] applicato a ${updated} sessioni`);

  // ✅ STEP 7: Aggiorna campo ampiezza nel tab Analisi di Supporto
  if (window.updateSupportAmplitude && state.manualAmplitude) {
    window.updateSupportAmplitude(state.manualAmplitude);
  }

  return updated;
}
