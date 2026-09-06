"""Pilot tests for the admin TUI shell and management pages (preview mode)."""

import pytest
from textual.widgets import Button, Checkbox, ContentSwitcher, Input, Select

from fit_ctf_admin.admin_app import AdminApp
from fit_ctf_admin.core.admin_core import AdminCore
from fit_ctf_admin.screens.dialogs.confirm_dialog import ConfirmDialog
from fit_ctf_admin.screens.dialogs.enroll_dialog import EnrollDialog
from fit_ctf_admin.screens.dialogs.new_user_dialog import NewUserDialog
from fit_ctf_admin.screens.dialogs.secret_reveal_dialog import SecretRevealDialog
from fit_ctf_admin.widgets.refreshable_table import RefreshableTable

SIZE = (120, 45)


@pytest.fixture
def app() -> AdminApp:
    return AdminApp(AdminCore.preview())


async def _settle(pilot) -> None:
    # let pending messages (e.g. Show -> refresh_page) spawn their workers first
    await pilot.pause()
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()


async def _goto(pilot, page_id: str) -> None:
    # sidebar buttons for later pages can be scrolled out of view, so navigate
    # programmatically; click-based navigation is covered by
    # test_sidebar_navigation
    pilot.app.screen.show_page(page_id)
    await _settle(pilot)


def _switcher(app: AdminApp) -> ContentSwitcher:
    return app.screen.query_one("#admin-content", ContentSwitcher)


async def test_boots_into_dashboard(app: AdminApp):
    async with app.run_test(size=SIZE) as pilot:
        await _settle(pilot)
        assert _switcher(app).current == "dashboard-page"
        counts = str(app.screen.query_one("#dashboard-counts").render())
        assert "Users: 4" in counts
        assert "Scenarios: 3" in counts and "Modules: 3" in counts
        overview = app.screen.query_one("#dashboard-projects-table", RefreshableTable)
        assert overview.row_count == 2  # active sample projects
        running_cell = overview.get_row("intro_linux")
        assert "yes" in running_cell  # intro_linux cluster runs in sample data


async def test_sidebar_navigation(app: AdminApp):
    async with app.run_test(size=SIZE) as pilot:
        await pilot.click("#nav-users-page")
        await _settle(pilot)
        assert _switcher(app).current == "users-page"
        table = app.screen.query_one("#users-table", RefreshableTable)
        assert table.row_count == 3  # active sample users

        await _goto(pilot, "projects-page")
        assert _switcher(app).current == "projects-page"
        table = app.screen.query_one("#projects-table", RefreshableTable)
        assert table.row_count == 2  # active sample projects


async def test_page_keybindings(app: AdminApp):
    async with app.run_test(size=SIZE) as pilot:
        await pilot.press("4")
        await _settle(pilot)
        assert _switcher(app).current == "enrollments-page"
        table = app.screen.query_one("#enrollments-table", RefreshableTable)
        assert table.row_count == 4


async def test_show_inactive_filter(app: AdminApp):
    async with app.run_test(size=SIZE) as pilot:
        await _goto(pilot, "users-page")
        checkbox = app.screen.query_one("#users-show-inactive", Checkbox)
        checkbox.value = True
        await _settle(pilot)
        table = app.screen.query_one("#users-table", RefreshableTable)
        assert table.row_count == 4  # carol becomes visible


async def test_create_user_flow_reveals_password_once(app: AdminApp):
    async with app.run_test(size=SIZE) as pilot:
        await _goto(pilot, "users-page")
        await pilot.click("#users-new-btn")
        await pilot.pause()
        assert isinstance(app.screen, NewUserDialog)

        app.screen.query_one("#new-user-username", Input).value = "erin"
        app.screen.query_one("#new-user-generate", Checkbox).value = True
        await pilot.pause()
        await pilot.click("#new-user-create-btn")
        await _settle(pilot)

        assert isinstance(app.screen, SecretRevealDialog)
        await pilot.click("#secret-done-btn")
        await _settle(pilot)

        table = app.screen.query_one("#users-table", RefreshableTable)
        assert table.row_count == 4  # 3 active + erin


