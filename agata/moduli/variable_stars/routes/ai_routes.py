"""
ai_routes.py - AI Advisor con LLM per analisi curve di luce

Analizza sessioni fotometriche usando LLM (Cerebras/Claude/OpenAI) per:
- Qualità delle sessioni (noise, gaps, outliers)
- Suggerimenti pre-processing
- Range ottimale periodigramma
- Classificazione tipo variabile
- Stelle analoghe approvate dalla KB (analyze-with-kb)
"""

import json
import logging
import numpy as np
from collections import defaultdict
from flask import request, jsonify
from flask_login import login_required, current_user
from astropy.stats import mad_std

from agata.db import SessionLocal
from agata.auth_models import Project
from agata.moduli.variable_stars import variable_stars_bp
from agata.moduli.variable_stars.constants import MIN_POINTS_PER_SESSION
from agata.moduli.variable_stars.services.arrow_parser import read_arrow_table
from agata.moduli.variable_stars.services.llm_client import LLMClient

logger = logging.getLogger(__name__)


@variable_stars_bp.post("/api/analyze_with_llm.arrow")
def api_analyze_with_llm():
    """
    Analizza sessioni fotometriche usando Claude AI per suggerimenti intelligenti.

    Questo endpoint usa LLM per analizzare:
    1. Qualità delle sessioni (noise, gaps, outliers)
    2. Suggerimenti pre-processing (zero-align, detrending, sigma-clipping)
    3. Range ottimale per periodigramma
    4. Classificazione tipo di variabile (se periodigramma disponibile)

    Request:
        Body: Arrow IPC stream con colonne:
            - jd: float64 - Julian Date
            - mag: float64 - Magnitudine
            - session_id: int32 - ID sessione

        Query params (opzionali):
            - has_periodogram: bool - Se true, include analisi periodigramma
            - periods: str - JSON array con periodi trovati (es: "[0.5, 1.0]")
            - amplitudes: str - JSON array con ampiezze (es: "[0.3, 0.1]")

    Returns:
        JSON: Analisi strutturata con suggerimenti e classificazione

    Note:
        - Richiede API key configurata (CEREBRAS_API_KEY/ANTHROPIC_API_KEY/OPENAI_API_KEY)
        - Provider selezionabile via env AI_PROVIDER (default: cerebras)
        - Timeout 30s per chiamata API
    """
    try:
        # ===== INIZIALIZZA CLIENT LLM =====
        try:
            llm_client = LLMClient()
        except ValueError as e:
            logger.error(f"Errore configurazione AI: {e}")
            return jsonify({"error": str(e)}), 500

        # Leggi dati Arrow
        table = read_arrow_table(request.get_data(cache=False))

        jd = np.asarray(table["jd"].to_numpy(zero_copy_only=False), dtype=float)
        mag = np.asarray(table["mag"].to_numpy(zero_copy_only=False), dtype=float)
        session_id = np.asarray(table["session_id"].to_numpy(zero_copy_only=False), dtype=np.int32)

        # Parametri opzionali
        has_periodogram = request.args.get("has_periodogram", "false").lower() == "true"
        periods_str = request.args.get("periods", "[]")
        amplitudes_str = request.args.get("amplitudes", "[]")

        try:
            periods = json.loads(periods_str) if periods_str else []
            amplitudes = json.loads(amplitudes_str) if amplitudes_str else []
        except json.JSONDecodeError:
            periods = []
            amplitudes = []

        logger.info(f"AI Advisor: analizzando {len(np.unique(session_id))} sessioni, {len(jd)} punti totali")

        # ===== FASE 1: CALCOLA STATISTICHE PER SESSIONE =====
        session_stats = _compute_session_statistics(jd, mag, session_id)

        # ===== ANALISI OMOGENEITÀ TRA SESSIONI =====
        session_homogeneity = _analyze_session_homogeneity(
            jd, mag, session_id, session_stats, has_periodogram, periods
        )

        # ===== FASE 2: COSTRUISCI PROMPT PER LLM =====
        prompt = _build_llm_prompt(
            jd, mag, session_stats, session_homogeneity,
            has_periodogram, periods, amplitudes
        )

        # ===== FASE 3: CHIAMA LLM API =====
        logger.info("Chiamata LLM API...")

        try:
            llm_response = llm_client.generate(prompt, max_tokens=4096, temperature=0.3)
            response_text = llm_response["response_text"]
            model_used = llm_response["model_used"]
            provider = llm_response["provider"]

            logger.info(f"Risposta AI ricevuta: {len(response_text)} caratteri")

            # Parse JSON
            analysis = _parse_llm_response(response_text)

        except Exception as e:
            logger.error(f"Errore chiamata LLM: {e}", exc_info=True)
            return jsonify({"error": f"Errore comunicazione con AI: {str(e)}"}), 500

        # ===== FASE 4: NORMALIZZA E ARRICCHISCI RISPOSTA =====
        analysis = _normalize_llm_response(analysis)

        result = {
            "analysis": analysis,
            "summary": _generate_summary(analysis),
            "warnings": _extract_warnings(session_stats),
            "homogeneity": session_homogeneity,
            "llm_model": model_used,
            "ai_provider": provider,
            "timestamp": jd.max()
        }

        logger.info("AI Advisor completato con successo")

        return jsonify(result)

    except ValueError as e:
        logger.error(f"Errore validazione AI advisor: {e}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Errore AI advisor: {e}", exc_info=True)
        return jsonify({"error": "Errore interno"}), 500


