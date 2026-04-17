/**
 * Import Catalogs Tab - Ricerca e importazione cataloghi fotometrici
 *
 * Supports: TESS QLP, ZTF
 *
 * API Endpoints:
 * - POST /agata/admin/api/catalogs/tess/qlp/search-sectors - Search TESS QLP sectors by Gaia ID
 * - POST /agata/admin/api/catalogs/tess/qlp/download-sector - Download and import sector
 * - POST /agata/admin/api/catalogs/ztf/search-and-import - Search and import ZTF data
 */

import { state } from './state.js';

export function initImportCatalogs() {
  console.log('[ImportCatalogs] Module initialized');

  // Popola Gaia ID dal progetto
  const gaiaIdInput = document.getElementById('import-gaia-id');
  if (!gaiaIdInput) return;

  const projectGaiaId = document.getElementById('projectGaiaId')?.value;
  const urlParams = new URLSearchParams(window.location.search);
  const urlGaiaId = urlParams.get('gaia_id');

  const gaiaId = projectGaiaId || urlGaiaId;
  if (gaiaId) {
    gaiaIdInput.value = gaiaId;
    console.log(`[ImportCatalogs] Gaia ID loaded: ${gaiaId}`);
  }
}

/**
 * Main search function - dispatches to TESS, ZTF, or ASAS-SN based on dropdown selection
 */
window.searchImportCatalogs = async function() {
  const catalog = document.getElementById('import-catalog-select')?.value || 'TESS';

  if (catalog === 'ZTF') {
    await searchZTF();
  } else if (catalog === 'ASAS-SN') {
    await searchASASSN();
  } else if (catalog === 'FILE') {
    displayFileUploadForm();
  } else {
    await searchTESS();
  }
};

/**
 * Search TESS QLP sectors by Gaia ID
 */
async function searchTESS() {
  const gaiaId = document.getElementById('import-gaia-id')?.value;
  const resultsDiv = document.getElementById('import-results');
  const searchBtn = document.getElementById('import-search-btn');

  if (!gaiaId) {
    showImportStatus('error', 'Gaia ID mancante');
    return;
  }

  searchBtn.disabled = true;
  searchBtn.style.opacity = '0.6';
  searchBtn.textContent = 'Ricerca in corso...';
  showImportStatus('info', 'Step 1/2: Ricerca settori QLP disponibili su MAST...');
  resultsDiv.innerHTML = '<p style="color: #999; text-align: center; padding: 2rem;">Interrogazione archivio TESS su MAST...</p>';

  try {
    const response = await fetch('/agata/admin/api/catalogs/tess/qlp/search-sectors', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ gaia_id: gaiaId })
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.error || `HTTP ${response.status}`);
    }

    const data = await response.json();
    if (!data.success) {
      throw new Error(data.error || 'Search failed');
    }

    // Store lcfs_serialized for download step
    window.lcfsSerializedData = data.lcfs_serialized;
    console.log('[ImportCatalogs] Stored lcfs_serialized for download (', data.lcfs_serialized?.length, 'bytes)');

    displayTESSResults(data, gaiaId);
    showImportStatus('success', 'Step 2/2: Seleziona uno o piu settori da scaricare');

  } catch (error) {
    console.error('[ImportCatalogs] TESS search error:', error);
    showImportStatus('error', `Errore: ${error.message}`);
    resultsDiv.innerHTML = `
      <div style="padding: 2rem; text-align: center;">
        <p style="color: #dc2626; font-weight: 600;">Errore durante la ricerca TESS</p>
        <p class="tess-error-detail" style="color: #666; font-size: 0.9rem;"></p>
      </div>
    `;
    const errDetail = resultsDiv.querySelector('.tess-error-detail');
    if (errDetail) errDetail.textContent = error.message;
  } finally {
    searchBtn.disabled = false;
    searchBtn.style.opacity = '1';
    searchBtn.textContent = '🔍 Cerca';
  }
}

/**
 * Search ZTF bands by Gaia ID (Step 1 - search available bands)
 */
async function searchZTF() {
  const gaiaId = document.getElementById('import-gaia-id')?.value;
  const resultsDiv = document.getElementById('import-results');
  const searchBtn = document.getElementById('import-search-btn');

  if (!gaiaId) {
    showImportStatus('error', 'Gaia ID mancante');
    return;
  }

  searchBtn.disabled = true;
  searchBtn.style.opacity = '0.6';
  searchBtn.textContent = 'Ricerca ZTF in corso...';
  showImportStatus('info', 'Step 1/2: Ricerca bande ZTF disponibili su IRSA...');
  resultsDiv.innerHTML = '<p style="color: #999; text-align: center; padding: 2rem;">Interrogazione archivio ZTF su IRSA...</p>';

  try {
    const response = await fetch('/agata/admin/api/catalogs/ztf/search-bands', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ gaia_id: gaiaId })
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.error || `HTTP ${response.status}`);
    }

    const data = await response.json();
    if (!data.success) {
      throw new Error(data.error || 'Search failed');
    }

    displayZTFResults(data, gaiaId);
    showImportStatus('success', 'Step 2/2: Seleziona una o piu bande da importare');

  } catch (error) {
    console.error('[ImportCatalogs] ZTF search error:', error);
    showImportStatus('error', `Errore: ${error.message}`);
    resultsDiv.innerHTML = `
      <div style="padding: 2rem; text-align: center;">
        <p style="color: #dc2626; font-weight: 600;">Errore durante la ricerca ZTF</p>
        <p style="color: #666; font-size: 0.9rem;">${error.message}</p>
      </div>
    `;
  } finally {
    searchBtn.disabled = false;
    searchBtn.style.opacity = '1';
    searchBtn.textContent = '🔍 Cerca';
  }
}

/**
 * Search ASAS-SN data by Gaia ID (Step 1 - search available bands)
 */
