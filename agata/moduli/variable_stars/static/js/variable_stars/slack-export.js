/**
 * slack-export.js - Gestione esportazione verso Slack
 *
 * Fornisce funzioni per inviare:
 * 1. Analisi in Fase: immagine PNG del diagramma + testo minimale
 * 2. Periodigramma: immagine PNG + valori testuali (min, max, periodi)
 * 3. Analisi di Supporto: dati completi formattati in testo
 *
 * Dipendenze:
 * - state.js: accesso ai dati e parametri globali
 * - phase-statistics.js: calculatePhaseStatistics()
 * - plots.js: Plotly charts
 */

import { state, nameForSession, colorForSession, getTotalOffset } from './state.js';
import { calculatePhaseStatistics } from './phase-statistics.js';
import { detrendValue } from './math-logic.js';

// =============================================================================
// 1. INVIO ANALISI IN FASE A SLACK
// =============================================================================

/**
 * Esporta l'analisi in fase a Slack
 * Invia: immagine PNG del diagramma + testo minimale
 */
export async function exportPhaseAnalysisToSlack() {
  if (!state.lastPeriod) {
    alert("❌ Calcola prima l'analisi in fase!");
    return;
  }

  // Estrai project_id dall'input nascosto
  const projectIdInput = document.getElementById("projectId");
  const projectId = projectIdInput?.value;

  if (!projectId) {
    alert("❌ Project ID non trovato!");
    return;
  }

  // Disabilita bottone durante invio
  const btn = document.getElementById("btn-slack-phase-analysis");
  if (btn) btn.disabled = true;

  try {
    // Genera PNG
    const pngData = await generatePhaseAnalysisPNG();
    if (!pngData) {
      alert("❌ Errore generazione PNG");
      return;
    }

    // Compila messaggio
    const message = buildPhaseAnalysisMessage();

    // Invia a backend per upload Slack
    const success = await sendImageAndMessageToSlack(
      projectId,
      'phase_analysis',
      pngData,
      message
    );

    if (success) {
      alert("✅ Analisi in Fase inviata a Slack!");
      if (btn) btn.classList.add('success');
      setTimeout(() => {
        if (btn) btn.classList.remove('success');
      }, 2000);
    } else {
      alert("❌ Errore invio a Slack");
    }
  } catch (error) {
    console.error("❌ Errore esportazione fase:", error);
    alert(`❌ Errore: ${error.message}`);
  } finally {
    if (btn) btn.disabled = false;
  }
}

/**
 * Genera PNG del diagramma in fase
 */
async function generatePhaseAnalysisPNG() {
  const gd = document.getElementById("plotPhase");
  if (!gd) {
    console.error("❌ Elemento plotPhase non trovato");
    return null;
  }

  const opts = {
    format: 'png',
    width: 1200,
    height: 800,
    scale: 2  // 2x per qualità migliore
  };

  try {
    return await Plotly.toImage(gd, opts);
  } catch (error) {
    console.error("❌ Errore generazione PNG fase:", error);
    return null;
  }
}

/**
 * Compila messaggio per Analisi in Fase
 */
function buildPhaseAnalysisMessage() {
  const P = state.lastPeriod;
  const stats = calculatePhaseStatistics();

  let message = `📊 *Analisi in Fase*\n`;
  message += `Inviato dall'editor AGATA\n\n`;
  message += `*Periodo:* ${P.toFixed(8)} giorni\n`;

  if (stats) {
    message += `*RMS:* ${stats.rms.toFixed(6)} mag\n`;
    message += `*χ² ridotto:* ${stats.reducedChiSq.toFixed(4)}\n`;
    message += `*Copertura fase:* ${(stats.coverage * 100).toFixed(1)}%\n`;
  }

  return message;
}

// =============================================================================
// 2. INVIO PERIODIGRAMMA A SLACK
// =============================================================================

/**
 * Esporta periodigramma a Slack
 * Invia: immagine PNG + valori testuali (min, max, periodi, prewhitening)
 */
