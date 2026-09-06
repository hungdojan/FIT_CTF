"""Generic key→value editor used for secrets and config params."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input

from fit_ctf_admin.scenario.secret_macro import (
    DEFAULT_GENERATED_LENGTH,
    random_token,
)


def generate_flag_value() -> str:
    """Random CTF-style flag with a 32-char token, e.g. ``FLAG{…}``."""
    return f"FLAG{{{random_token(DEFAULT_GENERATED_LENGTH)}}}"


class KVRow(Horizontal):
    DEFAULT_CSS = """
    KVRow {
        height: auto;
    }
    KVRow .kv-key {
        width: 1fr;
    }
    KVRow .kv-value {
        width: 2fr;
    }
    """

    def __init__(
        self,
        key: str = "",
        value: str = "",
        *,
        masked: bool = False,
        generatable: bool = False,
    ) -> None:
        super().__init__()
        self._key = key
        self._value = value
        self._masked = masked
        self._generatable = generatable

    def compose(self) -> ComposeResult:
        yield Input(value=self._key, placeholder="key", classes="kv-key")
        yield Input(
            value=self._value,
            placeholder="value",
            password=self._masked,
            classes="kv-value",
        )
        if self._generatable:
            yield Button("Gen", classes="kv-generate", tooltip="Fill with a random FLAG{…} value")
        yield Button("✕", classes="kv-remove")

    @property
    def item(self) -> tuple[str, str]:
        key = self.query_one(".kv-key", Input).value.strip()
        value = self.query_one(".kv-value", Input).value
        return key, value


class KeyValueEditor(Vertical):
    """Editable key/value rows with add/remove; read back via :meth:`data`.

    With ``generatable=True`` every row gets a "Gen" button that fills the
    value with a random ``FLAG{…}`` string (for CTF secrets).
    """

    DEFAULT_CSS = """
    KeyValueEditor {
        height: auto;
    }
    KeyValueEditor .kv-add {
        margin-top: 1;
    }
    """

    def __init__(
        self,
        initial: dict[str, str] | None = None,
        *,
        masked: bool = False,
        generatable: bool = False,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._initial = dict(initial or {})
        self._masked = masked
        self._generatable = generatable

    def _make_row(self, key: str = "", value: str = "") -> KVRow:
        return KVRow(key, value, masked=self._masked, generatable=self._generatable)

    def compose(self) -> ComposeResult:
        for key, value in self._initial.items():
            yield self._make_row(key, str(value))
        yield Button("Add entry", classes="kv-add")

    def data(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for row in self.query(KVRow):
            key, value = row.item
            if key:
                result[key] = value
        return result

    @on(Button.Pressed, ".kv-remove")
    async def _remove_row(self, event: Button.Pressed) -> None:
        event.stop()
        parent = event.button.parent
        if isinstance(parent, KVRow):
            await parent.remove()

    @on(Button.Pressed, ".kv-generate")
    def _generate_value(self, event: Button.Pressed) -> None:
        event.stop()
        parent = event.button.parent
        if isinstance(parent, KVRow):
            parent.query_one(".kv-value", Input).value = generate_flag_value()

    @on(Button.Pressed, ".kv-add")
    async def _add_row(self, event: Button.Pressed) -> None:
        event.stop()
        add_button = self.query_one(".kv-add", Button)
        await self.mount(self._make_row(), before=add_button)
