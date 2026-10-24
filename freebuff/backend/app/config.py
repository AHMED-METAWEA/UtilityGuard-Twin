"""Central configuration for UtilityGuard Twin.

Every tunable threshold lives here (or in finance/assumptions.yaml) so the
prototype has no magic numbers inside the algorithms.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, Field

APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
PROJECT_DIR = BACKEND_DIR.parent
DATA_DIR = Path(os.environ.get("UTILITYGUARD_DATA_DIR", PROJECT_DIR / "data"))
DB_PATH = DATA_DIR / "utilityguard.db"
FRONTEND_DIR = PROJECT_DIR / "frontend"

NETWORK_VERSION = "ugtwin-v1"
DETECTOR_VERSION = "rules-v1"
SIM_ENGINE = "WNTR 1.5.0 (Python)"
DEFAULT_SEED = 42
SIM_START = "2026-01-01T00:00:00"
DEFAULT_HORIZON_HOURS = 48
DEFAULT_TIMESTEP_MINUTES = 5
DEFAULT_SPEED = 3600.0  # simulated seconds per real second (1 simulated hour / s)
MAX_SPEED = 86400.0
MIN_SPEED = 1.0

# ---------------------------------------------------------------------------
# Network geometry / hydraulics (hypothetical, not a real city)
# ---------------------------------------------------------------------------
GRID_COLS = 6
GRID_ROWS = 6
SENSOR_IDS = (
    "P01", "P02", "P03", "P04", "P05", "P06", "P07", "P08",
    "F01", "F02", "F03", "T01",
)

# Gaussian measurement noise (1 sigma) used by the simulated sensor layer.
SENSOR_NOISE: dict[str, float] = {
    "P01": 0.12, "P02": 0.12, "P03": 0.12, "P04": 0.12,
    "P05": 0.12, "P06": 0.12, "P07": 0.12, "P08": 0.12,
    "F01": 0.8, "F02": 0.8, "F03": 0.6,   # L/s
    "T01": 0.01,                           # m
}

# Rate-of-change limits per tick for the quality layer (5-min ticks).
QUALITY_RATE_LIMITS: dict[str, float] = {
    "pressure": 3.0,   # m per tick
    "flow": 12.0,      # L/s per tick
    "level": 0.15,     # m per tick
}
QUALITY_RANGES: dict[str, tuple[float, float]] = {
    "pressure": (-2.0, 120.0),
    "flow": (-10.0, 500.0),
    "level": (0.0, 20.0),
}


class QualityConfig(BaseModel):
    """Data-quality thresholds; all defaults are stated in the README/docs."""

    stuck_window: int = Field(default=6, description="ticks of near-zero variance => stuck")
    stuck_epsilon_pressure: float = 0.01
    stuck_epsilon_flow: float = 0.05
    stuck_epsilon_level: float = 0.002
    rate_limit_pressure: float = QUALITY_RATE_LIMITS["pressure"]
    rate_limit_flow: float = QUALITY_RATE_LIMITS["flow"]
    rate_limit_level: float = QUALITY_RATE_LIMITS["level"]
    drift_neighbor_sigma: float = 3.5
    drift_min_sigma: float = 2.0
    drift_baseline_sigma: float = 3.0
    mass_balance_window_ticks: int = 6
    mass_balance_floor_m: float = 0.04
    mass_balance_rel_tolerance: float = 0.35
    score_suspect_below: float = 0.8
    score_bad_below: float = 0.45
    min_good_fraction_for_confidence: float = 0.6
    late_after_ticks: int = 1


class DetectorConfig(BaseModel):
    """Rule-based detector thresholds. Residuals are in sensor-noise sigmas."""

    watch_threshold: float = 2.5
    alert_threshold: float = 4.0
    persistence_ticks: int = 3
    cusum_drift: float = 0.75
    cusum_threshold: float = 15.0
    cluster_distance_m: float = 220.0
    leak_min_sensors: int = 2
    network_confidence_bad_fraction: float = 0.35
    group_window_ticks: int = 12
    group_distance_m: float = 320.0


class PlaybackConfig(BaseModel):
    default_speed: float = DEFAULT_SPEED
    min_speed: float = MIN_SPEED
    max_speed: float = MAX_SPEED


class Settings(BaseModel):
    network_version: str = NETWORK_VERSION
    detector_version: str = DETECTOR_VERSION
    sim_start: str = SIM_START
    default_horizon_hours: int = DEFAULT_HORIZON_HOURS
    default_timestep_minutes: int = DEFAULT_TIMESTEP_MINUTES
    quality: QualityConfig = Field(default_factory=QualityConfig)
    detector: DetectorConfig = Field(default_factory=DetectorConfig)
    playback: PlaybackConfig = Field(default_factory=PlaybackConfig)
    db_path: str = str(DB_PATH)
    cors_origins: list[str] = field(default_factory=lambda: [
        "http://127.0.0.1:5173", "http://localhost:5173",
        "http://127.0.0.1:4173", "http://localhost:4173",
    ])


SETTINGS = Settings()
