const state = {
  preview: null,
  selections: [],
  evaluation: null,
  lastSeries: null,
  lastRunResult: null,
  view: {
    scale: 1,
    offsetX: 0,
    offsetY: 0,
    dragging: false,
    moved: false,
    dragStartX: 0,
    dragStartY: 0,
    dragOriginX: 0,
    dragOriginY: 0,
  },
};

const folderInput = document.getElementById("folder");
const previewButton = document.getElementById("preview-button");
const runButton = document.getElementById("run-button");
const exportButton = document.getElementById("export-button");
const previewImage = document.getElementById("preview-image");
const previewWrap = document.getElementById("preview-wrap");
const previewStage = document.getElementById("preview-stage");
const previewOverlay = document.getElementById("preview-overlay");
const errorBox = document.getElementById("error");
const statusBox = document.getElementById("status");
const metaBox = document.getElementById("meta");
const selectionBox = document.getElementById("selection");
const warningBox = document.getElementById("warnings");
const resultsBox = document.getElementById("results");
const chartCanvas = document.getElementById("lightcurve-chart");
const chartContext = chartCanvas.getContext("2d");
const targetModeInput = document.getElementById("target_mode");
const curveViewModeInput = document.getElementById("curve_view_mode");
const exportModeInput = document.getElementById("export_mode");
const zoomInButton = document.getElementById("zoom-in-button");
const zoomOutButton = document.getElementById("zoom-out-button");
const resetViewButton = document.getElementById("reset-view-button");

function configPayload() {
  return {
    aperture_radius: Number(document.getElementById("aperture_radius").value),
    annulus_r_in: Number(document.getElementById("annulus_r_in").value),
    annulus_r_out: Number(document.getElementById("annulus_r_out").value),
    centroid_stamp_r: Number(document.getElementById("centroid_stamp_r").value),
    fwhm_stamp_r: Number(document.getElementById("fwhm_stamp_r").value),
    starlike_check_r: Number(document.getElementById("starlike_check_r").value),
    starlike_sigma: Number(document.getElementById("starlike_sigma").value),
    detrend_mode: document.getElementById("detrend_mode").value,
  };
}

function targetCoordinatesPayload() {
  return {
    ra: document.getElementById("target_ra").value.trim(),
    dec: document.getElementById("target_dec").value.trim(),
  };
}

function setError(message) {
  errorBox.textContent = message || "";
}

function setStatus(message) {
  statusBox.textContent = `Stato: ${message}`;
}

async function snapPoint(point) {
  return postJson("/agata/lightcurve/api/snap-point", {
    folder: folderInput.value.trim(),
    config: configPayload(),
    point,
  });
}

function renderSelection() {
  if (!state.selections.length) {
    selectionBox.innerHTML = '<div class="hint">Nessuna selezione.</div>';
    return;
  }
  const targetEval = state.evaluation?.target || null;
  const compEvals = state.evaluation?.comparators || [];
  selectionBox.innerHTML = "";
  state.selections.forEach((point, index) => {
    const label = index === 0 ? "TARGET" : `COMP ${index}`;
    const quality = index === 0 ? targetEval : compEvals[index - 1];
    const row = document.createElement("div");
    row.className = `selection-row ${quality?.status || "bad"}`;
    const text = document.createElement("div");
    const lines = [`<strong>${label}</strong>`];
    lines.push(`Coordinate: x=${point.x.toFixed(2)} y=${point.y.toFixed(2)}`);
    if (quality) {
      lines.push(`Qualità: ${quality.status} | Star-like: ${quality.star_like ? "sì" : "no"} | Score: ${quality.score.toFixed(2)}`);
      lines.push(`Centroide raffinato: x=${quality.refined_x?.toFixed?.(2) ?? "n/a"} y=${quality.refined_y?.toFixed?.(2) ?? "n/a"}`);
      lines.push(`Drift dal click: ${quality.distance_to_refined?.toFixed?.(2) ?? "n/a"} px`);
      if (quality.sky) {
        lines.push(`RA/Dec: ${quality.sky.ra_hms} | ${quality.sky.dec_dms}`);
        lines.push(`RA/Dec gradi: ${quality.sky.ra_deg.toFixed(6)} | ${quality.sky.dec_deg.toFixed(6)}`);
      }
    }
    text.className = "details-grid";
    text.innerHTML = lines.map((line) => `<div>${line}</div>`).join("");
    const removeButton = document.createElement("button");
    removeButton.className = "ghost";
    removeButton.type = "button";
    removeButton.textContent = "Rimuovi";
    removeButton.addEventListener("click", async () => {
      state.selections.splice(index, 1);
      if (state.selections.length) {
        await refreshSelectionEvaluation();
      } else {
        state.evaluation = null;
      }
      renderSelection();
      renderMarkers();
    });
    row.appendChild(text);
    row.appendChild(removeButton);
    selectionBox.appendChild(row);
  });
}