# ==========================================================
# FUNZIONI HELPER INTERNE
# ==========================================================

def _compute_session_statistics(jd, mag, session_id):
    """Calcola statistiche per ogni sessione."""
    session_stats = {}
    unique_sessions = np.unique(session_id)

    for sid in unique_sessions:
        mask = (session_id == sid)
        session_jd = jd[mask]
        session_mag = mag[mask]

        n_points = len(session_mag)

        if n_points < 3:
            session_stats[int(sid)] = {
                "n_points": n_points,
                "quality_score": 0,
                "issues": ["Troppo pochi punti (<3)"]
            }
            continue

        # Statistiche robuste
        median = float(np.median(session_mag))
        mad = float(mad_std(session_mag))
        amplitude = float(np.max(session_mag) - np.min(session_mag))

        # Gaps temporali
        jd_sorted = np.sort(session_jd)
        gaps = np.diff(jd_sorted)
        max_gap = float(np.max(gaps)) if len(gaps) > 0 else 0
        median_gap = float(np.median(gaps)) if len(gaps) > 0 else 0

        # Durata sessione
        duration = float(jd_sorted[-1] - jd_sorted[0])

        # Stima qualità (0-10)
        quality = 10.0
        issues = []

        if n_points < MIN_POINTS_PER_SESSION:
            quality -= 3
            issues.append(f"Pochi punti ({n_points})")

        if mad > 0.2:
            quality -= 2
            issues.append(f"Alto rumore fotometrico (MAD={mad:.3f})")

        if max_gap > 0.5 and max_gap > 3 * median_gap:
            quality -= 1
            issues.append(f"Gap temporali significativi ({max_gap:.2f}d)")

        if duration < 0.1:
            quality -= 1
            issues.append("Sessione molto breve")

        quality = max(0, quality)

        session_stats[int(sid)] = {
            "n_points": n_points,
            "median_mag": median,
            "mad": mad,
            "amplitude": amplitude,
            "duration_days": duration,
            "max_gap_days": max_gap,
            "median_gap_days": median_gap,
            "quality_score": quality,
            "issues": issues
        }

    return session_stats