async def test_create_user_empty_username_shows_error(app: AdminApp):
    async with app.run_test(size=SIZE) as pilot:
        await _goto(pilot, "users-page")
        await pilot.click("#users-new-btn")
        await pilot.pause()
        app.screen.query_one("#new-user-generate", Checkbox).value = True
        await pilot.pause()
        await pilot.click("#new-user-create-btn")
        await _settle(pilot)
        # dialog dismissed, error surfaced as a notification, table unchanged
        table = app.screen.query_one("#users-table", RefreshableTable)
        assert table.row_count == 3


async def test_delete_project_requires_confirmation(app: AdminApp):
    async with app.run_test(size=SIZE) as pilot:
        await _goto(pilot, "projects-page")
        table = app.screen.query_one("#projects-table", RefreshableTable)
        assert table.row_count == 2

        await pilot.click("#projects-delete-btn")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmDialog)
        await pilot.click("#confirm-cancel-btn")
        await _settle(pilot)
        assert table.row_count == 2  # cancel keeps the project

        await pilot.click("#projects-delete-btn")
        await pilot.pause()
        await pilot.click("#confirm-ok-btn")
        await _settle(pilot)
        assert table.row_count == 1


async def test_enroll_flow(app: AdminApp):
    async with app.run_test(size=SIZE) as pilot:
        await _goto(pilot, "enrollments-page")
        await pilot.click("#enrollments-enroll-btn")
        await _settle(pilot)
        assert isinstance(app.screen, EnrollDialog)

        project_select = app.screen.query_one("#enroll-project-select", Select)
        project_select.value = "intro_linux"
        await _settle(pilot)
        user_select = app.screen.query_one("#enroll-user-select", Select)
        assert not user_select.disabled
        user_select.value = "dave"  # not yet enrolled in intro_linux
        await pilot.click("#enroll-ok-btn")
        await _settle(pilot)

        table = app.screen.query_one("#enrollments-table", RefreshableTable)
        assert table.row_count == 5


async def test_clusters_page_lifecycle(app: AdminApp):
    async with app.run_test(size=SIZE) as pilot:
        await _goto(pilot, "clusters-page")
        table = app.screen.query_one("#project-clusters-table", RefreshableTable)
        assert table.row_count == 2  # active sample projects

        # select web_exploitation project cluster and start it
        table.move_cursor(row=table.get_row_index("web_exploitation"))
        await pilot.click("#pc-start-btn")
        await _settle(pilot)
        core = app.admin_core
        assert core.gateway.store.project_clusters_running["web_exploitation"] is True

        # user clusters table follows the project select
        select = app.screen.query_one("#uc-project-select", Select)
        select.value = "intro_linux"
        await _settle(pilot)
        user_table = app.screen.query_one("#user-clusters-table", RefreshableTable)
        assert user_table.row_count == 2  # alice + bob enrolled in intro_linux


async def test_clusters_health_dialog(app: AdminApp):
    from fit_ctf_admin.screens.dialogs.table_dialog import TableDialog

    async with app.run_test(size=SIZE) as pilot:
        await _goto(pilot, "clusters-page")
        table = app.screen.query_one("#project-clusters-table", RefreshableTable)
        table.move_cursor(row=table.get_row_index("intro_linux"))
        await pilot.click("#pc-health-btn")
        await _settle(pilot)
        assert isinstance(app.screen, TableDialog)
        await pilot.click("#table-dialog-close-btn")
        await _settle(pilot)