async function searchASASSN() {
  const gaiaId = document.getElementById('import-gaia-id')?.value;
  const resultsDiv = document.getElementById('import-results');
  const searchBtn = document.getElementById('import-search-btn');

  if (!gaiaId) {
    showImportStatus('error', 'Gaia ID mancante');
    return;
  }

  searchBtn.disabled = true;
  searchBtn.style.opacity = '0.6';
  searchBtn.textContent = 'Ricerca ASAS-SN in corso...';
  showImportStatus('info', 'Step 1/2: Ricerca bande ASAS-SN disponibili...');
  resultsDiv.innerHTML = '<p style="color: #999; text-align: center; padding: 2rem;">Interrogazione archivio ASAS-SN...</p>';

  try {
    const response = await fetch('/agata/admin/api/catalogs/asassn/auto/search-data', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ gaia_id: gaiaId })
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.error || `HTTP ${response.status}`);
    }

    const data = await response.json();

    if (!data.success) {
      throw new Error(data.error || 'Search failed');
    }

    if (!data.data_available) {
      showImportStatus('warning', data.error || 'Nessun dato ASAS-SN trovato per questa stella');
      resultsDiv.innerHTML = `
        <div style="padding: 2rem; text-align: center; background: #fef3c7; border-radius: 6px; border: 1px solid #fcd34d;">
          <p style="color: #92400e; margin: 0;">${data.error || 'Nessun dato ASAS-SN disponibile'}</p>
        </div>
      `;
      return;
    }

    displayASASSNResults(data, gaiaId);
    showImportStatus('success', 'Step 2/2: Seleziona una o più bande da importare');

  } catch (error) {
    console.error('[ImportCatalogs] ASAS-SN search error:', error);
    showImportStatus('error', `Errore: ${error.message}`);
    resultsDiv.innerHTML = `
      <div style="padding: 2rem; text-align: center;">
        <p style="color: #dc2626; font-weight: 600;">Errore durante la ricerca ASAS-SN</p>
        <p style="color: #666; font-size: 0.9rem;">${error.message}</p>
      </div>
    `;
  } finally {
    searchBtn.disabled = false;
    searchBtn.style.opacity = '1';
    searchBtn.textContent = '🔍 Cerca';
  }
}

/**
 * Display ASAS-SN search results with per-band selection (like ZTF)
 */
function displayASASSNResults(data, gaiaId) {
  const resultsDiv = document.getElementById('import-results');
  if (!resultsDiv) return;

  // Bande già importate
  const importedBands = new Set();
  for (const sessionName of state.sessionNameFromDB.values()) {
    if (sessionName === 'ASAS-SN V' || sessionName === 'ASAS-SN g') {
      importedBands.add(sessionName);
    }
  }

  const bands = data.bands || {};   // {"ASAS-SN V": 340, "ASAS-SN g": 1226}
  const bandStats = data.band_stats || {};
  const bandColors = { 'ASAS-SN V': '#f59e0b', 'ASAS-SN g': '#22c55e' };
  const bandDesc = {
    'ASAS-SN V': 'V-band storica (2014-2018), telescopi Brutus/Halley',
    'ASAS-SN g': 'g-band attuale (2017-presente), Sky Patrol V2'
  };

  let html = '<div style="display: flex; flex-direction: column; gap: 1.5rem;">';

  // Header
  html += `
    <div style="padding: 1rem; background: #f9fafb; border-radius: 6px; border: 1px solid #e5e7eb;">
      <h5 style="margin: 0 0 0.5rem 0; color: #374151;">ASAS-SN — Bande disponibili</h5>
      <div style="font-size: 0.9rem; color: #6b7280;">Gaia ID: <code>${data.gaia_id}</code> · ${data.point_count} punti totali</div>
    </div>
  `;

  if (Object.keys(bands).length > 0) {
    html += `<div style="display: flex; flex-direction: column; gap: 0.75rem;">`;

    for (const [band, count] of Object.entries(bands)) {
      const isAlreadyImported = importedBands.has(band);
      const color = bandColors[band] || '#6b7280';
      const desc = bandDesc[band] || 'Banda fotometrica ASAS-SN';
      const stats = bandStats[band] || {};
      const spanDays = stats.time_range?.span_days?.toFixed(0) || '?';
      const magMin = stats.mag_range?.min?.toFixed(2) || '?';
      const magMax = stats.mag_range?.max?.toFixed(2) || '?';

      const labelBgColor = isAlreadyImported ? '#f0fdf4' : '#f9fafb';
      const borderColor = isAlreadyImported ? '#bbf7d0' : '#e5e7eb';
      const importedBadge = isAlreadyImported
        ? `<span style="padding: 0.2rem 0.6rem; background: #10b981; color: white; border-radius: 10px; font-size: 0.75rem; font-weight: 600; white-space: nowrap;">✓ Già importato</span>`
        : '';

      html += `
        <label style="display: flex; align-items: flex-start; gap: 0.75rem; padding: 0.75rem 1rem; background: ${labelBgColor}; border-radius: 6px; cursor: ${isAlreadyImported ? 'default' : 'pointer'}; border: 1px solid ${borderColor}; transition: all 0.2s;">
          <input type="checkbox" name="import-asassn-bands" value="${band}"
            style="margin-top: 0.2rem; cursor: pointer;"
            onchange="updateASASSNSummary()"
            ${isAlreadyImported ? 'disabled' : ''}>
          <div style="flex-grow: 1;">
            <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.25rem;">
              <strong style="color: ${color};">${band}</strong>
              ${importedBadge}
            </div>
            <div style="font-size: 0.82rem; color: #6b7280; margin-bottom: 0.4rem;">${desc}</div>
            <div style="font-size: 0.85rem; color: #374151;">
              <strong>${count}</strong> punti ·
              <span style="color: #6b7280;">${spanDays} giorni · mag ${magMin}–${magMax}</span>
            </div>
          </div>
        </label>
      `;
    }

    html += `</div>`;

    html += `
      <div style="display: flex; align-items: center; gap: 1rem; padding-top: 0.5rem;">
        <button
          id="import-execute-btn-asassn"
          style="padding: 0.75rem 1.5rem; background: #10b981; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: 600; transition: opacity 0.2s;"
          onclick="executeASASSNImport('${gaiaId}')"
        >
          Importa bande selezionate
        </button>
        <span id="import-summary-asassn" style="font-size: 0.9rem; color: #6b7280;">Nessuna banda selezionata</span>
      </div>
    `;
  } else {
    html += `
      <div style="padding: 2rem; text-align: center; background: #fef3c7; border-radius: 6px; border: 1px solid #fcd34d;">
        <p style="color: #92400e; margin: 0;">Nessuna banda ASAS-SN disponibile per questa stella</p>
      </div>
    `;
  }

  html += '</div>';
  resultsDiv.innerHTML = html;
  updateASASSNSummary();
}

