# Input forms, profiles, error triggers before a run
from typing import NamedTuple

from textual.app import ComposeResult
from textual.containers import Grid, Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Select, Static

from ...core.config_loader import (
    ConfigError,
    load_track_environments,
    load_vehicle_profiles,
)
from ...core.dataclasses import (
    TrackEnvironment,
    TrackUncertainties,
    VehicleProfile,
    VehicleUncertainties,
)


class _Rule(NamedTuple):
    label: str
    kind: str
    minimum: float
    maximum: float
    hint: str


RULES: dict[str, _Rule] = {
    "veh-mass": _Rule("Mass", "float", 1.0, 1000.0, "between 1 and 1000 g"),
    "veh-area": _Rule("Frontal area", "float", 0.0001, 1.0, "between 0 and 1 m2"),
    "veh-cd": _Rule("Drag coefficient", "float", 0.0, 5.0, "between 0 and 5"),
    "veh-cl": _Rule("Lift coefficient", "float", -5.0, 5.0, "between -5 and 5"),
    "veh-wheelbase": _Rule("Wheelbase", "float", 1.0, 1000.0, "between 1 and 1000 mm"),
    "veh-offset": _Rule("Nozzle offset Y", "float", -100.0, 100.0, "between -100 and 100 mm"),
    "veh-friction": _Rule("Bearing friction", "float", 0.0, 1.0, "between 0 and 1"),
    "trk-length": _Rule("Track length", "float", 1.0, 100.0, "between 1 and 100 m"),
    "trk-temp": _Rule("Ambient temperature", "float", -50.0, 80.0, "between -50 and 80 C"),
    "trk-pressure": _Rule("Ambient pressure", "float", 1.0, 200.0, "between 1 and 200 kPa"),
    "trk-humidity": _Rule("Relative humidity", "float", 0.0, 100.0, "between 0 and 100 %"),
    "trk-wire": _Rule("Wire tension", "float", 0.0, 500.0, "between 0 and 500 N"),
    "trk-orifice": _Rule("Orifice throat", "float", 0.1, 50.0, "between 0.1 and 50 mm"),
    "unc-mass": _Rule("Mass std dev", "float", 0.0, 100.0, "0 or greater grams"),
    "unc-cd": _Rule("Cd std dev", "float", 0.0, 5.0, "0 or greater"),
    "unc-cl": _Rule("Cl std dev", "float", 0.0, 5.0, "0 or greater"),
    "unc-friction": _Rule("Friction std dev", "float", 0.0, 1.0, "0 or greater"),
    "unc-temp": _Rule("Temp std dev", "float", 0.0, 50.0, "0 or greater C"),
    "unc-pressure": _Rule("Pressure std dev", "float", 0.0, 100.0, "0 or greater kPa"),
    "unc-orifice": _Rule("Orifice std dev", "float", 0.0, 50.0, "0 or greater mm"),
    "run-iterations": _Rule("Monte Carlo iterations", "int", 1.0, 1_000_000.0, "a whole number above 0"),
}


