from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import math
import random
import time
from typing import Any


@dataclass(frozen=True)
class GaiaConeQueryParams:
    ra_deg: float
    dec_deg: float
    radius_deg: float
    gmax: float = 21.0
    ruwe_max: float | None = 1.6
    enforce_extragal: bool = True
    max_rows: int | None = None
    tries: int = 3
    sleep_s: float = 3.0
    use_sync_fallback: bool = True
    verbose: bool = False
    provider_mode: str = "mock"


@dataclass
class GaiaQueryMeta:
    provider_mode: str
    table_name: str
    adql: str
    jobid: str | None
    job_url: str | None
    note: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_gaia_cone_adql(params: GaiaConeQueryParams) -> str:
    ruwe_cond = (
        f" AND (ruwe IS NULL OR ruwe < {params.ruwe_max})"
        if params.ruwe_max is not None
        else ""
    )
    g_cond = f" AND phot_g_mean_mag < {params.gmax}" if params.gmax is not None else ""
    extra_cond = ""
    if params.enforce_extragal:
        extra_cond = (
            " AND ( "
            " (parallax IS NOT NULL AND parallax_error IS NOT NULL AND ABS(parallax) < 2*parallax_error) "
            " OR (parallax IS NOT NULL AND parallax < 0.2) "
            " OR (parallax IS NULL) "
            ") "
        )

    limit_clause = f"\nLIMIT {int(params.max_rows)}" if params.max_rows else ""
    return f"""
SELECT
    source_id, ra, dec, phot_g_mean_mag, phot_bp_mean_mag, phot_rp_mean_mag,
    bp_rp, parallax, parallax_error, pmra, pmdec, ruwe
FROM {gaia_source_table_name()}
WHERE 1=1
  AND CONTAINS(
        POINT('ICRS', ra, dec),
        CIRCLE('ICRS', {params.ra_deg}, {params.dec_deg}, {params.radius_deg})
      ) = 1
  {g_cond}
  {ruwe_cond}
  {extra_cond}
{limit_clause}
""".strip()


def query_gaia_cone_sources(params: GaiaConeQueryParams) -> tuple[list[dict[str, Any]], GaiaQueryMeta]:
    """
    API definitiva del modulo per interrogare Gaia (singolo cono).

    Per ora NON interroga Gaia reale: genera dati sintetici deterministici.
    Quando abiliteremo Gaia reale, il cambio dovrà avvenire solo in questo file.
    """
    if (params.provider_mode or "mock").lower() == "real":
        return _query_gaia_cone_sources_real(params)

    sources = _generate_mock_gaia_cone_sources(params)
    meta = GaiaQueryMeta(
        provider_mode="mock",
        table_name=gaia_source_table_name(),
        adql=build_gaia_cone_adql(params),
        jobid=None,
        job_url=None,
        note="Mock provider attivo (nessuna chiamata reale a Gaia)",
    )
    return sources, meta


def _query_gaia_cone_sources_real(
    params: GaiaConeQueryParams,
) -> tuple[list[dict[str, Any]], GaiaQueryMeta]:
    """
    Provider reale Gaia TAP (astroquery).

    Tutta l'integrazione Gaia è centralizzata qui:
    - import lazy di astroquery
    - submit job async
    - retry
    - fallback sync opzionale
    - parsing uniforme del risultato
    """
    adql = build_gaia_cone_adql(params)
    Gaia = _import_astroquery_gaia()

    last_exc: Exception | None = None
    for attempt in range(1, max(1, int(params.tries)) + 1):
        try:
            job = Gaia.launch_job_async(adql, dump_to_file=False)
            rows = job.get_results()
            return _normalize_gaia_results(rows), GaiaQueryMeta(
                provider_mode="real",
                table_name=gaia_source_table_name(),
                adql=adql,
                jobid=_safe_getattr(job, "jobid"),
                job_url=_safe_getattr(job, "remote_location"),
                note=f"Gaia TAP async OK (attempt {attempt})",
            )
        except Exception as exc:
            last_exc = exc
            if attempt < max(1, int(params.tries)):
                time.sleep(max(0.0, float(params.sleep_s)))

    if params.use_sync_fallback:
        try:
            job = Gaia.launch_job(adql, dump_to_file=False)
            rows = job.get_results()
            return _normalize_gaia_results(rows), GaiaQueryMeta(
                provider_mode="real",
                table_name=gaia_source_table_name(),
                adql=adql,
                jobid=_safe_getattr(job, "jobid"),
                job_url=_safe_getattr(job, "remote_location"),
                note="Gaia TAP sync fallback OK",
            )
        except Exception as exc:
            last_exc = exc

    detail = str(last_exc) if last_exc else "Errore Gaia sconosciuto"
    raise RuntimeError(f"Query Gaia fallita dopo retry/fallback: {detail}")


def _import_astroquery_gaia():
    try:
        from astroquery.gaia import Gaia  # type: ignore
    except Exception as exc:  # pragma: no cover - dipende dall'ambiente locale
        raise RuntimeError(
            "astroquery.gaia non disponibile nell'ambiente corrente"
        ) from exc
    return Gaia


def gaia_source_table_name() -> str:
    # Punto unico: se in futuro vogliamo cambiare release/tabella, si cambia qui.
    return "gaiadr3.gaia_source"