async def test_scenarios_page_assignment_flow(app: AdminApp):
    from textual.widgets import TextArea

    from fit_ctf_admin.screens.scenario_config_screen import ScenarioConfigScreen
    from fit_ctf_admin.widgets.kv_editor import KeyValueEditor, KVRow

    async with app.run_test(size=(140, 50)) as pilot:
        await _goto(pilot, "scenarios-page")
        templates = app.screen.query_one("#scenario-templates-table", RefreshableTable)
        assert templates.row_count == 3  # sample scenario defs

        # pick target: project cluster intro_linux
        app.screen.query_one("#target-project-select", Select).value = "intro_linux"
        await _settle(pilot)
        assigned = app.screen.query_one("#assigned-scenarios-table", RefreshableTable)
        assert assigned.row_count == 1  # admin_node from sample data

        # assign web_stack
        templates.move_cursor(row=templates.get_row_index("web_stack"))
        await pilot.click("#scenario-assign-btn")
        await _settle(pilot)
        assert isinstance(app.screen, ScenarioConfigScreen)

        # fill the required port in the YAML section and the secret in the kv editor
        yaml_area = app.screen.query_one("#services-yaml", TextArea)
        yaml_area.text = yaml_area.text.replace("http: ''", "http: '8080'").replace(
            "ADMIN: ''", "ADMIN: admin"
        )
        secrets = app.screen.query_one("#secrets-editor", KeyValueEditor)
        secret_row = secrets.query(KVRow).first()
        secret_row.query_one(".kv-value", Input).value = "FLAG{pilot}"

        await pilot.click("#config-save-btn")
        await _settle(pilot)
        # back on the scenarios page, web_stack now assigned
        assigned = app.screen.query_one("#assigned-scenarios-table", RefreshableTable)
        assert assigned.row_count == 2


async def test_scenario_config_validation_surface(app: AdminApp):
    from textual.widgets import Static

    from fit_ctf_admin.screens.scenario_config_screen import ScenarioConfigScreen

    async with app.run_test(size=(140, 50)) as pilot:
        await _goto(pilot, "scenarios-page")
        app.screen.query_one("#target-project-select", Select).value = "intro_linux"
        await _settle(pilot)
        templates = app.screen.query_one("#scenario-templates-table", RefreshableTable)
        templates.move_cursor(row=templates.get_row_index("web_stack"))
        await pilot.click("#scenario-assign-btn")
        await _settle(pilot)
        assert isinstance(app.screen, ScenarioConfigScreen)

        await pilot.click("#config-validate-btn")
        await _settle(pilot)
        results = str(app.screen.query_one("#config-results", Static).render())
        assert "port" in results  # empty port reported

        await pilot.click("#config-cancel-btn")
        await _settle(pilot)


async def test_designer_new_save_open_roundtrip(app: AdminApp):
    from fit_ctf_admin.screens.dialogs.input_dialog import InputDialog
    from fit_ctf_admin.widgets.designer.design_form import DesignForm
    from fit_ctf_admin.widgets.designer.preview_panel import PreviewPanel

    async with app.run_test(size=(140, 50)) as pilot:
        await _goto(pilot, "designer-page")

        # new design via dialog
        await pilot.click("#designer-new-btn")
        await pilot.pause()
        assert isinstance(app.screen, InputDialog)
        app.screen.query_one("#input-dialog-value", Input).value = "pilot_scn"
        await pilot.click("#input-dialog-ok-btn")
        await _settle(pilot)

        form = app.screen.query_one("#design-form", DesignForm)
        assert form.design.name == "pilot_scn"
        assert len(form.design.blocks) == 1

        # preview follows the design
        preview = app.screen.query_one("#designer-preview", PreviewPanel)
        assert "pilot_scn" in preview.design.name

        # save writes into the preview store and registers the scenario
        await pilot.click("#designer-save-btn")
        await _settle(pilot)
        store = app.admin_core.gateway.store
        assert "pilot_scn" in store.designs
        assert "pilot_scn" in store.scenario_defs

        # open restores the design from the sidecar equivalent
        app.screen.query_one("#designer-scenario-select", Select).value = "pilot_scn"
        await pilot.click("#designer-open-btn")
        await _settle(pilot)
        form = app.screen.query_one("#design-form", DesignForm)
        assert form.design.name == "pilot_scn"


async def test_designer_raw_edit_flow(app: AdminApp):
    from textual.widgets import TextArea

    from fit_ctf_admin.screens.raw_template_screen import RawTemplateScreen

    async with app.run_test(size=(140, 50)) as pilot:
        await _goto(pilot, "designer-page")
        app.screen.query_one("#designer-scenario-select", Select).value = "web_stack"
        await pilot.click("#designer-raw-btn")
        await _settle(pilot)
        assert isinstance(app.screen, RawTemplateScreen)
        area = app.screen.query_one("#raw-template-area", TextArea)
        area.text = "# edited raw\n" + area.text
        await pilot.click("#raw-save-btn")
        await _settle(pilot)
        store = app.admin_core.gateway.store
        assert store.designs["web_stack"]["compose_text"].startswith("# edited raw")