export async function exportPeriodogramToSlack() {
  // Estrai project_id
  const projectIdInput = document.getElementById("projectId");
  const projectId = projectIdInput?.value;

  if (!projectId) {
    alert("❌ Project ID non trovato!");
    return;
  }

  // Disabilita bottone durante invio
  const btn = document.getElementById("btn-slack-periodogram");
  if (btn) btn.disabled = true;

  try {
    // Genera PNG del periodigramma
    const pngData = await generatePeriodogramPNG();
    if (!pngData) {
      alert("❌ Errore generazione PNG periodigramma");
      return;
    }

    // Compila messaggio con valori testuali
    const message = buildPeriodogramMessage();

    // Invia a Slack
    const success = await sendImageAndMessageToSlack(
      projectId,
      'periodogram',
      pngData,
      message
    );

    if (success) {
      alert("✅ Periodigramma inviato a Slack!");
      if (btn) btn.classList.add('success');
      setTimeout(() => {
        if (btn) btn.classList.remove('success');
      }, 2000);
    } else {
      alert("❌ Errore invio a Slack");
    }
  } catch (error) {
    console.error("❌ Errore esportazione periodigramma:", error);
    alert(`❌ Errore: ${error.message}`);
  } finally {
    if (btn) btn.disabled = false;
  }
}

/**
 * Genera PNG del periodigramma
 */
async function generatePeriodogramPNG() {
  // In modalità per-sessione usa il combinato, altrimenti il grafico classico
  const gd = document.getElementById("plotPeriod-combined") || document.getElementById("plotPeriod");
  if (!gd) {
    console.error("❌ Elemento periodogramma non trovato");
    return null;
  }

  const opts = {
    format: 'png',
    width: 1200,
    height: 600,
    scale: 2
  };

  try {
    return await Plotly.toImage(gd, opts);
  } catch (error) {
    console.error("❌ Errore generazione PNG periodigramma:", error);
    return null;
  }
}

/**
 * Compila messaggio per Periodigramma
 */
function buildPeriodogramMessage() {
  const minP = parseFloat(document.getElementById("minP")?.value || 0.1);
  const maxP = parseFloat(document.getElementById("maxP")?.value || 15);
  const enablePrewhitening = document.getElementById("enablePrewhitening")?.checked || false;
  const nPeriods = document.getElementById("nPeriods")?.value || 3;

  // Estrai i picchi se presenti
  const peaksDiv = document.getElementById("peaks");
  const peaksText = peaksDiv?.innerText || "-";

  let message = `📈 *Periodigramma*\n`;
  message += `Inviato dall'editor AGATA\n\n`;
  message += `*Range Periodo:* ${minP.toFixed(3)} - ${maxP.toFixed(2)} giorni\n`;
  message += `*Pre-whitening:* ${enablePrewhitening ? "✅ Abilitato" : "❌ Disabilitato"}\n`;

  if (enablePrewhitening) {
    message += `*N. Periodi per pre-whitening:* ${nPeriods}\n`;
  }

  message += `\n*Periodi trovati:*\n`;
  message += peaksText;

  return message;
}

// =============================================================================
// 3. INVIO ANALISI DI SUPPORTO A SLACK
// =============================================================================

/**
 * Esporta Analisi di Supporto a Slack
 * Invia: dati completi formattati in testo
 */
export async function exportSupportAnalysisToSlack() {
  // Estrai project_id
  const projectIdInput = document.getElementById("projectId");
  const projectId = projectIdInput?.value;

  if (!projectId) {
    alert("❌ Project ID non trovato!");
    return;
  }

  // Disabilita bottone durante invio
  const btn = document.getElementById("btn-slack-support-analysis");
  if (btn) btn.disabled = true;

  try {
    // Compila messaggio completo
    const message = buildSupportAnalysisMessage();
    if (!message) {
      alert("❌ Errore compilazione dati supporto");
      return;
    }

    // Invia a Slack (senza immagine, solo testo)
    const success = await sendMessageToSlack(
      projectId,
      'support_analysis',
      message
    );

    if (success) {
      alert("✅ Analisi di Supporto inviata a Slack!");
      if (btn) btn.classList.add('success');
      setTimeout(() => {
        if (btn) btn.classList.remove('success');
      }, 2000);
    } else {
      alert("❌ Errore invio a Slack");
    }
  } catch (error) {
    console.error("❌ Errore esportazione supporto:", error);
    alert(`❌ Errore: ${error.message}`);
  } finally {
    if (btn) btn.disabled = false;
  }
}