class ConfigurationScreen(Screen):
    BINDINGS = [("escape", "app.pop_screen", "Back")]

    _profiles: dict[str, VehicleProfile]
    _locations: dict[str, TrackEnvironment]

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="config-body"):
            yield Static("Configuration", id="config-title")
            yield Static(
                "Development example data is loaded by default. "
                "Adjust the vehicle and track before a run.",
                id="config-subtitle",
            )
            with Grid(id="panel-grid"):
                with Vertical(classes="panel"):
                    yield Static("Vehicle Profile", classes="panel-title")
                    yield Select([], id="vehicle-select")
                    yield from self._vehicle_fields()
                with Vertical(classes="panel"):
                    yield Static("Track Environment", classes="panel-title")
                    yield Select([], id="location-select")
                    yield from self._track_fields()
                with Vertical(classes="panel"):
                    yield Static("Uncertainties", classes="panel-title")
                    yield from self._uncertainty_fields()
                with Vertical(classes="panel"):
                    yield Static("Run Settings", classes="panel-title")
                    yield from self._run_fields()
            yield Static("", id="config-status")
            with Horizontal(id="config-actions"):
                yield Button("Run Simulation", id="run-button", variant="primary")
                yield Button("Quit", id="quit-button", variant="error")

    def on_mount(self) -> None:
        self._profiles = {}
        self._locations = {}
        try:
            self._profiles, active_profile = load_vehicle_profiles()
            self._locations, active_location = load_track_environments()
        except ConfigError as exc:
            self.query_one("#config-status", Static).update(f"[red]{exc}[/red]")
            return

        vehicle_select = self.query_one("#vehicle-select", Select)
        location_select = self.query_one("#location-select", Select)
        vehicle_select.set_options(
            [(profile.name, key) for key, profile in self._profiles.items()]
        )
        location_select.set_options(
            [(place.name, key) for key, place in self._locations.items()]
        )
        if active_profile:
            vehicle_select.value = active_profile
        if active_location:
            location_select.value = active_location

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.value is Select.BLANK:
            return
        key = str(event.value)
        if event.select.id == "vehicle-select":
            profile = self._profiles.get(key)
            if profile is not None:
                self._fill_vehicle(profile)
                self._fill_vehicle_uncertainties(profile.uncertainties)
        elif event.select.id == "location-select":
            location = self._locations.get(key)
            if location is not None:
                self._fill_track(location)
                self._fill_track_uncertainties(location.uncertainties)

    def on_input_changed(self, event: Input.Changed) -> None:
        event.input.remove_class("error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "quit-button":
            self.app.exit()
        elif event.button.id == "run-button":
            self._on_run()

    def _on_run(self) -> None:
        status = self.query_one("#config-status", Static)
        errors = self._validate()
        if errors:
            status.update("[red]" + "   ".join(errors) + "[/red]")
            self.notify("Fix the highlighted fields before running.", severity="error")
            return
        status.update("[green]Inputs valid.[/green]")
        self.notify(
            "Runtime engine not wired up yet - that's the next screen.",
            severity="information",
        )

    def _validate(self) -> list[str]:
        errors: list[str] = []
        for widget_id, rule in RULES.items():
            widget = self.query_one(f"#{widget_id}", Input)
            raw = widget.value.strip()
            valid = bool(raw)
            if valid:
                try:
                    number = int(raw) if rule.kind == "int" else float(raw)
                    valid = rule.minimum <= number <= rule.maximum
                except ValueError:
                    valid = False
            widget.set_class(not valid, "error")
            if not valid:
                errors.append(f"{rule.label}: {rule.hint}")
        return errors

    def _field(self, label: str, widget_id: str, value: str = "") -> ComposeResult:
        with Horizontal(classes="field"):
            yield Label(label, classes="field-label")
            yield Input(value=value, id=widget_id, classes="field-input")

    def _vehicle_fields(self) -> ComposeResult:
        yield from self._field("Mass (g)", "veh-mass")
        yield from self._field("Frontal area (m2)", "veh-area")
        yield from self._field("Drag coeff Cd", "veh-cd")
        yield from self._field("Lift coeff Cl", "veh-cl")
        yield from self._field("Wheelbase (mm)", "veh-wheelbase")
        yield from self._field("Nozzle offset Y (mm)", "veh-offset")
        yield from self._field("Bearing friction", "veh-friction")

    def _track_fields(self) -> ComposeResult:
        yield from self._field("Track length (m)", "trk-length")
        yield from self._field("Ambient temp (C)", "trk-temp")
        yield from self._field("Ambient pressure (kPa)", "trk-pressure")
        yield from self._field("Relative humidity (%)", "trk-humidity")
        yield from self._field("Wire tension (N)", "trk-wire")
        yield from self._field("Orifice throat (mm)", "trk-orifice")

    def _uncertainty_fields(self) -> ComposeResult:
        yield from self._field("Mass std dev (g)", "unc-mass")
        yield from self._field("Cd std dev", "unc-cd")
        yield from self._field("Cl std dev", "unc-cl")
        yield from self._field("Friction std dev", "unc-friction")
        yield from self._field("Temp std dev (C)", "unc-temp")
        yield from self._field("Pressure std dev (kPa)", "unc-pressure")
        yield from self._field("Orifice std dev (mm)", "unc-orifice")

    def _run_fields(self) -> ComposeResult:
        yield from self._field("Monte Carlo iterations", "run-iterations", "10000")

    def _fill_vehicle(self, profile: VehicleProfile) -> None:
        self._set("veh-mass", profile.empty_mass_grams)
        self._set("veh-area", profile.frontal_area_m2)
        self._set("veh-cd", profile.drag_coefficient_cd)
        self._set("veh-cl", profile.lift_coefficient_cl)
        self._set("veh-wheelbase", profile.wheelbase_mm)
        self._set("veh-offset", profile.nozzle_center_offset_y_mm)
        self._set("veh-friction", profile.bearing_base_friction_mu)

    def _fill_track(self, location: TrackEnvironment) -> None:
        self._set("trk-length", location.track_length_m)
        self._set("trk-temp", location.ambient_temperature_c)
        self._set("trk-pressure", location.ambient_pressure_kpa)
        self._set("trk-humidity", location.relative_humidity_percent)
        self._set("trk-wire", location.guide_wire_tension_newtons)
        self._set("trk-orifice", location.orifice_throat_diameter_mm)

    def _fill_vehicle_uncertainties(self, uncertainties: VehicleUncertainties) -> None:
        self._set("unc-mass", uncertainties.mass_std_dev_grams)
        self._set("unc-cd", uncertainties.cd_std_dev)
        self._set("unc-cl", uncertainties.cl_std_dev)
        self._set("unc-friction", uncertainties.bearing_mu_std_dev)

    def _fill_track_uncertainties(self, uncertainties: TrackUncertainties) -> None:
        self._set("unc-temp", uncertainties.ambient_temp_std_dev_c)
        self._set("unc-pressure", uncertainties.ambient_pressure_std_dev_kpa)
        self._set("unc-orifice", uncertainties.orifice_diameter_std_dev_mm)

    def _set(self, widget_id: str, value: float) -> None:
        self.query_one(f"#{widget_id}", Input).value = f"{value:g}"
