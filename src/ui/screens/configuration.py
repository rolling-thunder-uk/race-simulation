# Input forms, profiles, error triggers before a run
import os
from typing import NamedTuple

from textual.app import ComposeResult
from textual.containers import Grid, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Input, Label, Rule, Select, Static

from ...core.config_loader import (
    ConfigError,
    load_track_environments,
    load_vehicle_profiles,
)
from ...core.constants import APP_HEADER, MODE_LABEL
from ...core.dataclasses import TrackEnvironment, VehicleProfile


class _Rule(NamedTuple):
    label: str
    kind: str
    minimum: float
    maximum: float
    hint: str


RULES: dict[str, _Rule] = {
    "veh-mass": _Rule("Body Mass", "float", 1.0, 1000.0, "between 1 and 1000 g"),
    "veh-area": _Rule("Frontal Area", "float", 0.0001, 1.0, "between 0 and 1 m2"),
    "veh-cd": _Rule("Drag Coeff", "float", 0.0, 5.0, "between 0 and 5"),
    "veh-cl": _Rule("Lift Coeff", "float", -5.0, 5.0, "between -5 and 5"),
    "trk-length": _Rule("Track Length", "float", 1.0, 100.0, "between 1 and 100 m"),
    "trk-temp": _Rule("Ambient Temp", "float", -50.0, 80.0, "between -50 and 80 C"),
    "trk-pressure": _Rule("Baro Pressure", "float", 1.0, 200.0, "between 1 and 200 kPa"),
    "trk-humidity": _Rule("Relative Humidity", "float", 0.0, 100.0, "between 0 and 100 %"),
    "sys-orifice": _Rule("Orifice Throat", "float", 0.1, 50.0, "between 0.1 and 50 mm"),
    "sys-friction": _Rule("Bearing Friction", "float", 0.0, 1.0, "between 0 and 1"),
    "run-iterations": _Rule("Monte Carlo Batch", "int", 1.0, 1_000_000.0, "a whole number above 0"),
    "run-threads": _Rule("CPU Worker Threads", "int", 1.0, 256.0, "a whole number above 0"),
}

DEFAULTS: dict[str, str] = {
    "veh-mass": "0.0",
    "veh-area": "0.000000",
    "veh-cd": "0.000",
    "veh-cl": "0.000",
    "trk-length": "20.0",
    "trk-temp": "0.0",
    "trk-pressure": "0.0",
    "trk-humidity": "0.0",
    "sys-orifice": "0.00",
    "sys-friction": "0.000",
    "run-iterations": "10000",
}


