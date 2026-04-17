from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ObservatoryConfig:
    lat_deg: float = 42.296601
    lon_deg: float = 11.87135
    elev_m: float = 0.0


@dataclass(slots=True)
class PhotometryConfig:
    aperture_radius: float = 6.0
    annulus_r_in: float = 10.0
    annulus_r_out: float = 16.0
    centroid_stamp_r: int = 8
    fwhm_stamp_r: int = 8
    starlike_check_r: int = 6
    starlike_sigma: float = 5.0
    detrend_mode: str = "full"

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "PhotometryConfig":
        defaults = cls()
        return cls(
            aperture_radius=float(payload.get("aperture_radius", defaults.aperture_radius)),
            annulus_r_in=float(payload.get("annulus_r_in", defaults.annulus_r_in)),
            annulus_r_out=float(payload.get("annulus_r_out", defaults.annulus_r_out)),
            centroid_stamp_r=int(payload.get("centroid_stamp_r", defaults.centroid_stamp_r)),
            fwhm_stamp_r=int(payload.get("fwhm_stamp_r", defaults.fwhm_stamp_r)),
            starlike_check_r=int(payload.get("starlike_check_r", defaults.starlike_check_r)),
            starlike_sigma=float(payload.get("starlike_sigma", defaults.starlike_sigma)),
            detrend_mode=str(payload.get("detrend_mode", defaults.detrend_mode)),
        )


@dataclass(slots=True)
class Point:
    x: float
    y: float


@dataclass(slots=True)
class TargetCoordinates:
    ra: str | None = None
    dec: str | None = None


@dataclass(slots=True)
class LightcurveResult:
    reference_frame: dict[str, Any]
    selection: dict[str, Any]
    warnings: list[str] = field(default_factory=list)
    series: dict[str, list[float]] = field(default_factory=dict)