/**
 * Compila messaggio completo per Analisi di Supporto
 */
function buildSupportAnalysisMessage() {
  // === SEZIONE 1: Informazioni Base ===
  const gaiaId = document.getElementById("info-gaia-id")?.innerText || "-";
  const coords = document.getElementById("info-coords")?.value || "-";
  const coordsJ2000 = document.getElementById("info-coords-j2000")?.value || "-";
  const vmag = document.getElementById("info-vmag")?.textContent || "-";
  const vmagDetail = document.getElementById("info-vmag-detail")?.textContent || "";
  const period = document.getElementById("info-period")?.innerText || "-";

  // === SEZIONE 2: Parametri Fisici ===
  const spectralClass = document.getElementById("spectral_class")?.value || "-";
  const teff = document.getElementById("teff")?.value || "-";
  const distance = document.getElementById("distance")?.value || "-";
  const luminosity = document.getElementById("luminosity")?.value || "-";
  const radius = document.getElementById("radius")?.value || "-";
  const mass = document.getElementById("mass")?.value || "-";
  const colorBV = document.getElementById("color_bv")?.value || "-";
  const colorBPRP = document.getElementById("color_bprp")?.value || "-";
  const variableType = document.getElementById("variable_type")?.value || "-";
  const catalogIds = document.getElementById("catalog_identifiers")?.value || "-";
  const amplitude = document.getElementById("variability_amplitude")?.value || "-";
  const passband = document.getElementById("passband")?.value || "-";
  const epoch = document.getElementById("epochPhase")?.value || document.getElementById("epoch")?.value || "-";

  // Compila messaggio strutturato
  let message = `📊 *Analisi di Supporto - Preparazione AAVSO/VSX*\n`;
  message += `Inviato dall'editor AGATA\n\n`;

  message += `*═══ INFORMAZIONI BASE ═══*\n`;
  message += `Stella Gaia DR3: ${gaiaId}\n`;
  message += `Coordinate (RA, Dec): ${coords}\n`;
  message += `Coordinate J2000: ${coordsJ2000}\n`;
  message += `Magnitudine V (Gaia): ${vmag} ${vmagDetail}\n`;
  message += `Periodo (dall'analisi in fase): ${period}\n\n`;

  message += `*═══ PARAMETRI FISICI STELLA ═══*\n`;
  message += `Classe Spettrale: ${spectralClass}\n`;
  message += `Teff (K): ${teff}\n`;
  message += `Distanza (pc): ${distance}\n`;
  message += `Luminosità (L☉): ${luminosity}\n`;
  message += `Raggio (R☉): ${radius}\n`;
  message += `Massa (M☉): ${mass}\n`;
  message += `Colore B-V: ${colorBV}\n`;
  message += `Colore BP-RP: ${colorBPRP}\n\n`;

  message += `*═══ TIPO DI VARIABILE ═══*\n`;
  message += `Tipo Proposto: ${variableType}\n\n`;

  message += `*═══ IDENTIFICATORI CATALOGHI ═══*\n`;
  if (catalogIds && catalogIds !== "-") {
    message += catalogIds.split('\n').map(id => `• ${id.trim()}`).join('\n') + '\n\n';
  } else {
    message += "-\n\n";
  }

  message += `*═══ PARAMETRI VARIABILITÀ ═══*\n`;
  message += `Ampiezza Variabilità (mag): ${amplitude}\n`;
  message += `Passband: ${passband}\n`;
  message += `Epoch (JD): ${epoch}\n`;

  return message;
}