def _analyze_session_homogeneity(jd, mag, session_id, session_stats, has_periodogram, periods):
    """Analizza omogeneità tra sessioni."""
    unique_sessions = np.unique(session_id)

    if len(unique_sessions) <= 1:
        return {}

    session_medians = {}
    session_mads = {}

    for sid in unique_sessions:
        mask = (session_id == sid)
        session_mag = mag[mask]
        session_medians[int(sid)] = float(np.median(session_mag))
        session_mads[int(sid)] = float(mad_std(session_mag))

    median_values = list(session_medians.values())
    offset_range = float(np.max(median_values) - np.min(median_values))
    offset_std = float(np.std(median_values))

    mad_values = list(session_mads.values())
    mad_ratio = float(np.max(mad_values) / np.min(mad_values)) if np.min(mad_values) > 0 else 0

    # Controllo periodi spurii
    spurious_period_warnings = []
    if has_periodogram and periods:
        for sid in unique_sessions:
            sess_duration = session_stats[int(sid)]["duration_days"]
            for i, period in enumerate(periods[:3]):
                if 0.8 * sess_duration <= period <= 1.2 * sess_duration:
                    spurious_period_warnings.append({
                        "session_id": int(sid),
                        "session_duration": sess_duration,
                        "period": float(period),
                        "period_rank": i + 1,
                        "warning": f"Period {period:.2f}d is suspiciously close to session {sid} duration ({sess_duration:.2f}d)"
                    })

    # Outlier dominanti
    outlier_analysis = {}
    global_mad = float(mad_std(mag))
    for sid in unique_sessions:
        mask = (session_id == sid)
        session_mag = mag[mask]
        session_median = np.median(session_mag)
        outliers = np.abs(session_mag - session_median) > 3 * global_mad
        outlier_fraction = float(np.sum(outliers) / len(session_mag))
        if outlier_fraction > 0.1:
            outlier_analysis[int(sid)] = {
                "outlier_fraction": outlier_fraction,
                "outlier_count": int(np.sum(outliers))
            }

    return {
        "offset_range": offset_range,
        "offset_std": offset_std,
        "mad_ratio": mad_ratio,
        "session_medians": session_medians,
        "session_mads": session_mads,
        "spurious_period_warnings": spurious_period_warnings,
        "outlier_analysis": outlier_analysis
    }


def _build_llm_prompt(jd, mag, session_stats, session_homogeneity, has_periodogram, periods, amplitudes):
    """Costruisce prompt strutturato per LLM."""
    global_median = float(np.median(mag))
    global_amplitude = float(np.max(mag) - np.min(mag))
    total_duration = float(jd.max() - jd.min())

    prompt = f"""You are an expert astronomer analyzing photometric data of a variable star. Provide detailed scientific analysis.

**GLOBAL DATA:**
- Total points: {len(jd)}
- Number of sessions: {len(session_stats)}
- Total duration: {total_duration:.2f} days
- Variation amplitude: {global_amplitude:.3f} mag
- Median magnitude: {global_median:.2f}

**PER-SESSION STATISTICS:**
{json.dumps(session_stats, indent=2)}

**SESSION HOMOGENEITY ANALYSIS:**
{json.dumps(session_homogeneity, indent=2)}
"""

    if has_periodogram and periods:
        prompt += f"""

**PERIODOGRAM ANALYSIS:**
- Found periods (days): {periods[:5]}
- Amplitudes (mag): {amplitudes[:5]}
- Amplitude ratios: {[round(amplitudes[0]/a, 2) if a > 0 else 0 for a in amplitudes[1:3]] if len(amplitudes) > 1 else []}
- Period ratios: {[round(periods[0]/p, 2) if p > 0 else 0 for p in periods[1:3]] if len(periods) > 1 else []}
"""

    prompt += """

**YOUR TASK:**
Provide expert analysis as valid JSON with this EXACT structure:

{
  "session_quality": {
    "overall_score": <float 0-10>,
    "sessions": {
      "0": {
        "score": <float 0-10>,
        "issues": [<list of specific problems>],
        "recommendations": [<list of specific actions>]
      }
    }
  },
  "preprocessing_suggestions": [
    {
      "action": "<zero_align|detrending|sigma_clip|remove_session>",
      "priority": "<high|medium|low>",
      "reason": "<detailed scientific explanation>",
      "parameters": {<suggested parameters>}
    }
  ],
  "periodogram_recommendations": {
    "min_period": <float in days>,
    "max_period": <float in days>,
    "reasoning": "<scientific explanation based on session duration and gaps>"
  }"""

    if has_periodogram and periods:
        prompt += """,
  "variable_classification": {
    "type": "<specific variable star type>",
    "confidence": "<high|medium|low>",
    "reasoning": "<detailed scientific explanation>",
    "alternative_types": [<other possible types>]
  }"""

    prompt += """
}

**CRITICAL GUIDELINES:**
- Analyze EACH session individually with specific numeric scores
- Identify real issues (high MAD, gaps, low points, short duration)
- CHECK SESSION HOMOGENEITY: Look at offset_range, mad_ratio, spurious period warnings
- Suggest actions ONLY if needed (don't suggest if data is good)
- For periodogram range: consider session duration (Nyquist limit ~duration/2)
- Be specific with numbers and thresholds
- FLAG INHOMOGENEOUS SESSIONS: If sessions are not homogeneous, explicitly mention which ones and why

RESPOND ONLY WITH VALID JSON. NO OTHER TEXT BEFORE OR AFTER."""

    return prompt


