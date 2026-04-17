//main.js
import {
  state,
  rebuildDefaults,
  nameForSession,
  colorForSession,
  getSampledIndices,           // ✅ NUOVO
  setActiveSamplingPercent,    // ✅ NUOVO
  invalidateSamplingCache,     // ✅ NUOVO
  activeSamplingPercent        // ✅ NUOVO
} from './state.js';
import { unpackActiveBitsetFromBase64, packActiveBitsetToBase64 } from '../common/utils-arrow.js';
import { computeDetrendCoefficients } from './math-logic.js';
import { drawLightcurve, computePeriodogram, updateDeltaTDisplay, updateDeltaMagDisplay, zoomToSession, resetSessionZoom, initNFreqController, refreshNFreqSuggestion } from './plots.js';
import { computePhase } from './phase-analysis.js';
import { renderSessionList, updateCounters, recalculateAllSliderRanges } from './session-ui.js';
import { renderPeriodPeaks } from './period-ui.js';
import { loadDataArrow } from './data-loader.js';
window.loadDataArrow = loadDataArrow;
import { exportDetrendedCSV, exportFoldedCSV, exportPhasePNG } from './export-utils.js';
import { getCurrentLCRange } from './plots.js';
import {
  alignSessionsByPhaseMedian,
  alignSessionsZeroPoint
} from "./math-logic.js";
import { HistoryTracker } from './history-tracker.js';
import { initializePhaseControls, goToPhaseTabAndUpdate } from './phase-controls.js';
import { computeExtremaPerSession } from './extrema-analysis.js';
import { initAIAdvisor } from './ai-advisor.js';
import { initVariabilityComparison } from './variability-comparison.js';
import { initSupportAnalysis, loadSupportData } from './support-analysis.js';
import { initSlackExportButtons } from './slack-export.js';
import { initCatalogs } from './catalogs.js';
import { initImportCatalogs } from './import_catalogs.js';
import { initTutorial } from './tutorial.js';


// ============================================
// WIRING EVENT HANDLERS
// ============================================
document.getElementById("load").onclick = loadDataArrow;

// ============================================
// SINCRONIZZAZIONE PERIODO TRA ANALISI IN FASE E SUPPORTO
// ============================================
// Quando l'utente cambia il periodo nel campo chosenP,
// aggiorna automaticamente il display info-period nel tab Supporto
const chosenPInput = document.getElementById("chosenP");
if (chosenPInput) {
  chosenPInput.addEventListener('change', () => {
    const period = parseFloat(chosenPInput.value);
    const infoPeriodEl = document.getElementById("info-period");

    if (infoPeriodEl && isFinite(period) && period > 0) {
      const pDec = parseInt(document.getElementById("periodDecimals")?.value) || 6;
      const pStr = period.toFixed(pDec);
      infoPeriodEl.textContent = `${pStr} d`;
      console.log(`📊 Periodo aggiornato: ${pStr} d`);
    }
  });
}

// ============================================
// AUTO-LOAD PER PROJECT_ID PRECARICATO
// ============================================
// Attesa che il DOM sia completamente caricato
document.addEventListener('DOMContentLoaded', () => {
  initNFreqController();
  const projectIdInput = document.getElementById("projectId");
  if (projectIdInput && projectIdInput.value) {
    // Delay per assicurare che tutti i moduli siano inizializzati
    setTimeout(async () => {
      console.log('🔄 Auto-caricamento dati per project_id:', projectIdInput.value);
      const loadingIndicator = document.getElementById("autoLoadingIndicator");
      if (loadingIndicator) loadingIndicator.style.display = "block";

      // Nascondi il bottone "Carica dati progetto" poiché il caricamento è automatico
      const loadButton = document.getElementById("load");
      if (loadButton) {
        loadButton.style.display = "none";
      }

      // Chiama direttamente loadDataArrow (il gestore è già stato associato sopra)
      if (loadButton && loadButton.onclick) {
        loadButton.click();
      } else {
        console.warn('❌ Bottone load non trovato o gestore non associato');
        const errorDiv = document.getElementById("autoLoadError");
        if (errorDiv) {
          errorDiv.innerHTML = '❌ Errore: bottone caricamento non trovato';
          errorDiv.style.display = "block";
        }
        if (loadingIndicator) loadingIndicator.style.display = "none";
      }

      // Carica periodo dal progetto se disponibile
      const projectPeriodInput = document.getElementById("projectPeriod");
      if (projectPeriodInput && projectPeriodInput.value) {
        const periodValue = parseFloat(projectPeriodInput.value);
        if (isFinite(periodValue) && periodValue > 0) {
          const chosenPInput = document.getElementById("chosenP");
          if (chosenPInput) {
            chosenPInput.value = parseFloat(periodValue.toFixed(6)).toString();
            console.log(`📊 Periodo caricato dal progetto: ${parseFloat(periodValue.toFixed(6)).toString()} giorni`);
          }
        }
      }

      // Carica dati analisi di supporto
      try {
        await loadSupportData(parseInt(projectIdInput.value));
        console.log('✅ Dati analisi di supporto caricati');
      } catch (error) {
        console.warn('⚠️ Errore caricamento dati supporto:', error);
      }

      // Inizializza bottoni export Slack
      initSlackExportButtons();
      console.log('✅ Bottoni Slack export inizializzati');
    }, 100); // Piccolo delay per assicurare inizializzazione moduli
  } else {
    // Anche se no project_id, inizializza i bottoni Slack
    initSlackExportButtons();

    // AUTO-LOAD per modalità preview pipeline (ZTF / TESS / VAST)
    const previewModeEl = document.getElementById("previewMode");
    if (previewModeEl && previewModeEl.value === "true") {
      setTimeout(async () => {
        console.log('🔭 Auto-caricamento preview pipeline');
        const loadingIndicator = document.getElementById("autoLoadingIndicator");
        if (loadingIndicator) loadingIndicator.style.display = "block";
        const loadButton = document.getElementById("load");
        if (loadButton) loadButton.style.display = "none";
        await loadDataArrow();
        if (loadingIndicator) loadingIndicator.style.display = "none";
      }, 100);
    }
  }

  // Abilita/disabilita select armoniche al toggle Fourier
  document.getElementById("enableAdvancedPrewhiten")?.addEventListener("change", (e) => {
    const sel = document.getElementById("nHarmonics");
    if (sel) sel.disabled = !e.target.checked;
  });

  // Auto-avvio tutorial se URL contiene ?tutorial=1 (dal link admin)
  if (new URLSearchParams(window.location.search).get('tutorial') === '1') {
    setTimeout(() => window.startTutorial(), 400);
  }
});

// ✅ Ricalcola ampiezza manuale con sigma clipping
// Usa event delegation perché il bottone è aggiunto dinamicamente
document.getElementById("phaseStats").addEventListener('click', (e) => {
  if (e.target.id === 'recalcSliderRanges' || e.target.closest('#recalcSliderRanges')) {
    const btn = document.getElementById("recalcSliderRanges");
    if (!btn) return;

    // Ricalcola ampiezza manuale e range slider
    const updated = recalculateAllSliderRanges();

    if (updated > 0) {
      // Feedback visivo
      btn.classList.add('success');
      btn.innerHTML = `✓ Ampiezza aggiornata`;

      setTimeout(() => {
        btn.classList.remove('success');
        btn.innerHTML = '⟲ Ricalcola';
      }, 2000);

      HistoryTracker.record('recalc_manual_amplitude', {
        sessions_updated: updated
      });
    } else {
      // Errore
      btn.innerHTML = `⚠ Errore`;
      setTimeout(() => {
        btn.innerHTML = '⟲ Ricalcola';
      }, 2000);
    }
  }
});