/**
 * Update ASAS-SN import summary (count selected bands)
 */
window.updateASASSNSummary = function() {
  const checkboxes = document.querySelectorAll('input[name="import-asassn-bands"]:checked');
  const summarySpan = document.getElementById('import-summary-asassn');
  if (summarySpan) {
    const count = checkboxes.length;
    summarySpan.textContent = count > 0
      ? `${count} ${count === 1 ? 'banda selezionata' : 'bande selezionate'}`
      : 'Nessuna banda selezionata';
  }
};

/**
 * Execute ASAS-SN import - Download selected bands one by one (like ZTF)
 */
window.executeASASSNImport = async function(gaiaId) {
  const selectedBands = Array.from(
    document.querySelectorAll('input[name="import-asassn-bands"]:checked')
  ).map(cb => cb.value);

  if (selectedBands.length === 0) {
    showImportStatus('error', 'Seleziona almeno una banda');
    return;
  }

  const resultsDiv = document.getElementById('import-results');
  const execBtn = document.getElementById('import-execute-btn-asassn');

  execBtn.disabled = true;
  execBtn.style.opacity = '0.6';
  execBtn.textContent = 'Import in corso...';

  showImportStatus('info', `Download e import (${selectedBands.length} ${selectedBands.length === 1 ? 'banda' : 'bande'})...`);

  let totalImported = 0;
  const errors = [];

  try {
    for (let i = 0; i < selectedBands.length; i++) {
      const band = selectedBands[i];
      const progress = `${i + 1}/${selectedBands.length}`;
      showImportStatus('info', `[${progress}] Download banda ${band}...`);

      try {
        const response = await fetch('/agata/admin/api/catalogs/asassn/download-band', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ gaia_id: gaiaId, band })
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.error || `HTTP ${response.status}`);
        }

        const result = await response.json();
        if (result.success) {
          totalImported += result.points_imported || 0;
          showImportStatus('info', `[${progress}] ${band}: ${result.points_imported} punti importati`);
        } else {
          errors.push(`${band}: ${result.error || 'Import failed'}`);
        }
      } catch (error) {
        errors.push(`${band}: ${error.message}`);
      }
    }

    if (totalImported > 0) {
      showImportStatus('success', `Import completato! ${totalImported} punti fotometrici importati`);
      resultsDiv.innerHTML = `
        <div style="padding: 1.5rem; background: #d1fae5; border-radius: 6px; border: 1px solid #6ee7b7; text-align: center;">
          <h5 style="color: #065f46; margin: 0 0 0.5rem 0;">Import Completato</h5>
          <p style="color: #047857; margin: 0;">
            ${totalImported} punti fotometrici importati da ${selectedBands.length} ${selectedBands.length === 1 ? 'banda' : 'bande'} ASAS-SN
          </p>
          ${errors.length > 0 ? `<p style="color: #b45309; font-size: 0.85rem; margin: 0.5rem 0 0 0;">Avvisi: ${errors.join(', ')}</p>` : ''}
        </div>
      `;
      // Ricarica la curva di luce con i nuovi dati
      if (typeof window.loadDataArrow === 'function') {
        await window.loadDataArrow();
      }
    } else if (errors.length > 0) {
      showImportStatus('error', 'Errori durante l\'import');
      resultsDiv.innerHTML = `
        <div style="padding: 1.5rem; background: #fee2e2; border-radius: 6px; border: 1px solid #fca5a5;">
          <h5 style="color: #991b1b; margin: 0 0 0.5rem 0;">Errori</h5>
          <ul class="import-errors-list" style="margin: 0; color: #7f1d1d;"></ul>
        </div>
      `;
      const errList = resultsDiv.querySelector('.import-errors-list');
      if (errList) errors.forEach(e => {
        const li = document.createElement('li');
        li.textContent = e;
        errList.appendChild(li);
      });
    } else {
      showImportStatus('error', 'Nessun punto importato');
    }

  } catch (error) {
    console.error('[ImportCatalogs] ASAS-SN import error:', error);
    showImportStatus('error', `Errore durante l'import: ${error.message}`);
  } finally {
    execBtn.disabled = false;
    execBtn.style.opacity = '1';
    execBtn.textContent = 'Importa bande selezionate';
  }
};

/**
 * Show status message (info/success/error)
 */
function showImportStatus(type, message) {
  const statusDiv = document.getElementById('import-status');
  if (!statusDiv) return;

  const colors = {
    info: { bg: '#dbeafe', text: '#1e40af' },
    success: { bg: '#d1fae5', text: '#065f46' },
    error: { bg: '#fee2e2', text: '#991b1b' }
  };

  const color = colors[type] || colors.info;
  statusDiv.style.background = color.bg;
  statusDiv.style.color = color.text;
  statusDiv.style.border = `1px solid ${color.text}`;
  statusDiv.textContent = message;
  statusDiv.style.display = 'block';
}

/**
 * Display TESS QLP search results with sector options
 */
