from __future__ import annotations

import base64
import glob
import os
import struct
from typing import Any
import zlib

import numpy as np
from astropy.coordinates import AltAz, EarthLocation, SkyCoord
from astropy.io import fits
from astropy.time import Time
from astropy.wcs import WCS
import astropy.units as u
from photutils.aperture import CircularAnnulus, CircularAperture, aperture_photometry
from photutils.centroids import centroid_com
from scipy.ndimage import maximum_filter

from .schemas import ObservatoryConfig, PhotometryConfig, Point, TargetCoordinates

_REFERENCE_FRAME_CACHE: dict[str, dict[str, Any]] = {}


def robust_median(values: np.ndarray) -> float:
    array = np.asarray(values, dtype=float)
    array = array[np.isfinite(array)]
    return float(np.median(array)) if len(array) else float("nan")


def get_time_midexp(header: fits.Header) -> Time:
    date_obs = header.get("DATE-OBS")
    exptime = header.get("EXPTIME", header.get("EXPOSURE"))
    if date_obs is None or exptime is None:
        raise ValueError("DATE-OBS o EXPTIME mancanti")
    start = Time(date_obs, format="isot", scale="utc")
    return start + (float(exptime) / 2.0) * u.s


def find_fits_files(folder: str) -> list[str]:
    patterns = [
        "*.fits",
        "*.fit",
        "*.fts",
        "*.fits.gz",
        "*.fit.gz",
        "*.fts.gz",
        "*.fits.fz",
        "*.fit.fz",
        "*.fts.fz",
    ]
    files: list[str] = []
    for pattern in patterns:
        files.extend(glob.glob(os.path.join(folder, pattern)))
        files.extend(glob.glob(os.path.join(folder, "**", pattern), recursive=True))
    return sorted(set(files))


def load_reference_frame(folder: str) -> dict[str, Any]:
    cached = _REFERENCE_FRAME_CACHE.get(folder)
    if cached is not None:
        return cached

    fits_files = find_fits_files(folder)
    if not fits_files:
        raise FileNotFoundError("Nessun FITS trovato nella cartella indicata")

    with fits.open(fits_files[0]) as hdul:
        data = hdul[0].data.astype(float)
        header = hdul[0].header
        wcs = WCS(header)

    vmin, vmax = np.nanpercentile(data, [5, 99])
    reference = {
        "folder": folder,
        "fits_files": fits_files,
        "frame_path": fits_files[0],
        "data": data,
        "header": header,
        "wcs": wcs,
        "width": int(data.shape[1]),
        "height": int(data.shape[0]),
        "preview_png_base64": render_preview(data, vmin, vmax),
    }
    _REFERENCE_FRAME_CACHE[folder] = reference
    return reference


def reference_frame_metadata(
    folder: str,
    target_coordinates: TargetCoordinates | None = None,
) -> dict[str, Any]:
    reference = load_reference_frame(folder)
    auto_target = None
    overlay = build_preview_overlay(reference["wcs"], reference["width"], reference["height"])
    if target_coordinates and target_coordinates.ra and target_coordinates.dec:
        auto_target = find_target_pixel(reference["wcs"], target_coordinates, reference["width"], reference["height"])
    return {
        "folder": folder,
        "frame_path": reference["frame_path"],
        "fits_count": len(reference["fits_files"]),
        "width": reference["width"],
        "height": reference["height"],
        "preview_png_base64": reference["preview_png_base64"],
        "auto_target": auto_target,
        "overlay": overlay,
    }


def render_preview(data: np.ndarray, vmin: float, vmax: float) -> str:
    clipped = np.clip(data, vmin, vmax)
    normalized = (clipped - vmin) / max(vmax - vmin, 1e-9)
    normalized = np.flipud(normalized)
    image_array = np.asarray(normalized * 255.0, dtype=np.uint8)
    png_bytes = encode_grayscale_png(image_array)
    return base64.b64encode(png_bytes).decode("ascii")