// =============================================================================
// FUNZIONI BACKEND COMMUNICATION
// =============================================================================

/**
 * Invia immagine + messaggio a Slack via backend nel thread del progetto
 */
async function sendImageAndMessageToSlack(projectId, analysisType, imageData, message) {
  try {
    const formData = new FormData();
    formData.append('project_id', projectId);
    formData.append('analysis_type', analysisType);
    formData.append('message', message);

    // Converte data URL a blob
    const blob = await fetch(imageData).then(r => r.blob());
    formData.append('image', blob, `${analysisType}.png`);

    const response = await fetch('/agata/admin/api/slack-export', {
      method: 'POST',
      body: formData
    });

    const result = await response.json();

    if (!response.ok) {
      console.error("❌ Errore backend:", result);

      // Gestisci errori specifici
      if (result.error?.includes('No Slack thread')) {
        alert("❌ Errore: Il progetto deve essere creato prima di esportare a Slack");
      } else if (result.error?.includes('Slack not enabled')) {
        alert("❌ Errore: Slack non è abilitato per questa associazione");
      } else {
        alert(`❌ Errore: ${result.error || 'Errore sconosciuto'}`);
      }
      return false;
    }

    return true;
  } catch (error) {
    console.error("❌ Errore comunicazione backend:", error);
    alert(`❌ Errore: ${error.message}`);
    return false;
  }
}

/**
 * Invia solo messaggio a Slack via backend nel thread del progetto (per Analisi di Supporto)
 */
async function sendMessageToSlack(projectId, analysisType, message) {
  // Validazione: project_id è obbligatorio
  if (!projectId || projectId === '' || projectId === '0') {
    console.error("❌ Project ID non disponibile:", projectId);
    alert("❌ Errore: Il progetto non è stato caricato. Ricarica la pagina e prova di nuovo.");
    return false;
  }

  try {
    const response = await fetch('/agata/admin/api/slack-export', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        project_id: projectId,
        analysis_type: analysisType,
        message: message
      })
    });

    const result = await response.json();

    if (!response.ok) {
      console.error("❌ Errore backend:", result);

      // Gestisci errori specifici
      if (result.error?.includes('No Slack thread')) {
        alert("❌ Errore: Il progetto deve essere creato prima di esportare a Slack");
      } else if (result.error?.includes('Slack not enabled')) {
        alert("❌ Errore: Slack non è abilitato per questa associazione");
      } else {
        alert(`❌ Errore: ${result.error || 'Errore sconosciuto'}`);
      }
      return false;
    }

    return true;
  } catch (error) {
    console.error("❌ Errore comunicazione backend:", error);
    alert(`❌ Errore: ${error.message}`);
    return false;
  }
}

// =============================================================================
// INIT BOTTONI
// =============================================================================

/**
 * Inizializza event handler per bottoni Slack
 * Chiamare da main.js dopo DOM ready
 */
export function initSlackExportButtons() {
  // Bottone Analisi in Fase
  const btnPhase = document.getElementById("btn-slack-phase-analysis");
  if (btnPhase) {
    btnPhase.addEventListener('click', exportPhaseAnalysisToSlack);
  }

  // Bottone Periodigramma
  const btnPeriodogram = document.getElementById("btn-slack-periodogram");
  if (btnPeriodogram) {
    btnPeriodogram.addEventListener('click', exportPeriodogramToSlack);
  }

  // Bottone Analisi di Supporto
  const btnSupport = document.getElementById("btn-slack-support-analysis");
  if (btnSupport) {
    btnSupport.addEventListener('click', exportSupportAnalysisToSlack);
  }

  // Bottone Curva di Luce
  const btnLc = document.getElementById("btn-slack-lc");
  if (btnLc) {
    btnLc.addEventListener('click', exportLightCurveToSlack);
  }

  // Bottone Stack Sessioni → Slack
  const btnSlackStack = document.getElementById("btn-slack-stack");
  if (btnSlackStack) {
    btnSlackStack.addEventListener('click', exportSessionStackToSlack);
  }

  // Bottone Stack Sessioni → Download locale
  const btnDownloadStack = document.getElementById("btn-download-stack");
  if (btnDownloadStack) {
    btnDownloadStack.addEventListener('click', downloadSessionStack);
  }
}

