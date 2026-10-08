from textual.app import App

from .screens.intro import IntroScreen


class RollingThunderApp(App):
    TITLE = "Rolling Thunder"
    SUB_TITLE = "Multi-Physics & Thermodynamic Simulator"
    CSS_PATH = "stylet.tcss"
    BINDINGS = [("ctrl+q", "quit", "Quit")]

    def on_mount(self) -> None:
        self.push_screen(IntroScreen())
