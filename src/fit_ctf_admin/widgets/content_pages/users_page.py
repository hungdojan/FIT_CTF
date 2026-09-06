"""User management page."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Checkbox, Label

from fit_ctf_admin.dto import UserRow
from fit_ctf_admin.screens.dialogs.confirm_dialog import ConfirmDialog
from fit_ctf_admin.screens.dialogs.new_user_dialog import (
    NewUserDialog,
    NewUserRequest,
)
from fit_ctf_admin.screens.dialogs.secret_reveal_dialog import SecretRevealDialog
from fit_ctf_admin.widgets.core_widget import AdminPage
from fit_ctf_admin.widgets.refreshable_table import RefreshableTable

COLUMNS = ("Username", "Role", "Active", "Email", "Projects")


class UsersPage(AdminPage):
    def compose(self) -> ComposeResult:
        yield Label("Users", classes="page-title")
        with Horizontal(classes="page-toolbar"):
            yield Button("New user", variant="primary", id="users-new-btn")
            yield Button("Disable", id="users-disable-btn")
            yield Button("Delete", variant="error", id="users-delete-btn")
            yield Checkbox("Show inactive", id="users-show-inactive")
        yield RefreshableTable(id="users-table")

    def refresh_page(self) -> None:
        include_inactive = self.query_one("#users-show-inactive", Checkbox).value
        self.call_gateway(
            lambda: self.core.gateway.list_users(include_inactive),
            self._fill_table,
            group="users-load",
        )

    def _fill_table(self, rows: list[UserRow]) -> None:
        self.query_one("#users-table", RefreshableTable).set_data(
            COLUMNS,
            [
                (
                    row.username,
                    row.role,
                    "yes" if row.active else "no",
                    row.email,
                    ", ".join(row.projects),
                )
                for row in rows
            ],
            [row.username for row in rows],
        )

    @property
    def _selected_username(self) -> str | None:
        return self.query_one("#users-table", RefreshableTable).selected_key

    @on(Checkbox.Changed, "#users-show-inactive")
    def _filter_changed(self) -> None:
        self.refresh_page()

    @on(Button.Pressed, "#users-new-btn")
    def _new_user(self) -> None:
        self.app.push_screen(NewUserDialog(), self._handle_new_user)

    def _handle_new_user(self, request: NewUserRequest | None) -> None:
        if request is None:
            return
        self.call_gateway(
            lambda: self.core.gateway.create_user(
                request.username,
                request.password,
                generate_password=request.generate_password,
                email=request.email,
                role=request.role,
            ),
            self._user_created,
            group="users-mutate",
        )

    def _user_created(self, result: tuple[UserRow, str]) -> None:
        row, password = result
        self.app.push_screen(SecretRevealDialog(f"Password for `{row.username}`", password))
        self.refresh_page()

    @on(Button.Pressed, "#users-disable-btn")
    def _disable_user(self) -> None:
        username = self._selected_username
        if username is None:
            self.notify("Select a user first.", severity="warning")
            return
        self.app.push_screen(
            ConfirmDialog(
                f"Disable user `{username}`?",
                "The user is deactivated and all their enrollments are cancelled.",
                confirm_label="Disable",
            ),
            lambda confirmed: self._do_disable(username) if confirmed else None,
        )

    def _do_disable(self, username: str) -> None:
        self.call_gateway(
            lambda: self.core.gateway.disable_user(username),
            lambda _: self._mutation_done(f"User `{username}` disabled."),
            group="users-mutate",
        )

    @on(Button.Pressed, "#users-delete-btn")
    def _delete_user(self) -> None:
        username = self._selected_username
        if username is None:
            self.notify("Select a user first.", severity="warning")
            return
        self.app.push_screen(
            ConfirmDialog(
                f"Delete user `{username}`?",
                "Removes the user, their enrollments, and their home directory.",
            ),
            lambda confirmed: self._do_delete(username) if confirmed else None,
        )

    def _do_delete(self, username: str) -> None:
        self.call_gateway(
            lambda: self.core.gateway.delete_user(username),
            lambda _: self._mutation_done(f"User `{username}` deleted."),
            group="users-mutate",
        )

    def _mutation_done(self, message: str) -> None:
        self.notify(message)
        self.refresh_page()