function displayTESSResults(data, gaiaId) {
  const resultsDiv = document.getElementById('import-results');
  if (!resultsDiv) return;

  // Estrai i numeri di settore già importati da state.sessionNameFromDB
  const importedSectors = new Set();
  for (const sessionName of state.sessionNameFromDB.values()) {
    // Estrai numero settore da "TESS-QLP_Sector17"
    const match = sessionName.match(/TESS-QLP_Sector(\d+)/);
    if (match) {
      importedSectors.add(parseInt(match[1]));
    }
  }

  if (importedSectors.size > 0) {
    console.log('[ImportCatalogs] Already imported sectors:', Array.from(importedSectors).sort((a, b) => a - b));
  }

  let html = '<div style="display: flex; flex-direction: column; gap: 1.5rem;">';

  // Target Info
  html += `
    <div style="padding: 1rem; background: #f9fafb; border-radius: 6px; border: 1px solid #e5e7eb;">
      <h5 style="margin: 0 0 0.75rem 0; color: #374151;">Target TESS</h5>
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 0.5rem; font-size: 0.9rem;">
        <div><strong>Gaia ID:</strong> <code>${data.gaia_id}</code></div>
        <div><strong>TIC ID:</strong> <code>${data.tic_id}</code></div>
        <div><strong>TESS Mag:</strong> ${data.tmag?.toFixed(2) || 'N/A'}</div>
        <div><strong>Settori:</strong> ${data.sectors?.length || 0}</div>
      </div>
    </div>
  `;

  // Sector Options (Checkboxes)
  if (data.sectors && data.sectors.length > 0) {
    html += `
      <div style="padding: 1rem; border: 1px solid var(--border); border-radius: 6px; background: white;">
        <h5 style="margin: 0 0 1rem 0; color: #374151;">Seleziona settori da importare</h5>
        <div style="display: flex; flex-direction: column; gap: 0.75rem;">
    `;

    for (const sectorInfo of data.sectors) {
      const sector = sectorInfo.sector;
      const idx = sectorInfo.idx;
      const isAlreadyImported = importedSectors.has(sector);

      // Stile diverso se già importato
      const labelBgColor = isAlreadyImported ? '#f0fdf4' : '#f9fafb';
      const borderColor = isAlreadyImported ? '#dcfce7' : '#e5e7eb';

      // Badge se già importato
      const importedBadge = isAlreadyImported
        ? `<span style="margin-left: auto; padding: 0.25rem 0.75rem; background: #10b981; color: white; border-radius: 12px; font-size: 0.75rem; font-weight: 600; white-space: nowrap;">✓ Già importato</span>`
        : '';

      html += `
        <label style="display: flex; align-items: center; gap: 0.75rem; padding: 0.75rem; background: ${labelBgColor}; border-radius: 4px; cursor: ${isAlreadyImported ? 'default' : 'pointer'}; border: 1px solid ${borderColor}; transition: all 0.2s;">
          <input type="checkbox" name="import-sectors" value="${sector}" data-idx="${idx}" style="cursor: pointer;" onchange="updateImportSummary()" ${isAlreadyImported ? 'disabled' : ''}>
          <div style="flex-grow: 1;">
            <strong>Settore ${sector}</strong>
            <div style="font-size: 0.85rem; color: #666;">
              TESS QLP dati completi
            </div>
          </div>
          ${importedBadge}
        </label>
      `;
    }

    html += `
        </div>
        <div style="margin-top: 1rem; padding-top: 1rem; border-top: 1px solid #e5e7eb;">
          <button
            id="import-execute-btn"
            style="padding: 0.75rem 1.5rem; background: #10b981; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: 600; transition: opacity 0.2s;"
            onclick="executeImport('${data.gaia_id}', ${data.tic_id})"
          >
            Importa settori selezionati
          </button>
          <span id="import-summary" style="margin-left: 1rem; color: #666; font-size: 0.9rem;"></span>
        </div>
      </div>
    `;
  } else {
    html += `
      <div style="padding: 2rem; text-align: center; background: #fef3c7; border-radius: 6px; border: 1px solid #fcd34d;">
        <p style="color: #92400e; margin: 0;">Nessun settore QLP disponibile per questa stella</p>
        <p style="color: #b45309; font-size: 0.9rem; margin: 0.5rem 0 0 0;">Prova con un Gaia ID diverso</p>
      </div>
    `;
  }

  html += '</div>';
  resultsDiv.innerHTML = html;
  updateImportSummary();
}

/**
 * Display ZTF search results with band selection options
 */