async def test_modules_page(app: AdminApp):
    from fit_ctf_admin.screens.dialogs.input_dialog import InputDialog

    async with app.run_test(size=SIZE) as pilot:
        await _goto(pilot, "modules-page")
        table = app.screen.query_one("#modules-table", RefreshableTable)
        assert table.row_count == 3  # template, ssh_debian, ssh_ubi

        await pilot.click("#modules-new-btn")
        await pilot.pause()
        assert isinstance(app.screen, InputDialog)
        app.screen.query_one("#input-dialog-value", Input).value = "custom_mod"
        await pilot.click("#input-dialog-ok-btn")
        await _settle(pilot)
        assert table.row_count == 4

        # deleting a referenced module fails with a notification, module stays
        table.move_cursor(row=table.get_row_index("ssh_ubi"))
        await pilot.click("#modules-delete-btn")
        await pilot.pause()
        await pilot.click("#confirm-ok-btn")
        await _settle(pilot)
        assert table.row_count == 4


async def test_progress_page(app: AdminApp):
    async with app.run_test(size=(140, 50)) as pilot:
        await _goto(pilot, "progress-page")
        app.screen.query_one("#progress-project-select", Select).value = "intro_linux"
        await _settle(pilot)
        board = app.screen.query_one("#leaderboard-table", RefreshableTable)
        assert board.row_count == 2

        # highlight alice -> drill-down tables fill
        board.move_cursor(row=board.get_row_index("alice"))
        await _settle(pilot)
        solved = app.screen.query_one("#solved-table", RefreshableTable)
        submissions = app.screen.query_one("#submissions-table", RefreshableTable)
        assert solved.row_count == 1
        assert submissions.row_count == 2


async def test_logs_page(app: AdminApp):
    from textual.widgets import Log

    async with app.run_test(size=(140, 50)) as pilot:
        await _goto(pilot, "logs-page")
        app.screen.query_one("#logs-project-select", Select).value = "intro_linux"
        app.screen.query_one("#logs-load-btn", Button).press()
        await _settle(pilot)
        log_widget = app.screen.query_one("#logs-output", Log)
        assert any("admin node ready" in line for line in log_widget.lines)

        # user cluster logs
        app.screen.query_one("#logs-kind-select", Select).value = "user"
        await _settle(pilot)
        app.screen.query_one("#logs-user-select", Select).value = "alice"
        app.screen.query_one("#logs-load-btn", Button).press()
        await _settle(pilot)
        assert any("Accepted password" in line for line in log_widget.lines)


async def test_sessions_page(app: AdminApp):
    async with app.run_test(size=(140, 50)) as pilot:
        await _goto(pilot, "sessions-page")
        app.screen.query_one("#sessions-user-select", Select).value = "alice"
        await pilot.click("#sessions-user-btn")
        await _settle(pilot)
        table = app.screen.query_one("#sessions-table", RefreshableTable)
        assert table.row_count == 3  # login, instance start, logout

        app.screen.query_one("#sessions-project-select", Select).value = "intro_linux"
        await pilot.click("#sessions-ssh-btn")
        await _settle(pilot)
        assert table.row_count == 3  # canned sshd lines: login, opened, closed


