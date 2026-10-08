from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static


class ConfigurationScreen(Screen):
    BINDINGS = [("escape", "app.pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        yield Static("Configuration", id="config-title")
        yield Static("Coming soon. Press Esc to go back.", id="config-body")
