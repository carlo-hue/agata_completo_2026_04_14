// period-analysis.js
// Analisi multi-periodo con pre-whitening (usa backend Astropy)

import { buildAnalysisArraysTyped } from './math-logic.js';
import { buildArrowStreamJDMag } from '../common/utils-arrow.js';

/**
 * Analisi multi-periodo con pre-whitening iterativo
 * Delega il calcolo al backend Python che usa astropy.timeseries.LombScargle
 *
 * @param {number} nPeriods - Numero di periodi da cercare
 * @param {number} minP - Periodo minimo
 * @param {number} maxP - Periodo massimo
 * @returns {Array} - Array di oggetti periodo con statistiche
 */
export async function computeMultiPeriod(nPeriods, minP, maxP, nFreq = 10000) {
  const { jd, mag } = buildAnalysisArraysTyped();

  if (jd.length < 10) {
    throw new Error("Dati insufficienti per analisi multi-periodo");
  }

  console.log(`🎯 Multi-periodo (backend Astropy): ${nPeriods} periodi, ${jd.length} punti, n_freq=${nFreq}`);

  // Chiamata singola al backend che fa tutto il pre-whitening
  const res = await fetch(
    `/agata/variable-stars/api/multiperiod.arrow?min_period=${minP}&max_period=${maxP}&n_freq=${nFreq}&n_periods=${nPeriods}`,
    {
      method: "POST",
      body: buildArrowStreamJDMag(jd, mag)
    }
  );

  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.error || "Errore server");
  }

  const data = await res.json();

  // Converti formato backend → formato atteso dal frontend
  const results = data.periods.map(p => ({
    iteration: p.iteration,
    period: p.period,
    power: p.power,
    fap: p.fap,
    snr: p.snr,
    amplitude: p.amplitude,
    spectrum: p.iteration === 1 ? data.spectrum : null // Solo prima iterazione
  }));

  // Log risultati
  console.log(`✅ Trovati ${results.length} periodi:`);
  results.forEach((r, idx) => {
    console.log(`   P${idx + 1}: ${r.period.toFixed(6)} d (Amp: ${r.amplitude.toFixed(4)} mag, FAP: ${r.fap.toExponential(2)})`);
  });

  return results;
}

/**
 * Analisi periodogramma su dati JD/MAG già estratti (senza leggere state globale)
 * Usato per calcolare il periodigramma per singola sessione
 *
 * @param {Float64Array} jd - Array di Julian Dates
 * @param {Float32Array} mag - Array di magnitudini
 * @param {number} minP - Periodo minimo
 * @param {number} maxP - Periodo massimo
 * @param {boolean} usePrewhiten - Se true usa multiperiod con pre-whitening
 * @param {number} nPeriods - Numero di periodi da cercare (se usePrewhiten)
 * @param {boolean} advancedFourier - Se true usa pre-whitening Fourier N-armoniche
 * @param {number} nHarmonics - Numero di armoniche (solo se advancedFourier=true)
 * @returns {Object} - {type, periods, spectrum, simon_lee?, classification?}
 */