// =============================================================================
// 4. INVIO CURVA DI LUCE A SLACK
// =============================================================================

/**
 * Genera PNG della curva di luce visibile
 */
async function generateLightCurvePNG() {
  const gd = document.getElementById("plotLC");
  if (!gd) {
    console.error("❌ Elemento curva di luce non trovato");
    return null;
  }
  try {
    return await Plotly.toImage(gd, { format: 'png', width: 1200, height: 500, scale: 2 });
  } catch (error) {
    console.error("❌ Errore generazione PNG curva di luce:", error);
    return null;
  }
}

/**
 * Compila messaggio riepilogativo curva di luce
 */
function buildLightCurveMessage() {
  const projectName = document.getElementById("info-project-name")?.innerText || "";
  const gaiaId = document.getElementById("projectGaiaId")?.value || "";

  const sids = Array.from(state.activeSession.keys()).sort((a, b) => a - b);

  // Conta punti attivi totali
  let totalActive = 0;
  for (let i = 0; i < state.n; i++) {
    if (state.activePoint[i] === 1) totalActive++;
  }
  const totalRemoved = state.n - totalActive;

  // Sessioni visibili
  const visibleSids = sids.filter(sid => state.activeSession.get(sid));
  let sessionVisibleNote = '';
  if (visibleSids.length === 1) {
    sessionVisibleNote = `\n📌 *Sessione visibile*: ${nameForSession(visibleSids[0])}`;
  } else if (visibleSids.length === 0) {
    sessionVisibleNote = '\n⚠️ Nessuna sessione visibile';
  }

  // Righe per sessione
  const sessionLines = sids.map(sid => {
    const name = nameForSession(sid);
    const visible = state.activeSession.get(sid) ? '👁' : '🙈';
    let pts = 0;
    let total = 0;
    for (let i = 0; i < state.n; i++) {
      if (state.session[i] === sid) {
        total++;
        if (state.activePoint[i] === 1) pts++;
      }
    }
    const removed = total - pts;
    const offset = getTotalOffset(sid);
    const offsetStr = offset !== 0 ? ` | offset ${offset > 0 ? '+' : ''}${offset.toFixed(3)} mag` : '';
    const removedStr = removed > 0 ? ` | ❌ ${removed} rimossi` : '';
    return `• ${visible} *${name}*: ${pts} punti${removedStr}${offsetStr}`;
  }).join('\n');

  // Misure barre (se attive)
  const dtText = document.getElementById('lc-delta-t')?.textContent?.trim();
  const dmText = document.getElementById('lc-delta-mag')?.textContent?.trim();

  let msg = `🌟 *Curva di Luce — ${projectName}*`;
  if (gaiaId) msg += ` (Gaia ${gaiaId})`;
  msg += `\n\n*Sessioni (${sids.length}):*\n${sessionLines}`;
  msg += `\n\n📊 *Totale attivi*: ${totalActive} / ${state.n} punti`;
  if (totalRemoved > 0) msg += ` | ❌ ${totalRemoved} rimossi`;
  msg += sessionVisibleNote;
  if (dtText) msg += `\n📏 *${dtText}*`;
  if (dmText) msg += `\n📐 *${dmText}*`;
  return msg;
}

/**
 * Esporta curva di luce (PNG + riepilogo) a Slack
 */
