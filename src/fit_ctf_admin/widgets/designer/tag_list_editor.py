"""Editor for a list of name-only tags (used for scenario secrets)."""

from __future__ import annotations

from typing import Callable

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, Input, OptionList


class TagListEditor(Vertical):
    DEFAULT_CSS = """
    TagListEditor {
        height: auto;
    }
    TagListEditor OptionList {
        max-height: 6;
        height: auto;
    }
    TagListEditor Horizontal {
        height: auto;
    }
    TagListEditor Input {
        width: 1fr;
    }
    """

    class Changed(Message):
        pass

    def __init__(
        self,
        tags: list[str],
        *,
        add_tag: Callable[[str], object],
        remove_tag: Callable[[str], object],
        placeholder: str = "new entry",
        **kwargs,
    ) -> None:
        """``add_tag``/``remove_tag`` mutate the backing list and may raise ValueError."""
        super().__init__(**kwargs)
        self._tags = tags
        self._add_tag = add_tag
        self._remove_tag = remove_tag
        self._placeholder = placeholder

    def compose(self) -> ComposeResult:
        yield OptionList(*self._tags, id="tag-list")
        with Horizontal():
            yield Input(placeholder=self._placeholder, id="tag-input")
            yield Button("Add", id="tag-add-btn")
            yield Button("Remove", id="tag-remove-btn")

    def _refresh_options(self) -> None:
        option_list = self.query_one("#tag-list", OptionList)
        option_list.clear_options()
        option_list.add_options(list(self._tags))

    def _reload(self) -> None:
        self._refresh_options()
        self.post_message(self.Changed())

    def rebind(
        self,
        tags: list[str],
        *,
        add_tag: Callable[[str], object] | None = None,
        remove_tag: Callable[[str], object] | None = None,
    ) -> None:
        """Point the editor at a different backing list (no Changed message)."""
        self._tags = tags
        if add_tag is not None:
            self._add_tag = add_tag
        if remove_tag is not None:
            self._remove_tag = remove_tag
        self._refresh_options()

    @on(Input.Submitted, "#tag-input")
    @on(Button.Pressed, "#tag-add-btn")
    def _add(self, event) -> None:
        event.stop()
        value = self.query_one("#tag-input", Input).value.strip()
        if not value:
            return
        try:
            self._add_tag(value)
        except ValueError as exc:
            self.notify(str(exc), severity="error")
            return
        self.query_one("#tag-input", Input).value = ""
        self._reload()

    @on(Button.Pressed, "#tag-remove-btn")
    def _remove(self, event: Button.Pressed) -> None:
        event.stop()
        option_list = self.query_one("#tag-list", OptionList)
        if option_list.highlighted is None:
            self.notify("Select an entry first.", severity="warning")
            return
        option = option_list.get_option_at_index(option_list.highlighted)
        self._remove_tag(str(option.prompt))
        self._reload()