// removeSelected handler è alla fine del file (versione combinata sigma+manuale)
document.getElementById("restoreAll").onclick = async () => {
  // Pulisci anche sigma clipping
  state.sigmaClipSuggested.clear();
  state.selectedRaw.clear();
  const resultsDiv = document.getElementById("sigmaClipResults");
  const infoDiv = document.getElementById("sigmaClipInfo");
  if (resultsDiv) resultsDiv.style.display = 'none';
  if (infoDiv) infoDiv.innerHTML = '';

  invalidateSamplingCache();
  rebuildDefaults();
  renderSessionList();
  drawLightcurve();
  updateCounters();

  // Ricalcola estremi
  try {
    await computeExtremaPerSession();
    renderSessionList();
    console.log('✅ Estremi ricalcolati dopo restore');
  } catch (error) {
    console.warn('⚠️ Errore ricalcolo estremi:', error);
  }

  HistoryTracker.record('restore_all', {
    points_restored: state.n
  });
};
document.getElementById("computeP").onclick = async () => {
  const enablePrewhitening = document.getElementById("enablePrewhitening")?.checked || false;
  const peaks = await computePeriodogram(goToPhaseTabAndUpdate);

  // ✅ Modalità classica singolo periodo: renderizza peaks nel #peaks div
  const enablePerSession = document.getElementById("enablePerSession")?.checked ?? true;
  if (!enablePrewhitening && !enablePerSession && peaks && peaks.length > 0) {
    renderPeriodPeaks(peaks, goToPhaseTabAndUpdate);
  }
  // Altrimenti renderMultiPeriodTable o i peaks per-sessione sono già stati gestiti dentro computePeriodogram

  if (peaks && peaks.length > 0) {
    HistoryTracker.record('compute_period', {
      min_period: parseFloat(document.getElementById('minP')?.value || 0.02),
      max_period: parseFloat(document.getElementById('maxP')?.value || 10),
      n_freq: parseInt(document.getElementById('nFreq')?.value || 6000),
      best_period: peaks[0]?.period?.toFixed(6),
      n_peaks: peaks.length
    });
  }
};

// VISTA COMPATTA
document.getElementById("compactView")?.addEventListener("change", () => {
  // Reset barre (cambio scala X/Y)
  state.verticalBars.bar1 = null;
  state.verticalBars.bar2 = null;
  state.horizontalBars.bar1 = null;
  state.horizontalBars.bar2 = null;
  drawLightcurve();
});

// SESSION NAVIGATOR
{
  let _navIndex = -1;

  // Tutte le sessioni (attive e non), ordinate per sid
  const getAllSids = () =>
    Array.from(state.activeSession.keys()).sort((a, b) => a - b);

  const updateNavLabel = (sid) => {
    const sids = getAllSids();
    const idx = sids.indexOf(sid);
    const isActive = state.activeSession.get(sid);
    const name = state.sessionName?.get(sid) || state.sessionNameFromDB?.get(sid) || `S${sid}`;
    const nameEl = document.getElementById('sessionNavName');
    const label = document.getElementById('sessionNavLabel');
    const btn = document.getElementById('navToggleSession');
    if (nameEl) nameEl.textContent = name;
    if (label) {
      const prefix = isActive ? '' : '[OFF] ';
      label.textContent = `${prefix}(${idx + 1}/${sids.length})`;
    }
    if (btn) {
      btn.textContent = isActive ? '✓ ON' : '✗ OFF';
      btn.style.background = isActive ? '#e0e7ff' : '#fee2e2';
      btn.style.color = isActive ? '#3b82f6' : '#dc2626';
    }
  };

  // Espone callback per pulsante zoom su card sessione
  // sigma opzionale: se passato, sincronizza i controlli navigator
  window._sessionNavSetActive = (sid, sigma) => {
    const sids = getAllSids();
    _navIndex = sids.indexOf(sid);
    updateNavLabel(sid);
    if (sigma !== undefined) {
      _sessionSigma.set(sid, sigma);
      const slider = document.getElementById('navSigmaSlider');
      const input = document.getElementById('navSigmaInput');
      if (slider) slider.value = Math.min(10, Math.max(1, sigma));
      if (input) input.value = sigma;
    }
  };

  // Sigma per sessione: ogni sessione ricorda il suo valore (default 5)
  const _sessionSigma = new Map();

  // Espone stato navigazione per salvataggio file
  window._navState = {
    getIndex: () => _navIndex,
    getSigmaMap: () => Object.fromEntries(_sessionSigma),
    setIndex: (i) => { _navIndex = i; },
    setSigmaMap: (obj) => { for (const [k, v] of Object.entries(obj)) _sessionSigma.set(Number(k), v); }
  };

  const getSessionSigma = (sid) => _sessionSigma.get(sid) ?? 5;

  const setSessionSigma = (sid, val) => {
    _sessionSigma.set(sid, val);
    // Sincronizza controlli navigator
    const slider = document.getElementById('navSigmaSlider');
    const input = document.getElementById('navSigmaInput');
    const clamped = Math.min(10, Math.max(1, val));
    if (slider) slider.value = clamped;
    if (input) input.value = val;
    // Sincronizza input nella card sessione
    const cardInput = document.getElementById(`sigmaZoom${sid}`);
    if (cardInput) cardInput.value = val;
  };

  const getNavSigma = () => {
    if (document.getElementById('navShowAll')?.checked) return Infinity;
    return parseFloat(document.getElementById('navSigmaInput')?.value || 5);
  };

  const reapplyNavZoom = async () => {
    if (_navIndex < 0) return;
    const sids = getAllSids();
    const sid = sids[_navIndex];
    if (sid === undefined) return;
    const sigma = getNavSigma();
    _sessionSigma.set(sid, sigma);
    // Sincronizza card sessione
    const cardInput = document.getElementById(`sigmaZoom${sid}`);
    if (cardInput) cardInput.value = sigma === Infinity ? cardInput.value : sigma;
    await zoomToSession(sid, sigma);
  };

  // Slider: sincronizza input e riapplica zoom (senza navigare)
  document.getElementById('navSigmaSlider')?.addEventListener('input', (e) => {
    const input = document.getElementById('navSigmaInput');
    if (input) input.value = e.target.value;
    reapplyNavZoom();
  });

  // Input numerico: sincronizza slider (clampato) e riapplica zoom (senza navigare)
  document.getElementById('navSigmaInput')?.addEventListener('input', (e) => {
    const val = parseFloat(e.target.value);
    if (!isNaN(val)) {
      const slider = document.getElementById('navSigmaSlider');
      if (slider) slider.value = Math.min(10, Math.max(1, val));
      reapplyNavZoom();
    }
  });

  // Checkbox "tutti": disabilita/abilita controlli sigma e riapplica zoom
  document.getElementById('navShowAll')?.addEventListener('change', (e) => {
    const slider = document.getElementById('navSigmaSlider');
    const input = document.getElementById('navSigmaInput');
    if (slider) slider.disabled = e.target.checked;
    if (input) input.disabled = e.target.checked;
    reapplyNavZoom();
  });

  document.getElementById('btnPrevSession')?.addEventListener('click', async () => {
    const sids = getAllSids();
    if (!sids.length) return;
    _navIndex = _navIndex <= 0 ? sids.length - 1 : _navIndex - 1;
    const sid = sids[_navIndex];
    setSessionSigma(sid, getSessionSigma(sid));
    await zoomToSession(sid, getNavSigma());
    updateNavLabel(sid);
  });

  document.getElementById('btnNextSession')?.addEventListener('click', async () => {
    const sids = getAllSids();
    if (!sids.length) return;
    _navIndex = _navIndex >= sids.length - 1 ? 0 : _navIndex + 1;
    const sid = sids[_navIndex];
    setSessionSigma(sid, getSessionSigma(sid));
    await zoomToSession(sid, getNavSigma());
    updateNavLabel(sid);
  });

  // Toggle attiva/disattiva sessione corrente dal navigator
  document.getElementById('navToggleSession')?.addEventListener('click', async () => {
    if (_navIndex < 0) return;
    const sids = getAllSids();
    const sid = sids[_navIndex];
    if (sid === undefined) return;
    const isActive = state.activeSession.get(sid);
    const newState = !isActive;
    // Delega alla checkbox della card: ha tutta la logica (invalidateEpoch, updatePhase, ecc.)
    const cardCb = document.getElementById(`cb${sid}`);
    if (cardCb) {
      cardCb.checked = newState;
      cardCb.dispatchEvent(new Event('change'));
    } else {
      // Fallback se card non è nel DOM
      state.activeSession.set(sid, newState);
      invalidateSamplingCache();
      computeDetrendCoefficients();
      drawLightcurve();
      updateCounters();
    }
    // Se disattivata, avanza automaticamente alla sessione successiva
    if (!newState) {
      _navIndex = _navIndex >= sids.length - 1 ? 0 : _navIndex + 1;
      const nextSid = sids[_navIndex];
      setSessionSigma(nextSid, getSessionSigma(nextSid));
      await zoomToSession(nextSid, getNavSigma());
      updateNavLabel(nextSid);
    } else {
      updateNavLabel(sid);
    }
  });

  document.getElementById('btnResetSessionZoom')?.addEventListener('click', async () => {
    if (_navIndex < 0) return;
    const sids = getAllSids();
    const sid = sids[_navIndex];
    if (sid === undefined) return;
    setSessionSigma(sid, 5);
    await zoomToSession(sid, 5);
  });

  document.getElementById('btnResetZoom')?.addEventListener('click', () => {
    _navIndex = -1;
    const label = document.getElementById('sessionNavLabel');
    if (label) label.textContent = '— Sfoglia sessioni —';
    const navCb = document.getElementById('navSessionActive');
    if (navCb) navCb.checked = false;
    resetSessionZoom();
  });
}