def encode_grayscale_png(image_array: np.ndarray) -> bytes:
    height, width = image_array.shape
    raw_rows = b"".join(b"\x00" + image_array[row].tobytes() for row in range(height))
    compressed = zlib.compress(raw_rows, level=9)

    def chunk(chunk_type: bytes, payload: bytes) -> bytes:
        crc = zlib.crc32(chunk_type + payload) & 0xFFFFFFFF
        return (
            struct.pack("!I", len(payload))
            + chunk_type
            + payload
            + struct.pack("!I", crc)
        )

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack("!IIBBBBB", width, height, 8, 0, 0, 0, 0)
    return signature + chunk(b"IHDR", ihdr) + chunk(b"IDAT", compressed) + chunk(b"IEND", b"")


def is_star_like(
    data: np.ndarray,
    x: float,
    y: float,
    *,
    radius: int,
    sigma_threshold: float,
) -> bool:
    ny, nx = data.shape
    xi = int(round(x))
    yi = int(round(y))
    if xi < 0 or yi < 0 or xi >= nx or yi >= ny:
        return False
    x1 = max(0, xi - radius)
    x2 = min(nx, xi + radius + 1)
    y1 = max(0, yi - radius)
    y2 = min(ny, yi + radius + 1)
    stamp = data[y1:y2, x1:x2].astype(float)
    median = np.nanmedian(stamp)
    p95 = np.nanpercentile(stamp, 95)
    sigma = np.nanstd(stamp)
    if not np.isfinite(sigma) or sigma <= 0:
        return False
    return bool((p95 - median) > sigma_threshold * sigma)


def evaluate_point_quality(
    data: np.ndarray,
    point: Point,
    config: PhotometryConfig,
    wcs: WCS,
) -> dict[str, Any]:
    ny, nx = data.shape
    xi = int(round(point.x))
    yi = int(round(point.y))
    if xi < 0 or yi < 0 or xi >= nx or yi >= ny:
        return {
            "x": point.x,
            "y": point.y,
            "status": "out_of_bounds",
            "star_like": False,
            "score": 0.0,
            "peak_minus_median": 0.0,
            "sigma": 0.0,
            "sky": None,
        }

    radius = config.starlike_check_r
    x1 = max(0, xi - radius)
    x2 = min(nx, xi + radius + 1)
    y1 = max(0, yi - radius)
    y2 = min(ny, yi + radius + 1)
    stamp = data[y1:y2, x1:x2].astype(float)
    median = float(np.nanmedian(stamp))
    peak = float(np.nanmax(stamp))
    p95 = float(np.nanpercentile(stamp, 95))
    sigma = float(np.nanstd(stamp))
    score = 0.0 if not np.isfinite(sigma) or sigma <= 0 else float((p95 - median) / sigma)
    star_like = bool(score > config.starlike_sigma)
    refined_x, refined_y = refine_target_centroid(data, point, config)
    sky = pixel_to_sky_details(wcs, point.x, point.y)
    return {
        "x": point.x,
        "y": point.y,
        "refined_x": refined_x,
        "refined_y": refined_y,
        "distance_to_refined": float(np.hypot(refined_x - point.x, refined_y - point.y)),
        "status": quality_status(score, star_like),
        "star_like": star_like,
        "score": score,
        "peak_minus_median": peak - median,
        "sigma": sigma,
        "sky": sky,
    }


def quality_status(score: float, star_like: bool) -> str:
    if not np.isfinite(score) or score <= 0:
        return "bad"
    if star_like:
        return "good"
    if score >= 0.6 * 5.0:
        return "weak"
    return "bad"


def evaluate_selection(
    folder: str,
    target: Point | None,
    comparators: list[Point],
    config: PhotometryConfig,
    target_coordinates: TargetCoordinates | None = None,
) -> dict[str, Any]:
    reference = load_reference_frame(folder)
    data = reference["data"]
    wcs = reference["wcs"]
    auto_target = None
    if target_coordinates and target_coordinates.ra and target_coordinates.dec:
        auto_target = find_target_pixel(wcs, target_coordinates, reference["width"], reference["height"])

    target_result = evaluate_point_quality(data, target, config, wcs) if target else None
    comparator_results = [evaluate_point_quality(data, point, config, wcs) for point in comparators]
    return {
        "auto_target": auto_target,
        "target": target_result,
        "comparators": comparator_results,
    }


