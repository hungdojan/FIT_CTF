"""Form-based editor over a shared :class:`ScenarioDesign` instance.

The form mutates the design object owned by the designer page and posts
:class:`DesignForm.Changed` so the page can refresh the preview/layout tabs.
"""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.message import Message
from textual.widgets import (
    Button,
    Checkbox,
    Input,
    Label,
    OptionList,
    Select,
)

from fit_ctf_admin.scenario.design_model import (
    BUILTIN_NETWORKS,
    ScenarioDesign,
    VolumeSlot,
    format_key_value_lines,
    format_port_lines,
    parse_port_lines,
)
from fit_ctf_admin.screens.dialogs.volume_slot_dialog import VolumeSlotDialog
from fit_ctf_admin.widgets.designer.tag_list_editor import TagListEditor

TARGET_OPTIONS = [
    ("User cluster scenario", "user"),
    ("Project cluster scenario", "project"),
]


class DesignForm(VerticalScroll):
    DEFAULT_CSS = """
    DesignForm {
        padding: 0 1;
    }
    DesignForm .form-section {
        text-style: bold;
        margin-top: 1;
    }
    DesignForm .field-label {
        color: $text-muted;
    }
    DesignForm Input, DesignForm Select {
        margin-bottom: 1;
    }
    DesignForm #service-list, DesignForm #volume-list {
        max-height: 6;
        height: auto;
        margin-bottom: 1;
    }
    DesignForm .form-row {
        height: auto;
    }
    DesignForm .form-row Button {
        margin-right: 2;
    }
    DesignForm .network-row {
        height: auto;
    }
    """

    class Changed(Message):
        pass

    def __init__(self, design: ScenarioDesign, module_names: list[str], **kwargs) -> None:
        super().__init__(**kwargs)
        self.design = design
        self._module_names = module_names or ["template"]
        self._selected_block_id: str | None = design.blocks[0].id if design.blocks else None

    # -- composition -----------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Label("Scenario", classes="form-section")
        yield Input(value=self.design.name, placeholder="scenario name (slug)", id="design-name")
        yield Select(
            TARGET_OPTIONS,
            value=self.design.target_kind,
            allow_blank=False,
            id="design-target",
        )
        yield Label("Secrets (values are set per assignment)", classes="form-section")
        yield TagListEditor(
            self.design.secrets,
            add_tag=lambda name: self.design.add_secret(name),
            remove_tag=lambda name: self.design.remove_secret(name),
            placeholder="secret name (e.g. flag_main)",
            id="secrets-tags",
        )
        yield Label("Services", classes="form-section")
        yield OptionList(id="service-list")
        with Horizontal(classes="form-row"):
            yield Button("Add service", id="service-add-btn")
            yield Button("Remove service", id="service-remove-btn")
        yield Label("Selected service", classes="form-section")
        yield Label("Display name", classes="field-label")
        yield Input(placeholder="e.g. Web challenge", id="svc-label")
        yield Label("Module (container image source)", classes="field-label")
        yield Select(
            [(name, name) for name in self._module_names],
            value=self._module_names[0],
            allow_blank=False,
            id="svc-module",
        )
        yield Label("Service key (compose service name, slug)", classes="field-label")
        yield Input(placeholder="e.g. web", id="svc-key")
        yield Label("Container name (empty = random)", classes="field-label")
        yield Input(placeholder="e.g. web_ctr_1", id="svc-container")
        yield Label("Networks", classes="field-label")
        with Horizontal(classes="network-row"):
            for network in BUILTIN_NETWORKS:
                yield Checkbox(network, id=f"svc-net-{network}")
        yield Label("Ports (name:port, comma separated)", classes="field-label")
        yield Input(placeholder="e.g. http:8080, ssh:2222", id="svc-ports")
        yield Label("Env variables of the selected service", classes="field-label")
        yield TagListEditor(
            [],
            add_tag=self._add_env_key,
            remove_tag=self._remove_env_key,
            placeholder="env name (e.g. ADMIN)",
            id="svc-env-tags",
        )
        yield Label("Volumes of the selected service", classes="form-section")
        yield OptionList(id="volume-list")
        with Horizontal(classes="form-row"):
            yield Button("Add volume", id="volume-add-btn")
            yield Button("Edit volume", id="volume-edit-btn")
            yield Button("Remove volume", id="volume-remove-btn")
        with Horizontal(classes="form-row"):
            yield Button("Apply service changes", variant="primary", id="svc-apply-btn")

    def on_mount(self) -> None:
        self._reload_service_list()
        self._load_detail()

    # -- helpers ---------------------------------------------------------------

    @property
    def selected_block(self):
        if self._selected_block_id is None:
            return None
        return self.design.get_block(self._selected_block_id)

    def _changed(self) -> None:
        self.post_message(self.Changed())

    def _add_env_key(self, key: str) -> None:
        if self._selected_block_id is None:
            raise ValueError("Select a service first.")
        self.design.add_env_to_block(self._selected_block_id, key)

    def _remove_env_key(self, key: str) -> None:
        if self._selected_block_id is None:
            return
        self.design.remove_env_from_block(self._selected_block_id, key)

    def _rebind_env_editor(self) -> None:
        block = self.selected_block
        self.query_one("#svc-env-tags", TagListEditor).rebind(
            block.env_keys if block is not None else []
        )

    def _reload_service_list(self) -> None:
        option_list = self.query_one("#service-list", OptionList)
        option_list.clear_options()
        option_list.add_options([block.label for block in self.design.blocks])
        if self.selected_block is not None:
            index = next(
                (
                    i
                    for i, block in enumerate(self.design.blocks)
                    if block.id == self._selected_block_id
                ),
                None,
            )
            if index is not None:
                option_list.highlighted = index

    def _load_detail(self) -> None:
        block = self.selected_block
        detail_ids = (
            "#svc-label",
            "#svc-key",
            "#svc-container",
            "#svc-ports",
        )
        if block is None:
            for widget_id in detail_ids:
                self.query_one(widget_id, Input).value = ""
            for network in BUILTIN_NETWORKS:
                self.query_one(f"#svc-net-{network}", Checkbox).value = False
            self.query_one("#volume-list", OptionList).clear_options()
            self._rebind_env_editor()
            return
        self.query_one("#svc-label", Input).value = block.label
        self.query_one("#svc-module", Select).value = (
            block.module_name if block.module_name in self._module_names else Select.BLANK
        )
        self.query_one("#svc-key", Input).value = block.service_key
        self.query_one("#svc-container", Input).value = block.container_name or ""
        for network in BUILTIN_NETWORKS:
            self.query_one(f"#svc-net-{network}", Checkbox).value = network in block.networks
        self.query_one("#svc-ports", Input).value = format_port_lines(block.ports)
        self._rebind_env_editor()
        self._reload_volume_list()

    def _reload_volume_list(self) -> None:
        block = self.selected_block
        option_list = self.query_one("#volume-list", OptionList)
        option_list.clear_options()
        if block is not None:
            option_list.add_options(
                [
                    f"{slot.name} → {slot.container_path} ({slot.kind}"
                    f"{', ro' if slot.read_only else ''})"
                    for slot in block.volumes
                ]
            )

    # -- scenario meta -----------------------------------------------------------

    @on(Input.Changed, "#design-name")
    def _name_changed(self, event: Input.Changed) -> None:
        self.design.name = event.value.strip() or "new_scenario"
        self._changed()

    @on(Select.Changed, "#design-target")
    def _target_changed(self, event: Select.Changed) -> None:
        self.design.target_kind = str(event.value)  # type: ignore[assignment]
        self._changed()

    @on(TagListEditor.Changed)
    def _secrets_changed(self) -> None:
        self._changed()

    # -- service list ------------------------------------------------------------

    @on(OptionList.OptionHighlighted, "#service-list")
    def _service_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if event.option_index is not None and event.option_index < len(self.design.blocks):
            self._selected_block_id = self.design.blocks[event.option_index].id
            self._load_detail()

    @on(Button.Pressed, "#service-add-btn")
    def _add_service(self, event: Button.Pressed) -> None:
        event.stop()
        module = str(self.query_one("#svc-module", Select).value or "template")
        block = self.design.add_block(module_name=module)
        self._selected_block_id = block.id
        self._reload_service_list()
        self._load_detail()
        self._changed()

    @on(Button.Pressed, "#service-remove-btn")
    def _remove_service(self, event: Button.Pressed) -> None:
        event.stop()
        if self._selected_block_id is None:
            self.notify("Select a service first.", severity="warning")
            return
        self.design.remove_block(self._selected_block_id)
        self._selected_block_id = self.design.blocks[0].id if self.design.blocks else None
        self._reload_service_list()
        self._load_detail()
        self._changed()

    # -- service detail ------------------------------------------------------------

    @on(Button.Pressed, "#svc-apply-btn")
    def _apply_detail(self, event: Button.Pressed) -> None:
        event.stop()
        block = self.selected_block
        if block is None:
            self.notify("Select a service first.", severity="warning")
            return
        try:
            label = self.query_one("#svc-label", Input).value.strip()
            if label:
                block.label = label
            key = self.query_one("#svc-key", Input).value.strip()
            if key and key != block.service_key:
                self.design.set_service_key(block.id, key)
                block.service_key_mode = "concrete"
            container = self.query_one("#svc-container", Input).value.strip()
            self.design.set_container_name(block.id, container or None)
            block.container_name_mode = "concrete" if container else "random"
            module = self.query_one("#svc-module", Select).value
            if module is not Select.BLANK:
                block.module_name = str(module)
            networks = [
                network
                for network in BUILTIN_NETWORKS
                if self.query_one(f"#svc-net-{network}", Checkbox).value
            ]
            block.networks = networks or ["shared"]
            block.ports = parse_port_lines(self.query_one("#svc-ports", Input).value)
        except ValueError as exc:
            self.notify(str(exc), severity="error")
            return
        self._reload_service_list()
        self._load_detail()
        self._changed()
        self.notify(f"Service `{block.label}` updated.")

    # -- volumes ---------------------------------------------------------------------

    def _selected_volume_index(self) -> int | None:
        option_list = self.query_one("#volume-list", OptionList)
        return option_list.highlighted

    @on(Button.Pressed, "#volume-add-btn")
    def _add_volume(self, event: Button.Pressed) -> None:
        event.stop()
        if self.selected_block is None:
            self.notify("Select a service first.", severity="warning")
            return
        self.app.push_screen(VolumeSlotDialog(), self._volume_saved(None))

    @on(Button.Pressed, "#volume-edit-btn")
    def _edit_volume(self, event: Button.Pressed) -> None:
        event.stop()
        block = self.selected_block
        index = self._selected_volume_index()
        if block is None or index is None or index >= len(block.volumes):
            self.notify("Select a volume first.", severity="warning")
            return
        self.app.push_screen(VolumeSlotDialog(block.volumes[index]), self._volume_saved(index))

    def _volume_saved(self, index: int | None):
        def _callback(slot: VolumeSlot | None) -> None:
            block = self.selected_block
            if slot is None or block is None:
                return
            duplicate = any(
                other.name == slot.name for i, other in enumerate(block.volumes) if i != index
            )
            if duplicate:
                self.notify(f"Volume `{slot.name}` already exists.", severity="error")
                return
            if index is None:
                block.volumes.append(slot)
            else:
                block.volumes[index] = slot
            self._reload_volume_list()
            self._changed()

        return _callback

    @on(Button.Pressed, "#volume-remove-btn")
    def _remove_volume(self, event: Button.Pressed) -> None:
        event.stop()
        block = self.selected_block
        index = self._selected_volume_index()
        if block is None or index is None or index >= len(block.volumes):
            self.notify("Select a volume first.", severity="warning")
            return
        del block.volumes[index]
        self._reload_volume_list()
        self._changed()


# re-export for callers formatting env maps (kept for API parity with the old toolbox)
__all__ = ["DesignForm", "format_key_value_lines"]