function displayZTFResults(data, gaiaId) {
  const resultsDiv = document.getElementById('import-results');
  if (!resultsDiv) return;

  // Estrai bande già importate da state.sessionNameFromDB
  const importedBands = new Set();
  const bandNames = ['ZTFg', 'ZTFr', 'ZTFi'];

  for (const sessionName of state.sessionNameFromDB.values()) {
    for (const band of bandNames) {
      if (sessionName === band) {
        importedBands.add(band);
      }
    }
  }

  if (importedBands.size > 0) {
    console.log('[ImportCatalogs] Already imported ZTF bands:', Array.from(importedBands));
  }

  let html = '<div style="display: flex; flex-direction: column; gap: 1.5rem;">';

  // Target Info
  html += `
    <div style="padding: 1rem; background: #f9fafb; border-radius: 6px; border: 1px solid #e5e7eb;">
      <h5 style="margin: 0 0 0.75rem 0; color: #374151;">Target ZTF</h5>
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 0.5rem; font-size: 0.9rem;">
        <div><strong>Gaia ID:</strong> <code>${data.gaia_id}</code></div>
        <div><strong>RA:</strong> ${data.ra?.toFixed(6) || 'N/A'}</div>
        <div><strong>Dec:</strong> ${data.dec?.toFixed(6) || 'N/A'}</div>
        <div><strong>Bande disponibili:</strong> ${Object.keys(data.bands || {}).length}</div>
      </div>
    </div>
  `;

  // Band selection
  if (data.bands && Object.keys(data.bands).length > 0) {
    html += `
      <div style="padding: 1rem; border: 1px solid var(--border); border-radius: 6px; background: white;">
        <h5 style="margin: 0 0 1rem 0; color: #374151;">Seleziona bande da importare</h5>
        <div style="display: flex; flex-direction: column; gap: 0.75rem;">
    `;

    const bandColors = { 'ZTFg': '#22c55e', 'ZTFr': '#ef4444', 'ZTFi': '#a855f7' };
    const bandFiltercodes = { 'ZTFg': 'zg', 'ZTFr': 'zr', 'ZTFi': 'zi' };

    for (const [band, count] of Object.entries(data.bands)) {
      const isAlreadyImported = importedBands.has(band);
      const color = bandColors[band] || '#6b7280';
      const filtercode = bandFiltercodes[band] || band.toLowerCase();

      // Stile diverso se già importato
      const labelBgColor = isAlreadyImported ? '#f0fdf4' : '#f9fafb';
      const borderColor = isAlreadyImported ? '#dcfce7' : '#e5e7eb';

      // Badge se già importato
      const importedBadge = isAlreadyImported
        ? `<span style="margin-left: auto; padding: 0.25rem 0.75rem; background: #10b981; color: white; border-radius: 12px; font-size: 0.75rem; font-weight: 600; white-space: nowrap;">✓ Già importato</span>`
        : '';

      html += `
        <label style="display: flex; align-items: center; gap: 0.75rem; padding: 0.75rem; background: ${labelBgColor}; border-radius: 4px; cursor: ${isAlreadyImported ? 'default' : 'pointer'}; border: 1px solid ${borderColor}; transition: all 0.2s;">
          <input type="checkbox" name="import-ztf-bands" value="${band}" data-filtercode="${filtercode}" style="cursor: pointer;" onchange="updateZTFSummary()" ${isAlreadyImported ? 'disabled' : ''}>
          <div style="flex-grow: 1;">
            <strong style="color: ${color};">Banda ${band}</strong>
            <div style="font-size: 0.85rem; color: #666;">
              ${count} punti fotometrici
            </div>
          </div>
          ${importedBadge}
        </label>
      `;
    }

    html += `
        </div>
        <div style="margin-top: 1rem; padding-top: 1rem; border-top: 1px solid #e5e7eb;">
          <button
            id="import-execute-btn-ztf"
            style="padding: 0.75rem 1.5rem; background: #10b981; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: 600; transition: opacity 0.2s;"
            onclick="executeZTFImport('${data.gaia_id}')"
          >
            Importa bande selezionate
          </button>
          <span id="import-summary-ztf" style="margin-left: 1rem; color: #666; font-size: 0.9rem;"></span>
        </div>
      </div>
    `;

    // Time and magnitude range
    if (data.time_range && data.mag_range) {
      html += `
        <div style="padding: 1rem; background: #f3f4f6; border-radius: 6px; border: 1px solid #e5e7eb; font-size: 0.9rem; color: #666;">
          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 0.75rem;">
            <div><strong>Copertura:</strong> ${data.time_range.span_days?.toFixed(0) || '?'} giorni</div>
            <div><strong>Range mag:</strong> ${data.mag_range?.min?.toFixed(2) || '?'} - ${data.mag_range?.max?.toFixed(2) || '?'}</div>
          </div>
        </div>
      `;
    }
  } else {
    html += `
      <div style="padding: 2rem; text-align: center; background: #fef3c7; border-radius: 6px; border: 1px solid #fcd34d;">
        <p style="color: #92400e; margin: 0;">Nessuna banda ZTF disponibile per questa stella</p>
        <p style="color: #b45309; font-size: 0.9rem; margin: 0.5rem 0 0 0;">La stella potrebbe essere fuori dalla copertura ZTF (Dec > -30°)</p>
      </div>
    `;
  }

  html += '</div>';
  resultsDiv.innerHTML = html;
  updateZTFSummary();
}

/**
 * Update import summary (count selected sectors) - TESS only
 */
window.updateImportSummary = function() {
  const checkboxes = document.querySelectorAll('input[name="import-sectors"]:checked');
  const summarySpan = document.getElementById('import-summary');

  if (summarySpan) {
    const count = checkboxes.length;
    const label = count === 1 ? 'settore' : 'settori';
    summarySpan.textContent = count > 0 ? `${count} ${label} selezionati` : 'Nessun settore selezionato';
  }
};

/**
 * Update ZTF import summary (count selected bands)
 */
window.updateZTFSummary = function() {
  const checkboxes = document.querySelectorAll('input[name="import-ztf-bands"]:checked');
  const summarySpan = document.getElementById('import-summary-ztf');

  if (summarySpan) {
    const count = checkboxes.length;
    const label = count === 1 ? 'banda' : 'bande';
    summarySpan.textContent = count > 0 ? `${count} ${label} selezionate` : 'Nessuna banda selezionata';
  }
};

/**
 * Execute ZTF import - Download and process selected bands
 */