// BARRE VERTICALI DI MISURA ΔT
document.getElementById('btn-toggle-vbars')?.addEventListener('click', () => {
  state.verticalBars.enabled = !state.verticalBars.enabled;
  const btn = document.getElementById('btn-toggle-vbars');
  const dtEl = document.getElementById('lc-delta-t');
  if (state.verticalBars.enabled) {
    btn.style.background = '#dbeafe';
    btn.style.color = '#1d4ed8';
    btn.style.borderColor = '#3b82f6';
    if (dtEl) dtEl.style.display = '';
  } else {
    btn.style.background = '#e2e8f0';
    btn.style.color = '#334155';
    btn.style.borderColor = '#cbd5e1';
    state.verticalBars.bar1 = null;
    state.verticalBars.bar2 = null;
    if (dtEl) { dtEl.style.display = 'none'; dtEl.textContent = ''; }
  }
  drawLightcurve(getCurrentLCRange());
  if (state.verticalBars.enabled) updateDeltaTDisplay();
});

// BARRE ORIZZONTALI DI MISURA ΔMag
document.getElementById('btn-toggle-hbars')?.addEventListener('click', () => {
  state.horizontalBars.enabled = !state.horizontalBars.enabled;
  const btn = document.getElementById('btn-toggle-hbars');
  const dmEl = document.getElementById('lc-delta-mag');
  if (state.horizontalBars.enabled) {
    btn.style.background = '#d1fae5';
    btn.style.color = '#065f46';
    btn.style.borderColor = '#10b981';
    if (dmEl) dmEl.style.display = '';
  } else {
    btn.style.background = '#e2e8f0';
    btn.style.color = '#334155';
    btn.style.borderColor = '#cbd5e1';
    state.horizontalBars.bar1 = null;
    state.horizontalBars.bar2 = null;
    if (dmEl) { dmEl.style.display = 'none'; dmEl.textContent = ''; }
  }
  drawLightcurve(getCurrentLCRange());
  if (state.horizontalBars.enabled) updateDeltaMagDisplay();
});

// Toggle legenda semplice (senza conteggio punti)
document.getElementById('btn-simple-legend')?.addEventListener('click', () => {
  state.simpleLegend = !state.simpleLegend;
  const btn = document.getElementById('btn-simple-legend');
  if (state.simpleLegend) {
    btn.style.background = '#dbeafe';
    btn.style.color = '#1d4ed8';
    btn.style.borderColor = '#3b82f6';
  } else {
    btn.style.background = '#e2e8f0';
    btn.style.color = '#334155';
    btn.style.borderColor = '#cbd5e1';
  }
  drawLightcurve(getCurrentLCRange());
});

// Export scientifico
document.getElementById("exportDetrended").onclick = () => {
  exportDetrendedCSV();
  document.getElementById("exportMsg").textContent = "CSV Detrended esportato ✅";
  setTimeout(() => document.getElementById("exportMsg").textContent = "", 3000);
};

document.getElementById("exportFolded").onclick = () => {
  exportFoldedCSV();
  document.getElementById("exportMsg").textContent = "CSV Folded esportato ✅";
  setTimeout(() => document.getElementById("exportMsg").textContent = "", 3000);
};

document.getElementById("exportPhasePNG").onclick = async () => {
  await exportPhasePNG();
  document.getElementById("exportMsg").textContent = "PNG esportato ✅";
  setTimeout(() => document.getElementById("exportMsg").textContent = "", 3000);
};

//allienamento sessioni in fase (removed from UI)
const alignSessionsBtn = document.getElementById("alignSessions");
if (alignSessionsBtn) {
  alignSessionsBtn.onclick = () => {
    const P = parseFloat(document.getElementById("chosenP").value);
    if (!isFinite(P) || P <= 0) {
      alert("Imposta prima un periodo valido");
      return;
    }

    alignSessionsByPhaseMedian(P);
    drawLightcurve();
    updateCounters();

    HistoryTracker.record('align_sessions', {
      period: P,
      method: 'phase_median',
      sessions: state.activeSession.size
    });

    console.log("Auto offset:", Object.fromEntries(state.sessionAutoOffset));
  };
}

// Allineamento ZERO-POINT: porta la mediana di ogni sessione a 0
document.getElementById("alignSessionsZP").onclick = () => {
  applyAlignToMag(0);
  HistoryTracker.record('align_sessions', {
    method: 'zero_point',
    sessions: state.activeSession.size
  });
};

// ============================================
// MODALE: Allinea a Riferimento
// ============================================

/** Calcola la mediana delle magnitudini correnti (dopo detrend + offset) di una sessione */
function sessionCurrentMedian(sid) {
  const mags = [];
  for (let i = 0; i < state.n; i++) {
    if (state.session[i] === sid && state.activePoint[i]) {
      const auto = state.sessionAutoOffset.get(sid) || 0;
      const manual = state.sessionManualOffset.get(sid) || 0;
      mags.push(state.mag[i] + auto + manual);
    }
  }
  if (mags.length === 0) return null;
  mags.sort((a, b) => a - b);
  return mags[Math.floor(mags.length / 2)];
}

/** Allinea tutte le sessioni attive alla magnitudine targetMag spostando sessionManualOffset */
function applyAlignToMag(targetMag) {
  for (const [sid, active] of state.activeSession) {
    if (!active) continue;
    const mags = [];
    for (let i = 0; i < state.n; i++) {
      if (state.session[i] === sid && state.activePoint[i]) {
        mags.push(state.mag[i]);
      }
    }
    if (mags.length === 0) continue;
    mags.sort((a, b) => a - b);
    const median = mags[Math.floor(mags.length / 2)];
    const shift = targetMag - median;
    const currentManual = state.sessionManualOffset.get(sid) || 0;
    state.sessionManualOffset.set(sid, currentManual + shift);
  }
  renderSessionList();
  drawLightcurve();
  updateCounters();
}