class ConfigurationScreen(Screen):
    BINDINGS = [
        ("enter", "run", "Run simulator"),
        ("f2", "reset", "Reset config"),
        ("escape", "close", "Close simulation"),
    ]

    _profiles: dict[str, VehicleProfile]
    _locations: dict[str, TrackEnvironment]

    def compose(self) -> ComposeResult:
        with Vertical(id="config-root"):
            with Horizontal(id="config-header"):
                yield Static(f"🏁 {APP_HEADER}", id="header-title")
                yield Static(MODE_LABEL, id="header-mode", markup=False)
            yield Rule()
            with Grid(id="panel-grid"):
                with Vertical(classes="panel"):
                    yield Static(
                        "📥 CAR PROPERTIES (VEHICLE SPEC)", classes="panel-title"
                    )
                    yield from self._select_field("Active Profile ID", "vehicle-select")
                    yield from self._number_field("Body Mass (grams)", "veh-mass", "0.0")
                    yield from self._number_field("Frontal Area (m²)", "veh-area", "0.000000")
                    yield from self._number_field("Drag Coeff (Cd)", "veh-cd", "0.000")
                    yield from self._number_field("Lift Coeff (Cl)", "veh-cl", "0.000")
                with Vertical(classes="panel"):
                    yield Static(
                        "🌡️ TRACK CONDITIONS (ENVIRONMENT)", classes="panel-title"
                    )
                    yield from self._select_field("Location ID", "location-select")
                    yield from self._number_field("Track Length (m)", "trk-length", "20.0")
                    yield from self._number_field("Ambient Temp (°C)", "trk-temp", "0.0")
                    yield from self._number_field("Baro Pressure (kPa)", "trk-pressure", "0.0")
                    yield from self._number_field("Relative Humidity (%)", "trk-humidity", "0.0")
                with Vertical(classes="panel panel-last"):
                    yield Static(
                        "🔧 SYSTEM TUNING & HARDWARE", classes="panel-title"
                    )
                    yield from self._number_field("Orifice Throat (mm)", "sys-orifice", "0.00")
                    yield from self._number_field("Bearing Friction (μ)", "sys-friction", "0.000")
                    yield from self._number_field("Monte Carlo Batch", "run-iterations", "10000")
                    threads = str(os.cpu_count() or 1)
                    yield from self._number_field("CPU Worker Threads", "run-threads", threads)
            yield Rule()
            with Vertical(id="checklist-panel"):
                yield Static(
                    "📋 SYSTEM PRE-FLIGHT CHECKLIST & PROFILE DATA VALIDATION",
                    id="checklist-title",
                )
                yield Static("", id="check-vehicle", classes="check-row")
                yield Static("", id="check-fluid", classes="check-row")
                yield Static("", id="check-nozzle", classes="check-row")
                yield Static("", id="check-status", classes="check-status")
            yield Rule()
            yield Static(
                "[ENTER] Trigger Multi-Threaded Simulator Run  │  "
                "[F2] Reset Config Values  │  [ESC] Close Simulation",
                id="config-footer",
                markup=False,
            )

    def on_mount(self) -> None:
        self._profiles = {}
        self._locations = {}
        try:
            self._profiles, _ = load_vehicle_profiles()
            self._locations, _ = load_track_environments()
        except ConfigError as exc:
            self.query_one("#check-status", Static).update(
                f"[bold red]{exc}[/]"
            )

        self.query_one("#vehicle-select", Select).set_options(
            [(profile.name, key) for key, profile in self._profiles.items()]
        )
        self.query_one("#location-select", Select).set_options(
            [(place.name, key) for key, place in self._locations.items()]
        )
        self.refresh_checklist()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.value is Select.BLANK:
            return
        key = str(event.value)
        if event.select.id == "vehicle-select":
            profile = self._profiles.get(key)
            if profile is not None:
                self._fill_vehicle(profile)
        elif event.select.id == "location-select":
            location = self._locations.get(key)
            if location is not None:
                self._fill_track(location)
        self.refresh_checklist()

    def on_input_changed(self, event: Input.Changed) -> None:
        event.input.remove_class("error")
        self.refresh_checklist()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.action_run()

    def action_run(self) -> None:
        self.refresh_checklist()
        if self._launch_blocked():
            self.notify(
                "Launch blocked - initialize the system variables first.",
                severity="error",
            )
            return
        self._validate_fields()
        self.notify(
            "Inputs valid - runtime engine is not wired up yet.",
            severity="information",
        )

    def action_reset(self) -> None:
        for widget_id, value in DEFAULTS.items():
            self.query_one(f"#{widget_id}", Input).value = value
        self.query_one("#vehicle-select", Select).clear()
        self.query_one("#location-select", Select).clear()
        self.refresh_checklist()

    def action_close(self) -> None:
        self.app.exit()

    def _launch_blocked(self) -> bool:
        return not self._checklist_state()[0]

    def _checklist_state(self) -> tuple[bool, bool, bool, bool]:
        mass = self._as_float("veh-mass")
        temp = self._as_float("trk-temp")
        orifice = self._as_float("sys-orifice")
        vehicle_ok = mass is not None and mass > 0
        fluid_ok = temp is not None and temp > 0
        nozzle_ok = orifice is not None and orifice > 0
        return vehicle_ok, fluid_ok, nozzle_ok, vehicle_ok and fluid_ok and nozzle_ok

    def refresh_checklist(self) -> None:
        vehicle_ok, fluid_ok, nozzle_ok, ready = self._checklist_state()
        self.query_one("#check-vehicle", Static).update(
            self._check_line(
                vehicle_ok,
                "Vehicle Data Validation Failure : Target Car Mass is currently "
                "unassigned (0.0g limit breach)",
                "Vehicle Data Verified : Body mass is within operating range",
            )
        )
        self.query_one("#check-fluid", Static).update(
            self._check_line(
                fluid_ok,
                "Fluid Boundary Exception : Ambient Temperature must be verified "
                "before launch cycle",
                "Fluid Boundary Verified : Ambient temperature within operating range",
            )
        )
        self.query_one("#check-nozzle", Static).update(
            self._check_line(
                nozzle_ok,
                "Nozzle Boundary Exception : Orifice puncture throat geometric "
                "channel is uninitialized",
                "Nozzle Boundary Verified : Orifice throat channel initialized",
            )
        )
        if ready:
            self.query_one("#check-status", Static).update(
                "[bold green]📊 SYSTEM DIAGNOSTIC STATUS: "
                "✅ LAUNCH READY — ALL SYSTEMS NOMINAL[/]"
            )
        else:
            self.query_one("#check-status", Static).update(
                "[bold red]📊 SYSTEM DIAGNOSTIC STATUS: "
                "🛑 LAUNCH BLOCKED — INITIALIZE SYSTEM VARIABLES[/]"
            )

    def _check_line(self, ok: bool, failure: str, success: str) -> str:
        colour = "green" if ok else "red"
        icon = "✅" if ok else "❌"
        message = success if ok else failure
        return f"[{colour}]\\[{icon}] {message}[/]"

    def _validate_fields(self) -> list[str]:
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

    def _number_field(self, label: str, widget_id: str, value: str) -> ComposeResult:
        with Horizontal(classes="field-row"):
            yield Label(label.ljust(21) + ":", classes="field-label")
            yield Static("[", classes="field-bracket", markup=False)
            yield Input(value=value, id=widget_id, classes="field-input", compact=True)
            yield Static("]", classes="field-bracket", markup=False)

    def _select_field(self, label: str, widget_id: str) -> ComposeResult:
        with Horizontal(classes="field-row"):
            yield Label(label.ljust(21) + ":", classes="field-label")
            yield Static("[", classes="field-bracket", markup=False)
            yield Select(
                [],
                prompt="N/A",
                allow_blank=True,
                id=widget_id,
                classes="field-select",
                compact=True,
            )
            yield Static("]", classes="field-bracket", markup=False)

    def _fill_vehicle(self, profile: VehicleProfile) -> None:
        self._set("veh-mass", profile.empty_mass_grams)
        self._set("veh-area", profile.frontal_area_m2)
        self._set("veh-cd", profile.drag_coefficient_cd)
        self._set("veh-cl", profile.lift_coefficient_cl)
        self._set("sys-friction", profile.bearing_base_friction_mu)

    def _fill_track(self, location: TrackEnvironment) -> None:
        self._set("trk-length", location.track_length_m)
        self._set("trk-temp", location.ambient_temperature_c)
        self._set("trk-pressure", location.ambient_pressure_kpa)
        self._set("trk-humidity", location.relative_humidity_percent)
        self._set("sys-orifice", location.orifice_throat_diameter_mm)

    def _as_float(self, widget_id: str) -> float | None:
        raw = self.query_one(f"#{widget_id}", Input).value.strip()
        if not raw:
            return None
        try:
            return float(raw)
        except ValueError:
            return None

    def _set(self, widget_id: str, value: float) -> None:
        self.query_one(f"#{widget_id}", Input).value = f"{value:g}"