window.executeZTFImport = async function(gaiaId) {
  const selectedBands = Array.from(
    document.querySelectorAll('input[name="import-ztf-bands"]:checked')
  ).map(cb => ({
    band: cb.value,
    filtercode: cb.dataset.filtercode
  }));

  if (selectedBands.length === 0) {
    showImportStatus('error', 'Seleziona almeno una banda');
    return;
  }

  const resultsDiv = document.getElementById('import-results');
  const execBtn = document.getElementById('import-execute-btn-ztf');

  execBtn.disabled = true;
  execBtn.style.opacity = '0.6';
  execBtn.textContent = 'Import in corso...';

  showImportStatus('info', `Download e import dei file in corso (${selectedBands.length} bande)...`);

  let totalImported = 0;
  let errors = [];

  try {
    // Download each band sequentially
    for (let i = 0; i < selectedBands.length; i++) {
      const bandInfo = selectedBands[i];
      const progress = `${i + 1}/${selectedBands.length}`;

      showImportStatus('info', `[${progress}] Download banda ${bandInfo.band}...`);

      try {
        const response = await fetch('/agata/admin/api/catalogs/ztf/download-band', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            gaia_id: gaiaId,
            band: bandInfo.band,
            filtercode: bandInfo.filtercode
          })
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.error || `HTTP ${response.status}`);
        }

        const result = await response.json();

        if (result.success) {
          totalImported += result.points_imported || 0;
          showImportStatus('info', `[${progress}] Banda ${bandInfo.band}: ${result.points_imported} punti importati`);
        } else {
          errors.push(`Banda ${bandInfo.band}: ${result.error || 'Import failed'}`);
        }
      } catch (error) {
        errors.push(`Banda ${bandInfo.band}: ${error.message}`);
      }
    }

    // Show final result
    if (totalImported > 0) {
      showImportStatus('success', `Import completato! ${totalImported} punti fotometrici importati`);
      resultsDiv.innerHTML = `
        <div style="padding: 1.5rem; background: #d1fae5; border-radius: 6px; border: 1px solid #6ee7b7; text-align: center;">
          <h5 style="color: #065f46; margin: 0 0 0.5rem 0;">Import Completato</h5>
          <p style="color: #047857; margin: 0;">
            ${totalImported} punti fotometrici importati da ${selectedBands.length} bande
          </p>
        </div>
      `;
      // Ricarica la curva di luce con i nuovi dati
      if (typeof window.loadDataArrow === 'function') {
        await window.loadDataArrow();
      }
    } else if (errors.length > 0) {
      showImportStatus('error', `Errori durante l'import`);
      resultsDiv.innerHTML = `
        <div style="padding: 1.5rem; background: #fee2e2; border-radius: 6px; border: 1px solid #fca5a5;">
          <h5 style="color: #991b1b; margin: 0 0 0.5rem 0;">Errori</h5>
          <ul style="margin: 0; color: #7f1d1d;">
            ${errors.map(e => `<li>${e}</li>`).join('')}
          </ul>
        </div>
      `;
    } else {
      showImportStatus('error', 'Nessun punto importato');
    }

  } catch (error) {
    console.error('[ImportCatalogs] ZTF import error:', error);
    showImportStatus('error', `Errore durante l'import: ${error.message}`);
  } finally {
    execBtn.disabled = false;
    execBtn.style.opacity = '1';
    execBtn.textContent = 'Importa bande selezionate';
  }
};

/**
 * Execute TESS import - Download and process selected sectors
 */
window.executeImport = async function(gaiaId, ticId) {
  const selectedSectors = Array.from(
    document.querySelectorAll('input[name="import-sectors"]:checked')
  ).map(cb => ({
    sector: parseInt(cb.value),
    idx: parseInt(cb.dataset.idx)
  }));

  if (selectedSectors.length === 0) {
    showImportStatus('error', 'Seleziona almeno un settore');
    return;
  }

  const resultsDiv = document.getElementById('import-results');
  const execBtn = document.getElementById('import-execute-btn');

  execBtn.disabled = true;
  execBtn.style.opacity = '0.6';
  execBtn.textContent = 'Import in corso...';

  showImportStatus('info', `Download e import dei file in corso (${selectedSectors.length} settori)...`);

  let totalImported = 0;
  let errors = [];

  try {
    // Download each sector sequentially
    for (let i = 0; i < selectedSectors.length; i++) {
      const sectorInfo = selectedSectors[i];
      const progress = `${i + 1}/${selectedSectors.length}`;

      showImportStatus('info', `[${progress}] Download settore ${sectorInfo.sector}...`);

      try {
        const downloadPayload = {
          gaia_id: gaiaId,
          tic_id: ticId,
          sector: sectorInfo.sector,
          sector_idx: sectorInfo.idx
        };

        // Include serialized SearchResult if available (optimization)
        if (window.lcfsSerializedData) {
          downloadPayload.lcfs_serialized = window.lcfsSerializedData;
          console.log('[ImportCatalogs] Using cached lcfs_serialized (skips Lightkurve search)');
        }

        const response = await fetch('/agata/admin/api/catalogs/tess/qlp/download-sector', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(downloadPayload)
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.error || `HTTP ${response.status}`);
        }

        const result = await response.json();

        if (result.success) {
          totalImported += result.points_imported || 0;
          showImportStatus('info', `[${progress}] Settore ${sectorInfo.sector}: ${result.points_imported} punti importati`);
        } else {
          errors.push(`Settore ${sectorInfo.sector}: ${result.error || 'Import failed'}`);
        }
      } catch (error) {
        errors.push(`Settore ${sectorInfo.sector}: ${error.message}`);
      }
    }

    // Show final result
    if (totalImported > 0) {
      showImportStatus('success', `Import completato! ${totalImported} punti fotometrici importati`);
      resultsDiv.innerHTML = `
        <div style="padding: 1.5rem; background: #d1fae5; border-radius: 6px; border: 1px solid #6ee7b7; text-align: center;">
          <h5 style="color: #065f46; margin: 0 0 0.5rem 0;">Import Completato</h5>
          <p style="color: #047857; margin: 0;">
            ${totalImported} punti fotometrici importati da ${selectedSectors.length} settori
          </p>
        </div>
      `;
      // Ricarica la curva di luce con i nuovi dati
      if (typeof window.loadDataArrow === 'function') {
        await window.loadDataArrow();
      }
    } else if (errors.length > 0) {
      showImportStatus('error', `Errori durante l'import`);
      resultsDiv.innerHTML = `
        <div style="padding: 1.5rem; background: #fee2e2; border-radius: 6px; border: 1px solid #fca5a5;">
          <h5 style="color: #991b1b; margin: 0 0 0.5rem 0;">Errori</h5>
          <ul style="margin: 0; color: #7f1d1d;">
            ${errors.map(e => `<li>${e}</li>`).join('')}
          </ul>
        </div>
      `;
    } else {
      showImportStatus('error', 'Nessun punto importato');
    }

  } catch (error) {
    console.error('[ImportCatalogs] Import error:', error);
    showImportStatus('error', `Errore durante l'import: ${error.message}`);
  } finally {
    execBtn.disabled = false;
    execBtn.style.opacity = '1';
    execBtn.textContent = 'Importa settori selezionati';
  }
};

