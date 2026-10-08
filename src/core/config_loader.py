# Parses and validates external .toml settings files
import tomllib
from pathlib import Path

from .dataclasses import (
    TrackEnvironment,
    TrackUncertainties,
    VehicleProfile,
    VehicleUncertainties,
)

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"
VEHICLE_FILE = CONFIG_DIR / "vehicle_profiles.toml"
TRACK_FILE = CONFIG_DIR / "track_environments.toml"

_RESERVED_KEYS = {"meta", "uncertainties"}
_PLACEHOLDER_PREFIXES = ("ENTER_",)
_PLACEHOLDER_NAMES = {"NOT_SET"}


class ConfigError(Exception):
    """Raised when a configuration file is missing or malformed."""


def _read_toml(path: Path) -> dict:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except FileNotFoundError as exc:
        raise ConfigError(f"Missing configuration file: {path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Invalid TOML in {path}: {exc}") from exc


def _section_keys(data: dict) -> list[str]:
    return [
        key
        for key, value in data.items()
        if key not in _RESERVED_KEYS and isinstance(value, dict)
    ]


def _is_placeholder(key: str, name: str) -> bool:
    return name in _PLACEHOLDER_NAMES or key.startswith(_PLACEHOLDER_PREFIXES)


def load_vehicle_profiles(path: Path | None = None) -> tuple[dict[str, VehicleProfile], str]:
    data = _read_toml(path or VEHICLE_FILE)
    shared = data.get("uncertainties", {})
    uncertainties = VehicleUncertainties(
        mass_std_dev_grams=float(shared.get("mass_std_dev_grams", 0.0)),
        cd_std_dev=float(shared.get("cd_std_dev", 0.0)),
        cl_std_dev=float(shared.get("cl_std_dev", 0.0)),
        bearing_mu_std_dev=float(shared.get("bearing_mu_std_dev", 0.0)),
    )

    profiles: dict[str, VehicleProfile] = {}
    for key in _section_keys(data):
        section = data[key]
        name = str(section.get("name", key))
        profiles[key] = VehicleProfile(
            key=key,
            name=name,
            empty_mass_grams=float(section.get("empty_mass_grams", 0.0)),
            frontal_area_m2=float(section.get("frontal_area_m2", 0.0)),
            drag_coefficient_cd=float(section.get("drag_coefficient_cd", 0.0)),
            lift_coefficient_cl=float(section.get("lift_coefficient_cl", 0.0)),
            wheelbase_mm=float(section.get("wheelbase_mm", 0.0)),
            nozzle_center_offset_y_mm=float(
                section.get("nozzle_center_offset_y_mm", 0.0)
            ),
            bearing_base_friction_mu=float(
                section.get("bearing_base_friction_mu", 0.0)
            ),
            is_placeholder=_is_placeholder(key, name),
            uncertainties=uncertainties,
        )

    active = str(data.get("meta", {}).get("active_profile", ""))
    if active not in profiles and profiles:
        active = next(iter(profiles))
    return profiles, active


def load_track_environments(path: Path | None = None) -> tuple[dict[str, TrackEnvironment], str]:
    data = _read_toml(path or TRACK_FILE)
    shared = data.get("uncertainties", {})
    uncertainties = TrackUncertainties(
        ambient_temp_std_dev_c=float(shared.get("ambient_temp_std_dev_c", 0.0)),
        ambient_pressure_std_dev_kpa=float(
            shared.get("ambient_pressure_std_dev_kpa", 0.0)
        ),
        orifice_diameter_std_dev_mm=float(
            shared.get("orifice_diameter_std_dev_mm", 0.0)
        ),
    )

    locations: dict[str, TrackEnvironment] = {}
    for key in _section_keys(data):
        section = data[key]
        name = str(section.get("location_name", key))
        locations[key] = TrackEnvironment(
            key=key,
            name=name,
            track_length_m=float(section.get("track_length_m", 0.0)),
            ambient_temperature_c=float(section.get("ambient_temperature_c", 0.0)),
            ambient_pressure_kpa=float(section.get("ambient_pressure_kpa", 0.0)),
            relative_humidity_percent=float(
                section.get("relative_humidity_percent", 0.0)
            ),
            guide_wire_tension_newtons=float(
                section.get("guide_wire_tension_newtons", 0.0)
            ),
            orifice_throat_diameter_mm=float(
                section.get("orifice_throat_diameter_mm", 0.0)
            ),
            is_placeholder=_is_placeholder(key, name),
            uncertainties=uncertainties,
        )

    active = str(data.get("meta", {}).get("active_location", ""))
    if active not in locations and locations:
        active = next(iter(locations))
    return locations, active