def _normalize_gaia_results(rows: Any) -> list[dict[str, Any]]:
    """
    Converte l'output astroquery/astropy (Table) nel contratto usato dal modulo.
    """
    if rows is None:
        return []

    records: list[dict[str, Any]] = []
    for row in rows:
        rec = {
            "source_id": _to_text(_row_get(row, "source_id")),
            "ra": _to_float(_row_get(row, "ra")),
            "dec": _to_float(_row_get(row, "dec")),
            "phot_g_mean_mag": _to_float(_row_get(row, "phot_g_mean_mag")),
            "phot_bp_mean_mag": _to_float(_row_get(row, "phot_bp_mean_mag")),
            "phot_rp_mean_mag": _to_float(_row_get(row, "phot_rp_mean_mag")),
            "bp_rp": _to_float(_row_get(row, "bp_rp")),
            "parallax": _to_float(_row_get(row, "parallax")),
            "parallax_error": _to_float(_row_get(row, "parallax_error")),
            "pmra": _to_float(_row_get(row, "pmra")),
            "pmdec": _to_float(_row_get(row, "pmdec")),
            "ruwe": _to_float(_row_get(row, "ruwe")),
        }
        records.append(rec)
    return records


def _row_get(row: Any, key: str) -> Any:
    try:
        return row[key]
    except Exception:
        return None


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    # astropy masked values espongono `.mask`
    try:
        if getattr(value, "mask", False):
            return None
    except Exception:
        pass
    try:
        v = float(value)
    except Exception:
        return None
    if math.isnan(v) or math.isinf(v):
        return None
    return v


def _to_text(value: Any) -> str | None:
    if value is None:
        return None
    try:
        if getattr(value, "mask", False):
            return None
    except Exception:
        pass
    try:
        # source_id va mantenuto senza notazione scientifica
        if isinstance(value, float):
            return str(int(value))
        return str(value)
    except Exception:
        return None


def _safe_getattr(obj: Any, attr: str) -> str | None:
    try:
        value = getattr(obj, attr, None)
        if value is None:
            return None
        return str(value)
    except Exception:
        return None


def _generate_mock_gaia_cone_sources(params: GaiaConeQueryParams) -> list[dict[str, Any]]:
    seed_key = (
        f"{params.ra_deg:.6f}|{params.dec_deg:.6f}|{params.radius_deg:.6f}|"
        f"{params.gmax}|{params.ruwe_max}|{params.enforce_extragal}|{params.max_rows}"
    )
    seed = int(hashlib.sha256(seed_key.encode("utf-8")).hexdigest()[:16], 16)
    rng = random.Random(seed)

    area_deg2 = math.pi * max(params.radius_deg, 1e-6) ** 2
    base_count = max(80, int(900 * area_deg2))
    cluster_bonus = rng.randint(20, 90)
    n_sources = base_count + cluster_bonus
    if params.max_rows is not None:
        n_sources = min(n_sources, int(params.max_rows))

    # Centro di una finta overdensità leggermente spostato dal centro del cono.
    cluster_ra = params.ra_deg + rng.uniform(-0.12, 0.12) * params.radius_deg
    cluster_dec = params.dec_deg + rng.uniform(-0.12, 0.12) * params.radius_deg

    records: list[dict[str, Any]] = []
    for idx in range(n_sources):
        in_cluster = idx < int(n_sources * 0.22)
        if in_cluster:
            # Piccola nube concentrata.
            ra, dec = _sample_disc(
                rng,
                cluster_ra,
                cluster_dec,
                max(params.radius_deg * 0.18, 1e-4),
            )
        else:
            ra, dec = _sample_disc(rng, params.ra_deg, params.dec_deg, params.radius_deg)

        g_mag = rng.uniform(15.8, min(21.8, params.gmax + 0.6))
        bp_rp = rng.uniform(-0.1, 2.6)
        rp_mag = g_mag - rng.uniform(-0.4, 0.8)
        bp_mag = rp_mag + bp_rp
        parallax_err = rng.uniform(0.03, 0.25)
        parallax = rng.uniform(-0.12, 0.18) if params.enforce_extragal else rng.uniform(-1.0, 2.5)
        ruwe = rng.uniform(0.7, 1.8)
        if params.ruwe_max is not None and ruwe > params.ruwe_max + 0.2:
            ruwe = params.ruwe_max - rng.uniform(0.0, 0.1)

        records.append(
            {
                "source_id": str(10_000_000_000_000_000 + idx + (seed % 1_000_000)),
                "ra": ra,
                "dec": dec,
                "phot_g_mean_mag": g_mag,
                "phot_bp_mean_mag": bp_mag,
                "phot_rp_mean_mag": rp_mag,
                "bp_rp": bp_rp,
                "parallax": parallax,
                "parallax_error": parallax_err,
                "pmra": rng.uniform(-1.2, 1.2),
                "pmdec": rng.uniform(-1.2, 1.2),
                "ruwe": ruwe,
            }
        )

    if params.gmax is not None:
        records = [r for r in records if r["phot_g_mean_mag"] < params.gmax]
    if params.ruwe_max is not None:
        records = [r for r in records if (r["ruwe"] is None or r["ruwe"] < params.ruwe_max)]

    return records


def _sample_disc(rng: random.Random, ra0: float, dec0: float, radius_deg: float) -> tuple[float, float]:
    # Campionamento uniforme in area per piccoli campi.
    rr = radius_deg * math.sqrt(rng.random())
    ang = rng.uniform(0.0, 2.0 * math.pi)
    dra = rr * math.cos(ang) / max(math.cos(math.radians(dec0)), 1e-6)
    ddec = rr * math.sin(ang)
    return ra0 + dra, dec0 + ddec