// =============================================================================
// FILE UPLOAD
// =============================================================================

/**
 * Mostra il form di caricamento file nell'area import-results
 */
function displayFileUploadForm() {
  const gaiaId = document.getElementById('import-gaia-id')?.value || '';
  const resultsDiv = document.getElementById('import-results');
  if (!resultsDiv) return;

  resultsDiv.innerHTML = `
    <div style="max-width: 600px; margin: 0 auto; padding: 1rem;">

      <!-- File input -->
      <div style="margin-bottom: 1rem;">
        <label style="display: block; font-weight: 600; margin-bottom: 0.4rem; font-size: 0.9rem; color: #374151;">
          File dati fotometrici <span style="color: #ef4444;">*</span>
        </label>
        <input type="file" id="import-file-input" accept=".csv,.txt,.dat"
               style="display: block; width: 100%; padding: 0.4rem; border: 1px solid #cbd5e1;
                      border-radius: 4px; font-size: 0.9rem; cursor: pointer;">
        <div style="font-size: 0.8rem; color: #6b7280; margin-top: 0.3rem;">
          CSV o TXT con colonne: tempo, magnitudine, errore (opz.). Supporta file ASAS-SN.
        </div>
      </div>

      <!-- Gaia ID (readonly) -->
      <div style="margin-bottom: 1rem;">
        <label style="display: block; font-weight: 600; margin-bottom: 0.4rem; font-size: 0.9rem; color: #374151;">
          Gaia DR3 ID
        </label>
        <input type="text" id="file-gaia-id" value="${gaiaId}" readonly
               style="width: 100%; padding: 0.4rem 0.6rem; border: 1px solid #cbd5e1;
                      border-radius: 4px; font-size: 0.9rem; box-sizing: border-box;
                      background: #f1f5f9; color: #64748b; cursor: default;">
      </div>

      <!-- Nome catalogo -->
      <div style="margin-bottom: 1rem;">
        <label style="display: block; font-weight: 600; margin-bottom: 0.4rem; font-size: 0.9rem; color: #374151;">
          Nome catalogo/sorgente
        </label>
        <input type="text" id="file-catalog-name"
               placeholder="es. AAVSO, Osservatorio XYZ"
               style="width: 100%; padding: 0.4rem 0.6rem; border: 1px solid #cbd5e1;
                      border-radius: 4px; font-size: 0.9rem; box-sizing: border-box;">
        <div style="font-size: 0.8rem; color: #6b7280; margin-top: 0.3rem;">
          Opzionale. Se vuoto usa il nome del file.
        </div>
      </div>

      <!-- Opzioni avanzate -->
      <details style="margin-bottom: 1rem; border: 1px solid #e2e8f0; border-radius: 6px; padding: 0.6rem 0.8rem;">
        <summary style="cursor: pointer; font-weight: 600; font-size: 0.9rem; color: #374151; user-select: none;">
          ⚙️ Opzioni avanzate
        </summary>
        <div style="margin-top: 0.8rem; display: grid; grid-template-columns: 1fr 1fr; gap: 0.8rem;">
          <div>
            <label style="display: block; font-size: 0.85rem; font-weight: 500; margin-bottom: 0.3rem; color: #4b5563;">
              Formato tempo
            </label>
            <select id="file-time-format"
                    style="width: 100%; padding: 0.35rem; border: 1px solid #cbd5e1; border-radius: 4px; font-size: 0.85rem;">
              <option value="hjd">HJD (Heliocentric Julian Date)</option>
              <option value="jd">JD (Julian Date)</option>
              <option value="mjd">MJD (Modified Julian Date)</option>
              <option value="bjd">BJD (Barycentric Julian Date)</option>
              <option value="btjd">BTJD (TESS)</option>
            </select>
          </div>
          <div>
            <label style="display: block; font-size: 0.85rem; font-weight: 500; margin-bottom: 0.3rem; color: #4b5563;">
              Banda
            </label>
            <input type="text" id="file-band" placeholder="es. V, R, g"
                   style="width: 100%; padding: 0.35rem 0.5rem; border: 1px solid #cbd5e1;
                          border-radius: 4px; font-size: 0.85rem; box-sizing: border-box;">
          </div>
          <div>
            <label style="display: block; font-size: 0.85rem; font-weight: 500; margin-bottom: 0.3rem; color: #4b5563;">
              Col. tempo
            </label>
            <input type="text" id="file-time-col" placeholder="auto"
                   style="width: 100%; padding: 0.35rem 0.5rem; border: 1px solid #cbd5e1;
                          border-radius: 4px; font-size: 0.85rem; box-sizing: border-box;">
          </div>
          <div>
            <label style="display: block; font-size: 0.85rem; font-weight: 500; margin-bottom: 0.3rem; color: #4b5563;">
              Col. mag
            </label>
            <input type="text" id="file-mag-col" placeholder="auto"
                   style="width: 100%; padding: 0.35rem 0.5rem; border: 1px solid #cbd5e1;
                          border-radius: 4px; font-size: 0.85rem; box-sizing: border-box;">
          </div>
          <div>
            <label style="display: block; font-size: 0.85rem; font-weight: 500; margin-bottom: 0.3rem; color: #4b5563;">
              Col. errore
            </label>
            <input type="text" id="file-err-col" placeholder="auto"
                   style="width: 100%; padding: 0.35rem 0.5rem; border: 1px solid #cbd5e1;
                          border-radius: 4px; font-size: 0.85rem; box-sizing: border-box;">
          </div>
        </div>
      </details>

      <!-- Preview area -->
      <div id="file-preview" style="margin-bottom: 1rem;"></div>

      <!-- Import button -->
      <button id="btn-import-file" disabled
              onclick="executeFileImport()"
              style="width: 100%; padding: 0.6rem 1rem; background: #3b82f6; color: white;
                     border: none; border-radius: 4px; font-size: 0.95rem; font-weight: 600;
                     cursor: not-allowed; opacity: 0.5; transition: opacity 0.2s;">
        📥 Importa file
      </button>

      <!-- Link ASAS-SN SkyPatrol -->
      <div style="margin-top: 1rem; padding: 0.75rem; background: #f0f9ff; border: 1px solid #bae6fd;
                  border-radius: 6px; font-size: 0.85rem; color: #0369a1;">
        <strong>Per file ASAS-SN:</strong>
        <a href="http://asas-sn.ifa.hawaii.edu/skypatrol/" target="_blank" rel="noopener"
           style="color: #2563eb; font-weight: 600;">
          🔗 Apri ASAS-SN SkyPatrol
        </a>
        → sezione <em>Cross Match Search</em> → inserisci il Gaia ID
        <strong>${gaiaId ? `<span style="font-family:monospace; background:#e0f2fe; padding:1px 5px; border-radius:3px;">${_escHtml(gaiaId)}</span>` : 'della stella'}</strong>
        → scarica il file CSV → caricalo qui sopra.
      </div>
    </div>
  `;

  // Listener file change: preview + abilita bottone
  document.getElementById('import-file-input')?.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const previewDiv = document.getElementById('file-preview');
    const importBtn = document.getElementById('btn-import-file');

    // Leggi prime righe per preview
    const reader = new FileReader();
    reader.onload = (ev) => {
      const lines = ev.target.result.split('\n').slice(0, 8).filter(l => l.trim());
      const preview = lines.map(l => `<code style="display:block; word-break:break-all; font-size:0.75rem;">${_escHtml(l)}</code>`).join('');
      previewDiv.innerHTML = `
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 4px; padding: 0.6rem;
                    font-family: monospace; font-size: 0.8rem; overflow-x: auto;">
          <div style="font-size: 0.8rem; font-weight: 600; color: #374151; margin-bottom: 0.4rem;">
            📄 ${_escHtml(file.name)} (${_fmtSize(file.size)}) — prime righe:
          </div>
          ${preview}
        </div>
      `;
    };
    reader.readAsText(file.slice(0, 2000));

    // Abilita bottone
    importBtn.disabled = false;
    importBtn.style.opacity = '1';
    importBtn.style.cursor = 'pointer';
  });
}

