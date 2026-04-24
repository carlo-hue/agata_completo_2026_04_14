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
    const queryTargetsButton = document.getElementById("queryTargetsButton");
    const suggestComparisonsButton = document.getElementById("suggestComparisonsButton");
    const selectTargetButton = document.getElementById("selectTargetButton");
    const addComparisonButton = document.getElementById("addComparisonButton");
    const toggleCenterButton = document.getElementById("toggleCenterButton");
    const zoomInButton = document.getElementById("zoomInButton");
    const zoomOutButton = document.getElementById("zoomOutButton");
    const zoomResetButton = document.getElementById("zoomResetButton");
    const referenceImage = document.getElementById("referenceImage");
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
    const lightcurvePlot = document.getElementById("lightcurvePlot");
    const statusBox = document.getElementById("statusBox");
    const errorBox = document.getElementById("errorBox");
    const outputBox = document.getElementById("outputBox");
    const apertureRadiusInput = document.getElementById("apertureRadiusInput");
    const annulusInnerInput = document.getElementById("annulusInnerInput");
    const annulusOuterInput = document.getElementById("annulusOuterInput");

    const endpoints = {
        browseUrl: appRoot.dataset.browseUrl,
        inspectUrl: appRoot.dataset.inspectUrl,
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
            referenceImage.classList.add("hidden");
            referenceViewport.classList.add("hidden");
            referenceInfo.textContent = "Nessuna reference image disponibile.";
            return;
        }
        referenceImage.src = `data:image/png;base64,${reference.preview_png_base64}`;
        referenceImage.classList.remove("hidden");
        referenceViewport.classList.remove("hidden");
        resetReferenceView();
        updateReferenceViewportLayout();
        referenceInfo.textContent = `${reference.source.filename} | ${reference.shape[1]}x${reference.shape[0]} | mode=${reference.mode}`;
        renderOverlay();
    }

    function renderOverlay() {
        referenceOverlay.innerHTML = "";
        if (!inspectResult || !inspectResult.reference) {
            return;
        }
        const svgNs = "http://www.w3.org/2000/svg";
        const width = inspectResult.reference.shape[1];
        const height = inspectResult.reference.shape[0];
        const centerPixel = inspectResult.reference.center_pixel || null;
        const overlaySvg = document.createElementNS(svgNs, "svg");
        overlaySvg.setAttribute("class", "overlay-svg");
        overlaySvg.setAttribute("viewBox", `0 0 ${width} ${height}`);
        overlaySvg.setAttribute("preserveAspectRatio", "none");
        referenceOverlay.appendChild(overlaySvg);

        function appendSvgShape(tagName, attributes, className) {
            const element = document.createElementNS(svgNs, tagName);
            if (className) {
                element.setAttribute("class", className);
            }
            Object.entries(attributes).forEach(function ([key, value]) {
                element.setAttribute(key, String(value));
            });
            overlaySvg.appendChild(element);
            return element;
        }

        function addTextLabel(x, y, text, className) {
            const label = appendSvgShape("text", {
                x,
                y,
                dx: 10,
                dy: -10,
            }, className || "overlay-text");
            label.textContent = String(text);
        }

        function addMarker(x, y, klass, title) {
            appendSvgShape("circle", {
                cx: x,
                cy: y,
                r: klass === "candidate" ? 5 : 7,
            }, `overlay-shape ${klass}`);
        }

        function addCrosshair(center) {
            if (!center) {
                return;
            }
            const cx = Number(center.x);
            const cy = Number(center.y);
            const armLength = 15;
            const gap = 7;
            appendSvgShape("line", {
                x1: cx - armLength,
                y1: cy,
                x2: cx - gap,
                y2: cy,
            }, "overlay-shape crosshair");
            appendSvgShape("line", {
                x1: cx + gap,
                y1: cy,
                x2: cx + armLength,
                y2: cy,
            }, "overlay-shape crosshair");
            appendSvgShape("line", {
                x1: cx,
                y1: cy - armLength,
                x2: cx,
                y2: cy - gap,
            }, "overlay-shape crosshair");
            appendSvgShape("line", {
                x1: cx,
                y1: cy + gap,
                x2: cx,
                y2: cy + armLength,
            }, "overlay-shape crosshair");
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
            appendSvgShape("circle", {
                cx: x,
                cy: y,
                r: radiusPx,
            }, `overlay-ring ${role || "target"} ${klass}`);
        }

        if (centerVisible) {
            addCrosshair(centerPixel);
        }

        (inspectResult.targeting.target_candidates || []).forEach((item) => {
            addMarker(item.x, item.y, "candidate", item.label || "candidate");
        });
        if (selectedTarget) {
            getPhotometryRingRadii().forEach(function (item) {
                addRing(Number(selectedTarget.x), Number(selectedTarget.y), item.value, item.klass, item.title, "target");
            });
        }
        selectedComparisons.forEach((item, index) => {
            getPhotometryRingRadii().forEach(function (ring) {
                addRing(Number(item.x), Number(item.y), ring.value, ring.klass, `comparison ${index + 1} ${ring.title}`, "comparison");
            });
            addTextLabel(Number(item.x), Number(item.y), index + 1, "overlay-text comparison-label");
        });
    }

    function renderTargeting(result) {
        const targeting = result.targeting || {};
        selectedTarget = selectedTarget || targeting.auto_target || null;
        targetInfo.textContent = selectedTarget
            ? `x=${Number(selectedTarget.x).toFixed(2)} y=${Number(selectedTarget.y).toFixed(2)}`
            : "Target non selezionato.";

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
                    selectedTarget = { x: item.x, y: item.y, label: item.label };
                    renderTargeting(inspectResult);
                    renderOverlay();
                },
            }));
        }

        const comparisonCandidates = (result.comparison_stars || {}).candidates || [];
        const comparisonCandidatesLoaded = !!((result.comparison_stars || {}).comparison_candidates_loaded);
        if (!selectedComparisons.length && comparisonCandidatesLoaded) {
            selectedComparisons = ((result.comparison_stars || {}).auto_selected || []).slice();
        }
        comparisonInfo.textContent = selectedComparisons.length
            ? `${selectedComparisons.length} stelle selezionate`
            : "Nessuna comparison star selezionata.";
        comparisonCandidatesBox.innerHTML = "";
        if (!comparisonCandidates.length && selectedComparisons.length) {
            comparisonCandidatesBox.className = "table-box";
            comparisonCandidatesBox.appendChild(buildCandidateTable({
                headers: [
                    { key: "label", label: "Comparison" },
                    { key: "x", label: "x", numeric: true },
                    { key: "y", label: "y", numeric: true },
                ],
                rows: selectedComparisons.map(function (item, index) {
                    return {
                        x: Number(item.x).toFixed(2),
                        y: Number(item.y).toFixed(2),
                        label: `manual ${index + 1}`,
                        _raw: item,
                    };
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
        setError("");
        setBusy(queryTargetsButton, true, "Ricerca...");
        setStatus("Query target noti in corso...", "status-neutral");
        try {
            const { response, data } = await postJson(endpoints.queryTargetsUrl, { dataset_path: datasetPath });
            outputBox.textContent = JSON.stringify(data, null, 2);
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
            setStatus(data.message || "Candidati target aggiornati.", "status-success");
        } catch (error) {
            setStatus("Errore di rete durante la query target.", "status-error");
            setError(error instanceof Error ? error.message : String(error));
        } finally {
            setBusy(queryTargetsButton, false, "Ricerca...");
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
            outputBox.textContent = JSON.stringify(data, null, 2);
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
    }

    function applyReferenceTransform() {
        if (!referenceViewport) {
            return;
        }
        referenceViewport.style.transform = `translate(${referenceView.offsetX}px, ${referenceView.offsetY}px) scale(${referenceView.scale})`;
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
        photometryInfo.textContent = `frame usati=${photometry.summary.used_frames} | scatter=${photometry.summary.normalized_flux_scatter ?? "-"}`;
        const x = photometry.series.time_jd || [];
        const y = photometry.series.differential_flux || [];
        Plotly.newPlot(lightcurvePlot, [{
            x,
            y,
            mode: "lines+markers",
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
        const pixelY = (sourceY / referenceView.baseHeight) * inspectResult.reference.shape[0];
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
            outputBox.textContent = JSON.stringify(data, null, 2);
            if (!response.ok || data.status === "error") {
                setStatus("Ispezione FITS fallita.", "status-error");
                setError(data.message || `Errore HTTP ${response.status}`);
                return;
            }
            inspectResult = data;
            runResult = null;
            renderReference(data);
            renderTargeting(data);
            renderFrameQuality(data);
            renderPhotometry({ photometry: null });
            await refreshSessions();
            setStatus(data.message || "Dataset pronto.", "status-success");
            runButton.disabled = false;
            saveButton.disabled = true;
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
            outputBox.textContent = JSON.stringify(data, null, 2);
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
            outputBox.textContent = JSON.stringify(data, null, 2);
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
            outputBox.textContent = JSON.stringify(data, null, 2);
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
            renderFrameQuality(data);
            renderPhotometry(data);
            saveButton.disabled = false;
            runButton.disabled = false;
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
            outputBox.textContent = JSON.stringify(data, null, 2);
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
            selectedTarget = { x: pixel.x, y: pixel.y, label: "manual-target" };
        } else {
            selectedComparisons.push({ x: pixel.x, y: pixel.y });
        }
        renderTargeting(inspectResult);
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
    queryTargetsButton.addEventListener("click", handleQueryTargets);
    runButton.addEventListener("click", handleRun);
    saveButton.addEventListener("click", handleSave);
    suggestComparisonsButton.addEventListener("click", handleSuggestComparisons);
    referenceImage.addEventListener("load", updateReferenceViewportLayout);
    window.addEventListener("resize", updateReferenceViewportLayout);
    apertureRadiusInput.addEventListener("input", renderOverlay);
    annulusInnerInput.addEventListener("input", renderOverlay);
    annulusOuterInput.addEventListener("input", renderOverlay);

    setStatus("In attesa di input.", "status-neutral");
    updateDatasetSelectionBanner();
    setZoomControlsEnabled(false);
    inspectButton.disabled = true;
    queryTargetsButton.disabled = true;
    suggestComparisonsButton.disabled = true;
    toggleCenterButton.disabled = true;
    toggleCenterButton.classList.add("is-active");
})();
