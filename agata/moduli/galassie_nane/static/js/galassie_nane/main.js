(function () {
    const ui = {
        apiBaseUrl: document.getElementById("apiBaseUrl"),
        runBtn: document.getElementById("runSingleBtn"),
        singleRunTitle: document.getElementById("singleRunTitle"),
        runStatus: document.getElementById("runStatus"),
        errorBox: document.getElementById("errorBox"),
        sourcesPreviewBody: document.getElementById("sourcesPreviewBody"),
        countsCanvas: document.getElementById("countsCanvas"),
        zMapCanvas: document.getElementById("zMapCanvas"),
        kpiSources: document.getElementById("kpiSources"),
        kpiMaxZ: document.getElementById("kpiMaxZ"),
        kpiScore: document.getElementById("kpiScore"),
        kpiProvider: document.getElementById("kpiProvider"),
        kpiElapsed: document.getElementById("kpiElapsed"),
        resultExtragal: document.getElementById("resultExtragal"),
        currentRunName: document.getElementById("currentRunName"),
        saveStatus: document.getElementById("saveStatus"),
        saveRunNameInput: document.getElementById("saveRunNameInput"),
        saveRunBtn: document.getElementById("saveRunBtn"),
        refreshSavedRunsBtn: document.getElementById("refreshSavedRunsBtn"),
        savedRunsBody: document.getElementById("savedRunsBody"),
        savedRunsStatus: document.getElementById("savedRunsStatus"),
        raInput: document.getElementById("raInput"),
        decInput: document.getElementById("decInput"),
        radiusInput: document.getElementById("radiusInput"),
        gmaxInput: document.getElementById("gmaxInput"),
        ruweInput: document.getElementById("ruweInput"),
        cellInput: document.getElementById("cellInput"),
        extragalOffInput: document.getElementById("extragalOffInput"),
        useRealGaiaInput: document.getElementById("useRealGaiaInput"),
    };
    let lastRunPayload = null;
    let lastRunResult = null;
    let currentDisplayedRunName = "non salvato";

    function apiBaseUrl() {
        return (window.GALASSIE_NANE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
    }

    function setStatus(text) {
        if (ui.runStatus) {
            ui.runStatus.textContent = text || "";
        }
    }

    function setSaveStatus(text, isError) {
        if (!ui.saveStatus) return;
        if (!text) {
            ui.saveStatus.textContent = "";
            ui.saveStatus.classList.add("hidden");
            ui.saveStatus.style.color = "";
            return;
        }
        ui.saveStatus.textContent = text;
        ui.saveStatus.style.color = isError ? "#9f1239" : "#2b5f2e";
        ui.saveStatus.classList.remove("hidden");
    }

    function setSavedRunsStatus(text, isError) {
        if (!ui.savedRunsStatus) return;
        if (!text) {
            ui.savedRunsStatus.textContent = "";
            ui.savedRunsStatus.classList.add("hidden");
            ui.savedRunsStatus.style.color = "";
            return;
        }
        ui.savedRunsStatus.textContent = text;
        ui.savedRunsStatus.style.color = isError ? "#9f1239" : "";
        ui.savedRunsStatus.classList.remove("hidden");
    }

    function setCurrentRunName(name) {
        currentDisplayedRunName = (name || "").trim() || "non salvato";
        if (ui.currentRunName) ui.currentRunName.textContent = currentDisplayedRunName;
    }

    function refreshSingleRunTitle() {
        if (!ui.singleRunTitle) return;
        const useReal = !!(ui.useRealGaiaInput && ui.useRealGaiaInput.checked);
        ui.singleRunTitle.textContent = useReal
            ? "Analisi Singola (Gaia reale)"
            : "Analisi Singola (Mock Gaia)";
    }

    function setError(message) {
        if (!ui.errorBox) return;
        if (!message) {
            ui.errorBox.textContent = "";
            ui.errorBox.classList.add("hidden");
            return;
        }
        ui.errorBox.textContent = message;
        ui.errorBox.classList.remove("hidden");
    }

    function setKpis(result) {
        const score = result && result.tile_score ? result.tile_score : null;
        const summary = result && result.summary ? result.summary : null;
        const meta = result && result.gaia_meta ? result.gaia_meta : null;
        if (ui.kpiSources) ui.kpiSources.textContent = summary ? String(summary.n_sources) : "-";
        if (ui.kpiMaxZ) ui.kpiMaxZ.textContent = score ? Number(score.s_spatial).toFixed(2) : "-";
        if (ui.kpiScore) ui.kpiScore.textContent = score ? Number(score.score).toFixed(3) : "-";
        if (ui.kpiProvider) ui.kpiProvider.textContent = meta ? (meta.table_name || meta.provider_mode || "-") : "-";
        if (ui.kpiElapsed) {
            const totalMs = result && result.timing ? Number(result.timing.total_ms) : NaN;
            ui.kpiElapsed.textContent = Number.isFinite(totalMs) ? `${(totalMs / 1000).toFixed(2)} s` : "-";
        }
        if (ui.resultExtragal) {
            if (result && result.input) {
                ui.resultExtragal.textContent = result.input.no_extragal ? "disattivato" : "attivo";
            } else {
                ui.resultExtragal.textContent = "-";
            }
        }
    }

    function buildPayload() {
        return {
            ra: Number(ui.raInput.value),
            dec: Number(ui.decInput.value),
            radius: Number(ui.radiusInput.value),
            gmax: Number(ui.gmaxInput.value),
            ruwe_max: ui.ruweInput.value === "" ? null : Number(ui.ruweInput.value),
            cell_arcmin: Number(ui.cellInput.value),
            no_extragal: !!ui.extragalOffInput.checked,
            use_real_gaia: !!(ui.useRealGaiaInput && ui.useRealGaiaInput.checked),
        };
    }

    function renderSourcesPreview(rows) {
        if (!ui.sourcesPreviewBody) return;
        if (!Array.isArray(rows) || rows.length === 0) {
            ui.sourcesPreviewBody.innerHTML = '<tr><td colspan="7" class="empty-cell">Nessun dato.</td></tr>';
            return;
        }
        ui.sourcesPreviewBody.innerHTML = rows.map((row) => {
            const g = Number(row.phot_g_mean_mag);
            const bpRp = Number(row.bp_rp);
            const parallax = Number(row.parallax);
            const ruwe = Number(row.ruwe);
            return `<tr>
                <td>${String(row.source_id ?? "-")}</td>
                <td>${Number(row.ra).toFixed(5)}</td>
                <td>${Number(row.dec).toFixed(5)}</td>
                <td>${Number.isFinite(g) ? g.toFixed(3) : "-"}</td>
                <td>${Number.isFinite(bpRp) ? bpRp.toFixed(3) : "-"}</td>
                <td>${Number.isFinite(parallax) ? parallax.toFixed(4) : "-"}</td>
                <td>${Number.isFinite(ruwe) ? ruwe.toFixed(3) : "-"}</td>
            </tr>`;
        }).join("");
    }

    function clearCanvas(canvas, label) {
        if (!canvas) return;
        const ctx = canvas.getContext("2d");
        if (!ctx) return;
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = "#f8fbff";
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = "#6b7a88";
        ctx.font = "12px sans-serif";
        ctx.fillText(label || "Nessun dato", 12, 20);
    }

    function renderHeatmaps(result) {
        const density = result && result.density ? result.density : null;
        if (!density || !Array.isArray(density.counts) || !Array.isArray(density.z_map)) {
            clearCanvas(ui.countsCanvas, "Nessuna mappa densitÃ ");
            clearCanvas(ui.zMapCanvas, "Nessuna Z-map");
            return;
        }
        drawGridHeatmap(ui.countsCanvas, density.counts, "counts", density.ra_edges, density.dec_edges);
        drawGridHeatmap(ui.zMapCanvas, density.z_map, "z", density.ra_edges, density.dec_edges);
    }

    function drawGridHeatmap(canvas, grid, mode, raEdges, decEdges) {
        if (!canvas) return;
        const ctx = canvas.getContext("2d");
        if (!ctx) return;
        const rows = Array.isArray(grid) ? grid.length : 0;
        const cols = rows > 0 && Array.isArray(grid[0]) ? grid[0].length : 0;
        if (!rows || !cols) {
            clearCanvas(canvas, "Griglia vuota");
            return;
        }

        const padLeft = 44;
        const padRight = 10;
        const padTop = 10;
        const padBottom = 28;
        const w = canvas.width - padLeft - padRight;
        const h = canvas.height - padTop - padBottom;
        const cellW = w / cols;
        const cellH = h / rows;

        const values = [];
        for (let r = 0; r < rows; r += 1) {
            for (let c = 0; c < cols; c += 1) {
                values.push(Number(grid[r][c]));
            }
        }
        const minVal = Math.min(...values);
        const maxVal = Math.max(...values);
        const maxAbs = Math.max(Math.abs(minVal), Math.abs(maxVal));

        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = "#ffffff";
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        for (let r = 0; r < rows; r += 1) {
            for (let c = 0; c < cols; c += 1) {
                const v = Number(grid[r][c]);
                ctx.fillStyle = mode === "z"
                    ? zColor(v, maxAbs || 1)
                    : countColor(v, minVal, maxVal);
                ctx.fillRect(
                    padLeft + c * cellW,
                    padTop + r * cellH,
                    Math.ceil(cellW),
                    Math.ceil(cellH)
                );
            }
        }

        ctx.strokeStyle = "#d7e3ef";
        ctx.lineWidth = 1;
        ctx.strokeRect(padLeft, padTop, w, h);
        drawAxesLabels(ctx, {
            padLeft,
            padTop,
            w,
            h,
            raEdges,
            decEdges,
        });
    }

    function drawAxesLabels(ctx, opts) {
        const { padLeft, padTop, w, h, raEdges, decEdges } = opts;
        ctx.fillStyle = "#5d6b78";
        ctx.font = "9px sans-serif";

        const raMin = Array.isArray(raEdges) && raEdges.length ? Number(raEdges[0]) : null;
        const raMax = Array.isArray(raEdges) && raEdges.length ? Number(raEdges[raEdges.length - 1]) : null;
        const decMin = Array.isArray(decEdges) && decEdges.length ? Number(decEdges[0]) : null;
        const decMax = Array.isArray(decEdges) && decEdges.length ? Number(decEdges[decEdges.length - 1]) : null;

        if (Number.isFinite(raMin) && Number.isFinite(raMax)) {
            ctx.textAlign = "left";
            ctx.fillText(raMin.toFixed(3), padLeft, padTop + h + 16);
            ctx.textAlign = "right";
            ctx.fillText(raMax.toFixed(3), padLeft + w, padTop + h + 16);
            ctx.textAlign = "center";
            ctx.fillText("RA [deg]", padLeft + w / 2, padTop + h + 26);
        }

        if (Number.isFinite(decMin) && Number.isFinite(decMax)) {
            ctx.textAlign = "right";
            ctx.fillText(decMin.toFixed(3), padLeft - 6, padTop + h);
            ctx.fillText(decMax.toFixed(3), padLeft - 6, padTop + 10);
            ctx.save();
            ctx.translate(12, padTop + h / 2);
            ctx.rotate(-Math.PI / 2);
            ctx.textAlign = "center";
            ctx.fillText("Dec [deg]", 0, 0);
            ctx.restore();
        }
    }

    function countColor(v, minVal, maxVal) {
        const span = Math.max(1e-9, maxVal - minVal);
        const t = (v - minVal) / span;
        const r = Math.round(235 - t * 120);
        const g = Math.round(246 - t * 80);
        const b = Math.round(255 - t * 170);
        return `rgb(${r},${g},${b})`;
    }

    function zColor(v, maxAbs) {
        const t = Math.max(-1, Math.min(1, v / Math.max(maxAbs, 1e-9)));
        if (t >= 0) {
            const a = t;
            const r = Math.round(245 - a * 20);
            const g = Math.round(245 - a * 145);
            const b = Math.round(245 - a * 170);
            return `rgb(${r},${g},${b})`;
        }
        const a = Math.abs(t);
        const r = Math.round(245 - a * 165);
        const g = Math.round(245 - a * 95);
        const b = Math.round(245 - a * 20);
        return `rgb(${r},${g},${b})`;
    }

    async function runSingleAnalysis() {
        const requestRealGaia = !!(ui.useRealGaiaInput && ui.useRealGaiaInput.checked);
        ui.runBtn.disabled = true;
        setError("");
        setSaveStatus("");
        lastRunPayload = buildPayload();
        lastRunResult = null;
        setCurrentRunName("non salvato");
        setStatus(
            requestRealGaia
                ? "Richiesta analisi con provider Gaia reale..."
                : "Esecuzione analisi mock in corso..."
        );
        try {
            const response = await fetch("/agata/galassie-nane/api/single-run", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(buildPayload()),
            });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data?.error || data?.detail || "Richiesta fallita");
            }
            setKpis(data);
            renderHeatmaps(data);
            renderSourcesPreview(data.sources_preview || []);
            lastRunResult = data;
            setStatus(`Analisi completata (${(data.gaia_meta && data.gaia_meta.provider_mode) || "n/d"}).`);
        } catch (err) {
            const errMsg = err instanceof Error ? err.message : "Errore sconosciuto";
            const isRealGaiaNotImplemented =
                !!(ui.useRealGaiaInput && ui.useRealGaiaInput.checked) &&
                /gaia reale|non ancora implementat/i.test(errMsg.toLowerCase());
            setStatus(
                isRealGaiaNotImplemented
                    ? "Gaia reale non ancora implementata (usa mock per le prove)."
                    : "Errore durante l'analisi."
            );
            renderHeatmaps(null);
            renderSourcesPreview([]);
            setKpis(null);
            setError(errMsg);
        } finally {
            ui.runBtn.disabled = false;
        }
    }

    async function saveCurrentRun() {
        setSaveStatus("");
        if (!lastRunResult) {
            setSaveStatus("Esegui prima un'analisi e poi salva il risultato.", true);
            return;
        }
        const rawName = ui.saveRunNameInput ? ui.saveRunNameInput.value : "";
        const name = (rawName || "").trim();
        if (!name) {
            setSaveStatus("Inserisci un nome per il salvataggio.", true);
            return;
        }
        if (ui.saveRunBtn) ui.saveRunBtn.disabled = true;
        try {
            const response = await fetch("/agata/galassie-nane/api/save-run", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    name,
                    input: lastRunPayload,
                    result: lastRunResult,
                }),
            });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data?.error || "Salvataggio fallito");
            }
            setSaveStatus(`Salvato: ${data.file_name}`, false);
            setCurrentRunName(data.name || name);
            await refreshSavedRuns();
        } catch (err) {
            setSaveStatus(err instanceof Error ? err.message : "Errore di salvataggio", true);
        } finally {
            if (ui.saveRunBtn) ui.saveRunBtn.disabled = false;
        }
    }

    function applyInputFromPayload(input) {
        if (!input || typeof input !== "object") return;
        if (ui.raInput && Number.isFinite(Number(input.ra))) ui.raInput.value = String(input.ra);
        if (ui.decInput && Number.isFinite(Number(input.dec))) ui.decInput.value = String(input.dec);
        if (ui.radiusInput && Number.isFinite(Number(input.radius))) ui.radiusInput.value = String(input.radius);
        if (ui.gmaxInput && Number.isFinite(Number(input.gmax))) ui.gmaxInput.value = String(input.gmax);
        if (ui.ruweInput) ui.ruweInput.value = input.ruwe_max == null ? "" : String(input.ruwe_max);
        if (ui.cellInput && Number.isFinite(Number(input.cell_arcmin))) ui.cellInput.value = String(input.cell_arcmin);
        if (ui.extragalOffInput) ui.extragalOffInput.checked = !!input.no_extragal;
        if (ui.useRealGaiaInput) ui.useRealGaiaInput.checked = !!input.use_real_gaia;
        refreshSingleRunTitle();
    }

    function renderSavedRuns(items) {
        if (!ui.savedRunsBody) return;
        if (!Array.isArray(items) || items.length === 0) {
            ui.savedRunsBody.innerHTML = '<tr><td colspan="6" class="empty-cell">Nessuna run salvata.</td></tr>';
            return;
        }
        ui.savedRunsBody.innerHTML = items.map((item) => `
            <tr>
                <td>${String(item.name ?? "-")}</td>
                <td>${String(item.saved_at_utc ?? "-")}</td>
                <td>${Number.isFinite(Number(item.n_sources)) ? String(Number(item.n_sources)) : "-"}</td>
                <td>${Number.isFinite(Number(item.total_ms)) ? `${(Number(item.total_ms) / 1000).toFixed(2)} s` : "-"}</td>
                <td>${String(item.file_name ?? "-")}</td>
                <td><button type="button" class="btn-secondary-link saved-run-open-btn" data-run-id="${String(item.id ?? "")}">Riapri</button></td>
            </tr>
        `).join("");
    }

    async function refreshSavedRuns() {
        setSavedRunsStatus("");
        try {
            const response = await fetch("/agata/galassie-nane/api/saved-runs?limit=30");
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data?.error || "Caricamento run salvate fallito");
            }
            renderSavedRuns(data.items || []);
        } catch (err) {
            renderSavedRuns([]);
            setSavedRunsStatus(err instanceof Error ? err.message : "Errore caricamento run", true);
        }
    }

    async function openSavedRun(runId) {
        if (!runId) return;
        setSavedRunsStatus("Apertura run salvata...");
        setError("");
        setSaveStatus("");
        try {
            const response = await fetch(`/agata/galassie-nane/api/saved-runs/${encodeURIComponent(runId)}`);
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data?.error || "Apertura run fallita");
            }
            const payload = data && data.payload ? data.payload : {};
            const savedInput = payload.input || null;
            const savedResult = payload.result || null;
            applyInputFromPayload(savedInput);
            lastRunPayload = savedInput;
            lastRunResult = savedResult;
            setCurrentRunName(data.name || runId);
            setKpis(savedResult);
            renderHeatmaps(savedResult);
            renderSourcesPreview(savedResult && savedResult.sources_preview ? savedResult.sources_preview : []);
            setStatus(`Run salvata caricata: ${data.name || runId}`);
            setSavedRunsStatus("");
        } catch (err) {
            setSavedRunsStatus(err instanceof Error ? err.message : "Errore apertura run", true);
        }
    }
    if (ui.apiBaseUrl) {
        ui.apiBaseUrl.textContent = apiBaseUrl();
    }
    if (ui.runBtn) {
        ui.runBtn.addEventListener("click", runSingleAnalysis);
    }
    if (ui.saveRunBtn) {
        ui.saveRunBtn.addEventListener("click", saveCurrentRun);
    }
    if (ui.refreshSavedRunsBtn) {
        ui.refreshSavedRunsBtn.addEventListener("click", refreshSavedRuns);
    }
    if (ui.savedRunsBody) {
        ui.savedRunsBody.addEventListener("click", (event) => {
            const target = event.target;
            if (!(target instanceof HTMLElement)) return;
            const btn = target.closest(".saved-run-open-btn");
            if (!btn) return;
            openSavedRun(btn.getAttribute("data-run-id"));
        });
    }
    if (ui.useRealGaiaInput) {
        ui.useRealGaiaInput.addEventListener("change", refreshSingleRunTitle);
    }
    refreshSingleRunTitle();
    setCurrentRunName("non salvato");
    renderHeatmaps(null);
    renderSourcesPreview([]);
    refreshSavedRuns();
})();