function resetChart(message = "In attesa di esecuzione.") {
  chartContext.clearRect(0, 0, chartCanvas.width, chartCanvas.height);
  chartContext.fillStyle = "#020617";
  chartContext.fillRect(0, 0, chartCanvas.width, chartCanvas.height);
  chartContext.fillStyle = "#94a3b8";
  chartContext.font = "16px Segoe UI";
  chartContext.fillText(message, 24, 40);
}

function clearMarkers() {
  previewWrap.querySelectorAll(".marker").forEach((node) => node.remove());
}

function flipPreviewY(y) {
  return state.preview.height - y;
}

function syncPreviewStageSize() {
  if (!state.preview) {
    return;
  }
  previewStage.style.width = `${state.preview.width}px`;
  previewStage.style.height = `${state.preview.height}px`;
}

function clampView() {
  if (!state.preview) {
    return;
  }
  const scaledWidth = state.preview.width * state.view.scale;
  const scaledHeight = state.preview.height * state.view.scale;
  let minOffsetX = previewWrap.clientWidth - scaledWidth;
  let maxOffsetX = 0;
  let minOffsetY = previewWrap.clientHeight - scaledHeight;
  let maxOffsetY = 0;

  if (scaledWidth <= previewWrap.clientWidth) {
    minOffsetX = maxOffsetX = (previewWrap.clientWidth - scaledWidth) / 2;
  }
  if (scaledHeight <= previewWrap.clientHeight) {
    minOffsetY = maxOffsetY = (previewWrap.clientHeight - scaledHeight) / 2;
  }

  state.view.offsetX = Math.min(maxOffsetX, Math.max(minOffsetX, state.view.offsetX));
  state.view.offsetY = Math.min(maxOffsetY, Math.max(minOffsetY, state.view.offsetY));
}

function applyViewTransform() {
  if (!state.preview) {
    return;
  }
  clampView();
  previewStage.style.transform = `translate(${state.view.offsetX}px, ${state.view.offsetY}px) scale(${state.view.scale})`;
}

function resetView() {
  if (!state.preview) {
    return;
  }
  const scaleX = previewWrap.clientWidth / state.preview.width;
  const scaleY = previewWrap.clientHeight / state.preview.height;
  state.view.scale = Math.min(scaleX, scaleY);
  const scaledWidth = state.preview.width * state.view.scale;
  const scaledHeight = state.preview.height * state.view.scale;
  state.view.offsetX = (previewWrap.clientWidth - scaledWidth) / 2;
  state.view.offsetY = (previewWrap.clientHeight - scaledHeight) / 2;
  applyViewTransform();
}

function zoomAt(clientX, clientY, factor) {
  if (!state.preview) {
    return;
  }
  const rect = previewWrap.getBoundingClientRect();
  const px = clientX - rect.left;
  const py = clientY - rect.top;
  const oldScale = state.view.scale;
  const fitScale = Math.min(previewWrap.clientWidth / state.preview.width, previewWrap.clientHeight / state.preview.height);
  const newScale = Math.min(8, Math.max(fitScale, oldScale * factor));
  if (newScale === oldScale) {
    return;
  }
  const imageX = (px - state.view.offsetX) / oldScale;
  const imageY = (py - state.view.offsetY) / oldScale;
  state.view.scale = newScale;
  state.view.offsetX = px - imageX * newScale;
  state.view.offsetY = py - imageY * newScale;
  applyViewTransform();
}

