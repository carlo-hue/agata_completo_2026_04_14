(function () {
    const appRoot = document.getElementById("tpfApp");
    console.log("DEBUG: appRoot element found?", !!appRoot);
    if (appRoot) console.log("DEBUG: appRoot.dataset.mastLocalSectorsUrl =", appRoot.dataset.mastLocalSectorsUrl);

    const gaiaSourceIdInput = document.getElementById("gaiaSourceIdInput");
    const saveButton = document.getElementById("saveButton");
    const promoteButton = document.getElementById("promoteButton");
    const gaiaOverlayToggleButton = document.getElementById("gaiaOverlayToggleButton");
    const gaiaSizeToggleButton = document.getElementById("gaiaSizeToggleButton");
    const gaiaSizeMaxMagInput = document.getElementById("gaiaSizeMaxMagInput");
    const fixedScaleToggleButton = document.getElementById("fixedScaleToggleButton");
    const pixelInfoToggleButton = document.getElementById("pixelInfoToggleButton");
    const targetModeButton = document.getElementById("targetModeButton");
    const backgroundModeButton = document.getElementById("backgroundModeButton");
    const recalcButton = document.getElementById("recalcButton");
    const loadVisibleFramesButton = document.getElementById("loadVisibleFramesButton");
    const findMastSectorsButton = document.getElementById("findMastSectorsButton");
    const mastCutoutSizeInput = document.getElementById("mastCutoutSizeInput");
    const mastSectorsBox = document.getElementById("mastSectorsBox");
    const sessionRestoreBox = document.getElementById("sessionRestoreBox");
    const frameSlider = document.getElementById("frameSlider");
    const frameIndexLabel = document.getElementById("frameIndexLabel");
    const frameTimeLabel = document.getElementById("frameTimeLabel");
    const frameInfo = document.getElementById("frameInfo");
    const loadFramesInfo = document.getElementById("loadFramesInfo");
    const statusBox = document.getElementById("statusBox");
    const errorBox = document.getElementById("errorBox");
    const output = document.getElementById("output");
    const returnPayloadBox = document.getElementById("returnPayloadBox");
    const sessionChoiceDialog = document.getElementById("sessionChoiceDialog");
    const sessionChoiceMessage = document.getElementById("sessionChoiceMessage");
    const sessionChoiceUpdateButton = document.getElementById("sessionChoiceUpdateButton");
    const sessionChoiceNewButton = document.getElementById("sessionChoiceNewButton");
    const sessionChoiceCancelButton = document.getElementById("sessionChoiceCancelButton");
    const targetInfo = document.getElementById("targetInfo");
    const tpfInfo = document.getElementById("tpfInfo");
    const tpfHeaderMeta = document.getElementById("tpfHeaderMeta");
    const overlayInfo = document.getElementById("overlayInfo");
    const gaiaStarsTableBox = document.getElementById("gaiaStarsTableBox");
    const tpfDetailsInfo = document.getElementById("tpfDetailsInfo");
    const overlayDetailsInfo = document.getElementById("overlayDetailsInfo");
    const lightcurveDetailsInfo = document.getElementById("lightcurveDetailsInfo");
    const editInfo = document.getElementById("editInfo");
    const maskInfo = document.getElementById("maskInfo");
    const lightcurveInfo = document.getElementById("lightcurveInfo");
    const lightcurveSeriesToggleButton = document.getElementById("lightcurveSeriesToggleButton");
    const lightcurveDisplayToggleButton = document.getElementById("lightcurveDisplayToggleButton");
    const lightcurveResetZoomButton = document.getElementById("lightcurveResetZoomButton");
    const tpfPlot = document.getElementById("tpfPlot");
    const lightcurvePlot = document.getElementById("lightcurvePlot");

    let lastRunResult = null;
    let targetMask = [];
    let backgroundMask = [];
    let committedTargetMask = [];
    let committedBackgroundMask = [];
    let editMode = "target";
    let editingEnabled = false;
    let gaiaOverlayEnabled = true;
    let gaiaSizeByMagnitudeEnabled = false;
    let fixedColorScaleEnabled = false;
    let pixelInfoEnabled = false;
    let fixedColorScaleRange = null;
    let lightcurveSeriesMode = "flux";
    let lightcurveDisplayMode = "lines";
    let currentFrameIndex = 0;
    let tpfFrames = [];
    let tpfFrameTimes = [];
    let lightcurveFrameIndices = [];
    let loadedFrameStartIndex = null;
    let loadedFrameEndIndex = null;
    let lastMastSectorsResult = null;
    let mastHasRemoteResults = false;
    let activeRestoredSessionId = null;
    let gaiaStarsSort = { key: "dist_arcsec", direction: "asc" };

    if (
        !appRoot || !gaiaSourceIdInput || !saveButton || !promoteButton
        || !gaiaOverlayToggleButton || !gaiaSizeToggleButton || !gaiaSizeMaxMagInput || !fixedScaleToggleButton || !pixelInfoToggleButton || !targetModeButton || !backgroundModeButton || !recalcButton || !loadVisibleFramesButton
        || !frameSlider || !frameIndexLabel || !frameTimeLabel || !frameInfo || !loadFramesInfo
        || !statusBox || !errorBox || !output || !returnPayloadBox
        || !sessionChoiceDialog || !sessionChoiceMessage || !sessionChoiceUpdateButton || !sessionChoiceNewButton || !sessionChoiceCancelButton
        || !targetInfo
        || !tpfInfo || !tpfHeaderMeta || !overlayInfo || !gaiaStarsTableBox || !tpfDetailsInfo || !overlayDetailsInfo || !lightcurveDetailsInfo
        || !editInfo || !maskInfo || !lightcurveInfo || !tpfPlot || !lightcurvePlot || !sessionRestoreBox
    ) {
        return;
    }

    const LIGHTCURVE_SERIES_MODES = ["flux", "mag_ref"];

    const endpointUrls = {
        runUrl: appRoot.dataset.runUrl || "/tpf/api/run",
        framesUrl: appRoot.dataset.framesUrl || "/tpf/api/frames",
        mastLocalSectorsUrl: appRoot.dataset.mastLocalSectorsUrl || "/tpf/api/mast/local-sectors",
        mastSectorsUrl: appRoot.dataset.mastSectorsUrl || "/tpf/api/mast/sectors",
        mastDownloadUrl: appRoot.dataset.mastDownloadUrl || "/tpf/api/mast/download",
        sessionsUrl: appRoot.dataset.sessionsUrl || "/tpf/api/sessions",
        restoreSessionUrl: appRoot.dataset.restoreSessionUrl || "/tpf/api/restore-session",
        deleteSessionUrl: appRoot.dataset.deleteSessionUrl || "/tpf/api/delete-session",
        saveUrl: appRoot.dataset.saveUrl || "/tpf/api/save",
        promoteUrl: appRoot.dataset.promoteUrl || "/tpf/api/promote",
    };
    console.log("DEBUG: endpointUrls.mastLocalSectorsUrl =", endpointUrls.mastLocalSectorsUrl);

    const pageContext = {
        mode: appRoot.dataset.mode || "standalone",
        gaia_source_id: appRoot.dataset.gaiaSourceId || "",
        sector: appRoot.dataset.sector || "",
        source_context: appRoot.dataset.sourceContext || null,
        default_cutout_size: appRoot.dataset.defaultCutoutSize || "10",
        overview_mode: appRoot.dataset.overviewMode === "1",
    };

    function setStatus(message, tone) {
        statusBox.textContent = message || "-";
        statusBox.className = `status-box ${tone || "status-neutral"}`;
    }

    function setSaveStatus(message, tone) {
        setStatus(message, tone);
    }

    function setError(message) {
        if (!message) {
            errorBox.textContent = "";
            errorBox.classList.add("hidden");
            return;
        }
        errorBox.textContent = message;
        errorBox.classList.remove("hidden");
    }

    async function parseApiJsonResponse(response, fallbackMessage) {
        const contentType = String(response && response.headers ? (response.headers.get("content-type") || "") : "").toLowerCase();
        if (contentType.includes("application/json")) {
            return response.json().catch(() => ({
                status: "error",
                ok: false,
                message: fallbackMessage || "Risposta JSON non valida",
            }));
        }

        let responseText = "";
        try {
            responseText = await response.text();
        } catch (_) {
            responseText = "";
        }

        if (response.status === 401) {
            return {
                status: "error",
                ok: false,
                message: "Sessione scaduta o autenticazione mancante. Ricarica AGATA e rifai login.",
            };
        }

        if (response.status === 403) {
            return {
                status: "error",
                ok: false,
                message: "Accesso non autorizzato a questa operazione.",
            };
        }

        return {
            status: "error",
            ok: false,
            message: fallbackMessage || `Risposta non JSON ricevuta dal server (HTTP ${response.status}).`,
            raw_response: responseText ? responseText.slice(0, 300) : "",
        };
    }

    function setButtonBusy(button, busyText, isBusy) {
        if (!button) {
            return;
        }
        if (!button.dataset.originalText) {
            button.dataset.originalText = button.textContent;
        }
        button.textContent = isBusy ? busyText : button.dataset.originalText;
        button.disabled = isBusy;
        button.classList.toggle("is-busy", !!isBusy);
    }

    function setMastStatus(message, tone) {
        const toneMap = { success: "status-success", warning: "status-neutral", error: "status-error" };
        setStatus(message, toneMap[tone] || "status-neutral");
    }

    function chooseSessionSaveMode(sessionId) {
        return new Promise((resolve) => {
            sessionChoiceMessage.textContent = `Sessione ${sessionId} caricata. Vuoi aggiornare la sessione esistente o crearne una nuova?`;
            sessionChoiceDialog.classList.remove("hidden");
            sessionChoiceDialog.setAttribute("aria-hidden", "false");

            function cleanup(choice) {
                sessionChoiceDialog.classList.add("hidden");
                sessionChoiceDialog.setAttribute("aria-hidden", "true");
                sessionChoiceUpdateButton.removeEventListener("click", onUpdate);
                sessionChoiceNewButton.removeEventListener("click", onNew);
                sessionChoiceCancelButton.removeEventListener("click", onCancel);
                resolve(choice);
            }

            function onUpdate() {
                cleanup("update");
            }

            function onNew() {
                cleanup("new");
            }

            function onCancel() {
                cleanup("cancel");
            }

            sessionChoiceUpdateButton.addEventListener("click", onUpdate);
            sessionChoiceNewButton.addEventListener("click", onNew);
            sessionChoiceCancelButton.addEventListener("click", onCancel);
        });
    }

    function escapeHtml(text) {
        return String(text)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/\"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function numericOrNull(value) {
        if (value === null || value === undefined || value === "") {
            return null;
        }
        const numeric = Number(value);
        return Number.isFinite(numeric) ? numeric : null;
    }

    function firstNumericValue(values) {
        for (const value of values) {
            const numeric = numericOrNull(value);
            if (numeric !== null) {
                return numeric;
            }
        }
        return null;
    }

    function formatDecimal(value, digits) {
        const numeric = numericOrNull(value);
        return numeric === null ? "-" : numeric.toFixed(digits);
    }

    function formatFluxRatio(value) {
        const numeric = numericOrNull(value);
        if (numeric === null) {
            return "-";
        }
        if (numeric >= 0.1) {
            return numeric.toFixed(3);
        }
        if (numeric >= 0.001) {
            return numeric.toFixed(5);
        }
        return numeric.toExponential(2);
    }

    function getCurrentMastCutoutSize() {
        const fallback = String(pageContext.default_cutout_size || "10").trim() || "10";
        const raw = mastCutoutSizeInput ? String(mastCutoutSizeInput.value || "").trim() : fallback;
        if (!raw) {
            return fallback;
        }
        const numeric = parseInt(raw, 10);
        return Number.isFinite(numeric) && numeric > 0 ? String(numeric) : fallback;
    }

    function cloneMask(maskMatrix) {
        if (!Array.isArray(maskMatrix)) {
            return [];
        }
        return maskMatrix.map((row) => Array.isArray(row) ? row.map((value) => !!value) : []);
    }

    function masksEqual(leftMask, rightMask) {
        if (!Array.isArray(leftMask) || !Array.isArray(rightMask) || leftMask.length !== rightMask.length) {
            return false;
        }
        for (let row = 0; row < leftMask.length; row += 1) {
            if (!Array.isArray(leftMask[row]) || !Array.isArray(rightMask[row]) || leftMask[row].length !== rightMask[row].length) {
                return false;
            }
            for (let col = 0; col < leftMask[row].length; col += 1) {
                if (!!leftMask[row][col] !== !!rightMask[row][col]) {
                    return false;
                }
            }
        }
        return true;
    }

    function masksNeedRecalc() {
        if (!editingEnabled) {
            return false;
        }
        return !masksEqual(targetMask, committedTargetMask) || !masksEqual(backgroundMask, committedBackgroundMask);
    }

    function maskSummary(currentTargetMask, currentBackgroundMask) {
        let targetPixels = 0;
        let backgroundPixels = 0;
        for (let row = 0; row < currentTargetMask.length; row += 1) {
            for (let col = 0; col < currentTargetMask[row].length; col += 1) {
                if (currentTargetMask[row][col]) targetPixels += 1;
                if (currentBackgroundMask[row] && currentBackgroundMask[row][col]) backgroundPixels += 1;
            }
        }
        return { targetPixels, backgroundPixels };
    }

    function buildCurrentMasksPayload(mode, message) {
        const summary = maskSummary(targetMask, backgroundMask);
        return {
            available: editingEnabled,
            mode: mode || "manual-ui",
            message: message || 'Premi "Ricalcola light curve" per aggiornare la curva.',
            target: cloneMask(targetMask),
            background: cloneMask(backgroundMask),
            summary: {
                target_pixels: summary.targetPixels,
                background_pixels: summary.backgroundPixels,
            },
        };
    }

    function clearPlots() {
        Plotly.purge(tpfPlot);
        Plotly.purge(lightcurvePlot);
        tpfPlot.__maskClickBound = false;
        lightcurvePlot.__lightcurveClickBound = false;
        tpfPlot.innerHTML = "";
        lightcurvePlot.innerHTML = "";
    }

    function updateFixedScaleToggleButton() {
        if (!fixedScaleToggleButton) {
            return;
        }
        fixedScaleToggleButton.textContent = fixedColorScaleEnabled ? "scala.fissa OFF" : "scala.fissa ON";
        fixedScaleToggleButton.title = fixedColorScaleEnabled
            ? "Clicca per disattivare la scala fissa."
            : "Clicca per rendere fissa la scala colore.";
    }

    function updateLightcurveDisplayToggleButton() {
        if (!lightcurveDisplayToggleButton) {
            return;
        }
        lightcurveDisplayToggleButton.textContent = lightcurveDisplayMode === "markers" ? "vis.linea" : "vis.punti";
        lightcurveDisplayToggleButton.title = lightcurveDisplayMode === "markers"
            ? "Passa alla visualizzazione come linea continua."
            : "Passa alla visualizzazione come soli punti.";
    }

    function getAvailableLightcurveSeriesModes(lightcurve) {
        const available = ["flux"];
        const anchoringApplied = !!(lightcurve && lightcurve.metadata && lightcurve.metadata.anchoring_applied);
        if (
            anchoringApplied
            && lightcurve
            && Array.isArray(lightcurve.mag_tess_anchored)
            && lightcurve.mag_tess_anchored.some((value) => value !== null && Number.isFinite(Number(value)))
        ) {
            available.push("mag_ref");
        }
        return available;
    }

    function getLightcurveSeriesConfig(lightcurve) {
        const availableModes = getAvailableLightcurveSeriesModes(lightcurve);
        if (!availableModes.includes(lightcurveSeriesMode)) {
            lightcurveSeriesMode = availableModes[0] || "flux";
        }

        if (lightcurveSeriesMode === "mag_ref") {
            const values = Array.isArray(lightcurve && lightcurve.mag_tess_anchored) ? lightcurve.mag_tess_anchored : [];
            const referenceBand = lightcurve && lightcurve.metadata && lightcurve.metadata.reference_mag_band
                ? String(lightcurve.metadata.reference_mag_band)
                : "ref";
            const compactReferenceBand = referenceBand === "Gaia G" ? "Gaia" : referenceBand;
            return {
                mode: "mag_ref",
                values,
                traceName: `Mag ${referenceBand} anchored`,
                title: `Mag Light Curve (${compactReferenceBand})`,
                yAxisTitle: `Mag ${referenceBand} anchored`,
                reverseYAxis: true,
                hoverLabel: "mag",
            };
        }
        const values = Array.isArray(lightcurve && lightcurve.corrected_flux) ? lightcurve.corrected_flux : (Array.isArray(lightcurve && lightcurve.flux) ? lightcurve.flux : []);
        return {
            mode: "flux",
            values,
            traceName: "Corrected Flux",
            title: "Flux Light Curve",
            yAxisTitle: "Corrected Flux",
            reverseYAxis: false,
            hoverLabel: "flux",
        };
    }

    function getCurrentAxisRange(axisName) {
        if (!lightcurvePlot || !lightcurvePlot.layout || !lightcurvePlot.layout[axisName]) {
            return null;
        }
        const axis = lightcurvePlot.layout[axisName];
        if (!Array.isArray(axis.range) || axis.range.length !== 2) {
            return null;
        }
        const start = Number(axis.range[0]);
        const end = Number(axis.range[1]);
        if (!Number.isFinite(start) || !Number.isFinite(end)) {
            return null;
        }
        return [start, end];
    }

    function updateLightcurveSeriesToggleButton(lightcurve) {
        if (!lightcurveSeriesToggleButton) {
            return;
        }
        const config = getLightcurveSeriesConfig(lightcurve || (lastRunResult ? lastRunResult.lightcurve : null));
        const referenceBand = lightcurve && lightcurve.metadata && lightcurve.metadata.reference_mag_band
            ? String(lightcurve.metadata.reference_mag_band)
            : "ref";
        const availableModes = getAvailableLightcurveSeriesModes(lightcurve || (lastRunResult ? lastRunResult.lightcurve : null));
        const currentIndex = availableModes.indexOf(config.mode);
        const nextMode = currentIndex >= 0 ? availableModes[(currentIndex + 1) % availableModes.length] : "flux";
        const labels = {
            flux: "vis.flusso",
            mag_ref: "vis.mag",
        };
        const nextLabel = labels[nextMode] || "vis.flusso";
        const descriptiveLabel = nextMode === "mag_ref"
            ? (referenceBand === "Gaia G" ? "magnitudine Gaia" : `magnitudine ${referenceBand}`)
            : "flusso";
        lightcurveSeriesToggleButton.textContent = nextLabel;
        lightcurveSeriesToggleButton.title = `Passa alla serie ${descriptiveLabel}`;
    }

    function recomputeFixedColorScaleRange() {
        if (!fixedColorScaleEnabled || !Array.isArray(tpfFrames) || !tpfFrames.length) {
            fixedColorScaleRange = null;
            return;
        }

        const allValues = [];
        for (const frame of tpfFrames) {
            if (!Array.isArray(frame)) {
                continue;
            }
            for (const row of frame) {
                if (!Array.isArray(row)) {
                    continue;
                }
                for (const value of row) {
                    const numeric = Number(value);
                    if (!Number.isFinite(numeric)) {
                        continue;
                    }
                    allValues.push(numeric);
                }
            }
        }

        if (!allValues.length) {
            fixedColorScaleRange = null;
            return;
        }

        allValues.sort((left, right) => left - right);
        const percentile = (fraction) => {
            const clamped = Math.min(1, Math.max(0, fraction));
            const index = Math.round((allValues.length - 1) * clamped);
            return allValues[index];
        };

        let minValue = percentile(0.02);
        let maxValue = percentile(0.90);

        if (!Number.isFinite(minValue) || !Number.isFinite(maxValue) || minValue >= maxValue) {
            minValue = allValues[0];
            maxValue = allValues[allValues.length - 1];
        }

        if (minValue === maxValue) {
            const padding = Math.abs(minValue || 1) * 0.01;
            minValue -= padding;
            maxValue += padding;
        }

        fixedColorScaleRange = { zmin: minValue, zmax: maxValue };
    }

    function resetFrameState() {
        currentFrameIndex = 0;
        tpfFrames = [];
        tpfFrameTimes = [];
        lightcurveFrameIndices = [];
        fixedColorScaleRange = null;
        loadedFrameStartIndex = null;
        loadedFrameEndIndex = null;
        frameSlider.min = "0";
        frameSlider.max = "0";
        frameSlider.step = "1";
        frameSlider.value = "0";
        frameSlider.disabled = true;
        frameIndexLabel.textContent = "Frame: - / -";
        frameTimeLabel.textContent = "Time: -";
        frameInfo.textContent = "Frame non ancora caricati. Usa il pulsante dedicato dopo aver scelto la porzione di light curve.";
        loadVisibleFramesButton.disabled = true;
        loadFramesInfo.textContent = "Fai zoom sulla light curve e usa questo pulsante per caricare solo i cadence visibili.";
    }

    function resetSections() {
        renderTarget(null);
        tpfHeaderMeta.textContent = "gaia_source_id=- | sector=- | ra=- | dec=- | gmag=-";
        tpfInfo.textContent = "TPF non ancora richiesto.";
        overlayInfo.textContent = "Overlay target/Gaia non ancora disponibile.";
        tpfDetailsInfo.textContent = "TPF non ancora richiesto.";
        overlayDetailsInfo.textContent = "Overlay target/Gaia non ancora disponibile.";
        lightcurveDetailsInfo.textContent = "Light curve non ancora richiesta.";
        renderGaiaStarsTable(null);
        maskInfo.textContent = "Selezione automatica foreground/background non ancora disponibile.";
        maskInfo.classList.remove("warning");
        lightcurveInfo.textContent = "Light curve non ancora richiesta.";
        updateLightcurveSeriesToggleButton(null);
        editInfo.textContent = "Editing pixel disponibile solo con TPF reale.";
        resetFrameState();
    }

    function renderMastSectors(data) {
        if (!mastSectorsBox) {
            return;
        }

        if (!data || !Array.isArray(data.sectors) || !data.sectors.length) {
            const gaiaId = String(gaiaSourceIdInput.value || "").trim();
            if (gaiaId && !mastHasRemoteResults) {
                mastSectorsBox.className = "mast-sectors-box";
                mastSectorsBox.innerHTML = `
                    <div class="mast-sector-footer">
                        <span>Nessun TPF locale trovato. Puoi verificare se esistono settori disponibili su MAST.</span>
                        <button type="button" class="button-secondary" data-mast-check-remote="1">Verifica altri TPF</button>
                    </div>
                `;
            } else {
                mastSectorsBox.className = "mast-sectors-box empty-state";
                mastSectorsBox.innerHTML = "<div>Nessun settore TESS disponibile.</div>";
            }
            return;
        }

        const orderedSectors = data.sectors.slice().sort((left, right) => {
            const leftDownloaded = !!(left && left.downloaded);
            const rightDownloaded = !!(right && right.downloaded);
            if (leftDownloaded !== rightDownloaded) {
                return leftDownloaded ? -1 : 1;
            }
            return Number(left && left.sector) - Number(right && right.sector);
        });

        const tbodyHtml = orderedSectors.map((entry) => {
            const sector = entry && entry.sector !== undefined ? entry.sector : "-";
            const downloaded = !!(entry && entry.downloaded);
            const statusText = downloaded ? "Sul server AGATA" : "Non scaricato";
            const filename = entry && entry.filename ? entry.filename : "-";
            const buttonLabel = downloaded ? "Riusa" : "Scarica TPF";
            const actionAttr = downloaded ? "data-mast-reuse" : "data-mast-download";
            return `
                <tr class="${downloaded ? "is-downloaded" : ""}">
                    <td class="is-compact">${escapeHtml(sector)}</td>
                    <td class="is-compact">${escapeHtml(statusText)}</td>
                    <td class="sector-file">${escapeHtml(filename)}</td>
                    <td class="is-compact">
                        <button
                            type="button"
                            class="button-secondary"
                            ${actionAttr}="1"
                            data-sector="${escapeHtml(sector)}"
                        >${escapeHtml(buttonLabel)}</button>
                    </td>
                </tr>
            `;
        }).join("");

        const tableHtml = `
            <table class="sector-table">
                <thead>
                    <tr>
                        <th>Settore</th>
                        <th>Stato</th>
                        <th>File</th>
                        <th></th>
                    </tr>
                </thead>
                <tbody>${tbodyHtml}</tbody>
            </table>
        `;

        const footerHtml = mastHasRemoteResults
            ? ""
            : `<div class="mast-sector-footer">
                <span>Verifica se esistono altri settori TESS non ancora scaricati per questa sorgente.</span>
                <button type="button" class="button-secondary" data-mast-check-remote="1">Verifica altri TPF</button>
               </div>`;

        mastSectorsBox.className = "mast-sectors-box";
        mastSectorsBox.innerHTML = tableHtml + footerHtml;
    }

    function renderSavedSessions(data) {
        if (!sessionRestoreBox) {
            return;
        }

        if (!data || !Array.isArray(data.sessions) || !data.sessions.length) {
            const gaiaId = String(gaiaSourceIdInput.value || "").trim();
            sessionRestoreBox.className = "mast-sectors-box empty-state";
            sessionRestoreBox.innerHTML = gaiaId
                ? "<div>Nessuna sessione tecnica salvata per questa sorgente.</div>"
                : "<div>Inserisci un Gaia source id per vedere eventuali sessioni tecniche salvate.</div>";
            return;
        }

        const rowsHtml = data.sessions.map((entry) => {
            const sessionId = entry && entry.session_id !== undefined ? entry.session_id : "-";
            const sector = entry && entry.sector !== undefined ? entry.sector : "-";
            const maskOrigin = entry && entry.mask_origin ? entry.mask_origin : "-";
            const savedAt = entry && entry.saved_at ? entry.saved_at : "-";
            const promoted = entry && entry.is_promoted ? ` | promossa (${entry.promoted_points || 0} punti)` : "";
            const filename = entry && entry.tpf_filename ? entry.tpf_filename : "TPF non specificato";
            return `
                <div class="mast-sector-row">
                    <div class="mast-sector-meta">
                        <div class="mast-sector-inline">Sessione ${escapeHtml(sessionId)} | sector ${escapeHtml(sector)} | ${escapeHtml(maskOrigin)} | ${escapeHtml(filename)}${escapeHtml(promoted)}</div>
                        <div class="mast-sector-subtitle">Salvata il ${escapeHtml(savedAt)}</div>
                    </div>
                    <div class="mast-sector-actions">
                        <button
                            type="button"
                            class="button-secondary"
                            data-restore-session="${escapeHtml(sessionId)}"
                        >Riprendi sessione</button>
                        <button
                            type="button"
                            class="button-secondary"
                            data-delete-session="${escapeHtml(sessionId)}"
                        >Elimina</button>
                    </div>
                </div>
            `;
        }).join("");

        sessionRestoreBox.className = "mast-sectors-box";
        sessionRestoreBox.innerHTML = rowsHtml;
    }

    function renderTarget(target) {
        if (!target) {
            targetInfo.className = "info-grid empty-state";
            targetInfo.textContent = "Nessun target caricato.";
            return;
        }
        targetInfo.className = "info-grid";
        targetInfo.innerHTML = `
            <div><span class="k">Gaia source_id</span><span class="v mono">${escapeHtml(target.gaia_source_id || "-")}</span></div>
            <div><span class="k">Catalogo</span><span class="v">${escapeHtml(target.catalog || "Gaia DR3")}</span></div>
            <div><span class="k">RA [deg]</span><span class="v mono">${escapeHtml(target.ra_deg ?? "-")}</span></div>
            <div><span class="k">Dec [deg]</span><span class="v mono">${escapeHtml(target.dec_deg ?? "-")}</span></div>
            <div><span class="k">Gmag</span><span class="v">${escapeHtml(target.gmag ?? "-")}</span></div>
        `;
    }

    function getFrameCount() {
        return Array.isArray(tpfFrames) ? tpfFrames.length : 0;
    }

    function clampFrameIndex(index) {
        const numeric = Number.isFinite(index) ? index : parseInt(index, 10);
        if (!Number.isFinite(numeric)) {
            return loadedFrameStartIndex !== null ? loadedFrameStartIndex : 0;
        }
        if (loadedFrameStartIndex !== null && loadedFrameEndIndex !== null) {
            return Math.min(loadedFrameEndIndex, Math.max(loadedFrameStartIndex, Math.round(numeric)));
        }
        const count = getFrameCount();
        if (count <= 0) {
            return 0;
        }
        return Math.min(count - 1, Math.max(0, Math.round(numeric)));
    }

    function getCurrentFrameGrid(tpf) {
        if (tpf && tpf.frames && tpf.frames.available && getFrameCount() > 0) {
            const relativeIndex = loadedFrameStartIndex === null ? clampFrameIndex(currentFrameIndex) : clampFrameIndex(currentFrameIndex) - loadedFrameStartIndex;
            return tpfFrames[relativeIndex];
        }
        return tpf && Array.isArray(tpf.flux_grid) ? tpf.flux_grid : null;
    }

    function getLoadedFrameBounds() {
        if (loadedFrameStartIndex === null || loadedFrameEndIndex === null) {
            return null;
        }
        return { start: loadedFrameStartIndex, end: loadedFrameEndIndex };
    }

    function getVisibleLightcurveFrameRange() {
        if (!lastRunResult || !lastRunResult.lightcurve || !Array.isArray(lastRunResult.lightcurve.time) || !lastRunResult.lightcurve.time.length) {
            return null;
        }

        const times = lastRunResult.lightcurve.time;
        const mappedFrameIndices = Array.isArray(lightcurveFrameIndices) && lightcurveFrameIndices.length
            ? lightcurveFrameIndices
            : times.map((_, index) => index);

        let minTime = times[0];
        let maxTime = times[times.length - 1];
        const currentRange = lightcurvePlot && lightcurvePlot.layout && lightcurvePlot.layout.xaxis ? lightcurvePlot.layout.xaxis.range : null;
        if (Array.isArray(currentRange) && currentRange.length === 2 && Number.isFinite(Number(currentRange[0])) && Number.isFinite(Number(currentRange[1]))) {
            minTime = Math.min(Number(currentRange[0]), Number(currentRange[1]));
            maxTime = Math.max(Number(currentRange[0]), Number(currentRange[1]));
        }

        const visibleFrameIndices = [];
        for (let index = 0; index < times.length; index += 1) {
            const timeValue = Number(times[index]);
            if (!Number.isFinite(timeValue)) {
                continue;
            }
            if (timeValue >= minTime && timeValue <= maxTime) {
                visibleFrameIndices.push(mappedFrameIndices[index]);
            }
        }

        if (!visibleFrameIndices.length) {
            return null;
        }
        return {
            frameStart: Math.min(...visibleFrameIndices),
            frameEnd: Math.max(...visibleFrameIndices),
        };
    }

    function findLightcurvePointIndexForFrame(frameIndex) {
        if (Array.isArray(lightcurveFrameIndices) && lightcurveFrameIndices.length) {
            const directIndex = lightcurveFrameIndices.indexOf(frameIndex);
            if (directIndex >= 0) {
                return directIndex;
            }
            return -1;
        }

        if (lastRunResult && lastRunResult.lightcurve && Array.isArray(lastRunResult.lightcurve.time)) {
            return frameIndex < lastRunResult.lightcurve.time.length ? frameIndex : -1;
        }
        return -1;
    }

    function updateFrameControls(tpf) {
        const frames = tpf && tpf.frames ? tpf.frames : null;
        const canLoadFrames = !!(tpf && tpf.mode === "real" && frames && frames.available);
        loadVisibleFramesButton.disabled = !canLoadFrames;
        if (!canLoadFrames) {
            loadFramesInfo.textContent = "Caricamento frame disponibile solo con TPF reale.";
        } else if (frames.loaded) {
            loadFramesInfo.textContent = "Frame caricati per la finestra visibile della light curve. Puoi fare nuovo zoom e ricaricare se ti serve un altro intervallo.";
        } else {
            loadFramesInfo.textContent = "Fai zoom sulla light curve e usa questo pulsante per caricare solo i cadence visibili.";
        }

        if (!frames || !frames.available || !frames.loaded || getFrameCount() === 0) {
            frameSlider.disabled = true;
            frameIndexLabel.textContent = "Frame: - / -";
            frameTimeLabel.textContent = "Time: -";
            frameInfo.textContent = (frames && frames.message) || "Navigazione frame disponibile solo con TPF reale.";
            return;
        }

        const safeIndex = clampFrameIndex(currentFrameIndex);
        currentFrameIndex = safeIndex;
        const totalCount = Number.isFinite(frames.count) ? frames.count : getFrameCount();
        const windowBounds = getLoadedFrameBounds();
        const currentPosition = safeIndex + 1;
        const currentTime = Array.isArray(tpfFrameTimes) && tpfFrameTimes[safeIndex] !== undefined
            ? tpfFrameTimes[safeIndex - (loadedFrameStartIndex || 0)]
            : "-";

        frameSlider.disabled = false;
        frameSlider.min = String(windowBounds ? windowBounds.start : 0);
        frameSlider.max = String(windowBounds ? windowBounds.end : Math.max(0, totalCount - 1));
        frameSlider.step = "1";
        frameSlider.value = String(safeIndex);
        frameIndexLabel.textContent = `Frame: ${currentPosition} / ${totalCount}`;
        frameTimeLabel.textContent = `Time: ${currentTime}`;
        frameInfo.textContent = `Frame reale corrente: ${currentPosition}/${totalCount} | Time=${currentTime} | finestra caricata=${windowBounds ? `${windowBounds.start + 1}-${windowBounds.end + 1}` : "-"} | ${frames.message || "Clicca un punto della light curve per vedere il frame corrispondente."}`;
    }
    function handleTpfPlotClick(eventData) {
        if (!lastRunResult || !lastRunResult.tpf || lastRunResult.tpf.mode !== "real") {
            return;
        }
        const point = eventData && eventData.points && eventData.points[0] ? eventData.points[0] : null;
        if (!point || typeof point.x !== "number" || typeof point.y !== "number") {
            return;
        }
        if (point.data && point.data.type && point.data.type !== "heatmap") {
            return;
        }

        const row = Math.round(point.y);
        const col = Math.round(point.x);
        if (pixelInfoEnabled) {
            const currentTpf = buildCurrentTpfView();
            const currentGrid = getCurrentFrameGrid(currentTpf);
            const fluxValue = Array.isArray(currentGrid) && Array.isArray(currentGrid[row]) ? Number(currentGrid[row][col]) : null;
            const pixelWorld = currentTpf && currentTpf.metadata ? currentTpf.metadata.pixel_world : null;
            const raDeg = pixelWorld && Array.isArray(pixelWorld.ra_deg) && Array.isArray(pixelWorld.ra_deg[row]) ? Number(pixelWorld.ra_deg[row][col]) : null;
            const decDeg = pixelWorld && Array.isArray(pixelWorld.dec_deg) && Array.isArray(pixelWorld.dec_deg[row]) ? Number(pixelWorld.dec_deg[row][col]) : null;
            editInfo.textContent = [
                `Info pixel: x=${col + 1}, y=${row + 1}`,
                Number.isFinite(fluxValue) ? `flux=${fluxValue.toFixed(3)}` : "flux=-",
                Number.isFinite(raDeg) ? `ra_ctr_pxl=${raDeg.toFixed(5)}` : "ra_ctr_pxl=-",
                Number.isFinite(decDeg) ? `dec_ctr_pxl=${decDeg.toFixed(5)}` : "dec_ctr_pxl=-",
            ].join(" | ");
            return;
        }
        if (!editingEnabled) {
            return;
        }
        if (!targetMask[row] || targetMask[row][col] === undefined || !backgroundMask[row] || backgroundMask[row][col] === undefined) {
            return;
        }

        if (editMode === "target") {
            const nextValue = !targetMask[row][col];
            targetMask[row][col] = nextValue;
            if (nextValue) {
                backgroundMask[row][col] = false;
            }
        } else {
            const nextValue = !backgroundMask[row][col];
            backgroundMask[row][col] = nextValue;
            if (nextValue) {
                targetMask[row][col] = false;
            }
        }

        renderCurrentTpfState();
        editInfo.textContent = `Modalita' editing attiva: ${editMode}. Clicca un pixel del TPF per modificarlo e poi premi "Ricalcola light curve".`;
    }

    function buildMaskShapes(maskMatrix, kind) {
        if (!Array.isArray(maskMatrix) || !maskMatrix.length) {
            return [];
        }

        const shapes = [];
        for (let row = 0; row < maskMatrix.length; row += 1) {
            for (let col = 0; col < maskMatrix[row].length; col += 1) {
                if (!maskMatrix[row][col]) {
                    continue;
                }

                const x0 = col - 0.5;
                const x1 = col + 0.5;
                const y0 = row - 0.5;
                const y1 = row + 0.5;

                if (kind === "target") {
                    shapes.push({
                        type: "rect",
                        xref: "x",
                        yref: "y",
                        x0,
                        x1,
                        y0,
                        y1,
                        line: {
                            color: "rgba(255, 0, 0, 0.98)",
                            width: 2.5,
                        },
                        fillcolor: "rgba(255, 0, 0, 0.10)",
                    });
                } else if (kind === "background") {
                    shapes.push({
                        type: "rect",
                        xref: "x",
                        yref: "y",
                        x0,
                        x1,
                        y0,
                        y1,
                        line: {
                            color: "rgba(255, 255, 255, 0.95)",
                            width: 1.4,
                        },
                        fillcolor: "rgba(255, 255, 255, 0.02)",
                    });
                }
            }
        }

        return shapes;
    }

    function getMagnitudeScaleBounds(overlay) {
        const allMagnitudes = [];
        const targetFallbackGmag = Number(lastRunResult && lastRunResult.target ? lastRunResult.target.gmag : null);
        if (overlay && overlay.target_position) {
            const targetGmag = Number.isFinite(Number(overlay.target_position.gmag))
                ? Number(overlay.target_position.gmag)
                : targetFallbackGmag;
            if (Number.isFinite(targetGmag)) {
                allMagnitudes.push(targetGmag);
            }
        }
        if (overlay && Array.isArray(overlay.gaia_sources)) {
            for (const item of overlay.gaia_sources) {
                const rawGmag = item && item.gmag;
                if (rawGmag === null || rawGmag === undefined || rawGmag === "") {
                    continue;
                }
                const gmag = Number(rawGmag);
                if (Number.isFinite(gmag)) {
                    allMagnitudes.push(gmag);
                }
            }
        }
        if (!allMagnitudes.length) {
            return null;
        }
        const brightMag = Math.min(...allMagnitudes);
        const faintFieldMag = Math.max(...allMagnitudes);
        return { brightMag, faintMag: faintFieldMag };
    }

    function syncGaiaMaxMagInput(overlay) {
        if (!gaiaSizeMaxMagInput || !overlay || !Array.isArray(overlay.gaia_sources) || !overlay.gaia_sources.length) {
            return;
        }
        const magnitudes = overlay.gaia_sources
            .map((item) => item && item.gmag)
            .filter((value) => value !== null && value !== undefined && value !== "")
            .map((value) => Number(value))
            .filter((value) => Number.isFinite(value));
        if (!magnitudes.length) {
            return;
        }
        if (String(gaiaSizeMaxMagInput.value || "").trim()) {
            return;
        }
        gaiaSizeMaxMagInput.value = Math.max(...magnitudes).toFixed(2);
    }

    function getMagnitudeScaledMarkerSize(gmag, bounds, fallbackSize, minSize, maxSize) {
        if (gmag === null || gmag === undefined || gmag === "") {
            return fallbackSize;
        }
        const numericGmag = Number(gmag);
        if (!Number.isFinite(numericGmag) || !bounds) {
            return fallbackSize;
        }
        const brightMag = Number(bounds.brightMag);
        const faintMag = Number(bounds.faintMag);
        if (!Number.isFinite(brightMag) || !Number.isFinite(faintMag) || faintMag <= brightMag) {
            return fallbackSize;
        }
        const normalized = (numericGmag - brightMag) / (faintMag - brightMag);
        const clamped = Math.max(0, Math.min(1, normalized));
        return maxSize - (clamped * (maxSize - minSize));
    }

    function getVisibleGaiaSources(overlay) {
        if (!overlay || !Array.isArray(overlay.gaia_sources) || !overlay.gaia_sources.length) {
            return [];
        }
        const maxVisibleMag = Number(gaiaSizeMaxMagInput.value);
        if (!Number.isFinite(maxVisibleMag)) {
            return overlay.gaia_sources.slice();
        }
        return overlay.gaia_sources.filter((item) => {
            const gmag = numericOrNull(item && item.gmag);
            return gmag === null || gmag <= maxVisibleMag;
        });
    }

    function buildTargetOverlayTrace(overlay) {
        if (!overlay || !overlay.target_position || overlay.target_position.x === undefined || overlay.target_position.y === undefined) {
            return null;
        }
        const sizeBounds = gaiaSizeByMagnitudeEnabled ? getMagnitudeScaleBounds(overlay) : null;
        const targetGmag = Number.isFinite(Number(overlay.target_position.gmag))
            ? Number(overlay.target_position.gmag)
            : Number(lastRunResult && lastRunResult.target ? lastRunResult.target.gmag : null);
        const fixedSize = 5;
        const targetSize = gaiaSizeByMagnitudeEnabled
            ? getMagnitudeScaledMarkerSize(targetGmag, sizeBounds, fixedSize, 3, 22)
            : fixedSize;
        const targetHoverText = formatGaiaOverlayHoverText({
            source_id: (lastRunResult && lastRunResult.target && lastRunResult.target.gaia_source_id) || "-",
            gmag: targetGmag,
            ra_deg: lastRunResult && lastRunResult.target ? lastRunResult.target.ra_deg : null,
            dec_deg: lastRunResult && lastRunResult.target ? lastRunResult.target.dec_deg : null,
            dist_arcsec: 0,
            variable_type: null,
            variable_catalogs: [],
        });
        return {
            x: [overlay.target_position.x],
            y: [overlay.target_position.y],
            type: "scatter",
            mode: "markers",
            name: "Target",
            marker: {
                symbol: "circle",
                size: targetSize,
                color: "rgba(250, 204, 21, 0.22)",
                line: {
                    color: "#ef4444",
                    width: 3,
                },
            },
            text: [targetHoverText],
            hovertemplate: "%{text}<br>x=%{x:.2f}<br>y=%{y:.2f}<extra></extra>",
        };
    }

    function formatGaiaOverlayHoverText(item) {
        const ra = Number(item && item.ra_deg);
        const dec = Number(item && item.dec_deg);
        const distArcsec = Number(item && item.dist_arcsec);
        const parts = [`source_id=${item.source_id}`, `Gmag=${item.gmag ?? "-"}`];
        if (Number.isFinite(ra)) {
            parts.push(`ra=${ra.toFixed(5)}`);
        }
        if (Number.isFinite(dec)) {
            parts.push(`dec=${dec.toFixed(5)}`);
        }
        if (Number.isFinite(distArcsec)) {
            parts.push(`dist_tgt=${distArcsec.toFixed(3)} arcsec`);
            parts.push(`dist_tgt=${(distArcsec / 60.0).toFixed(3)} arcmin`);
        }
        if (item && item.variable_type) {
            parts.push(`VarType=${item.variable_type}`);
        }
        if (item && Array.isArray(item.variable_catalogs) && item.variable_catalogs.length) {
            parts.push(`Catalogs=${item.variable_catalogs.join(", ")}`);
        }
        return parts.join("<br>");
    }

    function buildGaiaOverlayTraces(overlay) {
        if (!gaiaOverlayEnabled || !overlay || !Array.isArray(overlay.gaia_sources) || !overlay.gaia_sources.length) {
            return [];
        }
        const visibleSources = getVisibleGaiaSources(overlay);
        if (!visibleSources.length) {
            return [];
        }
        const sizeBounds = gaiaSizeByMagnitudeEnabled ? getMagnitudeScaleBounds(overlay) : null;
        const fixedSize = 5;
        const normalSources = visibleSources.filter((item) => !(item && item.is_variable));
        const variableSources = visibleSources.filter((item) => !!(item && item.is_variable));
        const traces = [];

        function buildTrace(items, name, color, lineColor) {
            if (!items.length) {
                return null;
            }
            const markerSizes = gaiaSizeByMagnitudeEnabled
                ? items.map((item) => getMagnitudeScaledMarkerSize(item && item.gmag, sizeBounds, fixedSize, 3, 22))
                : fixedSize;
            return {
                x: items.map((item) => item.x),
                y: items.map((item) => item.y),
                text: items.map((item) => formatGaiaOverlayHoverText(item)),
                type: "scatter",
                mode: "markers",
                name: name,
                marker: {
                    symbol: "circle",
                    size: markerSizes,
                    color: color,
                    line: {
                        color: lineColor,
                        width: 1.8,
                    },
                },
                hovertemplate: "%{text}<br>x=%{x:.2f}<br>y=%{y:.2f}<extra></extra>",
            };
        }

        const normalTrace = buildTrace(
            normalSources,
            "Gaia",
            "rgba(37, 99, 235, 0.78)",
            "rgba(219, 234, 254, 0.85)",
        );
        const variableTrace = buildTrace(
            variableSources,
            "Gaia variabile",
            "rgba(239, 68, 68, 0.82)",
            "rgba(254, 226, 226, 0.95)",
        );

        if (normalTrace) {
            traces.push(normalTrace);
        }
        if (variableTrace) {
            traces.push(variableTrace);
        }
        return traces;
    }

    const GAIA_STAR_COLUMNS = [
        { key: "source_id", label: "src id", formatter: (row) => escapeHtml(row.source_id || "-") },
        { key: "ra_deg", label: "RA", formatter: (row) => formatDecimal(row.ra_deg, 6) },
        { key: "dec_deg", label: "Dec", formatter: (row) => formatDecimal(row.dec_deg, 6) },
        { key: "dist_arcsec", label: "r sec", formatter: (row) => formatDecimal(row.dist_arcsec, 2) },
        { key: "dist_target_px", label: "r pix", formatter: (row) => formatDecimal(row.dist_target_px, 3) },
        { key: "dist_arcmin", label: "r min", formatter: (row) => formatDecimal(row.dist_arcmin, 3) },
        { key: "gmag", label: "G mag", formatter: (row) => formatDecimal(row.gmag, 3) },
        { key: "delta_mag", label: "delta mag", formatter: (row) => formatDecimal(row.delta_mag, 3) },
        { key: "flux_ratio", label: "flux r", formatter: (row) => formatFluxRatio(row.flux_ratio) },
        { key: "period", label: "Per", formatter: (row) => formatDecimal(row.period, 5) },
        { key: "variable_label", label: "var", formatter: (row) => escapeHtml(row.variable_label || "-") },
        { key: "psf_flux_v", label: "PSF flux V", formatter: (row) => formatDecimal(row.psf_flux_v, 6) },
    ];

    function getTargetGmagForDelta(overlay) {
        return firstNumericValue([
            overlay && overlay.target_position ? overlay.target_position.gmag : null,
            lastRunResult && lastRunResult.target ? lastRunResult.target.gmag : null,
        ]);
    }

    function getGaiaPeriod(item) {
        return firstNumericValue([
            item && item.variable_period,
            item && item.variable_period_days,
            item && item.period,
            item && item.Period,
        ]);
    }

    function getVariableLabel(item) {
        if (!item || !item.is_variable) {
            return "-";
        }
        if (item.variable_type) {
            return String(item.variable_type);
        }
        if (Array.isArray(item.variable_catalogs) && item.variable_catalogs.length) {
            return item.variable_catalogs.join(", ");
        }
        return "si";
    }

    function buildGaiaStarRows(overlay) {
        const targetGmag = getTargetGmagForDelta(overlay);
        const rows = [];
        if (overlay && overlay.target_position && overlay.target_position.x !== undefined && overlay.target_position.y !== undefined) {
            const targetSourceId = lastRunResult && lastRunResult.target && lastRunResult.target.gaia_source_id
                ? String(lastRunResult.target.gaia_source_id)
                : "target";
            rows.push({
                source_id: `${targetSourceId} (target)`,
                ra_deg: numericOrNull(lastRunResult && lastRunResult.target ? lastRunResult.target.ra_deg : null),
                dec_deg: numericOrNull(lastRunResult && lastRunResult.target ? lastRunResult.target.dec_deg : null),
                dist_arcsec: 0,
                dist_target_px: 0,
                dist_arcmin: 0,
                gmag: targetGmag,
                delta_mag: targetGmag !== null ? 0 : null,
                flux_ratio: targetGmag !== null ? 1 : null,
                psf_flux_v: null,
                period: null,
                variable_label: "-",
            });
        }
        const gaiaRows = gaiaOverlayEnabled ? getVisibleGaiaSources(overlay) : [];
        for (const item of gaiaRows) {
            const gmag = numericOrNull(item && item.gmag);
            const deltaMag = gmag !== null && targetGmag !== null ? gmag - targetGmag : null;
            const fluxRatio = deltaMag !== null ? Math.pow(10, -0.4 * deltaMag) : null;
            const distArcsec = numericOrNull(item && item.dist_arcsec);
            const sourceId = item && item.source_id !== undefined ? String(item.source_id) : "-";
            const sourceLabel = distArcsec !== null && Math.abs(distArcsec) <= 1.0
                ? `${sourceId} (coincidenti?)`
                : sourceId;
            rows.push({
                source_id: sourceLabel,
                ra_deg: numericOrNull(item && item.ra_deg),
                dec_deg: numericOrNull(item && item.dec_deg),
                dist_arcsec: distArcsec,
                dist_target_px: numericOrNull(item && item.dist_target_px),
                dist_arcmin: distArcsec !== null ? distArcsec / 60.0 : null,
                gmag,
                delta_mag: deltaMag,
                flux_ratio: fluxRatio,
                psf_flux_v: numericOrNull(item && (item.psf_flux_v ?? item.psf_flux)),
                period: getGaiaPeriod(item),
                variable_label: getVariableLabel(item),
            });
        }
        return rows;
    }

    function compareGaiaStarRows(left, right, key) {
        const leftValue = left[key];
        const rightValue = right[key];
        const leftMissing = leftValue === null || leftValue === undefined || leftValue === "";
        const rightMissing = rightValue === null || rightValue === undefined || rightValue === "";
        if (leftMissing && rightMissing) {
            return 0;
        }
        if (leftMissing) {
            return 1;
        }
        if (rightMissing) {
            return -1;
        }
        if (typeof leftValue === "number" && typeof rightValue === "number") {
            return leftValue - rightValue;
        }
        return String(leftValue).localeCompare(String(rightValue), "it", { numeric: true, sensitivity: "base" });
    }

    function renderGaiaStarsTable(overlay) {
        if (!gaiaStarsTableBox) {
            return;
        }
        const totalGaiaSources = gaiaOverlayEnabled && overlay && Array.isArray(overlay.gaia_sources) ? overlay.gaia_sources.length : 0;
        const hasTargetRow = !!(overlay && overlay.target_position && overlay.target_position.x !== undefined && overlay.target_position.y !== undefined);
        const totalSources = totalGaiaSources + (hasTargetRow ? 1 : 0);
        const rows = buildGaiaStarRows(overlay);
        if (!rows.length) {
            gaiaStarsTableBox.className = "gaia-stars-box empty-state";
            gaiaStarsTableBox.textContent = totalSources ? "Nessuna stella Gaia visibile con il filtro mag max corrente." : "Nessuna stella/target visualizzata.";
            return;
        }
        const sortDirection = gaiaStarsSort.direction === "desc" ? -1 : 1;
        const sortedRows = rows.slice().sort((left, right) => compareGaiaStarRows(left, right, gaiaStarsSort.key) * sortDirection);
        const maxVisibleMag = Number(gaiaSizeMaxMagInput.value);
        const magText = gaiaOverlayEnabled && Number.isFinite(maxVisibleMag) ? ` | mag max ${maxVisibleMag.toFixed(2)}` : "";
        const headerHtml = GAIA_STAR_COLUMNS.map((column) => {
            const indicator = gaiaStarsSort.key === column.key
                ? (gaiaStarsSort.direction === "asc" ? " ↑" : " ↓")
                : "";
            return `<th><button type="button" data-gaia-star-sort="${escapeHtml(column.key)}">${escapeHtml(column.label)}${indicator}</button></th>`;
        }).join("");
        const bodyHtml = sortedRows.map((row) => {
            const cells = GAIA_STAR_COLUMNS.map((column) => `<td>${column.formatter(row)}</td>`).join("");
            return `<tr>${cells}</tr>`;
        }).join("");
        gaiaStarsTableBox.className = "gaia-stars-box";
        gaiaStarsTableBox.innerHTML = `
            <p class="gaia-stars-summary">Stelle visualizzate: ${rows.length} / ${totalSources}${magText}</p>
            <table class="gaia-stars-table">
                <thead><tr>${headerHtml}</tr></thead>
                <tbody>${bodyHtml}</tbody>
            </table>
        `;
    }

    function updateGaiaOverlayToggleButton() {
        gaiaOverlayToggleButton.textContent = gaiaOverlayEnabled ? "vis.Gaia OFF" : "vis.Gaia ON";
        gaiaOverlayToggleButton.title = gaiaOverlayEnabled
            ? "Clicca per togliere la visualizzazione dei cerchietti delle stelle Gaia."
            : "Clicca per visualizzare i cerchietti delle stelle Gaia.";
    }

    function updateGaiaSizeToggleButton() {
        gaiaSizeToggleButton.textContent = gaiaSizeByMagnitudeEnabled ? "size.Gaia OFF" : "size.Gaia ON";
        gaiaSizeToggleButton.title = gaiaSizeByMagnitudeEnabled
            ? "Clicca per togliere la dimensione Gaia proporzionale alla magnitudine."
            : "Clicca per visualizzare i cerchietti Gaia con dimensioni proporzionali alla magnitudine.";
    }

    function updatePixelInfoToggleButton() {
        pixelInfoToggleButton.textContent = pixelInfoEnabled ? "info.pixel OFF" : "info.pixel ON";
        pixelInfoToggleButton.title = pixelInfoEnabled
            ? "Clicca per togliere le informazioni pixel e tornare alla modifica delle mask."
            : "Clicca per visualizzare le informazioni del pixel.";
    }

    function renderTPF(grid, masks) {
        const rowCount = Array.isArray(grid) ? grid.length : 0;
        const colCount = rowCount && Array.isArray(grid[0]) ? grid[0].length : 0;
        const currentTpf = buildCurrentTpfView();

        const pixelWorld = currentTpf && currentTpf.metadata ? currentTpf.metadata.pixel_world : null;
        const raGrid = pixelWorld && Array.isArray(pixelWorld.ra_deg) ? pixelWorld.ra_deg : null;
        const decGrid = pixelWorld && Array.isArray(pixelWorld.dec_deg) ? pixelWorld.dec_deg : null;
        const customdata = rowCount ? grid.map((row, rowIdx) =>
            row.map((flux, colIdx) => [
                colIdx + 1,
                rowIdx + 1,
                Number.isFinite(Number(flux)) ? Number(flux).toFixed(1) : "-",
                raGrid && Array.isArray(raGrid[rowIdx]) && Number.isFinite(raGrid[rowIdx][colIdx]) ? Number(raGrid[rowIdx][colIdx]).toFixed(5) : "-",
                decGrid && Array.isArray(decGrid[rowIdx]) && Number.isFinite(decGrid[rowIdx][colIdx]) ? Number(decGrid[rowIdx][colIdx]).toFixed(5) : "-",
            ])
        ) : [];
        const hovertemplate = pixelInfoEnabled
            ? "Col %{customdata[0]} | Row %{customdata[1]}<br>Flux: %{customdata[2]}<br>RA: %{customdata[3]}°<br>Dec: %{customdata[4]}°<extra></extra>"
            : "<extra></extra>";

        const traces = [{
            z: grid,
            type: "heatmap",
            colorscale: "Viridis",
            hoverongaps: false,
            showscale: true,
            name: "TPF",
            customdata,
            hovertemplate,
            zmin: fixedColorScaleEnabled && fixedColorScaleRange ? fixedColorScaleRange.zmin : undefined,
            zmax: fixedColorScaleEnabled && fixedColorScaleRange ? fixedColorScaleRange.zmax : undefined,
        }];
        const shapes = [];
        const overlay = currentTpf && currentTpf.overlay ? currentTpf.overlay : null;
        const gaiaTraces = buildGaiaOverlayTraces(overlay);
        const targetTrace = buildTargetOverlayTrace(overlay);

        if (Array.isArray(gaiaTraces) && gaiaTraces.length) {
            traces.push(...gaiaTraces);
        }
        if (targetTrace) {
            traces.push(targetTrace);
        }

        if (masks && masks.available) {
            shapes.push(...buildMaskShapes(masks.background, "background"));
            shapes.push(...buildMaskShapes(masks.target, "target"));
            traces.push({
                x: [null],
                y: [null],
                type: "scatter",
                mode: "markers",
                name: "Background",
                marker: {
                    symbol: "square",
                    size: 12,
                    color: "rgba(255,255,255,0.20)",
                    line: {
                        color: "rgba(255,255,255,0.95)",
                        width: 1.5,
                    },
                },
                hoverinfo: "skip",
            });
            traces.push({
                x: [null],
                y: [null],
                type: "scatter",
                mode: "markers",
                name: "Foreground",
                marker: {
                    symbol: "square",
                    size: 12,
                    color: "rgba(255,0,0,0.16)",
                    line: {
                        color: "rgba(255,0,0,0.98)",
                        width: 2.5,
                    },
                },
                hoverinfo: "skip",
            });
        }

        const layout = {
            title: getFrameCount() > 0 ? `TPF Flux Grid | frame ${clampFrameIndex(currentFrameIndex) + 1}` : "TPF Flux Grid",
            margin: { t: 40, r: 20, b: 40, l: 40 },
            xaxis: {
                title: "Pixel X",
                constrain: "domain",
                range: [-0.5, Math.max(0.5, colCount - 0.5)],
                autorange: false,
                fixedrange: true,
                tickmode: "array",
                tickvals: Array.from({ length: colCount }, (_, index) => index),
                ticktext: Array.from({ length: colCount }, (_, index) => String(index + 1)),
            },
            yaxis: {
                title: "Pixel Y",
                range: [-0.5, Math.max(0.5, rowCount - 0.5)],
                autorange: false,
                fixedrange: true,
                constrain: "domain",
                scaleanchor: "x",
                scaleratio: 1,
                tickmode: "array",
                tickvals: Array.from({ length: rowCount }, (_, index) => index),
                ticktext: Array.from({ length: rowCount }, (_, index) => String(index + 1)),
            },
            legend: {
                orientation: "h",
                x: 0,
                xanchor: "left",
                y: -0.08,
                yanchor: "top",
            },
            shapes,
            hovermode: "closest",
            uirevision: "tpf-frame-view",
        };
        const renderPromise = tpfPlot.data
            ? Plotly.react(tpfPlot, traces, layout, { responsive: true, displayModeBar: false })
            : Plotly.newPlot(tpfPlot, traces, layout, { responsive: true, displayModeBar: false });
        renderPromise.then(function () {
            if (!tpfPlot.__maskClickBound && typeof tpfPlot.on === "function") {
                tpfPlot.on("plotly_click", handleTpfPlotClick);
                tpfPlot.__maskClickBound = true;
            }
        });
    }

    function handleLightcurveClick(eventData) {
        const point = eventData && eventData.points && eventData.points[0] ? eventData.points[0] : null;
        if (!point || typeof point.pointIndex !== "number") {
            return;
        }
        const clickedIndex = point.pointIndex;
        const targetFrameIndex = Array.isArray(lightcurveFrameIndices) && lightcurveFrameIndices.length
            ? lightcurveFrameIndices[clickedIndex]
            : clickedIndex;
        const bounds = getLoadedFrameBounds();
        if (!bounds) {
            setStatus("Fai zoom sulla light curve e usa \"Carica frame visibili\" per attivare lo scorrimento del TPF.", "status-neutral");
            return;
        }
        if (targetFrameIndex < bounds.start || targetFrameIndex > bounds.end) {
            setStatus("Il punto selezionato e' fuori dalla finestra frame caricata. Fai nuovo zoom e ricarica i frame visibili.", "status-neutral");
            return;
        }
        setCurrentFrameIndex(targetFrameIndex);
    }

    function renderLightcurve(lightcurve) {
        updateLightcurveSeriesToggleButton(lightcurve);
        const time = Array.isArray(lightcurve.time) ? lightcurve.time : [];
        const seriesConfig = getLightcurveSeriesConfig(lightcurve);
        const corrected = Array.isArray(seriesConfig.values) ? seriesConfig.values : [];
        const previousXRange = getCurrentAxisRange("xaxis");
        const previousYRange = getCurrentAxisRange("yaxis");
        const previousSeriesMode = lightcurvePlot && lightcurvePlot.__seriesMode ? lightcurvePlot.__seriesMode : null;
        const mainTrace = {
            x: time,
            y: corrected,
            mode: lightcurveDisplayMode,
            name: seriesConfig.traceName,
        };
        if (lightcurveDisplayMode === "lines") {
            mainTrace.line = { color: "#2f7ed8", width: 2 };
        } else {
            mainTrace.marker = { color: "#2f7ed8", size: 5 };
        }
        const traces = [mainTrace];

        const highlightIndex = findLightcurvePointIndexForFrame(clampFrameIndex(currentFrameIndex));
        const highlightX = highlightIndex >= 0 && highlightIndex < time.length ? time[highlightIndex] : null;
        if (highlightIndex >= 0 && highlightIndex < time.length && highlightIndex < corrected.length) {
            traces.push({
                x: [highlightX],
                y: [corrected[highlightIndex]],
                mode: "markers",
                name: "Frame corrente",
                marker: {
                    size: 9,
                    color: "#ef4444",
                    line: {
                        color: "#ffffff",
                        width: 1.5,
                    },
                },
                hovertemplate: `Frame corrente<br>time=%{x}<br>${seriesConfig.hoverLabel}=%{y}<extra></extra>`,
            });
        }

        const layout = {
            title: seriesConfig.title,
            margin: { t: 40, r: 20, b: 40, l: 50 },
            xaxis: { title: "Time" },
            yaxis: {
                title: seriesConfig.yAxisTitle,
                autorange: seriesConfig.reverseYAxis ? "reversed" : true,
            },
            uirevision: "lightcurve-view",
        };
        if (highlightX !== null && highlightX !== undefined) {
            layout.shapes = [{
                type: "line",
                xref: "x",
                yref: "paper",
                x0: highlightX,
                x1: highlightX,
                y0: 0,
                y1: 1,
                line: {
                    color: "#ef4444",
                    width: 2,
                    dash: "solid",
                },
            }];
        }
        if (seriesConfig.reverseYAxis) {
            const finiteValues = corrected
                .map((value) => Number(value))
                .filter((value) => Number.isFinite(value));
            if (finiteValues.length > 0) {
                let minValue = Math.min(...finiteValues);
                let maxValue = Math.max(...finiteValues);
                if (minValue === maxValue) {
                    const padding = Math.abs(minValue || 1) * 0.01;
                    minValue -= padding;
                    maxValue += padding;
                }
                layout.yaxis.range = [maxValue, minValue];
                layout.yaxis.autorange = false;
            }
        }
        if (previousXRange) {
            layout.xaxis.range = previousXRange;
            layout.xaxis.autorange = false;
        }
        if (previousYRange && previousSeriesMode === seriesConfig.mode && !seriesConfig.reverseYAxis) {
            layout.yaxis.range = previousYRange;
            layout.yaxis.autorange = false;
        }
        const renderPromise = lightcurvePlot.data
            ? Plotly.react(lightcurvePlot, traces, layout, { responsive: true, displayModeBar: true })
            : Plotly.newPlot(lightcurvePlot, traces, layout, { responsive: true, displayModeBar: true });
        renderPromise.then(function () {
            lightcurvePlot.__seriesMode = seriesConfig.mode;
            if (!lightcurvePlot.__lightcurveClickBound && typeof lightcurvePlot.on === "function") {
                lightcurvePlot.on("plotly_click", handleLightcurveClick);
                lightcurvePlot.__lightcurveClickBound = true;
            }
        });
    }
    function formatTpfInfo(tpf) {
        if (!tpf) {
            return "TPF non disponibile.";
        }
        const parts = [];
        if (tpf.message) parts.push(tpf.message);
        if (tpf.mode) parts.push(`mode=${tpf.mode}`);
        if (tpf.source && tpf.source.type) parts.push(`source=${tpf.source.type}`);
        if (Array.isArray(tpf.shape)) parts.push(`shape=${tpf.shape.join("x")}`);
        if (tpf.metadata && tpf.metadata.sector !== undefined && tpf.metadata.sector !== null) parts.push(`sector=${tpf.metadata.sector}`);
        if (tpf.metadata && tpf.metadata.camera !== undefined && tpf.metadata.camera !== null) parts.push(`camera=${tpf.metadata.camera}`);
        if (tpf.metadata && tpf.metadata.ccd !== undefined && tpf.metadata.ccd !== null) parts.push(`ccd=${tpf.metadata.ccd}`);
        if (tpf.metadata && tpf.metadata.tessmag !== undefined && tpf.metadata.tessmag !== null) parts.push(`tessmag=${tpf.metadata.tessmag}`);
        if (tpf.metadata && tpf.metadata.ticid !== undefined && tpf.metadata.ticid !== null) parts.push(`ticid=${tpf.metadata.ticid}`);
        return parts.join(" | ") || "TPF disponibile.";
    }

    function formatTpfHeaderMeta(result) {
        const input = result && result.input ? result.input : {};
        const target = result && result.target ? result.target : {};
        const tpf = result && result.tpf ? result.tpf : {};
        const gaiaSourceId = target.gaia_source_id || input.gaia_source_id || "-";
        const sector = input.sector ?? "-";
        const raDeg = Number.isFinite(Number(target.ra_deg)) ? Number(target.ra_deg).toFixed(2) : "-";
        const decDeg = Number.isFinite(Number(target.dec_deg)) ? Number(target.dec_deg).toFixed(2) : "-";
        const gmag = Number.isFinite(Number(target.gmag)) ? Number(target.gmag).toFixed(2) : "-";
        const camera = tpf && tpf.metadata && tpf.metadata.camera !== undefined && tpf.metadata.camera !== null
            ? tpf.metadata.camera
            : "-";
        const ccd = tpf && tpf.metadata && tpf.metadata.ccd !== undefined && tpf.metadata.ccd !== null
            ? tpf.metadata.ccd
            : "-";
        return `gaia_id=${gaiaSourceId} | sect=${sector} | cam=${camera} | ccd=${ccd} | ra=${raDeg} | dec=${decDeg} | gmag=${gmag}`;
    }

    function formatMaskInfo(tpf) {
        if (!tpf || !tpf.masks) {
            return "Selezione foreground/background non disponibile.";
        }
        if (!tpf.masks.available) {
            return tpf.masks.message || "Selezione foreground/background non disponibile.";
        }
        const summary = tpf.masks.summary || {};
        const message = masksNeedRecalc()
            ? 'Premi "Ricalcola light curve" per aggiornare la curva.'
            : "Light curve aggiornata.";
        return `${message} | target_pixels=${summary.target_pixels ?? 0} | background_pixels=${summary.background_pixels ?? 0}`;
    }

    function formatOverlayInfo(tpf) {
        if (!tpf || !tpf.overlay) {
            return "Overlay target/Gaia non disponibile.";
        }
        const parts = [];
        if (tpf.overlay.message) parts.push(tpf.overlay.message);
        if (tpf.overlay.target_position && tpf.overlay.target_position.source) parts.push(`target_source=${tpf.overlay.target_position.source}`);
        if (Array.isArray(tpf.overlay.gaia_sources)) parts.push(`gaia_sources=${tpf.overlay.gaia_sources.length}`);
        if (Number.isFinite(Number(tpf.overlay.variable_sources_count))) parts.push(`gaia_variable=${tpf.overlay.variable_sources_count}`);
        parts.push(`gaia_overlay=${gaiaOverlayEnabled ? "on" : "off"}`);
        parts.push("target=giallo");
        parts.push("gaia=blu");
        parts.push("variabili=rosso");
        return parts.join(" | ");
    }

    function formatLightcurveInfo(lightcurve) {
        if (!lightcurve) {
            return "Light curve non disponibile.";
        }
        const parts = [];
        if (lightcurve.message) parts.push(lightcurve.message);
        if (lightcurve.mode) parts.push(`mode=${lightcurve.mode}`);
        parts.push(`series=${getLightcurveSeriesConfig(lightcurve).mode}`);
        if (lightcurve.summary && lightcurve.summary.target_pixels !== undefined) parts.push(`target_pixels=${lightcurve.summary.target_pixels}`);
        if (lightcurve.summary && lightcurve.summary.background_pixels !== undefined) parts.push(`background_pixels=${lightcurve.summary.background_pixels}`);
        return parts.join(" | ") || "Light curve disponibile.";
    }

    function setEditMode(mode) {
        editMode = mode === "background" ? "background" : "target";
        targetModeButton.classList.toggle("is-active", editMode === "target");
        backgroundModeButton.classList.toggle("is-active", editMode === "background");
        if (editingEnabled) {
            editInfo.textContent = pixelInfoEnabled
                ? "Modalita' Info pixel attiva. Clicca un pixel del TPF per vedere flux, RA e Dec."
                : `Modalita' editing attiva: ${editMode}. Clicca un pixel del TPF per modificarlo e poi premi "Ricalcola light curve".`;
        }
    }

    function updateEditingControls() {
        targetModeButton.disabled = !editingEnabled;
        backgroundModeButton.disabled = !editingEnabled;
        recalcButton.disabled = !editingEnabled;
        if (!editingEnabled) {
            const reason = lastRunResult && lastRunResult.tpf && lastRunResult.tpf.mode === "preview"
                ? "Editing pixel non disponibile: il TPF corrente e' una preview sintetica. Per abilitare Target, Background e Ricalcola light curve serve un TPF reale locale."
                : "Editing pixel disponibile solo con TPF reale.";
            editInfo.textContent = reason;
            targetModeButton.title = reason;
            backgroundModeButton.title = reason;
            recalcButton.title = reason;
        } else {
            editInfo.textContent = pixelInfoEnabled
                ? "Modalita' Info pixel attiva. Clicca un pixel del TPF per vedere flux, RA e Dec."
                : `Modalita' editing attiva: ${editMode}. Clicca un pixel del TPF per modificarlo e poi premi "Ricalcola light curve".`;
            targetModeButton.title = "Modalita' editing target attiva.";
            backgroundModeButton.title = "Modalita' editing background attiva.";
            recalcButton.title = "Ricalcola la light curve usando le maschere correnti.";
        }
        setEditMode(editMode);
    }

    function syncMasksFromResult(result) {
        const tpf = result && result.tpf ? result.tpf : null;
        if (tpf && tpf.mode === "real" && tpf.masks && tpf.masks.available) {
            targetMask = cloneMask(tpf.masks.target);
            backgroundMask = cloneMask(tpf.masks.background);
            committedTargetMask = cloneMask(tpf.masks.target);
            committedBackgroundMask = cloneMask(tpf.masks.background);
            editingEnabled = true;
        } else {
            targetMask = [];
            backgroundMask = [];
            committedTargetMask = [];
            committedBackgroundMask = [];
            editingEnabled = false;
        }
        updateEditingControls();
    }

    function syncFrameStateFromResult(result) {
        const tpf = result && result.tpf ? result.tpf : null;
        const frames = tpf && tpf.frames ? tpf.frames : null;
        if (frames && frames.available && frames.loaded && Array.isArray(frames.grids) && frames.grids.length) {
            tpfFrames = frames.grids;
            tpfFrameTimes = Array.isArray(frames.time) ? frames.time : [];
            loadedFrameStartIndex = Number.isFinite(frames.start_index) ? frames.start_index : 0;
            loadedFrameEndIndex = Number.isFinite(frames.end_index) ? frames.end_index : (loadedFrameStartIndex + frames.grids.length - 1);
            currentFrameIndex = Number.isFinite(frames.initial_index) ? frames.initial_index : loadedFrameStartIndex;
            recomputeFixedColorScaleRange();
        } else {
            tpfFrames = [];
            tpfFrameTimes = [];
            currentFrameIndex = 0;
            loadedFrameStartIndex = null;
            loadedFrameEndIndex = null;
            fixedColorScaleRange = null;
        }

        if (result && result.lightcurve && Array.isArray(result.lightcurve.frame_indices)) {
            lightcurveFrameIndices = result.lightcurve.frame_indices.slice();
        } else {
            lightcurveFrameIndices = [];
        }
    }

    function buildCurrentTpfView() {
        if (!lastRunResult || !lastRunResult.tpf) {
            return null;
        }
        if (!editingEnabled) {
            return lastRunResult.tpf;
        }
        return {
            ...lastRunResult.tpf,
            masks: buildCurrentMasksPayload("manual-ui", 'Premi "Ricalcola light curve" per aggiornare la curva.'),
        };
    }

    function renderCurrentTpfState() {
        const tpf = buildCurrentTpfView();
        if (!tpf) {
            return;
        }

        updateGaiaOverlayToggleButton();
        updateFixedScaleToggleButton();
        tpfHeaderMeta.textContent = formatTpfHeaderMeta(lastRunResult);
        tpfInfo.textContent = formatTpfInfo(tpf);
        overlayInfo.textContent = formatOverlayInfo(tpf);
        tpfDetailsInfo.textContent = tpfInfo.textContent;
        overlayDetailsInfo.textContent = overlayInfo.textContent;
        lightcurveDetailsInfo.textContent = lightcurveInfo.textContent;
        maskInfo.textContent = formatMaskInfo(tpf);
        maskInfo.classList.toggle("warning", masksNeedRecalc());
        updateFrameControls(tpf);
        syncGaiaMaxMagInput(tpf.overlay || null);
        renderGaiaStarsTable(tpf.overlay || null);

        const currentGrid = getCurrentFrameGrid(tpf);
        if (Array.isArray(currentGrid)) {
            renderTPF(currentGrid, tpf.masks || null);
        } else {
            Plotly.purge(tpfPlot);
            tpfPlot.innerHTML = "";
        }
    }

    function renderDebugInfo(data) {
        const debugContent = document.getElementById("debugContent");
        if (!debugContent) return;

        if (!data || !data.tpf) {
            debugContent.innerHTML = '<p style="color: #666;">Nessuna info di debug disponibile.</p>';
            return;
        }

        const debug = data.tpf.metadata ? data.tpf.metadata.wcs_debug : null;
        const overlayDebug = data.tpf.overlay ? data.tpf.overlay.debug_stats : null;
        let html = '<div style="line-height: 1.6;">';

        // FITS Header
        if (debug) {
            html += '<div style="margin-bottom: 1.5rem;">';
            html += '<strong>[FITS Header Keywords]</strong><br>';
            if (debug.fits_header && Object.keys(debug.fits_header).length > 0) {
                for (const [key, value] of Object.entries(debug.fits_header)) {
                    html += `<div>&nbsp;&nbsp;${key} = ${value}</div>`;
                }
            } else {
                html += '<div style="color: #999;">Nessun keyword disponibile</div>';
            }
            html += '</div>';

            // Shape Calculated
            html += '<div style="margin-bottom: 1.5rem;">';
            html += '<strong>[Shape Calcolato]</strong><br>';
            if (debug.shape_calculated && Array.isArray(debug.shape_calculated)) {
                html += `<div>&nbsp;&nbsp;shape = [${debug.shape_calculated[0]}, ${debug.shape_calculated[1]}]</div>`;
                html += `<div style="color: #666;">&nbsp;&nbsp;(rows=${debug.shape_calculated[0]}, cols=${debug.shape_calculated[1]})</div>`;
            } else {
                html += '<div style="color: #999;">Shape non disponibile</div>';
            }
            html += '</div>';

            // WCS Info
            html += '<div style="margin-bottom: 1.5rem;">';
            html += '<strong>[WCS Info]</strong><br>';
            if (debug.wcs_info && Object.keys(debug.wcs_info).length > 0) {
                for (const [key, value] of Object.entries(debug.wcs_info)) {
                    let displayValue = value;
                    if (Array.isArray(value)) {
                        displayValue = `[${value.join(", ")}]`;
                    }
                    html += `<div>&nbsp;&nbsp;${key} = ${displayValue}</div>`;
                }
            } else {
                html += '<div style="color: #999;">WCS non disponibile</div>';
            }
            html += '</div>';

            // Test Conversion
            html += '<div style="margin-bottom: 1.5rem;">';
            html += '<strong>[Test Conversione WCS (Centro Griglia)]</strong><br>';
            if (debug.test_conversion) {
                if (debug.test_conversion.error) {
                    html += `<div style="color: #c33;">Errore: ${debug.test_conversion.error}</div>`;
                } else if (debug.test_conversion.pixel_input && debug.test_conversion.world_output) {
                    const [px, py] = debug.test_conversion.pixel_input;
                    const [ra, dec] = debug.test_conversion.world_output;
                    html += `<div>&nbsp;&nbsp;Input Pixel: [${px.toFixed(1)}, ${py.toFixed(1)}]</div>`;
                    html += `<div>&nbsp;&nbsp;Output World: RA=${ra}, DEC=${dec}</div>`;
                    html += `<div style="color: #666;">&nbsp;&nbsp;${debug.test_conversion.description}</div>`;
                }
            } else {
                html += '<div style="color: #999;">Test conversion non disponibile</div>';
            }
            html += '</div>';

            // CRVAL vs Target Info Alignment Check
            if (debug.crval_vs_target) {
                const alignment = debug.crval_vs_target;
                const [crval_ra, crval_dec] = alignment.wcs_crval;
                const [target_ra, target_dec] = alignment.target_info;
                const delta_ra = alignment.delta_ra_arcsec;
                const delta_dec = alignment.delta_dec_arcsec;
                const delta_total = Math.sqrt(delta_ra * delta_ra + delta_dec * delta_dec);
                const isAligned = delta_total < 5; // 5 arcsec è OK per TPF
                const statusColor = isAligned ? '#0066cc' : '#c33';
                const statusIcon = isAligned ? '✓' : '⚠';

                html += '<div style="margin-bottom: 1.5rem; padding: 0.8rem; background: #fff9e6; border-left: 3px solid ' + statusColor + ';">';
                html += '<strong>[CRVAL (WCS) vs Target Info Alignment] ' + statusIcon + '</strong><br>';
                html += `<div>&nbsp;&nbsp;WCS CRVAL: RA=${crval_ra}, DEC=${crval_dec}</div>`;
                html += `<div>&nbsp;&nbsp;Target Info: RA=${target_ra}, DEC=${target_dec}</div>`;
                html += `<div style="color: ${statusColor}; font-weight: bold;">&nbsp;&nbsp;Δ RA=${delta_ra} arcsec, Δ DEC=${delta_dec} arcsec (totale ${delta_total.toFixed(1)} arcsec)</div>`;
                if (!isAligned) {
                    html += `<div style="color: #c33; margin-top: 0.5rem;">⚠ ATTENZIONE: WCS non allineato al target! Centro griglia != target coordinato.</div>`;
                }
                html += '</div>';
            }
        }

        // Gaia Overlay Debug Stats
        if (overlayDebug) {
            html += '<div style="margin-bottom: 1.5rem; padding: 0.8rem; background: #fafafa; border-left: 3px solid #0066cc;">';
            html += '<strong>[Query Gaia Overlay]</strong><br>';
            if (overlayDebug.error) {
                html += `<div style="color: #c33;">Errore: ${overlayDebug.error}</div>`;
            } else {
                html += `<div>&nbsp;&nbsp;Raggio query: ${overlayDebug.radius_deg ? overlayDebug.radius_deg.toFixed(3) : 'N/A'} deg</div>`;
                html += `<div>&nbsp;&nbsp;Centro: RA=${overlayDebug.center_ra ? overlayDebug.center_ra.toFixed(5) : 'N/A'}, DEC=${overlayDebug.center_dec ? overlayDebug.center_dec.toFixed(5) : 'N/A'}</div>`;
                html += `<div style="margin-top: 0.5rem; font-weight: bold;">Risultati filtro:</div>`;
                html += `<div style="color: #0066cc;">&nbsp;&nbsp;✓ Accettate: ${overlayDebug.accepted}</div>`;
                html += `<div style="color: #c33;">&nbsp;&nbsp;✗ Rifiutate: ${overlayDebug.rejected}</div>`;
                html += `<div style="color: #666;">&nbsp;&nbsp;⊙ Totale Vizier: ${overlayDebug.total_vizier}</div>`;

                if (overlayDebug.returned_to_frontend !== undefined) {
                    html += `<div style="color: #666;">&nbsp;&nbsp;Restituite al viewer: ${overlayDebug.returned_to_frontend}</div>`;
                }
                if (overlayDebug.selection_order) {
                    html += `<div style="color: #666;">&nbsp;&nbsp;Ordine: ${overlayDebug.selection_order}</div>`;
                }

                function formatOverlayDebugSample(src) {
                    const variableText = src.is_variable
                        ? `variabile=si${src.variable_type ? ` (${src.variable_type})` : ""}`
                        : "variabile=no";
                    const catalogs = Array.isArray(src.variable_catalogs) && src.variable_catalogs.length
                        ? ` | cat=${src.variable_catalogs.join(",")}`
                        : "";
                    return `ID ${src.id}: x=${src.x}, y=${src.y}, ra=${src.ra_deg}, dec=${src.dec_deg}, G=${src.gmag}, dist=${src.dist_target_arcsec}" / ${src.dist_target_px}px, ${variableText}${catalogs}`;
                }

                // Campioni accettati
                if (overlayDebug.accepted_samples && overlayDebug.accepted_samples.length > 0) {
                    html += `<div style="margin-top: 0.8rem; font-weight: bold; color: #0066cc;">Campione accettate (pixel):</div>`;
                    for (const src of overlayDebug.accepted_samples) {
                        html += `<div style="color: #0066cc; margin-left: 1rem; font-family: monospace;">${formatOverlayDebugSample(src)}</div>`;
                    }
                }

                // Campioni rifiutati
                if (overlayDebug.rejected_samples && overlayDebug.rejected_samples.length > 0) {
                    html += `<div style="margin-top: 0.8rem; font-weight: bold; color: #c33;">Campione rifiutate (pixel):</div>`;
                    for (const src of overlayDebug.rejected_samples) {
                        html += `<div style="color: #c33; margin-left: 1rem; font-family: monospace;">${formatOverlayDebugSample(src)}</div>`;
                    }
                }
            }
            html += '</div>';
        }

        html += '</div>';
        debugContent.innerHTML = html;
    }

    function updateSections(data) {
        renderTarget(data.target || null);
        renderDebugInfo(data);
        if (data.tpf && data.tpf.available && (Array.isArray(data.tpf.flux_grid) || (data.tpf.frames && data.tpf.frames.available))) {
            renderCurrentTpfState();
        } else {
            tpfHeaderMeta.textContent = formatTpfHeaderMeta(data);
            tpfInfo.textContent = formatTpfInfo(data.tpf);
            overlayInfo.textContent = formatOverlayInfo(data.tpf);
            tpfDetailsInfo.textContent = tpfInfo.textContent;
            overlayDetailsInfo.textContent = overlayInfo.textContent;
            renderGaiaStarsTable(data.tpf && data.tpf.overlay ? data.tpf.overlay : null);
            maskInfo.textContent = formatMaskInfo(data.tpf);
            maskInfo.classList.toggle("warning", masksNeedRecalc());
            updateFrameControls(data.tpf || null);
            Plotly.purge(tpfPlot);
            tpfPlot.innerHTML = "";
        }

        if (data.lightcurve && data.lightcurve.available && Array.isArray(data.lightcurve.time) && Array.isArray(data.lightcurve.corrected_flux || data.lightcurve.flux)) {
            lightcurveInfo.textContent = formatLightcurveInfo(data.lightcurve);
            lightcurveDetailsInfo.textContent = lightcurveInfo.textContent;
            renderLightcurve(data.lightcurve);
        } else {
            lightcurveInfo.textContent = formatLightcurveInfo(data.lightcurve);
            lightcurveDetailsInfo.textContent = lightcurveInfo.textContent;
            updateLightcurveSeriesToggleButton(null);
            Plotly.purge(lightcurvePlot);
            lightcurvePlot.innerHTML = "";
        }
    }

    function buildAgataReturnPayload(result, context) {
        const gaiaSourceId = result && result.input && result.input.gaia_source_id
            ? result.input.gaia_source_id
            : (context.gaia_source_id || null);
        const sector = result && result.input && result.input.sector !== undefined
            ? result.input.sector
            : (context.sector || null);

        return {
            component: "tpf",
            mode: context.mode,
            source_context: context.source_context || null,
            input: {
                gaia_source_id: gaiaSourceId,
                sector: sector,
            },
            result: {
                status: result && result.status ? result.status : "not-ready",
                target: result && result.target ? {
                    gaia_source_id: result.target.gaia_source_id || null,
                    catalog: result.target.catalog || null,
                    ra_deg: result.target.ra_deg ?? null,
                    dec_deg: result.target.dec_deg ?? null,
                    gmag: result.target.gmag ?? null,
                } : null,
                tpf: {
                    available: !!(result && result.tpf && result.tpf.available),
                    mode: result && result.tpf ? (result.tpf.mode || null) : null,
                    metadata: result && result.tpf && result.tpf.metadata ? {
                        sector: result.tpf.metadata.sector ?? null,
                        camera: result.tpf.metadata.camera ?? null,
                        ccd: result.tpf.metadata.ccd ?? null,
                        tessmag: result.tpf.metadata.tessmag ?? null,
                        ticid: result.tpf.metadata.ticid ?? null,
                    } : null,
                    frames: result && result.tpf && result.tpf.frames ? {
                        available: !!result.tpf.frames.available,
                        loaded: !!result.tpf.frames.loaded,
                        count: result.tpf.frames.count ?? 0,
                        current_index: getLoadedFrameBounds() ? clampFrameIndex(currentFrameIndex) : null,
                    } : null,
                    overlay: result && result.tpf && result.tpf.overlay ? {
                        target_position: result.tpf.overlay.target_position || null,
                        gaia_sources_count: Array.isArray(result.tpf.overlay.gaia_sources) ? result.tpf.overlay.gaia_sources.length : 0,
                    } : null,
                    masks: result && result.tpf && result.tpf.masks ? {
                        available: !!result.tpf.masks.available,
                        mode: result.tpf.masks.mode || null,
                        summary: result.tpf.masks.summary || null,
                    } : null,
                },
                lightcurve: {
                    available: !!(result && result.lightcurve && result.lightcurve.available),
                    mode: result && result.lightcurve ? (result.lightcurve.mode || null) : null,
                    summary: result && result.lightcurve ? (result.lightcurve.summary || null) : null,
                },
                save: {
                    mode: result && result.save ? (result.save.mode || null) : null,
                    saved: !!(result && result.save && result.save.saved),
                },
            },
        };
    }

    function renderReturnPayloadPreview(result) {
        returnPayloadBox.textContent = JSON.stringify(buildAgataReturnPayload(result, pageContext), null, 2);
    }

    async function pollJobStatus(jobId, onProgress, timeout = 120000) {
        return new Promise((resolve, reject) => {
            const startTime = Date.now();
            const interval = setInterval(async () => {
                const elapsed = Date.now() - startTime;
                if (elapsed > timeout) {
                    clearInterval(interval);
                    reject(new Error("Job timeout dopo " + Math.round(timeout / 1000) + " sec"));
                    return;
                }

                try {
                    const statusResp = await fetch(`/agata/tpf/api/job/${jobId}/status`);
                    if (!statusResp.ok) {
                        clearInterval(interval);
                        reject(new Error("Errore polling status: HTTP " + statusResp.status));
                        return;
                    }
                    const statusData = await statusResp.json();

                    if (statusData.job_status === "running") {
                        if (onProgress) onProgress(statusData.progress);
                    } else if (statusData.job_status === "completed") {
                        clearInterval(interval);
                        const resultResp = await fetch(`/agata/tpf/api/job/${jobId}/result`);
                        if (!resultResp.ok) {
                            reject(new Error("Errore lettura result: HTTP " + resultResp.status));
                            return;
                        }
                        const result = await resultResp.json();
                        resolve(result);
                    } else if (statusData.job_status === "failed") {
                        clearInterval(interval);
                        reject(new Error(statusData.error || "Job fallito"));
                    }
                } catch (error) {
                    clearInterval(interval);
                    reject(error);
                }
            }, 1500);
        });
    }

    async function fetchMastSectors(gaiaId, cutoutSize) {
        const startResp = await fetch(endpointUrls.mastSectorsUrl, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                gaia_id: gaiaId,
                cutout_size: cutoutSize,
            }),
        });

        if (startResp.status !== 202) {
            const data = await parseApiJsonResponse(startResp, "Errore avvio job query settori MAST");
            output.textContent = JSON.stringify(data, null, 2);
            return { response: startResp, data };
        }

        const startData = await startResp.json();
        const jobId = startData.job_id;

        try {
            const result = await pollJobStatus(jobId, (progress) => {
                setMastStatus(
                    `${progress.message || ""}${progress.percent ? ` (${progress.percent}%)` : ""}`,
                    "warning"
                );
            });
            output.textContent = JSON.stringify(result, null, 2);
            return { response: startResp, data: result };
        } catch (error) {
            const errorData = { status: "error", message: error.message };
            output.textContent = JSON.stringify(errorData, null, 2);
            throw error;
        }
    }

    async function fetchLocalMastSectors(gaiaId, cutoutSize) {
        const response = await fetch(endpointUrls.mastLocalSectorsUrl, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                gaia_id: gaiaId,
                cutout_size: cutoutSize,
            }),
        });
        const data = await parseApiJsonResponse(response, "Risposta JSON non valida durante il controllo TPF locali");
        output.textContent = JSON.stringify(data, null, 2);
        return { response, data };
    }

    async function fetchSavedSessions(gaiaSourceId, sector) {
        const response = await fetch(endpointUrls.sessionsUrl, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                gaia_source_id: gaiaSourceId,
                sector: sector || undefined,
            }),
        });
        const data = await response.json().catch(() => ({ status: "error", message: "Risposta JSON non valida" }));
        return { response, data };
    }

    async function refreshSavedSessions(gaiaSourceId, sector) {
        if (!gaiaSourceId) {
            renderSavedSessions(null);
            return;
        }
        try {
            const { response, data } = await fetchSavedSessions(gaiaSourceId, sector);
            if (!response.ok || data.status === "error") {
                renderSavedSessions(null);
                return;
            }
            renderSavedSessions(data);
        } catch (_) {
            renderSavedSessions(null);
        }
    }

    async function downloadMastTpf(gaiaId, sector, cutoutSize) {
        const controller = new AbortController();
        const timeoutMs = 95000;
        const timeoutHandle = window.setTimeout(() => controller.abort(), timeoutMs);
        let response;
        try {
            response = await fetch(endpointUrls.mastDownloadUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    gaia_id: gaiaId,
                    sector: sector,
                    cutout_size: cutoutSize,
                }),
                signal: controller.signal,
            });
        } catch (error) {
            if (error && error.name === "AbortError") {
                throw new Error("Timeout durante il download TPF da MAST/TESS. Il servizio remoto non ha risposto in tempo.");
            }
            throw error;
        } finally {
            window.clearTimeout(timeoutHandle);
        }
        const data = await response.json().catch(() => ({ ok: false, status: "error", message: "Risposta JSON non valida" }));
        output.textContent = JSON.stringify(data, null, 2);
        return { response, data };
    }

    async function runPipeline(gaiaSourceId, sector, masks) {
        const response = await fetch(endpointUrls.runUrl, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                gaia_source_id: gaiaSourceId,
                sector: sector,
                source_context: pageContext.source_context,
                masks: masks || undefined,
            }),
        });
        const data = await response.json().catch(() => ({ status: "error", message: "Risposta JSON non valida" }));
        output.textContent = JSON.stringify(data, null, 2);
        return { response, data };
    }

    async function loadFramesWindow(gaiaSourceId, sector, frameStart, frameEnd) {
        const response = await fetch(endpointUrls.framesUrl, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                gaia_source_id: gaiaSourceId,
                sector: sector,
                frame_start: frameStart,
                frame_end: frameEnd,
            }),
        });
        const data = await response.json().catch(() => ({ status: "error", message: "Risposta JSON non valida" }));
        output.textContent = JSON.stringify(data, null, 2);
        return { response, data };
    }

    async function handlePipelineSuccess(data, statusMessage) {
        pageContext.gaia_source_id = String((data && data.input && data.input.gaia_source_id) || pageContext.gaia_source_id || "");
        pageContext.sector = String((data && data.input && data.input.sector) || pageContext.sector || "");
        if (gaiaSourceIdInput) {
            gaiaSourceIdInput.value = pageContext.gaia_source_id;
        }
        if (data && data.restored_session && data.restored_session.session_id) {
            activeRestoredSessionId = String(data.restored_session.session_id);
        }
        lastRunResult = data;
        if (data && data.mast_sectors && typeof data.mast_sectors === "object") {
            lastMastSectorsResult = data.mast_sectors;
            mastHasRemoteResults = !!data.mast_sectors.remote_available;
            renderMastSectors(data.mast_sectors);
        }
        saveButton.disabled = false;
        promoteButton.disabled = false;
        syncMasksFromResult(data);
        syncFrameStateFromResult(data);
        const tpfAvailable = !!(data.tpf && data.tpf.available);
        const lcAvailable = !!(data.lightcurve && data.lightcurve.available);
        setStatus(
            statusMessage || data.message || `Pipeline completata | TPF: ${tpfAvailable ? "disponibile" : "non disponibile"} | Light curve: ${lcAvailable ? "disponibile" : "non disponibile"}`,
            "status-success"
        );
        setSaveStatus("Risultato pronto per salvataggio tecnico o promozione.", "status-neutral");
        renderReturnPayloadPreview(lastRunResult);
        updateSections(data);
        refreshSavedSessions(
            String((data && data.input && data.input.gaia_source_id) || pageContext.gaia_source_id || ""),
            null
        );
    }

    function mergeLoadedFramesIntoResult(framesPayload) {
        if (!lastRunResult || !lastRunResult.tpf) {
            return;
        }
        lastRunResult = {
            ...lastRunResult,
            tpf: {
                ...lastRunResult.tpf,
                frames: framesPayload,
            },
        };
        syncFrameStateFromResult(lastRunResult);
        renderReturnPayloadPreview(lastRunResult);
        renderCurrentTpfState();
        if (lastRunResult.lightcurve && lastRunResult.lightcurve.available) {
            renderLightcurve(lastRunResult.lightcurve);
        }
    }

    async function pollMetadataJob(jobId, onComplete, timeout = 60000) {
        const startTime = Date.now();
        const interval = setInterval(async () => {
            const elapsed = Date.now() - startTime;
            if (elapsed > timeout) {
                clearInterval(interval);
                setStatus("Timeout risoluzione metadata (continuando con dati parziali).", "status-warning");
                return;
            }

            try {
                const statusResp = await fetch(`/agata/tpf/api/job/${jobId}/status`);
                if (!statusResp.ok) {
                    return;
                }
                const statusData = await statusResp.json();

                if (statusData.job_status === "running") {
                    const progress = statusData.progress || {};
                    const msg = progress.message || "Risoluzione metadata in corso...";
                    const percent = progress.percent ? ` (${progress.percent}%)` : "";
                    setStatus(msg + percent, "status-neutral");
                } else if (statusData.job_status === "completed") {
                    clearInterval(interval);
                    try {
                        const resultResp = await fetch(`/agata/tpf/api/job/${jobId}/result`);
                        if (!resultResp.ok) {
                            setStatus("Metadata completato con errore di lettura.", "status-warning");
                            return;
                        }
                        const result = await resultResp.json();
                        if (result.metadata) {
                            onComplete(result);
                            setStatus("Informazioni stelle aggiornate.", "status-success");
                        }
                    } catch (error) {
                        const message = error instanceof Error ? error.message : String(error);
                        setStatus(`Errore durante lettura metadata: ${message}`, "status-warning");
                    }
                } else if (statusData.job_status === "failed") {
                    clearInterval(interval);
                    setStatus(`Metadata job fallito: ${statusData.error || "Errore sconosciuto"}`, "status-warning");
                }
            } catch (error) {
                // Silent failure, keep trying until timeout
            }
        }, 1500);
    }

    async function startPipelineRun(gaiaSourceId, sector) {
        pageContext.gaia_source_id = gaiaSourceId;
        pageContext.sector = sector;
        if (gaiaSourceIdInput) {
            gaiaSourceIdInput.value = gaiaSourceId;
        }
        setError("");
        setStatus("Loading... esecuzione pipeline in corso.", "status-neutral");
        setSaveStatus("Nessun salvataggio eseguito.", "status-neutral");
        output.textContent = JSON.stringify({ status: "ok", message: "Loading..." }, null, 2);
        activeRestoredSessionId = null;
        lastRunResult = null;
        targetMask = [];
        backgroundMask = [];
        committedTargetMask = [];
        committedBackgroundMask = [];
        editingEnabled = false;
        saveButton.disabled = true;
        promoteButton.disabled = true;
        updateEditingControls();
        resetFrameState();
        clearPlots();
        resetSections();
        renderReturnPayloadPreview(null);

        try {
            const { response, data } = await runPipeline(gaiaSourceId, sector, null);
            if (!response.ok || data.status === "error") {
                lastRunResult = null;
                saveButton.disabled = true;
                promoteButton.disabled = true;
                setStatus(data.message || "Pipeline completata con errore.", "status-error");
                setError(data.message || `Errore HTTP ${response.status}`);
                renderReturnPayloadPreview(null);
                updateSections(data || {});
                return false;
            }
            await handlePipelineSuccess(data, null);

            // If metadata job is running, start polling for metadata updates
            if (data.metadata_job_id) {
                pollMetadataJob(data.metadata_job_id, (result) => {
                    // Update metadata in lastRunResult
                    if (lastRunResult && lastRunResult.tpf) {
                        if (result.metadata) {
                            // Merge metadata instead of overwriting (preserve camera, ccd, etc.)
                            lastRunResult.tpf.metadata = {
                                ...lastRunResult.tpf.metadata,
                                ...result.metadata,
                            };
                        }
                        if (result.overlay) {
                            lastRunResult.tpf.overlay = result.overlay;
                        }
                        if (result.target_info) {
                            // Update target at root level for renderTarget to find it
                            lastRunResult.target = result.target_info;
                            lastRunResult.tpf.target_info = result.target_info;
                        }
                        // Re-render with updated data
                        renderReturnPayloadPreview(lastRunResult);
                        updateSections(lastRunResult);
                        renderCurrentTpfState();
                    }
                });
            }

            return true;
        } catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            lastRunResult = null;
            saveButton.disabled = true;
            promoteButton.disabled = true;
            setStatus("Errore di rete durante la pipeline.", "status-error");
            setError(message);
            output.textContent = JSON.stringify({ status: "error", message }, null, 2);
            clearPlots();
            resetSections();
            renderReturnPayloadPreview(null);
            return false;
        } finally {
        }
    }

    async function handleMastSectorSearch() {
        const gaiaId = String(gaiaSourceIdInput.value || "").trim();
        const cutoutSize = getCurrentMastCutoutSize();
        setError("");
        setMastStatus("Controllo TPF locali in corso...", "warning");
        setButtonBusy(findMastSectorsButton, "Ricerca...", true);
        try {
            const { response, data } = await fetchLocalMastSectors(gaiaId, cutoutSize);
            if (!response.ok || data.ok === false || data.status === "error") {
                lastMastSectorsResult = null;
                renderMastSectors(null);
                setMastStatus(data.message || `Errore HTTP ${response.status}`, "error");
                return;
            }

            lastMastSectorsResult = data;
            mastHasRemoteResults = false;
            renderMastSectors(data);

            const localCount = Array.isArray(data.sectors) ? data.sectors.length : 0;
            if (localCount > 0) {
                setMastStatus(`TPF locali trovati per gaia_id=${data.gaia_id}: ${localCount}.`, "success");
            } else {
                setMastStatus(`Nessun TPF locale trovato per gaia_id=${data.gaia_id}.`, "warning");
            }
        } catch (error) {
            lastMastSectorsResult = null;
            mastHasRemoteResults = false;
            renderMastSectors(null);
            const message = error instanceof Error ? error.message : String(error);
            setMastStatus(`Errore di rete durante il controllo settori: ${message}`, "error");
        } finally {
            setButtonBusy(findMastSectorsButton, "Ricerca...", false);
        }
    }

    async function handleMastRemoteSectorSearch(buttonElement) {
        const gaiaId = String(gaiaSourceIdInput.value || "").trim();
        const cutoutSize = getCurrentMastCutoutSize();
        setError("");
        setMastStatus("Ricerca completa settori TESS in corso...", "warning");
        setButtonBusy(buttonElement, "Verifica...", true);
        try {
            const { response, data } = await fetchMastSectors(gaiaId, cutoutSize);
            if (!response.ok || data.ok === false || data.status === "error") {
                setMastStatus(data.message || `Errore HTTP ${response.status}`, "error");
                return;
            }

            lastMastSectorsResult = data;
            mastHasRemoteResults = !!data.remote_available;
            renderMastSectors(data);
            if (!data.remote_available) {
                const localCount = Array.isArray(data.sectors) ? data.sectors.length : 0;
                if (localCount > 0) {
                    setMastStatus(data.message || `Controllo remoto non disponibile per gaia_id=${data.gaia_id}; mostro ${localCount} TPF locali.`, "warning");
                } else {
                    setMastStatus(data.message || `Controllo remoto non disponibile per gaia_id=${data.gaia_id}.`, "error");
                }
            } else if (data.ra !== undefined && data.dec !== undefined) {
                setMastStatus(
                    `Settori TESS trovati per gaia_id=${data.gaia_id} | ra=${data.ra} | dec=${data.dec} | gmag=${data.gmag ?? "-"}`,
                    "success"
                );
            } else {
                setMastStatus(`Settori TESS trovati per gaia_id=${data.gaia_id}.`, "success");
            }
        } catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            setMastStatus(`Errore di rete durante la ricerca completa dei settori: ${message}`, "error");
        } finally {
            setButtonBusy(buttonElement, "Verifica...", false);
        }
    }

    async function handleMastDownload(sector, buttonElement) {
        const gaiaId = String(gaiaSourceIdInput.value || "").trim();
        const cutoutSize = getCurrentMastCutoutSize();
        setError("");
        setMastStatus(`Download TPF in corso per sector=${sector}... Timeout automatico dopo circa 90 secondi.`, "warning");
        setButtonBusy(buttonElement, "Download...", true);
        try {
            const { response, data } = await downloadMastTpf(gaiaId, sector, cutoutSize);
            if (!response.ok || data.ok === false || data.status === "error") {
                setMastStatus(data.message || `Errore HTTP ${response.status}`, "error");
                return;
            }

            if (lastMastSectorsResult && Array.isArray(lastMastSectorsResult.sectors)) {
                lastMastSectorsResult = {
                    ...lastMastSectorsResult,
                    sectors: lastMastSectorsResult.sectors.map((entry) => (
                        entry.sector === Number(sector)
                            ? { ...entry, downloaded: true, filename: data.filename || entry.filename || null }
                            : entry
                    )),
                };
                renderMastSectors(lastMastSectorsResult);
            }

            setMastStatus(data.message || "TPF scaricato con successo.", "success");
            const openViewer = window.confirm("TPF pronto. Vuoi aprirlo ora nel viewer TPF esistente?");
            if (openViewer) {
                await startPipelineRun(gaiaId, String(sector));
            }
        } catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            setMastStatus(`Errore di rete durante il download TPF: ${message}`, "error");
        } finally {
            setButtonBusy(buttonElement, "Download...", false);
        }
    }

    async function handleMastReuse(sector, buttonElement) {
        const gaiaId = String(gaiaSourceIdInput.value || "").trim();
        setError("");
        setButtonBusy(buttonElement, "Apertura...", true);
        setMastStatus(`Apertura del TPF locale per sector=${sector}...`, "warning");
        try {
            const opened = await startPipelineRun(gaiaId, String(sector));
            if (opened) {
                setMastStatus(`TPF locale riusato e aperto nel viewer per sector=${sector}.`, "success");
            } else {
                setMastStatus(`Impossibile aprire il TPF locale per sector=${sector}.`, "error");
            }
        } finally {
            setButtonBusy(buttonElement, "Apertura...", false);
        }
    }

    async function saveCurrentResult() {
        if (!lastRunResult) {
            setSaveStatus("Nessun risultato disponibile da salvare.", "status-error");
            return;
        }

        setButtonBusy(saveButton, "Salvataggio...", true);
        setSaveStatus("Salvataggio sessione tecnica in corso...", "status-neutral");
        try {
            let updateSessionId = null;
            if (activeRestoredSessionId) {
                const saveChoice = await chooseSessionSaveMode(activeRestoredSessionId);
                if (saveChoice === "cancel") {
                    setSaveStatus("Salvataggio annullato dall'utente.", "status-neutral");
                    return;
                }
                if (saveChoice === "update") {
                    updateSessionId = activeRestoredSessionId;
                }
            }
            const currentMasksPayload = editingEnabled
                ? buildCurrentMasksPayload("manual-ui", 'Premi "Ricalcola light curve" per aggiornare la curva.')
                : null;
            const currentTpfPayload = buildCurrentTpfView();
            const currentLightcurvePayload = lastRunResult.lightcurve ? {
                ...lastRunResult.lightcurve,
                masks: currentMasksPayload || (lastRunResult.lightcurve.masks || null),
            } : null;
            const payloadToSave = buildCurrentSavePayload(currentTpfPayload, currentLightcurvePayload);
            if (updateSessionId) {
                payloadToSave.technical_session = { update_session_id: updateSessionId };
            }
            const response = await fetch(endpointUrls.saveUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify(payloadToSave),
            });
            const data = await response.json().catch(() => ({ status: "error", message: "Risposta JSON non valida" }));
            output.textContent = JSON.stringify(data, null, 2);

            if (!response.ok || data.status === "error") {
                setSaveStatus(data.message || `Errore HTTP ${response.status}`, "status-error");
                return;
            }

            lastRunResult = {
                ...lastRunResult,
                save: {
                    mode: data.mode,
                    saved: data.saved,
                    save_id: data.save_id,
                    saved_at_utc: data.saved_at_utc,
                    summary: data.summary || null,
                },
            };
            activeRestoredSessionId = data && data.session && data.session.session_id
                ? String(data.session.session_id)
                : activeRestoredSessionId;
            renderReturnPayloadPreview(lastRunResult);
            const savedAt = data.saved_at_utc ? ` | ${data.saved_at_utc}` : "";
            setSaveStatus(`${data.message || "Sessione tecnica salvata."}${savedAt}`, "status-success");
            refreshSavedSessions(pageContext.gaia_source_id, null);
        } catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            setSaveStatus(`Errore di rete durante il salvataggio: ${message}`, "status-error");
        } finally {
            setButtonBusy(saveButton, "Salvataggio...", false);
            saveButton.disabled = !lastRunResult;
            promoteButton.disabled = !lastRunResult;
        }
    }

    function buildCurrentSavePayload(currentTpfPayload, currentLightcurvePayload) {
        return {
            ...lastRunResult,
            tpf: currentTpfPayload || lastRunResult.tpf,
            lightcurve: currentLightcurvePayload || lastRunResult.lightcurve,
            agata_context: pageContext,
            mast_sectors: lastMastSectorsResult || null,
        };
    }

    async function promoteCurrentResult() {
        if (!lastRunResult) {
            setSaveStatus("Nessun risultato disponibile da promuovere.", "status-error");
            return;
        }
        const confirmed = window.confirm(
            "Confermi la promozione della curva nel DB fotometrico?\n\nLa curva precedente per questo TPF verra' sostituita."
        );
        if (!confirmed) {
            setSaveStatus("Promozione annullata dall'utente.", "status-neutral");
            return;
        }

        setButtonBusy(promoteButton, "Promozione...", true);
        setSaveStatus("Promozione curva in corso...", "status-neutral");
        try {
            const currentMasksPayload = editingEnabled
                ? buildCurrentMasksPayload("manual-ui", 'Premi "Ricalcola light curve" per aggiornare la curva.')
                : null;
            const currentTpfPayload = buildCurrentTpfView();
            const currentLightcurvePayload = lastRunResult.lightcurve ? {
                ...lastRunResult.lightcurve,
                masks: currentMasksPayload || (lastRunResult.lightcurve.masks || null),
            } : null;
            const payloadToPromote = buildCurrentSavePayload(currentTpfPayload, currentLightcurvePayload);
            const response = await fetch(endpointUrls.promoteUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify(payloadToPromote),
            });
            const data = await response.json().catch(() => ({ status: "error", message: "Risposta JSON non valida" }));
            output.textContent = JSON.stringify(data, null, 2);

            if (!response.ok || data.status === "error") {
                const savedAt = data.saved_at_utc ? ` | ${data.saved_at_utc}` : "";
                setSaveStatus(`${data.message || `Errore HTTP ${response.status}`}${savedAt}`, "status-error");
                return;
            }

            lastRunResult = {
                ...lastRunResult,
                save: {
                    mode: data.mode,
                    saved: data.saved,
                    save_id: data.save_id,
                    saved_at_utc: data.saved_at_utc,
                    summary: data.summary || null,
                },
            };
            renderReturnPayloadPreview(lastRunResult);
            const savedAt = data.saved_at_utc ? ` | ${data.saved_at_utc}` : "";
            setSaveStatus(`${data.message || "Promozione completata."}${savedAt}`, "status-success");
            refreshSavedSessions(pageContext.gaia_source_id, null);
        } catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            setSaveStatus(`Errore di rete durante la promozione: ${message}`, "status-error");
        } finally {
            setButtonBusy(promoteButton, "Promozione...", false);
            saveButton.disabled = !lastRunResult;
            promoteButton.disabled = !lastRunResult;
        }
    }

    async function handleRestoreSession(sessionId, buttonElement) {
        if (!sessionId) {
            return;
        }
        setError("");
        setButtonBusy(buttonElement, "Ripristino...", true);
        setSaveStatus(`Ripristino della sessione ${sessionId} in corso...`, "status-neutral");
        try {
            const response = await fetch(endpointUrls.restoreSessionUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ session_id: sessionId }),
            });
            const data = await response.json().catch(() => ({ status: "error", message: "Risposta JSON non valida" }));
            output.textContent = JSON.stringify(data, null, 2);
            if (!response.ok || data.status === "error") {
                setSaveStatus(data.message || `Errore HTTP ${response.status}`, "status-error");
                return;
            }
            await handlePipelineSuccess(data, data.message || `Sessione ${sessionId} ripristinata.`);
        } catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            setSaveStatus(`Errore di rete durante il ripristino: ${message}`, "status-error");
        } finally {
            setButtonBusy(buttonElement, "Ripristino...", false);
        }
    }

    async function handleDeleteSession(sessionId, buttonElement) {
        if (!sessionId) {
            return;
        }
        const confirmed = window.confirm(
            `Confermi l'eliminazione della sessione TPF ${sessionId}?\n\nL'operazione non modifica la fotometria gia' promossa.`
        );
        if (!confirmed) {
            return;
        }
        setError("");
        setButtonBusy(buttonElement, "Eliminazione...", true);
        setSaveStatus(`Eliminazione della sessione ${sessionId} in corso...`, "status-neutral");
        try {
            const response = await fetch(endpointUrls.deleteSessionUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ session_id: sessionId }),
            });
            const data = await response.json().catch(() => ({ status: "error", message: "Risposta JSON non valida" }));
            output.textContent = JSON.stringify(data, null, 2);
            if (!response.ok || data.status === "error") {
                setSaveStatus(data.message || `Errore HTTP ${response.status}`, "status-error");
                return;
            }
            if (activeRestoredSessionId && String(activeRestoredSessionId) === String(sessionId)) {
                activeRestoredSessionId = null;
            }
            setSaveStatus(data.message || `Sessione ${sessionId} eliminata.`, "status-success");
            refreshSavedSessions(pageContext.gaia_source_id, null);
        } catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            setSaveStatus(`Errore di rete durante l'eliminazione: ${message}`, "status-error");
        } finally {
            setButtonBusy(buttonElement, "Eliminazione...", false);
        }
    }
    function setCurrentFrameIndex(nextIndex) {
        const clampedIndex = clampFrameIndex(nextIndex);
        currentFrameIndex = clampedIndex;
        if (!lastRunResult) {
            updateFrameControls(null);
            return;
        }
        renderCurrentTpfState();
        if (lastRunResult.lightcurve && lastRunResult.lightcurve.available) {
            renderLightcurve(lastRunResult.lightcurve);
        }
    }

    recalcButton.addEventListener("click", async function () {
        if (!editingEnabled || !lastRunResult) {
            return;
        }
        setError("");
        setButtonBusy(recalcButton, "Ricalcolo...", true);
        setStatus("Ricalcolo light curve in corso...", "status-neutral");
        try {
            // Preserva overlay e target precedenti in caso di ricalcolo
            const previousOverlay = lastRunResult && lastRunResult.tpf ? lastRunResult.tpf.overlay : null;
            const previousTarget = lastRunResult ? lastRunResult.target : null;

            const masksPayload = {
                target: cloneMask(targetMask),
                background: cloneMask(backgroundMask),
            };
            const { response, data } = await runPipeline(pageContext.gaia_source_id, pageContext.sector, masksPayload);
            if (!response.ok || data.status === "error") {
                setStatus("Ricalcolo light curve fallito.", "status-error");
                setError(data.message || `Errore HTTP ${response.status}`);
                output.textContent = JSON.stringify(data, null, 2);
                renderCurrentTpfState();
                return;
            }
            await handlePipelineSuccess(data, "Light curve aggiornata.");

            // Se il nuovo target/overlay è incompleto ma c'è metadata_job_id, preserva i precedenti
            if (data.metadata_job_id && lastRunResult) {
                // Preserva overlay se vuoto e abbiamo overlay precedente
                if (lastRunResult.tpf &&
                    (!lastRunResult.tpf.overlay || !Array.isArray(lastRunResult.tpf.overlay.gaia_sources) || lastRunResult.tpf.overlay.gaia_sources.length === 0) &&
                    previousOverlay && Array.isArray(previousOverlay.gaia_sources) && previousOverlay.gaia_sources.length > 0) {
                    lastRunResult.tpf.overlay = previousOverlay;
                }
                // Preserva target se incompleto e abbiamo target precedente
                if ((!lastRunResult.target || !lastRunResult.target.ra_deg) &&
                    previousTarget && previousTarget.ra_deg) {
                    lastRunResult.target = previousTarget;
                    if (lastRunResult.tpf) {
                        lastRunResult.tpf.target_info = previousTarget;
                    }
                }
                renderCurrentTpfState();
                updateSections(lastRunResult);
            }
        } catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            setStatus("Errore di rete durante il ricalcolo.", "status-error");
            setError(message);
        } finally {
            setButtonBusy(recalcButton, "Ricalcolo...", false);
            updateEditingControls();
        }
    });

    targetModeButton.addEventListener("click", function () {
        setEditMode("target");
    });

    backgroundModeButton.addEventListener("click", function () {
        setEditMode("background");
    });

    gaiaOverlayToggleButton.addEventListener("click", function () {
        gaiaOverlayEnabled = !gaiaOverlayEnabled;
        updateGaiaOverlayToggleButton();
        renderCurrentTpfState();
        if (lastRunResult && lastRunResult.lightcurve && lastRunResult.lightcurve.available) {
            renderLightcurve(lastRunResult.lightcurve);
        }
    });

    gaiaSizeToggleButton.addEventListener("click", function () {
        gaiaSizeByMagnitudeEnabled = !gaiaSizeByMagnitudeEnabled;
        updateGaiaSizeToggleButton();
        renderCurrentTpfState();
    });

    pixelInfoToggleButton.addEventListener("click", function () {
        pixelInfoEnabled = !pixelInfoEnabled;
        updatePixelInfoToggleButton();
        updateEditingControls();
        renderCurrentTpfState();
    });

    gaiaSizeMaxMagInput.addEventListener("input", function () {
        renderCurrentTpfState();
    });

    gaiaStarsTableBox.addEventListener("click", function (event) {
        const button = event.target.closest("[data-gaia-star-sort]");
        if (!button) {
            return;
        }
        const key = button.getAttribute("data-gaia-star-sort");
        if (!key) {
            return;
        }
        if (gaiaStarsSort.key === key) {
            gaiaStarsSort = {
                key,
                direction: gaiaStarsSort.direction === "asc" ? "desc" : "asc",
            };
        } else {
            gaiaStarsSort = { key, direction: "asc" };
        }
        renderCurrentTpfState();
    });

    if (fixedScaleToggleButton) {
        fixedScaleToggleButton.addEventListener("click", function () {
            fixedColorScaleEnabled = !fixedColorScaleEnabled;
            recomputeFixedColorScaleRange();
            updateFixedScaleToggleButton();
            renderCurrentTpfState();
        });
    }

    if (lightcurveDisplayToggleButton) {
        lightcurveDisplayToggleButton.addEventListener("click", function () {
            lightcurveDisplayMode = lightcurveDisplayMode === "lines" ? "markers" : "lines";
            updateLightcurveDisplayToggleButton();
            if (lastRunResult && lastRunResult.lightcurve && lastRunResult.lightcurve.available) {
                renderLightcurve(lastRunResult.lightcurve);
            }
        });
    }

    if (lightcurveResetZoomButton) {
        lightcurveResetZoomButton.addEventListener("click", function () {
            if (!lightcurvePlot || !lightcurvePlot.data) {
                return;
            }
            Plotly.relayout(lightcurvePlot, {
                "xaxis.autorange": true,
                "yaxis.autorange": true,
            });
        });
    }

    if (lightcurveSeriesToggleButton) {
        lightcurveSeriesToggleButton.addEventListener("click", function () {
            const availableModes = getAvailableLightcurveSeriesModes(lastRunResult ? lastRunResult.lightcurve : null);
            const currentIndex = availableModes.indexOf(lightcurveSeriesMode);
            const nextIndex = currentIndex >= 0 ? (currentIndex + 1) % availableModes.length : 0;
            lightcurveSeriesMode = availableModes[nextIndex] || "flux";
            updateLightcurveSeriesToggleButton(lastRunResult ? lastRunResult.lightcurve : null);
            if (lastRunResult && lastRunResult.lightcurve && lastRunResult.lightcurve.available) {
                renderLightcurve(lastRunResult.lightcurve);
                lightcurveInfo.textContent = formatLightcurveInfo(lastRunResult.lightcurve);
            }
        });
    }

    if (findMastSectorsButton) {
        findMastSectorsButton.addEventListener("click", function () {
            handleMastSectorSearch();
        });
    }

    if (mastSectorsBox) {
        mastSectorsBox.addEventListener("click", function (event) {
            const downloadButton = event.target && typeof event.target.closest === "function"
                ? event.target.closest("[data-mast-download]")
                : null;
            const reuseButton = event.target && typeof event.target.closest === "function"
                ? event.target.closest("[data-mast-reuse]")
                : null;
            const remoteCheckButton = event.target && typeof event.target.closest === "function"
                ? event.target.closest("[data-mast-check-remote]")
                : null;

            if (downloadButton) {
                const sector = downloadButton.dataset.sector;
                if (!sector) {
                    return;
                }
                handleMastDownload(sector, downloadButton);
                return;
            }

            if (remoteCheckButton) {
                handleMastRemoteSectorSearch(remoteCheckButton);
                return;
            }

            if (!reuseButton) {
                return;
            }
            const sector = reuseButton.dataset.sector;
            if (!sector) {
                return;
            }
            handleMastReuse(sector, reuseButton);
        });
    }

    if (sessionRestoreBox) {
        sessionRestoreBox.addEventListener("click", function (event) {
            const restoreButton = event.target && typeof event.target.closest === "function"
                ? event.target.closest("[data-restore-session]")
                : null;
            const deleteButton = event.target && typeof event.target.closest === "function"
                ? event.target.closest("[data-delete-session]")
                : null;
            if (deleteButton) {
                const sessionId = deleteButton.dataset.deleteSession;
                handleDeleteSession(sessionId, deleteButton);
                return;
            }
            if (!restoreButton) {
                return;
            }
            const sessionId = restoreButton.dataset.restoreSession;
            handleRestoreSession(sessionId, restoreButton);
        });
    }

    loadVisibleFramesButton.addEventListener("click", async function () {
        if (!lastRunResult || !lastRunResult.tpf || !lastRunResult.tpf.frames || !lastRunResult.tpf.frames.available) {
            return;
        }

        const frameRange = getVisibleLightcurveFrameRange();
        if (!frameRange) {
            setStatus("Nessuna finestra valida disponibile sulla light curve per caricare i frame.", "status-error");
            return;
        }

        const confirmed = window.confirm(
            `Caricare i frame reali visibili dal cadence ${frameRange.frameStart + 1} al ${frameRange.frameEnd + 1}? L'operazione puo' richiedere tempo.`
        );
        if (!confirmed) {
            return;
        }

        setError("");
        setButtonBusy(loadVisibleFramesButton, "Caricamento frame...", true);
        setStatus("Caricamento frame TPF visibili in corso...", "status-neutral");
        try {
            const { response, data } = await loadFramesWindow(
                pageContext.gaia_source_id,
                pageContext.sector,
                frameRange.frameStart,
                frameRange.frameEnd,
            );
            if (!response.ok || data.status === "error") {
                setStatus("Caricamento frame fallito.", "status-error");
                setError(data.message || `Errore HTTP ${response.status}`);
                return;
            }
            mergeLoadedFramesIntoResult(data.frames);
            setStatus(`Frame caricati: cadence ${frameRange.frameStart + 1}-${frameRange.frameEnd + 1}.`, "status-success");
        } catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            setStatus("Errore di rete durante il caricamento frame.", "status-error");
            setError(message);
        } finally {
            setButtonBusy(loadVisibleFramesButton, "Caricamento frame...", false);
            updateFrameControls(lastRunResult ? lastRunResult.tpf : null);
        }
    });

    frameSlider.addEventListener("input", function () {
        if (frameSlider.disabled) {
            return;
        }
        setCurrentFrameIndex(parseInt(frameSlider.value, 10));
    });

    saveButton.addEventListener("click", function () {
        saveCurrentResult();
    });

    promoteButton.addEventListener("click", function () {
        promoteCurrentResult();
    });

    updateEditingControls();
    updateGaiaOverlayToggleButton();
    updateGaiaSizeToggleButton();
    updateFixedScaleToggleButton();
    updatePixelInfoToggleButton();
    updateLightcurveSeriesToggleButton(null);
    updateLightcurveDisplayToggleButton();
    setMastStatus(
        pageContext.overview_mode
            ? (
                pageContext.gaia_source_id
                    ? "Ricerca automatica dei TPF locali in corso..."
                    : 'Inserisci un Gaia source id oppure apri questa pagina con ?gaia_source_id=... per vedere subito i TPF locali.'
            )
            : 'Usa il Gaia source id sopra, poi premi "Controlla TPF locali".',
        null
    );
    renderMastSectors(null);
    renderSavedSessions(null);
    renderReturnPayloadPreview(null);
    refreshSavedSessions(pageContext.gaia_source_id, null);
    console.log("=== TPF Initialization ===");
    console.log("pageContext:", pageContext);
    console.log("overview_mode:", pageContext.overview_mode);
    console.log("gaia_source_id:", pageContext.gaia_source_id);
    console.log("sector:", pageContext.sector);

    if (pageContext.overview_mode && pageContext.gaia_source_id) {
        console.log("Branch 1: Overview mode with gaia_source_id");
        handleMastSectorSearch();
    } else if (!pageContext.overview_mode && pageContext.gaia_source_id && pageContext.sector) {
        console.log("Branch 2: Editor mode with gaia_source_id and sector");
        handleMastSectorSearch();
        startPipelineRun(pageContext.gaia_source_id, pageContext.sector);
    } else if (!pageContext.overview_mode && pageContext.gaia_source_id && !pageContext.sector) {
        console.log("Branch 3: Editor mode with gaia_source_id but NO sector - calling handleMastSectorSearch");
        handleMastSectorSearch();
    } else {
        console.log("Branch 4: No automatic action taken");
    }
})();