async def test_designer_refresh_does_not_duplicate_block_ids(app: AdminApp):
    """Regression: target-kind switch / secret add / repeated applies used to
    crash with DuplicateIds because the canvas mounted new BlockNodes before
    the old ones were removed."""
    from fit_ctf_admin.widgets.designer.design_canvas import DesignCanvas
    from fit_ctf_admin.widgets.designer.design_form import DesignForm
    from fit_ctf_admin.widgets.designer.tag_list_editor import TagListEditor

    async with app.run_test(size=(140, 50)) as pilot:
        await _goto(pilot, "designer-page")
        form = app.screen.query_one("#design-form", DesignForm)
        form.query_one("#service-add-btn", Button).press()
        await _settle(pilot)
        assert len(form.design.blocks) == 1

        # (a) switching the target kind refreshes the canvas
        app.screen.query_one("#design-target", Select).value = "project"
        await _settle(pilot)

        # (b) adding a secret refreshes the canvas again
        tags = app.screen.query_one("#secrets-tags", TagListEditor)
        tags.query_one("#tag-input", Input).value = "flag_x"
        tags.query_one("#tag-add-btn", Button).press()
        await _settle(pilot)
        assert "flag_x" in form.design.secrets

        # (c) applying service changes twice refreshes twice more
        form.query_one("#svc-ports", Input).value = "http:8080"
        form.query_one("#svc-apply-btn", Button).press()
        await _settle(pilot)
        form.query_one("#svc-apply-btn", Button).press()
        await _settle(pilot)

        canvas = app.screen.query_one("#designer-canvas", DesignCanvas)
        from fit_ctf_admin.widgets.designer.block_node import BlockNode

        assert len(canvas.query(BlockNode)) == len(form.design.blocks) == 1


async def test_secret_generate_button(app: AdminApp):
    import re as _re

    from fit_ctf_admin.screens.scenario_config_screen import ScenarioConfigScreen
    from fit_ctf_admin.widgets.kv_editor import KeyValueEditor, KVRow

    async with app.run_test(size=(140, 50)) as pilot:
        await _goto(pilot, "scenarios-page")
        app.screen.query_one("#target-project-select", Select).value = "intro_linux"
        await _settle(pilot)
        templates = app.screen.query_one("#scenario-templates-table", RefreshableTable)
        templates.move_cursor(row=templates.get_row_index("web_stack"))
        await pilot.click("#scenario-assign-btn")
        await _settle(pilot)
        assert isinstance(app.screen, ScenarioConfigScreen)

        secrets = app.screen.query_one("#secrets-editor", KeyValueEditor)
        row = secrets.query(KVRow).first()
        row.query_one(".kv-generate", Button).press()
        await _settle(pilot)
        value = row.query_one(".kv-value", Input).value
        assert _re.fullmatch(r"FLAG\{[A-Za-z0-9]{32}\}", value), value
        await pilot.click("#config-cancel-btn")
        await _settle(pilot)


async def test_compiled_preview_dialog(app: AdminApp):
    from textual.widgets import TextArea

    from fit_ctf_admin.screens.dialogs.text_dialog import TextDialog
    from fit_ctf_admin.screens.scenario_config_screen import ScenarioConfigScreen

    async with app.run_test(size=(140, 50)) as pilot:
        # store a designed scenario so preview mode has real compose text
        from fit_ctf_admin.scenario.design_model import ScenarioDesign

        design = ScenarioDesign(name="prev_scn")
        block = design.add_block("web", module_name="template")
        design.set_service_key(block.id, "web")
        block.ports = {"http": 8080}
        app.admin_core.gateway.store.designer_save(design.to_json())

        await _goto(pilot, "scenarios-page")
        app.screen.query_one("#target-project-select", Select).value = "intro_linux"
        await _settle(pilot)
        templates = app.screen.query_one("#scenario-templates-table", RefreshableTable)
        templates.move_cursor(row=templates.get_row_index("prev_scn"))
        await pilot.click("#scenario-assign-btn")
        await _settle(pilot)
        assert isinstance(app.screen, ScenarioConfigScreen)

        # fill the port in the YAML section, then preview
        yaml_area = app.screen.query_one("#services-yaml", TextArea)
        yaml_area.text = yaml_area.text.replace("http: ''", "http: '9001'")
        app.screen.query_one("#config-preview-btn", Button).press()
        await _settle(pilot)
        assert isinstance(app.screen, TextDialog)
        rendered = app.screen.query_one("#text-dialog-area", TextArea).text
        assert "9001:80" in rendered
        assert "<project>" in rendered  # compile-time placeholder