def _parse_llm_response(response_text):
    """Parse risposta JSON dal LLM."""
    # Rimuovi markdown code blocks
    response_text = response_text.strip()
    if response_text.startswith("```json"):
        response_text = response_text[7:]
    if response_text.startswith("```"):
        response_text = response_text[3:]
    if response_text.endswith("```"):
        response_text = response_text[:-3]
    response_text = response_text.strip()

    return json.loads(response_text)


def _normalize_llm_response(analysis):
    """Normalizza risposta LLM a formato standard."""
    # Normalizza session_quality
    if "session_quality" in analysis:
        sq = analysis["session_quality"]
        if "sessions" not in sq:
            sessions_dict = {}
            overall_scores = []
            for key, value in sq.items():
                if isinstance(value, dict) and "score" in value:
                    sessions_dict[str(key)] = value
                    overall_scores.append(value.get("score", 5))
            analysis["session_quality"] = {
                "overall_score": sum(overall_scores) / len(overall_scores) if overall_scores else 5.0,
                "sessions": sessions_dict
            }

    # Normalizza periodogram_recommendations
    if "periodogram_recommendations" in analysis:
        pr = analysis["periodogram_recommendations"]
        if "period_range" in pr and "min_period" not in pr:
            period_range = pr["period_range"]
            if isinstance(period_range, list) and len(period_range) >= 2:
                pr["min_period"] = float(period_range[0])
                pr["max_period"] = float(period_range[1])
        if "suggestions" in pr and "reasoning" not in pr:
            pr["reasoning"] = pr["suggestions"]
        if "min_period" not in pr:
            pr["min_period"] = 0.1
        if "max_period" not in pr:
            pr["max_period"] = 10.0
        if "reasoning" not in pr:
            pr["reasoning"] = "Range basato sulla durata delle sessioni osservative"

    return analysis


def _generate_summary(analysis):
    """Genera riassunto testuale."""
    try:
        parts = []
        if "session_quality" in analysis:
            sq = analysis["session_quality"]
            if "overall_score" in sq:
                parts.append(f"Qualità globale: {sq['overall_score']:.1f}/10")
        if "preprocessing_suggestions" in analysis:
            high_priority = [s for s in analysis["preprocessing_suggestions"]
                           if s.get("priority") == "high"]
            if high_priority:
                parts.append(f"{len(high_priority)} azioni prioritarie raccomandate")
        if "variable_classification" in analysis:
            vc = analysis["variable_classification"]
            if "type" in vc:
                parts.append(f"Possibile {vc['type']}")
        return " • ".join(parts) if parts else "Analisi completata"
    except Exception as e:
        logger.warning(f"Errore generazione summary: {e}")
        return "Analisi completata"


def _extract_warnings(session_stats):
    """Estrai warning critici."""
    warnings = []
    for sid, stats in session_stats.items():
        if stats.get("quality_score", 10) < 3:
            warnings.append(f"Sessione {sid}: qualità molto bassa")
        if stats.get("n_points", 0) < MIN_POINTS_PER_SESSION:
            warnings.append(f"Sessione {sid}: troppo pochi punti per analisi affidabile")
    return warnings


# ==========================================================
# ENDPOINT UNIFICATO: ANALYZE WITH KB
# ==========================================================