def snap_point_to_star(
    folder: str,
    point: Point,
    config: PhotometryConfig,
) -> dict[str, Any]:
    reference = load_reference_frame(folder)
    data = reference["data"]
    wcs = reference["wcs"]
    snapped = refine_to_local_star(data, point, config)
    quality = evaluate_point_quality(data, snapped, config, wcs)
    quality["original_x"] = point.x
    quality["original_y"] = point.y
    return quality


def estimate_fwhm_moments(data: np.ndarray, x: float, y: float, radius: int) -> float:
    ny, nx = data.shape
    x0 = int(round(x))
    y0 = int(round(y))
    x1 = max(0, x0 - radius)
    x2 = min(nx, x0 + radius + 1)
    y1 = max(0, y0 - radius)
    y2 = min(ny, y0 + radius + 1)
    stamp = data[y1:y2, x1:x2].astype(float)
    if stamp.size < 25:
        return float("nan")
    stamp = stamp - np.nanmedian(stamp)
    stamp[stamp < 0] = 0
    total = np.nansum(stamp)
    if total <= 0:
        return float("nan")
    yy, xx = np.indices(stamp.shape)
    xbar = np.nansum(xx * stamp) / total
    ybar = np.nansum(yy * stamp) / total
    varx = np.nansum((xx - xbar) ** 2 * stamp) / total
    vary = np.nansum((yy - ybar) ** 2 * stamp) / total
    return float(2.355 * np.sqrt(0.5 * (varx + vary)))


def compute_airmass(
    times: Time,
    ra_deg: float,
    dec_deg: float,
    observatory: ObservatoryConfig,
) -> tuple[np.ndarray, np.ndarray]:
    location = EarthLocation(
        lat=observatory.lat_deg * u.deg,
        lon=observatory.lon_deg * u.deg,
        height=observatory.elev_m * u.m,
    )
    altaz = AltAz(obstime=times, location=location)
    target = SkyCoord(ra=ra_deg * u.deg, dec=dec_deg * u.deg)
    transformed = target.transform_to(altaz)
    return transformed.secz.value, transformed.alt.deg


def refine_target_centroid(
    data: np.ndarray,
    point: Point,
    config: PhotometryConfig,
) -> tuple[float, float]:
    x0i = int(round(point.x))
    y0i = int(round(point.y))
    ny, nx = data.shape
    radius = config.centroid_stamp_r
    x1 = max(0, x0i - radius)
    x2 = min(nx, x0i + radius + 1)
    y1 = max(0, y0i - radius)
    y2 = min(ny, y0i + radius + 1)
    stamp = data[y1:y2, x1:x2]
    cy_s, cx_s = centroid_com(stamp)
    return float(x1 + cx_s), float(y1 + cy_s)


def refine_to_local_star(
    data: np.ndarray,
    point: Point,
    config: PhotometryConfig,
) -> Point:
    ny, nx = data.shape
    search_radius = max(config.centroid_stamp_r * 2, config.starlike_check_r + 2)
    x0 = int(round(point.x))
    y0 = int(round(point.y))
    x1 = max(0, x0 - search_radius)
    x2 = min(nx, x0 + search_radius + 1)
    y1 = max(0, y0 - search_radius)
    y2 = min(ny, y0 + search_radius + 1)
    stamp = data[y1:y2, x1:x2].astype(float)
    if stamp.size == 0 or np.all(~np.isfinite(stamp)):
        return point

    finite_stamp = np.array(stamp, copy=True)
    median = float(np.nanmedian(finite_stamp))
    sigma = float(np.nanstd(finite_stamp))
    finite_stamp[~np.isfinite(finite_stamp)] = median

    filtered = maximum_filter(finite_stamp, size=3, mode="nearest")
    local_maxima = (finite_stamp == filtered) & (finite_stamp > median + max(2.0 * sigma, 1.0))
    candidate_indices = np.argwhere(local_maxima)

    if len(candidate_indices) == 0:
        peak_index = np.unravel_index(np.argmax(finite_stamp), finite_stamp.shape)
    else:
        click_x_local = point.x - x1
        click_y_local = point.y - y1

        def candidate_rank(index_pair: np.ndarray) -> tuple[float, float]:
            dy = float(index_pair[0] - click_y_local)
            dx = float(index_pair[1] - click_x_local)
            distance = np.hypot(dx, dy)
            brightness = float(finite_stamp[index_pair[0], index_pair[1]])
            return (distance, -brightness)

        peak_index = tuple(min(candidate_indices, key=candidate_rank))

    peak_y = y1 + peak_index[0]
    peak_x = x1 + peak_index[1]
    refined_x, refined_y = refine_target_centroid(data, Point(float(peak_x), float(peak_y)), config)
    return Point(refined_x, refined_y)