async def test_scenarios_view_template_dialog(app: AdminApp):
    from textual.widgets import TextArea

    from fit_ctf_admin.screens.dialogs.text_dialog import TextDialog

    async with app.run_test(size=(140, 50)) as pilot:
        await _goto(pilot, "scenarios-page")
        templates = app.screen.query_one("#scenario-templates-table", RefreshableTable)
        templates.move_cursor(row=templates.get_row_index("web_stack"))
        app.screen.query_one("#scenario-view-btn", Button).press()
        await _settle(pilot)
        assert isinstance(app.screen, TextDialog)
        assert "web_stack" in app.screen.query_one("#text-dialog-area", TextArea).text
        await pilot.click("#text-dialog-close-btn")
        await _settle(pilot)


async def test_projects_export_preview_shows_error(app: AdminApp):
    from fit_ctf_admin.screens.dialogs.input_dialog import InputDialog

    async with app.run_test(size=SIZE) as pilot:
        await _goto(pilot, "projects-page")
        table = app.screen.query_one("#projects-table", RefreshableTable)
        table.move_cursor(row=table.get_row_index("intro_linux"))
        app.screen.query_one("#projects-export-btn", Button).press()
        await pilot.pause()
        assert isinstance(app.screen, InputDialog)
        assert app.screen.query_one("#input-dialog-value", Input).value.endswith("_export.zip")
        await pilot.click("#input-dialog-ok-btn")
        await _settle(pilot)
        # preview mode: export raises AdminError -> surfaced as a notification,
        # app stays alive on the projects page
        assert table.row_count == 2


async def test_modules_edit_files_screen(app: AdminApp):
    from textual.widgets import TextArea

    from fit_ctf_admin.screens.module_files_screen import ModuleFilesScreen

    async with app.run_test(size=(140, 50)) as pilot:
        await _goto(pilot, "modules-page")
        table = app.screen.query_one("#modules-table", RefreshableTable)
        table.move_cursor(row=table.get_row_index("template"))
        app.screen.query_one("#modules-edit-btn", Button).press()
        await _settle(pilot)
        assert isinstance(app.screen, ModuleFilesScreen)

        area = app.screen.query_one("#module-file-area", TextArea)
        assert area.text.startswith("FROM ")
        area.text = area.text + "\n# tui edit\n"
        app.screen.query_one("#module-file-save-btn", Button).press()
        await _settle(pilot)
        store = app.admin_core.gateway.store
        assert store.module_files[("template", "Containerfile")].endswith("# tui edit\n")
        await pilot.click("#module-file-close-btn")
        await _settle(pilot)


async def test_modules_build_shows_log_dialog(app: AdminApp):
    from textual.widgets import TextArea

    from fit_ctf_admin.screens.dialogs.text_dialog import TextDialog

    async with app.run_test(size=(140, 50)) as pilot:
        await _goto(pilot, "modules-page")
        table = app.screen.query_one("#modules-table", RefreshableTable)
        table.move_cursor(row=table.get_row_index("template"))
        app.screen.query_one("#modules-build-btn", Button).press()
        await _settle(pilot)
        assert isinstance(app.screen, TextDialog)
        assert "preview mode" in app.screen.query_one("#text-dialog-area", TextArea).text
        await pilot.click("#text-dialog-close-btn")
        await _settle(pilot)


async def test_designer_env_vars_via_add_button(app: AdminApp):
    from fit_ctf_admin.widgets.designer.design_form import DesignForm
    from fit_ctf_admin.widgets.designer.preview_panel import PreviewPanel

    async with app.run_test(size=(140, 60)) as pilot:
        await _goto(pilot, "designer-page")
        form = app.screen.query_one("#design-form", DesignForm)
        form.query_one("#service-add-btn", Button).press()
        await _settle(pilot)

        env_editor = form.query_one("#svc-env-tags")
        env_editor.query_one("#tag-input", Input).value = "ADMIN"
        env_editor.query_one("#tag-add-btn", Button).press()
        await _settle(pilot)

        block = form.design.blocks[0]
        assert block.env_keys == ["ADMIN"]
        preview = app.screen.query_one("#designer-preview", PreviewPanel)
        assert "__env_map__ADMIN" in preview.query_one("#compose-preview").text

        # remove it again
        env_editor.query_one("#tag-list").highlighted = 0
        env_editor.query_one("#tag-remove-btn", Button).press()
        await _settle(pilot)
        assert block.env_keys == []