export async function computePeriodogramForData(jd, mag, minP, maxP, usePrewhiten = false, nPeriods = 3, advancedFourier = false, nHarmonics = 4, nFreq = 10000) {
  if (jd.length < 5) {
    throw new Error(`Dati insufficienti: ${jd.length} punti`);
  }

  const body = buildArrowStreamJDMag(jd, mag);

  if (usePrewhiten && nPeriods > 1 && advancedFourier) {
    const res = await fetch(
      `/agata/variable-stars/api/multiperiod_fourier.arrow?min_period=${minP}&max_period=${maxP}&n_freq=${nFreq}&n_periods=${nPeriods}&n_harmonics=${nHarmonics}`,
      { method: "POST", body }
    );
    if (!res.ok) throw new Error((await res.json()).error || "Errore server");
    const data = await res.json();
    return {
      type: "multiperiod_fourier",
      periods: data.periods,
      spectrum: data.spectrum,
      simon_lee: data.simon_lee || {},
      classification: data.classification || ""
    };
  } else if (usePrewhiten && nPeriods > 1) {
    const res = await fetch(
      `/agata/variable-stars/api/multiperiod.arrow?min_period=${minP}&max_period=${maxP}&n_freq=${nFreq}&n_periods=${nPeriods}`,
      { method: "POST", body }
    );
    if (!res.ok) throw new Error((await res.json()).error || "Errore server");
    const data = await res.json();
    return {
      type: "multiperiod",
      periods: data.periods.map(p => ({
        iteration: p.iteration,
        period: p.period,
        power: p.power,
        fap: p.fap,
        snr: p.snr,
        amplitude: p.amplitude,
        spectrum: p.iteration === 1 ? data.spectrum : null
      })),
      spectrum: data.spectrum
    };
  } else {
    const res = await fetch(
      `/agata/variable-stars/api/periodogram.arrow?min_period=${minP}&max_period=${maxP}&n_freq=${nFreq}`,
      { method: "POST", body }
    );
    if (!res.ok) throw new Error((await res.json()).error || "Errore server");
    const data = await res.json();
    return {
      type: "single",
      periods: data.peaks.map((p, i) => ({
        iteration: i + 1,
        period: p.period,
        power: p.power,
        fap: p.fap,
        snr: p.snr,
        amplitude: null,
        spectrum: i === 0 ? { period: data.period, power: data.power, fap_levels: data.fap_levels } : null
      })),
      spectrum: { period: data.period, power: data.power, fap_levels: data.fap_levels }
    };
  }
}

/**
 * Classifica un singolo periodo in base al suo valore
 */
export function classifySinglePeriod(period) {
  if (period < 0.2) {
    return "δ Scuti / SX Phe";
  } else if (period >= 0.2 && period < 1.0) {
    return "RR Lyrae / δ Scuti";
  } else if (period >= 1.0 && period < 3.0) {
    return "Binaria eclissante";
  } else if (period >= 3.0 && period < 10.0) {
    return "Cefeide classica";
  } else if (period >= 10.0 && period < 50.0) {
    return "Mira / Semi-regolare";
  } else {
    return "Variabile lenta";
  }
}

/**
 * Genera suggerimento tipo variabile basato sui periodi trovati
 */
export function suggestVariableType(results) {
  if (!results || results.length === 0) return "Sconosciuto";

  const P1 = results[0].period;
  const suggestions = [];

  // Controlli specifici sul periodo principale
  if (P1 > 0.2 && P1 < 1.0) {
    suggestions.push("RR Lyrae / δ Scuti");
  } else if (P1 > 1.0 && P1 < 10.0) {
    suggestions.push("Cefeide / Binaria");
  } else if (P1 < 0.2) {
    suggestions.push("δ Scuti / SX Phe");
  } else if (P1 > 10.0) {
    suggestions.push("Mira / Semi-regolare");
  }

  // Se ci sono più periodi, controlla relazioni
  if (results.length >= 2) {
    const P2 = results[1].period;
    const ratio = P1 / P2;

    // Cerca pattern specifici
    if (Math.abs(ratio - 2) < 0.15) {
      // P2 è circa metà di P1 → probabile binaria o armonica
      suggestions.push("Binaria (P₂ ≈ P₁/2)");
    } else if (ratio > 5 && ratio < 15) {
      // P1 molto più lungo di P2 → binaria + pulsazione
      suggestions.push("Binaria + δ Scuti");
    } else if (ratio >= 1.2 && ratio <= 3) {
      // Periodi simili → multi-modo pulsazionale
      suggestions.push("Multi-modo (γ Dor / SPB)");
    }

    // Cerca periodo orbitale tipico + pulsazione rapida
    if (P1 > 1.0 && P1 < 5.0 && P2 > 0.2 && P2 < 0.5) {
      suggestions.push("Algol-type + pulsazioni");
    }
  }

  // Se ci sono 3+ periodi, specifica complessità
  if (results.length >= 3) {
    suggestions.push(`(${results.length} periodi)`);
  }

  return suggestions.length > 0 ? suggestions.join(" • ") : "Variabile multi-periodica";
}