function renderPreviewOverlay() {
  previewOverlay.innerHTML = "";
  if (!state.preview?.overlay) {
    return;
  }
  syncPreviewStageSize();
  previewOverlay.setAttribute("viewBox", `0 0 ${state.preview.width} ${state.preview.height}`);

  const ns = "http://www.w3.org/2000/svg";
  const grid = state.preview.overlay.grid || [];
  grid.forEach((line) => {
    if (!line.points?.length) {
      return;
    }
    const polyline = document.createElementNS(ns, "polyline");
    polyline.setAttribute(
      "points",
      line.points.map((point) => `${point.x},${flipPreviewY(point.y)}`).join(" "),
    );
    polyline.setAttribute("class", "grid-line");
    previewOverlay.appendChild(polyline);

    const labelPoint = line.points[0];
    if (labelPoint) {
      const text = document.createElementNS(ns, "text");
      text.setAttribute("x", String(labelPoint.x + 10));
      text.setAttribute("y", String(flipPreviewY(labelPoint.y) - 6));
      text.setAttribute("class", "grid-label");
      text.textContent = line.label;
      previewOverlay.appendChild(text);
    }
  });

  const center = state.preview.overlay.center;
  if (center) {
    const size = 18;
    const centerY = flipPreviewY(center.y);
    const line1 = document.createElementNS(ns, "line");
    line1.setAttribute("x1", String(center.x - size));
    line1.setAttribute("y1", String(centerY - size));
    line1.setAttribute("x2", String(center.x + size));
    line1.setAttribute("y2", String(centerY + size));
    line1.setAttribute("class", "center-cross");
    const line2 = document.createElementNS(ns, "line");
    line2.setAttribute("x1", String(center.x - size));
    line2.setAttribute("y1", String(centerY + size));
    line2.setAttribute("x2", String(center.x + size));
    line2.setAttribute("y2", String(centerY - size));
    line2.setAttribute("class", "center-cross");
    previewOverlay.appendChild(line1);
    previewOverlay.appendChild(line2);
  }
}

function renderMarkers() {
  clearMarkers();
  if (!state.preview) {
    return;
  }
  state.selections.forEach((point, index) => {
    const marker = document.createElement("div");
    const quality = index === 0 ? state.evaluation?.target : state.evaluation?.comparators?.[index - 1];
    marker.className = `marker ${index === 0 ? "target" : "comp"}`;
    marker.title = quality ? `${quality.status} | score ${quality.score.toFixed(2)}` : "";
    marker.style.left = `${state.view.offsetX + point.x * state.view.scale}px`;
    marker.style.top = `${state.view.offsetY + flipPreviewY(point.y) * state.view.scale}px`;
    previewWrap.appendChild(marker);
  });
}