(function initAlignRefModal() {
  const modal = document.getElementById("alignRefModal");
  const openBtn = document.getElementById("alignToRefBtn");
  const cancelBtn = document.getElementById("alignRefCancel");
  const confirmBtn = document.getElementById("alignRefConfirm");
  const sessionPanel = document.getElementById("alignRefSessionPanel");
  const magPanel = document.getElementById("alignRefMagPanel");
  const sessionSelect = document.getElementById("alignRefSessionSelect");
  const magInput = document.getElementById("alignRefMagInput");
  const radios = () => document.querySelectorAll('input[name="alignRefMode"]');

  if (!modal || !openBtn) return;

  // Aggiorna stile radio buttons al cambio selezione
  function syncRadioStyles() {
    radios().forEach(r => {
      const label = r.closest('label');
      if (r.checked) {
        label.style.borderColor = '#3b82f6';
        label.style.background = '#eff6ff';
      } else {
        label.style.borderColor = '#d1d5db';
        label.style.background = '#fff';
      }
    });
    const mode = document.querySelector('input[name="alignRefMode"]:checked')?.value;
    sessionPanel.style.display = mode === 'session' ? 'block' : 'none';
    magPanel.style.display = mode === 'mag' ? 'block' : 'none';
  }

  radios().forEach(r => r.addEventListener('change', syncRadioStyles));

  // Apri modale: popola dropdown sessioni attive
  openBtn.addEventListener('click', () => {
    sessionSelect.innerHTML = '';
    for (const [sid, active] of state.activeSession) {
      if (!active) continue;
      const name = nameForSession(sid);
      const opt = document.createElement('option');
      opt.value = sid;
      opt.textContent = name;
      sessionSelect.appendChild(opt);
    }
    magInput.value = '';
    // Reset radio a "session"
    document.querySelector('input[name="alignRefMode"][value="session"]').checked = true;
    syncRadioStyles();
    modal.style.display = 'flex';
  });

  // Chiudi modale
  cancelBtn.addEventListener('click', () => { modal.style.display = 'none'; });
  modal.addEventListener('click', e => { if (e.target === modal) modal.style.display = 'none'; });

  // Conferma allineamento
  confirmBtn.addEventListener('click', () => {
    const mode = document.querySelector('input[name="alignRefMode"]:checked')?.value;

    if (mode === 'session') {
      const refSid = parseInt(sessionSelect.value);
      if (isNaN(refSid)) { alert("Seleziona una sessione di riferimento"); return; }
      const refMedian = sessionCurrentMedian(refSid);
      if (refMedian === null) { alert("La sessione selezionata non ha dati"); return; }
      // Allinea a magnitudine mediana corrente della sessione di riferimento
      // ma usa le magnitudini raw (senza offset già applicati) per il calcolo shift
      for (const [sid, active] of state.activeSession) {
        if (!active || sid === refSid) continue;
        const mags = [];
        for (let i = 0; i < state.n; i++) {
          if (state.session[i] === sid && state.activePoint[i]) {
            mags.push(state.mag[i]);
          }
        }
        if (mags.length === 0) continue;
        mags.sort((a, b) => a - b);
        const median = mags[Math.floor(mags.length / 2)];
        // Target: la mediana raw della sessione di riferimento + i suoi offset
        const refAuto = state.sessionAutoOffset.get(refSid) || 0;
        const refManual = state.sessionManualOffset.get(refSid) || 0;
        const refRawMags = [];
        for (let i = 0; i < state.n; i++) {
          if (state.session[i] === refSid && state.activePoint[i]) {
            refRawMags.push(state.mag[i]);
          }
        }
        if (refRawMags.length === 0) continue;
        refRawMags.sort((a, b) => a - b);
        const refRawMedian = refRawMags[Math.floor(refRawMags.length / 2)];
        const targetMag = refRawMedian + refAuto + refManual;
        const shift = targetMag - median;
        const currentManual = state.sessionManualOffset.get(sid) || 0;
        state.sessionManualOffset.set(sid, currentManual + shift);
      }
      renderSessionList();
      drawLightcurve();
      updateCounters();
      modal.style.display = 'none';

    } else {
      const targetMag = parseFloat(magInput.value);
      if (!isFinite(targetMag)) { alert("Inserisci una magnitudine valida"); return; }
      applyAlignToMag(targetMag);
      modal.style.display = 'none';
    }
  });
})();