def run_lightcurve(
    folder: str,
    target: Point,
    comparators: list[Point],
    config: PhotometryConfig,
    target_coordinates: TargetCoordinates | None = None,
    observatory: ObservatoryConfig | None = None,
) -> dict[str, Any]:
    if len(comparators) < 1:
        raise ValueError("Servono almeno 1 target e 1 comparatore")

    observatory = observatory or ObservatoryConfig()
    reference = load_reference_frame(folder)
    data0 = reference["data"]
    wcs = reference["wcs"]
    warnings: list[str] = []

    valid_comparators = [
        point
        for point in comparators
        if is_star_like(
            data0,
            point.x,
            point.y,
            radius=config.starlike_check_r,
            sigma_threshold=config.starlike_sigma,
        )
    ]
    if not is_star_like(
        data0,
        target.x,
        target.y,
        radius=config.starlike_check_r,
        sigma_threshold=config.starlike_sigma,
    ):
        warnings.append("Il target non supera il filtro stellare sul frame di riferimento.")
    if not valid_comparators:
        warnings.append("Nessun comparatore supera il filtro stellare: uso i comparatori grezzi.")
        valid_comparators = comparators

    ra_deg, dec_deg, coordinate_source = resolve_target_coordinates(wcs, target, target_coordinates)

    times: list[Time] = []
    flux_target: list[float] = []
    flux_comps: list[np.ndarray] = []
    background_target: list[float] = []
    fwhm_target: list[float] = []
    xcen_target: list[float] = []
    ycen_target: list[float] = []

    for frame_path in reference["fits_files"]:
        with fits.open(frame_path) as hdul:
            data = hdul[0].data.astype(float)
            header = hdul[0].header

        times.append(get_time_midexp(header))

        cx, cy = refine_target_centroid(data, target, config)
        xcen_target.append(cx)
        ycen_target.append(cy)

        positions = [(cx, cy)] + [(point.x, point.y) for point in valid_comparators]
        apertures = CircularAperture(positions, r=config.aperture_radius)
        annuli = CircularAnnulus(positions, r_in=config.annulus_r_in, r_out=config.annulus_r_out)

        phot_ap = aperture_photometry(data, apertures)
        phot_an = aperture_photometry(data, annuli)

        bkg = np.asarray(phot_an["aperture_sum"] / annuli.area, dtype=float)
        net = np.asarray(phot_ap["aperture_sum"] - bkg * apertures.area, dtype=float)

        flux_target.append(float(net[0]))
        flux_comps.append(net[1:])
        background_target.append(float(bkg[0]))
        fwhm_target.append(estimate_fwhm_moments(data, cx, cy, config.fwhm_stamp_r))

    times_astropy = Time(times)
    time_jd = np.asarray(times_astropy.jd, dtype=float)
    flux_target_arr = np.asarray(flux_target, dtype=float)
    flux_comps_arr = np.asarray(flux_comps, dtype=float)
    comp_sum = np.nansum(flux_comps_arr, axis=1)
    raw_ratio = flux_target_arr / comp_sum
    normalized_flux = raw_ratio / robust_median(raw_ratio)
    airmass, altitude = compute_airmass(times_astropy, ra_deg, dec_deg, observatory)
    detrended_flux = apply_detrend(
        normalized_flux,
        airmass=airmass,
        fwhm=np.asarray(fwhm_target, dtype=float),
        background=np.asarray(background_target, dtype=float),
        xcen=np.asarray(xcen_target, dtype=float),
        ycen=np.asarray(ycen_target, dtype=float),
        time_jd=time_jd,
        detrend_mode=config.detrend_mode,
    )

    return {
        "reference_frame": {
            "folder": folder,
            "frame_path": reference["frame_path"],
            "fits_count": len(reference["fits_files"]),
            "width": reference["width"],
            "height": reference["height"],
            "target_ra_deg": ra_deg,
            "target_dec_deg": dec_deg,
            "target_coordinate_source": coordinate_source,
        },
        "preview": {
            "png_base64": reference["preview_png_base64"],
            "width": reference["width"],
            "height": reference["height"],
        },
        "selection": {
            "target": {"x": target.x, "y": target.y},
            "comparators": [{"x": point.x, "y": point.y} for point in valid_comparators],
            "raw_comparators_count": len(comparators),
            "effective_comparators_count": len(valid_comparators),
        },
        "warnings": warnings,
        "series": {
            "jd": time_jd.tolist(),
            "flux_target": flux_target_arr.tolist(),
            "comparison_sum": comp_sum.tolist(),
            "flux_normalized": normalized_flux.tolist(),
            "flux_detrended": detrended_flux.tolist(),
            "airmass": np.asarray(airmass, dtype=float).tolist(),
            "altitude_deg": np.asarray(altitude, dtype=float).tolist(),
            "background_target": np.asarray(background_target, dtype=float).tolist(),
            "fwhm_target": np.asarray(fwhm_target, dtype=float).tolist(),
            "xcen_target": np.asarray(xcen_target, dtype=float).tolist(),
            "ycen_target": np.asarray(ycen_target, dtype=float).tolist(),
        },
    }