export async function exportLightCurveToSlack() {
  const btn = document.getElementById("btn-slack-lc");
  const projectId = document.getElementById("projectId")?.value;
  if (!projectId) {
    alert("❌ Project ID non trovato!");
    return;
  }
  if (btn) btn.disabled = true;
  const origHtml = btn ? btn.innerHTML : '';
  if (btn) btn.textContent = '⏳';

  try {
    const message = buildLightCurveMessage();
    const pngDataUrl = await generateLightCurvePNG();
    if (!pngDataUrl) throw new Error('PNG non generato');

    await sendImageAndMessageToSlack(projectId, 'light_curve', pngDataUrl, message);

    if (btn) {
      btn.textContent = '✅';
      setTimeout(() => { btn.innerHTML = origHtml; btn.disabled = false; }, 2000);
    }
  } catch (error) {
    console.error("❌ Errore invio curva di luce a Slack:", error);
    if (btn) {
      btn.textContent = '❌';
      setTimeout(() => { btn.innerHTML = origHtml; btn.disabled = false; }, 2000);
    }
  }
}

// =============================================================================
// 5. EXPORT STACK SESSIONI (PNG impilate verticalmente)
// =============================================================================

/**
 * Genera un PNG canvas con tutte le sessioni visibili impilate verticalmente.
 * Ogni pannello: mini-grafico Plotly esportato via toImage, poi combinati su canvas.
 */
export async function generateSessionStackPNG() {
  const PANEL_WIDTH = 1200;
  const PANEL_HEIGHT = 300;
  const SCALE = 2;

  const activeSids = Array.from(state.activeSession.entries())
    .filter(([, visible]) => visible)
    .map(([sid]) => sid)
    .sort((a, b) => a - b);

  if (activeSids.length === 0) return null;

  // Genera PNG per ogni sessione con un grafico Plotly temporaneo
  const panelImages = [];
  const tempDiv = document.createElement('div');
  tempDiv.style.cssText = 'position:fixed;left:-9999px;top:0;width:600px;height:300px;';
  document.body.appendChild(tempDiv);

  try {
    for (const sid of activeSids) {
      const jdArr = [], magArr = [];
      for (let i = 0; i < state.n; i++) {
        if (state.session[i] !== sid) continue;
        if (state.activePoint[i] === 0) continue;
        jdArr.push(state.jd[i]);
        magArr.push(state.mag[i] + getTotalOffset(sid));
      }
      if (jdArr.length === 0) continue;

      const jdMin = Math.min(...jdArr);
      const xVals = jdArr.map(v => v - jdMin);
      const color = colorForSession(sid);
      const sessionLabel = state.simpleLegend ? nameForSession(sid) : `${nameForSession(sid)} (${jdArr.length})`;
      const panelTitle = `JD Plot — ${sessionLabel}`;

      const traces = [{
        type: 'scattergl',
        mode: 'markers',
        x: xVals,
        y: magArr,
        name: sessionLabel,
        marker: { size: 4, color, opacity: 0.85 }
      }];

      const layout = {
        title: { text: panelTitle, font: { size: 13 } },
        xaxis: { title: `JD \u2212 ${jdMin.toFixed(5)}`, tickfont: { size: 10 } },
        yaxis: { title: 'Mag', autorange: 'reversed', tickfont: { size: 10 } },
        margin: { t: 40, b: 50, l: 55, r: 15 },
        showlegend: false,
        paper_bgcolor: 'white',
        plot_bgcolor: 'white'
      };

      await Plotly.react(tempDiv, traces, layout, { staticPlot: true, responsive: false });
      const imgUrl = await Plotly.toImage(tempDiv, { format: 'png', width: PANEL_WIDTH, height: PANEL_HEIGHT, scale: SCALE });
      panelImages.push(imgUrl);
    }
  } finally {
    document.body.removeChild(tempDiv);
  }

  if (panelImages.length === 0) return null;

  // Carica tutte le immagini
  const loadImage = url => new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = url;
  });
  const imgs = await Promise.all(panelImages.map(loadImage));

  // Combina su canvas verticale (nessun header generale — ogni pannello ha il suo titolo)
  const canvasW = PANEL_WIDTH * SCALE;
  const panelH = PANEL_HEIGHT * SCALE;
  const GAP = 30 * SCALE;  // spazio bianco tra pannelli (px fisici)
  const canvas = document.createElement('canvas');
  canvas.width = canvasW;
  canvas.height = imgs.length * panelH + (imgs.length - 1) * GAP;
  const ctx = canvas.getContext('2d');

  ctx.fillStyle = 'white';
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  // Disegna ogni pannello con gap tra loro
  imgs.forEach((img, i) => {
    const yOffset = i * (panelH + GAP);
    ctx.drawImage(img, 0, yOffset, canvasW, panelH);
    if (i < imgs.length - 1) {
      // Linea separatrice grigia al centro del gap
      const lineY = yOffset + panelH + GAP / 2;
      ctx.strokeStyle = '#9ca3af';
      ctx.lineWidth = 1 * SCALE;
      ctx.beginPath();
      ctx.moveTo(0, lineY);
      ctx.lineTo(canvasW, lineY);
      ctx.stroke();
    }
  });

  return canvas.toDataURL('image/png');
}