function drawSeries(series) {
  state.lastSeries = series;
  resetChart("");
  chartContext.fillStyle = "#020617";
  chartContext.fillRect(0, 0, chartCanvas.width, chartCanvas.height);

  const raw = series.flux_normalized || [];
  const detrended = series.flux_detrended || [];
  const mode = curveViewModeInput.value;
  const visibleSeries = [];
  if (mode === "raw" || mode === "both") {
    visibleSeries.push({ values: raw, color: "#38bdf8", label: "raw" });
  }
  if (mode === "detrended" || mode === "both") {
    visibleSeries.push({ values: detrended, color: "#f59e0b", label: "detrended" });
  }
  if (!visibleSeries.length) {
    resetChart("Nessuna serie selezionata.");
    return;
  }

  const allValues = visibleSeries.flatMap((item) => item.values).filter(Number.isFinite);
  if (!allValues.length) {
    resetChart("Nessun dato disponibile.");
    return;
  }

  const minY = Math.min(...allValues);
  const maxY = Math.max(...allValues);
  const pad = 28;
  const plotWidth = chartCanvas.width - pad * 2;
  const plotHeight = chartCanvas.height - pad * 2;

  chartContext.strokeStyle = "#334155";
  chartContext.lineWidth = 1;
  chartContext.strokeRect(pad, pad, plotWidth, plotHeight);

  function project(index, value, length) {
    const x = pad + (index / Math.max(length - 1, 1)) * plotWidth;
    const y = pad + (1 - (value - minY) / Math.max(maxY - minY, 1e-9)) * plotHeight;
    return { x, y };
  }

  function drawDataset(values, color) {
    chartContext.fillStyle = color;
    values.forEach((value, index) => {
      if (!Number.isFinite(value)) {
        return;
      }
      const point = project(index, value, values.length);
      chartContext.beginPath();
      chartContext.arc(point.x, point.y, 2.2, 0, Math.PI * 2);
      chartContext.fill();
    });
  }

  visibleSeries.forEach((item) => drawDataset(item.values, item.color));

  chartContext.fillStyle = "#94a3b8";
  chartContext.font = "12px Segoe UI";
  const labels = visibleSeries.map((item) => item.label).join(" + ");
  chartContext.fillText(`${labels} min/max: ${minY.toFixed(5)} / ${maxY.toFixed(5)}`, pad, chartCanvas.height - 10);
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const text = await response.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { error: text || "Risposta non JSON dal server." };
  }
  if (!response.ok) {
    throw new Error(data.error || "Richiesta fallita");
  }
  return data;
}

async function refreshSelectionEvaluation() {
  if (!state.preview) {
    return;
  }
  setStatus("valuto la qualità delle stelle selezionate...");
  const [target, ...comparators] = state.selections;
  state.evaluation = await postJson("/agata/lightcurve/api/evaluate-selection", {
    folder: folderInput.value.trim(),
    config: configPayload(),
    target_coordinates: targetCoordinatesPayload(),
    target,
    comparators,
  });
  setStatus("valutazione selezione completata.");
}

function applyAutoTarget(autoTarget) {
  if (!autoTarget || !autoTarget.in_bounds) {
    return;
  }
  if (state.selections.length === 0) {
    state.selections.push({ x: autoTarget.x, y: autoTarget.y });
  } else {
    state.selections[0] = { x: autoTarget.x, y: autoTarget.y };
  }
}

function shouldUseAutoTarget() {
  return targetModeInput.value === "auto";
}

previewButton.addEventListener("click", async () => {
  setError("");
  state.selections = [];
  state.evaluation = null;
  renderSelection();
  clearMarkers();
  warningBox.textContent = "Nessun warning.";
  resultsBox.innerHTML = '<div class="hint">In attesa di esecuzione.</div>';
  resetChart();

  try {
    setStatus("sto caricando il frame FITS di riferimento...");
    const data = await postJson("/agata/lightcurve/api/preview", {
      folder: folderInput.value.trim(),
      target_coordinates: targetCoordinatesPayload(),
    });
    state.preview = data;
    previewImage.src = `data:image/png;base64,${data.preview_png_base64}`;
    syncPreviewStageSize();
    renderPreviewOverlay();
    resetView();
    if (shouldUseAutoTarget()) {
      setStatus("sto proiettando il target da RA/Dec sul frame...");
      applyAutoTarget(data.auto_target);
    }
    if (state.selections.length) {
      await refreshSelectionEvaluation();
    } else {
      setStatus("preview caricata. Seleziona il target e i comparatori.");
    }
    renderSelection();
    renderMarkers();
    metaBox.innerHTML = [
      `<div><strong>Folder:</strong> ${data.folder}</div>`,
      `<div><strong>Frame:</strong> ${data.frame_path}</div>`,
      `<div><strong>FITS trovati:</strong> ${data.fits_count}</div>`,
      `<div><strong>Dimensioni:</strong> ${data.width} x ${data.height}</div>`,
      `<div><strong>Centro frame:</strong> x=${data.overlay?.center?.x?.toFixed?.(2) ?? "n/a"} y=${data.overlay?.center?.y?.toFixed?.(2) ?? "n/a"}</div>`,
      `<div><strong>Target auto da coordinate:</strong> ${data.auto_target ? `x=${data.auto_target.x.toFixed(2)} y=${data.auto_target.y.toFixed(2)} | in bounds: ${data.auto_target.in_bounds ? "sì" : "no"}` : "non disponibile"}</div>`,
    ].join("");
    if (!shouldUseAutoTarget()) {
      setStatus("preview caricata. Modalità manuale attiva.");
    }
  } catch (error) {
    setError(error.message);
    setStatus("errore durante il caricamento preview.");
  }
});

