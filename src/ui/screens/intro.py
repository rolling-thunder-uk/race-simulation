from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Static

from .configuration import ConfigurationScreen


class IntroScreen(Screen):
    def compose(self) -> ComposeResult:
        with Vertical(id="intro-card"):
            yield Static("ROLLING THUNDER", id="intro-title")
            yield Static(
                "Multi-Physics & Thermodynamic Simulator  v1.0.0",
                id="intro-subtitle",
            )
            yield Static(
                "Designed by Alex Chouliaras for Rolling Thunder",
                id="intro-by",
            )
            yield Static("Team Software Engineer", id="intro-author")
            yield Static(
                "Not responsible for inaccurate timing or simulation results.",
                id="intro-disclaimer",
            )
            yield Static("Licensed under the MIT License.", id="intro-license")
            yield Static(
                "Technical support: DM @mark.api on Discord",
                id="intro-support",
            )
            yield Static("Press any key to continue", id="intro-hint")

    def on_key(self, event: events.Key) -> None:
        event.stop()
        self.app.push_screen(ConfigurationScreen())