function _escHtml(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
function _fmtSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

/**
 * Esegue il caricamento del file verso il backend
 */
window.executeFileImport = async function() {
  const fileInput = document.getElementById('import-file-input');
  const gaiaId = document.getElementById('file-gaia-id')?.value?.trim();
  const resultsDiv = document.getElementById('import-results');
  const importBtn = document.getElementById('btn-import-file');

  if (!fileInput?.files[0]) {
    showImportStatus('error', 'Seleziona un file prima di importare');
    return;
  }
  if (!gaiaId) {
    showImportStatus('error', 'Gaia DR3 ID obbligatorio');
    return;
  }

  importBtn.disabled = true;
  importBtn.style.opacity = '0.6';
  importBtn.textContent = '⏳ Importazione in corso...';
  showImportStatus('info', 'Caricamento e parsing del file in corso...');

  try {
    const fd = new FormData();
    fd.append('file', fileInput.files[0]);
    fd.append('gaia_id', gaiaId);
    fd.append('catalog_name', document.getElementById('file-catalog-name')?.value?.trim() || '');
    fd.append('time_format', document.getElementById('file-time-format')?.value || 'hjd');
    fd.append('band', document.getElementById('file-band')?.value?.trim() || '');
    fd.append('time_col', document.getElementById('file-time-col')?.value?.trim() || '');
    fd.append('mag_col', document.getElementById('file-mag-col')?.value?.trim() || '');
    fd.append('err_col', document.getElementById('file-err-col')?.value?.trim() || '');

    const res = await fetch('/agata/admin/api/external-catalogs/upload-file', {
      method: 'POST',
      body: fd
    });

    const data = await res.json();

    if (!res.ok || !data.success) {
      throw new Error(data.error || `Errore server (${res.status})`);
    }

    showImportStatus('success', `Import completato: ${data.points_imported} punti importati`);

    const projectNote = data.project_created
      ? `<p style="margin: 0.4rem 0 0 0; font-size: 0.85rem; color: #065f46;">
           Progetto creato automaticamente: <strong>${_escHtml(data.project_code || '')}</strong>
         </p>`
      : '';

    resultsDiv.innerHTML = `
      <div style="max-width: 600px; margin: 0 auto; padding: 1rem;">
        <div style="padding: 1.25rem; background: #d1fae5; border-radius: 6px; border: 1px solid #6ee7b7;">
          <h5 style="color: #065f46; margin: 0 0 0.5rem 0;">✅ Import Completato</h5>
          <p style="color: #047857; margin: 0;">
            <strong>${data.points_imported}</strong> punti fotometrici importati
            da <strong>${_escHtml(data.source_name || fileInput.files[0].name)}</strong>
          </p>
          ${projectNote}
        </div>
      </div>
    `;

    console.log(`[ImportCatalogs] File import OK: ${data.points_imported} punti, source=${data.source_name}`);

    // Aggiorna curva di luce con i nuovi dati
    if (typeof window.loadDataArrow === 'function') {
      await window.loadDataArrow();
    }

  } catch (err) {
    console.error('[ImportCatalogs] File import error:', err);
    showImportStatus('error', `Errore: ${err.message}`);
    importBtn.disabled = false;
    importBtn.style.opacity = '1';
    importBtn.textContent = '📥 Importa file';
  }
};