previewWrap.addEventListener("wheel", (event) => {
  if (!state.preview) {
    return;
  }
  event.preventDefault();
  const factor = event.deltaY < 0 ? 1.15 : 1 / 1.15;
  zoomAt(event.clientX, event.clientY, factor);
  renderMarkers();
});

previewWrap.addEventListener("pointerdown", (event) => {
  if (!state.preview) {
    return;
  }
  event.preventDefault();
  state.view.dragging = true;
  state.view.moved = false;
  state.view.dragStartX = event.clientX;
  state.view.dragStartY = event.clientY;
  state.view.dragOriginX = state.view.offsetX;
  state.view.dragOriginY = state.view.offsetY;
  if (previewWrap.setPointerCapture) {
    try {
      previewWrap.setPointerCapture(event.pointerId);
    } catch {}
  }
});

window.addEventListener("pointermove", (event) => {
  if (!state.view.dragging || !state.preview) {
    return;
  }
  const deltaX = event.clientX - state.view.dragStartX;
  const deltaY = event.clientY - state.view.dragStartY;
  if (!state.view.moved && Math.hypot(deltaX, deltaY) > 6) {
    state.view.moved = true;
    previewWrap.style.cursor = "grabbing";
  }
  if (!state.view.moved) {
    return;
  }
  event.preventDefault();
  state.view.offsetX = state.view.dragOriginX + (event.clientX - state.view.dragStartX);
  state.view.offsetY = state.view.dragOriginY + (event.clientY - state.view.dragStartY);
  applyViewTransform();
  renderMarkers();
});

window.addEventListener("pointerup", async (event) => {
  if (state.view.dragging && state.preview && !state.view.moved) {
    setError("");
    const rect = previewWrap.getBoundingClientRect();
    const x = (event.clientX - rect.left - state.view.offsetX) / state.view.scale;
    const y = state.preview.height - (event.clientY - rect.top - state.view.offsetY) / state.view.scale;
    if (x >= 0 && x <= state.preview.width && y >= 0 && y <= state.preview.height) {
      try {
        setStatus("sto agganciando la stella più vicina al click...");
        const snapped = await snapPoint({ x, y });
        state.selections.push({ x: snapped.x, y: snapped.y });
        await refreshSelectionEvaluation();
        renderSelection();
        renderMarkers();
      } catch (error) {
        setError(error.message);
        setStatus("errore durante l'aggancio della stella.");
      }
    }
  }
  state.view.dragging = false;
  state.view.moved = false;
  previewWrap.style.cursor = "crosshair";
  if (previewWrap.releasePointerCapture) {
    try {
      previewWrap.releasePointerCapture(event.pointerId);
    } catch {}
  }
});

zoomInButton.addEventListener("click", () => {
  const rect = previewWrap.getBoundingClientRect();
  zoomAt(rect.left + rect.width / 2, rect.top + rect.height / 2, 1.2);
  renderMarkers();
});

zoomOutButton.addEventListener("click", () => {
  const rect = previewWrap.getBoundingClientRect();
  zoomAt(rect.left + rect.width / 2, rect.top + rect.height / 2, 1 / 1.2);
  renderMarkers();
});

resetViewButton.addEventListener("click", () => {
  resetView();
  renderMarkers();
});

