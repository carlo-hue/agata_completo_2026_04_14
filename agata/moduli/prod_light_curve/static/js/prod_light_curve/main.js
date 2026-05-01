(function () {
    const appRoot = document.getElementById("prodLightCurveApp");
    if (!appRoot) {
        return;
    }

    const datasetSelectionBanner = document.getElementById("datasetSelectionBanner");
    const browseDatasetsButton = document.getElementById("browseDatasetsButton");
    const datasetBrowserPanel = document.getElementById("datasetBrowserPanel");
    const datasetBrowserList = document.getElementById("datasetBrowserList");
    const datasetSelectionSummary = document.getElementById("datasetSelectionSummary");
    const datasetSelectionDetails = document.getElementById("datasetSelectionDetails");
    const inspectButton = document.getElementById("inspectButton");
    const runButton = document.getElementById("runButton");
    const saveButton = document.getElementById("saveButton");
    const solveAstrometryButton = document.getElementById("solveAstrometryButton");
    const queryTargetsButton = document.getElementById("queryTargetsButton");
    const targetSearchRadiusInput = document.getElementById("targetSearchRadiusInput");
    const suggestComparisonsButton = document.getElementById("suggestComparisonsButton");
    const selectTargetButton = document.getElementById("selectTargetButton");
    const addComparisonButton = document.getElementById("addComparisonButton");
    const toggleCenterButton = document.getElementById("toggleCenterButton");
    const zoomInButton = document.getElementById("zoomInButton");
    const zoomOutButton = document.getElementById("zoomOutButton");
    const zoomResetButton = document.getElementById("zoomResetButton");
    const referenceImage = document.getElementById("referenceImage");
    const referenceTitle = document.getElementById("referenceTitle");
    const referenceStage = document.getElementById("referenceStage");
    const referenceViewport = document.getElementById("referenceViewport");
    const referenceOverlay = document.getElementById("referenceOverlay");
    const referenceInfo = document.getElementById("referenceInfo");
    const targetInfo = document.getElementById("targetInfo");
    const targetCandidatesBox = document.getElementById("targetCandidatesBox");
    const comparisonInfo = document.getElementById("comparisonInfo");
    const comparisonCandidatesBox = document.getElementById("comparisonCandidatesBox");
    const frameQualitySummary = document.getElementById("frameQualitySummary");
    const frameQualityBox = document.getElementById("frameQualityBox");
    const sessionsBox = document.getElementById("sessionsBox");
    const photometryInfo = document.getElementById("photometryInfo");
    const plotModeSelect = document.getElementById("plotModeSelect");
    const binSizeInput = document.getElementById("binSizeInput");
    const lightcurvePlot = document.getElementById("lightcurvePlot");
    const statusBox = document.getElementById("statusBox");
    const errorBox = document.getElementById("errorBox");
    const apertureRadiusInput = document.getElementById("apertureRadiusInput");
    const annulusInnerInput = document.getElementById("annulusInnerInput");
    const annulusOuterInput = document.getElementById("annulusOuterInput");

    const endpoints = {
        browseUrl: appRoot.dataset.browseUrl,
        inspectUrl: appRoot.dataset.inspectUrl,
        inspectStatusUrlTemplate: appRoot.dataset.inspectStatusUrlTemplate,
        inspectResultUrlTemplate: appRoot.dataset.inspectResultUrlTemplate,
        estimateSelectionUrl: appRoot.dataset.estimateSelectionUrl,
        solveAstrometryUrl: appRoot.dataset.solveAstrometryUrl,
        queryTargetsUrl: appRoot.dataset.queryTargetsUrl,
        runUrl: appRoot.dataset.runUrl,
        saveUrl: appRoot.dataset.saveUrl,
        suggestComparisonsUrl: appRoot.dataset.suggestComparisonsUrl,
        sessionsUrl: appRoot.dataset.sessionsUrl,
        restoreUrl: appRoot.dataset.restoreUrl,
        deleteUrl: appRoot.dataset.deleteUrl,
    };

    let inspectResult = null;
    let runResult = null;
    let editMode = "target";
    let selectedTarget = null;
    let selectedComparisons = [];
    let frameInclusion = new Set();
    let suppressStageClick = false;
    let centerVisible = true;
    let browserVisible = false;
    let browserState = null;
    let selectedBrowserPath = "";
    let selectionMetricsRequestId = 0;
    const referenceView = {
        scale: 1,
        offsetX: 0,
        offsetY: 0,
        baseLeft: 0,
        baseTop: 0,
        baseWidth: 0,
        baseHeight: 0,
        dragging: false,
        dragStartX: 0,
        dragStartY: 0,
        dragOriginOffsetX: 0,
        dragOriginOffsetY: 0,
    };

    function currentSelectedDatasetPath() {
        return String(selectedBrowserPath || "").trim();
    }

    function pathDisplayName(path) {
        const normalized = String(path || "").trim().replace(/[\\/]+$/, "");
        if (!normalized) {
            return "";
        }
        const parts = normalized.split(/[/\\]/);
        return parts[parts.length - 1] || normalized;
    }

    function updateDatasetSelectionBanner() {
        datasetSelectionBanner.textContent = selectedBrowserPath
            ? pathDisplayName(selectedBrowserPath)
            : "nessuna osservazione selezionata";
        inspectButton.disabled = !selectedBrowserPath;
    }

    function setStatus(message, tone) {
        statusBox.textContent = message || "-";
        statusBox.className = `status-box ${tone || "status-neutral"}`;
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

    function setBusy(button, busy, label) {
        if (!button) {
            return;
        }
        if (!button.dataset.originalText) {
            button.dataset.originalText = button.textContent;
        }
        button.disabled = busy;
        button.textContent = busy ? label : button.dataset.originalText;
    }

    function updateDebugPayload(_) {
        // Payload tecnico nascosto nella UI corrente.
    }

    async function postJson(url, payload) {
        const response = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const data = await response.json().catch(() => ({
            status: "error",
            message: "Risposta JSON non valida",
        }));
        return { response, data };
    }

    async function getJson(url) {
        const response = await fetch(url, { method: "GET" });
        const text = await response.text();
        let data;
        try {
            data = text ? JSON.parse(text) : {
                status: "error",
                message: "Risposta vuota dal server",
            };
        } catch (_) {
            data = {
                status: "error",
                message: `Risposta non JSON dal server (HTTP ${response.status})`,
            };
        }
        return { response, data };
    }

    function resolveJobUrl(template, jobId) {
        return String(template || "").replace("__JOB_ID__", encodeURIComponent(jobId));
    }

    function renderDatasetBrowser(payload) {
        browserState = payload;
        if (!selectedBrowserPath) {
            selectedBrowserPath = payload.current_path || "";
        }
        datasetBrowserList.innerHTML = "";

        const entries = (payload.directories || []).map(function (item) {
            return {
                kind: "directory",
                name: item.name,
                path: item.path,
                meta: Number(item.direct_fits_count || 0) > 0 ? `(${Number(item.direct_fits_count || 0)} FITS)` : "",
                directFitsCount: Number(item.direct_fits_count || 0),
            };
        });

        if (!entries.length) {
            datasetBrowserList.textContent = "Nessuna osservazione disponibile.";
            datasetBrowserList.className = "frame-quality-box empty-state";
            return;
        }

        datasetBrowserList.className = "frame-quality-box";
        entries.forEach(function (item) {
            const row = document.createElement("div");
            row.className = `dataset-browser-entry${selectedBrowserPath === item.path ? " is-selected" : ""}`;

            const textWrap = document.createElement("div");
            textWrap.className = "dataset-browser-entry-main";
            textWrap.addEventListener("click", function () {
                selectedBrowserPath = item.path;
                renderDatasetBrowser(browserState);
            });
            const name = document.createElement("div");
            name.className = "dataset-browser-entry-name";
            name.textContent = item.name;
            const meta = document.createElement("div");
            meta.className = "dataset-browser-entry-meta";
            meta.textContent = item.meta;
            textWrap.appendChild(name);
            if (item.meta) {
                textWrap.appendChild(meta);
            }

            row.appendChild(textWrap);
            datasetBrowserList.appendChild(row);
        });
        renderDatasetSelectionDetails(entries);
    }

    function renderDatasetSelectionDetails(entries) {
        const selectedEntry = (entries || []).find(function (item) {
            return item.path === selectedBrowserPath;
        }) || null;

        if (!selectedEntry) {
            datasetSelectionSummary.textContent = "Nessuna cartella selezionata.";
            datasetSelectionDetails.textContent = "Seleziona una voce dalla lista per vedere i dettagli del dataset.";
            selectedBrowserPath = "";
            updateDatasetSelectionBanner();
            return;
        }

        selectedBrowserPath = selectedEntry.path;
        updateDatasetSelectionBanner();
        datasetSelectionSummary.textContent = selectedEntry.path;
        const fitsCount = Number(selectedEntry.directFitsCount || 0);
        datasetSelectionDetails.textContent = fitsCount > 0
            ? `Sono stati rilevati ${fitsCount} FITS diretti in questa cartella. Premi Selezione reference image per avviare l'analisi.`
            : "In questa cartella non risultano FITS diretti.";
    }

    async function loadDatasetBrowser(path) {
        setError("");
        setBusy(browseDatasetsButton, true, "Carico...");
        try {
            const { response, data } = await postJson(endpoints.browseUrl, {
                path: path || currentSelectedDatasetPath() || appRoot.dataset.defaultDatasetRoot || "",
            });
            if (!response.ok || data.status === "error") {
                setStatus("Navigazione cartelle fallita.", "status-error");
                setError(data.message || `Errore HTTP ${response.status}`);
                return;
            }
            renderDatasetBrowser(data);
            browserVisible = true;
            datasetBrowserPanel.classList.remove("hidden");
            setStatus("Browser cartelle aggiornato.", "status-success");
        } catch (error) {
            setStatus("Errore di rete durante la navigazione cartelle.", "status-error");
            setError(error instanceof Error ? error.message : String(error));
        } finally {
            setBusy(browseDatasetsButton, false, "Carico...");
        }
    }

    function toggleDatasetBrowser() {
        browserVisible = !browserVisible;
        datasetBrowserPanel.classList.toggle("hidden", !browserVisible);
        if (browserVisible && !browserState) {
            selectedBrowserPath = currentSelectedDatasetPath() || appRoot.dataset.defaultDatasetRoot || "";
            loadDatasetBrowser(currentSelectedDatasetPath() || appRoot.dataset.defaultDatasetRoot || "");
        }
    }

    function renderReference(result) {
        const reference = result && result.reference;
        if (!reference || !reference.preview_png_base64) {
            referenceTitle.textContent = "Reference image";
            referenceImage.classList.add("hidden");
            referenceViewport.classList.add("hidden");
            referenceOverlay.classList.add("hidden");
            referenceInfo.textContent = "Nessuna reference image disponibile.";
            return;
        }
        const observationName = pathDisplayName(currentSelectedDatasetPath());
        referenceTitle.textContent = observationName
            ? `Reference image (${observationName})`
            : "Reference image";
        referenceImage.src = `data:image/png;base64,${reference.preview_png_base64}`;
        referenceImage.classList.remove("hidden");
        referenceViewport.classList.remove("hidden");
        referenceOverlay.classList.remove("hidden");
        resetReferenceView();
        updateReferenceViewportLayout();
        referenceInfo.textContent = `${reference.source.filename} | ${reference.shape[1]}x${reference.shape[0]} | mode=${reference.mode}`;
        renderOverlay();
    }

    function nearestDetectedSource(target, result) {
        const sources = (((result || {}).targeting || {}).detected_sources) || [];
        if (!target || !sources.length) {
            return null;
        }
        let best = null;
        let bestDistance = Infinity;
        sources.forEach(function (item) {
            const distance = Math.hypot(
                Number(item.x || 0) - Number(target.x || 0),
                Number(item.y || 0) - Number(target.y || 0),
            );
            if (distance < bestDistance) {
                bestDistance = distance;
                best = item;
            }
        });
        return bestDistance <= 15 ? best : null;
    }

    const selectionMetricHeaders = [
        { key: "label", label: "Selezione" },
        { key: "x", label: "x", numeric: true },
        { key: "y", label: "y", numeric: true },
        { key: "ra_deg", label: "RA", numeric: true },
        { key: "dec_deg", label: "Dec", numeric: true },
        { key: "peak_adu", label: "Peak", numeric: true },
        { key: "aperture_sum_adu", label: "Apertura lorda", numeric: true },
        { key: "aperture_net_adu", label: "Apertura netta", numeric: true },
        { key: "annulus_mean_adu", label: "Media annulus", numeric: true },
        { key: "annulus_median_adu", label: "Mediana annulus", numeric: true },
    ];

    function buildSelectionMetricsRow(item, label) {
        return {
            label: label || "-",
            x: Number(item.x).toFixed(2),
            y: Number(item.y).toFixed(2),
            ra_deg: item.ra_deg !== undefined && item.ra_deg !== null && Number.isFinite(Number(item.ra_deg))
                ? Number(item.ra_deg).toFixed(3)
                : null,
            dec_deg: item.dec_deg !== undefined && item.dec_deg !== null && Number.isFinite(Number(item.dec_deg))
                ? Number(item.dec_deg).toFixed(3)
                : null,
            peak_adu: item.peak_adu !== undefined && item.peak_adu !== null && Number.isFinite(Number(item.peak_adu))
                ? Math.round(Number(item.peak_adu))
                : null,
            aperture_sum_adu: item.aperture_sum_adu !== undefined && item.aperture_sum_adu !== null && Number.isFinite(Number(item.aperture_sum_adu))
                ? Math.round(Number(item.aperture_sum_adu))
                : null,
            aperture_net_adu: item.aperture_net_adu !== undefined && item.aperture_net_adu !== null && Number.isFinite(Number(item.aperture_net_adu))
                ? Math.round(Number(item.aperture_net_adu))
                : null,
            annulus_mean_adu: item.annulus_mean_adu !== undefined && item.annulus_mean_adu !== null && Number.isFinite(Number(item.annulus_mean_adu))
                ? Number(item.annulus_mean_adu).toFixed(1)
                : null,
            annulus_median_adu: item.annulus_median_adu !== undefined && item.annulus_median_adu !== null && Number.isFinite(Number(item.annulus_median_adu))
                ? Number(item.annulus_median_adu).toFixed(1)
                : null,
            _raw: item,
        };
    }

    async function refreshSelectionMetrics() {
        if (!inspectResult) {
            return;
        }
        const datasetPath = currentSelectedDatasetPath();
        if (!datasetPath) {
            return;
        }
        const hasTarget = !!(
            selectedTarget
            && Number.isFinite(Number(selectedTarget.x))
            && Number.isFinite(Number(selectedTarget.y))
        );
        const validComparisons = selectedComparisons.filter(function (item) {
            return Number.isFinite(Number(item.x)) && Number.isFinite(Number(item.y));
        });
        if (!hasTarget && !validComparisons.length) {
            return;
        }

        const requestId = ++selectionMetricsRequestId;
        try {
            const { response, data } = await postJson(endpoints.estimateSelectionUrl, {
                dataset_path: datasetPath,
                reference_path: inspectResult && inspectResult.reference && inspectResult.reference.source
                    ? inspectResult.reference.source.path
                    : null,
                target: hasTarget ? selectedTarget : null,
                comparison_stars: validComparisons,
                aperture_radius: Number(apertureRadiusInput.value),
                annulus_inner_radius: Number(annulusInnerInput.value),
                annulus_outer_radius: Number(annulusOuterInput.value),
            });
            if (requestId !== selectionMetricsRequestId) {
                return;
            }
            if (!response.ok || data.status === "error") {
                return;
            }
            if (hasTarget && data.target) {
                selectedTarget = { ...selectedTarget, ...data.target };
            }
            if (validComparisons.length && Array.isArray(data.comparison_stars)) {
                selectedComparisons = selectedComparisons.map(function (item, index) {
                    const metrics = data.comparison_stars[index];
                    return metrics ? { ...item, ...metrics } : item;
                });
            }
            renderTargeting(inspectResult);
        } catch (_) {
            // Manteniamo la UI reattiva anche se la stima ADU fallisce.
        }
    }

    function renderOverlay() {
        referenceOverlay.innerHTML = "";
        if (!inspectResult || !inspectResult.reference) {
            return;
        }
        const width = Number(inspectResult.reference.shape[1]);
        const height = Number(inspectResult.reference.shape[0]);
        const stageWidth = referenceStage.clientWidth || 1;
        const stageHeight = referenceStage.clientHeight || 1;
        const centerPixel = inspectResult.reference.center_pixel || null;
        const canvas = document.createElement("canvas");
        canvas.className = "overlay-canvas";
        const dpr = window.devicePixelRatio || 1;
        canvas.width = Math.max(1, Math.round(stageWidth * dpr));
        canvas.height = Math.max(1, Math.round(stageHeight * dpr));
        canvas.style.width = `${stageWidth}px`;
        canvas.style.height = `${stageHeight}px`;
        referenceOverlay.appendChild(canvas);
        const ctx = canvas.getContext("2d");
        if (!ctx) {
            return;
        }
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, stageWidth, stageHeight);
        ctx.imageSmoothingEnabled = true;

        function fitsYToDisplayY(y) {
            return (height - 1) - Number(y);
        }

        function imagePixelToStagePoint(x, y) {
            const sourceX = (Number(x) / width) * referenceView.baseWidth;
            const sourceY = (fitsYToDisplayY(y) / height) * referenceView.baseHeight;
            const localX = ((sourceX - (referenceView.baseWidth / 2)) * referenceView.scale)
                + referenceView.offsetX
                + (referenceView.baseWidth / 2);
            const localY = ((sourceY - (referenceView.baseHeight / 2)) * referenceView.scale)
                + referenceView.offsetY
                + (referenceView.baseHeight / 2);
            return {
                x: referenceView.baseLeft + localX,
                y: referenceView.baseTop + localY,
            };
        }

        function imageRadiusToStageRadius(radiusPx) {
            const scaleX = referenceView.baseWidth / width;
            return Number(radiusPx) * scaleX * referenceView.scale;
        }

        function drawCircle(cx, cy, radius, color, lineWidth) {
            ctx.beginPath();
            ctx.arc(cx, cy, Math.max(0.01, radius), 0, Math.PI * 2);
            ctx.strokeStyle = color;
            ctx.lineWidth = lineWidth;
            ctx.lineCap = "round";
            ctx.lineJoin = "round";
            ctx.stroke();
        }

        function drawText(x, y, text, color) {
            ctx.font = "700 11px system-ui, sans-serif";
            ctx.lineJoin = "round";
            ctx.miterLimit = 2;
            ctx.strokeStyle = "rgba(0, 0, 0, 0.82)";
            ctx.lineWidth = 3;
            ctx.strokeText(String(text), x + 10, y - 10);
            ctx.fillStyle = color;
            ctx.fillText(String(text), x + 10, y - 10);
        }

        function drawCrosshair(center) {
            if (!center) {
                return;
            }
            const point = imagePixelToStagePoint(center.x, center.y);
            const cx = point.x;
            const cy = point.y;
            const armLength = 15;
            const gap = 7;
            ctx.strokeStyle = "rgba(255, 205, 104, 0.95)";
            ctx.lineWidth = 2;
            ctx.lineCap = "round";
            ctx.beginPath();
            ctx.moveTo(cx - armLength, cy);
            ctx.lineTo(cx - gap, cy);
            ctx.moveTo(cx + gap, cy);
            ctx.lineTo(cx + armLength, cy);
            ctx.moveTo(cx, cy - armLength);
            ctx.lineTo(cx, cy - gap);
            ctx.moveTo(cx, cy + gap);
            ctx.lineTo(cx, cy + armLength);
            ctx.stroke();
        }

        function getPhotometryRingRadii() {
            const radii = [
                { value: Number(apertureRadiusInput.value), klass: "aperture", title: "aperture" },
                { value: Number(annulusInnerInput.value), klass: "annulus-inner", title: "annulus inner" },
                { value: Number(annulusOuterInput.value), klass: "annulus-outer", title: "annulus outer" },
            ];
            return radii.filter(function (item) {
                return Number.isFinite(item.value) && item.value > 0;
            });
        }

        function addRing(x, y, radiusPx, klass, title, role) {
            const point = imagePixelToStagePoint(x, y);
            const radius = imageRadiusToStageRadius(radiusPx);
            const color = role === "comparison"
                ? "rgba(156, 97, 255, 0.98)"
                : "rgba(235, 54, 54, 0.98)";
            const lineWidth = role === "comparison" ? 1.15 : 1.25;
            drawCircle(point.x, point.y, radius, color, lineWidth);
        }

        if (centerVisible) {
            drawCrosshair(centerPixel);
        }

        if (selectedTarget) {
            getPhotometryRingRadii().forEach(function (item) {
                addRing(Number(selectedTarget.x), Number(selectedTarget.y), item.value, item.klass, item.title, "target");
            });
        }
        selectedComparisons.forEach((item, index) => {
            getPhotometryRingRadii().forEach(function (ring) {
                addRing(Number(item.x), Number(item.y), ring.value, ring.klass, `comparison ${index + 1} ${ring.title}`, "comparison");
            });
            const point = imagePixelToStagePoint(item.x, item.y);
            drawText(point.x, point.y, index + 1, "rgba(156, 97, 255, 0.98)");
        });
    }

    function renderTargeting(result) {
        const targeting = result.targeting || {};
        selectedTarget = selectedTarget || targeting.auto_target || null;
        targetInfo.innerHTML = "";
        if (!selectedTarget) {
            targetInfo.textContent = "Target non selezionato.";
            targetInfo.className = "detail-text";
        } else {
            targetInfo.className = "table-box";
            targetInfo.appendChild(buildCandidateTable({
                headers: selectionMetricHeaders,
                rows: [buildSelectionMetricsRow(selectedTarget, "target")],
            }));
        }

        const candidates = targeting.target_candidates || [];
        const targetCandidatesLoaded = !!targeting.target_candidates_loaded;
        targetCandidatesBox.innerHTML = "";
        if (!candidates.length) {
            targetCandidatesBox.textContent = targetCandidatesLoaded
                ? "Nessun candidato catalogato disponibile."
                : 'Premi "Cerca target noti" per lanciare la query catalografica.';
            targetCandidatesBox.className = "list-box empty-state";
        } else {
            targetCandidatesBox.className = "table-box";
            targetCandidatesBox.appendChild(buildCandidateTable({
                headers: [
                    { key: "label", label: "Target" },
                    { key: "catalog_name", label: "Catalogo" },
                    { key: "distance_from_center_px", label: "d px", numeric: true },
                ],
                rows: candidates,
                isSelected: function (item) {
                    return !!selectedTarget
                        && Number(selectedTarget.x) === Number(item.x)
                        && Number(selectedTarget.y) === Number(item.y);
                },
                onClick: function (item) {
                    selectedTarget = { ...item, x: item.x, y: item.y, label: item.label, mode: "catalogo" };
                    renderTargeting(inspectResult);
                    renderOverlay();
                    void refreshSelectionMetrics();
                },
            }));
        }

        const comparisonCandidates = (result.comparison_stars || {}).candidates || [];
        const comparisonCandidatesLoaded = !!((result.comparison_stars || {}).comparison_candidates_loaded);
        if (!selectedComparisons.length && comparisonCandidatesLoaded) {
            selectedComparisons = ((result.comparison_stars || {}).auto_selected || []).slice();
        }
        comparisonCandidatesBox.innerHTML = "";
        if (!comparisonCandidates.length && selectedComparisons.length) {
            comparisonCandidatesBox.className = "table-box";
            comparisonCandidatesBox.appendChild(buildCandidateTable({
                headers: selectionMetricHeaders,
                rows: selectedComparisons.map(function (item, index) {
                    return buildSelectionMetricsRow(item, `man ${index + 1}`);
                }),
                isSelected: function () {
                    return true;
                },
                onClick: function (item) {
                    toggleComparison(item._raw);
                },
            }));
        } else if (!comparisonCandidates.length) {
            comparisonCandidatesBox.textContent = comparisonCandidatesLoaded
                ? "Nessun candidato disponibile."
                : 'Premi "Suggerisci comparison stars" per calcolare il ranking automatico.';
            comparisonCandidatesBox.className = "list-box empty-state";
        } else {
            comparisonCandidatesBox.className = "table-box";
            comparisonCandidatesBox.appendChild(buildCandidateTable({
                headers: [
                    { key: "snr", label: "SNR", numeric: true },
                    { key: "score", label: "Score", numeric: true },
                    { key: "selection_reason_short", label: "Nota" },
                ],
                rows: comparisonCandidates.map((item) => ({
                    ...item,
                    selection_reason_short: item.selection_reasons && item.selection_reasons.length ? item.selection_reasons[0] : "",
                })),
                isSelected: function (item) {
                    return selectedComparisons.some((current) => Number(current.x) === Number(item.x) && Number(current.y) === Number(item.y));
                },
                onClick: function (item) {
                    toggleComparison(item);
                },
            }));
        }
        renderOverlay();
    }

    async function handleQueryTargets() {
        if (!inspectResult) {
            return;
        }
        const datasetPath = currentSelectedDatasetPath();
        if (!datasetPath) {
            setError("Seleziona prima una sessione.");
            return;
        }
        const searchRadiusArcsec = Math.max(1, Number(targetSearchRadiusInput.value || 50));
        setError("");
        setBusy(queryTargetsButton, true, "Ricerca...");
        setStatus(`Query target noti in corso entro ${searchRadiusArcsec.toFixed(0)} arcsec...`, "status-neutral");
        try {
            const { response, data } = await postJson(endpoints.queryTargetsUrl, {
                dataset_path: datasetPath,
                reference_path: inspectResult && inspectResult.reference && inspectResult.reference.source
                    ? inspectResult.reference.source.path
                    : null,
                search_radius_arcsec: searchRadiusArcsec,
            });
            updateDebugPayload(data);
            if (!response.ok || data.status === "error") {
                setStatus("Query target fallita.", "status-error");
                setError(data.message || `Errore HTTP ${response.status}`);
                return;
            }
            inspectResult = {
                ...inspectResult,
                dataset: data.dataset || inspectResult.dataset,
                targeting: {
                    ...(inspectResult.targeting || {}),
                    ...(data.targeting || {}),
                },
            };
            renderTargeting(inspectResult);
            const effectiveRadius = data.targeting && data.targeting.search_radius_arcsec !== undefined && data.targeting.search_radius_arcsec !== null
                ? Number(data.targeting.search_radius_arcsec)
                : searchRadiusArcsec;
            const centerSkyUsed = data.targeting && data.targeting.center_sky_used
                ? data.targeting.center_sky_used
                : null;
            const centerSummary = centerSkyUsed
                && Number.isFinite(Number(centerSkyUsed.ra_deg))
                && Number.isFinite(Number(centerSkyUsed.dec_deg))
                ? ` centro usato: RA=${Number(centerSkyUsed.ra_deg).toFixed(3)} Dec=${Number(centerSkyUsed.dec_deg).toFixed(3)}`
                : "";
            setStatus(
                `${data.message || "Candidati target aggiornati."} [raggio usato: ${effectiveRadius.toFixed(0)} arcsec${centerSummary}]`,
                "status-success",
            );
        } catch (error) {
            setStatus("Errore di rete durante la query target.", "status-error");
            setError(error instanceof Error ? error.message : String(error));
        } finally {
            setBusy(queryTargetsButton, false, "Ricerca...");
        }
    }

    async function handleSolveAstrometry() {
        if (!inspectResult || !inspectResult.reference || !inspectResult.reference.source) {
            return;
        }
        setError("");
        setBusy(solveAstrometryButton, true, "Risolvo...");
        setStatus("Plate solving della reference image in corso...", "status-neutral");
        try {
            const { response, data } = await postJson(endpoints.solveAstrometryUrl, {
                reference_path: inspectResult.reference.source.path,
            });
            updateDebugPayload(data);
            if (!response.ok || data.status === "error") {
                setStatus("Plate solving fallito.", "status-error");
                setError(data.message || `Errore HTTP ${response.status}`);
                return;
            }
            inspectResult = {
                ...inspectResult,
                reference: data.reference || inspectResult.reference,
                astrometry: data.astrometry || null,
            };
            renderReference(inspectResult);
            await refreshSelectionMetrics();
            setStatus(data.message || "Plate solving completato.", "status-success");
        } catch (error) {
            setStatus("Errore di rete durante il plate solving.", "status-error");
            setError(error instanceof Error ? error.message : String(error));
        } finally {
            setBusy(solveAstrometryButton, false, "Risolvo...");
        }
    }

    async function handleSuggestComparisons() {
        if (!inspectResult) {
            return;
        }
        const datasetPath = currentSelectedDatasetPath();
        if (!datasetPath) {
            setError("Seleziona prima una sessione.");
            return;
        }
        setError("");
        setBusy(suggestComparisonsButton, true, "Calcolo...");
        setStatus("Selezione automatica comparison stars in corso...", "status-neutral");
        try {
            const { response, data } = await postJson(endpoints.suggestComparisonsUrl, {
                dataset_path: datasetPath,
                target: selectedTarget,
            });
            updateDebugPayload(data);
            if (!response.ok || data.status === "error") {
                setStatus("Suggerimento comparison stars fallito.", "status-error");
                setError(data.message || `Errore HTTP ${response.status}`);
                return;
            }
            inspectResult = {
                ...inspectResult,
                dataset: data.dataset || inspectResult.dataset,
                comparison_stars: {
                    ...(inspectResult.comparison_stars || {}),
                    ...(data.comparison_stars || {}),
                },
            };
            if (!selectedComparisons.length) {
                selectedComparisons = ((data.comparison_stars || {}).auto_selected || []).slice();
            }
            renderTargeting(inspectResult);
            await refreshSelectionMetrics();
            setStatus(data.message || "Comparison stars aggiornate.", "status-success");
        } catch (error) {
            setStatus("Errore di rete durante il suggerimento comparison stars.", "status-error");
            setError(error instanceof Error ? error.message : String(error));
        } finally {
            setBusy(suggestComparisonsButton, false, "Calcolo...");
        }
    }

    function buildCandidateTable(config) {
        const table = document.createElement("table");
        table.className = "candidate-table";

        const thead = document.createElement("thead");
        const headRow = document.createElement("tr");
        config.headers.forEach((header) => {
            const th = document.createElement("th");
            th.textContent = header.label;
            headRow.appendChild(th);
        });
        thead.appendChild(headRow);
        table.appendChild(thead);

        const tbody = document.createElement("tbody");
        config.rows.forEach((item) => {
            const tr = document.createElement("tr");
            if (config.isSelected && config.isSelected(item)) {
                tr.classList.add("is-selected");
            }
            tr.addEventListener("click", function () {
                config.onClick(item);
            });

            config.headers.forEach((header) => {
                const td = document.createElement("td");
                const rawValue = item[header.key];
                td.textContent = rawValue === null || rawValue === undefined || rawValue === "" ? "-" : String(rawValue);
                if (header.numeric) {
                    td.classList.add("is-numeric");
                } else if ((rawValue === null || rawValue === undefined ? 0 : String(rawValue).length) < 14) {
                    td.classList.add("is-compact");
                }
                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });

        table.appendChild(tbody);
        return table;
    }

    function clamp(value, min, max) {
        return Math.min(max, Math.max(min, value));
    }

    function resetReferenceView() {
        referenceView.scale = 1;
        referenceView.offsetX = 0;
        referenceView.offsetY = 0;
        applyReferenceTransform();
    }

    function updateReferenceViewportLayout() {
        if (!inspectResult || !inspectResult.reference) {
            return;
        }
        const imageWidth = Number(inspectResult.reference.shape[1] || 1);
        const imageHeight = Number(inspectResult.reference.shape[0] || 1);
        const stageWidth = referenceStage.clientWidth || 1;
        const stageHeight = referenceStage.clientHeight || 1;
        const imageAspect = imageWidth / imageHeight;
        const stageAspect = stageWidth / stageHeight;
        let baseWidth = stageWidth;
        let baseHeight = stageHeight;
        if (imageAspect > stageAspect) {
            baseHeight = baseWidth / imageAspect;
        } else {
            baseWidth = baseHeight * imageAspect;
        }
        referenceView.baseWidth = baseWidth;
        referenceView.baseHeight = baseHeight;
        referenceView.baseLeft = (stageWidth - baseWidth) / 2;
        referenceView.baseTop = (stageHeight - baseHeight) / 2;
        referenceViewport.style.left = `${referenceView.baseLeft}px`;
        referenceViewport.style.top = `${referenceView.baseTop}px`;
        referenceViewport.style.width = `${referenceView.baseWidth}px`;
        referenceViewport.style.height = `${referenceView.baseHeight}px`;
        applyReferenceTransform();
        renderOverlay();
    }

    function applyReferenceTransform() {
        if (!referenceViewport) {
            return;
        }
        referenceViewport.style.transform = `translate(${referenceView.offsetX}px, ${referenceView.offsetY}px) scale(${referenceView.scale})`;
        renderOverlay();
    }

    function setZoomControlsEnabled(enabled) {
        zoomInButton.disabled = !enabled;
        zoomOutButton.disabled = !enabled;
        zoomResetButton.disabled = !enabled;
    }

    function setReferenceScale(nextScale, anchorStageX, anchorStageY) {
        const clampedScale = clamp(nextScale, 1, 8);
        const currentScale = referenceView.scale;
        if (clampedScale === currentScale) {
            return;
        }
        const centerX = referenceView.baseLeft + (referenceView.baseWidth / 2);
        const centerY = referenceView.baseTop + (referenceView.baseHeight / 2);
        const anchorX = anchorStageX - centerX;
        const anchorY = anchorStageY - centerY;
        const sourceX = (anchorX - referenceView.offsetX) / currentScale;
        const sourceY = (anchorY - referenceView.offsetY) / currentScale;
        referenceView.scale = clampedScale;
        referenceView.offsetX = anchorX - (sourceX * clampedScale);
        referenceView.offsetY = anchorY - (sourceY * clampedScale);
        applyReferenceTransform();
    }

    function zoomReference(factor) {
        const stageRect = referenceStage.getBoundingClientRect();
        const anchorX = stageRect.width / 2;
        const anchorY = stageRect.height / 2;
        setReferenceScale(referenceView.scale * factor, anchorX, anchorY);
    }

    function toggleComparison(item) {
        const index = selectedComparisons.findIndex((current) => Number(current.x) === Number(item.x) && Number(current.y) === Number(item.y));
        if (index >= 0) {
            selectedComparisons.splice(index, 1);
        } else {
            selectedComparisons.push({ x: item.x, y: item.y });
        }
        renderTargeting(inspectResult);
        void refreshSelectionMetrics();
    }

    function renderFrameQuality(result) {
        const frameQuality = result.frame_quality || {};
        const frames = frameQuality.frames || [];
        if (!frameInclusion.size) {
            frames.forEach((item) => {
                if (!item.suspect) {
                    frameInclusion.add(item.index);
                }
            });
            if (!frameInclusion.size) {
                frames.forEach((item) => frameInclusion.add(item.index));
            }
        }

        frameQualitySummary.textContent = `frame=${frames.length} | sospetti=${frameQuality.summary ? frameQuality.summary.suspect_count : "-"}`;
        frameQualityBox.innerHTML = "";
        if (!frames.length) {
            frameQualityBox.textContent = "Nessun frame disponibile.";
            frameQualityBox.className = "frame-quality-box empty-state";
            return;
        }
        frameQualityBox.className = "frame-quality-box";
        frames.forEach((item) => {
            const row = document.createElement("button");
            row.type = "button";
            const enabled = frameInclusion.has(item.index);
            row.className = `frame-row${enabled ? " is-selected" : ""}${item.suspect ? " is-suspect" : ""}`;
            row.textContent = `#${item.index + 1} ${item.filename} | score=${item.quality_score ?? "-"}${item.suspect ? " | sospetto" : ""}`;
            row.title = (item.suspect_reasons || []).join(", ");
            row.addEventListener("click", function () {
                if (frameInclusion.has(item.index)) {
                    frameInclusion.delete(item.index);
                } else {
                    frameInclusion.add(item.index);
                }
                renderFrameQuality(result);
            });
            frameQualityBox.appendChild(row);
        });
    }

    function renderSessions(sessionsPayload) {
        const sessions = sessionsPayload && sessionsPayload.sessions ? sessionsPayload.sessions : [];
        sessionsBox.innerHTML = "";
        if (!sessions.length) {
            sessionsBox.textContent = "Nessuna sessione tecnica trovata per questo dataset.";
            sessionsBox.className = "frame-quality-box empty-state";
            return;
        }
        sessionsBox.className = "frame-quality-box";
        sessions.forEach((item) => {
            const row = document.createElement("div");
            row.className = "session-row";
            row.innerHTML = `<div>${item.session_id}</div><div>${item.saved_at_utc || "-"}</div>`;
            const restoreButton = document.createElement("button");
            restoreButton.type = "button";
            restoreButton.className = "button-secondary";
            restoreButton.textContent = "Ripristina";
            restoreButton.addEventListener("click", function () {
                handleRestore(item.session_id, restoreButton);
            });
            const deleteButton = document.createElement("button");
            deleteButton.type = "button";
            deleteButton.className = "button-secondary";
            deleteButton.textContent = "Elimina";
            deleteButton.addEventListener("click", function () {
                handleDelete(item.session_id, deleteButton);
            });
            row.appendChild(restoreButton);
            row.appendChild(deleteButton);
            sessionsBox.appendChild(row);
        });
    }

    function renderPhotometry(result) {
        const photometry = result.photometry;
        if (!photometry || !photometry.series) {
            photometryInfo.textContent = "Fotometria non ancora eseguita.";
            Plotly.purge(lightcurvePlot);
            return;
        }
        const rawX = photometry.series.time_jd || [];
        const rawY = photometry.series.differential_flux || [];
        const binSize = Math.max(1, Number.parseInt(binSizeInput.value || "1", 10) || 1);
        const plotMode = plotModeSelect.value || "lines+markers";
        const binned = buildBinnedSeries(rawX, rawY, binSize);
        photometryInfo.textContent = `frame usati=${photometry.summary.used_frames} | scatter=${photometry.summary.normalized_flux_scatter ?? "-"} | bin=${binSize}`;
        Plotly.newPlot(lightcurvePlot, [{
            x: binned.x,
            y: binned.y,
            mode: plotMode,
            type: "scatter",
            marker: { size: 6, color: "#b97411" },
            line: { color: "#365b76", width: 2 },
            name: "Differential Flux",
        }], {
            margin: { t: 20, r: 20, b: 40, l: 55 },
            xaxis: { title: "JD" },
            yaxis: { title: "Differential Flux" },
            paper_bgcolor: "rgba(0,0,0,0)",
            plot_bgcolor: "rgba(0,0,0,0)",
        }, { responsive: true });
    }

    function buildBinnedSeries(xValues, yValues, binSize) {
        if (binSize <= 1) {
            return {
                x: xValues.slice(),
                y: yValues.slice(),
            };
        }
        const pairs = [];
        for (let index = 0; index < Math.min(xValues.length, yValues.length); index += 1) {
            const x = Number(xValues[index]);
            const y = Number(yValues[index]);
            if (!Number.isFinite(x) || !Number.isFinite(y)) {
                continue;
            }
            pairs.push({ x, y });
        }
        const binnedX = [];
        const binnedY = [];
        for (let start = 0; start < pairs.length; start += binSize) {
            const chunk = pairs.slice(start, start + binSize);
            if (!chunk.length) {
                continue;
            }
            const meanX = chunk.reduce((sum, item) => sum + item.x, 0) / chunk.length;
            const meanY = chunk.reduce((sum, item) => sum + item.y, 0) / chunk.length;
            binnedX.push(meanX);
            binnedY.push(meanY);
        }
        return { x: binnedX, y: binnedY };
    }

    async function refreshSessions() {
        const datasetPath = currentSelectedDatasetPath();
        if (!datasetPath) {
            renderSessions({ sessions: [] });
            return;
        }
        const { data } = await postJson(endpoints.sessionsUrl, { dataset_path: datasetPath });
        renderSessions(data);
    }

    function buildRunPayload() {
        return {
            dataset_path: currentSelectedDatasetPath(),
            target: selectedTarget,
            comparison_stars: selectedComparisons,
            included_frame_indices: Array.from(frameInclusion).sort((a, b) => a - b),
            photometry: {
                aperture_radius: Number(apertureRadiusInput.value),
                annulus_inner_radius: Number(annulusInnerInput.value),
                annulus_outer_radius: Number(annulusOuterInput.value),
            },
        };
    }

    function rerenderPhotometryFromState() {
        if (!runResult) {
            return;
        }
        renderPhotometry(runResult);
    }

    function stagePointToPixel(event) {
        if (!inspectResult || !inspectResult.reference || !referenceView.baseWidth || !referenceView.baseHeight) {
            return null;
        }
        const stageRect = referenceStage.getBoundingClientRect();
        const stageX = event.clientX - stageRect.left;
        const stageY = event.clientY - stageRect.top;
        const localX = stageX - referenceView.baseLeft;
        const localY = stageY - referenceView.baseTop;
        const centeredX = localX - (referenceView.baseWidth / 2);
        const centeredY = localY - (referenceView.baseHeight / 2);
        const sourceX = ((centeredX - referenceView.offsetX) / referenceView.scale) + (referenceView.baseWidth / 2);
        const sourceY = ((centeredY - referenceView.offsetY) / referenceView.scale) + (referenceView.baseHeight / 2);
        const pixelX = (sourceX / referenceView.baseWidth) * inspectResult.reference.shape[1];
        const displayY = (sourceY / referenceView.baseHeight) * inspectResult.reference.shape[0];
        const pixelY = (inspectResult.reference.shape[0] - 1) - displayY;
        if (
            !Number.isFinite(pixelX) || !Number.isFinite(pixelY)
            || pixelX < 0 || pixelY < 0
            || pixelX > inspectResult.reference.shape[1]
            || pixelY > inspectResult.reference.shape[0]
        ) {
            return null;
        }
        return { x: pixelX, y: pixelY };
    }

    async function handleInspect() {
        const datasetPath = currentSelectedDatasetPath();
        if (!datasetPath) {
            setError("Seleziona prima una sessione.");
            return;
        }
        setError("");
        const selectedFitsCount = browserState && selectedBrowserPath
            ? (((browserState.directories || []).find(function (item) { return item.path === selectedBrowserPath; }) || {}).direct_fits_count
                ?? (browserState.current_path === selectedBrowserPath ? browserState.current_path_direct_fits_count : null))
            : null;
        setBusy(inspectButton, true, "Analisi...");
        setStatus(
            Number.isFinite(Number(selectedFitsCount))
                ? `Trovati ${Number(selectedFitsCount)} FITS. Ispezione in corso...`
                : "Ispezione FITS in corso...",
            "status-neutral",
        );
        selectedTarget = null;
        selectedComparisons = [];
        frameInclusion = new Set();
        try {
            const { response, data } = await postJson(endpoints.inspectUrl, { dataset_path: datasetPath });
            updateDebugPayload(data);
            if (!response.ok || data.status === "error") {
                setStatus("Ispezione FITS fallita.", "status-error");
                setError(data.message || `Errore HTTP ${response.status}`);
                return;
            }
            const jobId = data.job_id;
            if (!jobId) {
                setStatus("Avvio job di ispezione fallito.", "status-error");
                setError("job_id mancante nella risposta di inspect.");
                return;
            }
            let inspectPayload = null;
            while (!inspectPayload) {
                await new Promise((resolve) => window.setTimeout(resolve, 700));
                const { response: statusResponse, data: statusData } = await getJson(resolveJobUrl(endpoints.inspectStatusUrlTemplate, jobId));
                if (!statusResponse.ok && statusResponse.status >= 500) {
                    continue;
                }
                if (!statusResponse.ok || statusData.status === "error") {
                    setStatus("Stato ispezione non disponibile.", "status-error");
                    setError(statusData.message || `Errore HTTP ${statusResponse.status}`);
                    return;
                }
                const progress = statusData.progress || {};
                const detail = progress.total
                    ? ` (${progress.current || 0} / ${progress.total})`
                    : "";
                setStatus(`${progress.message || "Ispezione in corso..."}${detail}`, "status-neutral");
                if (statusData.job_status === "failed") {
                    setStatus("Ispezione FITS fallita.", "status-error");
                    setError(statusData.error || progress.message || "Job di ispezione fallito.");
                    return;
                }
                if (statusData.job_status !== "completed") {
                    continue;
                }
                const { response: resultResponse, data: resultData } = await getJson(resolveJobUrl(endpoints.inspectResultUrlTemplate, jobId));
                if (!resultResponse.ok || resultData.status === "error") {
                    setStatus("Recupero risultato ispezione fallito.", "status-error");
                    setError(resultData.message || `Errore HTTP ${resultResponse.status}`);
                    return;
                }
                inspectPayload = resultData;
            }
            inspectResult = inspectPayload;
            runResult = null;
            renderReference(inspectPayload);
            renderTargeting(inspectPayload);
            await refreshSelectionMetrics();
            renderFrameQuality(inspectPayload);
            renderPhotometry({ photometry: null });
            await refreshSessions();
            setStatus(inspectPayload.message || "Dataset pronto.", "status-success");
            runButton.disabled = false;
            saveButton.disabled = true;
            solveAstrometryButton.disabled = false;
            queryTargetsButton.disabled = false;
            suggestComparisonsButton.disabled = false;
            selectTargetButton.disabled = false;
            addComparisonButton.disabled = false;
            toggleCenterButton.disabled = false;
            setZoomControlsEnabled(true);
        } catch (error) {
            setStatus("Errore di rete durante l'ispezione FITS.", "status-error");
            setError(error instanceof Error ? error.message : String(error));
        } finally {
            setBusy(inspectButton, false, "Analisi...");
        }
    }

    async function handleRun() {
        if (!inspectResult) {
            return;
        }
        setError("");
        setBusy(runButton, true, "Esecuzione...");
        setStatus("Fotometria lato server in corso...", "status-neutral");
        try {
            const payload = buildRunPayload();
            const { response, data } = await postJson(endpoints.runUrl, payload);
            updateDebugPayload(data);
            if (!response.ok || data.status === "error") {
                setStatus("Fotometria fallita.", "status-error");
                setError(data.message || `Errore HTTP ${response.status}`);
                return;
            }
            runResult = data;
            inspectResult = data;
            renderReference(data);
            renderTargeting(data);
            renderFrameQuality(data);
            renderPhotometry(data);
            saveButton.disabled = false;
            setStatus(data.message || "Fotometria completata.", "status-success");
        } catch (error) {
            setStatus("Errore di rete durante la fotometria.", "status-error");
            setError(error instanceof Error ? error.message : String(error));
        } finally {
            setBusy(runButton, false, "Esecuzione...");
        }
    }

    async function handleSave() {
        if (!runResult) {
            setError("Esegui prima la fotometria.");
            return;
        }
        setBusy(saveButton, true, "Salvataggio...");
        setStatus("Salvataggio sessione tecnica in corso...", "status-neutral");
        try {
            const payload = {
                ...buildRunPayload(),
                ...runResult,
            };
            const { response, data } = await postJson(endpoints.saveUrl, payload);
            updateDebugPayload(data);
            if (!response.ok || data.status === "error") {
                setStatus("Salvataggio fallito.", "status-error");
                setError(data.message || `Errore HTTP ${response.status}`);
                return;
            }
            setStatus(data.message || "Sessione salvata.", "status-success");
            await refreshSessions();
        } catch (error) {
            setStatus("Errore di rete durante il salvataggio.", "status-error");
            setError(error instanceof Error ? error.message : String(error));
        } finally {
            setBusy(saveButton, false, "Salvataggio...");
        }
    }

    async function handleRestore(sessionId, button) {
        setBusy(button, true, "Ripristino...");
        setStatus(`Ripristino sessione ${sessionId}...`, "status-neutral");
        try {
            const { response, data } = await postJson(endpoints.restoreUrl, { session_id: sessionId });
            updateDebugPayload(data);
            if (!response.ok || data.status === "error") {
                setStatus("Ripristino fallito.", "status-error");
                setError(data.message || `Errore HTTP ${response.status}`);
                return;
            }
            inspectResult = data;
            runResult = data;
            selectedBrowserPath = data.dataset && data.dataset.dataset_path ? data.dataset.dataset_path : selectedBrowserPath;
            updateDatasetSelectionBanner();
            selectedTarget = data.targeting && data.targeting.selected_target ? data.targeting.selected_target : null;
            selectedComparisons = data.comparison_stars && data.comparison_stars.selected ? data.comparison_stars.selected.slice() : [];
            frameInclusion = new Set((data.photometry && data.photometry.selection && data.photometry.selection.included_frame_indices) || []);
            renderReference(data);
            renderTargeting(data);
            await refreshSelectionMetrics();
            renderFrameQuality(data);
            renderPhotometry(data);
            saveButton.disabled = false;
            runButton.disabled = false;
            solveAstrometryButton.disabled = false;
            queryTargetsButton.disabled = false;
            suggestComparisonsButton.disabled = false;
            selectTargetButton.disabled = false;
            addComparisonButton.disabled = false;
            toggleCenterButton.disabled = false;
            setZoomControlsEnabled(true);
            setStatus(data.message || "Sessione ripristinata.", "status-success");
            await refreshSessions();
        } catch (error) {
            setStatus("Errore di rete durante il ripristino.", "status-error");
            setError(error instanceof Error ? error.message : String(error));
        } finally {
            setBusy(button, false, "Ripristino...");
        }
    }

    async function handleDelete(sessionId, button) {
        setBusy(button, true, "Eliminazione...");
        try {
            const { response, data } = await postJson(endpoints.deleteUrl, { session_id: sessionId });
            updateDebugPayload(data);
            if (!response.ok || data.status === "error") {
                setStatus("Eliminazione fallita.", "status-error");
                setError(data.message || `Errore HTTP ${response.status}`);
                return;
            }
            setStatus(data.message || "Sessione eliminata.", "status-success");
            await refreshSessions();
        } catch (error) {
            setStatus("Errore di rete durante l'eliminazione.", "status-error");
            setError(error instanceof Error ? error.message : String(error));
        } finally {
            setBusy(button, false, "Eliminazione...");
        }
    }

    referenceStage.addEventListener("click", function (event) {
        if (suppressStageClick) {
            suppressStageClick = false;
            return;
        }
        const pixel = stagePointToPixel(event);
        if (!pixel) {
            return;
        }
        if (editMode === "target") {
            selectedTarget = { x: pixel.x, y: pixel.y, label: "manual-target", mode: "manuale" };
        } else {
            selectedComparisons.push({ x: pixel.x, y: pixel.y });
        }
        renderTargeting(inspectResult);
        void refreshSelectionMetrics();
    });

    referenceStage.addEventListener("wheel", function (event) {
        if (!inspectResult) {
            return;
        }
        event.preventDefault();
        const stageRect = referenceStage.getBoundingClientRect();
        const anchorX = event.clientX - stageRect.left;
        const anchorY = event.clientY - stageRect.top;
        const factor = event.deltaY < 0 ? 1.15 : 1 / 1.15;
        setReferenceScale(referenceView.scale * factor, anchorX, anchorY);
    }, { passive: false });

    referenceStage.addEventListener("pointerdown", function (event) {
        if (!inspectResult) {
            return;
        }
        referenceView.dragging = true;
        referenceView.dragStartX = event.clientX;
        referenceView.dragStartY = event.clientY;
        referenceView.dragOriginOffsetX = referenceView.offsetX;
        referenceView.dragOriginOffsetY = referenceView.offsetY;
        suppressStageClick = false;
        referenceStage.classList.add("is-dragging");
        referenceStage.setPointerCapture(event.pointerId);
    });

    referenceStage.addEventListener("pointermove", function (event) {
        if (!referenceView.dragging) {
            return;
        }
        const deltaX = event.clientX - referenceView.dragStartX;
        const deltaY = event.clientY - referenceView.dragStartY;
        if (Math.abs(deltaX) > 3 || Math.abs(deltaY) > 3) {
            suppressStageClick = true;
        }
        referenceView.offsetX = referenceView.dragOriginOffsetX + deltaX;
        referenceView.offsetY = referenceView.dragOriginOffsetY + deltaY;
        applyReferenceTransform();
    });

    function stopReferenceDrag(event) {
        if (!referenceView.dragging) {
            return;
        }
        referenceView.dragging = false;
        referenceStage.classList.remove("is-dragging");
        try {
            referenceStage.releasePointerCapture(event.pointerId);
        } catch (_) {
            // no-op
        }
    }

    referenceStage.addEventListener("pointerup", stopReferenceDrag);
    referenceStage.addEventListener("pointercancel", stopReferenceDrag);
    referenceStage.addEventListener("pointerleave", function () {
        if (!referenceView.dragging) {
            referenceStage.classList.remove("is-dragging");
        }
    });

    selectTargetButton.addEventListener("click", function () {
        editMode = "target";
        selectTargetButton.classList.add("is-active");
        addComparisonButton.classList.remove("is-active");
    });

    addComparisonButton.addEventListener("click", function () {
        editMode = "comparison";
        addComparisonButton.classList.add("is-active");
        selectTargetButton.classList.remove("is-active");
    });

    toggleCenterButton.addEventListener("click", function () {
        centerVisible = !centerVisible;
        toggleCenterButton.classList.toggle("is-active", centerVisible);
        renderOverlay();
    });

    zoomInButton.addEventListener("click", function () {
        zoomReference(1.2);
    });

    zoomOutButton.addEventListener("click", function () {
        zoomReference(1 / 1.2);
    });

    zoomResetButton.addEventListener("click", function () {
        resetReferenceView();
    });

    browseDatasetsButton.addEventListener("click", toggleDatasetBrowser);
    inspectButton.addEventListener("click", handleInspect);
    solveAstrometryButton.addEventListener("click", handleSolveAstrometry);
    queryTargetsButton.addEventListener("click", handleQueryTargets);
    runButton.addEventListener("click", handleRun);
    saveButton.addEventListener("click", handleSave);
    suggestComparisonsButton.addEventListener("click", handleSuggestComparisons);
    referenceImage.addEventListener("load", updateReferenceViewportLayout);
    window.addEventListener("resize", updateReferenceViewportLayout);
    apertureRadiusInput.addEventListener("input", function () {
        renderOverlay();
        void refreshSelectionMetrics();
    });
    annulusInnerInput.addEventListener("input", renderOverlay);
    annulusOuterInput.addEventListener("input", renderOverlay);
    plotModeSelect.addEventListener("change", rerenderPhotometryFromState);
    binSizeInput.addEventListener("input", rerenderPhotometryFromState);

    setStatus("In attesa di input.", "status-neutral");
    updateDatasetSelectionBanner();
    setZoomControlsEnabled(false);
    inspectButton.disabled = true;
    solveAstrometryButton.disabled = true;
    queryTargetsButton.disabled = true;
    suggestComparisonsButton.disabled = true;
    toggleCenterButton.disabled = true;
    toggleCenterButton.classList.add("is-active");
})();
