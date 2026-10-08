# Focusable inline selector that cycles options without a dropdown overlay
from textual.message import Message
from textual.widgets import Static


class ChoiceField(Static):
    can_focus = True

    BINDINGS = [
        ("left", "previous", "Previous option"),
        ("right", "next", "Next option"),
    ]

    class Changed(Message):
        def __init__(self, choice: "ChoiceField", value: str | None) -> None:
            self.choice = choice
            self.value = value
            super().__init__()

    def __init__(
        self,
        options: list[tuple[str, str]] | None = None,
        placeholder: str = "N/A",
        **kwargs,
    ) -> None:
        super().__init__(placeholder, **kwargs)
        self._options = list(options or [])
        self._placeholder = placeholder
        self._index = -1

    @property
    def value(self) -> str | None:
        if 0 <= self._index < len(self._options):
            return self._options[self._index][1]
        return None

    def set_options(self, options: list[tuple[str, str]]) -> None:
        self._options = list(options)
        self._index = -1
        self._render_value()

    def clear(self) -> None:
        self._index = -1
        self._render_value()

    def action_next(self) -> None:
        self._cycle(1)

    def action_previous(self) -> None:
        self._cycle(-1)

    def _cycle(self, step: int) -> None:
        if not self._options:
            return
        self._index = (self._index + step) % len(self._options)
        self._render_value()
        self.post_message(self.Changed(self, self.value))

    def _render_value(self) -> None:
        if 0 <= self._index < len(self._options):
            self.update(self._options[self._index][0])
        else:
            self.update(self._placeholder)