def resolve_target_coordinates(
    wcs: WCS,
    target: Point,
    target_coordinates: TargetCoordinates | None,
) -> tuple[float, float, str]:
    if target_coordinates and target_coordinates.ra and target_coordinates.dec:
        sky = SkyCoord(target_coordinates.ra, target_coordinates.dec, unit=(u.hourangle, u.deg))
        return float(sky.ra.deg), float(sky.dec.deg), "input"

    sky = wcs.pixel_to_world(target.x, target.y)
    return float(sky.ra.deg), float(sky.dec.deg), "wcs_from_pixel"


def find_target_pixel(
    wcs: WCS,
    target_coordinates: TargetCoordinates,
    width: int,
    height: int,
) -> dict[str, Any] | None:
    sky = SkyCoord(target_coordinates.ra, target_coordinates.dec, unit=(u.hourangle, u.deg))
    pixel_x, pixel_y = wcs.world_to_pixel(sky)
    pixel = {
        "x": float(pixel_x),
        "y": float(pixel_y),
        "in_bounds": bool(0 <= pixel_x < width and 0 <= pixel_y < height),
    }
    return pixel


def pixel_to_sky_details(wcs: WCS, x: float, y: float) -> dict[str, Any] | None:
    try:
        sky = wcs.pixel_to_world(x, y)
    except Exception:
        return None
    return {
        "ra_deg": float(sky.ra.deg),
        "dec_deg": float(sky.dec.deg),
        "ra_hms": sky.ra.to_string(unit=u.hourangle, sep=":", precision=2, pad=True),
        "dec_dms": sky.dec.to_string(unit=u.deg, sep=":", precision=2, alwayssign=True, pad=True),
    }


def build_preview_overlay(wcs: WCS, width: int, height: int) -> dict[str, Any]:
    center_x = (width - 1) / 2.0
    center_y = (height - 1) / 2.0
    center_sky = pixel_to_sky_details(wcs, center_x, center_y)
    return {
        "center": {
            "x": center_x,
            "y": center_y,
            "sky": center_sky,
        },
        "grid": approximate_grid_lines(wcs, width, height),
    }