@variable_stars_bp.post("/api/analyze-with-kb")
@login_required
def api_analyze_with_kb():
    """
    Analisi unificata: curva di luce + stelle analoghe approvate dalla KB + guida template AAVSO.

    Estende analyze_with_llm.arrow aggiungendo:
    - Ricerca semantica stelle GrAGVar analoghe (rating >= 8)
    - Immagini fisiche da Teams (phase plot, periodogramma, TPF)
    - Correzioni Otero/AAVSO per i casi analoghi
    - Guida LLM compilazione template AAVSO

    Solo superuser.

    Request:
        Body: Arrow IPC stream (jd, mag, session_id)
        Query params:
            - project_id: int
            - has_periodogram: bool
            - periods: JSON array
            - amplitudes: JSON array
            - variable_type: str
            - period_days: float
            - amplitude_mag: float
            - tess_sectors: JSON array
            - notes: str

    Returns:
        JSON: analisi curva + kb_analogues + template_guide
    """
    if current_user.role != 'superuser':
        return jsonify({"error": "Solo superuser"}), 403

    try:
        llm_client = LLMClient()
    except ValueError as e:
        logger.error(f"Errore configurazione AI: {e}")
        return jsonify({"error": str(e)}), 500

    try:
        # ===== FASE 1: ANALISI CURVA DI LUCE (identica all'endpoint esistente) =====
        table = read_arrow_table(request.get_data(cache=False))

        jd = np.asarray(table["jd"].to_numpy(zero_copy_only=False), dtype=float)
        mag = np.asarray(table["mag"].to_numpy(zero_copy_only=False), dtype=float)
        session_id = np.asarray(table["session_id"].to_numpy(zero_copy_only=False), dtype=np.int32)

        has_periodogram = request.args.get("has_periodogram", "false").lower() == "true"
        periods_str = request.args.get("periods", "[]")
        amplitudes_str = request.args.get("amplitudes", "[]")
        project_id_str = request.args.get("project_id")
        var_type = (request.args.get("variable_type") or "").strip()
        period_days_str = request.args.get("period_days")
        amplitude_mag_str = request.args.get("amplitude_mag")
        notes = (request.args.get("notes") or "").strip()

        try:
            periods = json.loads(periods_str) if periods_str else []
            amplitudes = json.loads(amplitudes_str) if amplitudes_str else []
        except json.JSONDecodeError:
            periods, amplitudes = [], []

        period = float(period_days_str) if period_days_str else (periods[0] if periods else None)
        amplitude = float(amplitude_mag_str) if amplitude_mag_str else (amplitudes[0] if amplitudes else None)

        logger.info(f"analyze-with-kb: {len(np.unique(session_id))} sessioni, project_id={project_id_str}")

        session_stats = _compute_session_statistics(jd, mag, session_id)
        session_homogeneity = _analyze_session_homogeneity(
            jd, mag, session_id, session_stats, has_periodogram, periods
        )

        # ===== FASE 2: DATI STELLA DAL DB =====
        project = None
        sectors_str = request.args.get("tess_sectors", "[]")
        try:
            sectors = json.loads(sectors_str) if sectors_str else []
        except json.JSONDecodeError:
            sectors = []

        if project_id_str:
            try:
                db = SessionLocal()
                try:
                    project = db.query(Project).filter_by(id=int(project_id_str)).first()
                finally:
                    db.close()
            except Exception as e:
                logger.warning(f"Errore recupero dati progetto: {e}")

        # ===== FASE 3: RICERCA KB ANALOGHE =====
        kb_analogues = []
        template_guide = None

        try:
            from agata.moduli.admin.routes.project_detail import (
                get_kb_services, _get_star_rating, _classify_image, _extract_graagvar,
                _get_star_gaia_id
            )
            from agata.kb.services.star_index import load_star_index, get_star_images

            # Query expansion
            queries = []
            if var_type or period or amplitude:
                q1_parts = []
                if var_type:
                    q1_parts.append(f"stella variabile tipo {var_type}")
                if period:
                    q1_parts.append(f"periodo {period:.4f} giorni")
                if amplitude:
                    q1_parts.append(f"ampiezza {amplitude:.2f} magnitudini")
                queries.append(' '.join(q1_parts))

            if sectors or notes:
                q2_parts = ['curva di luce TESS']
                if sectors:
                    q2_parts.append(f"settori {', '.join(str(s) for s in sectors)}")
                if notes:
                    q2_parts.append(notes)
                queries.append(' '.join(q2_parts))

            if var_type:
                queries.append(f"problemi analisi {var_type} blend contaminazione pixel TESS periodo doppio")

            if not queries:
                queries = [f"stella variabile {var_type or 'sconosciuta'}"]

            embedding_service, vector_store = get_kb_services()
            vecs = [np.array(embedding_service.embed(q)) for q in queries]
            combined_vec = np.mean(vecs, axis=0).tolist()
            raw_results = vector_store.search(combined_vec, top_k=25)

            star_index_data = load_star_index()
            by_star = defaultdict(lambda: {
                'star_id': None,
                'rating': 0,
                'messages': [],
                'max_score': 0.0,
                'variable_types': set(),
            })

            for r in raw_results:
                meta = r.get('metadata', {})
                score = r.get('score', 0.0)
                star_id = meta.get('star_id') or _extract_graagvar(
                    meta.get('subject', '') + ' ' + (meta.get('body_text') or '')[:200]
                )
                if not star_id:
                    continue
                entry = by_star[star_id]
                entry['star_id'] = star_id
                entry['messages'].append({
                    'source': meta.get('source', ''),
                    'score': round(score, 3),
                    'subject': meta.get('subject', ''),
                    'from_name': meta.get('from_name', ''),
                    'from_email': meta.get('from_email', ''),
                    'date': meta.get('date', ''),
                    'is_expert': (meta.get('from_email') or '').endswith('aavso.org'),
                    'body_text': (meta.get('body_text') or '')[:2000],
                })
                if score > entry['max_score']:
                    entry['max_score'] = score
                if meta.get('variable_type'):
                    entry['variable_types'].add(meta['variable_type'])

            # Reranking
            analogues_list = []
            for star_id, entry in by_star.items():
                rating = _get_star_rating(star_id)
                entry['rating'] = rating
                score = entry['max_score']

                if rating >= 8:
                    score += 0.20
                elif rating >= 6:
                    score += 0.05

                idx_entry = star_index_data.get(star_id, {})
                if var_type and var_type.upper() in [t.upper() for t in idx_entry.get('variable_types_discussed', [])]:
                    score += 0.15
                if period:
                    for p in idx_entry.get('period_values', []):
                        if p > 0 and abs(p - period) / period <= 0.10:
                            score += 0.10
                            break
                if idx_entry.get('expert_emails'):
                    score += 0.05

                entry['reranked_score'] = round(min(score, 1.0), 3)
                analogues_list.append(entry)

            approved = [a for a in analogues_list if a['rating'] >= 8]
            if len(approved) < 2:
                approved = [a for a in analogues_list if a['rating'] >= 6]
            if len(approved) < 2:
                approved = analogues_list

            approved.sort(key=lambda x: -x['reranked_score'])
            top_analogues = approved[:5]

            # Arricchisci con immagini e correzioni
            type_order = {'phase_plot': 0, 'periodogram': 1, 'tpf': 2, 'nearby_stars': 3, 'other': 4}
            for a in top_analogues:
                sid = a['star_id']
                idx_entry = star_index_data.get(sid, {})

                raw_images = get_star_images(sid)
                a['images'] = sorted([
                    {'filename': img['filename'], 'type': _classify_image(img['filename']), 'thread_dir': img['thread_dir']}
                    for img in raw_images
                ], key=lambda x: type_order.get(x['type'], 9))

                a['expert_corrections'] = [
                    c['text'] for c in idx_entry.get('corrections', []) if c.get('is_expert')
                ][:8]

                a['variable_types'] = sorted(a['variable_types']) or idx_entry.get('variable_types_discussed', [])
                a['period_values'] = idx_entry.get('period_values', [])
                a['similarity_score'] = a['reranked_score']
                a['gaia_id'] = _get_star_gaia_id(sid)

                expert_msgs = sorted(
                    [m for m in a['messages'] if m['is_expert']],
                    key=lambda m: -m['score']
                )
                a['best_expert_text'] = expert_msgs[0]['body_text'] if expert_msgs else ''

            kb_analogues = [{
                'star_id': a['star_id'],
                'gaia_id': a.get('gaia_id'),
                'rating': a['rating'],
                'variable_types': a['variable_types'],
                'similarity_score': a['similarity_score'],
                'period_values': a['period_values'],
                'expert_corrections': a['expert_corrections'],
                'images': a['images'],
                'messages_count': len(a['messages']),
                'has_expert': any(m['is_expert'] for m in a['messages']),
            } for a in top_analogues]

            # ===== FASE 4: PROMPT LLM UNIFICATO =====
            # Sezione A: qualità dati (esistente)
            curve_prompt = _build_llm_prompt(
                jd, mag, session_stats, session_homogeneity,
                has_periodogram, periods, amplitudes
            )

            # Sezione B: guida template AAVSO con KB
            stella_info = []
            if project and project.gaia_id:
                stella_info.append(f"Gaia DR3 source ID: {project.gaia_id}")
            if project and project.ra is not None:
                stella_info.append(f"Coordinate: RA={project.ra:.6f}°, Dec={project.dec_deg:.6f}°")
            if var_type:
                stella_info.append(f"Tipo variabile ipotizzato dall'analista: {var_type}")
            if period:
                stella_info.append(f"Periodo: {period:.6f} giorni")
            if amplitude:
                stella_info.append(f"Ampiezza: {amplitude:.3f} mag")
            if project and project.magnitude is not None:
                stella_info.append(f"Magnitudine media: {project.magnitude:.3f}")
            if project and project.passband:
                stella_info.append(f"Passband: {project.passband}")
            if sectors:
                stella_info.append(f"Settori TESS: {', '.join(str(s) for s in sectors)}")
            if project and project.teff:
                stella_info.append(f"Teff: {project.teff} K")
            if project and project.spectral_class:
                stella_info.append(f"Classe spettrale: {project.spectral_class}")
            if project and project.color_bprp:
                stella_info.append(f"BP-RP (Gaia): {project.color_bprp}")
            if project and project.color_bv:
                stella_info.append(f"B-V: {project.color_bv}")
            if project and project.distance:
                stella_info.append(f"Distanza: {project.distance} pc")
            if project and project.luminosity:
                stella_info.append(f"Luminosità: {project.luminosity}")
            if project and project.radius:
                stella_info.append(f"Raggio: {project.radius}")
            if project and project.variability_amplitude:
                stella_info.append(f"Ampiezza da catalogo: {project.variability_amplitude}")
            if project and project.catalog_identifiers:
                stella_info.append(f"Identificatori cataloghi:\n{project.catalog_identifiers[:400]}")
            if notes:
                stella_info.append(f"Note analista: {notes}")

            analogues_context_blocks = []
            for i, a in enumerate(top_analogues, 1):
                display_id = a.get('gaia_id') or a['star_id']
                block = [
                    f"CASO {i}: Gaia DR3 {display_id} (rating={a['rating']}, similarità={a['similarity_score']})",
                    f"  Tipo: {', '.join(a['variable_types']) or 'N/A'}",
                    f"  Periodi discussi: {a['period_values'] or 'N/A'}",
                    f"  Grafici disponibili: {', '.join(img['filename'] for img in a['images'][:4]) or 'nessuno'}",
                ]
                if a['expert_corrections']:
                    block.append("  Correzioni Otero:")
                    for c in a['expert_corrections'][:4]:
                        block.append(f"    - {c[:150]}")
                if a['best_expert_text']:
                    block.append(f"  Email esperto:\n    {a['best_expert_text'][:600]}")
                analogues_context_blocks.append('\n'.join(block))

            kb_prompt = f"""Sei un assistente esperto in astronomia delle stelle variabili e nel processo di submission al catalogo AAVSO VSX.

STELLA IN ANALISI:
{chr(10).join(f'- {s}' for s in stella_info)}

CASI PIÙ SIMILI GIÀ APPROVATI (rating >= 8):
{chr(10).join(analogues_context_blocks) if analogues_context_blocks else 'Nessun caso analogo trovato nella KB.'}

ISTRUZIONE IMPORTANTE: quando citi le stelle analoghe usa SEMPRE il loro Gaia DR3 source ID numerico (come indicato nel campo "Gaia DR3 XXXXXXXXX"), mai il nome interno GrAGVarXXX.

Produci una guida strutturata con ESATTAMENTE queste 5 sezioni in italiano:

## 1. Caratteristiche Estratte dalla Stella in Analisi
(elenco puntato con parametri chiave e implicazioni astronomiche)

## 2. Casi Analoghi Approvati
Per ogni caso usa il Gaia DR3 ID come identificatore:
- **Gaia DR3 ID**:
- **Similarità**: (Alta/Media con motivazione tecnica)
- **Perché simile**: (ragionamento tecnico su periodo, tipo, ampiezza)
- **Insight chiave**:
- **Come è stato compilato il template**:

## 3. Template AAVSO Raccomandato
Guida sezione per sezione con suggerimenti di wording dove utile.

## 4. Indicazioni Otero Applicabili
(punti specifici dalle correzioni recuperate che si applicano a questo caso)

## 5. Rischi e Incertezze
(cosa va validato prima della submission, possibili errori)

Usa terminologia astronomica appropriata. Non inventare dati non presenti nel contesto."""

            # Chiamate LLM separate: analisi curva e guida KB
            try:
                curve_response = llm_client.generate(curve_prompt, max_tokens=4096, temperature=0.3)
                analysis = _parse_llm_response(curve_response["response_text"])
                analysis = _normalize_llm_response(analysis)
                model_used = curve_response["model_used"]
                provider = curve_response["provider"]
            except Exception as e:
                logger.error(f"Errore LLM curva: {e}", exc_info=True)
                return jsonify({"error": f"Errore comunicazione con AI: {str(e)}"}), 500

            try:
                kb_response = llm_client.generate(kb_prompt, temperature=0.3, max_tokens=2000)
                template_guide = kb_response.get("response_text")
            except Exception as e:
                logger.warning(f"Errore LLM guida KB: {e}")
                template_guide = None

        except ImportError as e:
            logger.warning(f"KB non disponibile: {e}")
            # Fallback: solo analisi curva
            try:
                prompt = _build_llm_prompt(jd, mag, session_stats, session_homogeneity, has_periodogram, periods, amplitudes)
                curve_response = llm_client.generate(prompt, max_tokens=4096, temperature=0.3)
                analysis = _parse_llm_response(curve_response["response_text"])
                analysis = _normalize_llm_response(analysis)
                model_used = curve_response["model_used"]
                provider = curve_response["provider"]
            except Exception as e2:
                logger.error(f"Errore LLM: {e2}", exc_info=True)
                return jsonify({"error": f"Errore comunicazione con AI: {str(e2)}"}), 500
        except Exception as e:
            logger.error(f"Errore KB retrieval: {e}", exc_info=True)
            try:
                prompt = _build_llm_prompt(jd, mag, session_stats, session_homogeneity, has_periodogram, periods, amplitudes)
                curve_response = llm_client.generate(prompt, max_tokens=4096, temperature=0.3)
                analysis = _parse_llm_response(curve_response["response_text"])
                analysis = _normalize_llm_response(analysis)
                model_used = curve_response["model_used"]
                provider = curve_response["provider"]
            except Exception as e2:
                logger.error(f"Errore LLM fallback: {e2}", exc_info=True)
                return jsonify({"error": f"Errore comunicazione con AI: {str(e2)}"}), 500

        result = {
            "analysis": analysis,
            "summary": _generate_summary(analysis),
            "warnings": _extract_warnings(session_stats),
            "homogeneity": session_homogeneity,
            "kb_analogues": kb_analogues,
            "template_guide": template_guide,
            "llm_model": model_used,
            "ai_provider": provider,
            "timestamp": jd.max()
        }

        logger.info(f"analyze-with-kb completato: {len(kb_analogues)} analoghe trovate")
        return jsonify(result)

    except ValueError as e:
        logger.error(f"Errore validazione analyze-with-kb: {e}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Errore analyze-with-kb: {e}", exc_info=True)
        return jsonify({"error": "Errore interno"}), 500
