"""Live compose preview for the current design."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static, TextArea

from fit_ctf_admin.scenario.compose_export import export_compose_preview
from fit_ctf_admin.scenario.design_model import ScenarioDesign


class PreviewPanel(Widget):
    """Read-only YAML preview of the scenario compose template."""

    DEFAULT_CSS = """
    PreviewPanel {
        width: 1fr;
        height: 1fr;
        padding: 0 1;
    }

    PreviewPanel TextArea {
        width: 1fr;
        height: 1fr;
    }
    """

    def __init__(self, design: ScenarioDesign, **kwargs) -> None:
        super().__init__(**kwargs)
        self.design = design

    def compose(self) -> ComposeResult:
        yield Static("Compose preview (scenario_compose.yaml.j2)", id="preview-title")
        yield TextArea(
            export_compose_preview(self.design),
            id="compose-preview",
            read_only=True,
            language="yaml",
            show_line_numbers=True,
            soft_wrap=False,
        )

    def refresh_preview(self, design: ScenarioDesign | None = None) -> None:
        if design is not None:
            self.design = design
        self.query_one("#compose-preview", TextArea).text = export_compose_preview(self.design)