window.addEventListener("resize", () => {
  applyViewTransform();
  renderMarkers();
});
window.addEventListener("resize", renderPreviewOverlay);
resetChart();

runButton.addEventListener("click", async () => {
  setError("");
  if (!state.preview) {
    setError("Carica prima una preview.");
    return;
  }
  if (state.selections.length < 2) {
    setError("Seleziona almeno 1 target e 1 comparatore.");
    return;
  }
  const [target, ...comparators] = state.selections;
  try {
    setStatus("sto calcolando la fotometria e la curva di luce...");
    const result = await postJson("/agata/lightcurve/api/run", {
      folder: folderInput.value.trim(),
      config: configPayload(),
      target_coordinates: targetCoordinatesPayload(),
      target,
      comparators,
    });
    state.lastRunResult = result;
    warningBox.textContent = result.warnings.length ? result.warnings.join("\n") : "Nessun warning.";
    resultsBox.innerHTML = [
      `<div><strong>Frame di riferimento:</strong> ${result.reference_frame.frame_path}</div>`,
      `<div><strong>Numero FITS:</strong> ${result.reference_frame.fits_count}</div>`,
      `<div><strong>Comparatori effettivi:</strong> ${result.selection.effective_comparators_count}</div>`,
      `<div><strong>Punti curva:</strong> ${result.series.jd.length}</div>`,
      `<div><strong>RA target:</strong> ${result.reference_frame.target_ra_deg.toFixed(6)}</div>`,
      `<div><strong>DEC target:</strong> ${result.reference_frame.target_dec_deg.toFixed(6)}</div>`,
      `<div><strong>Sorgente coordinate:</strong> ${result.reference_frame.target_coordinate_source}</div>`,
    ].join("");
    drawSeries(result.series);
    setStatus("fotometria completata.");
  } catch (error) {
    setError(error.message);
    setStatus("errore durante il calcolo fotometrico.");
  }
});

exportButton.addEventListener("click", async () => {
  setError("");
  if (!state.lastRunResult) {
    setError("Calcola prima una curva di luce da esportare.");
    return;
  }
  if (exportModeInput.value === "preview_rows") {
    const series = state.lastRunResult.series || {};
    const jd = series.jd || [];
    const raw = series.flux_normalized || [];
    const detrended = series.flux_detrended || [];
    const previewCount = Math.min(8, jd.length);
    const rows = [];
    for (let i = 0; i < previewCount; i += 1) {
      rows.push(
        `<div>riga ${i + 1}: jd=${Number(jd[i]).toFixed(6)} | raw=${Number(raw[i]).toFixed(6)} | detrended=${Number(detrended[i]).toFixed(6)}</div>`,
      );
    }
    resultsBox.innerHTML += [
      `<div><strong>Anteprima curva:</strong> ${previewCount} righe</div>`,
      ...rows,
    ].join("");
    setStatus("anteprima righe curva completata.");
    return;
  }
  try {
    setStatus("sto esportando i risultati...");
    const exportResult = await postJson("/agata/lightcurve/api/export", {
      folder: folderInput.value.trim(),
      result: state.lastRunResult,
    });
    resultsBox.innerHTML += [
      `<div><strong>Export JSON:</strong> ${exportResult.export.files.json}</div>`,
      `<div><strong>Export CSV:</strong> ${exportResult.export.files.csv}</div>`,
    ].join("");
    setStatus("export completato.");
  } catch (error) {
    setError(error.message);
    setStatus("errore durante l'export.");
  }
});

targetModeInput.addEventListener("change", () => {
  if (targetModeInput.value === "manual") {
    if (state.selections.length === 1) {
      state.selections = [];
      state.evaluation = null;
      renderSelection();
      renderMarkers();
    }
    setStatus("modalità target manuale attiva.");
    return;
  }
  setStatus("modalità target automatico da RA/Dec attiva.");
});

curveViewModeInput.addEventListener("change", () => {
  if (state.lastSeries) {
    drawSeries(state.lastSeries);
  } else {
    resetChart();
  }
});
