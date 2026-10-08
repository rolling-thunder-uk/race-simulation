# Strict immutable definitions for states and specs
from dataclasses import dataclass


@dataclass(frozen=True)
class VehicleUncertainties:
    mass_std_dev_grams: float = 0.0
    cd_std_dev: float = 0.0
    cl_std_dev: float = 0.0
    bearing_mu_std_dev: float = 0.0


@dataclass(frozen=True)
class VehicleProfile:
    key: str
    name: str
    empty_mass_grams: float
    frontal_area_m2: float
    drag_coefficient_cd: float
    lift_coefficient_cl: float
    wheelbase_mm: float
    nozzle_center_offset_y_mm: float
    bearing_base_friction_mu: float
    is_placeholder: bool = False
    uncertainties: VehicleUncertainties = VehicleUncertainties()


@dataclass(frozen=True)
class TrackUncertainties:
    ambient_temp_std_dev_c: float = 0.0
    ambient_pressure_std_dev_kpa: float = 0.0
    orifice_diameter_std_dev_mm: float = 0.0


@dataclass(frozen=True)
class TrackEnvironment:
    key: str
    name: str
    track_length_m: float
    ambient_temperature_c: float
    ambient_pressure_kpa: float
    relative_humidity_percent: float
    guide_wire_tension_newtons: float
    orifice_throat_diameter_mm: float
    is_placeholder: bool = False
    uncertainties: TrackUncertainties = TrackUncertainties()