// ============================================
// SALVATAGGIO STATO SU DATABASE (MariaDB)
// ============================================
document.getElementById("saveState").onclick = async () => {
  const payload = {
    n: state.n,
    active_bitset_b64: packActiveBitsetToBase64(state.activePoint),
    session_active: Object.fromEntries(state.activeSession),

    // ✅ CORREZIONE: usa i nomi corretti delle mappe
    session_auto_offset: Object.fromEntries(state.sessionAutoOffset),
    session_manual_offset: Object.fromEntries(state.sessionManualOffset),

    session_name: Object.fromEntries(state.sessionName),
    session_color: Object.fromEntries(state.sessionColor),
    detrend: { model: state.detrend.model },
    period: state.lastPeriod,
    phase_shift: state.phaseShift,
    phase_title: state.phaseTitle,
    phase_range: state.phaseRange,
    phase_period_label: state.phasePeriodLabel,
    period_decimals: parseInt(document.getElementById("periodDecimals")?.value) || 6,
    epoch_decimals: parseInt(document.getElementById("epochDecimals")?.value) || 5,

    // ✅ NUOVO: Aggiungi cronologia operazioni (come oggetto, non stringa)
    history: {
      export_date: new Date().toISOString(),
      history: HistoryTracker.history,
      version: '1.0'
    }
  };
  try {
    const r = await fetch("/agata/variable-stars/api/state/save", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify(payload)
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    document.getElementById("stateMsg").textContent = (await r.json()).ok ? "Salvato ✅" : "Errore ❌";
  } catch (err) {
    console.error("Errore salvataggio stato:", err);
    document.getElementById("stateMsg").textContent = "Errore ❌";
  }
};

// ============================================
// CARICAMENTO STATO DA DATABASE (MariaDB)
// ============================================
document.getElementById("loadState").onclick = async () => {
  const r = await fetch("/agata/variable-stars/api/state/load");
  if (!r.ok) {
    document.getElementById("stateMsg").textContent = "Errore caricamento ❌";
    return;
  }
  const data = await r.json();
  if (!data.ok || !data.state) {
    document.getElementById("stateMsg").textContent = "Nessuno stato salvato";
    return;
  }
  const s = data.state;
  if (s.n !== state.n) {
    document.getElementById("stateMsg").textContent = "⚠️ Dati incompatibili";
    return;
  }
  
  // Ripristina stato
  state.activePoint = unpackActiveBitsetFromBase64(s.active_bitset_b64, s.n);
  state.activeSession = new Map(Object.entries(s.session_active).map(([k,v])=>[Number(k),v]));
  
  // ✅ CORREZIONE: ripristina entrambe le mappe offset
  state.sessionAutoOffset = new Map(
    Object.entries(s.session_auto_offset || {}).map(([k,v])=>[Number(k),v])
  );
  state.sessionManualOffset = new Map(
    Object.entries(s.session_manual_offset || {}).map(([k,v])=>[Number(k),v])
  );
  
  // Ripristina nomi e colori personalizzati
  if (s.session_name) {
    state.sessionName = new Map(Object.entries(s.session_name).map(([k,v])=>[Number(k),v]));
  }
  if (s.session_color) {
    state.sessionColor = new Map(Object.entries(s.session_color).map(([k,v])=>[Number(k),v]));
  }
  
  state.detrend.model = s.detrend?.model || "linear";
  const detrendModelEl = document.getElementById("detrendModel");
  if (detrendModelEl) detrendModelEl.value = state.detrend.model;

  if (s.period) {
    state.lastPeriod = s.period;
    const chosenPEl = document.getElementById("chosenP");
    if (chosenPEl) chosenPEl.value = s.period;
  }
  if (s.phase_shift !== undefined) {
    state.phaseShift = s.phase_shift;
    const phaseShiftEl = document.getElementById("phaseShift");
    if (phaseShiftEl) phaseShiftEl.value = s.phase_shift;
  }
  if (s.phase_title) {
    state.phaseTitle = s.phase_title;
    if (document.getElementById("phaseCustomTitle")) {
      document.getElementById("phaseCustomTitle").value = s.phase_title;
    }
  }
  if (s.phase_range) {
    state.phaseRange = s.phase_range;
    if (document.getElementById("phaseRange")) {
      document.getElementById("phaseRange").value = s.phase_range;
    }
  }
  if (s.phase_period_label !== undefined) {
    state.phasePeriodLabel = s.phase_period_label;
    if (document.getElementById("phasePeriodLabel")) {
      document.getElementById("phasePeriodLabel").value = s.phase_period_label;
    }
  }
  if (s.period_decimals) {
    const el = document.getElementById("periodDecimals");
    if (el) el.value = s.period_decimals;
  }
  if (s.epoch_decimals) {
    const el = document.getElementById("epochDecimals");
    if (el) el.value = s.epoch_decimals;
  }

  // ✅ NUOVO: Ripristina cronologia operazioni se presente
  if (s.history) {
    try {
      // s.history può essere già un oggetto o una stringa JSON (dipende dal backend)
      const historyData = typeof s.history === 'string' ? JSON.parse(s.history) : s.history;
      if (historyData && historyData.history && Array.isArray(historyData.history)) {
        HistoryTracker.history = historyData.history;
        console.log(`📝 Cronologia ripristinata: ${historyData.history.length} operazioni`);
      }
    } catch (e) {
      console.warn('⚠️ Errore ripristino cronologia:', e);
    }
  }

  computeDetrendCoefficients();
  renderSessionList();
  drawLightcurve();
  updateCounters();

  // ✅ NUOVO: Ricalcola fase se il periodo è presente
  if (s.period) {
    goToPhaseTabAndUpdate(s.period);
  }

  document.getElementById("stateMsg").textContent = "Caricato ✅";
};

// ============================================
// SALVATAGGIO SU FILE ZIP COMPRESSO
// ============================================
const saveFileBtn = document.getElementById("saveFile");
if (saveFileBtn) {
  saveFileBtn.onclick = async () => {
    try {
      // Carica JSZip se non è già presente
      if (!window.JSZip) {
        const script = document.createElement('script');
        script.src = 'https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js';
        await new Promise((resolve, reject) => {
          script.onload = resolve;
          script.onerror = reject;
          document.head.appendChild(script);
        });
      }

      const kindEl = document.getElementById("kind");
      const seedEl = document.getElementById("seed");
      const sessionsEl = document.getElementById("sessions");
      const projectIdEl = document.getElementById("projectId");
      const gaiaIdEl = document.getElementById("gaiaId");
      const projectGaiaIdEl = document.getElementById("projectGaiaId");

      // Costruisci i dati del progetto
      const fileData = {
        version: "1.0",
        timestamp: new Date().toISOString(),
        metadata: {
          kind: kindEl?.value || "",
          seed: seedEl?.value || "",
          sessions: sessionsEl?.value || ""
        },
        data: {
          n: state.n,
          jd: Array.from(state.jd),
          mag: Array.from(state.mag),
          session: Array.from(state.session),
          point_id: Array.from(state.pid)
        },
        state: {
          active_bitset_b64: packActiveBitsetToBase64(state.activePoint),
          session_active: Object.fromEntries(state.activeSession),

          // ✅ CORREZIONE: salva entrambe le mappe offset
          session_auto_offset: Object.fromEntries(state.sessionAutoOffset),
          session_manual_offset: Object.fromEntries(state.sessionManualOffset),

          session_name: Object.fromEntries(state.sessionName),
          session_color: Object.fromEntries(state.sessionColor),
          detrend: {
            model: state.detrend.model,
            coeff: Object.fromEntries(
              Array.from(state.detrend.coeff.entries()).map(([k, v]) => [k, v])
            )
          },
          period: state.lastPeriod,
          phase_shift: state.phaseShift,
          phase_title: state.phaseTitle,
          phase_range: state.phaseRange,
          phase_period_label: state.phasePeriodLabel,
          lock_phase_zoom: state.lockPhaseZoom,
          manual_amplitude: state.manualAmplitude,
          epoch: state.epoch,

          // Vista compatta e navigazione sessione
          compact_view: document.getElementById("compactView")?.checked || false,
          nav_index: window._navState?.getIndex() ?? -1,
          nav_sigma: window._navState?.getSigmaMap() ?? {},
          nav_show_all: document.getElementById("navShowAll")?.checked || false,
          nav_sigma_global: parseFloat(document.getElementById("navSigmaInput")?.value || "5"),

          // Barre ΔT e ΔMag
          vertical_bars: {
            enabled: state.verticalBars.enabled,
            bar1: state.verticalBars.bar1,
            bar2: state.verticalBars.bar2
          },
          horizontal_bars: {
            enabled: state.horizontalBars.enabled,
            bar1: state.horizontalBars.bar1,
            bar2: state.horizontalBars.bar2
          }
        }
      };

      // ✅ NUOVO: Formato timestamp ISO con data e ora (2026-02-20T15:30:45)
      const now = new Date();
      const isoTimestamp = now.toISOString().split('.')[0]; // Rimuove millisecondi

      // Costruisci nome file: AGATA_PRJ<projectid>_<gaia_id>_<timestamp>.zip
      const projectId = projectIdEl?.value || "unknown";
      const gaiaId = gaiaIdEl?.value || projectGaiaIdEl?.value || "unknown";
      const fileName = `AGATA_PRJ${projectId}_${gaiaId}_${isoTimestamp.replace(/:/g, '-')}`;

      // ✅ NUOVO: Crea ZIP con JSZip e compressione DEFLATE
      const zip = new window.JSZip();
      zip.file(`${fileName}.json`, JSON.stringify(fileData, null, 2));

      // Genera ZIP e scarica (con compressione DEFLATE per ridurre dimensioni)
      const zipBlob = await zip.generateAsync({
        type: "blob",
        compression: 'DEFLATE',
        compressionOptions: { level: 9 }  // Massima compressione
      });
      const url = URL.createObjectURL(zipBlob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${fileName}.zip`;
      a.click();
      URL.revokeObjectURL(url);

      document.getElementById("fileMsg").textContent = "Progetto salvato ✅ (compresso)";
      setTimeout(() => { document.getElementById("fileMsg").textContent = ""; }, 3000);
    } catch (error) {
      console.error("Errore salvataggio ZIP:", error);
      document.getElementById("fileMsg").textContent = `❌ Errore: ${error.message}`;
      setTimeout(() => { document.getElementById("fileMsg").textContent = ""; }, 5000);
    }
  };
}

// ============================================
// CARICAMENTO DA FILE ZIP O JSON
// ============================================
document.getElementById("loadFileInput").onchange = async (e) => {
  const file = e.target.files[0];
  if (!file) return;

  try {
    let fileData;

    // ✅ NUOVO: Supporta sia ZIP che JSON
    if (file.name.endsWith('.zip')) {
      // Carica JSZip se non è già presente
      if (!window.JSZip) {
        const script = document.createElement('script');
        script.src = 'https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js';
        await new Promise((resolve, reject) => {
          script.onload = resolve;
          script.onerror = reject;
          document.head.appendChild(script);
        });
      }

      // Decomprime ZIP
      const zip = new window.JSZip();
      await zip.loadAsync(file);

      // Trova il primo file .json dentro lo ZIP
      let jsonFile = null;
      for (const filename in zip.files) {
        if (filename.endsWith('.json')) {
          jsonFile = zip.files[filename];
          break;
        }
      }

      if (!jsonFile) {
        throw new Error("Nessun file JSON trovato nel ZIP");
      }

      const jsonText = await jsonFile.async('text');
      fileData = JSON.parse(jsonText);
    } else if (file.name.endsWith('.json')) {
      // Caricamento diretto JSON (backward compatibility)
      const text = await file.text();
      fileData = JSON.parse(text);
    } else {
      throw new Error("File non supportato (usare .zip o .json)");
    }

    if (!fileData.version) {
      throw new Error("Formato file non valido");
    }
    
    // Carica i dati raw
    state.n = fileData.data.n;
    state.jd = new Float64Array(fileData.data.jd);
    state.mag = new Float32Array(fileData.data.mag);
    state.session = new Int32Array(fileData.data.session);
    state.pid = new Int32Array(fileData.data.point_id);
    
    // Carica lo stato
    const s = fileData.state;
    state.activePoint = unpackActiveBitsetFromBase64(s.active_bitset_b64, state.n);
    state.activeSession = new Map(Object.entries(s.session_active).map(([k,v])=>[Number(k),v]));
    
    // ✅ CORREZIONE: carica entrambe le mappe offset
    state.sessionAutoOffset = new Map(
      Object.entries(s.session_auto_offset || {}).map(([k,v])=>[Number(k),v])
    );
    state.sessionManualOffset = new Map(
      Object.entries(s.session_manual_offset || {}).map(([k,v])=>[Number(k),v])
    );
    
    state.sessionName = new Map(Object.entries(s.session_name || {}).map(([k,v])=>[Number(k),v]));
    state.sessionColor = new Map(Object.entries(s.session_color || {}).map(([k,v])=>[Number(k),v]));
    
    // Detrend
    state.detrend.model = s.detrend.model;
    state.detrend.coeff = new Map(
      Object.entries(s.detrend.coeff || {}).map(([k, v]) => [Number(k), v])
    );
    const detrendModelEl2 = document.getElementById("detrendModel");
    if (detrendModelEl2) detrendModelEl2.value = state.detrend.model;

    // Fase
    if (s.period) {
      state.lastPeriod = s.period;
      const chosenPEl2 = document.getElementById("chosenP");
      if (chosenPEl2) chosenPEl2.value = s.period;
    }
    if (s.phase_shift !== undefined) {
      state.phaseShift = s.phase_shift;
      const phaseShiftEl2 = document.getElementById("phaseShift");
      if (phaseShiftEl2) phaseShiftEl2.value = s.phase_shift;
    }
    if (s.phase_title) {
      state.phaseTitle = s.phase_title;
      const phaseCustomTitleEl = document.getElementById("phaseCustomTitle");
      if (phaseCustomTitleEl) phaseCustomTitleEl.value = s.phase_title;
    }
    if (s.phase_range) {
      state.phaseRange = s.phase_range;
      const phaseRangeEl = document.getElementById("phaseRange");
      if (phaseRangeEl) phaseRangeEl.value = s.phase_range;
    }
    if (s.phase_period_label !== undefined) {
      state.phasePeriodLabel = s.phase_period_label;
      const phasePeriodLabelEl = document.getElementById("phasePeriodLabel");
      if (phasePeriodLabelEl) phasePeriodLabelEl.value = s.phase_period_label;
    }
    if (s.period_decimals) {
      const el = document.getElementById("periodDecimals");
      if (el) el.value = s.period_decimals;
    }
    if (s.epoch_decimals) {
      const el = document.getElementById("epochDecimals");
      if (el) el.value = s.epoch_decimals;
    }

    // Ripristina lock zoom e manualAmplitude
    if (s.lock_phase_zoom !== undefined) {
      state.lockPhaseZoom = s.lock_phase_zoom;
      const lockZoomEl = document.getElementById("lockPhaseZoom");
      if (lockZoomEl) lockZoomEl.checked = s.lock_phase_zoom;
    }
    if (s.manual_amplitude) {
      state.manualAmplitude = s.manual_amplitude;
    }
    if (s.epoch !== undefined) {
      state.epoch = s.epoch;
    }

    // Aggiorna i campi di configurazione se presenti
    if (fileData.metadata) {
      const kindEl = document.getElementById("kind");
      const seedEl = document.getElementById("seed");
      const sessionsEl = document.getElementById("sessions");

      if (kindEl) kindEl.value = fileData.metadata.kind;
      if (seedEl) seedEl.value = fileData.metadata.seed;
      if (sessionsEl) sessionsEl.value = fileData.metadata.sessions;
    }
    
    // Ripristina vista compatta
    const compactEl = document.getElementById("compactView");
    if (compactEl && s.compact_view !== undefined) compactEl.checked = s.compact_view;

    // Ripristina navigazione sessione
    if (s.nav_show_all !== undefined) {
      const showAllEl = document.getElementById("navShowAll");
      if (showAllEl) {
        showAllEl.checked = s.nav_show_all;
        const slider = document.getElementById('navSigmaSlider');
        const input = document.getElementById('navSigmaInput');
        if (slider) slider.disabled = s.nav_show_all;
        if (input) input.disabled = s.nav_show_all;
      }
    }
    if (s.nav_sigma_global !== undefined) {
      const sigmaSlider = document.getElementById("navSigmaSlider");
      const sigmaInput = document.getElementById("navSigmaInput");
      if (sigmaSlider) sigmaSlider.value = Math.min(10, Math.max(1, s.nav_sigma_global));
      if (sigmaInput) sigmaInput.value = s.nav_sigma_global;
    }
    if (s.nav_sigma && window._navState) window._navState.setSigmaMap(s.nav_sigma);
    if (s.nav_index !== undefined && s.nav_index >= 0 && window._navState) {
      window._navState.setIndex(s.nav_index);
      const sids = Array.from(state.activeSession.keys()).sort((a, b) => a - b);
      const sid = sids[s.nav_index];
      if (sid !== undefined) window._sessionNavSetActive?.(sid);
    }

    // Ripristina barre ΔT (verticali)
    if (s.vertical_bars) {
      state.verticalBars.enabled = s.vertical_bars.enabled || false;
      state.verticalBars.bar1 = s.vertical_bars.bar1 ?? null;
      state.verticalBars.bar2 = s.vertical_bars.bar2 ?? null;
    } else {
      state.verticalBars.enabled = false;
      state.verticalBars.bar1 = null;
      state.verticalBars.bar2 = null;
    }
    // Pulsante barre verticali
    const vbBtn = document.getElementById('btn-toggle-vbars');
    if (vbBtn) {
      const on = state.verticalBars.enabled;
      vbBtn.style.background = on ? '#dbeafe' : '#e2e8f0';
      vbBtn.style.color = on ? '#1d4ed8' : '#334155';
      vbBtn.style.borderColor = on ? '#93c5fd' : '#cbd5e1';
    }

    // Ripristina barre ΔMag (orizzontali)
    if (s.horizontal_bars) {
      state.horizontalBars.enabled = s.horizontal_bars.enabled || false;
      state.horizontalBars.bar1 = s.horizontal_bars.bar1 ?? null;
      state.horizontalBars.bar2 = s.horizontal_bars.bar2 ?? null;
    } else {
      state.horizontalBars.enabled = false;
      state.horizontalBars.bar1 = null;
      state.horizontalBars.bar2 = null;
    }
    const hbBtn = document.getElementById('btn-toggle-hbars');
    if (hbBtn) {
      const on = state.horizontalBars.enabled;
      hbBtn.style.background = on ? '#dbeafe' : '#e2e8f0';
      hbBtn.style.color = on ? '#1d4ed8' : '#334155';
      hbBtn.style.borderColor = on ? '#93c5fd' : '#cbd5e1';
    }

    // Ridisegna tutto
    renderSessionList();
    drawLightcurve();
    updateCounters();

    // Aggiorna display ΔT e ΔMag (dopo drawLightcurve che ha rigenerato il plot)
    const dtEl = document.getElementById('lc-delta-t');
    if (dtEl) {
      dtEl.textContent = '';
      dtEl.style.display = state.verticalBars.enabled ? 'inline' : 'none';
    }
    if (state.verticalBars.enabled) updateDeltaTDisplay();

    const dmEl = document.getElementById('lc-delta-mag');
    if (dmEl) {
      dmEl.textContent = '';
      dmEl.style.display = state.horizontalBars.enabled ? 'inline' : 'none';
    }
    if (state.horizontalBars.enabled) updateDeltaMagDisplay();

    // Autoscale curva di luce (massimizza al caricamento)
    setTimeout(() => {
      Plotly.relayout("plotLC", {
        'yaxis.autorange': 'reversed',
        'xaxis.autorange': true
      });
    }, 100);

    // Se è presente un periodo, aggiorna la fase e l'Analisi di Supporto
    if (s.period) {
      // ✅ Sincronizza info-period (campo read-only in tab Analisi di Supporto)
      const infoPeriodEl = document.getElementById("info-period");
      if (infoPeriodEl) {
        infoPeriodEl.textContent = `${s.period.toFixed(6)} d`;
      }

      goToPhaseTabAndUpdate(s.period);

      // Assicura che il campo periodo in Analisi di Supporto venga aggiornato
      setTimeout(() => {
        if (typeof window.updateSupportPeriod === 'function') {
          window.updateSupportPeriod(s.period);
        }
      }, 100);
    }

    document.getElementById("fileMsg").textContent = `Caricato: ${file.name} ✅`;
    setTimeout(() => { document.getElementById("fileMsg").textContent = ""; }, 5000);
    
  } catch (error) {
    document.getElementById("fileMsg").textContent = `❌ Errore: ${error.message}`;
    console.error("Errore caricamento file:", error);
  }
  
  e.target.value = "";
};

document.getElementById("recalcDetrend").onclick = async () => {
  computeDetrendCoefficients();
  drawLightcurve();
  updateCounters();

  // Ricalcola estremi (detrend cambia le magnitudini)
  try {
    await computeExtremaPerSession();
    renderSessionList();
    console.log('✅ Estremi ricalcolati dopo detrend');
  } catch (error) {
    console.warn('⚠️ Errore ricalcolo estremi:', error);
  }

  HistoryTracker.record('detrend', {
    model: state.detrend.model,
    sessions: state.activeSession.size
  });

  // AUTOSCALE PERFETTO dopo 100ms
  setTimeout(() => {
    Plotly.relayout("plotLC", {
      'yaxis.autorange': 'reversed',
      'xaxis.autorange': true
    });
  }, 100);
};

// ============================================
// SIGMA CLIPPING - SETUP CONTROLLI
// ============================================

// Sync slider e input numerico (bidirezionale)
const sigmaValueSlider = document.getElementById("sigmaValue");
const sigmaNumberInput = document.getElementById("sigmaValueNumber");  // ✅ CORRETTO

if (sigmaValueSlider && sigmaNumberInput) {
  sigmaValueSlider.oninput = (e) => {
    const val = e.target.value;
    sigmaNumberInput.value = val;
    
    // Visual feedback sul colore dello slider
    const slider = e.target;
    const percent = ((val - 1) / 4) * 100;
    
    if (val < 2) {
      slider.style.background = `linear-gradient(to right, #ef4444 0%, #f59e0b ${percent}%, #e5e7eb ${percent}%)`;
    } else if (val < 3.5) {
      slider.style.background = `linear-gradient(to right, #f59e0b 0%, #facc15 ${percent}%, #e5e7eb ${percent}%)`;
    } else {
      slider.style.background = `linear-gradient(to right, #22c55e 0%, #10b981 ${percent}%, #e5e7eb ${percent}%)`;
    }
  };

  sigmaNumberInput.onchange = (e) => {
    const val = parseFloat(e.target.value);
    if (val >= 1 && val <= 5) {
      sigmaValueSlider.value = val;
      // Trigger visual feedback
      sigmaValueSlider.dispatchEvent(new Event('input'));
    } else {
      e.target.value = 3; // Reset a default se fuori range
    }
  };
}

// ============================================
// CONTROLLO DIMENSIONE PUNTI
// ============================================

// Sync slider e input numerico per dimensione marker (bidirezionale)
const markerSizeSlider = document.getElementById("markerSizeSlider");
const markerSizeNumber = document.getElementById("markerSizeNumber");

if (markerSizeSlider && markerSizeNumber) {
  // Quando lo slider cambia, aggiorna il numero E il grafico
  markerSizeSlider.oninput = (e) => {
    const val = parseFloat(e.target.value);
    markerSizeNumber.value = val;
    
    // Aggiorna lo stato
    state.currentMarkerSize = val;
    
    // Ridisegna i grafici
    drawLightcurve(getCurrentLCRange());
    
    // Se c'è un grafico di fase attivo, ridisegnalo
    if (state.lastPeriod) {
      updatePhaseViewFull();
    }
  };

  // Quando il numero cambia, aggiorna lo slider E il grafico
  markerSizeNumber.onchange = (e) => {
    const val = parseFloat(e.target.value);
    if (val >= 1 && val <= 15) {
      markerSizeSlider.value = val;
      state.currentMarkerSize = val;
      
      // Ridisegna i grafici
      drawLightcurve(getCurrentLCRange());
      
      // Se c'è un grafico di fase attivo, ridisegnalo
      if (state.lastPeriod) {
        updatePhaseViewFull();
      }
    } else {
      // Reset a default se fuori range
      e.target.value = 3;
      markerSizeSlider.value = 3;
      state.currentMarkerSize = 3;
    }
  };
}

// ============================================
// CALCOLA E EVIDENZIA OUTLIER (PER SESSIONE)
// ============================================

const highlightSigmaClipBtn = document.getElementById("highlightSigmaClip");
if (highlightSigmaClipBtn) {
  highlightSigmaClipBtn.onclick = async () => {
    const sigma = parseFloat(document.getElementById("sigmaValue").value);
    const infoDiv = document.getElementById("sigmaClipInfo");
    const resultsDiv = document.getElementById("sigmaClipResults");
    const button = highlightSigmaClipBtn;
    
    // FEEDBACK IMMEDIATO
    button.disabled = true;
    button.style.opacity = "0.6";
    button.innerHTML = '⏳ Calcolo in corso...';
    infoDiv.innerHTML = '<span style="color: #3b82f6;">🔄 Analizzando sessioni...</span>';
    resultsDiv.style.display = 'none';
    
    try {
      // Prepara dati attivi
      const activeData = [];
      for (let i = 0; i < state.n; i++) {
        if (state.activePoint[i] === 1 && state.activeSession.get(state.session[i])) {
          activeData.push({
            index: i,
            jd: state.jd[i],
            mag: state.mag[i],
            session_id: state.session[i]
          });
        }
      }
      
      if (activeData.length === 0) {
        throw new Error("Nessun punto attivo da analizzare");
      }
      
      // COSTRUISCI ARROW STREAM
      const jd64 = new Float64Array(activeData.map(d => d.jd));
      const mag32 = new Float32Array(activeData.map(d => d.mag));
      const sid32 = new Int32Array(activeData.map(d => d.session_id));
      
      const tbl = window.Arrow.tableFromArrays({ 
        jd: jd64, 
        mag: mag32,
        session_id: sid32
      });
      const arrowStream = window.Arrow.tableToIPC(tbl, "stream");
      
      // CHIAMATA API
      const res = await fetch(`/agata/variable-stars/api/sigma_clip.arrow?sigma=${sigma}`, {
        method: "POST",
        body: arrowStream
      });
      
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      }
      
      const result = await res.json();
      
      // AGGIORNA STATE
      state.sigmaClipSuggested.clear();
      
      // Mappa indici dalla risposta agli indici originali
      for (const apiIndex of result.outlier_indices) {
        const originalIndex = activeData[apiIndex].index;
        state.sigmaClipSuggested.add(originalIndex);
      }
      
      // MOSTRA RISULTATI DETTAGLIATI PER SESSIONE
      if (result.n_outliers_total === 0) {
        infoDiv.innerHTML = `<span style="color: #22c55e;">✅ Nessun outlier trovato con σ=${sigma}</span>`;
        resultsDiv.style.display = 'none';
      } else {
        infoDiv.innerHTML = `<span style="color: #ef4444; font-size: 13px;">⚠️ Trovati <strong>${result.n_outliers_total}</strong> outlier in <strong>${Object.keys(result.session_stats).length}</strong> sessioni</span>`;

        // Render dettagli per sessione
        let html = '<div style="max-height: 300px; overflow-y: auto;">';
        html += `<div style="font-weight: 700; margin-bottom: 8px; padding-bottom: 6px; border-bottom: 2px solid #10b981;">📊 Dettaglio per Sessione (σ=${sigma})</div>`;

        for (const [sid, stats] of Object.entries(result.session_stats)) {
          const sessionName = nameForSession(parseInt(sid));
          const sessionColor = colorForSession(parseInt(sid));

          const outlierColor = stats.n_outliers > 0 ? '#ef4444' : '#22c55e';
          const outlierIcon = stats.n_outliers > 0 ? '⚠️' : '✓';

          html += `
            <div style="padding: 8px; margin-bottom: 6px; background: ${stats.n_outliers > 0 ? '#fee2e2' : '#f0fdf4'}; border-radius: 4px; border-left: 3px solid ${outlierColor};">
              <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">
                <span style="width: 10px; height: 10px; background: ${sessionColor}; border-radius: 50%;"></span>
                <strong>${sessionName}</strong>
                <span style="margin-left: auto; color: ${outlierColor}; font-weight: 700;">${outlierIcon} ${stats.n_outliers}/${stats.n_total}</span>
              </div>

              <div style="font-size: 10px; line-height: 1.4; color: #374151;">
                <strong>Mediana:</strong> ${stats.median.toFixed(3)} mag<br>
                <strong>σ equiv:</strong> ${stats.sigma_equiv.toFixed(4)} mag<br>
                <strong>Range:</strong> [${stats.bounds[0].toFixed(3)}, ${stats.bounds[1].toFixed(3)}]<br>
                <strong>% outlier:</strong> ${stats.outlier_percentage.toFixed(1)}%
              </div>
            </div>
          `;
        }

        html += '</div>';

        resultsDiv.innerHTML = html;
        resultsDiv.style.display = 'block';
      }
      
      // RIDISEGNA GRAFICO CON EVIDENZIAZIONE
      drawLightcurve();
      updateCounters();

      HistoryTracker.record('sigma_clip', {
        sigma: sigma,
        outliers_found: result.n_outliers_total,
        sessions_analyzed: Object.keys(result.session_stats).length,
        percentage: (result.n_outliers_total / activeData.length * 100).toFixed(2)
      });
      
      // ANIMAZIONE SUCCESS
      button.style.animation = 'pulse 0.5s ease-in-out';
      setTimeout(() => {
        button.style.animation = '';
      }, 500);
      
    } catch (error) {
      console.error("Errore sigma clipping:", error);
      infoDiv.textContent = `❌ Errore: ${error.message}`;
      infoDiv.style.color = '#ef4444';
      resultsDiv.style.display = 'none';
    } finally {
      // RIPRISTINA BOTTONE
      button.disabled = false;
      button.style.opacity = "1";
      button.innerHTML = '🔍 Evidenzia Outlier';
    }
  };
}

// ============================================
// RIMOZIONE PUNTI (COMBINATA)
// ============================================

const removeSelectedBtn = document.getElementById("removeSelected");
if (removeSelectedBtn) {
  // Sovrascrivi handler esistente
  removeSelectedBtn.onclick = async () => {
    const range = getCurrentLCRange();

    // UNISCI selezione manuale + sigma clipping
    const allToRemove = new Set([...state.selectedRaw, ...state.sigmaClipSuggested]);

    if (allToRemove.size === 0) {
      const infoDiv = document.getElementById("sigmaClipInfo");
      if (infoDiv) {
        infoDiv.innerHTML = '<span style="color: #f59e0b;">⚠️ Nessun punto selezionato</span>';
        setTimeout(() => {
          infoDiv.innerHTML = '';
        }, 2500);
      }
      return;
    }

    // CONTEGGIO DETTAGLIATO
    const nManual = state.selectedRaw.size;
    const nSigma = state.sigmaClipSuggested.size;
    const nOverlap = [...state.selectedRaw].filter(i => state.sigmaClipSuggested.has(i)).length;
    const nUnique = allToRemove.size;

    // RIMUOVI TUTTI
    for (const idx of allToRemove) {
      state.activePoint[idx] = 0;
    }

    // FEEDBACK DETTAGLIATO
    const infoDiv = document.getElementById("sigmaClipInfo");
    if (infoDiv) {
      let feedbackMsg = `<span style="color: #22c55e; font-weight: 700;">✓ Rimossi ${nUnique} punti</span>`;

      if (nManual > 0 && nSigma > 0) {
        feedbackMsg += `<br><span style="font-size: 11px;">(${nSigma} σ-clip + ${nManual} manuali`;
        if (nOverlap > 0) {
          feedbackMsg += `, ${nOverlap} in comune`;
        }
        feedbackMsg += `)</span>`;
      }

      infoDiv.innerHTML = feedbackMsg;
      setTimeout(() => {
        infoDiv.innerHTML = '';
      }, 4000);
    }

    // NASCONDI RISULTATI SIGMA
    const resultsDiv = document.getElementById("sigmaClipResults");
    if (resultsDiv) {
      resultsDiv.style.display = 'none';
    }

    // PULISCI SELEZIONI
    state.selectedRaw.clear();
    state.sigmaClipSuggested.clear();

    // Salva impostazioni zoom della fase e dragmode dei grafici prima del refresh
    const savedLockPhaseZoom = state.lockPhaseZoom;
    const savedPhaseRange = state.savedPhaseRange ? { ...state.savedPhaseRange } : null;

    // Salva dragmode (zoom vs select) da entrambi i grafici
    const lcgd = document.getElementById('plotLC');
    const phgd = document.getElementById('plotPhase');
    const savedLCDragmode = lcgd?._fullLayout?.dragmode ?? 'zoom';
    const savedPhDragmode = phgd?._fullLayout?.dragmode ?? 'zoom';

    // RICALCOLA E RIDISEGNA (preserva zoom corrente)
    invalidateSamplingCache();
    computeDetrendCoefficients();
    drawLightcurve(range);

    // Ripristina impostazioni zoom della fase
    state.lockPhaseZoom = savedLockPhaseZoom;
    state.savedPhaseRange = savedPhaseRange;

    computePhase();

    // Ripristina dragmode dei grafici se non è zoom (evita render inutile)
    if (savedLCDragmode !== 'zoom') {
      Plotly.relayout('plotLC', { dragmode: savedLCDragmode });
    }
    if (savedPhDragmode !== 'zoom') {
      Plotly.relayout('plotPhase', { dragmode: savedPhDragmode });
    }
    updateCounters();

    // Ricalcola estremi (rimossi punti)
    try {
      await computeExtremaPerSession();
      renderSessionList();
      console.log('✅ Estremi ricalcolati dopo rimozione punti');
    } catch (error) {
      console.warn('⚠️ Errore ricalcolo estremi:', error);
    }

    HistoryTracker.record('remove_points', {
      count: nUnique,
      manual_selection: nManual,
      sigma_clip: nSigma,
      overlap: nOverlap
    });
  };
}

function updateHistoryUI() {
  HistoryTracker.renderToHTML('#historyPanel');
}

// Listener per auto-update
document.addEventListener('historyUpdate', () => {
  updateHistoryUI();
});

// Export button
document.getElementById('exportHistory').onclick = () => {
  const json = HistoryTracker.exportJSON();
  
  // Download come file
  const blob = new Blob([json], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `aaaat_history_${Date.now()}.json`;
  a.click();
};

// Clear button
document.getElementById('clearHistory').onclick = () => {
  if (confirm('Cancellare cronologia?')) {
    HistoryTracker.clear();
    updateHistoryUI();
  }
};

// ============================================
// INIZIALIZZAZIONE CONTROLLI FASE
// ============================================
// Inizializza tutti gli handler per i controlli fase
// (shift, template, fine-tuning periodo, delta-P, sampling)
initializePhaseControls();

// ============================================
// INIZIALIZZAZIONE AI ADVISOR
// ============================================
initAIAdvisor();

// ============================================
// INIZIALIZZAZIONE VARIABILITY COMPARISON
// ============================================
initVariabilityComparison();

// ============================================
// INIZIALIZZAZIONE CATALOGS TAB
// ============================================
initCatalogs();

// ============================================
// INIZIALIZZAZIONE IMPORT CATALOGS TAB
// ============================================
initImportCatalogs();

// ============================================
// INIZIALIZZAZIONE TUTORIAL
// ============================================
initTutorial();

// ============================================
// INIZIALIZZAZIONE SUPPORT ANALYSIS
// ============================================
initSupportAnalysis();

// ============================================
// AUTO-LOAD DA URL PARAMETER (gaia_id)
// ============================================
/**
 * Se l'URL contiene ?gaia_id=XXXXX, carica automaticamente la stella
 * Utile per link diretti dall'interfaccia admin
 */
(function autoLoadFromUrlParam() {
  const urlParams = new URLSearchParams(window.location.search);
  const gaiaIdFromUrl = urlParams.get('gaia_id');

  if (gaiaIdFromUrl) {
    console.log(`🚀 Auto-load da URL: gaia_id=${gaiaIdFromUrl}`);

    // La template initialization ha già impostato correttamente:
    // - dataSource a "db" (se gaia_id è presente)
    // - pre-riempito il gaiaId input
    // - mostrato il gaiaBlock
    // Non sovrascrivere le impostazioni del template!

    // Attendi che il DOM sia completamente caricato e poi carica i dati
    // Usiamo setTimeout per assicurarci che tutti gli altri listener siano pronti
    setTimeout(async () => {
      try {
        console.log(`📊 Caricamento automatico stella ${gaiaIdFromUrl}...`);
        await loadDataArrow();
        console.log(`✅ Stella ${gaiaIdFromUrl} caricata con successo`);
      } catch (error) {
        console.error(`❌ Errore caricamento automatico:`, error);
      }
    }, 500);
  }
})();

// ============================================
// EXPORT GLOBALE DELLO STATE
// ============================================
// Esponi lo state globalmente per i moduli che ne hanno bisogno
window.phaseAnalysisState = state;

// Export vuoto - main.js è un modulo che non esporta funzioni, solo inizializza
export {};