def approximate_grid_lines(wcs: WCS, width: int, height: int) -> list[dict[str, Any]]:
    corners = [
        pixel_to_sky_details(wcs, 0, 0),
        pixel_to_sky_details(wcs, width - 1, 0),
        pixel_to_sky_details(wcs, 0, height - 1),
        pixel_to_sky_details(wcs, width - 1, height - 1),
    ]
    valid_corners = [corner for corner in corners if corner is not None]
    if len(valid_corners) < 4:
        return []

    ra_values = [corner["ra_deg"] for corner in valid_corners]
    dec_values = [corner["dec_deg"] for corner in valid_corners]
    ra_min, ra_max = min(ra_values), max(ra_values)
    dec_min, dec_max = min(dec_values), max(dec_values)
    if ra_max - ra_min <= 0 or dec_max - dec_min <= 0:
        return []

    lines: list[dict[str, Any]] = []
    for ra in np.linspace(ra_min, ra_max, 5):
        points = sample_constant_ra_line(wcs, ra, dec_min, dec_max, width, height)
        if len(points) >= 2:
            label = SkyCoord(ra=ra * u.deg, dec=np.mean([dec_min, dec_max]) * u.deg).ra.to_string(
                unit=u.hourangle,
                sep=":",
                precision=1,
                pad=True,
            )
            lines.append({"kind": "ra", "label": f"RA {label}", "points": points})
    for dec in np.linspace(dec_min, dec_max, 5):
        points = sample_constant_dec_line(wcs, dec, ra_min, ra_max, width, height)
        if len(points) >= 2:
            label = SkyCoord(ra=np.mean([ra_min, ra_max]) * u.deg, dec=dec * u.deg).dec.to_string(
                unit=u.deg,
                sep=":",
                precision=0,
                alwayssign=True,
                pad=True,
            )
            lines.append({"kind": "dec", "label": f"Dec {label}", "points": points})
    return lines


def sample_constant_ra_line(
    wcs: WCS,
    ra_deg: float,
    dec_min: float,
    dec_max: float,
    width: int,
    height: int,
) -> list[dict[str, float]]:
    points: list[dict[str, float]] = []
    for dec in np.linspace(dec_min, dec_max, 20):
        sky = SkyCoord(ra=ra_deg * u.deg, dec=dec * u.deg)
        try:
            x, y = wcs.world_to_pixel(sky)
        except Exception:
            continue
        if 0 <= x < width and 0 <= y < height:
            points.append({"x": float(x), "y": float(y)})
    return points


def sample_constant_dec_line(
    wcs: WCS,
    dec_deg: float,
    ra_min: float,
    ra_max: float,
    width: int,
    height: int,
) -> list[dict[str, float]]:
    points: list[dict[str, float]] = []
    for ra in np.linspace(ra_min, ra_max, 20):
        sky = SkyCoord(ra=ra * u.deg, dec=dec_deg * u.deg)
        try:
            x, y = wcs.world_to_pixel(sky)
        except Exception:
            continue
        if 0 <= x < width and 0 <= y < height:
            points.append({"x": float(x), "y": float(y)})
    return points


def apply_detrend(
    normalized_flux: np.ndarray,
    *,
    airmass: np.ndarray,
    fwhm: np.ndarray,
    background: np.ndarray,
    xcen: np.ndarray,
    ycen: np.ndarray,
    time_jd: np.ndarray,
    detrend_mode: str,
) -> np.ndarray:
    detrended = normalized_flux.copy()
    if detrend_mode == "none":
        return detrended

    columns = [np.ones_like(normalized_flux)]
    if detrend_mode in ("airmass", "full"):
        columns.append(airmass)
    if detrend_mode == "full":
        columns.extend([fwhm, background, xcen, ycen, time_jd - time_jd[0]])

    design = np.vstack(columns).T
    mask = np.isfinite(normalized_flux) & (normalized_flux > 0)
    if mask.sum() < design.shape[1]:
        return detrended

    beta, *_ = np.linalg.lstsq(design[mask], np.log(normalized_flux[mask]), rcond=None)
    model = np.exp(design @ beta)
    return normalized_flux / model