/**
 * Scarica lo stack PNG in locale
 */
export async function downloadSessionStack() {
  const btn = document.getElementById('btn-download-stack');
  if (btn) btn.disabled = true;
  const origHtml = btn ? btn.innerHTML : '';
  if (btn) btn.textContent = '⏳';

  try {
    const dataUrl = await generateSessionStackPNG();
    if (!dataUrl) throw new Error('Nessuna sessione visibile');

    const projectId = document.getElementById("projectId")?.value || '0';
    const gaiaId = document.getElementById("projectGaiaId")?.value || 'unknown';
    const ts = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
    const filename = `AGATA_PRJ${projectId}_${gaiaId}_${ts}_lightcurve_stack.png`;
    const a = document.createElement('a');
    a.href = dataUrl;
    a.download = filename;
    a.click();

    if (btn) {
      btn.textContent = '✅';
      setTimeout(() => { btn.innerHTML = origHtml; btn.disabled = false; }, 2000);
    }
  } catch (error) {
    console.error('❌ Errore download stack:', error);
    if (btn) {
      btn.textContent = '❌';
      setTimeout(() => { btn.innerHTML = origHtml; btn.disabled = false; }, 2000);
    }
  }
}

/**
 * Invia stack sessioni a Slack
 */
export async function exportSessionStackToSlack() {
  const btn = document.getElementById('btn-slack-stack');
  const projectId = document.getElementById("projectId")?.value;
  if (!projectId) { alert("❌ Project ID non trovato!"); return; }
  if (btn) btn.disabled = true;
  const origHtml = btn ? btn.innerHTML : '';
  if (btn) btn.textContent = '⏳';

  try {
    const dataUrl = await generateSessionStackPNG();
    if (!dataUrl) throw new Error('Nessuna sessione visibile');

    const projectName = document.getElementById("info-project-name")?.innerText || "";
    const gaiaId = document.getElementById("projectGaiaId")?.value || "";
    const activeSids = Array.from(state.activeSession.entries())
      .filter(([, v]) => v).map(([sid]) => sid);
    const sessionList = activeSids.map(sid => {
      const label = state.simpleLegend ? nameForSession(sid) : `${nameForSession(sid)}`;
      let pts = 0;
      for (let i = 0; i < state.n; i++) {
        if (state.session[i] === sid && state.activePoint[i] === 1) pts++;
      }
      return `• *${label}*: ${pts} punti`;
    }).join('\n');

    let message = `📊 *Stack Sessioni — ${projectName}*`;
    if (gaiaId) message += ` (Gaia ${gaiaId})`;
    message += `\n\n*Sessioni (${activeSids.length}):*\n${sessionList}`;

    await sendImageAndMessageToSlack(projectId, 'session_stack', dataUrl, message);

    if (btn) {
      btn.textContent = '✅';
      setTimeout(() => { btn.innerHTML = origHtml; btn.disabled = false; }, 2000);
    }
  } catch (error) {
    console.error('❌ Errore invio stack a Slack:', error);
    if (btn) {
      btn.textContent = '❌';
      setTimeout(() => { btn.innerHTML = origHtml; btn.disabled = false; }, 2000);
    }
  }
}
