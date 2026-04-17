from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass

from astroquery.gaia import Gaia

logger = logging.getLogger(__name__)

# Keep Gaia requests bounded in time (seconds).
Gaia.TIMEOUT = int(os.getenv("GAIA_TIMEOUT_SECONDS", "20"))
GAIA_RETRIES = int(os.getenv("GAIA_RETRIES", "2"))
GAIA_RETRY_DELAY_SECONDS = float(os.getenv("GAIA_RETRY_DELAY_SECONDS", "1.0"))


class GaiaQueryError(Exception):
    pass


@dataclass
class GaiaTarget:
    source_id: str
    ra: float
    dec: float
    g_mag: float


@dataclass
class GaiaFieldResult:
    stars: list[dict]
    cone_count: int
    truncated: bool


def _parse_source_id(source_id: str) -> int:
    try:
        return int(str(source_id).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError("source_id must be a valid Gaia numeric identifier") from exc


def _launch_job_with_retry(query: str, operation: str):
    attempts = max(1, GAIA_RETRIES + 1)
    last_exc: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            return Gaia.launch_job(query=query)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt < attempts:
                logger.warning(
                    "Gaia %s failed on attempt %s/%s: %s",
                    operation,
                    attempt,
                    attempts,
                    exc,
                )
                time.sleep(GAIA_RETRY_DELAY_SECONDS)

    assert last_exc is not None
    raise GaiaQueryError(f"Gaia {operation} failed after {attempts} attempts: {last_exc}") from last_exc


def get_target_by_source_id(source_id: str) -> GaiaTarget | None:
    sid = _parse_source_id(source_id)
    query = f"""
        SELECT source_id, ra, dec, phot_g_mean_mag
        FROM gaiadr3.gaia_source
        WHERE source_id = {sid}
    """
    try:
        job = _launch_job_with_retry(query=query, operation="target query")
        table = job.get_results()
    except GaiaQueryError:
        raise

    if len(table) == 0:
        return None

    row = table[0]
    return GaiaTarget(
        source_id=str(row["source_id"]),
        ra=float(row["ra"]),
        dec=float(row["dec"]),
        g_mag=float(row["phot_g_mean_mag"]),
    )


def query_field_stars(
    ra_deg: float,
    dec_deg: float,
    cone_radius_arcmin: float,
    g_mag_limit: float,
    max_results: int,
) -> GaiaFieldResult:
    top_n = int(max_results) + 1
    radius_deg = cone_radius_arcmin / 60.0
    query = f"""
        SELECT TOP {top_n}
            source_id, ra, dec, phot_g_mean_mag
        FROM gaiadr3.gaia_source
        WHERE CONTAINS(
            POINT('ICRS', ra, dec),
            CIRCLE('ICRS', {ra_deg}, {dec_deg}, {radius_deg})
        ) = 1
        AND phot_g_mean_mag <= {g_mag_limit}
        ORDER BY phot_g_mean_mag ASC
    """

    try:
        job = _launch_job_with_retry(query=query, operation="field query")
        table = job.get_results()
    except GaiaQueryError:
        raise

    cone_count = len(table)
    truncated = cone_count > max_results
    if truncated:
        table = table[:max_results]

    stars = [
        {
            "source_id": str(row["source_id"]),
            "ra": float(row["ra"]),
            "dec": float(row["dec"]),
            "g_mag": float(row["phot_g_mean_mag"]),
        }
        for row in table
    ]

    return GaiaFieldResult(stars=stars, cone_count=cone_count, truncated=truncated)
